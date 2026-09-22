package com.musicplayer.app;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.BitmapRegionDecoder;
import android.graphics.Rect;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.MediaStore;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.google.android.gms.tasks.OnFailureListener;
import com.google.android.gms.tasks.OnSuccessListener;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.lang.ref.WeakReference;

public class MainActivity extends Activity {
    private static final int REQ_PICK_IMAGE = 1001;

    private WebView webView;
    private FrameLayout root;
    private View fullView;                 // 视频全屏时的自定义视图
    private WebChromeClient.CustomViewCallback fullCallback;
    private TextRecognizer ocr;            // 歌单截图 OCR (懒加载)

    private static WeakReference<MainActivity> sRef;

    /** 供 PlaybackService 回调 (通知/锁屏按键 → 网页)。 */
    public static MainActivity get() {
        return sRef == null ? null : sRef.get();
    }

    /** 在 WebView 里执行一段 JS (主线程)。 */
    public void evalJs(final String js) {
        final WebView w = webView;
        if (w == null) {
            return;
        }
        w.post(new Runnable() {
            @Override
            public void run() {
                try {
                    w.evaluateJavascript(js, null);
                } catch (Exception ignored) {
                }
            }
        });
    }

    /** 网页 → 原生: 同步 "正在播放" 状态, 让前台服务/通知/锁屏跟着更新。 */
    private class JsBridge {
        @JavascriptInterface
        public void setNowPlaying(String title, String artist,
                                  boolean playing, String cover) {
            PlaybackService.update(MainActivity.this, title, artist, playing, cover);
        }

        @JavascriptInterface
        public void clear() {
            PlaybackService.clear(MainActivity.this);
        }

