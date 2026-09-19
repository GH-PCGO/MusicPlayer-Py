package com.musicplayer.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

public class MainActivity extends Activity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

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
        webView.setWebViewClient(new WebViewClient());
        setContentView(webView);
        webView.loadUrl("http://127.0.0.1:" + port + "/");
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
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}