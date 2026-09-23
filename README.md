# MusicPlayer (Python 复刻版)

用 Python + Tkinter 复刻的《音乐下载器》桌面应用，对照原 Java Swing 项目 `MusicPlayer-master` 的界面布局与功能逻辑逐项还原。

## 功能

- 热门歌曲推荐（首页 20 首，点击即可搜索）
- 轮播图（每 3 秒自动切换，`url1→url2→url3` 循环）
- 歌曲关键词搜索（酷我，每页 30 条，支持翻页、搜索历史保留重复项）
- 多选下载（复选框列表 + 全选），文件命名为 `《歌名》.mp3`（与原版一致）
- 在线播放（浏览器打开）
- 下载管理（列出已下载歌曲，双击播放）
- 本地音乐扫描（递归扫描指定目录下的 `.mp3`）
- 换肤（5 组主题色预设：绿/蓝/紫/橙/红，`set_accent` 即时生效）
- 设置默认存储位置
- 无边框可拖拽窗口、最小化到托盘

## 界面重设计（浅色极简 + 音乐绿）

在保留原版功能与 1000x600 无边框窗口的基础上，整体视觉重构为现代简约风格（不再逐像素复刻旧背景图）：

- **配色令牌**：内容底 `#F7F8FA`、卡片/侧栏/播放条纯白 `#FFFFFF`、边框 `#E7E9EE`、主文字 `#1F2430`、强调**音乐绿 `#1DB954`**（选中行浅绿底 `#E7F8EE` + 绿字 + 左侧绿条）；`widgets.set_accent()` 支持一键切换强调色（蓝/紫/橙/红预设）
- **字体**：全局微软雅黑（替换原宋体20）
- **布局**：左侧 200px 白侧栏（绿圆音符 Logo + 文字导航胶囊选中）；去掉 200px 大轮播横幅；顶栏圆角胶囊搜索框（浅灰胶囊 + 白色输入 + 绿色圆形搜索钮）+ 右上 4 个圆角图标按钮（设置/下载/最小化/关闭）
- **列表**：表头极浅灰底 + 下边框 + 加粗小字；行白底细分隔 + hover 浅灰 + 选中音乐绿白字白勾；行高 46px
- **推荐卡片**：圆角白卡 + 内缩 1:1 圆角封面 + 底部固定歌名区
- **播放条**：白底浅色重排（曲名/圆形成套传输钮/绿色填充进度条带白圆点/音量/词·外部按钮），右侧不再贴边裁切
- **歌词面板**：浅色底 `#F7F8FA`，当前行深绿加粗 + 浅绿光晕，上下行灰字渐隐，保留 QQ 风格平滑滚动动画
- **对话框**：主题色选择（5 色预设）、存储位置、本地扫描统一浅色卡片

## 与原版的功能还原点

- 主窗口 `1000x600` 无边框可拖拽，面板层级用 `tkraise()` 还原 `JLayeredPane`：内容(500) > 下载管理(400) > 本地音乐(300)，右上角图标置顶(999)；已重设计（见上节），不再使用旧背景图与图片按钮
- 搜索数据格式与原项目一致：`rid 《歌名》 歌手`；列表显示 `序号《歌名》.mp3`；下载文件名保留书名号 `《歌名》.mp3`
- 搜索/点击推荐每次都会往下拉框追加关键词（还原 `box.addItem`，不去重）
- 换肤由「背景图」改为「主题色预设」（`dialogs.ThemeDialog`，绿/蓝/紫/橙/红 5 色，`set_accent` 即时生效）

## 接口说明（`kuwo.py`）

官方已封死旧下载方式（`www.kuwo.cn` 系 csrf 接口返回 `The request is illegal!`；`antiserver.kuwo.cn/anti.s` 只回 ~11s 试听；`mobi.s` 传统 `convert_url` 一律 403），目前采用：

- **搜索**：`http://search.kuwo.cn/r.s?...`（web csrf 两步流程已死，仅作自动回落记录）
- **下载/播放**：`https://mobi.kuwo.cn/mobi.s` 的 **`convert_url_with_sign`** 车载签名接口（伪装酷我车载版 APK 客户端），返回完整全曲地址，**320k 优先、128k 自动回落**，最后才兜底 antiserver 试听；直接用搜索返回的 `rid`，无需 `MUSIC_` 前缀。

## 运行

```bash
pip install -r requirements.txt
python run.py                 # 便捷启动 (无需安装)

# 或安装为包后
pip install -e .
musicplayer                   # 控制台脚本
python -m musicplayer         # 模块方式
```

播放引擎自动选择（`musicplayer.engine.default_engine()`）：
- 装了 `pygame` → 跨平台 `CrossPlatformEngine`（macOS/Windows/Linux 皆可）
- **Windows 且未装 pygame → 自动回退 WinMM MCI 引擎（`engine.MciEngine`，零依赖，无需 pygame）**

若需托盘最小化：

```bash
pip install pystray
```

未安装 pystray 时最小化按钮在无边框窗口下保持现状（有托盘环境的机器上完美还原托盘收起/双击打开/右键菜单）。

## 项目结构

标准 `src` 布局（可 `pip install -e .` 安装）：

