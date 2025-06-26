# mail-analyzer

> メールの取得・解析バッチ
> ![Python](https://img.shields.io/badge/python-3.11+-green.svg)

---

## 📦 概要

IMAP 経由でメールボックスにアクセスし、指定条件に応じて本文抽出・集計を行うツールです。

- マルチスレッド対応
- `.env` による設定切り分け
- エラーログの自動出力

---

## 🔧 インストール

git からリポジトリのクローン取得し（SSH 推奨）、以下のコマンドを実行する。

```bash
./scripts/rebuild.sh
```

---

## ✅ 使い方

以下のコマンドを実行します。

```bash
# .env にIMAP情報の登録
python -m tool.encrypt_env_key --host (hostname) --user (username) --pass (password)
# .env の登録内容確認
python -m tool.encrypt_env_key --show

# config.json、.env にキーを追加・削除した場合のみ
python -m tool.generate_config_loader
python -m tool.generate_env_config

# メールボックス名一覧の取得（任意）
./run_list_mailboxes.py
# メール情報の取得
./run_fetch_mails.py
# メール情報の取得（取得件数の指定あり）
./run_fetch_mails.py 1000
```
