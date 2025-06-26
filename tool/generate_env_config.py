#!/usr/bin/env python
from datetime import datetime
import os
import argparse
from dotenv import dotenv_values

from util import to_snake_case

ENV_PATH = ".env"
script_name = os.path.basename(__file__)  # ファイル名のみ取得
OUTPUT_PATH = f"app_config/{script_name.replace('generate_', '')}"
SPLIT_MARK = "# --- 任意キー ---"

# 自動生成コード用のヘッダdocstringを作成
def generate_docstring_header(target_filename: str, generator_script: str) -> str:
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


def parse_env_keys(env_path: str):
    required_keys = []
    optional_keys = []
    is_optional = False
    found_split_mark = False

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                if line == SPLIT_MARK:
                    found_split_mark = True
                    is_optional = True
                continue

            if "=" not in line:
                continue

            key = line.split("=", 1)[0].strip()

            if is_optional:
                optional_keys.append(key)
            else:
                required_keys.append(key)

    if not found_split_mark:
        required_keys.extend(optional_keys)
        optional_keys = []

    return required_keys, optional_keys

def infer_type(value: str):
    if value is None or value == "":
        return "str", '""'

    lower = value.lower()
    if lower in {"true", "false", "yes", "no"}:
        bool_val = "True" if lower in {"true", "yes"} else "False"
        return "bool", bool_val

    try:
        int_val = int(value)
        return "int", str(int_val)
    except ValueError:
        pass

    try:
        float_val = float(value)
        return "float", str(float_val)
    except ValueError:
        pass

    escaped = value.replace('"', '\\"')
    return "str", f'"{escaped}"'

def generate_env_config(output_path: str):
    required_keys, optional_keys = parse_env_keys(ENV_PATH)
    env_vars = dotenv_values(ENV_PATH)

    lines = []
    lines.append(generate_docstring_header(OUTPUT_PATH, script_name))
    lines.append("import os\n\n\nclass EnvConfig:")
    indent = " " * 4

    # 必須項目（型推定＋変換付き）
    for key in required_keys:
        method_name = to_snake_case(key)
        raw_val = env_vars.get(key, "")
        typ, default_val = infer_type(raw_val) # type: ignore supress warning
        lines.append(f"{indent}@classmethod")
        lines.append(f"{indent}def {method_name}(cls) -> {typ}:")
        conv_code = {
            "int": f"int(cls._get_required('{key}'))",
            "float": f"float(cls._get_required('{key}'))",
            "bool": f"cls._get_required('{key}').lower() in ('true', 'yes')",
            "str": f"cls._get_required('{key}')",
        }
        lines.append(f"{indent*2}return {conv_code[typ]}\n")

    # 任意項目（型推定＋デフォルト＋変換付き）
    for key in optional_keys:
        method_name = to_snake_case(key)
        raw_val = env_vars.get(key, "")
        typ, default_val = infer_type(raw_val) # type: ignore supress warning
        lines.append(f"{indent}@classmethod")
        lines.append(f"{indent}def {method_name}(cls) -> {typ}:")
        conv_code = {
            "int": f"int(os.environ.get('{key}', '{default_val}'))",
            "float": f"float(os.environ.get('{key}', '{default_val}'))",
            "bool": f"os.environ.get('{key}', '{default_val}').lower() in ('true', 'yes')",
            "str": f"os.environ.get('{key}', '{default_val}')",
        }
        lines.append(f"{indent*2}return {conv_code[typ]}\n")

    # 共通ユーティリティ
    lines.append(f"{indent}@classmethod")
    lines.append(f"{indent}def _get_required(cls, key: str) -> str:")
    lines.append(f"{indent*2}val = os.environ.get(key)")
    lines.append(f"{indent*2}if val is None or val.strip() == '':")
    lines.append(f"{indent*3}raise ValueError(f\"必須の環境変数 '{{key}}' が設定されていません。\")")
    lines.append(f"{indent*2}return val")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ {script_name} を生成しました: {output_path}")

def main():
    parser = argparse.ArgumentParser(description=".envファイルからEnvConfigクラスを自動生成します。")
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=OUTPUT_PATH,
        help=f"出力先ファイルパス（デフォルト: {OUTPUT_PATH}）"
    )
    args = parser.parse_args()
    generate_env_config(args.output)

if __name__ == "__main__":
    main()
