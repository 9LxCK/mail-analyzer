from app_config.logger_manager import LoggerManager

logger = LoggerManager.get_logger(__name__)

import imaplib
import random
import re
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from email.parser import HeaderParser
from typing import Dict, Iterator, List, Literal, Optional, Tuple

from tqdm import tqdm

lock = threading.Lock()

from app_config.config_loader import ConfigLoader
from app_config.constants import PREVIEW_LENGTH, SearchScope
from core.email_record import EmailRecord
from core.imap import (
    extract_subject_and_body,
    fetch_raw_by_mailbox_and_uid_list,
    iter_mailbox_batches_from_uid_map,
    list_mailboxes,
    select_mailbox,
)
from util import (
    clean_text,
    create_preview,
    decode_from_utf7,
    decode_mime_words,
    format_size,
    measure_time,
    write_lines_to_file,
)

# メールボックス名とUIDをキーにした辞書
EmailRecords = Dict[Tuple[str, int], EmailRecord]


def _iter_mailbox_batches(
    imap: imaplib.IMAP4_SSL, email_records: EmailRecords, fetch_size: int
) -> Iterator[Tuple[str, List[int]]]:
    """
    EmailRecords を使って UIDマップを生成し、バッチイテレーションを行う。

    Args:
        imap: IMAP接続オブジェクト
        email_records: {(mailbox, uid): EmailRecord}
        fetch_size: 1回あたりのUIDフェッチ数

    Yields:
        (mailbox, uid_list) のタプル
    """
    uid_map: Dict[str, List[int]] = defaultdict(list)
    for (mailbox, uid), _ in email_records.items():
        uid_map[mailbox].append(uid)

    return iter_mailbox_batches_from_uid_map(imap, uid_map, fetch_size)


# メールボックス名とUIDをキーにした辞書
@measure_time
def extract_uids(
    imap: imaplib.IMAP4_SSL,
    mailboxes: Optional[List[str]] = None,
    since_days: Optional[int] = None,
    scope: Optional[str] = None,
) -> EmailRecords:
    email_records: EmailRecords = {}
    # IMAP検索条件を取得
    date_criteria = _get_imap_date_criteria_dict(since_days=since_days)
    search_criteria = _build_search_criteria(since=date_criteria.get("SINCE"))
    logger.debug(f"検索条件: {search_criteria}")
    # メールボックスを選択してUIDを取得
    mailboxes = mailboxes or list_mailboxes(imap)
    for mailbox in mailboxes:
        show_name = decode_from_utf7(mailbox)
        if not select_mailbox(imap, mailbox, readonly=True):
            continue
        _, data = imap.uid("search", search_criteria)
        if not data or not data[0]:
            logger.warning(f"メールボックス '{show_name}' にメールが見つかりませんでした。")
            continue
        uid_list = list(map(int, data[0].decode().split()))
        email_records.update(_prepare_email_records(mailbox, uid_list))
        logger.debug(f"メールボックス: {show_name!r}, UID件数: {len(uid_list)}")
    return email_records


# レコードにキー情報を追加
def _prepare_email_records(mailbox: str, uid_int_list: list[int]) -> EmailRecords:
    records: EmailRecords = {}
    for uid in uid_int_list:
        key = (mailbox, uid)
        if key not in records:
            records[key] = EmailRecord(mailbox=mailbox, uid=uid)
    return records


# 検索Criteria文字列を生成する関数
def _build_search_criteria(
    since: Optional[str] = None,
    before: Optional[str] = None,
    subject: Optional[str] = None,
    from_: Optional[str] = None,
    to: Optional[str] = None,
    seen: Optional[bool] = None,
    unseen: Optional[bool] = None,
    custom: Optional[List[str]] = None,
) -> str:
    criteria = []

    if since:
        criteria += ["SINCE", since]
    if before:
        criteria += ["BEFORE", before]
    if subject:
        criteria += ["SUBJECT", f'"{subject}"']
    if from_:
        criteria += ["FROM", f'"{from_}"']
    if to:
        criteria += ["TO", f'"{to}"']
    if seen is True:
        criteria.append(SearchScope.SEEN)
    elif seen is False or unseen is True:
        criteria.append(SearchScope.UNSEEN)

    if custom:
        criteria += custom

    if not criteria:
        return SearchScope.ALL

    return " ".join(criteria)


