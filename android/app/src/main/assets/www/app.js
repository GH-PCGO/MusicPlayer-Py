/* 音乐下载器 - Android 移动端 Web 界面 (主流音乐 App 风格) */
"use strict";

/* ---------------- 主题 ---------------- */
const THEMES = {
  green:  { accent: "#1DB954", dark: "#17A34A", soft: "#E7F8EE", txt: "#0F9D4A" },
  blue:   { accent: "#3B82F6", dark: "#2F6FDB", soft: "#EAF1FE", txt: "#2563D9" },
  purple: { accent: "#8B5CF6", dark: "#7C3AED", soft: "#F1EAFE", txt: "#6D28D9" },
  orange: { accent: "#F59E0B", dark: "#D97706", soft: "#FEF4E4", txt: "#C2700A" },
  red:    { accent: "#EF4444", dark: "#DC2626", soft: "#FDECEC", txt: "#C81E1E" },
};

const MODE_NAMES = ["顺序播放", "列表循环", "单曲循环", "随机播放"];
const MODE_SHORT = ["顺序", "列表", "单曲", "随机"];   // 用文字代替 emoji, 避免豆腐块
const HOT_WORDS = ["周杰伦", "陈奕迅", "林俊杰", "邓紫棋", "薛之谦",
                   "晴天", "稻香", "夜曲", "起风了", "少年"];

const state = {
  theme: "green", br: "320kmp3", mode: 1, volume: 60, muted: false,
  queue: [], idx: -1,
  results: [], resultBase: 0, page: 1, kw: "", hasMore: false, loadingMore: false,
  lyrics: [], lyrDragging: false, lyrTranslate: null, pendingSeek: null, errorCount: 0,
  history: [], lastPlayAt: 0,
  downloads: [], _dlTimer: null,
  mvList: [], mvIndex: 0,
  favorites: [],
  skipCount: 0,
  page: "home",
};

let _playSeq = 0;   // 快速切歌时丢弃过期的 play() 结果

const audio = new Audio();
audio.preload = "none";
const $ = (id) => document.getElementById(id);

/* SVG 图标 (不依赖设备字体, 避免 ⏮⏭⏸≡ 渲染成豆腐块) */
const ICON_PLAY = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const ICON_PAUSE = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';
const ICON_PREV = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M6 6h2v12H6zM19 6v12l-9-6z"/></svg>';
const ICON_NEXT = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M16 6h2v12h-2zM5 18V6l9 6z"/></svg>';
const ICON_QUEUE = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M4 6h16v2H4zM4 11h16v2H4zM4 16h10v2H4z"/></svg>';
const ICON_PLAY_SM = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const ICON_VOL = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3z"/><path d="M15.5 8c1.7 2.3 1.7 5.7 0 8l1.9 1.2c2.3-3.1 2.3-7.3 0-10.4l-1.9 1.2z"/></svg>';
const ICON_MUTE = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3z"/><path d="M16 8l5 8-1.5 1-5-8z"/></svg>';
const ICON_HEART = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 20s-7-4.4-9.3-8.5C1.1 8.6 2.6 5.5 5.6 5.1 7.6 4.9 9.3 6 12 8.7c2.7-2.7 4.4-3.8 6.4-3.6 3 .4 4.5 3.5 2.9 6.4C19 15.6 12 20 12 20z"/></svg>';
const ICON_HEART_ON = '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 20s-7-4.4-9.3-8.5C1.1 8.6 2.6 5.5 5.6 5.1 7.6 4.9 9.3 6 12 8.7c2.7-2.7 4.4-3.8 6.4-3.6 3 .4 4.5 3.5 2.9 6.4C19 15.6 12 20 12 20z"/></svg>';
const ICON_DL = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M11 3h2v9.6l3.3-3.3 1.4 1.4L12 16.4 6.3 10.7l1.4-1.4L11 12.6V3zM5 18h14v2H5z"/></svg>';
const ICON_MV = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 5h16a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V6a1 1 0 011-1zm1 2v10h14V7H5zm5 2l5 3-5 3V9z"/></svg>';

/* ---------------- 工具 ---------------- */
function toast(msg, ms) {
  const t = $("toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), ms || 1600);
}
async function fetchJson(url, ms) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms || 20000);
  try {
    const resp = await fetch(url, { signal: ctrl.signal });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
  } finally {
    clearTimeout(timer);
  }
}
function fmt(t) {
  t = Math.floor(t || 0);
  if (!isFinite(t) || t < 0) t = 0;
  return Math.floor(t / 60) + ":" + String(t % 60).padStart(2, "0");
}
async function postJson(url, body) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 30000);
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    return resp.status === 200 ? resp.json() : { error: "HTTP " + resp.status };
  } finally {
    clearTimeout(timer);
  }
}
async function delJson(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15000);
  try {
    const resp = await fetch(url, { method: "DELETE", signal: ctrl.signal });
    return resp.status === 200 ? resp.json() : { error: "HTTP " + resp.status };
  } finally {
    clearTimeout(timer);
  }
}
function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
/* 行尾图标按钮: 下载 ⬇ + 观看MV ▶ (主流音乐 App 做法) */
function actionBtns(item, opts) {
  opts = opts || {};
  let html = "";
  if (opts.download !== false && item && !item.local) {
    html += '<button class="rowBtn dlBtn" title="下载">' + ICON_DL + '</button>';
  }
  if (opts.mv !== false && item && item.name) {
    html += '<button class="rowBtn mvBtn" title="观看MV">' + ICON_MV + '</button>';
  }
  return html;
}
function bindRowActions(row, item) {
  const dl = row.querySelector(".dlBtn");
  if (dl) dl.addEventListener("click", (e) => {
    e.stopPropagation(); downloadTrack(item);
  });
  const mv = row.querySelector(".mvBtn");
  if (mv) mv.addEventListener("click", (e) => {
    e.stopPropagation(); watchMv(item);
  });
}

/* ---------------- 主题 ---------------- */
function applyTheme(name) {
  const t = THEMES[name] || THEMES.green;
  const r = document.documentElement.style;
  r.setProperty("--accent", t.accent);
  r.setProperty("--accent-dark", t.dark);
  r.setProperty("--accent-soft", t.soft);
  r.setProperty("--accent-txt", t.txt);
  document.querySelectorAll(".themeDot").forEach((el) => {
    el.classList.toggle("active", el.dataset.name === name);
  });
  const logo = $("logo");
  if (logo) logo.style.color = t.accent;
  state.theme = name;
  saveState();
}
function buildThemeDots(container, active) {
  if (!container) return;
  container.innerHTML = "";
  Object.keys(THEMES).forEach((name) => {
    const d = document.createElement("button");
    d.className = "themeDot" + (name === state.theme ? " active" : "");
    d.dataset.name = name;
    d.style.background = THEMES[name].accent;
    d.style.color = THEMES[name].accent;   // 供选中态 currentColor 色环使用
    d.addEventListener("click", () => applyTheme(name));
    container.appendChild(d);
  });
}

/* ---------------- 设置面板 ---------------- */
const BR_OPTIONS = [["320kmp3", "320k"], ["192kmp3", "192k"], ["128kmp3", "128k"]];

function buildBrSeg() {
  const box = $("brSeg");
  if (!box) return;
  box.innerHTML = "";
  BR_OPTIONS.forEach(([val, label]) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.classList.toggle("on", state.br === val);
    b.addEventListener("click", () => setQuality(val));
    box.appendChild(b);
  });
  const sel = $("brSelect");
  if (sel) sel.value = state.br;
}

function setQuality(br) {
  state.br = br;
  buildBrSeg();
  const label = (BR_OPTIONS.find((o) => o[0] === br) || [, br])[1];
  toast("音质已切换为 " + label);
  saveState();
}

function openSettings() {
  const s = $("settingsSheet"), m = $("sheetMask");
  if (s) s.classList.add("on");
  if (m) m.classList.add("on");
}
function closeSettings() {
  const s = $("settingsSheet"), m = $("sheetMask");
  if (s) s.classList.remove("on");
  if (m) m.classList.remove("on");
}
function updateVolPct() {
  const el = $("volPct");
  if (el) el.textContent = Math.round(state.volume) + "%";
}

/* ---------------- 收藏夹 ---------------- */
const FKEY = "musicplayer_favorites_v1";

function loadFavorites() {
  try {
    const a = JSON.parse(localStorage.getItem(FKEY) || "[]");
    state.favorites = Array.isArray(a) ? a.filter((x) => x && x.name) : [];
  } catch (e) {
    state.favorites = [];
  }
}
function saveFavorites() {
  try { localStorage.setItem(FKEY, JSON.stringify(state.favorites)); } catch (e) {}
}
function favKey(t) {
  if (!t) return "";
  return t.rid ? ("r:" + t.rid)
    : ("n:" + (t.name || "") + "|" + (t.artist || ""));
}
function isFav(t) {
  const k = favKey(t);
  return !!k && (state.favorites || []).some((f) => favKey(f) === k);
}
function toggleFav(t) {
  if (!t || !t.name) return;
  const k = favKey(t);
  const i = (state.favorites || []).findIndex((f) => favKey(f) === k);
  if (i >= 0) {
    state.favorites.splice(i, 1);
    toast("已取消收藏");
  } else {
    state.favorites.unshift({
      rid: t.rid || "", name: t.name, artist: t.artist || "",
      cover: t.cover || "", local: !!t.local,
    });
    toast("已收藏 ♥");
  }
  saveFavorites();
  updatePlayerFav();
  if (state.page === "favorites") renderFavorites();
}
function removeFav(i) {
  if (i < 0 || i >= (state.favorites || []).length) return;
  state.favorites.splice(i, 1);
  saveFavorites();
  updatePlayerFav();
  renderFavorites();
  toast("已取消收藏");
}
function updatePlayerFav() {
  const btn = $("playerFav");
  if (!btn) return;
  const on = isFav(currentTrack());
  btn.innerHTML = (on ? ICON_HEART_ON : ICON_HEART) + (on ? " 已收藏" : " 收藏");
  btn.classList.toggle("on", on);
}
function renderFavorites() {
  const box = $("favList");
  if (!box) return;
  const favs = state.favorites || [];
  const selOn = _sel.on && _sel.kind === "fav";
  box.classList.toggle("selMode", selOn);
  const empty = $("favEmpty");
  if (empty) empty.style.display = favs.length ? "none" : "";
  const cnt = $("favCount");
  if (cnt) cnt.textContent = favs.length ? "· " + favs.length + " 首" : "";
  box.innerHTML = "";
  favs.forEach((t, i) => {
    const key = favKey(t);
    const row = document.createElement("div");
    row.className = "hotRow" + (selOn && _sel.ids.has(key) ? " sel" : "");
    const cover = t.cover
      ? '<img class="hotCover" src="' + t.cover + '" onerror="this.style.visibility=\'hidden\'">'
      : '<div class="hotCover"></div>';
    row.innerHTML =
      (selOn ? '<span class="selBox">\u2713</span>' : "") + cover +
      '<div class="hotInfo"><div class="hotName">' + escapeHtml(trackLabel(t)) +
      '</div><div class="hotArtist">' + escapeHtml(t.artist || "") + '</div></div>' +
      (selOn ? "" : '<span class="hotHeart">' + ICON_HEART_ON + '</span>');
    row.addEventListener("click", () => {
      if (Date.now() < _selGuard) return;      // 长按补发的 click, 忽略
      if (selOn) { toggleSel(key); return; }
      startQueue(favs.slice(0), i);
      openPlayer();
    });
    bindLongPress(row, () => { if (!selOn) enterSelect("fav", key); });
    const heart = row.querySelector(".hotHeart");
    if (heart) {
      heart.addEventListener("click", (e) => {
        e.stopPropagation();
        removeFav(i);
      });
    }
    box.appendChild(row);
  });
}

