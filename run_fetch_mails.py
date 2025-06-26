#!/usr/bin/env python
import argparse

from app_config.config_loader import ConfigLoader
from app_config.logger_manager import LoggerManager

logger = LoggerManager.get_logger(__name__)

from bootstrap import run
from core.handler import email_fetch_handler


def main():
    # ツールの引数設定
    parser = argparse.ArgumentParser(description="指定した件数のメールを取得するツール")
    parser.add_argument(
        "count",
        type=int,
        nargs="?",  # 引数がなくてもOK
        help="取得メール件数（省略時は全件取得）",
    )
    args = parser.parse_args()
    mail_count = args.count or None

    # ハンドラの実行
    run(email_fetch_handler, mail_count, ConfigLoader.IS_MULTI_THREADED)


if __name__ == "__main__":
    main()
