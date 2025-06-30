#!/bin/bash
# 定数定義
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
CLEANUP_SH="$SCRIPT_DIR/cleanup.sh"

# プロジェクトルートに移動
cd "$PROJECT_ROOT"

# cleanup.sh を呼び出し
bash "$CLEANUP_SH"

# 実行ファイルの作成
# ※現在のプロジェクトルートやパッケージを import 可能にするため、paths を指定
for target in run_*.py src/tool/encrypt_*.py; do
  if [ -f "$target" ]; then
    echo "🚀 Building $target..."
    pyinstaller --onefile --noconfirm --clean --paths "$(pwd)" "$target"
  fi
done

echo "✅ Build complete. Executables are in ./dist/"