/* ---------------- 长按多选 (收藏 / 下载 批量删除) ---------------- */
let _sel = { on: false, kind: "", ids: new Set() };
let _selGuard = 0;   // 长按后短暂忽略列表 click (吞掉浏览器补发的那个)

function selKeyOf(kind, item) {
  return kind === "fav" ? favKey(item) : ((item && item.name) || "");
}
function selItems() {
  return _sel.kind === "fav" ? (state.favorites || []) : (state.downloads || []);
}
function enterSelect(kind, key) {
  _sel = { on: true, kind: kind, ids: new Set(key ? [key] : []) };
  // 长按后浏览器还会补一个 click; 列表这时已经重绘, 捕获阶段的拦截会失效,
  // 所以用一个全局时间窗, 让列表的 click 处理在这段时间内直接忽略。
  _selGuard = Date.now() + 700;
  try { if (navigator.vibrate) navigator.vibrate(18); } catch (e) {}
  renderSel();
}
function exitSelect() {
  if (!_sel.on) return;
  const kind = _sel.kind;
  _sel = { on: false, kind: "", ids: new Set() };
  renderSel();
  // 退出时把刚才那个列表重绘一遍 (删完要立刻反映到界面上)
  if (kind === "fav") renderFavorites();
  else if (kind === "dl") renderDownloads();
}
function toggleSel(key) {
  if (!_sel.on) return;
  if (_sel.ids.has(key)) _sel.ids.delete(key);
  else _sel.ids.add(key);
  renderSel();
}
function selAll() {
  const keys = selItems().map((it) => selKeyOf(_sel.kind, it));
  const all = keys.length > 0 && keys.every((k) => _sel.ids.has(k));
  _sel.ids = new Set(all ? [] : keys);
  renderSel();
}
/** 刷新选择态 UI: 切换页头 + 重绘对应列表。 */
function renderSel() {
  const favOn = _sel.on && _sel.kind === "fav";
  const dlOn = _sel.on && _sel.kind === "dl";
  const set = (headId, selId, on) => {
    const h = $(headId), s = $(selId);
    if (h) h.style.display = on ? "none" : "";
    if (s) s.style.display = on ? "" : "none";
  };
  set("favHead", "favSelHead", favOn);
  set("dlHead", "dlSelHead", dlOn);
  const n1 = $("favSelN");
  if (n1) n1.textContent = favOn ? _sel.ids.size : 0;
  const n2 = $("dlSelN");
  if (n2) n2.textContent = dlOn ? _sel.ids.size : 0;
  if (favOn) renderFavorites();
  if (dlOn) renderDownloads();
}
async function selDelete() {
  const ids = new Set(_sel.ids);
  const kind = _sel.kind;
  if (!ids.size) { toast("先勾选要删除的歌曲"); return; }
  if (kind === "fav") {
    state.favorites = (state.favorites || []).filter((t) => !ids.has(favKey(t)));
    saveFavorites();
    updatePlayerFav();
    exitSelect();
    toast("已删除 " + ids.size + " 首收藏");
    return;
  }
  // 下载: 逐个删 (含同名 .lrc, 安卓同步删媒体库条目)
  const names = [...ids];
  const cur = currentTrack();
  let ok = 0, fail = 0;
  for (const name of names) {
    try {
      const res = await delJson("/api/download?name=" + encodeURIComponent(name));
      if (res && res.ok) ok++;
      else fail++;
    } catch (e) { fail++; }
  }
  if (cur && cur.local && ids.has(cur.name)) {
    audio.pause();
    try { audio.removeAttribute("src"); } catch (e) {}
    updateNowPlaying(null, 0, 0);
    setPlayIcons(false);
  }
  dropLocalFromQueue(names);
  exitSelect();
  await refreshDownloads();
  toast("已删除 " + ok + " 首" + (fail ? "，失败 " + fail : ""));
}
/** 删掉的本地文件若还在播放列表里, 一并摘掉并修正当前下标。 */
function dropLocalFromQueue(names) {
  const set = new Set(names);
  const cur = currentTrack();
  const key = cur ? (cur.local ? "l:" + cur.name : "r:" + cur.rid) : "";
  const before = state.queue.length;
  state.queue = state.queue.filter((t) => !(t.local && set.has(t.name)));
  if (state.queue.length === before) return;
  if (!state.queue.length) {
    state.idx = -1;
  } else {
    const i = key ? state.queue.findIndex(
      (t) => (t.local ? "l:" + t.name : "r:" + t.rid) === key) : -1;
    state.idx = i >= 0 ? i : Math.max(0, Math.min(state.idx, state.queue.length - 1));
  }
  saveState();
  if (state.page === "queue") renderQueuePage();
}
/** 长按 (触摸或鼠标) 触发; 触发后吞掉紧随的 click, 免得又播了一首。 */
function bindLongPress(el, onLong) {
  let timer = null, sx = 0, sy = 0, fired = false;
  const pos = (e) => ((e.touches && e.touches[0]) ? e.touches[0] : e);
  const start = (e) => {
    const t = pos(e);
    sx = t.clientX; sy = t.clientY; fired = false;
    clearTimeout(timer);
    timer = setTimeout(() => { fired = true; onLong(); }, 520);
  };
  const move = (e) => {
    const t = pos(e);
    if (Math.abs(t.clientX - sx) > 12 || Math.abs(t.clientY - sy) > 12) {
      clearTimeout(timer);
    }
  };
  const end = () => clearTimeout(timer);
  el.addEventListener("touchstart", start, { passive: true });
  el.addEventListener("touchmove", move, { passive: true });
  el.addEventListener("touchend", end);
  el.addEventListener("touchcancel", end);
  el.addEventListener("mousedown", start);
  el.addEventListener("mousemove", move);
  el.addEventListener("mouseup", end);
  el.addEventListener("mouseleave", end);
  el.addEventListener("click", (e) => {
    if (fired) { fired = false; e.stopPropagation(); e.preventDefault(); }
  }, true);
}

/* ---------------- 歌单导入 (网易云 cookie) ---------------- */
const CKEY = "musicplayer_ne_cookie_v1";
const IMP_MAX = 1000;          // 单次导入上限 (匹配音源是逐首搜索, 不宜无上限)
const IMP_CHUNK = 20;          // 每批匹配歌曲数
let _impCancel = false;
let _impMode = "link";     // 当前导入来源页签 (link/text/image/account)
let _ocrPending = false;   // 是否正在等原生 OCR 结果
let _ocrMode = false;      // 文本框里的内容是否来自图片识别
let _ocrLines = "";        // OCR 每行坐标 (JSON), 供服务端按位置配对
let _impRunning = false;

