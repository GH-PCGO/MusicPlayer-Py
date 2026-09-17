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
function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
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

/* ---------------- 页面切换 ---------------- */
function renderPage(name) {
  state.page = name;
  ["home", "search", "queue"].forEach((p) => {
    $(p + "View").style.display = p === name ? "" : "none";
  });
  document.querySelectorAll(".navItem").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === name);
  });
  if (name === "queue") renderQueuePage();
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
  if ($("player").style.display !== "none") {
    $("player").style.display = "none";
    return;
  }
  const p = history.state && history.state.page;
  if (p === "player") return;                 // 过期的播放器条目
  if (p && p !== state.page && ["home", "search", "queue"].includes(p)) {
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
      '<span class="hotPlay">' + ICON_PLAY_SM + '</span>';
    row.addEventListener("click", () => playByName(it.name, it.artist));
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

/** 点热歌/搜索结果: 按"歌手 歌名"在酷我搜索并播放第一条 */
async function playByName(name, artist) {
  toast("加载中: " + name);
  try {
    const kw = artist ? (artist.split(" / ")[0] + " " + name) : name;
    const data = await fetchJson("/api/search?kw=" + encodeURIComponent(kw) + "&pn=1", 20000);
    const items = (data.items || []).filter((x) => x && x.rid);
    if (!items.length) { toast("未找到: " + name); return; }
    state.results = items;
    state.resultBase = 0;
    renderResults(items, false);
    state.queue = items.slice(0);
    state.idx = 0;
    state.history = [];
    playTrack(state.queue[0], 0);
    openPlayer();
  } catch (e) {
    toast("加载失败，请重试");
  }
}

/** 每日推荐: 随机播一首热歌 */
function playRandomHot() {
  if (!_hotSongs.length) { toast("推荐加载中…"); return; }
  const it = _hotSongs[Math.floor(Math.random() * _hotSongs.length)];
  playByName(it.name, it.artist);
}

function reloadHome() {
  loadHome();
  toast("已刷新推荐");
}

/** 打开歌单: 拉取歌曲 → 播放第一首, 队列=整个歌单 */
async function openPlaylist(id, name) {
  toast("加载歌单: " + name);
  try {
    const data = await fetchJson("/api/playlist?id=" + id + "&limit=50", 25000);
    const items = (data.items || []).filter((x) => x && x.name);
    if (!items.length) { toast("歌单为空"); return; }
    // 用结果页展示歌单, 再从酷我匹配播放
    state.kw = name;
    const first = items[0];
    playByName(first.name, first.artist);
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
      '<button class="addBtn">+</button>';
    row.addEventListener("click", () => playFromResults(idx));
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
  state.queue = state.results.slice(i);
  state.idx = 0;
  state.history = [];
  playTrack(state.queue[0], 0);
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
      '<span class="qt">' + escapeHtml(t.name) + '</span>' +
      (i === state.idx ? '<span class="qmark">\u25B6</span>' : "");
    row.addEventListener("click", () => {
      if (i === state.idx) togglePlay();
      else { pushHistory(state.idx); playTrack(state.queue[i], i); }
    });
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

/* ---------------- 播放 ---------------- */
function currentTrack() {
  return (state.idx >= 0 && state.idx < state.queue.length) ? state.queue[state.idx] : null;
}
async function playTrack(track, index, seekTo) {
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
    const data = await fetchJson("/api/stream?rid=" + track.rid + "&br=" + state.br);
    if (seq !== _playSeq) return;              // 期间已切歌, 丢弃过期结果
    if (!data.url) throw new Error("no url");
    audio.src = data.url;
    await audio.play();
    if (seq !== _playSeq) return;
  } catch (e) {
    if (seq !== _playSeq) return;
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
    return;
  }
  $("pbTitle").textContent = track.name || "未知歌曲";
  $("pbArtist").textContent = track.artist || "";
  $("playerTitle").textContent = track.name || "";
  $("playerArtist").textContent = track.artist || "";
  const img = $("pbCover"), pimg = $("playerCover");
  img.onerror = () => { img.style.display = "none"; };
  pimg.onerror = () => { pimg.style.display = "none"; updatePlayerBg(""); };
  if (track.cover) {
    img.src = track.cover; img.style.display = "";
    pimg.src = track.cover; pimg.style.display = "";
  } else {
    img.style.display = "none"; pimg.style.display = "none";
  }
  updatePlayerBg(track.cover || "");
  setProgressMini(pos);
  setProgress(pos, dur || audio.duration || 0);
  $("pbCur").textContent = fmt(pos);
  $("pbTotal").textContent = fmt(dur || audio.duration || 0);
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
  playTrack(state.queue[next], next);
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
    const data = await fetchJson("/api/lyrics?rid=" + track.rid +
      "&title=" + encodeURIComponent(track.name) +
      "&artist=" + encodeURIComponent(track.artist || ""));
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
  $("playerQueue").addEventListener("click", () => { closePlayer(); showPage("queue"); });
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
    if (!currentTrack()) { toast("播放失败"); setPlayIcons(false); return; }
    state.errorCount = (state.errorCount || 0) + 1;
    if (state.errorCount >= 3) {
      // 连续失败: 停止自动跳过, 避免坏歌单无限循环
      setPlayIcons(false);
      toast("连续播放失败，请重试");
      state.errorCount = 0;
      return;
    }
    toast("播放失败，自动播放下一首");
    prevNext(1);
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
  };
  buildThemeDots($("themeDots"));
  buildBrSeg();
  bindEvents();
  restoreState();
  setModeUI();          // 始终刷新模式按钮文字 (无存档时也要)
  showPage("home");
  setPlayIcons(false);
  updateVolIcon();
  updateVolPct();
  loadHome();
}
document.addEventListener("DOMContentLoaded", init);