```
MusicPlayer-Py/
├── pyproject.toml           # 打包/依赖/控制台脚本
├── requirements.txt
├── run.py                   # 便捷启动 (把 src 加入 sys.path)
├── tests/
│   └── test_core.py         # 纯逻辑单元测试 (pytest 兼容)
├── packaging/               # 打包为 Windows 安装程序 (见"打包"节)
│   ├── MusicPlayer.spec     # 应用本体 PyInstaller 配置 (onedir)
│   ├── installer.spec       # 安装程序配置 (onefile, 内嵌 payload)
│   ├── entry.py             # 冻结/源码双模式入口
│   ├── installer.py         # 自研 Tk 安装器 (安装/卸载/快捷方式/注册表)
│   └── build.py             # 一键打包 (生成图标 + 应用 + 安装程序)
└── src/
    └── musicplayer/
        ├── __init__.py
        ├── __main__.py      # python -m musicplayer
        ├── app.py           # 主界面/全部事件 (原 main.py)
        ├── widgets.py       # 自定义组件 (面板/列表/推荐格/播放条/歌词面板)
        ├── dialogs.py       # 主题色/存储位置/本地扫描/播放队列悬浮层 + 托盘
        ├── kuwo.py          # 酷我搜索 / 直链 / 下载
        ├── lyrics.py        # 纯 Python ID3v2 读写 + 歌词抓取 + LRC 解析
        ├── engine.py        # 播放引擎 (pygame + Windows MCI 回退)
        ├── paths.py         # 资产/数据目录解析
        ├── util.py          # 通用工具 (split_artists 等)
        └── assets/
            ├── app_icon.png       # 应用图标 (任务栏/最小化/托盘/exe)
            ├── logo_wordmark.png  # 左上角 Music. 字标 (白+alpha 掩膜, 按主题色着色)
            └── Pictrue/           # 其它图片资源
```

数据目录（`paths.py`）：源码布局下 `music/`（下载）与 `settings.json` 位于**项目根**；已安装布局下位于 `~/MusicPlayer/`。资产固定随包（`assets/`，其中 `Pictrue` 为旧界面素材）。

## 打包为 Windows 可安装程序

需要 `pip install pyinstaller`（应用还依赖 `pywin32`、`Pillow`、`requests`，打包含自动收集）。

```bash
python packaging/build.py
```

- `[1/3]` 由 `assets/app_icon.png` 生成多尺寸 `packaging/app.ico`（缺失时回落 `<Pictrue>/logo.jpg`）
- `[2/3]` PyInstaller 打包应用本体 → `dist/MusicPlayer/`（onedir，`MusicPlayer.exe`）
- `[3/3]` 打包安装程序 → `dist/MusicPlayerSetup.exe`（单文件，内嵌整个应用目录）

把 `MusicPlayerSetup.exe` 拷到目标 **Windows 10/11** 机，运行即可选择安装位置、勾选桌面/开始菜单快捷方式；卸载走「设置 → 应用」或安装目录下的 `uninstall.bat`（带用户级卸载注册表项）。应用安装到任意目录后数据统一存 `~/MusicPlayer/`，播放引擎自动回退为系统 WinMM MCI，无需装 pygame。

`packaging/installer.py` 为自研 Tk 安装器（`.spec` 打包，无 Inno/NSIS 依赖）：复制 payload、`WScript.Shell` 建快捷方式、写 `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MusicPlayer-Py` 卸载项；命令行 `MusicPlayerSetup.exe --uninstall` 可静默卸载。

## 模块说明

| 模块 (`src/musicplayer/`) | 对应原 Java 文件 | 说明 |
| --- | --- | --- |
| `kuwo.py` | `Search.java` / `Function.saveMusicFile` | 酷我搜索 / 播放直链 / 下载 |
| `widgets.py` | `MyMusicPanel` / `SearchPanel` / `SlidePanel` / `MyJcheckBox` | 背景合成组件、轮播图、推荐网格、复选框列表 |
| `dialogs.py` | `ChangeBackground` / `StorageLocation` / `ReadLocalMusic` | 主题色、存储位置、本地扫描窗口 |
| `app.py` | `Maininterface.java` / `Function.java` | 主界面、层级切换、全部事件 |
| `lyrics.py` | — | 纯 Python ID3v2 USLT 嵌入/读取、Q音/网易云/酷我歌词抓取、LRC 解析 |
| `engine.py` | — | 播放引擎工厂：pygame 跨平台引擎 + Windows winmm MCI 回退引擎 |

## 改动记录

- **安卓 v2.0 歌曲「下载 + 观看MV」**：
  - 每条歌曲（首页热歌榜 / 搜索结果 / 播放队列 / 我的下载 / 全屏播放器）行尾并排两个图标按钮「⬇ 下载 + ▶ MV」（`www` 前端 `actionBtns`，首页热歌无 rid 时由 `webapp._resolve_rid` 按「歌手 歌名」现解析）。
  - **下载入系统媒体库**：新增 `androidstorage.py`，用 Chaquopy `java` 桥经 `ContentResolver` 把下载好的 mp3 (`IS_PENDING=1 → 拷贝 → IS_PENDING=0`) 发布到 `Music/音乐下载器/`，文件管理器 / 系统音乐 App 可见；采用「私有副本 + 媒体库发布」，删除时两边同删。免存储权限。桌面/iPhone 无 java 桥时自动降级为仅私有目录。因 `MediaStore.RELATIVE_PATH/IS_PENDING` 要求，`minSdk` 24 → **29**。
  - **观看MV 双源**：新增 `bilibili.py`（先访问 `www.bilibili.com` 取 `buvid3` cookie + Referer 规避风控，再 `search/type` 拿 `bvid`，`player.bilibili.com` iframe 内嵌播放）；`netease.py` 新增 MV 搜索（`type=1004`）与 MV 详情直链（`api/mv/detail` 的 `brs` 240/480/720/1080，`<video>` 播放，签名短时效故每次现取）。新接口 `/api/mv/search`、`/api/mv/url`、`/api/mv/embed`。点 MV 直接播最佳匹配，MV 全屏层自适应横竖屏（竖屏 16:9 居中黑边、横屏铺满，`100dvh` + 安全区）。
  - `/api/download` 支持无 `rid`（服务端解析）与 `br` 音质；`MainActivity` 注入 Context（`set_android_storage`），`server.py` 转发。