function impCookie() {
  try { return localStorage.getItem(CKEY) || ""; } catch (e) { return ""; }
}
function impSetCookie(c) {
  try {
    if (c) localStorage.setItem(CKEY, c);
    else localStorage.removeItem(CKEY);
  } catch (e) { /* 隐私模式等 */ }
}
function impStep(step) {
  const map = { login: "impLogin", list: "impList", run: "impRun" };
  Object.keys(map).forEach((k) => {
    const el = $(map[k]);
    if (el) el.style.display = k === step ? "" : "none";
  });
}
function setImpProgress(f, txt) {
  const fill = $("impFill");
  if (fill) fill.style.width = Math.round(Math.max(0, Math.min(1, f)) * 100) + "%";
  if (txt != null) $("impRunTxt").textContent = txt;
}
function openImport() {
  impStep(impCookie() ? "list" : "login");
  impMode(_impMode || "link");         // 回到上次用的来源页签
  $("impCookie").value = impCookie();
  $("impMask").classList.add("on");
  $("impSheet").classList.add("on");
  if (impCookie()) impLoadPlaylists();
}
function closeImport() {
  _impCancel = true;
  $("impMask").classList.remove("on");
  $("impSheet").classList.remove("on");
}
async function impLogin() {
  const ck = ($("impCookie").value || "").trim();
  if (!ck) { toast("请先粘贴 cookie"); return; }
  const btn = $("impLoginBtn");
  btn.disabled = true; btn.textContent = "登录中…";
  const d = await postJson("/api/import/login", { cookie: ck });
  btn.disabled = false; btn.textContent = "登录并读取歌单";
  if (!d || d.error) { toast((d && d.error) || "登录失败"); return; }
  impSetCookie(ck);
  toast("已登录 " + (d.nickname || d.uid));
  impStep("list");
  impLoadPlaylists(d.uid);
}
function impLogout() {
  impSetCookie("");
  $("impCookie").value = "";
  $("impPl").innerHTML = "";
  impStep("login");
  toast("已退出登录");
}
async function impLoadPlaylists(uid) {
  const box = $("impPl");
  box.innerHTML = '<div class="impRunTxt">读取歌单…</div>';
  const d = await postJson("/api/import/playlists",
                           { cookie: impCookie(), uid: uid || "" });
  if (!d || d.error) {
    box.innerHTML = "";
    const msg = (d && d.error) || "读取歌单失败";
    if (msg.indexOf("cookie") >= 0) { impSetCookie(""); impStep("login"); }
    toast(msg);
    return;
  }
  const items = d.items || [];
  $("impUser").innerHTML = "<span>共 " + items.length + " 个歌单</span>";
  box.innerHTML = "";
  items.forEach((p) => {
    const row = document.createElement("div");
    row.className = "impPlRow";
    row.innerHTML =
      (p.cover ? '<img src="' + p.cover + '" onerror="this.style.visibility=\'hidden\'">'
               : '<div class="ph"></div>') +
      '<div class="impPlInfo"><div class="impPlName">' +
        (p.special ? '<i class="impBadge">我喜欢</i>' : "") +
        "<span>" + escapeHtml(p.name) + "</span></div>" +
        '<div class="impPlSub">' + (p.count || 0) + " 首</div></div>" +
      '<span class="impGo">导入</span>';
    row.addEventListener("click", () => impRun(p));
    box.appendChild(row);
  });
  if (!items.length) box.innerHTML = '<div class="impRunTxt">这个账号下没有歌单</div>';
}
function impExtractId(s) {
  s = (s || "").trim();
  const m = s.match(/[?&#]id=(\d+)/) || s.match(/\/(\d{5,})/) || s.match(/(\d{5,})/);
  return m ? m[1] : "";
}
/** 酷狗分享链接 (m.kugou.com/songlist/gcid_xxx 或 short link) 直接用原链接。 */
function impIsKugou(s) {
  return /kugou\.com|gcid_|songlist\//i.test(s || "");
}
/** 从整段分享文案里抽出歌单链接/标识 —— App 分享的"文案+链接"整段粘贴也能用。
 *  优先取已知音乐平台的链接, 其次任意链接, 再退到 gcid_xxx / playlist_detail/<id> / 纯数字 id。 */
function impPickLink(text) {
  const s = String(text || "");
  const urls = s.match(/https?:\/\/[^\s"'<>()\[\]{}（）【】,，。;；、!！？\u4e00-\u9fff]+/gi) || [];
  const known = urls.find((u) => /kugou\.com|kuwo\.cn|163\.com/i.test(u));
  if (known) return known;
  if (urls.length) return urls[0];
  const g = s.match(/gcid_[0-9a-z]+/i);
  if (g) return g[0];
  const pid = s.match(/playlist_detail\/(\d{5,})/i) || s.match(/[?&#]id=(\d{5,})/);
  if (pid) return pid[1];
  return s.trim();
}
function impPublic() {
  const raw = impPickLink($("impPid").value);
  if (!raw) { toast("请粘贴歌单链接或 id"); return; }
  $("impPid").value = raw;               // 回填抽出来的链接, 让用户看清用了哪条
  const kg = impIsKugou(raw);
  const link = kg ? raw : impExtractId(raw);
  if (!link) { toast("没识别到歌单，请粘贴完整链接或纯数字 id"); return; }
  impRun({ id: link, name: kg ? "酷狗歌单" : "公开歌单", count: 0 });
}
function impPublicPrompt() {
  impStep("login");
  $("impPid").focus();
}
function impCancel() {
  if (!_impRunning) { closeImport(); return; }   // 跑完了: 这按钮就是「完成」
  _impCancel = true;
  toast("正在停止…");
}
/** 切换导入来源页签: link / text / image / account */
function impMode(mode) {
  const map = { link: "impPaneLink", text: "impPaneText",
                image: "impPaneImage", account: "impPaneAccount" };
  Object.keys(map).forEach((k) => {
    const el = $(map[k]);
    if (el) el.style.display = k === mode ? "" : "none";
  });
  const tabs = $("impTabs");
  if (tabs) {
    const idx = ["link", "text", "image", "account"].indexOf(mode);
    [...tabs.children].forEach((b, i) => b.classList.toggle("on", i === idx));
  }
  _impMode = mode;
}
/** 从图片导入: 调原生选图 + 离线 OCR, 结果由 onOcrText 回传。 */
function impImage() {
  const p = window.AndroidPlayer;
  if (!p || !p.pickImage) {
    toast("该功能在手机端可用（从相册选歌单截图）");
    return;
  }
  _ocrPending = true;
  toast("请选择歌单截图…");
  try { p.pickImage(); } catch (e) { _ocrPending = false; toast("打开相册失败"); }
}
/** 原生 OCR 回调 (识别完成/失败/取消)。text=纯文本; lines=每行坐标(JSON)。 */
function onOcrText(text, lines, err) {
  if (!_ocrPending) return;            // 不是从"图片导入"发起的, 忽略
  _ocrPending = false;
  if (err) { toast(err); return; }
  text = (text || "").trim();
  if (!text) { toast("没识别到文字（或已取消）"); return; }
  _ocrMode = true;                     // 这段文字来自图片 → 用"歌名/歌手两行配对"解析
  _ocrLines = lines || "";
  $("impText").value = text;
  impMode("text");                     // 切到「文本」页让用户核对
  const rows = text.split("\n").filter((x) => x.trim()).length;
  toast("识别到 " + rows + " 行，核对后点「导入这些歌曲」", 5000);
}

/** 一键勾选"疑似 OCR 乱码"的收藏 (判定在后端, 与导入时同一套规则)。
 *  只勾选不删除, 由用户确认后再点删除。 */
async function selJunk() {
  const favs = state.favorites || [];
  if (!favs.length) { toast("收藏是空的"); return; }
  let junk = [];
  try {
    const r = await postJson("/api/import/check",
                             { names: favs.map((t) => trackLabel(t)) });
    junk = (r && r.items) || [];
  } catch (e) { toast("检查失败"); return; }
  const set = new Set(junk);
  if (!_sel.on || _sel.kind !== "fav") enterSelect("fav", null);
  _sel.ids = new Set();
  favs.forEach((t) => { if (set.has(trackLabel(t))) _sel.ids.add(favKey(t)); });
  renderSel();
  toast(_sel.ids.size
    ? ("已勾选 " + _sel.ids.size + " 条疑似乱码，确认后点「删除」")
    : "没发现疑似乱码的条目", 4000);
}

/** 从粘贴的「歌名 + 歌手」文本导入 (每行一首)。 */
async function impText(fromOcr) {
  const text = ($("impText").value || "").trim();
  if (!text) { toast("请先粘贴「歌名 + 歌手」的列表"); return; }
  if (fromOcr == null) fromOcr = _ocrMode;   // 按钮进入时按来源决定解析方式
  _impCancel = false;
  _impRunning = true;
  $("impCancel").textContent = "取消";
  impStep("run");
  $("impRunName").textContent = fromOcr ? "图片识别结果" : "粘贴的列表";
  setImpProgress(0, "解析文本…");
  const r = await postJson("/api/import/text",
                           { text: text, limit: IMP_MAX, ocr: !!fromOcr,
                             lines: fromOcr ? _ocrLines : "" });
  if (!r || r.error) {
    toast((r && r.error) || "解析失败");
    _impRunning = false; impStep("login"); return;
  }
  const songs = (r.items || []).slice(0, IMP_MAX);
  if (!songs.length) {
    toast(fromOcr ? "没解析出歌曲：图里是否是「歌名 / 歌手」的列表？"
                  : "没解析出歌曲：每行一首「歌名 + 歌手」(TAB / 竖线 / 空格 分隔)");
    _impRunning = false; impStep("login"); return;
  }
  $("impRunName").textContent = (fromOcr ? "图片识别（" : "粘贴的列表（") +
    songs.length + " 首" + (r.skipped ? "，跳过 " + r.skipped + " 行" : "") + "）";
  await impMatchAndSave(songs, "");
}

async function impRun(pl) {
  _impCancel = false;
  _impRunning = true;
  $("impCancel").textContent = "取消";
  impStep("run");
  $("impRunName").textContent = pl.name || "歌单";
  setImpProgress(0, "读取歌单歌曲…");
  const info = await postJson("/api/import/songs",
                              { cookie: impCookie(), link: pl.id, limit: IMP_MAX });
  if (!info || info.error) {
    toast((info && info.error) || "读取歌单失败");
    _impRunning = false; impStep("list"); return;
  }
  const songs = (info.items || []).slice(0, IMP_MAX);
  if (!songs.length) {
    toast("歌单里没有歌曲");
    _impRunning = false; impStep("list"); return;
  }
  if (info.name) $("impRunName").textContent = info.name;
  // 酷狗云歌单: 分享页只内嵌前 10 首, 这里明确告诉用户, 别让人以为导全了
  const truncMsg = info.truncated
    ? ("酷狗分享页只提供前 " + songs.length + " 首（共 " + info.total +
       " 首），其余需在酷狗 App 内查看")
    : "";
  await impMatchAndSave(songs, truncMsg);
}

/** 匹配音源并写入收藏 (链接导入 / 文本粘贴导入共用)。 */
async function impMatchAndSave(songs, truncMsg) {
  const total = songs.length;
  const got = new Array(total).fill(null);     // 每首的匹配结果 (按歌单顺序)

  // 跑一遍匹配; idxs 是要查的下标 (第二轮只补第一轮没匹配上的)
  async function pass(idxs, label) {
    for (let n = 0; n < idxs.length; n += IMP_CHUNK) {
      if (_impCancel) return;
      const idx = idxs.slice(n, n + IMP_CHUNK);
      const r = await postJson("/api/import/match",
                               { items: idx.map((i) => songs[i]) });
      if (_impCancel) return;                    // 取消: 保留已匹配部分
      const rows = (r && r.items) || [];
      idx.forEach((i, k) => { if (rows[k]) got[i] = rows[k]; });
      const done = Math.min(n + IMP_CHUNK, idxs.length);
      setImpProgress(done / idxs.length,
                     label + " " + done + "/" + idxs.length);
    }
  }

  await pass(songs.map((_x, i) => i), "匹配音源");
  // 被酷我限流/超时的会失败且不入服务端缓存, 歇一下再补一轮, 未匹配率能降一大截
  let missIdx = [];
  for (let i = 0; i < total; i++) {
    if (!got[i] || !got[i].matched) missIdx.push(i);
  }
  if (missIdx.length && !_impCancel) {
    await new Promise((res) => setTimeout(res, 1500));
    await pass(missIdx, "重试未匹配");
  }

  const have = new Set((state.favorites || []).map(favKey));
  const news = [];
  let dup = 0, missed = 0;
  got.forEach((t) => {
    if (!t || !t.matched) { missed++; return; }  // 没匹配到音源的跳过 (留着也播不了)
    const k = favKey(t);
    if (have.has(k)) { dup++; return; }
    have.add(k);
    news.push({ rid: t.rid, name: t.name, artist: t.artist || "",
                cover: t.cover || "", local: false });
  });
  if (news.length) {
    state.favorites = news.concat(state.favorites || []);
    saveFavorites();
    updatePlayerFav();
    renderFavorites();
  }
  _impRunning = false;
  $("impCancel").textContent = "完成";
  setImpProgress(1, "完成 · 导入 " + news.length + " 首" +
                 (missed ? " · 未匹配 " + missed : "") +
                 (dup ? " · 重复 " + dup : "") +
                 (truncMsg ? " ｜ " + truncMsg : "") +
                 (total >= IMP_MAX ? " (歌单过长, 只取前 " + IMP_MAX + " 首)" : ""));
  toast(_impCancel
    ? "已取消，导入 " + news.length + " 首"
    : "导入完成 " + news.length + " 首" + (missed ? "，跳过 " + missed + " 首未匹配" : ""),
    truncMsg ? 8000 : undefined);
  if (truncMsg) toast(truncMsg, 8000);
}

/* ---------------- 页面切换 ---------------- */
function renderPage(name) {
  state.page = name;
  ["home", "search", "favorites", "queue", "download"].forEach((p) => {
    $(p + "View").style.display = p === name ? "" : "none";
  });
  document.querySelectorAll(".navItem").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === name);
  });
  if (name === "queue") renderQueuePage();
  if (name === "favorites") renderFavorites();
  if (name === "download") refreshDownloads();
  if (name === "search") {
    const inp = $("searchInput");
    if (!state.kw) setTimeout(() => inp.focus(), 80);
    else $("resultsList").scrollIntoView({ block: "start" });
  }
}
function showPage(name) {
  if (state.page === name) { renderPage(name); return; }
  // 页面用 replaceState: 永远只有一条页面历史, 返回键只负责收起播放器 / 退出
  history.replaceState({ page: name }, "");
  renderPage(name);
}
// 安卓返回键: 播放器开着先收起; 否则只在确实换了页面条目时才渲染,
// 避免 closePlayer 内部 history.back() 触发的 popstate 把当前页面覆盖掉
window.addEventListener("popstate", () => {
  if ($("mvOverlay").style.display !== "none") {
    hideMvOverlay();               // MV 层最上层: 返回键先收起
    return;
  }
  if ($("player").style.display !== "none") {
    $("player").style.display = "none";
    return;
  }
  if (_sel.on) {                 // 多选态: 返回键先退出多选
    exitSelect();
    return;
  }
  const p = history.state && history.state.page;
  if (p === "player") return;                 // 过期的播放器条目
  if (p && p !== state.page && ["home", "search", "favorites", "queue", "download"].includes(p)) {
    renderPage(p);
  }
});

/* ---------------- 会话持久化 ---------------- */
const SKEY = "musicplayer_session_v1";
function saveState() {
  try {
    localStorage.setItem(SKEY, JSON.stringify({
      theme: state.theme, br: state.br, volume: state.volume, mode: state.mode,
      muted: audio.muted,
      queue: state.queue, idx: state.idx,
      pos: audio.currentTime || 0, dur: audio.duration || 0,
    }));
  } catch (e) {}
}
let _saveTimer = null;
function saveStateThrottled() {
  if (_saveTimer) return;
  _saveTimer = setTimeout(() => { _saveTimer = null; saveState(); }, 3000);
}
function restoreState() {
  let s = null;
  try { s = JSON.parse(localStorage.getItem(SKEY) || "null"); } catch (e) {}
  if (!s) return;
  if (THEMES[s.theme]) state.theme = s.theme;
  if (["320kmp3", "192kmp3", "128kmp3"].indexOf(s.br) >= 0) state.br = s.br;
  if (typeof s.volume === "number") state.volume = Math.max(0, Math.min(100, s.volume));
  if (typeof s.mode === "number") state.mode = s.mode % 4;
  if (Array.isArray(s.queue)) state.queue = s.queue;
  if (typeof s.idx === "number") state.idx = s.idx;
  applyTheme(state.theme);
  buildThemeDots($("themeDots"));
  buildBrSeg();
  $("pbVol").value = state.volume;
  updateVolPct();
  audio.volume = state.volume / 100;
  if (typeof s.muted === "boolean") {
    audio.muted = s.muted;
    updateVolIcon();
  }
  setModeUI();
  if (state.idx >= 0 && state.queue[state.idx]) {
    const t = state.queue[state.idx];
    const pos = s.pos || 0, dur = s.dur || 0;
    if (pos > 1) state.pendingSeek = pos;   // 点播放时从中断处续播
    updateNowPlaying(t, pos, dur);
    setPlayIcons(false);
  }
}

function shade(hex, amt) {
  // amt>0 混白, amt<0 混黑; 返回 hex
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const t = Math.abs(amt);
  if (amt >= 0) {
    r += (255 - r) * t; g += (255 - g) * t; b += (255 - b) * t;
  } else {
    r *= 1 - t; g *= 1 - t; b *= 1 - t;
  }
  return "#" + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
}

/* ---------------- 首页 (真实热榜 + 推荐歌单) ---------------- */
let _hotSongs = [];

async function loadHome() {
  const loading = $("homeLoad");
  if (loading) { loading.style.display = "block"; loading.textContent = "正在加载推荐…"; }
  // 并行拉取热榜与推荐歌单
  const [hot, pls] = await Promise.allSettled([
    fetchJson("/api/hot?limit=20", 20000),
    fetchJson("/api/playlists?limit=8", 20000),
  ]);
  let ok = false;
  if (hot.status === "fulfilled" && hot.value.items) {
    _hotSongs = hot.value.items;
    renderHomeHot(_hotSongs);
    ok = true;
  }
  if (pls.status === "fulfilled" && pls.value.items) {
    renderHomePlaylists(pls.value.items);
    ok = true;
  }
  if (loading) {
    loading.style.display = ok ? "none" : "block";
    if (!ok) loading.textContent = "推荐加载失败，请检查网络后点右上角刷新";
  }
}

function renderHomeHot(items) {
  const box = $("rankList");
  if (!box) return;
  box.innerHTML = "";
  items.forEach((it, i) => {
    const row = document.createElement("div");
    row.className = "hotRow";
    const cover = it.cover
      ? '<img class="hotCover" src="' + it.cover + '" onerror="this.style.visibility=\'hidden\'">'
      : '<div class="hotCover"></div>';
    row.innerHTML =
      '<span class="hotRank' + (i < 3 ? " top" : "") + '">' + (i + 1) + '</span>' +
      cover +
      '<div class="hotInfo"><div class="hotName">' + escapeHtml(it.name) +
      '</div><div class="hotArtist">' + escapeHtml(it.artist) + '</div></div>' +
      '<div class="hotActions">' + actionBtns(it) + '</div>';
    row.addEventListener("click", () => playHotAt(i));
    bindRowActions(row, it);
    box.appendChild(row);
  });
}

function renderHomePlaylists(items) {
  const strip = $("plStrip");
  if (!strip) return;
  strip.innerHTML = "";
  items.forEach((p) => {
    const card = document.createElement("div");
    card.className = "plCard";
    const cover = p.cover
      ? '<img src="' + p.cover + '" onerror="this.style.display=\'none\'">'
      : "";
    card.innerHTML =
      '<div class="plCover">' + cover +
      '<span class="plCount">&#9654; ' + fmtCount(p.count) + '</span></div>' +
      '<div class="plName">' + escapeHtml(p.name) + '</div>';
    card.addEventListener("click", () => openPlaylist(p.id, p.name));
    strip.appendChild(card);
  });
}

function fmtCount(n) {
  n = n || 0;
  if (n >= 100000000) return (n / 100000000).toFixed(1) + "亿";
  if (n >= 10000) return (n / 10000).toFixed(0) + "万";
  return String(n);
}

/** 点热榜某首: 播放列表换成整张热榜(从这首开始), 缺 rid 的曲目播放时再解析。
 *  之前是把队列换成"该歌名的酷我搜索结果", 于是听到的并不是这张榜。 */
function playHotAt(i) {
  const it = _hotSongs[i];
  if (!it) return;
  const list = _hotSongs.map((x) => ({ rid: "", name: x.name,
                                       artist: x.artist, cover: x.cover }));
  startQueue(list, i);
  openPlayer();
}

/** 每日推荐: 随机播一首热歌 */
function playRandomHot() {
  if (!_hotSongs.length) { toast("推荐加载中…"); return; }
  playHotAt(Math.floor(Math.random() * _hotSongs.length));
}

function reloadHome() {
  loadHome();
  toast("已刷新推荐");
}

/** 打开歌单: 队列=整张歌单 (缺 rid 的曲目播放时按相关性解析), 播第一首。 */
async function openPlaylist(id, name) {
  toast("加载歌单: " + name);
  try {
    const data = await fetchJson("/api/playlist?id=" + id + "&limit=50", 25000);
    const items = (data.items || []).filter((x) => x && x.name);
    if (!items.length) { toast("歌单为空"); return; }
    state.kw = name;
    state.results = items.map((x) => ({ rid: "", name: x.name,
                                        artist: x.artist, cover: x.cover }));
    state.resultBase = 0;
    showPage("search");
    renderResults(state.results, false);
    startQueue(state.results.slice(0), 0);
    openPlayer();
  } catch (e) {
    toast("歌单加载失败");
  }
}

/* ---------------- 搜索 ---------------- */
async function doSearch(kw, page, append) {
  if (!kw) return;
  state.kw = kw; state.page = page; state.loadingMore = append;
  $("loadMore").textContent = "加载中...";
  let data;
  try {
    data = await fetchJson("/api/search?kw=" + encodeURIComponent(kw) + "&pn=" + page);
  } catch (e) {
    toast("搜索失败，请检查网络");
    $("loadMore").textContent = "加载失败";
    return;
  }
  const items = data.items || [];
  state.hasMore = items.length >= 30;
  if (append) {
    state.results = state.results.concat(items);
    renderResults(items, true);
  } else {
    state.results = items;
    state.resultBase = 0;
    renderResults(items, false);
  }
  state.loadingMore = false;
  $("loadMore").textContent = state.hasMore ? "上滑加载更多" : "已显示全部";
}
function renderResults(items, append) {
  const list = $("resultsList");
  if (!append) list.innerHTML = "";
  const base = append ? state.resultBase : 0;
  items.forEach((item, k) => {
    const idx = base + k;
    const row = document.createElement("div");
    row.className = "row";
    const cover = item.cover
      ? '<img class="rCover" src="' + item.cover + '" onerror="this.style.display=\'none\'">'
      : '<div class="rCover"></div>';
    row.innerHTML =
      '<span class="idx">' + (idx + 1) + '</span>' + cover +
      '<div class="rInfo"><div class="rName">' + escapeHtml(item.name) +
      '</div><div class="rArtist">' + escapeHtml(item.artist) + '</div></div>' +
      actionBtns(item) +
      '<button class="addBtn">+</button>';
    row.addEventListener("click", () => playFromResults(idx));
    bindRowActions(row, item);
    row.querySelector(".addBtn").addEventListener("click", (e) => {
      e.stopPropagation();
      addToQueue(item);
    });
    list.appendChild(row);
  });
  state.resultBase += items.length;
  markPlayingRows();
}
function markPlayingRows() {
  const rows = $("resultsList").children;
  const cur = state.idx >= 0 ? state.queue[state.idx] : null;
  for (let i = 0; i < rows.length; i++) {
    const item = state.results[i];
    rows[i].classList.toggle("playing", !!(cur && item && item.rid === cur.rid));
  }
}
function playFromResults(i) {
  const track = state.results[i];
  if (!track) return;
  startQueue(state.results.slice(i), 0);
}
function addToQueue(track) {
  state.queue.push({ rid: track.rid, name: track.name, artist: track.artist, cover: track.cover });
  if (state.idx < 0) { state.idx = 0; updateNowPlaying(state.queue[0], 0, 0); setPlayIcons(false); }
  toast("已加入队列");
  saveState();
}

/* ---------------- 队列页 ---------------- */
function renderQueuePage() {
  const list = $("queueList");
  list.innerHTML = "";
  $("queueEmpty").style.display = state.queue.length ? "none" : "";
  state.queue.forEach((t, i) => {
    const row = document.createElement("div");
    row.className = "qRow" + (i === state.idx ? " cur" : "");
    row.innerHTML = '<span class="qn">' + (i + 1) + '</span>' +
      '<span class="qt">' + escapeHtml(trackLabel(t)) + '</span>' +
      (i === state.idx ? '<span class="qmark">\u25B6</span>' : "") +
      actionBtns(t);
    row.addEventListener("click", () => {
      if (i === state.idx) togglePlay();
      else { pushHistory(state.idx); playTrack(state.queue[i], i); }
    });
    bindRowActions(row, t);
    list.appendChild(row);
  });
}
function clearQueue() {
  state.queue = []; state.idx = -1; state.history = [];
  audio.pause(); audio.removeAttribute("src");
  updateNowPlaying(null, 0, 0);
  setPlayIcons(false);
  renderQueuePage();
  saveState();
}

/* ---------------- 我的下载 / 本地音乐库 ---------------- */
async function downloadTrack(track) {
  if (!track || !track.name) { toast("暂不支持下载该歌曲"); return; }
  if (track.local) { toast("该歌曲已在本地"); return; }
  toast("开始下载: " + track.name);
  try {
    // 首页热歌等无 rid 时由服务端按「歌手 歌名」现解析
    const res = await postJson("/api/download", {
      rid: track.rid || "", title: track.name, artist: track.artist || "",
      cover: track.cover || "", br: state.br,
    });
    if (res && res.ok) {
      toast("已开始下载，完成后可在“我的”查看");
      refreshDownloads();
    } else {
      toast((res && res.error) || "下载失败");
    }
  } catch (e) {
    toast("下载请求失败");
  }
}

function dlDisplayName(fn) {
  const m = /《([^》]+)》/.exec(fn || "");
  return m ? m[1] : String(fn || "").replace(/\.mp3$/i, "");
}
/** 曲目显示名: 本地文件取《歌名》.mp3 里的歌名, 在线曲目直接用歌名。 */
function trackLabel(t) {
  if (!t) return "";
  return t.local ? dlDisplayName(t.name) : (t.name || "");
}

async function refreshDownloads() {
  try {
    const data = await fetchJson("/api/downloads", 15000);
    state.downloads = data.items || [];
  } catch (e) {
    state.downloads = [];
  }
  renderDownloads();
  let busy = false;
  (state.downloads || []).forEach((it) => {
    if (it.status === "downloading") busy = true;
  });
  // 有下载在跑时每 2s 自刷新; 否则停表
  clearTimeout(state._dlTimer);
  state._dlTimer = null;
  if (busy) {
    state._dlTimer = setTimeout(refreshDownloads, 2000);
  }
}

function renderDownloads() {
  const list = $("dlList");
  if (!list) return;
  list.innerHTML = "";
  const items = state.downloads || [];
  const selOn = _sel.on && _sel.kind === "dl";
  list.classList.toggle("selMode", selOn);
  $("dlEmpty").style.display = items.length ? "none" : "";
  const cur = currentTrack();
  items.forEach((it, i) => {
    const key = it.name;
    const row = document.createElement("div");
    row.className = "row dRow" +
      (cur && cur.local && cur.name === it.name ? " playing" : "") +
      (selOn && _sel.ids.has(key) ? " sel" : "");
    let meta = "";
    if (it.dur) meta += escapeHtml(it.dur);
    if (it.size) meta += (meta ? " · " : "") + escapeHtml(it.size);
    let right;
    if (it.status === "downloading") {
      const pct = it.bytes > 0
        ? Math.min(100, ((it.mb || 0) * 1048576 / it.bytes) * 100) : 0;
      right = '<div class="dlBar"><div class="dlFill" style="width:' +
        pct.toFixed(0) + '%"></div></div><span class="dlPct">' +
        pct.toFixed(0) + '%</span>';
    } else if (it.status === "failed") {
      right = '<span class="dlFail">失败</span>';
    } else {
      right = '<button class="dDel" title="删除">\u2715</button>';
    }
    const disp = dlDisplayName(it.name);
    row.innerHTML =
      (selOn ? '<span class="selBox">\u2713</span>'
             : '<span class="idx">' + (i + 1) + '</span>') +
      '<div class="rInfo"><div class="rName">' +
      escapeHtml(disp) +
      '</div><div class="rArtist">' + meta + '</div></div>' +
      (selOn ? "" : actionBtns({ name: disp }, { download: false }) + right);
    row.addEventListener("click", () => {
      if (Date.now() < _selGuard) return;      // 长按补发的 click, 忽略
      if (selOn) { toggleSel(key); return; }
      if (it.status === "downloading" || it.status === "failed") return;
      playLocal(it.name);
    });
    bindLongPress(row, () => { if (!selOn) enterSelect("dl", key); });
    if (!selOn) {
      bindRowActions(row, { name: disp });
      const del = row.querySelector(".dDel");
      if (del) {
        del.addEventListener("click", (e) => {
          e.stopPropagation();
          deleteLocal(it.name, row);
        });
      }
    }
    list.appendChild(row);
  });
}

/** 下载列表 → 本地曲目队列项 (只含已完成/可播的)。 */
function localTracks() {
  return (state.downloads || [])
    .filter((it) => it && it.name && it.status !== "downloading" && it.status !== "failed")
    .map((it) => ({ local: true, name: it.name, rid: "", artist: "" }));
}

/** 点下载列表里的一首: 播放列表换成整个下载列表, 从这首接着播。 */
function playLocal(name) {
  const list = localTracks();
  let i = list.findIndex((t) => t.name === name);
  if (i < 0) { list.unshift({ local: true, name: name, rid: "", artist: "" }); i = 0; }
  startQueue(list, i);
  if (state.page === "download") renderDownloads();
}

/** 「播放全部」的统一入口: 先清空播放列表, 再把这一批歌整批放进列表, 从 index 开始播。 */
function startQueue(list, index) {
  const items = (list || []).filter((t) => t && t.name);
  if (!items.length) return false;
  // 1) 清空播放列表 (含旧音频, 避免新歌取流失败时旧歌还在响)
  state.queue = [];
  state.idx = -1;
  state.history = [];
  _playSeq++;                       // 让进行中的取流结果作废
  try { audio.pause(); audio.removeAttribute("src"); } catch (e) {}
  updateNowPlaying(null, 0, 0);
  setPlayIcons(false);
  // 2) 整批加入列表并开始播
  items.forEach((t) => state.queue.push(t));
  const i = (index >= 0 && index < items.length) ? index : 0;
  state.idx = i;
  playTrack(state.queue[i], i);
  saveState();
  if (state.page === "queue") renderQueuePage();
  return true;
}

/** 收藏夹「全部播放」: 只放收藏夹里的歌。 */
function playAllFav() {
  const list = (state.favorites || []).map((t) => ({
    rid: t.rid || "", name: t.name, artist: t.artist || "",
    cover: t.cover || "", local: !!t.local,
  }));
  if (!list.length) { toast("收藏夹是空的"); return; }
  startQueue(list, 0);
  openPlayer();
}

/** 下载列表「全部播放」: 只播已下载到本地的歌。 */
function playAllLocal() {
  const list = localTracks();
  if (!list.length) { toast("还没有下载歌曲"); return; }
  startQueue(list, 0);
  openPlayer();
}

async function deleteLocal(name, rowEl) {
  try {
    const res = await delJson("/api/download?name=" + encodeURIComponent(name));
    if (res && res.ok) {
      toast("已删除");
      if (currentTrack() && currentTrack().local &&
          currentTrack().name === name) {
        audio.pause(); audio.removeAttribute("src");
        updateNowPlaying(null, 0, 0);
      }
      return refreshDownloads();
    }
    toast((res && res.error) || "删除失败");
  } catch (e) {
    toast("删除失败");
  }
}

/* ---------------- 观看 MV (网易云 <video> / B站 iframe) ---------------- */
async function watchMv(item) {
  if (!item || !item.name) return;
  const title = /\.mp3$/i.test(item.name) ? dlDisplayName(item.name) : item.name;
  const kw = (item.artist ? item.artist.split(" / ")[0] + " " : "") + title;
  toast("正在获取 MV…");
  try {
    const data = await fetchJson(
      "/api/mv/search?kw=" + encodeURIComponent(kw)
      + "&title=" + encodeURIComponent(title)
      + "&artist=" + encodeURIComponent(item.artist || "") + "&limit=8", 25000);
    const items = (data.items || []).filter((x) => x && (x.bvid || x.id));
    if (!items.length) { toast("未找到该歌曲的 MV"); return; }
    state.mvList = items;
    state.mvIndex = 0;
    openMvOverlay();
  } catch (e) {
    toast("MV 获取失败");
  }
}
let _mvResume = false;   // 放 MV 前音乐是否在播 (退出 MV 后接着放)
function openMvOverlay() {
  const mv = state.mvList[state.mvIndex];
  if (!mv) return;
  // MV 自带声音: 先把音乐停掉, 免得两路声音叠在一起; 退出时再接着放
  _mvResume = !audio.paused;
  if (!audio.paused) {
    audio.pause();
    setPlayIcons(false);
    saveState();
  }
  setMvTitle(mv);
  playMv(mv);
  $("mvList").classList.remove("on");
  $("mvOverlay").style.display = "flex";
  renderMvCandidates();
  history.pushState({ page: "mv" }, "");
}
function setMvTitle(mv) {
  $("mvTitle").textContent = mv.name + (mv.artist ? "  ·  " + mv.artist : "");
}
function playMv(mv) {
  const video = $("mvVideo"), frame = $("mvFrame");
  if (!mv) return;
  if (mv.source === "netease") {
    // 网易云: 详情接口取签名 mp4 直链 (短时效, 每次现取), 用 <video> 播
    frame.style.display = "none";
    frame.removeAttribute("src");
    video.style.display = "";
    video.removeAttribute("src");
    fetchJson("/api/mv/url?id=" + mv.id, 25000).then((d) => {
      if (!d || !d.url) { toast("该 MV 暂不可播放"); return; }
      video.src = d.url;
      const p = video.play();
      if (p && p.catch) p.catch(() => {});
    }).catch(() => toast("MV 解析失败"));
  } else {
    // B站: 取内嵌播放地址(JSON) 再设为 iframe.src (之前误把 JSON 接口当页面直接塞进去 → 显示 JSON 文本)
    try { video.pause(); } catch (e) {}
    video.style.display = "none";
    video.removeAttribute("src");
    frame.style.display = "";
    frame.removeAttribute("src");
    fetchJson("/api/mv/embed?bvid=" + mv.bvid, 15000).then((d) => {
      frame.src = (d && d.url) ? d.url : ("https://player.bilibili.com/player.html"
        + "?bvid=" + mv.bvid + "&page=1&autoplay=1&danmaku=0"
        + "&high_quality=1&as_wide=1");
    }).catch(() => {
      frame.src = "https://player.bilibili.com/player.html?bvid=" + mv.bvid
        + "&page=1&autoplay=1&danmaku=0&high_quality=1&as_wide=1";
    });
  }
}
function renderMvCandidates() {
  const box = $("mvList");
  box.innerHTML = "";
  const items = state.mvList || [];
  box.classList.toggle("on", items.length > 1);
  items.forEach((mv, i) => {
    const row = document.createElement("div");
    row.className = "mvItem" + (i === state.mvIndex ? " cur" : "");
    const isNt = mv.source === "netease";
    const tag = isNt ? "网易云" : "B站";
    const tagCls = isNt ? "nt" : "bili";
    const cover = mv.cover
      ? '<img class="miCover" src="' + mv.cover + '" onerror="this.style.visibility=\'hidden\'">'
      : '<div class="miCover"></div>';
    let sub = escapeHtml(mv.artist || "");
    if (mv.play) sub += (sub ? " · " : "") + fmtCount(mv.play) + "次播放";
    row.innerHTML = cover +
      '<div class="miInfo"><div class="miName">' + escapeHtml(mv.name) +
      '</div><div class="miSub">' + sub + '</div></div>' +
      '<span class="miTag ' + tagCls + '">' + tag + '</span>';
    row.addEventListener("click", () => {
      state.mvIndex = i;
      setMvTitle(mv);
      renderMvCandidates();
      playMv(mv);
    });
    box.appendChild(row);
  });
}
function toggleMvList() {
  $("mvList").classList.toggle("on");
}
function hideMvOverlay() {
  const video = $("mvVideo"), frame = $("mvFrame");
  try { video.pause(); } catch (e) {}
  video.removeAttribute("src");
  frame.removeAttribute("src");
  $("mvOverlay").style.display = "none";
  $("mvList").classList.remove("on");
  // 退出 MV: 接着放刚才被打断的音乐
  if (_mvResume) {
    _mvResume = false;
    if (state.idx >= 0 && audio.src) {
      audio.play().then(() => setPlayIcons(true)).catch(() => {});
    } else if (state.idx >= 0) {
      playTrack(state.queue[state.idx], state.idx, null, true);
    }
  }
}
function closeMvOverlay() {
  hideMvOverlay();
  if (history.state && history.state.page === "mv") history.back();
}
/** 全屏: 网易云 <video> 直接请求全屏; B站 iframe 用它自带的全屏按钮 */
function toggleMvFullscreen() {
  const video = $("mvVideo"), frame = $("mvFrame");
  const iframeActive = frame && frame.style.display !== "none";
  const el = iframeActive ? frame : video;
  const doc = document;
  const fsEl = doc.fullscreenElement || doc.webkitFullscreenElement;
  try {
    if (!fsEl) {
      if (el.requestFullscreen) el.requestFullscreen();
      else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
      else if (el.webkitEnterFullscreen) el.webkitEnterFullscreen();
      else if (iframeActive) { toast("请点 B站播放器右下角的全屏按钮"); return; }
      else toast("当前环境不支持全屏");
    } else {
      if (doc.exitFullscreen) doc.exitFullscreen();
      else if (doc.webkitExitFullscreen) doc.webkitExitFullscreen();
    }
  } catch (e) {
    toast(iframeActive ? "请点 B站播放器内的全屏按钮" : "全屏失败");
  }
}

/* ---------------- 播放 ---------------- */
function currentTrack() {
  return (state.idx >= 0 && state.idx < state.queue.length) ? state.queue[state.idx] : null;
}
/** 无 rid 的曲目 (热榜/网易云歌单) → 用服务端相关性匹配补一个可播放的 rid。
 *  匹配结果在服务端有缓存, 重复播放不必重搜。 */
async function resolveTrack(track) {
  if (track.rid || track.local) return track;
  const r = await postJson("/api/import/match",
                           { items: [{ name: track.name, artist: track.artist || "" }] });
  const m = r && (r.items || [])[0];
  if (!m || !m.matched) throw new Error("未匹配到音源");
  track.rid = m.rid;
  if (!track.cover) track.cover = m.cover || "";
  return track;
}

/** 单曲播放失败 → 自动跳下一首; 连续失败过多才停 (避免坏队列无限空转)。 */
function skipFailed(track) {
  state.skipCount = (state.skipCount || 0) + 1;
  const n = state.queue.length;
  if (state.skipCount > 4 || n <= 1) {
    state.skipCount = 0;
    setPlayIcons(false);
    toast("播放失败，已停止");
    return;
  }
  toast("《" + (trackLabel(track) || "该曲") + "》播放失败，已跳过");
  const i = (state.idx + 1) % n;
  playTrack(state.queue[i], i, null, true);
}

async function playTrack(track, index, seekTo, auto) {
  const seq = ++_playSeq;
  state.idx = index;
  state.errorCount = 0;
  state.lastPlayAt = Date.now();   // 切歌时间戳: 过滤旧音频的 ended/error 误触发
  // 只有显式传入 seekTo 才应用跳转 (恢复续播 / 播放器拖动), 避免旧进度串到新歌
  state.pendingSeek = (seekTo != null && seekTo > 0) ? seekTo : null;
  updateNowPlaying(track, 0, 0);
  setPlayIcons(true);
  state.lyrics = []; $("lyricsLines").innerHTML = ""; $("lyricsHint").style.display = "none";
  try {
    const url = track.local
      ? "/api/audio?name=" + encodeURIComponent(track.name)
      : null;
    if (track.local) {
      audio.src = url;
      state.pendingSeek = (seekTo != null && seekTo > 0) ? seekTo : null;
      await audio.play();
      if (seq !== _playSeq) return;
      updateNowPlaying(track, 0, 0);
    } else {
      await resolveTrack(track);
      if (seq !== _playSeq) return;              // 期间已切歌, 丢弃过期结果
      const data = await fetchJson("/api/stream?rid=" + track.rid + "&br=" + state.br);
      if (seq !== _playSeq) return;              // 期间已切歌, 丢弃过期结果
      if (!data.url) throw new Error("no url");
      audio.src = data.url;
      await audio.play();
      if (seq !== _playSeq) return;
    }
    state.skipCount = 0;
  } catch (e) {
    if (seq !== _playSeq) return;
    if (auto) { skipFailed(track); return; }     // 自动连播中失败: 跳过, 别整列停住
    toast("播放失败，请重试");
    setPlayIcons(false);
  }
  loadLyrics(track);
  if (state.page === "queue") renderQueuePage();
  saveState();
}
function updateNowPlaying(track, pos, dur) {
  if (!track) {
    $("pbTitle").textContent = "未在播放";
    $("pbArtist").textContent = "";
    $("pbCover").style.display = "none";
    $("playerTitle").textContent = "";
    $("playerArtist").textContent = "";
    $("playerCover").style.display = "none";
    setProgressMini(0); setProgress(0, 0);
    $("pbCur").textContent = "0:00"; $("pbTotal").textContent = "0:00";
    updatePlayerBg("");
    updatePlayerFav();
    return;
  }
  $("pbTitle").textContent = trackLabel(track) || "未知歌曲";
  $("pbArtist").textContent = track.artist || "";
  $("playerTitle").textContent = trackLabel(track);
  $("playerArtist").textContent = track.artist || "";
  const img = $("pbCover"), pimg = $("playerCover");
  img.onerror = () => { img.style.display = "none"; };
  pimg.onerror = () => { pimg.style.display = "none"; updatePlayerBg(""); };
  const cover = track.local
    ? ("/api/audio_cover?name=" + encodeURIComponent(track.name))
    : (track.cover || "");
  if (cover) {
    img.src = cover; img.style.display = "";
    pimg.src = cover; pimg.style.display = "";
  } else {
    img.style.display = "none"; pimg.style.display = "none";
  }
  updatePlayerBg(cover || "");
  setProgressMini(pos);
  setProgress(pos, dur || audio.duration || 0);
  $("pbCur").textContent = fmt(pos);
  $("pbTotal").textContent = fmt(dur || audio.duration || 0);
  updatePlayerFav();
  notifyNative();
}
function updatePlayerBg(cover) {
  const bg = document.querySelector("#playerBg .bgImg");
  if (!bg) return;
  // 只设 backgroundImage, 不要再写 background=""(那会清掉图片)
  bg.style.backgroundImage = cover ? "url('" + cover + "')" : "none";
}
function setProgress(pos, dur) {
  dur = dur || audio.duration || 0;
  const pct = dur > 0 ? Math.max(0, Math.min(100, (pos / dur) * 100)) : 0;
  $("pbFill").style.width = pct + "%";
  $("pbDot").style.left = pct + "%";
}
function setProgressMini(pos) {
  const dur = audio.duration || 0;
  const pct = dur > 0 ? Math.max(0, Math.min(100, (pos / dur) * 100)) : 0;
  $("pbFillMini").style.width = pct + "%";
}
function setPlayIcons(playing) {
  const g = playing ? ICON_PAUSE : ICON_PLAY;
  $("pbPlay").innerHTML = g;
  $("playerPlay").innerHTML = g;
  notifyNative();
}

let _nativeKey = "";
/** 同步 "正在播放" 给安卓端 (前台服务 → 通知 / 锁屏 / 耳机按键)。
 *  浏览器与桌面版没有 AndroidPlayer 桥, 静默跳过。 */
function notifyNative() {
  const p = window.AndroidPlayer;
  if (!p || !p.setNowPlaying) return;
  const t = currentTrack();
  if (!t) {
    if (_nativeKey) { _nativeKey = ""; try { p.clear(); } catch (e) {} }
    return;
  }
  const playing = !audio.paused;
  const cover = t.local
    ? (location.origin + "/api/audio_cover?name=" + encodeURIComponent(t.name))
    : (t.cover || "");
  const key = [trackLabel(t), t.artist || "", playing ? "1" : "0", cover].join("|");
  if (key === _nativeKey) return;      // 没变化就别重启服务
  _nativeKey = key;
  try { p.setNowPlaying(trackLabel(t), t.artist || "", playing, cover); } catch (e) {}
}
function updateVolIcon() {
  $("volIcon").innerHTML = (audio.muted || state.volume === 0) ? ICON_MUTE : ICON_VOL;
}
function togglePlay() {
  if (state.idx < 0 && state.queue.length) { state.idx = 0; playTrack(state.queue[0], 0); return; }
  if (state.idx < 0) return;
  if (audio.paused) {
    if (audio.ended) audio.currentTime = 0;      // 顺序播放到结尾后, 再按播放从头开始
    if (!audio.src) {
      const seek = state.pendingSeek;            // 会话恢复/进度条拖动 的待跳转位置
      state.pendingSeek = null;
      playTrack(state.queue[state.idx], state.idx, seek);
    } else {
      audio.play().catch(() => toast("播放失败"));
      setPlayIcons(true);
    }
  } else {
    audio.pause(); setPlayIcons(false);
  }
  saveState();
}
function prevNext(d) {
  const n = state.queue.length;
  if (!n) return;
  const cur = state.idx;
  let i;
  if (d > 0) {
    // 下一首: 随机模式随机挑一首 (避免与当前相同); 其它模式顺序 +1
    if (cur >= 0) pushHistory(cur);
    if (state.mode === 3 && n > 1) {
      do { i = Math.floor(Math.random() * n); } while (i === cur);
    } else {
      i = cur < 0 ? 0 : (cur + 1) % n;
    }
  } else {
    // 上一首: 随机模式回退到上一首播过的 (历史栈); 无历史则顺序 -1
    if (state.mode === 3 && state.history.length) {
      i = state.history.pop();
    } else {
      i = cur < 0 ? n - 1 : (cur - 1 + n) % n;
    }
  }
  playTrack(state.queue[i], i);
}
function pushHistory(idx) {
  if (idx < 0) return;
  state.history.push(idx);
  if (state.history.length > 50) state.history.shift();
}
function onEnded() {
  // 切歌后短时间内旧音频可能触发 ended/error, 直接忽略 (避免误切歌/污染历史)
  if (Date.now() - state.lastPlayAt < 1500) return;
  const n = state.queue.length;
  if (!n) { setPlayIcons(false); saveState(); return; }
  let next;
  if (state.mode === 2) {
    // 单曲循环: 直接重播, 不必重新解析在线直链
    audio.currentTime = 0;
    audio.play().catch(() => {});
    setPlayIcons(true);
    return;
  } else if (state.mode === 3) {
    // 随机: 避免与当前曲目相同 (仅一首时无所谓)
    if (n > 1) {
      let r;
      do { r = Math.floor(Math.random() * n); } while (r === state.idx);
      next = r;
    } else next = state.idx;
  } else if (state.mode === 0) {
    // 顺序: 播完最后一首即停, 进度归零 (再按播放从头开始)
    if (state.idx >= n - 1) {
      audio.currentTime = 0;
      setPlayIcons(false); saveState(); return;
    }
    next = state.idx + 1;
  } else {
    next = (state.idx + 1) % n;
  }
  pushHistory(state.idx);   // 自动切歌也记入历史, 便于随机模式"上一首"回退
  playTrack(state.queue[next], next, null, true);
}
function cycleMode() {
  state.mode = (state.mode + 1) % 4;
  setModeUI();
  toast(MODE_NAMES[state.mode]);
  saveState();
}
function setModeUI() {
  $("playerMode").textContent = MODE_SHORT[state.mode];
}

/* ---------------- 全屏播放器 ---------------- */
function openPlayer() {
  if (!currentTrack()) return;
  $("player").style.display = "flex";
  if (!state.lyrics.length) {
    const hint = $("lyricsHint");
    hint.style.display = "flex"; hint.textContent = "暂无歌词";
  } else {
    positionLyrics(curLyricLine());
  }
  history.pushState({ page: "player" }, "");
}
/** 只隐藏播放器界面, 不碰 history —— 用于"从播放器跳到别的页面"。
 *  (若在这里 history.back(), 它的 popstate 是异步的, 会把刚切好的页面覆盖回去) */
function hidePlayer() {
  $("player").style.display = "none";
}
function closePlayer() {
  $("player").style.display = "none";
  // 若播放器历史项在最上层, 移除它 (↓ 按钮关闭 / 底部导航跳走时保持返回键干净)
  if (history.state && history.state.page === "player") {
    history.back();
  }
}

/* ---------------- 歌词 ---------------- */
async function loadLyrics(track) {
  state.lyrics = [];
  const hint = $("lyricsHint");
  $("lyricsLines").innerHTML = "";
  hint.style.display = "flex"; hint.textContent = "加载歌词...";
  try {
    // 本地曲目: 走同名 .lrc / 内嵌歌词; 在线曲目: 按 rid 抓 (歌名歌手兜底)
    const q = track.local
      ? ("name=" + encodeURIComponent(track.name)
         + "&title=" + encodeURIComponent(trackLabel(track))
         + "&artist=" + encodeURIComponent(track.artist || ""))
      : ("rid=" + encodeURIComponent(track.rid || "")
         + "&title=" + encodeURIComponent(track.name)
         + "&artist=" + encodeURIComponent(track.artist || ""));
    const data = await fetchJson("/api/lyrics?" + q);
    state.lyrics = data.lines || [];
  } catch (e) { state.lyrics = []; }
  renderLyrics();
}
function renderLyrics() {
  const wrap = $("lyricsLines");
  wrap.innerHTML = "";
  const hint = $("lyricsHint");
  if (!state.lyrics.length) {
    hint.style.display = "flex"; hint.textContent = "暂无歌词";
    return;
  }
  hint.style.display = "none";
  state.lyrics.forEach((line) => {
    const div = document.createElement("div");
    div.className = "lyrLine";
    div.textContent = line[1] || " ";
    wrap.appendChild(div);
  });
  updateLyrics(audio.currentTime * 1000);
}
function curLyricLine() {
  const ms = audio.currentTime * 1000;
  let i = 0;
  for (let j = 0; j < state.lyrics.length; j++) { if (state.lyrics[j][0] <= ms) i = j; else break; }
  return i;
}
const LYR_CENTER = 0.42;   // 当前/目标行在歌词区的垂直锚点比例

function positionLyrics(line) {
  const lines = $("lyricsLines").children;
  if (!lines.length) return;
  highlightLyrics(line);
  const cur = lines[line];
  if (cur) {
    const scroll = $("lyricsScroll");
    const t = -(cur.offsetTop - scroll.clientHeight * LYR_CENTER);
    state.lyrTranslate = t;
    $("lyricsLines").style.transform = "translateY(" + t + "px)";
  }
}
function highlightLyrics(line) {
  const lines = $("lyricsLines").children;
  for (let k = 0; k < lines.length; k++) {
    lines[k].classList.toggle("cur", k === line);
    lines[k].classList.toggle("dim", Math.abs(k - line) >= 3);
  }
}
function updateLyrics(ms) {
  if (state.lyrDragging || !state.lyrics.length) return;
  positionLyrics(curLyricLine());
}
/** 歌词区内距参考点最近的行 (拖动/点击定位用) */
function lyricLineAt(refY, translate) {
  const lines = $("lyricsLines").children;
  let best = 0, bd = Infinity;
  for (let i = 0; i < lines.length; i++) {
    const d = Math.abs((lines[i].offsetTop + lines[i].offsetHeight / 2)
                       - (refY - translate));
    if (d < bd) { bd = d; best = i; }
  }
  return best;
}
function seekToLyricLine(line) {
  if (!state.lyrics[line]) return;
  const ms = state.lyrics[line][0];
  if (audio.src && audio.duration) {
    audio.currentTime = ms / 1000;
    setProgress(audio.currentTime, audio.duration);
    setProgressMini(audio.currentTime);
    $("pbCur").textContent = fmt(audio.currentTime);
  } else if (currentTrack()) {
    state.pendingSeek = ms / 1000;
    setProgress(state.pendingSeek, audio.duration || 0);
    $("pbCur").textContent = fmt(state.pendingSeek);
  }
  positionLyrics(line);
}

/* 歌词上下滑动调整进度 (主流设计: 跟随手指 + 中心指示线 + 时间气泡 + 松手跳转) */
(function () {
  const scroll = $("lyricsScroll");
  let drag = null;

  function dragUI(on) {
    const c = $("lyrCenter"), b = $("lyrBadge");
    if (c) c.classList.toggle("on", on);
    if (!b) return;
    b.style.display = on ? "block" : "none";
    if (on && drag && state.lyrics[drag.target]) {
      b.textContent = fmt(state.lyrics[drag.target][0] / 1000) + "  ·  松手跳转";
    }
  }

  scroll.addEventListener("pointerdown", (e) => {
    if (!state.lyrics.length) return;
    const lines = $("lyricsLines").children;
    if (!lines.length) return;
    const rect = scroll.getBoundingClientRect();
    const startTranslate = (state.lyrTranslate != null) ? state.lyrTranslate : 0;
    drag = {
      startY: e.clientY,
      startTranslate: startTranslate,
      moved: false,
      target: curLyricLine(),
      tapped: lyricLineAt(e.clientY - rect.top, startTranslate),
    };
    state.lyrDragging = true;
    $("lyricsLines").classList.add("dragging");   // 拖动时禁用滚动动画, 直接跟手
    dragUI(true);
    try { scroll.setPointerCapture(e.pointerId); } catch (err) {}
    e.preventDefault();
    e.stopPropagation();
  });

  // 兜底: 拖动期间阻止原生滚动/回弹抢走手势 (老 WebView 不支持 touch-action 时)
  scroll.addEventListener("touchmove", (e) => {
    if (state.lyrDragging) e.preventDefault();
  }, { passive: false });

  scroll.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dy = e.clientY - drag.startY;
    if (Math.abs(dy) > 4) drag.moved = true;
    const t = drag.startTranslate + dy;
    state.lyrTranslate = t;
    $("lyricsLines").style.transform = "translateY(" + t + "px)";
    drag.target = lyricLineAt(scroll.clientHeight * LYR_CENTER, t);
    highlightLyrics(drag.target);
    dragUI(true);           // 同步刷新气泡时间
  });

  function endDrag() {
    if (!drag) return;
    const moved = drag.moved;
    const line = moved ? drag.target : drag.tapped;
    drag = null;
    state.lyrDragging = false;
    state.lyrTranslate = null;
    $("lyricsLines").classList.remove("dragging");
    dragUI(false);
    if (moved && line === curLyricLine()) {
      positionLyrics(line);          // 未跨行, 回到播放位置
    } else {
      seekToLyricLine(line);         // 单击行 / 拖到别的行 → 跳转
    }
  }
  scroll.addEventListener("pointerup", endDrag);
  // 手势被系统取消时也结算 (按当前预览行跳转), 不再静默丢弃 → 避免"断触后无反应"
  scroll.addEventListener("pointercancel", endDrag);
  // 兜底: 万一 setPointerCapture 失败, 手指移出歌词区仍能收尾
  document.addEventListener("pointerup", () => { if (drag) endDrag(); });
  document.addEventListener("pointercancel", () => { if (drag) endDrag(); });
})();

/* ---------------- 事件绑定 ---------------- */
function bindEvents() {
  // 页面/导航
  document.querySelectorAll(".navItem").forEach((b) => {
    b.addEventListener("click", () => showPage(b.dataset.page));
  });
  // 搜索
  $("searchBtn").addEventListener("click", () => {
    const kw = $("searchInput").value.trim();
    if (kw) doSearch(kw, 1, false);
  });
  $("searchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const kw = e.target.value.trim();
      if (kw) doSearch(kw, 1, false);
    }
  });
  $("backHome").addEventListener("click", () => showPage("home"));
  const hot = $("hotList");
  hot.innerHTML = "";
  HOT_WORDS.forEach((w) => {
    const c = document.createElement("button");
    c.className = "hotChip"; c.textContent = w;
    c.addEventListener("click", () => {
      $("searchInput").value = w;
      doSearch(w, 1, false);
    });
    hot.appendChild(c);
  });
  // 音质 (搜索页下拉 与 设置面板分段控件 双向同步)
  $("brSelect").addEventListener("change", (e) => setQuality(e.target.value));
  // 播放条
  $("pbPlay").addEventListener("click", (e) => { e.stopPropagation(); togglePlay(); });
  $("pbPrev").addEventListener("click", (e) => { e.stopPropagation(); prevNext(-1); });
  $("pbNext").addEventListener("click", (e) => { e.stopPropagation(); prevNext(1); });
  // 播放器
  $("playerClose").addEventListener("click", closePlayer);
  $("playerSettings").addEventListener("click", openSettings);
  $("playerPlay").addEventListener("click", togglePlay);
  $("playerPrev").addEventListener("click", () => prevNext(-1));
  $("playerNext").addEventListener("click", () => prevNext(1));
  $("playerMode").addEventListener("click", cycleMode);
  $("playerQueue").addEventListener("click", () => { hidePlayer(); showPage("queue"); });
  // 播放器: 收藏 / 下载 / 观看MV
  $("playerFav").addEventListener("click", () => toggleFav(currentTrack()));
  $("playerDl").addEventListener("click", () => {
    const t = currentTrack();
    if (!t) return;
    if (t.local) { toast("该歌曲已在本地"); return; }
    downloadTrack(t);
  });
  $("playerMv").addEventListener("click", () => {
    const t = currentTrack();
    if (!t) return;
    watchMv(t.local ? { name: dlDisplayName(t.name), artist: "" } : t);
  });
  // MV 播放层
  $("mvClose").addEventListener("click", closeMvOverlay);
  $("mvMore").addEventListener("click", toggleMvList);
  $("mvFull").addEventListener("click", toggleMvFullscreen);
  $("qpClear").addEventListener("click", clearQueue);
  // 音量
  $("volIcon").addEventListener("click", () => {
    audio.muted = !audio.muted;
    updateVolIcon();
    saveState();
  });
  $("pbVol").addEventListener("input", (e) => {
    state.volume = parseInt(e.target.value, 10);
    audio.volume = state.volume / 100;
    updateVolPct();
    updateVolIcon();
    saveState();
  });
  // 音频事件
  audio.addEventListener("timeupdate", () => {
    // 当前播放时间 (之前这里漏了, 导致歌词界面/播放器的时间一直停在切歌时的 0:00)
    $("pbCur").textContent = fmt(audio.currentTime);
    if (isFinite(audio.duration) && audio.duration > 0) {
      $("pbTotal").textContent = fmt(audio.duration);
    }
    setProgress(audio.currentTime, audio.duration);
    setProgressMini(audio.currentTime);
    updateLyrics(audio.currentTime * 1000);
    saveStateThrottled();
  });
  audio.addEventListener("durationchange", () => {
    $("pbTotal").textContent = fmt(audio.duration);
    setProgress(audio.currentTime, audio.duration);
    setProgressMini(audio.currentTime);
  });
  audio.addEventListener("loadedmetadata", () => {
    if (state.pendingSeek != null) {
      audio.currentTime = state.pendingSeek;
      state.pendingSeek = null;
    }
  });
  audio.addEventListener("ended", onEnded);
  audio.addEventListener("error", () => {
    if (Date.now() - state.lastPlayAt < 1500) return;   // 切歌瞬间的旧音频错误忽略
    const t = currentTrack();
    if (!t) { toast("播放失败"); setPlayIcons(false); return; }
    skipFailed(t);                                      // 连播中失败: 自动跳过
  });
  audio.volume = state.volume / 100;

  // 播放器进度拖动
  const prog = $("pbProgress");
  function seekFromEvent(e) {
    const r = prog.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    const dur = audio.duration || 0;
    const t = x * dur;
    if (dur > 0 && audio.src) { audio.currentTime = t; }
    else if (currentTrack()) { state.pendingSeek = t; }
    setProgress(t, dur); setProgressMini(t);
    $("pbCur").textContent = fmt(t);
  }
  prog.addEventListener("pointerdown", (e) => {
    try { prog.setPointerCapture(e.pointerId); } catch (err) {}
    seekFromEvent(e);
  });
  prog.addEventListener("pointermove", (e) => { if (e.buttons) seekFromEvent(e); });

  // 搜索无限滚动
  $("searchView").addEventListener("scroll", (ev) => {
    const el = ev.target;
    if (state.hasMore && !state.loadingMore &&
        el.scrollTop + el.clientHeight >= el.scrollHeight - 90) {
      doSearch(state.kw, state.page + 1, true);
    }
  });
  document.addEventListener("visibilitychange", saveState);
}

