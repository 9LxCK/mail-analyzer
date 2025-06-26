#!/bin/bash

# 定数定義
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
REQUIREMENTS_TXT="$SCRIPT_DIR/requirements.txt"
VENV_DIR="$PROJECT_ROOT/.venv"
CLEANUP_SH="$SCRIPT_DIR/cleanup.sh"

# プロジェクトルートに移動
cd "$PROJECT_ROOT"

# cleanup.sh を呼び出し
bash "$CLEANUP_SH"

# 仮想環境の作成
echo "仮想環境を作成します..."
rm -rf "$VENV_DIR"
python -m venv "$VENV_DIR"

# 仮想環境の有効化
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source "$VENV_DIR/Scripts/activate"
else
    source "$VENV_DIR/bin/activate"
fi

# 依存パッケージの再インストール
if [ -f "$REQUIREMENTS_TXT" ]; then
    echo "パッケージをインストールします..."
    python -m pip install --upgrade pip
    pip install -r "$REQUIREMENTS_TXT"
else
    echo "requirements.txt が見つかりません。パッケージのインストールをスキップします。"
fi

echo "完了しました。"