- **手机访问（iPhone / 局域网）**：`src/musicplayer/webapp.py` 共享 HTTP 服务（纯标准库，搜索/在线播放/歌词/热榜歌单/**下载到本地库**/本地音乐 Range 206 播放），安卓 `server.py` 改为薄包装复用；移动端网页唯一源迁到 `src/musicplayer/assets/www/`。新增 `run_iphone.py`、`musicplayer-web` 入口、`packaging/MusicPlayer_macos.spec` + `build_macos.sh`（macOS .app 含 pygame/mutagen）。**macOS 应用**右上角 ☎ 按钮弹出「手机访问」窗口：状态/地址/**二维码（segno）**/一键开启停止/复制链接/浏览器打开/「随应用启动自动开启」（写 `settings.json` 的 `mobile_auto`/`mobile_port`），退出应用自动 `webapp.stop()` 释放端口。
- **下载接口修复**：酷我官方封死旧链路后，下载/播放切换至 `mobi.s` 车载签名接口（`convert_url_with_sign`），320k 优先、128k 回落，恢复完整全曲下载（原 antiserver 仅返回 ~11s 试听）。见「接口说明」。
- **清理死代码**：移除了已失效的 `www.kuwo.cn/url` csrf 下载分支。
- **窗口拖拽修复**：背景标签（`_bg_label`）原先盖住面板吃掉鼠标事件导致无法拖动，现已把拖拽绑定同时挂到背景标签上。
- **闪退修复**：工作线程原先直接调用 `root.after(...)` 更新 UI（Tk 非线程安全），现统一改为「线程写入队列 → 主线程 `after` 轮询执行」（`main.py` 的 `_poll_ui`、`dialogs.py` 的 `_drain`），彻底消除跨线程崩溃。
- **界面还原（P1/P2）**：列表/推荐格/表头文字改为直接合成到背景图上，还原 Java `setOpaque(false)` 透明效果；全局字体宋体20、Logo 原尺寸、换肤窗口按原坐标重建、搜索历史保留重复项。
- **皮肤布局重做（方案C，已回退）**：曾改为「等比 cover 背景 + 半透明白卡片」渲染，因观感偏离原版已整体回退，恢复原「背景图拉伸铺满 + 文字直接合成」的 Java 式渲染（`widgets.py` 同步回退，最小化等修复保留）。
- **最小化修复**：无边框窗口原生 `iconify` 报错（TclError）导致最小化无效，现改为：装托盘（pystray）时最小化到托盘，否则临时去掉系统边框→`iconify`→任务栏最小化，点击任务栏图标通过 `<Map>` 事件（已加 `state()=='normal'` 守卫，避免最小化瞬间的 `iconic` 事件把窗口立即唤回）还原为无边框窗口。
- **视觉整改（P0~P2）**：依据 DeepSeek 视觉模型对 6 个界面截图的逐条评审落地整改：
  - P0-1 面板背景改为**等比 cover 居中裁切**铺底（`ImagePanel`/推荐格），消除背景拉伸变形；
  - P0-2 列表改为「连续背景切片 + 接近不透明白底 + 深色文字」，选中行主题蓝底白字，行高 34 加内边距；行右侧空出滚动条位，选中高亮不再钻到滚动条下；
  - P0-3 推荐格 = 连续 cover 背景 + 圆角白卡 + 1:1 裁切封面 + 完整歌名（标题不再贴下沿）；底部 "▼ 滚动查看更多" 提示；
  - P0-4 换肤/存储/本地扫描窗口改卡片式布局，按钮定宽、输入框加内边距与路径缩写，背景加低饱和暗色遮罩；
  - P1-5 统一 ttk 主题（clam：按钮/复选框/下拉框/滚动条/滑杆，新增 `Accent.TButton` 蓝色主按钮）；
  - P1-6 配色收敛为主题蓝 `#3B82F6`；换肤窗口当前皮肤蓝色描边高亮 + 卡片下方「当前」徽标；
  - P2-7 底部播放控制条：上一首/播放/下一首、进度与时间、音量滑杆；引擎为 WinMM 多媒体 API（`winmm.mciSendString`）进程内全曲播放，音量走 `waveOutSetVolume` 系统主音量；右侧「外部」按钮可手动切到系统播放器；
  - P2-8 列表列头（序号/歌名/歌手/时长，黑体19，下划线分隔），搜索列表按数据省略空「时长」列；搜索列表行数据扩展为 `(序号, 歌名, 歌手, 时长)` 四列结构。
  - 附：`widgets.py` 新增 `cover_crop/cover_image/cover_photo/compose_row/header_image/apply_tk_theme`；修复表头 `tk.PhotoImage` 对象被 GC 导致列头消失的问题（必须持有对象引用，仅存字符串会在销毁时 `image delete`）。
- **播放卡顿修复 / 引擎换 MCI**：原播放引擎 `WMPlayer.OCX` 是进程内 ActiveX，节拍依赖宿主线程泵消息；且在本机（含 RDP / 无声卡驱动的会话）该 OCX 永久卡在 `playState=9`「连接中」。现全部替换为 **WinMM 多媒体引擎**（`main.py` 新增 `_MciEngine`：CTypes 调 `winmm.mciSendString`，alias `appplay`），主线程只发"命令队列"、只读"状态 dict"（`ok/state/dur/pos/err`），`_poll_player` 每 400ms 轮询，任何界面阻塞都影响不到播放线程：
  - `_MciEngine` 带独立播放线程，`open/play/pause/resume/seek/stop` 全部走命令队列；进度 `status position` 毫秒级，已在无声卡设备机上实测正常走位；
  - 进度条只在进度变化 ≥0.2s 时 `set()`，减少重绘；
  - 音量经 `waveOutSetVolume(0, vol16|vol16<<16)` 控制系统主音量（MCI 的 `set audio volume` 对多数混音器返回错误，已弃用）；
  - 外部播放器改为**手动「外部」按钮** `_open_external`（`os.startfile`），播放条不再自动跳转外部；
  - 搜索改**异步**：`api.search` 网络调用移到后台线程，结果经 `_ui_queue` 回主线程（`_do_search` 增加序号守卫，旧搜索结果不会覆盖新结果），搜索期间 UI 不再冻结。