/* ---------------- 初始化 ---------------- */
function init() {
  // 供内联 onclick 调用的全局入口
  window.app = {
    goSearch: () => showPage("search"),
    goHome: () => showPage("home"),
    openPlayer: openPlayer,
    playRandomHot: playRandomHot,
    reloadHome: reloadHome,
    openSettings: openSettings,
    closeSettings: closeSettings,
    downloadTrack: downloadTrack,
    watchMv: watchMv,
    closeMvOverlay: closeMvOverlay,
    refreshDownloads: refreshDownloads,
    playLocal: playLocal,
    playAllLocal: playAllLocal,
    playAllFav: playAllFav,
    deleteLocal: deleteLocal,
    enterSelect: enterSelect,
    exitSelect: exitSelect,
    selAll: selAll,
    selJunk: selJunk,
    selDelete: selDelete,
    openImport: openImport,
    closeImport: closeImport,
    impLogin: impLogin,
    impLogout: impLogout,
    impPublic: impPublic,
    impText: impText,
    impImage: impImage,
    impMode: impMode,
    onOcrText: onOcrText,
    impPublicPrompt: impPublicPrompt,
    impCancel: impCancel,
    // 安卓端通知/锁屏/耳机按键 → 网页播放控制
    mediaCmd: (cmd) => {
      if (cmd === "play") { if (audio.paused) togglePlay(); }
      else if (cmd === "toggle") togglePlay();
      else if (cmd === "pause") {
        if (!audio.paused) { audio.pause(); setPlayIcons(false); saveState(); }
      } else if (cmd === "next") prevNext(1);
      else if (cmd === "prev") prevNext(-1);
    },
  };
  buildThemeDots($("themeDots"));
  buildBrSeg();
  bindEvents();
  loadFavorites();
  restoreState();
  setModeUI();          // 始终刷新模式按钮文字 (无存档时也要)
  showPage("home");
  setPlayIcons(false);
  updateVolIcon();
  updatePlayerFav();
  updateVolPct();
  loadHome();
}
document.addEventListener("DOMContentLoaded", init);