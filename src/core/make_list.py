from typing import Literal, Optional

from app_config.logger_manager import LoggerManager
from util import encode_to_utf7

logger = LoggerManager.get_logger(__name__)

from contextlib import contextmanager

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


def get_mailboxes(mailbox: MailBox, order: Literal["asc", "desc"] | None = None) -> list[str]:
    # フォルダ一覧の取得
    folders = mailbox.folder.list()
    lines = []
    for folder in folders:
        if '\\Noselect' in folder.flags:
            logger.warning(f"フォルダ '{folder.name}' は select 不可のためスキップ")
            continue
        try:
            status = mailbox.folder.status(folder.name)
            utf7_name = encode_to_utf7(folder.name)
            mail_count = status['MESSAGES']
            # folder.name は自動的に UTF-8 にデコードされている
            lines.append((folder.name, utf7_name, mail_count))
        except Exception as e:
            logger.error(f"MailBox接続中に予期しない例外が発生しました: {e}")
            raise
    
    # メール件数降順にソート
    if order is not None:
        lines = _sort_mailbox_rows(lines, order)

    # 出力文字列の整形
    lines = [f"- {line[0]} ({line[1]}): {line[2]}" for line in lines]
    lines.insert(0, "フォルダ一覧:")

    return lines

def _sort_mailbox_rows(rows: list[tuple[str, str, int]], order: Literal["asc", "desc"] = "desc") -> list[tuple[str, str, int]]:
    """
    rows: (フォルダ名, UTF7フォルダ名, 件数) のリスト
    order: "asc" または "desc"（件数の昇/降順）
    """
    if order == "desc":
        # 件数降順、フォルダ名昇順
        return sorted(rows, key=lambda x: (-x[2], x[0]))
    else:
        # デフォルト: 件数昇順、フォルダ名昇順
        return sorted(rows, key=lambda x: (x[2], x[0]))