- **歌词嵌入**：`lyrics.py` 纯 Python 实现 ID3v2 标签读写，下载歌曲自动获取歌词并以 `USLT` 帧嵌入 MP3（系统播放器如 WMP 可直接显示歌词），同时同目录保存 `<歌名>.lrc`；歌词源按 酷我 → QQ音乐 → 网易云 顺序回落；嵌入帧补齐 `TIT2/TPE1` 标题与歌手。修复要点：ID3v2 头部尺寸字段必须 synchsafe 编码（v2.3 亦如此），帧尺寸 v2.3 用普通 32bit、v2.4 用 synchsafe，否则歌词超过 127 字节即解析错位。
- **歌词显示面板（QQ 音乐风格）**：`widgets.py` 新增 `LyricsPanel`，播放条新增「词」按钮切换歌词全屏；`lyrics.py` 新增 `parse_lrc()` 把 `.lrc` 解析成 `[(ms, text)]`。实现 QQ 音乐式动效：当前行 22px bold 蓝白渐变 + 外发光（字号 24 下层叠底色模拟 glow），上下行按距离渐隐变暗、字号 13→21 线性插值、`_LINE_H` = 38 紧凑行距、活动行锚定于画布 ~46% 高度；滚动用指数缓动（`_tick` 30fps，`_view_pos` 以 `1-exp(-10*dt)` 逼近目标行），播放中每 400ms 由 `_poll_player` 喂给 `set_position(ms)`，拖进度条即实时跳词；上下边缘向背景色混合做渐隐遮罩，消除贴边裁切。歌词加载顺序：同名 `.lrc` 侧车文件 → 嵌入的 USLT（`set_static` 静态列出，无时间轴则不高亮滚动）→ 「暂无歌词」。
- **播放卡顿二次修复**：排查发现 MCI 引擎仍有一处隐藏卡顿源——**`ttk.Scale.set()` 会触发自身的 `command` 回调**（Tk 特性）。原实现 `_poll_player` 每 400ms 调 `_pb_progress.set(pos)` 刷新进度，每次都触发 `_pb_seek`，等于每 0.4 秒把音频 `seek` 重启一次 → 持续卡顿。现改为自绘 `ProgressBar`（`set()` 不触发回调，仅用户拖动才 seek），并保留 `_pb_syncing` 守卫（已用插桩测试验证：4 秒播放中 seek 调用 0 次）。同时：歌词面板改为 `set_active(visible)` 控制动画，隐藏时彻底停掉 30fps 画布重绘（原 `set_lyrics` 无条件启动动画，播放整首歌期间后台空转）；引擎线程空闲时不再轮询 `status`，曲目时长只查询一次缓存。
- **界面重设计（浅色极简 + 音乐绿）**：整体视觉重构。`widgets.py` 新配色令牌 + `set_accent()` 主题色切换 + 微软雅黑 + 扁平 `apply_tk_theme`；`ImagePanel` 改纯色底、列表组件重绘（表头/行 hover/绿色选中）、`RecommendGrid` 圆角卡片、新增自绘 `ProgressBar`；`main.py` 侧栏改文字导航（`_NavItem` 绿色胶囊选中）、顶栏圆角胶囊搜索框、右上 `_CircleBtn` 圆形图标、播放条浅色重排、移除大轮播；`dialogs.py` 换肤改为 `ThemeDialog` 主题色预设 + 存储/扫描窗口浅色卡片。经视觉模型多轮评审迭代（卡片内缩、搜索胶囊、进度条绿色填充、歌词面板全高遮挡）确认达标。
- **逻辑问题修复**：
  - **可拖拽区域扩大**：原仅顶栏/侧栏可拖，现 `_bind_drag_all()` 额外绑定内容区、下载/本地面板、歌词面板、播放条、列表表头，任意空白处按住即可拖动无边框窗口；
  - **最小化可找回**：`_taskbar_minimize` 加回系统边框前 `update_idletasks()` 让任务栏按钮生效，`_on_map` 用 `_minimizing` 标志忽略最小化瞬间的 Map 误触发，恢复后还原无边框 + 原位置 + `focus_force()` 置顶聚焦；
  - **任意页面可搜索**：搜索框在下载/本地页同样可见，`_do_search` 完成后自动切回搜索结果视图（原实现只更新列表但停留在当前页，导致看似"只有首页能搜索"）；
  - **弹窗跟随主窗口**：`dialogs._center_over()` 把主题色/存储/本地扫描窗口居中到主窗口之上（含防跑出屏幕）；设置菜单 `tk_popup` 坐标改为相对主窗口。已用自动化逻辑测试验证：拖拽位移 (+60,+15)、非首页搜索自动回首页、最小化→恢复 normal、弹窗偏移 (±240,±140) 均符合预期。
