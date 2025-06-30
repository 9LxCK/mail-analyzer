import logging
from enum import IntEnum


class SearchScope:
    """
    IMAPの検索スコープを定義するクラス
    """

    ALL = "ALL"  # 全てのメール
    UNSEEN = "UNSEEN"  # 未読メール
    SEEN = "SEEN"  # 既読メール
    ANSWERED = "ANSWERED"  # 返信済みメール
    UNANSWERED = "UNANSWERED"  # 未返信メール
    DELETED = "DELETED"  # 削除済みメール
    NOT_DELETED = "NOT DELETED"  # 未削除メール


class EnvKey:
    IMAP_HOST = "IMAP_HOST"
    IMAP_USER = "IMAP_USER"
    IMAP_PASS = "IMAP_PASS"


class MailTupleIndex(IntEnum):
    MAILBOX = 0
    UID = 1


DEFAULT_ENCODING = "utf-8"  # デフォルトのエンコーディング
PREVIEW_LENGTH = 20  # ログ表示などでプレビュー表示する文字数
CONFIG_JSON_PATH = "src/app_config/config.json"

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s.%(funcName)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_LEVEL = logging.INFO
