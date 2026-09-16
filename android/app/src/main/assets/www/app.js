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
  lyrics: [], lyrDragging: false, pendingSeek: null, errorCount: 0,
  page: "home",
};

let _playSeq = 0;   // 快速切歌时丢弃过期的 play() 结果

const REC_SONGS = ["一路向北", "大风吹", "下辈子不一定还能遇见你", "半生雪", "少年",
  "潮汐", "烟雨人间", "雾里", "晴天", "奔赴星空",
  "稻香", "虞兮叹", "青花瓷", "起风了", "难渡",
  "夜曲", "刺客", "霍元甲", "谪仙", "听妈妈的话"];
const REC_GRADS = [
  ["#F97316", "#EF4444"], ["#8B5CF6", "#6366F1"], ["#06B6D4", "#3B82F6"],
  ["#22C55E", "#16A34A"], ["#EC4899", "#F97316"], ["#0EA5E9", "#6366F1"],
  ["#EAB308", "#F97316"], ["#14B8A6", "#06B6D4"], ["#F43F5E", "#EC4899"],
  ["#84CC16", "#22C55E"], ["#64748B", "#334155"], ["#D946EF", "#8B5CF6"],
  ["#F59E0B", "#EF4444"], ["#3B82F6", "#0EA5E9"], ["#22C55E", "#EAB308"],
  ["#A855F7", "#EC4899"], ["#0F766E", "#14B8A6"], ["#DC2626", "#F59E0B"],
  ["#6366F1", "#8B5CF6"], ["#16A34A", "#84CC16"],
];

const audio = new Audio();
audio.preload = "none";
const $ = (id) => document.getElementById(id);

/* SVG 图标 (不依赖设备字体, 避免 ⏮⏭⏸≡ 渲染成豆腐块) */
const ICON_PLAY = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const ICON_PAUSE = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';
const ICON_PREV = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M6 6h2v12H6zM19 6v12l-9-6z"/></svg>';
const ICON_NEXT = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M16 6h2v12h-2zM5 18V6l9 6z"/></svg>';
const ICON_QUEUE = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M4 6h16v2H4zM4 11h16v2H4zM4 16h10v2H4z"/></svg>';
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
  buildRecGrid();   // 推荐卡配色跟随主题
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
    d.addEventListener("click", () => applyTheme(name));
    container.appendChild(d);
  });
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
  buildThemeDots($("playerTheme"));
  $("brSelect").value = state.br;
  $("pbVol").value = state.volume;
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

/* ---------------- 首页 ---------------- */
function buildRecGrid() {
  const grid = $("recGrid");
  if (!grid) return;
  grid.innerHTML = "";
  const accent = THEMES[state.theme].accent;
  REC_SONGS.forEach((name, i) => {
    const card = document.createElement("div");
    card.className = "recCard";
    // 推荐卡用主题色衍生渐变 (与整体配色统一, 不再彩虹撞色)
    const c1 = shade(accent, 0.42 - (i % 3) * 0.06);
    const c2 = shade(accent, -0.18);
    card.innerHTML =
      '<div class="recCover" style="background:linear-gradient(135deg,' + c1 + ',' + c2 + ')">' +
      '<div class="name">' + escapeHtml(name) + '</div></div>' +
      '<div class="recName">' + escapeHtml(name) + '</div>';
    card.addEventListener("click", () => {
      $("searchInput").value = name;
      doSearch(name, 1, false);
      showPage("search");
    });
    grid.appendChild(card);
  });
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
      else playTrack(state.queue[i], i);
    });
    list.appendChild(row);
  });
}
function clearQueue() {
  state.queue = []; state.idx = -1;
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
  let i = state.idx;
  if (i < 0) i = d > 0 ? 0 : n - 1;
  else i = (i + d + n) % n;
  playTrack(state.queue[i], i);
}
function onEnded() {
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
function positionLyrics(line) {
  const lines = $("lyricsLines").children;
  if (!lines.length) return;
  for (let k = 0; k < lines.length; k++) {
    lines[k].classList.toggle("cur", k === line);
    lines[k].classList.toggle("dim", Math.abs(k - line) >= 3);
  }
  const cur = lines[line];
  if (cur) {
    const scroll = $("lyricsScroll");
    const target = cur.offsetTop - scroll.clientHeight * 0.42;
    $("lyricsLines").style.transform = "translateY(" + (-target) + "px)";
  }
}
function updateLyrics(ms) {
  if (state.lyrDragging || !state.lyrics.length) return;
  positionLyrics(curLyricLine());
}

/* 歌词拖拽 → 预览 + 松手 seek (上下滑动播放) */
(function () {
  const scroll = $("lyricsScroll");
  let drag = null;
  scroll.addEventListener("pointerdown", (e) => {
    if (!state.lyrics.length) return;
    const lines = $("lyricsLines").children;
    if (!lines.length) return;
    drag = { startY: e.clientY, startLine: curLyricLine(),
             lineH: lines[0].offsetHeight || 44, moved: false, preview: null };
    state.lyrDragging = true;
    try { scroll.setPointerCapture(e.pointerId); } catch (err) {}
    e.preventDefault();
  });
  scroll.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dy = e.clientY - drag.startY;
    if (Math.abs(dy) > 4) drag.moved = true;
    let line = Math.round(drag.startLine - dy / drag.lineH);
    line = Math.max(0, Math.min(state.lyrics.length - 1, line));
    drag.preview = line;
    positionLyrics(line);
  });
  function endDrag(e) {
    if (!drag) return;
    const line = drag.preview != null ? drag.preview : drag.startLine;
    const wasTap = !drag.moved;
    state.lyrDragging = false;
    drag = null;
    if (wasTap || line !== curLyricLine()) {
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
      updateLyrics(ms);
    }
  }
  scroll.addEventListener("pointerup", endDrag);
  scroll.addEventListener("pointercancel", () => {
    state.lyrDragging = false; drag = null;
  });
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
  // 音质
  $("brSelect").addEventListener("change", (e) => {
    state.br = e.target.value;
    toast("音质已切换为 " + e.target.options[e.target.selectedIndex].text);
    saveState();
  });
  // 播放条
  $("pbPlay").addEventListener("click", (e) => { e.stopPropagation(); togglePlay(); });
  $("pbPrev").addEventListener("click", (e) => { e.stopPropagation(); prevNext(-1); });
  $("pbNext").addEventListener("click", (e) => { e.stopPropagation(); prevNext(1); });
  // 播放器
  $("playerClose").addEventListener("click", closePlayer);
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
  };
  buildThemeDots($("playerTheme"));
  buildRecGrid();
  bindEvents();
  restoreState();
  showPage("home");
  setPlayIcons(false);
  updateVolIcon();
}
document.addEventListener("DOMContentLoaded", init);