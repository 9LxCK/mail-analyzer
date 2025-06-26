import email
import imaplib
import itertools
import re
import time
from contextlib import contextmanager
from email import policy
from email.message import EmailMessage, Message
from typing import Dict, Iterator, List, Optional, Tuple

from app_config.constants import DEFAULT_ENCODING
from app_config.logger_manager import LoggerManager

logger = LoggerManager.get_logger(__name__)

from util import decode_mime_words, encode_to_utf7, ensure_parentheses


@contextmanager
def connect_and_login_imap(host: str, user: str, password: str):
    """
    IMAP接続とログイン処理を共通化し、安全に扱えるようにする。

    Usage:
        with connect_and_login_imap(HOST, USER, PASS) as imap:
            imap.select("INBOX")
            ...

    Args:
        host (str): IMAPサーバのホスト名
        user (str): ログインユーザー名
        password (str): ログインパスワード

    Yields:
        imaplib.IMAP4_SSL: 接続済みIMAPオブジェクト
    """
    imap = None
    try:
        imap = imaplib.IMAP4_SSL(host)
        imap.login(user, password)
        logger.debug(f"IMAP_HOST={host}, IMAP_USER={user}")
        yield imap
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAPエラーが発生しました: {e}")
        raise
    except Exception as e:
        logger.exception(f"IMAP接続中に予期しない例外が発生しました: {e}")
        raise
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception as e:
                logger.warning(f"IMAPログアウト時に例外が発生しました: {e}")


def _chunked(iterable, size: int):
    """イテラブルを指定サイズで分割するジェネレータ"""
    it = iter(iterable)
    while chunk := list(itertools.islice(it, size)):
        yield chunk


def iter_mailbox_batches_from_uid_map(
    imap: imaplib.IMAP4_SSL, uid_map: Dict[str, List[int]], fetch_size: int
) -> Iterator[Tuple[str, List[int]]]:
    """
    UIDマップ（mailbox → uidリスト）から mailbox 単位・UIDバッチ単位でイテレート。

    Args:
        imap: IMAP接続オブジェクト
        uid_map: {mailbox: [uid1, uid2, ...]}
        fetch_size: 1回あたりのUIDフェッチ数

    Yields:
        (mailbox, uid_list) のタプル
    """
    for mailbox, uid_list in uid_map.items():
        if not select_mailbox(imap, mailbox, readonly=True):
            continue

        for uid_batch in _chunked(uid_list, fetch_size):
            yield (mailbox, uid_batch)

def extract_subject_and_body(rfc822_bytes: bytes) -> Tuple[str, str]:
    """
    RFC822形式のメールデータから Subject と Body を抽出する。
    :param rfc822_bytes: UID fetchで得たRFC822生データ
    :return: (subject, body)
    """
    msg: EmailMessage = email.message_from_bytes(rfc822_bytes, policy=policy.default)

    subject = decode_mime_words(msg.get("Subject", "")).strip()

    # 本文は text/plain 優先、multipartの処理も考慮
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = part.get_content_disposition()
            if content_type == "text/plain" and content_disposition != "attachment":
                body = _decode_mail_body(part)
                break
    else:
        body = _decode_mail_body(msg)

    return subject, body


# メールパートから本文をデコードする関数
def _decode_mail_body(part: Message) -> str:
    """メールパートから本文を安全にデコードして返す"""
    body = ""
    charset = part.get_content_charset() or DEFAULT_ENCODING
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        try:
            body = payload.decode(charset, errors="ignore")
        except Exception:
            body = payload.decode(DEFAULT_ENCODING, errors="ignore")
    elif isinstance(payload, str):
        body = payload
    return body


def select_mailbox(imap: imaplib.IMAP4, mailbox: str, readonly: bool = True) -> bool:
    """
    指定したメールボックスを選択する。失敗時はエラーログを出力する。

    Parameters:
        imap (imaplib.IMAP4): IMAPセッションオブジェクト
        mailbox (str): 選択するメールボックス名
        readonly (bool): 読み取り専用モードで開くかどうか（デフォルト: True）

    Returns:
        bool: 選択成功ならTrue、失敗ならFalse
    """
    try:
        status, data = imap.select(mailbox, readonly=readonly)
        if status != "OK":
            logger.warning(f"メールボックスの選択に失敗しました: '{mailbox}'（ステータス: {status}）")
            return False
        if not data or data[0] == b"0":
            logger.warning(f"メールボックスが空のためスキップ: '{mailbox}'（ステータス: {status}）")
            return False
        return True
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAPエラーが発生しました（メールボックス: '{mailbox}'）: {e}")
        return False
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました（メールボックス: '{mailbox}'）: {e}")
        return False