- **歌词获取按钮**：无歌词（无 `.lrc`、无嵌入 USLT、或获取失败）时，歌词面板显示「获取歌词」按钮（`LyricsPanel` 新增 `set_fetch_callback`/`_on_fetch`/`finish_fetch`，点击后按钮变「获取中...」禁用态）。`main.py` 的 `_fetch_lyrics_for_current` 按文件名解析歌名（支持 `《歌名》.mp3` 与 `歌名.mp3`），后台线程多源抓取（酷我→QQ音乐→网易云），成功后写入歌词面板并落地同名 `.lrc` 侧车文件（下次直接读取），失败则恢复按钮提示重试；切歌后丢弃过期结果（对比 `_pb_path`）。已实测：无歌词→按钮显示→点击→38 行歌词加载、按钮隐藏、`.lrc` 落盘。
- **搜索列表无限滚动**：去掉「上一页/下一页」按钮与 30 首限制。`_BgCanvasList` 新增 `on_scroll_end` 回调（滚轮滚动后检测 `yview()[1] >= 0.95` 触发，`_bottom_fired` 防抖）；`ImageCheckList.append_rows`/`ImageList.append_rows` 追加数据并保留滚动位置（不重置到顶部）。`main.py` 的 `_load_more` 异步加载下一页、追加到列表、编号连续、`_has_more`（满 30 条才继续）与 `_active_search_seq` 守卫（换搜索即丢弃过期分页结果）。工具栏改为提示文字「滚动到底部自动加载更多」。已实测 30→60→90 条连续加载、滚动位置保持。
- **在线播放改为 APP 内直接播放**：搜索结果的「播放」按钮不再 `webbrowser.open` 跳浏览器，改为 `api.download` 下载到系统临时目录 `%TEMP%\musicplayer_online`，下载线程完成回调经 `_ui_queue` 回主线程后走 MCI 引擎进程内播放（`_online_ready`/`_online_ready_ui`）；加载期间播放条显示「正在加载：歌名」。已实测：`webbrowser.open` 调用 0 次、临时文件下载、`state=3` 进程内播放。
- **Windows 无 pygame 播放回退**：`engine.py` 新增 `MciEngine`（winmm.mciSendString / waveOutSetVolume，零依赖），`default_engine()` 自动选择——pygame 可用走跨平台 `CrossPlatformEngine`，Windows 未装 pygame 自动回退 `MciEngine`，解决「缺少 pygame」导致无法播放的问题。实测：未装 pygame 的 Windows 上引擎 `ok=True`、进程内播放 `state=3`、暂停/seek 正常。
- **本地音乐启动自动加载**：`_load_download_dir` 在启动后台读取默认存储目录时，同时把歌曲填充到「本地音乐」列表（`local_paths`/`local_list`，含时长/歌手探读），打开 APP 即自动获取默认存储位置的歌曲；`add_local_song` 增加按路径去重，扫描默认目录不会重复加入。
- **进入本地音乐不再自动弹窗**：移除 `show_local_music` 里自动弹出扫描窗口的逻辑；本地面板右上角新增「扫描文件夹」按钮，需要时手动点开 `LocalScanDialog`。
- **面板顶栏被遮挡修复**：下载管理 / 本地音乐面板原放在 `y=0`，其标题与操作按钮被常驻搜索顶栏（`y=0..64`）盖住导致不可见；现将两个面板下移到 `y=64`（与内容区对齐），标题「下载管理 / 本地音乐」及「扫描文件夹」「加入队列 / 删除 / 本地打开」按钮全部可见，并按文字宽度调整按钮尺寸避免截断。
- **下载/播放音质选择**：搜索控制栏新增「音质」下拉（高品质 320k / 较高 192k / 标准 128k），选择写入 `settings.json` 的 `br` 字段并在启动恢复。`kuwo.download(..., br=)` 与 `_mobi_stream(rid, br)` 支持指定首选码率并沿回落链下降（320k→192k→128k）；下载、失败重试、在线临时播放统一使用所选音质。注：mobi.s 签名接口的 flac/ape 返回与 320k 相同，非真无损，故未提供无损档。实测 128k/320k 均按所选码率返回。
- **交互细节修复**：① 播放条**封面/歌名区域可点击跳转歌词界面**（`_open_lyrics`，已显示时不关闭）；② 搜索控制栏「加入队列」按钮加宽到 96px（原 76px 导致「列」被截断）、音质下拉加宽到 142px，播放条右侧按钮重排留出右边距；③ **音量滑杆/静音按钮上滚轮可调节音量**（`_on_vol_wheel`，每格 ±4，钳制 0..100）。
- **列表元数据与筛选/搜索**：
  - `mutagen` 缺失时新增**纯 Python** 回退（`lyrics.read_id3_tags` 解析 ID3v2 TIT2/TPE1；`lyrics.mp3_duration` 按 MP3 帧头/Xing 估算时长），`_probe_meta` 自动选用；下载管理与本地音乐列表现显示**序号/歌名/歌手/时长/大小/状态**（本地列表改用 6 列 `DownloadList`）。
  - 两个面板新增**搜索框**（按歌名/歌手模糊匹配，250ms 防抖）与**歌手下拉筛选**（自动汇总去重歌手）；`_dl_view`/`_local_view` 维护过滤后视图，双击播放/删除/显示目录等按视图索引正确映射；状态列显示 下载中x.xMB/完成/失败·双击重试/缺失，完成绿色。
  - 修复：歌手下拉筛选原读取 `self._dl_artist` 但选择只改控件值 → 无效果；现 `_dl_apply_filter`/`_local_apply_filter` 开头从下拉框回读当前选择。
  - 修复：下拉框未显示所选歌手/名称被截断——改用 `textvariable` 稳定显示并加宽到 160px；`split_artists` 按多种分隔符（`/`、`、`、`』`、`&` 等，部分酷我标签用 `』` 作分隔）拆分多歌手串，下拉显示单个歌手，筛选改为包含匹配（选「陈奕迅」可匹配「We Talk / 陈奕迅」）。
  - 已用 12 项自动化测试验证（六列内容、歌手/时长/大小/状态非空、歌手筛选、关键词搜索、视图索引映射）。
- **播放器进阶（对照成熟播放器）**：
  - **播放模式**：播放条 🔁 按钮在 顺序/列表循环/单曲循环/随机 间循环（与上一首/下一首/播放三键成组）；`_poll_player` 检测 `state 3→stopped` 触发 `_pb_auto_next`——单曲重播、列表循环回绕、随机随机索引、顺序播完即停；手动上一首/下一首始终 ±1；
  - **会话持久化（记忆上次关闭）**：`settings.json` 存 `{mode,volume,muted,br}` + 会话 `{track,pos,playlist,idx,queue}`，在模式切换/音量/静音/退出时保存。启动时恢复**正在播放的曲目、播放进度、播放队列、播放列表与音量**，曲名/封面/进度条/时间立即就位但处于**暂停态**（显示 ▶，不自动出声），点播放即从记忆进度继续；在线临时文件不持久化，恢复态下拖动进度条只更新记忆位置而不触发播放；
  - **播放条封面（真实优先）**：`lyrics.read_cover()` 解析 ID3v2 **APIC** 帧；`kuwo.py` 搜索返回 4 元组（含 `web_albumpic_short`），`main.py` 建 `歌名→封面URL` 映射（URL 基址 `img1.kuwo.cn/star/albumcover/`）；封面解析顺序 内嵌APIC → 同目录 jpg → 在线封面URL → 主题色音符占位，后台线程异步加载+防切歌竞态；
  - **搜索双击播放 + 播放队列**：搜索结果双击直接在线播放；控制栏「加入队列」勾选歌曲入队，播放条「队列」按钮**悬浮即在按钮上方展开**圆角浮层（`QueuePopup`，鼠标移开自动收起；顶部显示总数 + 「清空」，当前播放行绿色高亮带 ▶，单击行跳播，多项时滚轮/滚动条）；在线项播放时自动下载到临时目录；
  - **快捷键 + 静音**：空格=播放/暂停、←→=±5s、↑↓=音量（搜索框输入时忽略）；播放条喇叭按钮记忆音量一键静音；
  - **下载进度 + 失败重试**：`kuwo.download` 增 `on_progress(bytes)`，下载管理第 4 列实时显示「下载中 x.xMB → ✓ 完成 / 失败·双击重试」，失败行双击自动用记录的信息重下。
