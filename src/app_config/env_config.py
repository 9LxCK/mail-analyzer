"""
env_config.py

このファイルは `generate_env_config.py` によって自動生成されました。

作成日時: 2025-06-30 15:22:28

注意:
- このファイルは自動生成されたものであり、手動で編集しないでください。
- 設定項目の変更があった場合は、`generate_env_config.py` を再実行してください。
"""

import os


class EnvConfig:
    @classmethod
    def pythonpath(cls) -> str:
        return cls._get_required('PYTHONPATH')

    @classmethod
    def imap_host(cls) -> str:
        return cls._get_required('IMAP_HOST')

    @classmethod
    def imap_user(cls) -> str:
        return cls._get_required('IMAP_USER')

    @classmethod
    def imap_pass(cls) -> str:
        return cls._get_required('IMAP_PASS')

    @classmethod
    def target_mailboxes(cls) -> str:
        return os.environ.get('TARGET_MAILBOXES', '""')

    @classmethod
    def ignored_mailboxes(cls) -> str:
        return os.environ.get('IGNORED_MAILBOXES', '"Drafts,Sent,Spam,Trash"')

    @classmethod
    def since_days_ago(cls) -> int:
        return int(os.environ.get('SINCE_DAYS_AGO', '1'))

    @classmethod
    def to_addresses(cls) -> str:
        return os.environ.get('TO_ADDRESSES', '""')

    @classmethod
    def _get_required(cls, key: str) -> str:
        val = os.environ.get(key)
        if val is None or val.strip() == '':
            raise ValueError(f"必須の環境変数 '{key}' が設定されていません。")
        return val