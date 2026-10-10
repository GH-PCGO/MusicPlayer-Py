package com.musicplayer.app;

import android.animation.ValueAnimator;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.TextUtils;
import android.text.style.ForegroundColorSpan;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * 桌面歌词悬浮窗 —— 参考酷狗音乐:
 *  · 逐字点亮 (已唱字用主题色, 未唱亮白); 长句自动换行(最多2行), 不截断;
 *  · 当前句 + 下一句, 深色圆角卡片;
 *  · 点击展开控制条: 上一句 / 播放暂停 / 下一句 · 字号− / 字号+ · 锁定 · 打开应用 · 关闭;
 *  · 可拖动(位置记忆), 锁定后不可拖动。
 *
 * 仅应用切后台时由 MainActivity 显示; 播放态 / 歌词 / 进度由网页推送。
 */
public class LyricOverlay {

    public interface Host {
        void onCommand(String cmd);   // prev / pause / play / next
        void onClose();
    }

    private static final int BG = 0xF01A1B22;
    private static final int STROKE = 0x1FFFFFFF;
    private static final int BASE = 0xF2FFFFFF;    // 未唱 (亮白)
    private static final int NEXT_C = 0x66FFFFFF;  // 下一句 (暗)
    private static final int ICON = 0xE8FFFFFF;

    private final Context ctx;
    private final WindowManager wm;
    private final SharedPreferences pref;
    private final int screenW, screenH;
    private final int slop;

    private Host host;
    private int accent = 0xFF2CA8F5;

    private View root;
    private LinearLayout lyricBox;
    private TextView curView, nextView;
    private LinearLayout toolbar;
    private GlyphView playBtn;
    private TextView lockBtn;
    private GradientDrawable cardBg;
    private boolean touching = false;

    private WindowManager.LayoutParams lp;
    private float downRawX, downRawY;
    private int origX, origY;
    private boolean moved;

    private String curText = "", nextText = "";
    private float progress = 1f, shown = 1f;
    private boolean playing = false;
    private boolean locked;
    private int fontSp = 16;
    private ValueAnimator anim;

    public LyricOverlay(Context context) {
        ctx = context;
        wm = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        pref = context.getSharedPreferences("lyric_overlay", Context.MODE_PRIVATE);
        int sw = context.getResources().getDisplayMetrics().widthPixels;
        int sh = context.getResources().getDisplayMetrics().heightPixels;
        try {
            android.graphics.Point pt = new android.graphics.Point();
            wm.getDefaultDisplay().getRealSize(pt);
            if (pt.x > 0) sw = pt.x;
            if (pt.y > 0) sh = pt.y;
        } catch (Exception ignored) {
        }
        screenW = sw;
        screenH = sh;
        slop = ViewConfiguration.get(context).getScaledTouchSlop();
        locked = pref.getBoolean("locked", false);
        fontSp = pref.getInt("font", 16);
    }

    public void setHost(Host h) {
        host = h;
    }

    public void setAccent(int color) {
        accent = color;
        applyKaraoke();
        if (playBtn != null) {
            playBtn.setColor(accent);
        }
    }

    public boolean isShowing() {
        return root != null;
    }