- **启动优化**：`to_photo` 改用 `PIL.ImageTk.PhotoImage`（比 base64 PNG 重建更快，缺失时自动回落）；`RecommendGrid` 首屏 20 张卡片改为窗口首帧后延迟绘制（`draw_deferred`），列表填充延后到 `_poll_ui`（250ms）。`MainWindow` 构造 ~1.03s → ~0.75s。
- **项目结构重构为标准 src 布局**：源码移入 `src/musicplayer/`（`main.py`→`app.py`，图像资源移至 `assets/Pictrue/`），新增 `paths.py`（资产/数据目录解析，兼容源码与已安装布局）、`util.py`、`__init__.py`、`__main__.py`；根目录新增 `run.py` 与 `pyproject.toml`（含 `musicplayer` 控制台脚本）、`tests/test_core.py`（pytest 兼容纯逻辑测试，顺带修复 `parse_lrc` 同行多时间戳切片偏移 bug）；模块内导入改为相对导入。支持 `python run.py`、`pip install -e .` 后 `musicplayer` / `python -m musicplayer`。
- **打包为 Windows 10 可安装程序**：新增 `packaging/`（`MusicPlayer.spec` 应用 onedir + `installer.spec` 安装器 onefile + `installer.py` 自研 Tk 安装器 + `build.py` 一键构建）。`build.py` 先用 PIL 由 logo 生成多尺寸 `app.ico`，再依次打包应用与安装程序；安装器内嵌整个应用目录，支持选择安装位置、桌面/开始菜单快捷方式、HKCU 卸载注册表项与 `uninstall.bat`，并支持 `--uninstall` 静默卸载。实测：应用 exe 正常启动、`MusicPlayerSetup.exe` 界面正常（路径框加宽至满行并定位末尾，完整显示默认安装路径）、安装/注册表/卸载项全链路通过；已安装布局下数据统一落到 `~/MusicPlayer/`（`_save_settings` 自动建目录），打包后引擎自动回退 WinMM MCI 无需 pygame。
- **播放按钮文字被裁切修复**：`Ghost.TButton`/`TButton`/`Accent.TButton` 的请求高度（32/36px）大于代码分配的 `place` 高度（28/32px），导致按钮文字底部被裁。收窄样式内边距（`Ghost` `(6,4)`→`(6,2)`、`TButton`/`Accent.TButton` `(14,6)`→`(14,4)`）使请求高度降到 28/32px；播放条「队列/词/外部」改为 `y=18` 高 28（与其它 28px 按钮对齐）。已用像素余量检测（上下各 8px、左右 9–14px，无触边）验证主窗口、下载面板与四个对话框按钮全部完整。
- **音量滑块与喇叭图标对齐**：`_pb_vol` 原 `y=34`（高 16 → 中心 42）比 28px 静音按钮的中心（32）低 10px；改为 `y=24`，实测两者中心均为 568.0、滑块轨道中心 567.5。
- **播放队列改为悬浮浮层**：删除 `QueueDialog` 独立窗口，新增 `QueuePopup`（`dialogs.py`）——鼠标悬浮播放条「队列」按钮即在其上方展开圆角白卡（`overrideredirect` + `transparentcolor` 圆角 + 浅投影），移开 220ms 自动收起（移入浮层或回到按钮可取消隐藏，避免闪烁）。浮层含标题、总数、「清空」、行列表（当前播放行绿色高亮并带 ▶、hover 浅灰、单击跳播、滚轮/滚动条）与底部署名提示；高度按行数封顶（超 8 行滚动），空队列显示引导文案。浮层延后 400ms 创建以免拖慢启动，悬浮时按需创建。
- **自动记忆上次关闭的会话**：`_save_settings()` 新增 `track/pos/playlist/idx/queue` 字段（`_pb_pos` 由 `_poll_player` 每 400ms 刷新，退出时落盘）。`_load_settings()` 调 `_restore_session()` 恢复曲目/进度/队列/播放列表，并以**暂停态**呈现（曲名、封面、`mp3_duration` 探读的时长与进度条位置、时间「m:ss / m:ss」、▶ 图标），不自动播放。新增 `_pb_pending_load`/`_pb_resume_pos`：此时 `_poll_player` 跳过引擎轮询（避免把记忆进度清零），拖动进度条只改记忆位置；点播放才 `_play_path()` 载入并 `engine.seek(记忆进度)` 续播（引擎命令队列有序，play→seek 依次生效）。歌词加载抽成 `_load_lyrics_for()` 供播放与恢复共用；在线临时目录（`%TEMP%/musicplayer_online`）的曲目不持久化。实测：播放 3.5s（pos=3.21）退出 → 重启恢复为暂停态（时间 0:03/3:42、进度条 3.21、音量 73、队列 2 条）→ 点播放从 3.21 续播。
- **进度条按记忆时间渲染修复**：`ProgressBar._draw()` 原用 `winfo_width() or self._w` 兜底，但 `tk.Canvas` 会把 `self._w`/`self._h` 覆盖成控件路径名，且未布局时 `winfo_width()` 返回 **1**（非 0，`or` 不触发）→ 恢复会话时按 1px 宽度绘制，填充几乎为 0。现基准尺寸另存 `_cw`/`_ch`（避开 `_w`/`_h` 冲突），`winfo_width() <= 1` 时用基准值兜底，并绑定 `<Configure>` 在布局完成后重绘。实测恢复 pos=128s/3:42 → 填充 177.9px（310×0.574，与时间一致）；播放中 3.98s → 填充 5.5px，均与进度值吻合。

