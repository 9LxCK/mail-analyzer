import logging
import sys
from typing import Optional

from app_config.constants import DEFAULT_DATE_FORMAT, DEFAULT_ENCODING, DEFAULT_LOG_FORMAT, DEFAULT_LOG_LEVEL
from util import add_date_suffix_to_path, ensure_parent_dir


class LoggerManager:
    _initialized = False

    @classmethod
    def setup(cls, filepath: str = "app.log", log_level: Optional[str] = None, log_format: Optional[str] = None):
        """
        ログの初期化（最初の1回のみ実行される）
        """
        if cls._initialized:
            return

        filepath = add_date_suffix_to_path(filepath)
        ensure_parent_dir(filepath)
        logging.basicConfig(
            level=log_level or DEFAULT_LOG_LEVEL,
            format=log_format or DEFAULT_LOG_FORMAT,
            datefmt=DEFAULT_DATE_FORMAT,
            handlers=[
                logging.StreamHandler(sys.stdout),  # 標準出力にログを出力
                logging.FileHandler(filepath, mode="a", encoding=DEFAULT_ENCODING),  # ファイルにもログを出力
            ],
        )

        cls._initialized = True

    @staticmethod
    def get_logger(name: Optional[str] = None) -> logging.Logger:
        """
        logger を取得（必要に応じてモジュール名付き）
        """
        return logging.getLogger(name or "__main__")
