from typing import Optional

from app_config.logger_manager import LoggerManager

logger = LoggerManager.get_logger(__name__)

from contextlib import contextmanager

import imap_tools
import imap_tools.imap_utf7
from imap_tools.mailbox import MailBox


@contextmanager
def connect_and_login_mailbox(host: str, user: str, password: str, initial_folder: Optional[str] = None):
    """
    imap_tools.MailBox を安全に接続・ログイン・ログアウトする共通コンテキスト関数。

    Usage:
        with connect_and_login_mailbox(HOST, USER, PASS) as mailbox:
            for msg in mailbox.fetch():
                ...

    Args:
        host (str): IMAPホスト
        user (str): ユーザー名
        password (str): パスワード
        initial_folder (str, optional): 初期フォルダ

    Yields:
        MailBox: 接続済みの MailBox オブジェクト
    """
    mailbox = MailBox(host)
    try:
        mailbox.login(user, password, initial_folder)
        yield mailbox
    except Exception as e:
        logger.exception(f"MailBox接続・ログインエラー: {e}")
        raise
    finally:
        try:
            mailbox.logout()
        except Exception as e:
            logger.warning(f"MailBoxログアウト中にエラーが発生しました: {e}")


def get_mailboxes(mailbox: MailBox) -> list[str]:
    # フォルダ一覧の取得
    folders = mailbox.folder.list()
    lines = []
    lines.append("フォルダ一覧:")
    for folder in folders:
        # folder.name は自動的に UTF-8 にデコードされている
        lines.append(f"- {folder.name}\t({imap_tools.imap_utf7.utf7_encode(folder.name)})")
    return lines
