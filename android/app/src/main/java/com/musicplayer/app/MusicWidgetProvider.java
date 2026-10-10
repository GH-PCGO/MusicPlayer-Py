package com.musicplayer.app;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.RectF;
import android.widget.RemoteViews;

import java.io.File;
import java.io.FileOutputStream;

/**
 * 桌面小组件 (深色沉浸 · 网易云风):
 * 封面 + 歌名/歌手 + 上一首/播放暂停/下一首 + 今日·本周听歌时长。
 *
 * 播放状态由网页经 MainActivity → PlaybackService 推到这里; 封面落盘
 * (files/widget_cover.png) 以便进程被杀后冷启动恢复。控制按钮走
 * PendingIntent → PlaybackService("cmd:xxx") → 网页播放。
 */
public class MusicWidgetProvider extends AppWidgetProvider {
    private static final String PREF = "widget_state";
    private static final String COVER_FILE = "widget_cover.png";

    private static Bitmap sCover;
    private static String sTitle = "";
    private static String sArtist = "";
    private static boolean sPlaying = false;
    private static int sAccent = 0xFF1DB954;

    /** 网页 "正在播放" → 小组件。 */
    public static void push(Context c, String title, String artist,
                            boolean playing, String accentHex) {
        if (c == null) {
            return;
        }
        sTitle = title == null ? "" : title;
        sArtist = artist == null ? "" : artist;
        sPlaying = playing;
        int a = parseColor(accentHex);
        if (a != 0) {
            sAccent = a;
        }
        c.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
                .putString("title", sTitle).putString("artist", sArtist)
                .putBoolean("playing", sPlaying).putInt("accent", sAccent).apply();
        updateAll(c);
    }

    /** 封面到位 (已下载的原始 bitmap): 缩放圆角裁剪 + 落盘 + 刷新。 */
    public static void setCover(Context c, Bitmap src) {
        if (c == null) {
            return;
        }
        if (src == null) {
            sCover = null;
            updateAll(c);
            return;
        }
        float d = c.getResources().getDisplayMetrics().density;
        Bitmap rounded = roundCover(src, (int) (54 * d), (int) (12 * d));
        sCover = rounded;
        try {
            File f = new File(c.getFilesDir(), COVER_FILE);
            FileOutputStream out = new FileOutputStream(f);
            rounded.compress(Bitmap.CompressFormat.PNG, 100, out);
            out.close();
        } catch (Exception ignored) {
        }
        updateAll(c);
    }

    /** 主题色变化 → 小组件强调色 (播放按钮底色)。 */
    public static void setAccent(Context c, String hex) {
        if (c == null) {
            return;
        }
        int a = parseColor(hex);
        if (a == 0) {
            return;
        }
        sAccent = a;
        c.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit().putInt("accent", a).apply();
        updateAll(c);
    }

    public static void updateAll(Context c) {        if (c == null) {
            return;
        }
        AppWidgetManager mgr = AppWidgetManager.getInstance(c);
        if (mgr == null) {
            return;
        }
        int[] ids = mgr.getAppWidgetIds(new ComponentName(c, MusicWidgetProvider.class));
        if (ids == null || ids.length == 0) {
            return;
        }
        RemoteViews v = build(c);
        for (int id : ids) {
            mgr.updateAppWidget(id, v);
        }
    }

    @Override
    public void onUpdate(Context c, AppWidgetManager mgr, int[] ids) {
        loadState(c);
        RemoteViews v = build(c);
        for (int id : ids) {
            mgr.updateAppWidget(id, v);
        }
    }

    private static void loadState(Context c) {
        SharedPreferences sp = c.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        sTitle = sp.getString("title", "");
        sArtist = sp.getString("artist", "");
        sPlaying = sp.getBoolean("playing", false);
        sAccent = sp.getInt("accent", 0xFF1DB954);
    }

    private static RemoteViews build(Context c) {
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.music_widget);
        v.setTextViewText(R.id.wTitle,
                sTitle.isEmpty() ? c.getString(R.string.widget_idle) : sTitle);
        v.setTextViewText(R.id.wArtist, sArtist);
        v.setTextViewText(R.id.wStats, ListenStats.widgetSummary(c));

        Bitmap cover = sCover;
        if (cover == null) {
            File f = new File(c.getFilesDir(), COVER_FILE);
            if (f.exists()) {
                cover = BitmapFactory.decodeFile(f.getAbsolutePath());
                sCover = cover;
            }
        }
        if (cover != null) {
            v.setImageViewBitmap(R.id.wCover, cover);
        }
        v.setImageViewBitmap(R.id.wPlay, playPause(c, sAccent, sPlaying));

        v.setOnClickPendingIntent(R.id.wPrev, cmd(c, "prev", 11));
        v.setOnClickPendingIntent(R.id.wPlay, cmd(c, "toggle", 12));
        v.setOnClickPendingIntent(R.id.wNext, cmd(c, "next", 13));

        Intent open = new Intent(c, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        v.setOnClickPendingIntent(R.id.wRoot, PendingIntent.getActivity(c, 9, open, flags()));
        return v;
    }

    private static PendingIntent cmd(Context c, String action, int code) {
        Intent i = new Intent(c, PlaybackService.class);
        i.setAction("cmd:" + action);
        return PendingIntent.getService(c, code, i, flags());
    }

    private static int flags() {
        return PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
    }

    private static int parseColor(String hex) {
        if (hex == null || hex.isEmpty()) {
            return 0;
        }
        try {
            return Color.parseColor(hex.startsWith("#") ? hex : "#" + hex);
        } catch (Exception e) {
            return 0;
        }
    }

    private static Bitmap roundCover(Bitmap src, int size, int radius) {
        Bitmap out = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(out);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        int sw = src.getWidth(), sh = src.getHeight();
        if (sw <= 0 || sh <= 0) {
            return out;
        }
        float scale = Math.max((float) size / sw, (float) size / sh);
        float dw = sw * scale, dh = sh * scale;
        float left = (size - dw) / 2f, top = (size - dh) / 2f;
        Path clip = new Path();
        clip.addRoundRect(new RectF(0, 0, size, size), radius, radius, Path.Direction.CW);
        cv.clipPath(clip);
        cv.drawBitmap(src, new Rect(0, 0, sw, sh),
                new RectF(left, top, left + dw, top + dh), p);
        return out;
    }

    /** 主题色圆底 + 白色 播放/暂停 图形。 */
    private static Bitmap playPause(Context c, int color, boolean playing) {
        int size = (int) (46 * c.getResources().getDisplayMetrics().density);
        if (size < 2) {
            size = 92;
        }
        Bitmap bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas cv = new Canvas(bmp);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setColor(color);
        cv.drawCircle(size / 2f, size / 2f, size / 2f, p);
        p.setColor(Color.WHITE);
        float u = size / 46f;
        if (playing) {
            cv.drawRect(15 * u, 14 * u, 21 * u, 32 * u, p);
            cv.drawRect(25 * u, 14 * u, 31 * u, 32 * u, p);
        } else {
            Path path = new Path();
            path.moveTo(17 * u, 13 * u);
            path.lineTo(17 * u, 33 * u);
            path.lineTo(34 * u, 23 * u);
            path.close();
            cv.drawPath(path, p);
        }
        return bmp;
    }
}