def _get_imap_date_criteria_dict(since_days: Optional[int] = None, before_days: Optional[int] = None) -> Dict[str, str]:
    """
    SINCE・BEFOREキーを持つ辞書でIMAP検索用の日付条件を返す。
    since_days: N日前（負）またはN日後（正）からのSINCE条件
    before_days: N日前（負）またはN日後（正）からのBEFORE条件

    例:
      get_imap_date_criteria_dict(since_days=-7)
        → {'SINCE': '05-Jun-2024'}
      get_imap_date_criteria_dict(since_days=-7, before_days=0)
        → {'SINCE': '05-Jun-2024', 'BEFORE': '12-Jun-2024'}
      get_imap_date_criteria_dict()
        → {}
    """

    def _format_imap_date(days_offset: int) -> str:
        target_date = datetime.now() + timedelta(days=days_offset)
        return target_date.strftime("%d-%b-%Y")

    result = {}
    if since_days is not None:
        result["SINCE"] = _format_imap_date(since_days)
    if before_days is not None:
        result["BEFORE"] = _format_imap_date(before_days)

    return result


# メール件数制限
def _limit_mail_count(uids, mail_count):
    """
    UIDリストと希望件数から、実際に処理する件数を決定する。

    上限値 (MAILS_MAX_COUNT) を超える場合は制限し、ログを出力する。

    Args:
        uids (list): 処理対象UIDのリスト
        mail_count (int | None): 処理希望件数

    Returns:
        int: 実際に処理する件数
    """
    max_count = ConfigLoader.MAILS_MAX_COUNT

    # mail_count が None または非整数 → max_count 扱い
    if not isinstance(mail_count, int):
        mail_count = max_count

    uids_len = len(uids)

    # 処理件数の決定
    result_count = min(uids_len, mail_count, max_count)

    # 上限制約で切り詰められた場合に警告ログ
    if result_count == max_count and uids_len > max_count:
        logger.warning(
            f"処理対象件数が、システム上限（{max_count}件）に制限されました。"
            f"実UID件数: {uids_len}, 要求件数: {mail_count}"
        )

    return result_count


def _parse_fetch_metadata(mailbox: str, data: tuple[bytes, bytes]) -> Optional[EmailRecord]:
    """
    fetch_data を解析して EmailRecord を返却する
    """
    meta_bytes, body_bytes = data
    meta_str = meta_bytes.decode(errors="ignore")
    body_str = body_bytes.decode(errors="ignore")

    # UID 抽出
    uid_match = re.search(r"UID (\d+)", meta_str)
    if not uid_match:
        return None
    uid = int(uid_match.group(1))

    # INTERNALDATE 抽出
    date_match = re.search(r'INTERNALDATE "([^"]+)"', meta_str)
    internaldate = None
    if date_match:
        try:
            internaldate = datetime.strptime(date_match.group(1), "%d-%b-%Y %H:%M:%S %z")
        except ValueError:
            pass

    # TO 抽出、MIME デコードつき
    parser = HeaderParser()
    headers = parser.parsestr(body_str)
    to_address = decode_mime_words(headers.get("To"))

    return EmailRecord(mailbox=mailbox, uid=uid, to=to_address, internaldate=internaldate)


def filter_and_sort_records(
    records: EmailRecords, order: Literal["asc", "desc", "rand"] = "asc", limit: Optional[int] = None
) -> Dict[Tuple[str, int], EmailRecord]:
    """
    internaldate に従って EmailRecord を並べ替え、dict形式で返却。

    :param records: {(mailbox, uid): EmailRecord} 形式の辞書
    :param order: "asc"（昇順）| "desc"（降順）| "rand"（ランダム）
    :param limit: Optional[int] で None の場合は全件返す
    :return: 条件でフィルタされた {(mailbox, uid): EmailRecord}
    """
    items = list(records.items())

    log_lines = []
    if order == "rand":
        random.shuffle(items)
    else:
        reverse = order == "desc"
        items.sort(key=lambda x: x[1].internaldate or datetime.min, reverse=reverse)
    log_lines.append(f"並び順: {order}")

    limit = _limit_mail_count(records, limit)
    items = items[:limit]
    log_lines.append(f"上限値: {limit}")

    logger.debug(" / ".join(log_lines))

    return dict(items)


