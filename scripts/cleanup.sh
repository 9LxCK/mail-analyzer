#!/bin/bash

# このスクリプトの親ディレクトリ（プロジェクトルート）に移動
cd "$(dirname "$0")/.."

echo "クリーンアップ中..."
rm -rf dist build *.spec

# サブディレクトリの __pycache__ 削除
find . -type d -name "__pycache__" -exec rm -rf {} +
echo "クリーンアップ完了。"