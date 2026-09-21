package com.musicplayer.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.MediaMetadata;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * 播放前台服务: 让网页里的音频在息屏 / 切后台时继续播, 并提供通知栏 /
 * 锁屏 / 耳机的播放控制 (MediaSession)。
 *
 * 音乐本身仍由 WebView 播放, 这里只负责:
 *  - 常驻通知 (前台服务, 进程不被系统冻结/回收 → 连播不会中途停);
 *  - MediaSession 元数据 + 播放状态 (锁屏、蓝牙耳机按键);
 *  - 播放期间持有 PARTIAL_WAKE_LOCK (CPU 不睡, 换歌/拉流不被卡住);
 *  - 把控制指令回传给网页 (app.mediaCmd)。
 */
public class PlaybackService extends Service {
    private static final String CHANNEL_ID = "music_playback";
    private static final int NOTIF_ID = 8801;

    private MediaSession session;
    private PowerManager.WakeLock wake;
    private String title = "";
    private String artist = "";
    private String cover = "";
    private String loadedCover = null;   // 已发起加载的封面 URL
    private Bitmap art;
    private boolean playing = false;
    private boolean fgActive = false;    // 当前是否处于前台服务状态

    /** 网页调用: 更新 "正在播放" 信息。 */
    public static void update(Context ctx, String title, String artist,
                              boolean playing, String cover) {
        Intent i = new Intent(ctx, PlaybackService.class);
        i.setAction("update");
        i.putExtra("title", title);
        i.putExtra("artist", artist);
        i.putExtra("cover", cover);
        i.putExtra("playing", playing);
        // 只有真正在播时才用 startForegroundService (它强制 5s 内 startForeground);
        // 暂停态的更新走普通 startService, 避免"起来就得转前台"的强约束。
        start(ctx, i, playing);
    }

    /** 网页调用: 停止播放 / 清空通知。 */
    public static void clear(Context ctx) {
        Intent i = new Intent(ctx, PlaybackService.class);
        i.setAction("stop");
        start(ctx, i, false);
    }