        /** 网页调用: 选一张歌单截图 → 离线 OCR → 文字回传给网页。 */
        @JavascriptInterface
        public void pickImage() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    openImagePicker();
                }
            });
        }
    }

    // -------------------------------------------------------- 歌单截图 OCR
    private void openImagePicker() {
        // Android 13+ 用系统相册选择器 (无"打开方式"二选一弹窗); 低版本退回 ACTION_PICK
        try {
            Intent i;
            if (Build.VERSION.SDK_INT >= 33) {
                i = new Intent(MediaStore.ACTION_PICK_IMAGES);
            } else {
                i = new Intent(Intent.ACTION_PICK,
                        MediaStore.Images.Media.EXTERNAL_CONTENT_URI);
            }
            startActivityForResult(i, REQ_PICK_IMAGE);
            return;
        } catch (Exception ignored) {
        }
        try {
            Intent i = new Intent(Intent.ACTION_PICK,
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI);
            startActivityForResult(i, REQ_PICK_IMAGE);
            return;
        } catch (Exception ignored) {
        }
        try {
            Intent i = new Intent(Intent.ACTION_GET_CONTENT);
            i.setType("image/*");
            startActivityForResult(i, REQ_PICK_IMAGE);
        } catch (Exception e) {
            jsOcr(null, null, "无法打开图片选择器");
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != REQ_PICK_IMAGE) {
            return;
        }
        if (res != RESULT_OK || data == null || data.getData() == null) {
            jsOcr(null, null, "");                 // 用户取消
            return;
        }
        runOcr(data.getData());
    }

    /** 把图片交给 ML Kit 识别, 结果整段回传网页 (保留换行, 网页再解析)。

    长截屏 (歌单列表) 往往是一张又长又窄的图, 整张解码容易 OOM, ML Kit 对
    超长图也常常什么都识别不出; 所以先拷贝到缓存文件, 再**按高度分块**逐块
    识别 (块间留重叠), 最后把文字和"带坐标的行"合并成一份回传。
    */
    private static final int TILE_H = 1600;     // 每块高度 (px)
    private static final int TILE_OVERLAP = 200; // 块间重叠, 避免把一条切两半

    private void runOcr(final Uri uri) {
        File tmp = null;
        try {
            tmp = new File(getCacheDir(), "ocr_src.jpg");
            InputStream in = getContentResolver().openInputStream(uri);
            FileOutputStream out = new FileOutputStream(tmp);
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
            }
            out.close();
            if (in != null) {
                in.close();
            }
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            BitmapFactory.decodeFile(tmp.getAbsolutePath(), o);
            final int w = o.outWidth, h = o.outHeight;
            if (w <= 0 || h <= 0) {
                jsOcr(null, null, "图片读取失败（格式不支持？）");
                tmp.delete();
                return;
            }
            if (ocr == null) {
                ocr = TextRecognition.getClient(
                        new ChineseTextRecognizerOptions.Builder().build());
            }
            final JSONArray lines = new JSONArray();
            final StringBuilder text = new StringBuilder();
            final File src = tmp;
            recognizeTile(src, w, h, 0, lines, text);
        } catch (Exception e) {
            if (tmp != null) {
                tmp.delete();
            }
            jsOcr(null, null, "识别出错: " + e.getMessage());
        }
    }

    /** 识别第 y0 行开始的一块; 还有下一块就继续, 否则合并回传。 */
    private void recognizeTile(final File src, final int w, final int h, final int y0,
                               final JSONArray lines, final StringBuilder text) {
        int y1 = Math.min(h, y0 + TILE_H + TILE_OVERLAP);
        Bitmap tile = null;
        try {
            @SuppressWarnings("deprecation")
            BitmapRegionDecoder dec = BitmapRegionDecoder.newInstance(
                    new FileInputStream(src), false);
            tile = dec.decodeRegion(new Rect(0, y0, w, y1), null);
            dec.recycle();
        } catch (Exception e) {
            tile = null;
        }
        if (tile == null) {
            finishOcr(src, lines, text, "长图分块读取失败");
            return;
        }
        final Bitmap bmp = tile;
        final int offset = y0;
        ocr.process(InputImage.fromBitmap(bmp, 0))
                .addOnSuccessListener(new OnSuccessListener<Text>() {
                    @Override
                    public void onSuccess(Text t) {
                        appendOcr(t, offset, lines, text);
                        bmp.recycle();
                        int next = y0 + TILE_H;
                        if (next >= h) {
                            finishOcr(src, lines, text, null);
                        } else {
                            recognizeTile(src, w, h, next, lines, text);
                        }
                    }
                })
                .addOnFailureListener(new OnFailureListener() {
                    @Override
                    public void onFailure(Exception e) {
                        bmp.recycle();
                        finishOcr(src, lines, text, "识别失败: " + e.getMessage());
                    }
                });
    }

    private void finishOcr(File src, JSONArray lines, StringBuilder text, String err) {
        try {
            if (src != null) {
                src.delete();
            }
        } catch (Exception ignored) {
        }
        if (err != null && lines.length() == 0) {
            jsOcr(null, null, err);
            return;
        }
        jsOcr(text.toString(), lines.toString(), err);
    }

    /** 把一块的识别结果追加进来 (坐标按块偏移还原到整图坐标系)。 */
    private void appendOcr(Text t, int offset, JSONArray lines, StringBuilder text) {
        if (t == null) {
            return;
        }
        String s = t.getText();
        if (s != null && s.trim().length() > 0) {
            if (text.length() > 0) {
                text.append("\n");
            }
            text.append(s);
        }
        for (Text.TextBlock block : t.getTextBlocks()) {
            for (Text.Line line : block.getLines()) {
                Rect r = line.getBoundingBox();
                if (r == null) {
                    continue;
                }
                JSONArray one = new JSONArray();
                one.put(line.getText());
                one.put(r.left);
                one.put(r.top + offset);
                one.put(r.right);
                one.put(r.bottom + offset);
                lines.put(one);
            }
        }
    }

    private void jsOcr(String text, String lines, String err) {
        try {
            String js = "window.app && app.onOcrText("
                    + (text == null ? "null" : JSONObject.quote(text)) + ", "
                    + (lines == null ? "null" : JSONObject.quote(lines)) + ", "
                    + (err == null ? "null" : JSONObject.quote(err)) + ")";
            evalJs(js);
        } catch (Exception ignored) {
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sRef = new WeakReference<>(this);

        // 1) 启动 Python 运行时
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        Python py = Python.getInstance();

        // 2) 把内置的 Web 界面从 assets 拷贝到可写目录, 交 Python 服务器托管
        File www = copyAssetsToFiles("www");
        py.getModule("server").callAttr("set_web_dir", www.getAbsolutePath());

        // 2.5) 注入 Context: 下载完成后把 mp3 发布到系统媒体库
        //      Music/音乐下载器/ (免存储权限; 桌面环境无此调用会自动降级)
        py.getModule("server").callAttr("set_android_storage", this,
                                        "Music/音乐下载器");

        // 3) 启动本地 HTTP 服务 (127.0.0.1), 返回实际端口
        PyObject portObj = py.getModule("server").callAttr("start", 8760);
        int port = portObj.toInt();

        // 4) WebView 加载本机服务
        WebView.setWebContentsDebuggingEnabled(true);   // 允许 adb 远程调试 (仅调试用)
        webView = new WebView(this);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        webView.setWebViewClient(new WebViewClient());
        webView.addJavascriptInterface(new JsBridge(), "AndroidPlayer");
        requestNotifPermission();

        // 视频全屏支持: 进入时切横屏 + 沉浸式, 退出时还原
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onShowCustomView(View view,
                                         CustomViewCallback callback) {
                if (fullView != null) {
                    callback.onCustomViewHidden();
                    return;
                }
                fullView = view;
                fullCallback = callback;
                view.setBackgroundColor(0xFF000000);
                root.addView(view, new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT));
                webView.setVisibility(View.GONE);
                enterLandscapeFullscreen(view);
            }

            @Override
            public void onHideCustomView() {
                exitFullscreenView();
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                request.grant(request.getResources());
            }
        });

        root = new FrameLayout(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);
        webView.loadUrl("http://127.0.0.1:" + port + "/");
    }

    /** Android 13+ 需要运行时授权才能显示播放通知 (拒绝也不影响播放)。 */
    private void requestNotifPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return;
        }
        if (checkSelfPermission("android.permission.POST_NOTIFICATIONS")
                == PackageManager.PERMISSION_GRANTED) {
            return;
        }
        requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1);
    }

    /** 进入横屏全屏: 强制横屏 + 隐藏状态栏/导航栏 (沉浸式)。 */
    @SuppressWarnings("deprecation")
    private void enterLandscapeFullscreen(View view) {
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        view.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    /** 退出全屏: 移除全屏视图 + 还原竖屏 + 恢复状态栏。 */
    @SuppressWarnings("deprecation")
    private void exitFullscreenView() {
        if (fullView == null) {
            return;
        }
        root.removeView(fullView);
        fullView = null;
        webView.setVisibility(View.VISIBLE);
        webView.setSystemUiVisibility(View.SYSTEM_UI_FLAG_VISIBLE);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        if (fullCallback != null) {
            try {
                fullCallback.onCustomViewHidden();
            } catch (Exception ignored) {
            }
            fullCallback = null;
        }
    }

    private File copyAssetsToFiles(String dir) {
        File out = new File(getFilesDir(), dir);
        if (out.exists()) {
            // 每次都覆盖, 保证 APK 内网页资源更新能生效
            out.delete();
        }
        out.mkdirs();
        try {
            String[] names = getAssets().list(dir);
            for (String name : names) {
                InputStream is = null;
                FileOutputStream fos = null;
                try {
                    is = getAssets().open(dir + "/" + name);
                    fos = new FileOutputStream(new File(out, name));
                    byte[] buf = new byte[8192];
                    int c;
                    while ((c = is.read(buf)) > 0) {
                        fos.write(buf, 0, c);
                    }
                } finally {
                    if (fos != null) fos.close();
                    if (is != null) is.close();
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return out;
    }

    @Override
    protected void onPause() {
        super.onPause();
        // 故意不调用 webView.onPause(): 切后台/息屏后网页里的音频要继续播,
        // 连播 (ended → 下一首) 也依赖 WebView 保持运行。
        // 常驻由 PlaybackService 前台服务保证。
    }

    @Override
    public void onBackPressed() {
        // 视频全屏时, 返回键先退出全屏
        if (fullView != null) {
            exitFullscreenView();
            return;
        }
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