- **左上角 Logo 换为 Music. 字标 + 应用图标**：移除原「绿圆音符 + 音乐下载器 / Music Player」文字 Logo；`_draw_logo()` 改为渲染 `assets/logo_wordmark.png`（152×35）。该字标由用户提供的 `assets/透明背景logo.jpeg` 提取：原图实为**棋盘格底 + 白色字**（PNG 无 alpha，字形与棋盘格白格同为纯白、无法用亮度阈值区分），故采用「1/4 缩放 + 局部最小值滤波 → 字内保持 255、棋盘格被压暗」再二值化取掩膜，形态学开/闭运算清理噪点，最后用**连通域分析**剔除图像边框/水印残留（只保留 M . u s i c 与 i 的点等 7 个块；先前按「最大块」或用矩形裁切会把右侧 `c` 切掉，已修正）。字标存为**白色 + alpha 掩膜**，运行时由 `_logo_alpha()` / `_logo_photo_for(color)` 按当前主题色着色，因此**换肤时字母颜色随强调色同步变化**（`_apply_accent()` 已调用 `_draw_logo()`；logo 画布只创建一次，避免重复叠加）。新增 `_set_window_icon()`：以 `assets/app_icon.png` 生成 16–256px 多尺寸 `root.iconphoto(True, ...)` 作为任务栏/最小化图标（已截图确认任务栏显示为应用图标），托盘图标同步改用 `app_icon.png`；`build.py` 的 `app.ico` 改由 `app_icon.png` 生成（回落旧 logo）。`MusicPlayer.spec` 打包资源时排除设计稿源文件（`透明背景logo.jpeg`，1.4MB），仅随包运行时资源。实测：绿 `#1DB954` / 蓝 `#3B82F6` / 紫 `#8B5CF6` 切换后字标像素色随主题变化，且 `c` 完整无裁切。

- **歌词高亮色跟随主题色**：`LyricsPanel` 的当前行光晕/文字色原为类常量（写死绿），现改为实例色并在 `_sync_theme()` 中从 `widgets.ACCENT_SOFT_HEX`/`ACCENT_TXT_HEX` 同步；实现 `refresh()` 并 `register(self)` 进换肤列表，`_apply_accent()` 的 `refresh_all_theme()` 会即时重绘。非当前行仍用中性灰渐变（保证可读性）。实测绿/蓝/橙切换后当前行光晕与文字色随之改变。

## 提示

仅供学习交流使用，音乐版权归原版权方所有。

## 安卓版本（WebView + Chaquopy 混合）

`android/` 目录是一个独立的 Android Gradle 工程：**Chaquopy** 把桌面版纯 Python 逻辑（`src/musicplayer` 的 `kuwo.py`/`lyrics.py`/`paths.py`/`util.py`）打进 APK 并运行一个本地 HTTP 服务（`android/app/src/main/python/server.py`，纯标准库 `http.server`），界面是 WebView 里加载的移动端网页（`android/app/src/main/assets/www/`，HTML/CSS/JS，`<audio>` 直接播放在线直链）。第一版覆盖：搜索 / 在线播放 / 歌词同步 / 播放队列 / 主题色 / 音质选择 / 会话记忆（暂停恢复，不自动播放）。

**v2.0 新增**：所有歌曲列表行尾「⬇ 下载 + ▶ MV」；下载完成后自动复制一份进系统媒体库 `Music/音乐下载器/`（文件管理器 / 系统音乐 App 可见，`minSdk` 提升到 **29**）；「观看MV」双源（网易云官方 MV 直链 `<video>` + B站搜索内嵌 `player.bilibili.com`），全屏播放层自适应横竖屏。详见「改动记录」。

界面参照主流音乐 App（QQ 音乐 / 网易云风格）：
- **底部导航**（首页 / 搜索 / 队列）+ 首页推荐 Banner 与 3 列推荐卡；
- **全屏播放器**：模糊封面背景、居中大封面、歌词区 + 进度 + 上/下一首 + 播放模式 + 音量 + 主题色；
- **点击播放条封面 / 歌名区域**即打开全屏播放器（歌词页）；
- **歌词支持上下滑动**：拖动预览歌词行，松手即跳到对应时间播放（单击某行也可跳转）。

### 打包 APK（Windows 本机）

需要 JDK 17 + Android SDK 34 + Gradle 8.7（参考 `AndroidToolchain` 目录），并为本机 Python 版本。首次构建：

```bash
cd android
gradle :app:assembleDebug
# 产物: android/app/build/outputs/apk/debug/app-debug.apk
```

`app/build.gradle.kts` 里 `buildPython()` 指向本机 Python 3.11；ABI 覆盖 `arm64-v8a` + `armeabi-v7a`（Python 3.11 才支持 32 位）。装到手机：`adb install -r app-debug.apk`，或用文件管理器直接安装（需允许“安装未知来源应用”）。

安卓端 `server.py` 已改为复用共享后端 `musicplayer.webapp`（纯标准库 HTTP 服务，接口不变）；
服务器与移动端网页的唯一来源现在是 `src/musicplayer/webapp.py` + `src/musicplayer/assets/www/`，
改动后需同步到 `android/app/src/main/assets/www/`：
`cp src/musicplayer/assets/www/* android/app/src/main/assets/www/`

## iPhone / 局域网访问（Web 版）