    private int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                ctx.getResources().getDisplayMetrics());
    }

    private int sp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, v,
                ctx.getResources().getDisplayMetrics());
    }

    // ------------------------------------------------------------- 显示/隐藏
    public void show() {
        if (root != null || wm == null) {
            return;
        }
        buildView();
        applyText();
        lp = new WindowManager.LayoutParams();
        lp.type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
        lp.format = PixelFormat.TRANSLUCENT;
        lp.flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN;
        lp.gravity = Gravity.TOP | Gravity.START;
        lp.width = WindowManager.LayoutParams.WRAP_CONTENT;
        lp.height = WindowManager.LayoutParams.WRAP_CONTENT;
        lp.x = pref.getInt("x", dp(14));
        lp.y = pref.getInt("y", Math.round(screenH * 0.12f));
        clamp();
        try {
            wm.addView(root, lp);
        } catch (Exception e) {
            root = null;
            return;
        }
        root.post(new Runnable() {
            @Override
            public void run() {
                fitOnScreen();
            }
        });
    }

    public void hide() {
        if (root == null) {
            return;
        }
        if (anim != null) {
            anim.cancel();
        }
        try {
            wm.removeView(root);
        } catch (Exception ignored) {
        }
        root = null;
    }

    // ------------------------------------------------------------- 内容更新
    public void update(String cur, String next, float prog, boolean isPlaying) {
        curText = TextUtils.isEmpty(cur) ? "♪ 音乐下载器" : cur;
        nextText = TextUtils.isEmpty(next) ? "" : next;
        progress = Math.max(0f, Math.min(1f, prog));
        playing = isPlaying;
        applyText();
        animateTo(progress);
        if (playBtn != null) {
            playBtn.setKind(playing ? GlyphView.PAUSE : GlyphView.PLAY);
        }
    }

    private void applyText() {
        if (curView == null) {
            return;
        }
        int cap = screenW - dp(64);
        curView.setTextSize(TypedValue.COMPLEX_UNIT_PX, sp(fontSp));
        sizeLine(curView, curText, cap, 2);
        if (TextUtils.isEmpty(nextText)) {
            nextView.setVisibility(View.GONE);
        } else {
            nextView.setVisibility(View.VISIBLE);
            nextView.setTextSize(TypedValue.COMPLEX_UNIT_PX, sp(Math.max(10, fontSp - 4f)));
            sizeLine(nextView, nextText, cap, 1);
            nextView.setText(nextText);
        }
        applyKaraoke();
    }

    /** 短句按文字宽度收窄; 长句固定到上限并自动换行 (maxLines 行), 超出才省略。 */
    private void sizeLine(TextView tv, String text, int cap, int maxLines) {
        tv.setSingleLine(false);
        tv.setMaxLines(maxLines);
        tv.setEllipsize(TextUtils.TruncateAt.END);
        float tw = tv.getPaint().measureText(text);
        if (tw + dp(8) <= cap) {
            if (maxLines == 1) {
                tv.setSingleLine(true);
            }
            tv.setWidth((int) Math.ceil(tw) + dp(8));
        } else {
            tv.setWidth(cap);
        }
    }

    /** 逐字点亮: 已唱前缀用主题色, 其余亮白。 */
    private void applyKaraoke() {
        if (curView == null) {
            return;
        }
        int n = curText.length();
        int lit = Math.round(shown * n);
        SpannableString ss = new SpannableString(curText);
        if (lit > 0) {
            ss.setSpan(new ForegroundColorSpan(accent), 0, Math.min(lit, n),
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        }
        curView.setText(ss);
        curView.setTextColor(BASE);
    }

    private void animateTo(float target) {
        if (anim != null) {
            anim.cancel();
        }
        anim = ValueAnimator.ofFloat(shown, target);
        anim.setDuration(240);
        anim.addUpdateListener(new ValueAnimator.AnimatorUpdateListener() {
            @Override
            public void onAnimationUpdate(ValueAnimator a) {
                shown = (Float) a.getAnimatedValue();
                applyKaraoke();
            }
        });
        anim.start();
    }

    // ------------------------------------------------------------- 视图构建
    private void buildView() {
        LinearLayout box = new LinearLayout(ctx);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(18), dp(11), dp(18), dp(11));
        cardBg = new GradientDrawable();
        cardBg.setColor(0x00000000);          // 默认透明, 只有交互/展开时才有卡片底
        cardBg.setCornerRadius(dp(22));
        box.setBackground(cardBg);
        box.setElevation(0f);

        lyricBox = new LinearLayout(ctx);
        lyricBox.setOrientation(LinearLayout.VERTICAL);
        lyricBox.setGravity(Gravity.CENTER_HORIZONTAL);
        lyricBox.setPadding(dp(4), dp(2), dp(4), dp(2));

        curView = new TextView(ctx);
        curView.setTextColor(BASE);
        curView.setTypeface(Typeface.DEFAULT_BOLD);
        curView.setGravity(Gravity.CENTER);
        curView.setEllipsize(TextUtils.TruncateAt.END);
        curView.setMaxLines(2);
        curView.setShadowLayer(dp(4), 0, dp(1), 0xD0000000);

        nextView = new TextView(ctx);
        nextView.setTextColor(0xCCFFFFFF);
        nextView.setGravity(Gravity.CENTER);
        nextView.setEllipsize(TextUtils.TruncateAt.END);
        nextView.setMaxLines(1);
        nextView.setShadowLayer(dp(4), 0, dp(1), 0xD0000000);

        LinearLayout.LayoutParams nlp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        nlp.topMargin = dp(3);
        nlp.gravity = Gravity.CENTER_HORIZONTAL;

        lyricBox.addView(curView);
        lyricBox.addView(nextView, nlp);

        // 控制条
        toolbar = new LinearLayout(ctx);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER);
        toolbar.setVisibility(View.GONE);
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        tlp.topMargin = dp(10);
        tlp.gravity = Gravity.CENTER_HORIZONTAL;

        GlyphView prev = new GlyphView(ctx, GlyphView.PREV);
        playBtn = new GlyphView(ctx, GlyphView.PLAY);
        playBtn.setColor(accent);
        GlyphView next = new GlyphView(ctx, GlyphView.NEXT);
        toolbar.addView(iconBtn(prev, "prev"));
        toolbar.addView(iconBtn(playBtn, "toggle"));
        toolbar.addView(iconBtn(next, "next"));
        toolbar.addView(divider());

        TextView fMinus = textBtn("A-");
        fMinus.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) { changeFont(-2); }
        });
        TextView fPlus = textBtn("A+");
        fPlus.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) { changeFont(2); }
        });
        toolbar.addView(fMinus);
        toolbar.addView(fPlus);
        toolbar.addView(divider());

        lockBtn = textBtn(locked ? "已锁" : "锁定");
        lockBtn.setTextColor(locked ? accent : ICON);
        lockBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                locked = !locked;
                lockBtn.setText(locked ? "已锁" : "锁定");
                lockBtn.setTextColor(locked ? accent : ICON);
                pref.edit().putBoolean("locked", locked).apply();
            }
        });
        toolbar.addView(lockBtn);

        TextView openBtn = textBtn("应用");
        openBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) { openApp(); }
        });
        toolbar.addView(openBtn);

        TextView closeBtn = textBtn("✕");
        closeBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                hide();
                if (host != null) {
                    host.onClose();
                }
            }
        });
        toolbar.addView(closeBtn);

        box.addView(lyricBox, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        box.addView(toolbar, tlp);

        lyricBox.setOnTouchListener(new View.OnTouchListener() {
            @Override
            public boolean onTouch(View v, MotionEvent e) {
                switch (e.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        downRawX = e.getRawX();
                        downRawY = e.getRawY();
                        origX = lp.x;
                        origY = lp.y;
                        moved = false;
                        touching = true;
                        updateCard();
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float dx = e.getRawX() - downRawX;
                        float dy = e.getRawY() - downRawY;
                        if (!moved && (Math.abs(dx) > slop || Math.abs(dy) > slop)) {
                            moved = true;
                        }
                        if (moved && !locked) {
                            lp.x = (int) (origX + dx);
                            lp.y = (int) (origY + dy);
                            clamp();
                            try {
                                wm.updateViewLayout(root, lp);
                            } catch (Exception ignored) {
                            }
                        }
                        return true;
                    case MotionEvent.ACTION_UP:
                    case MotionEvent.ACTION_CANCEL:
                        touching = false;
                        if (!moved) {
                            toggleToolbar();
                        } else if (lp != null) {
                            pref.edit().putInt("x", lp.x).putInt("y", lp.y).apply();
                        }
                        updateCard();
                        return true;
                    default:
                        return false;
                }
            }
        });

        root = box;
    }

    private void toggleToolbar() {
        if (toolbar == null) {
            return;
        }
        boolean on = toolbar.getVisibility() != View.VISIBLE;
        toolbar.setVisibility(on ? View.VISIBLE : View.GONE);
        updateCard();
        root.post(new Runnable() {
            @Override
            public void run() {
                fitOnScreen();
            }
        });
    }

    /** 无交互时背景透明 (酷狗式漂浮歌词); 触摸中或控制条展开时显示深色卡片底。 */
    private void updateCard() {
        if (cardBg == null || root == null) {
            return;
        }
        boolean on = touching || (toolbar != null && toolbar.getVisibility() == View.VISIBLE);
        cardBg.setColor(on ? BG : 0x00000000);
        cardBg.setStroke(on ? dp(1) : 0, on ? STROKE : 0x00000000);
        root.setElevation(on ? dp(10) : 0f);
    }

    private void changeFont(int delta) {
        fontSp = Math.max(12, Math.min(28, fontSp + delta));
        pref.edit().putInt("font", fontSp).apply();
        applyText();
    }

    private View iconBtn(View v, final String cmd) {
        v.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View x) {
                if (host != null) {
                    host.onCommand(cmd);
                }
            }
        });
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(dp(32), dp(32));
        p.leftMargin = dp(1);
        p.rightMargin = dp(1);
        v.setLayoutParams(p);
        return v;
    }

    private View divider() {
        View v = new View(ctx);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(dp(1), dp(16));
        p.leftMargin = dp(5);
        p.rightMargin = dp(5);
        v.setLayoutParams(p);
        v.setBackgroundColor(0x33FFFFFF);
        return v;
    }

    private TextView textBtn(String label) {
        TextView t = new TextView(ctx);
        t.setText(label);
        t.setTextColor(ICON);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(6), dp(6), dp(6), dp(6));
        return t;
    }

    private void clamp() {
        if (lp.x < 0) lp.x = 0;
        if (lp.x > screenW - dp(80)) lp.x = Math.max(0, screenW - dp(80));
        if (lp.y < 0) lp.y = 0;
        if (lp.y > screenH - dp(60)) lp.y = Math.max(0, screenH - dp(60));
    }

    /** 保证窗口不超出屏幕右缘 (控制条展开后可能变宽)。 */
    private void fitOnScreen() {
        if (root == null || lp == null) {
            return;
        }
        int w = root.getWidth();
        if (w <= 0) {
            return;
        }
        int maxRight = screenW - dp(8);
        if (lp.x + w > maxRight) {
            lp.x = Math.max(0, maxRight - w);
            try {
                wm.updateViewLayout(root, lp);
            } catch (Exception ignored) {
            }
        }
    }

    private void openApp() {
        try {
            Intent i = new Intent(ctx, MainActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            ctx.startActivity(i);
        } catch (Exception ignored) {
        }
    }

    // ------------------------------------------------------------- 图标
    /** 上一句 / 播放暂停 / 下一句 图标 (自绘, 避免 unicode 豆腐块)。 */
    private static class GlyphView extends View {
        static final int PREV = 0, PLAY = 1, PAUSE = 2, NEXT = 3;
        private int kind;
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Path path = new Path();

        GlyphView(Context c, int kind) {
            super(c);
            this.kind = kind;
            p.setColor(ICON);
            p.setStyle(Paint.Style.FILL);
        }

        void setKind(int k) {
            kind = k;
            invalidate();
        }

        void setColor(int c) {
            p.setColor(c);
            invalidate();
        }

        @Override
        protected void onDraw(Canvas cv) {
            float w = getWidth(), h = getHeight();
            float cx = w / 2f, cy = h / 2f;
            float s = Math.min(w, h) * 0.20f;
            path.reset();
            switch (kind) {
                case PLAY:
                    path.moveTo(cx - s * 0.7f, cy - s);
                    path.lineTo(cx - s * 0.7f, cy + s);
                    path.lineTo(cx + s, cy);
                    path.close();
                    cv.drawPath(path, p);
                    break;
                case PAUSE:
                    cv.drawRect(cx - s * 0.75f, cy - s, cx - s * 0.15f, cy + s, p);
                    cv.drawRect(cx + s * 0.15f, cy - s, cx + s * 0.75f, cy + s, p);
                    break;
                case PREV:
                    cv.drawRect(cx - s * 1.05f, cy - s, cx - s * 0.7f, cy + s, p);
                    path.moveTo(cx + s, cy - s);
                    path.lineTo(cx + s, cy + s);
                    path.lineTo(cx - s * 0.45f, cy);
                    path.close();
                    cv.drawPath(path, p);
                    break;
                case NEXT:
                    cv.drawRect(cx + s * 0.7f, cy - s, cx + s * 1.05f, cy + s, p);
                    path.moveTo(cx - s, cy - s);
                    path.lineTo(cx - s, cy + s);
                    path.lineTo(cx + s * 0.45f, cy);
                    path.close();
                    cv.drawPath(path, p);
                    break;
                default:
                    break;
            }
        }
    }
}
