from concurrent.futures import ThreadPoolExecutor
import imaplib

from tqdm import tqdm
from app_config.config_loader import ConfigLoader
from app_config.logger_manager import LoggerManager

logger = LoggerManager.get_logger(__name__)

from typing import Optional

from app_config.env_config import EnvConfig
from app_config.fernet_cipher import FernetCipher
from core.fetch_emails import (
    extract_uids,
    fetch_email_body,
    fetch_email_metadata,
    filter_and_sort_records,
    write_email_records_to_file,
)
from core.imap import collect_target_mailboxes, connect_and_login_imap
from core.make_list import connect_and_login_mailbox, get_mailboxes
from util import (
    add_date_suffix_to_path,
    measure_time,
    split_and_strip,
    split_evenly,
    write_lines_to_file,
)


@measure_time
def emailbox_list_handler():
    # メール接続情報のデコード
    f = FernetCipher.get_instance(logger=logger)
    encrypt_host = f.decrypt(EnvConfig.imap_host())
    encrypt_user = f.decrypt(EnvConfig.imap_user())
    encrypt_pass = f.decrypt(EnvConfig.imap_pass())
    # メールボックス一覧を取得
    with connect_and_login_mailbox(encrypt_host, encrypt_user, encrypt_pass) as mailbox:
        lines = get_mailboxes(mailbox)
    # リスト一覧をファイル出力
    filepath = ConfigLoader.MAILBOX_LIST_PATH
    result = write_lines_to_file(filepath, lines)
    if result:
        logger.info(f"メールボックスの一覧を出力しました: {filepath}")


@measure_time
def email_fetch_handler(mail_count: Optional[int] = None, is_multi_thread: bool = False):
    # ログイン情報を復号
    f = FernetCipher.get_instance(logger=logger)
    encrypt_host = f.decrypt(EnvConfig.imap_host())
    encrypt_user = f.decrypt(EnvConfig.imap_user())
    encrypt_pass = f.decrypt(EnvConfig.imap_pass())

    email_records = {}
    # IMAP接続してUIDを抽出
    with connect_and_login_imap(encrypt_host, encrypt_user, encrypt_pass) as imap:
        email_records = _extract_email_uids(imap, mail_count)

        # シングルスレッド：本文を取得
        if not is_multi_thread:
            with tqdm(total=len(email_records), desc="本文抽出中", unit="件", ncols=80) as progress_bar:
                email_records = fetch_email_body(imap, email_records, progress_bar)
    
    if is_multi_thread:
        def fetch_email_body_handler(email_records: dict):   
            with connect_and_login_imap(encrypt_host, encrypt_user, encrypt_pass) as imap:
                return fetch_email_body(imap, email_records, pbar=progress_bar)
        
        batches = split_evenly(email_records, ConfigLoader.SPLIT_WORKERS)
        with tqdm(total=len(email_records), desc="本文抽出中", unit="件", ncols=80) as progress_bar:
            with ThreadPoolExecutor(max_workers=ConfigLoader.SPLIT_WORKERS) as executor:
                futures = [
                    executor.submit(fetch_email_body_handler, batch if isinstance(batch, dict) else dict(batch))
                    for batch in batches
                ]
                for future in futures:
                    result = future.result()  # 各スレッドの戻り値を取得
                    # print(result)
                    email_records.update(result)
            

    # メールの内容をファイルに出力
    output_filepath = add_date_suffix_to_path(ConfigLoader.OUTPUT_FILE_PATH)
    is_success = write_email_records_to_file(output_filepath, email_records)
    if not is_success:
        raise


def _extract_email_uids(imap: imaplib.IMAP4_SSL, mail_count: Optional[int] = None) -> dict:
    # メールボックスからUIDを抽出
    target_mailboxes = split_and_strip(EnvConfig.target_mailboxes())
    ignored_mailboxes = split_and_strip(EnvConfig.ignored_mailboxes())
    email_records = extract_uids(
        imap,
        mailboxes=collect_target_mailboxes(imap, target_mailboxes, ignored_mailboxes),
        since_days=-EnvConfig.since_days_ago(),  # 環境変数で指定された日数前からのメールを取得（負の値になることに注意）
    )
    logger.debug(f"取得UID件数: {len(email_records)}")
    # メールのメタ情報を取得
    email_records = fetch_email_metadata(imap, email_records)
    # メールの並び替え・件数での抽出
    email_records = filter_and_sort_records(email_records, order="desc", limit=mail_count)
    logger.debug(f"処理対象件数: {len(email_records)}")
        
    return email_records