桌面版的同时也在手机上用：让 iPhone 与电脑连同一 Wi-Fi，在电脑上启动共享 Web 服务，
iPhone 用 Safari 打开打印出的地址即可 **搜索 / 在线播放 / 歌词 / 下载到电脑本地库 / 管理本地音乐**：

```bash
# 方式 1: 直接跑 (输出地址后手机打开)
python run_iphone.py

# 方式 2: 安装了包后
musicplayer-web

# 方式 3 (推荐): 用打包好的 macOS 应用, 右上角 ☎ 一键开启, 见下节

# 端口可通过环境变量改 (默认 8000)
MUSICPLAYER_PORT=9000 python run_iphone.py
```

- 服务绑定 `0.0.0.0`，启动时打印电脑局域网 IP（`http://192.168.x.x:8000/`）；
- 下载会写入桌面版的**同一下载目录**（源码运行时为项目根 `music/`，打包版为 `~/MusicPlayer/music/`），文件带封面与歌词；
- 本地播放支持 HTTP Range（`206`），iPhone 上可自由拖动进度条；
- 若想把歌曲存到 iPhone 自身：iOS Safari 在网页播放条点 **… → 下载（片）** 存为 mp3。

### macOS 应用内一键开启手机访问

`MusicPlayer.app` 右上角新增 **☎ 手机访问** 按钮，点击弹出窗口：

- 显示手机访问地址与**二维码**（iPhone 直接扫码打开），可一键**复制链接** / **在浏览器打开**；
- **开启 / 停止**开关实时生效；勾选「启动应用时自动开启手机访问」会写进
  `settings.json`，下次打开 Mac 应用即自动起服务；
- 手机下载的歌曲写入与桌面版**同一**下载目录（打包版为 `~/MusicPlayer/music/`），
  含封面与歌词。安装时若勾选自动开启、第一次启动会弹出「允许传入连接」防火墙询问，
  允许即可。

### 打包为 macOS 应用

```bash
bash packaging/build_macos.sh        # 产物: dist/MusicPlayer.app (含 pygame/mutagen)
```

### 本地调试 Web 界面（不开安卓）

```bash
python android/app/src/main/python/server.py
# 浏览器打开 http://127.0.0.1:8760/
```

### 与桌面版的差异

- 界面为移动端网页（无 Tkinter）；下载 / 本地音乐库 / 删除已在「我的」页实现（写桌面同一下载目录）。
- 播放用 `<audio>` 直接拉取酷我签名直链（本地曲目走 `/api/audio` Range 流）；进度/seek/音量/切歌由 JS 处理。
- 会话（主题/音质/音量/模式/队列/进度）存在 WebView `localStorage`，启动恢复为暂停态。

## iOS 应用（Briefcase + WKWebView）

`ios/` 是独立的 **Briefcase** 工程：内嵌 CPython + Rubicon-ObjC，原生壳用 `WKWebView` 打开本机 `http://127.0.0.1:{port}/`，复用与桌面/安卓同一套 `src/musicplayer`（`webapp` 服务）和 `src/musicplayer/assets/www/` 移动端页面。

- **Bundle ID**：`com.ghpcgo.musicplayer.ios`（`bundle=com.ghpcgo.musicplayer` + `app_name=ios`）
- **入口**：`ios/src/ios/__main__.py` 定义 `PythonAppDelegate`（继承 `UIResponder`），启动时把下载目录指到 App 沙盒 `Documents/music`，再起 `webapp.start(8760)` 并加载 WebView
- **权限/后台**（`ios/pyproject.toml` 的 `[tool.briefcase.app.ios.iOS]`）：`UIBackgroundModes=["audio"]`、相册选图 OCR 描述、`UIFileSharingEnabled`（文件 App 可见下载目录）
- **图标**：`ios/icon.png`（1024×1024 占位，可替换为正式图标后重跑构建）

### 云构建（GitHub Actions，推荐）

仓库为私有仓，**macOS runner 按计费分钟计费**；推送改到 `ios/**`、`src/musicplayer/**` 或手动 `workflow_dispatch` 会触发 `.github/workflows/ios.yml`：

1. `pip install briefcase==0.4.5` → `briefcase create iOS` 生成 Xcode 工程并装好 `iphoneos` / `iphonesimulator` 依赖；
2. `xcodebuild -sdk iphoneos` **无签名** Release 构建真机包（CI 无 Apple 证书，故 `CODE_SIGNING_ALLOWED=NO`）；
3. 打成 `Payload/*.app` → `dist/MusicPlayer.ipa`，以 artifact **`musicplayer-ios-ipa`**（保留 30 天）上传。

Actions → 对应 run → Artifacts 下载 `.ipa`。

### 自签安装（免费 Apple ID）

CI 产出的是**未签名** IPA，需在本机用免费开发者账号重签安装：

- **Sideloadly**（Windows/macOS）：USB 连接 iPhone → 选中 `MusicPlayer.ipa` → 登录 Apple ID → Start；或
- **AltStore / SideStore**：把 IPA 导入后由其用你的 Apple ID 签名安装。

免费账号签名 **7 天过期**（AltStore 可在后台自动续签；Sideloadly 需到期重装）。设备需先在「设置 → 通用 → VPN与设备管理」信任对应开发者证书。最多 **3 个 App** 签名名额限制为 Apple 免费账号政策。

### 本地构建（需完整 Xcode）

本机只有 Command Line Tools 时 `briefcase` 会在 `Xcode.verify` 失败；安装完整 Xcode 后：

```bash
cd ios
pip install briefcase==0.4.5
briefcase create iOS          # 首次生成工程
briefcase build iOS           # 模拟器 Debug 构建
briefcase open iOS            # 打开 Xcode，选真机 + 自己的 Team 后 Archive 导出 .ipa
```

真机直接跑也可在 Xcode 里 Run（需 Apple ID 注册设备）。`briefcase package iOS` **不会**产出可分发文件（iOS 需走 Xcode 分发流程），故 CI 自行 `xcodebuild` + 打 Zip。