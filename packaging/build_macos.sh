#!/bin/bash
# 构建 macOS 应用 MusicPlayer.app
# 产物: dist/MusicPlayer.app   (双击运行桌面版; iPhone 用: python -m musicplayer.webapp)
set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# 1. icns 图标 (不存在则从 assets/app_icon.png 生成)
if [ ! -f packaging/app.icns ]; then
    SRC_PNG=src/musicplayer/assets/app_icon.png
    [ -f "$SRC_PNG" ] || { echo "缺少 $SRC_PNG"; exit 1; }
    ICONSET=build/AppIcon.iconset
    rm -rf "$ICONSET"; mkdir -p "$ICONSET"
    for s in 16 32 64 128 256 512 1024; do
        sips -z "$s" "$s" "$SRC_PNG" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
        if [ "$s" -le 512 ]; then
            sips -z "$((s*2))" "$((s*2))" "$SRC_PNG" \
                --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
        fi
    done
    iconutil -c icns "$ICONSET" -o packaging/app.icns
    echo "生成 packaging/app.icns"
fi

# 2. 依赖 (iOS/打包都需要的: pygame=音频引擎; mutagen=时长; pillow=封面; requests=酷我接口; segno=二维码)
python3 -m pip install --quiet "pyinstaller>=6" "pillow>=9" "requests>=2.28" \
    "pygame>=2.3" "mutagen>=1.46" "segno>=1.6"

# 3. 打包
python3 -m PyInstaller --clean -y packaging/MusicPlayer_macos.spec

echo
echo "完成 → dist/MusicPlayer.app"
echo "iPhone/局域网使用: python -m musicplayer.webapp  (见 README)"