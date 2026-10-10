package com.musicplayer.app;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Calendar;

/**
 * 听歌时长统计: 今日 / 本周累计毫秒数。
 *
 * 由 PlaybackService 在播放期间按 tick 累加; 跨天(自然日)、跨周(周一为界)
 * 自动归零。数据落在 SharedPreferences("listen_stats"), 供桌面小组件读取。
 */
public class ListenStats {
    private static final String PREF = "listen_stats";

    /** 累加一段播放时长 (ms)。 */
    public static void add(Context c, long ms) {
        if (c == null || ms <= 0) {
            return;
        }
        SharedPreferences sp = c.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        long now = System.currentTimeMillis();
        String day = dayKey(now);
        String week = weekKey(now);
        long today = day.equals(sp.getString("day", "")) ? sp.getLong("today_ms", 0) : 0;
        long weekMs = week.equals(sp.getString("wstart", "")) ? sp.getLong("week_ms", 0) : 0;
        sp.edit()
                .putString("day", day)
                .putLong("today_ms", today + ms)
                .putString("wstart", week)
                .putLong("week_ms", weekMs + ms)
                .apply();
    }

    public static long todayMs(Context c) {
        SharedPreferences sp = c.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        return dayKey(System.currentTimeMillis()).equals(sp.getString("day", ""))
                ? sp.getLong("today_ms", 0) : 0;
    }

    public static long weekMs(Context c) {
        SharedPreferences sp = c.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        return weekKey(System.currentTimeMillis()).equals(sp.getString("wstart", ""))
                ? sp.getLong("week_ms", 0) : 0;
    }

    /** "今日 12 分钟 · 本周 1 小时 20 分" */
    public static String summary(Context c) {
        return "今日 " + human(todayMs(c)) + " · 本周 " + human(weekMs(c));
    }

    /** 小组件用紧凑文案: "今日 12分 · 本周 34分" */
    public static String widgetSummary(Context c) {
        return "今日 " + compact(todayMs(c)) + " · 本周 " + compact(weekMs(c));
    }

    private static String compact(long ms) {
        long min = ms / 60000L;
        if (min < 60) {
            return min + "分";
        }
        long h = min / 60, m = min % 60;
        return m == 0 ? (h + "时") : (h + "时" + m + "分");
    }

    public static String human(long ms) {
        long min = ms / 60000L;
        if (min < 1) {
            return "0 分钟";
        }
        if (min < 60) {
            return min + " 分钟";
        }
        long h = min / 60, m = min % 60;
        return m == 0 ? (h + " 小时") : (h + " 小时 " + m + " 分");
    }

    private static String dayKey(long t) {
        Calendar c = Calendar.getInstance();
        c.setTimeInMillis(t);
        return pad(c.get(Calendar.YEAR)) + "-" + pad(c.get(Calendar.MONTH) + 1)
                + "-" + pad(c.get(Calendar.DAY_OF_MONTH));
    }

    /** 本周周一 的日期键 */
    private static String weekKey(long t) {
        Calendar c = Calendar.getInstance();
        c.setTimeInMillis(t);
        c.setFirstDayOfWeek(Calendar.MONDAY);
        int dow = c.get(Calendar.DAY_OF_WEEK);            // 周日=1 ... 周六=7
        int back = (dow + 5) % 7;                          // 到周一需要回退的天数
        c.add(Calendar.DAY_OF_MONTH, -back);
        return pad(c.get(Calendar.YEAR)) + "-" + pad(c.get(Calendar.MONTH) + 1)
                + "-" + pad(c.get(Calendar.DAY_OF_MONTH));
    }

    private static String pad(int n) {
        return n < 10 ? "0" + n : String.valueOf(n);
    }
}
