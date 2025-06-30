"""
config_loader.py

このファイルは `generate_config_loader.py` によって自動生成されました。

作成日時: 2025-06-27 16:24:01

注意:
- このファイルは自動生成されたものであり、手動で編集しないでください。
- 設定項目の変更があった場合は、`generate_config_loader.py` を再実行してください。
"""

import json
import os
from typing import Any, Dict
from app_config.constants import CONFIG_JSON_PATH, DEFAULT_ENCODING
from util import get_script_name, get_base_path


class ConfigLoader:
    # 型付き静的プロパティ（config.jsonのキーに基づく）
    FETCH_SIZE: int
    MAILS_MAX_COUNT: int
    OUTPUT_FILE_PATH: str
    MAILBOX_LIST_PATH: str
    LOG_FILE_PATH: str
    LOG_LEVEL: str
    USE_USER_INPUT: bool
    IS_MULTI_THREADED: bool
    SPLIT_WORKERS: int
    EXIT_DELAY_SECONDS: int

    _config_data: Dict[str, Any] = {}

    @classmethod
    def initialize(cls) -> None:
        cls._config_data = cls._load_system_config()
        if not cls._config_data:
            raise ValueError("読み込みに失敗しました。")

        for key, value in cls._config_data.items():
            setattr(cls, key.upper(), value)

    @staticmethod
    def _load_system_config() -> dict:
        base_path = get_base_path(__file__)
        json_path = os.path.join(base_path, get_script_name(CONFIG_JSON_PATH, True))
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"{json_path} が見つかりません。")
        with open(json_path, encoding=DEFAULT_ENCODING) as f:
            print(f"システム設定ファイルを読み込みます: {json_path}")
            return json.load(f)

"""
シングルトンでインスタンス化するため、実行スクリプトの最初にinitialize() を呼び出す
使用例：

from config.config_loader import ConfigLoader

ConfigLoader.initialize()
print(ConfigLoader.DB_HOST)
print(ConfigLoader.ALLOWED_IPS)
"""