@measure_time
def fetch_email_metadata(imap: imaplib.IMAP4_SSL, email_records: EmailRecords) -> EmailRecords:
    # メールボックスごとにUIDバッチを取得
    fetch_data = {}
    for mailbox, batch_uids in _iter_mailbox_batches(imap, email_records, ConfigLoader.FETCH_SIZE):
        fetch_data = fetch_raw_by_mailbox_and_uid_list(
            imap, mailbox, batch_uids, "(BODY.PEEK[HEADER.FIELDS (TO)] INTERNALDATE)"
        )
        # print(f"Mailbox: {mailbox} / UIDs: {batch_uids[:3]}... / Fetch Data: {fetch_data[str(batch_uids[0])]}")
        for uid, data in fetch_data.items():
            email_record = _parse_fetch_metadata(mailbox, data)
            if not email_record:
                logger.warning(f"メール情報が見つかりませんでした: '{mailbox}, {uid}'")
                continue
            email_records[(mailbox, int(uid))] = email_record
    # 最初の項目を確認
    first_key, first_record = next(iter(email_records.items()))
    logger.debug(
        f"(1件目データ) メールボックス: {first_key[0]} / UID: {first_key[1]} / internaldate: {first_record.get_internaldate_text()} / to: {first_record.to}"
    )

    return email_records


@measure_time
def fetch_email_body(imap: imaplib.IMAP4_SSL, email_records: EmailRecords, pbar: Optional[tqdm] = None) -> EmailRecords:
    """
    [メールボックス名, UID]のタプル型リストから、各メールボックスごとにUIDをfetchしてメール内容を取得する。
    """
    total_count = len(email_records)
    if total_count == 0:
        logger.warning("処理対象のメールがありません。")
        return email_records
    
    total_size = 0
    for mailbox, batch_uids in _iter_mailbox_batches(imap, email_records, ConfigLoader.FETCH_SIZE):
        try:
            raw_data = fetch_raw_by_mailbox_and_uid_list(imap, mailbox, batch_uids, "(RFC822)")
            for uid, (_, rfc822_bytes) in raw_data.items():
                total_size += len(rfc822_bytes)
                record = email_records.get((mailbox, int(uid)))
                if not record:
                    logger.warning(f"メール情報が見つかりませんでした: '{mailbox}, {uid}'")
                    if pbar:
                        with lock:
                            pbar.update(1)
                    continue
                record.subject, record.body = extract_subject_and_body(rfc822_bytes)
                email_records[(mailbox, int(uid))] = record
                if pbar:
                    with lock:
                        pbar.update(1)
        except KeyboardInterrupt:
            print("\n途中キャンセルされました。")
            break

    # 最初の項目を出力
    first_key, first_record = next(iter(email_records.items()))
    subject_preview = create_preview(first_record.subject, PREVIEW_LENGTH)
    body_preview = create_preview(first_record.body, PREVIEW_LENGTH)
    logger.debug(
        f"(1件目データ) メールボックス: {first_key[0]} / UID: {first_key[1]} / Subject: {subject_preview!r} / Body: {body_preview!r}"
    )
    logger.debug(
        f"全件数: {total_count} / 全サイズ: {total_size} / 平均サイズ: {format_size(int(total_size / total_count))}"
    )

    return email_records


def write_email_records_to_file(filepath: str, records: EmailRecords) -> bool:
    lines = []

    for (mailbox, uid), record in records.items():
        subject = record.subject or ""
        to = record.to or ""
        date = record.get_internaldate_text()  # internaldate → 文字列（例: "2025-06-18 10:30"）
        body = clean_text(record.body or "")

        lines.append(f"Mailbox: {mailbox}")
        lines.append(f"UID: {uid}")
        lines.append(f"To: {to}")
        lines.append(f"Subject: {subject}")
        lines.append(f"Date: {date}")
        lines.append(f"Body:\n{body}")
        lines.append("-" * 40)

    if not records:
        logger.debug("出力対象のメール情報がないため、ファイル出力をスキップします。")
        return False

    result = write_lines_to_file(filepath, lines)
    if result:
        logger.info(f"{len(records)} 件のメール情報をファイルに出力しました: {filepath}")
    else:
        logger.error(f"ファイル出力に失敗しました: {filepath}")
    return result