# 複数UIDに対してfetchを行い、失敗したUIDのみをリトライ対象として再試行
def fetch_raw_by_mailbox_and_uid_list(
    imap: imaplib.IMAP4_SSL, mailbox: str, uid_list: List[int], fetch_items: str, retry: int = 2, delay: float = 1.0
) -> Dict[str, Tuple[bytes, bytes]]:
    """
    複数UIDに対してfetchを行い、失敗したUIDのみをリトライ対象として再試行。

    :param imap: IMAP4_SSLオブジェクト
    :param mailbox: メールボックス名
    :param uid_list: 取得対象UIDのリスト
    :param fetch_items: fetch対象（例: 'INTERNALDATE BODY[HEADER]')
    :param retry: 最大リトライ回数
    :param delay: リトライ待機時間（秒）
    :return: UIDごとの取得結果 {uid: (meta_bytes, body_bytes)}
    """
    # メールボックス選択
    if not select_mailbox(imap, mailbox, True):
        return {}

    remaining_uids = set(map(str, uid_list))
    results: Dict[str, Tuple[bytes, bytes]] = {}

    for attempt in range(retry + 1):
        if not remaining_uids:
            break  # すべて取得済み

        uid_str = ",".join(remaining_uids)
        status, data = imap.uid("fetch", uid_str, f"{ensure_parentheses(fetch_items)}")

        if status != "OK" or not data:
            if attempt < retry:
                time.sleep(delay)
                continue
            else:
                raise Exception(f"fetch失敗: UID={uid_str}, 最終ステータス={status}")

        fetched_uids: set[str] = set()
        for item in data:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            meta_info = item[0].decode(errors="ignore")
            uid_match = re.search(r"UID (\d+)", meta_info)
            if not uid_match:
                # UIDが meta_info に含まれない場合もあるため fallback
                uid_match = re.search(r"^(\d+)", meta_info)
            if not uid_match:
                continue
            uid = uid_match.group(1)
            fetched_uids.add(uid)
            results[uid] = (item[0], item[1])

        # 残っているUIDから取得済みUIDを除外
        remaining_uids -= fetched_uids

        if remaining_uids and attempt < retry:
            time.sleep(delay)

    if remaining_uids:
        print(f"[警告] 一部のUIDは取得できませんでした: {sorted(remaining_uids)}")

    return results


# メールボックス一覧を取得する関数
def list_mailboxes(imap: imaplib.IMAP4_SSL, ignore_list: Optional[list[str]] = None) -> list[str]:
    """
    IMAPオブジェクト mail から、mail.select() に渡せるメールボックス名のリストを返す。
    日本語名も正しくデコードする。
    """
    status, mailboxes = imap.list()
    mailbox_names = []
    ignore_set = set(ignore_list) if ignore_list else set()
    if status == "OK":
        for mbox in mailboxes:
            try:
                if isinstance(mbox, bytes):
                    decoded = mbox.decode(errors="ignore")
                else:
                    decoded = str(mbox)
                # ダブルクォートで囲まれた部分を抽出
                match = re.search(r'"([^"]+)"\s*$', decoded)
                if match:
                    name = match.group(1)
                else:
                    # クォートがない場合
                    name = decoded.split()[-1]
            except Exception:
                logger.error(f"メールボックス名のデコードに失敗しました: {mbox}")
                pass
            if name not in ignore_set:
                mailbox_names.append(name)
    else:
        logger.error("メールボックス一覧の取得に失敗しました。")
    return mailbox_names


# 検索対象とするメールボックス一覧を取得する関数
def collect_target_mailboxes(
    imap: imaplib.IMAP4_SSL, target_mailboxes: Optional[list[str]] = None, ignored_mailboxes: Optional[list[str]] = None
) -> list[str]:
    """検索対象とするメールボックス一覧を UTF-7 で返却する。"""
    if target_mailboxes:
        # 指定がある場合はそれを使用
        mailbox_list = target_mailboxes
    else:
        # 指定がなければ全件取得
        mailbox_list = list_mailboxes(imap)

    # 除外対象の処理
    if ignored_mailboxes:
        ignored_set = set(ignored_mailboxes)
        mailbox_list = [mb for mb in mailbox_list if mb not in ignored_set]

    # UTF-7 にエンコードして返却
    return [encode_to_utf7(mb) for mb in mailbox_list]