    private static void start(Context ctx, Intent i, boolean foreground) {
        try {
            if (foreground && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(i);
            } else {
                ctx.startService(i);
            }
        } catch (Exception ignored) {
            // 后台启动限制等: 服务起不来也不该影响网页播放
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        session = new MediaSession(this, "MusicPlayer");
        session.setCallback(new MediaSession.Callback() {
            @Override
            public void onPlay() {
                send("play");
            }

            @Override
            public void onPause() {
                send("pause");
            }

            @Override
            public void onStop() {
                send("pause");
            }

            @Override
            public void onSkipToNext() {
                send("next");
            }

            @Override
            public void onSkipToPrevious() {
                send("prev");
            }
        });
        session.setActive(true);
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,
                                  "musicplayer:playback");
            wake.setReferenceCounted(false);
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? null : intent.getAction();
        if (action != null && action.startsWith("cmd:")) {
            send(action.substring(4));          // 通知栏按钮 → 交给网页执行
            return START_NOT_STICKY;
        }
        if ("stop".equals(action)) {
            releaseWake();
            if (session != null) {
                session.setActive(false);
            }
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        if (intent != null) {
            title = nvl(intent.getStringExtra("title"));
            artist = nvl(intent.getStringExtra("artist"));
            cover = nvl(intent.getStringExtra("cover"));
            playing = intent.getBooleanExtra("playing", false);
        }
        if (playing) {
            acquireWake();
        } else {
            releaseWake();
        }
        pushState();
        Notification notif = buildNotification();
        // 只要是被 startForegroundService 拉起来的, 就必须在 5s 内
        // startForeground(), 否则系统会抛 ForegroundServiceDidNotStartInTime
        // 把整个进程杀掉。所以这里先无条件转前台 (幂等), 不在播放再降级。
        startForeground(NOTIF_ID, notif);
        fgActive = true;
        if (!playing) {
            stopForeground(false);   // 降级为可划掉的普通通知, 服务留着待命
            fgActive = false;
        }
        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        releaseWake();
        if (session != null) {
            session.release();
            session = null;
        }
        super.onDestroy();
    }

    // ------------------------------------------------------------ 内部实现
    private static String nvl(String s) {
        return s == null ? "" : s;
    }

    /** 把控制指令回传给网页 (网页里由 app.mediaCmd 处理)。 */
    private void send(String cmd) {
        MainActivity a = MainActivity.get();
        if (a != null) {
            a.evalJs("window.app && app.mediaCmd('" + cmd + "')");
        }
    }

    private void acquireWake() {
        try {
            if (wake != null && !wake.isHeld()) {
                wake.acquire(3 * 60 * 60 * 1000L);   // 兜底上限 3 小时
            }
        } catch (Exception ignored) {
        }
    }

    private void releaseWake() {
        try {
            if (wake != null && wake.isHeld()) {
                wake.release();
            }
        } catch (Exception ignored) {
        }
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationManager nm =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null || nm.getNotificationChannel(CHANNEL_ID) != null) {
            return;
        }
        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, getString(R.string.playback_channel),
                NotificationManager.IMPORTANCE_LOW);
        ch.setShowBadge(false);
        ch.setSound(null, null);
        nm.createNotificationChannel(ch);
    }

    /** 元数据 + 播放状态 (锁屏 / 耳机按键靠这个)。 */
    private void pushState() {
        if (session == null) {
            return;
        }
        MediaMetadata.Builder m = new MediaMetadata.Builder();
        if (!title.isEmpty()) {
            m.putString(MediaMetadata.METADATA_KEY_TITLE, title);
            m.putString(MediaMetadata.METADATA_KEY_ARTIST, artist);
            if (art != null) {
                m.putBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART, art);
            }
        }
        session.setMetadata(m.build());
        long actions = PlaybackState.ACTION_PLAY | PlaybackState.ACTION_PAUSE
                | PlaybackState.ACTION_PLAY_PAUSE | PlaybackState.ACTION_STOP
                | PlaybackState.ACTION_SKIP_TO_NEXT
                | PlaybackState.ACTION_SKIP_TO_PREVIOUS;
        session.setPlaybackState(new PlaybackState.Builder()
                .setActions(actions)
                .setState(playing ? PlaybackState.STATE_PLAYING
                                  : PlaybackState.STATE_PAUSED, 0, 1.0f)
                .build());
        if (cover.isEmpty()) {
            loadedCover = null;
            art = null;
        } else if (!cover.equals(loadedCover)) {
            loadedCover = cover;
            loadArt(cover);
        }
    }

    private Notification buildNotification() {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 0, open, pendingFlags());

        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        b.setSmallIcon(android.R.drawable.ic_media_play)
                .setContentTitle(title.isEmpty() ? getString(R.string.app_name) : title)
                .setContentText(artist)
                .setContentIntent(pi)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .setOnlyAlertOnce(true)
                .setOngoing(playing);
        if (art != null) {
            b.setLargeIcon(art);
        }
        b.addAction(notifAction(android.R.drawable.ic_media_previous, "prev", 1));
        b.addAction(notifAction(playing ? android.R.drawable.ic_media_pause
                                        : android.R.drawable.ic_media_play,
                                playing ? "pause" : "play", 2));
        b.addAction(notifAction(android.R.drawable.ic_media_next, "next", 3));
        if (session != null) {
            b.setStyle(new Notification.MediaStyle()
                    .setMediaSession(session.getSessionToken())
                    .setShowActionsInCompactView(0, 1, 2));
        }
        return b.build();
    }

    /** 通知按钮 → 服务自己处理 (再转给网页)。 */
    private Notification.Action notifAction(int icon, String cmd, int code) {
        Intent i = new Intent(this, PlaybackService.class);
        i.setAction("cmd:" + cmd);
        PendingIntent pi = PendingIntent.getService(this, code, i, pendingFlags());
        return new Notification.Action.Builder(icon, cmd, pi).build();
    }

    private int pendingFlags() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                ? PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
                : PendingIntent.FLAG_UPDATE_CURRENT;
    }

    /** 封面异步下载 (失败就算了, 不影响播放)。 */
    private void loadArt(final String url) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                Bitmap bmp = null;
                HttpURLConnection conn = null;
                try {
                    conn = (HttpURLConnection) new URL(url).openConnection();
                    conn.setConnectTimeout(8000);
                    conn.setReadTimeout(8000);
                    InputStream in = conn.getInputStream();
                    bmp = BitmapFactory.decodeStream(in);
                    in.close();
                } catch (Exception ignored) {
                } finally {
                    if (conn != null) {
                        conn.disconnect();
                    }
                }
                final Bitmap got = bmp;
                new Handler(Looper.getMainLooper()).post(new Runnable() {
                    @Override
                    public void run() {
                        if (!url.equals(loadedCover)) {
                            return;          // 期间已经换歌了
                        }
                        art = got;
                        pushState();
                        if (fgActive) {
                            NotificationManager nm = (NotificationManager)
                                    getSystemService(Context.NOTIFICATION_SERVICE);
                            if (nm != null) {
                                nm.notify(NOTIF_ID, buildNotification());
                            }
                        }
                    }
                });
            }
        }).start();
    }
}
