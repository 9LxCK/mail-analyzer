#!/usr/bin/env python
import json
import os

# import sys
from datetime import datetime
from typing import Any

from util import find_project_root


# 自動生成コード用のヘッダdocstringを作成
def generate_docstring_header(target_filename: str, generator_script: str) -> str:
    """
    自動生成コード用のヘッダdocstringを作成する。

    Args:
        target_filename (str): 生成対象ファイル名（例: "config_loader.py"）
        generator_script (str): 生成スクリプト名（例: "generate_config_loader.py"）

    Returns:
        str: 整形済みのヘッダdocstring文字列
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f'''"""
{target_filename}

このファイルは `{generator_script}` によって自動生成されました。

作成日時: {timestamp}

注意:
- このファイルは自動生成されたものであり、手動で編集しないでください。
- 設定項目の変更があった場合は、`{generator_script}` を再実行してください。
"""
'''


from app_config.constants import CONFIG_JSON_PATH

script_name = os.path.basename(__file__)  # ファイル名のみ取得
_OUTPUT_FILE_NAME = script_name.replace("generate_", "")

def infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "str"
    elif isinstance(value, list):
        if not value:
            return "List[Any]"
        inner_type = infer_type(value[0])
        return f"List[{inner_type}]"
    elif isinstance(value, dict):
        return "Dict[str, Any]"
    else:
        return "Any"


with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
    config_data = json.load(f)

property_defs = "\n".join(f"    {key.upper()}: {infer_type(value)}" for key, value in config_data.items())

template = f'''{generate_docstring_header(_OUTPUT_FILE_NAME, script_name)}
import json
import os
from typing import Any, Dict
from app_config.constants import CONFIG_JSON_PATH, DEFAULT_ENCODING
from util import get_script_name, get_base_path


class ConfigLoader:
    # 型付き静的プロパティ（config.jsonのキーに基づく）
{property_defs}

    _config_data: Dict[str, Any] = {{}}

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
            raise FileNotFoundError(f"{{json_path}} が見つかりません。")
        with open(json_path, encoding=DEFAULT_ENCODING) as f:
            print(f"システム設定ファイルを読み込みます: {{json_path}}")
            return json.load(f)

"""
シングルトンでインスタンス化するため、実行スクリプトの最初にinitialize() を呼び出す
使用例：

from config.config_loader import ConfigLoader

ConfigLoader.initialize()
print(ConfigLoader.DB_HOST)
print(ConfigLoader.ALLOWED_IPS)
"""
'''

output_dir = os.path.dirname(CONFIG_JSON_PATH)
output_path = os.path.join(find_project_root(), output_dir, _OUTPUT_FILE_NAME)
with open(output_path, "w", encoding="utf-8") as f:
    f.write(template)

print(f"✅ {_OUTPUT_FILE_NAME} を生成しました: {output_path}")
