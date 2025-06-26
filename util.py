import datetime
import inspect
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from collections import defaultdict
from email.header import decode_header
from functools import wraps
from typing import Dict, List, Tuple, TypeVar, Union, cast

import imap_tools.imap_utf7
from dotenv import load_dotenv

from app_config.constants import DEFAULT_ENCODING, DEFAULT_LOG_FORMAT, DEFAULT_LOG_LEVEL


class EnvKeyError(Exception):
    """環境変数が未定義かつデフォルト値も設定されていない場合の例外"""

    pass


# 環境変数から値を取得する汎用関数
def load_env_key(env_key: str, default: Union[str, int, None] = None) -> str:
    value = os.getenv(env_key, default)

    if value is None:
        raise EnvKeyError(f"環境変数 '{env_key}' が設定されていません。")

    if not isinstance(value, str):
        raise EnvKeyError(f"環境変数 '{env_key}' は文字列型ではありません。: {type(value)}")

    return str(value)


# 複数行のテキストをファイルに出力する汎用関数（エラー処理付き）
def write_lines_to_file(
    filepath: str,
    lines: List[str],
    append: bool = False,
    encoding: str = DEFAULT_ENCODING,
) -> bool:
    """
    複数行のテキストをファイルに出力する汎用関数（エラー処理付き）。

    Parameters:
        filepath (str): 出力先のファイルパス。
        lines (List[str]): 出力する文字列のリスト。
        append (bool): Trueなら追記モード（デフォルト: False＝上書き）。
        encoding (str): ファイルのエンコーディング（デフォルト: utf-8）。
        log_errors (bool): エラー時に logging.error を使用するか（デフォルト: True）

    Returns:
        bool: 成功時は True、失敗時は False
    """
    mode = "a" if append else "w"
    try:
        ensure_parent_dir(filepath)
        with open(filepath, mode, encoding=encoding) as f:
            for line in lines:
                f.write(line.rstrip("\n") + "\n")
        return True
    except (OSError, IOError) as e:
        msg = f"ファイル書き込みエラー: {filepath} - {e}"
        logging.error(msg)
        return False


def ensure_parent_dir(filepath):
    """filepathの親ディレクトリがなければ作成する"""
    dirpath = os.path.dirname(filepath)
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath)


# デコレータ: 関数の実行時間を計測する
def measure_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        logging.debug(f"{func.__name__} 実行時間: {end - start:.3f} 秒")
        return result

    return wrapper


# MIMEヘッダーをテキストに変換する
def decode_mime_words(s: str | None) -> str:
    if not s:
        return ""
    decoded_fragments = decode_header(s)
    return "".join(
        [
            part.decode(encoding or "utf-8", errors="replace") if isinstance(part, bytes) else part
            for part, encoding in decoded_fragments
        ]
    )


# テキストの前後の空白を削除し、連続する空白を1つにまとめる
def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


# 基準パスを取得する
def get_base_path():
    if getattr(sys, "frozen", False):
        # PyInstallerでexe化された場合
        return os.path.dirname(sys.executable)
    else:
        # 通常のスクリプト実行
        return os.path.dirname(os.path.abspath(__file__))


# 実行ファイルと同じ場所にある.envを読み込む
def load_config(env_path=""):
    # exeとして実行された場合、exeのあるディレクトリを基準にする
    if not env_path:
        base_path = get_base_path()
        env_path = os.path.join(base_path, ".env")
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"{env_path} が見つかりません。")
    print(f"環境設定ファイルを読み込みます: {env_path}")
    success = load_dotenv(env_path, override=True)
    if not success:
        raise RuntimeError(f"{env_path} の読み込みに失敗しました。")


# ユーザー入力を指定範囲内で取得する関数
def get_input_in_range(prompt: str, min_value: int, max_value: int, cast_func=int) -> int:
    while True:
        try:
            value = cast_func(input(prompt))
            if min_value <= value <= max_value:
                return value
            else:
                print(f"{min_value}～{max_value}の範囲で入力してください。")
        except ValueError:
            print(f"{cast_func.__name__}型で入力してください。")


# ファイルパスまたはファイル名に日付の接尾詞を追加する関数
def add_date_suffix_to_path(path: str) -> str:
    """
    ファイルパスまたはファイル名に "_YYYYMMDD" の接尾詞を追加する。
    拡張子がある場合はその直前に追加される。
    例: "log.txt" → "log_20240612.txt"
         "logs/log" → "logs/log_20240612"
    """
    base, ext = os.path.splitext(path)
    today = datetime.datetime.now().strftime("%Y%m%d")
    return f"{base}_{today}{ext}"


# タプル型リストから階層型のマップ構造を作成する関数
def tuple_list_to_nested_map(tuple_list: list[tuple]) -> dict:
    """
    タプル型リストから、要素数に応じて階層型のマップ構造を作成する。
    タプルの最後の要素はvalue値として格納される。
    例: [('A', 'B', 'C'), ('A', 'B', 'D'), ('X', 'Y', 'Z')]
    → {'A': {'B': ['C', 'D']}, 'X': {'Y': ['Z']}}
    """

    def make_tree():
        return defaultdict(make_tree)

    root = make_tree()
    for tpl in tuple_list:
        d = root
        # 階層をたどる（末尾2つ前まで）
        for key in tpl[:-2]:
            d = d[key]
        if len(tpl) >= 2:
            # 末尾2つ目のキーでリスト化
            if not isinstance(d[tpl[-2]], list):
                d[tpl[-2]] = []
            d[tpl[-2]].append(tpl[-1])
    # defaultdictをdictに変換
    return json.loads(json.dumps(root))


# UTF-7エンコードを行う関数
def encode_to_utf7(text: str) -> str:
    """
    UTF-7エンコードを行う。
    imap_toolsのimap_utf7モジュールを使用。
    """
    if not isinstance(text, str):
        raise TypeError("引数は文字列型である必要があります。")
    return imap_tools.imap_utf7.utf7_encode(text).decode()


# UTF-7デコードを行う関数
def decode_from_utf7(text: str) -> str:
    """
    UTF-7デコードを行う。
    imap_toolsのimap_utf7モジュールを使用。
    """
    if not isinstance(text, str):
        raise TypeError("引数は文字列型である必要があります。")
    return imap_tools.imap_utf7.utf7_decode(text.encode())


def get_since_date_str(days: int, fmt: str = "%d-%b-%Y") -> str:
    """
    daysが正ならN日後、負ならN日前の日付文字列を返す。
    fmtで出力日付の書式を指定可能（デフォルトはIMAP用 "DD-Mon-YYYY"）。
    """
    target_date = datetime.datetime.now() + datetime.timedelta(days=days)
    return target_date.strftime(fmt)


def split_and_strip(s: str, sep: str = ",") -> list[str]:
    """
    文字列sを区切り文字sepで分割し、各要素の両端をトリムしてリストで返す。
    空要素は除外する。
    """
    return [item.strip() for item in s.split(sep) if item.strip()]


def ensure_parentheses(s: str, start_with: str = "(", end_with: str = ")") -> str:
    """
    文字列sの両端に括弧を追加する。
    """
    s = s.strip()
    if s.startswith(start_with) and s.endswith(end_with):
        return s
    return f"({s})"


def create_preview(text: str | None, limit: int) -> str:
    """
    文字列を指定文字数でプレビュー用に切り詰め、必要に応じて「...」を付加して返す。

    :param text: 元の文字列
    :param limit: 表示する最大文字数
    :return: 整形済みプレビュー文字列
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def get_script_name(script_path: str | None = None, include_extension: bool = False) -> str:
    """
    スクリプト名（ファイル名）を取得する関数。

    - 引数 script_path に明示的にスクリプトパスが渡された場合はそれを使用
    - 渡されない場合は、呼び出しスタックを遡って推定
    - PyInstaller などで EXE 化されている場合にも対応
    - 取得したファイル名から拡張子を付けるかどうかを制御可能

    Args:
        script_path (str | None): 対象のスクリプトパス（`__file__` を渡すと確実）。None の場合は自動推定。
        include_extension (bool): 拡張子を含めるかどうか（False の場合、.py や .exe を除去）

    Returns:
        str: スクリプト名（拡張子あり or なし）

    使用例:
        get_script_name(__file__)           # 明示的に現在のファイル名を取得
        get_script_name(include_extension=True)  # 推測して拡張子付きで取得
    """
    if script_path is None:
        # 実行ファイルからの起動（PyInstallerでexe化された場合など）
        if getattr(sys, "frozen", False):
            script_path = sys.executable
        else:
            try:
                # 呼び出し元のスタックからスクリプトパスを推定
                frame = inspect.stack()[-1]
                script_path = os.path.abspath(frame.filename)
            except Exception:
                # 推定に失敗した場合のフォールバック
                script_path = sys.argv[0]

    # ファイル名だけ抽出（パスを除く）
    filename = os.path.basename(script_path)

    # 拡張子の有無に応じて整形
    return filename if include_extension else os.path.splitext(filename)[0]


# ログ出力のデフォルト設定
def get_fallback_logger(name: str = "default") -> logging.Logger:
    logger = logging.getLogger(f"fallback.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(DEFAULT_LOG_LEVEL)
    return logger


# ファイルサイズのフォーマット
def format_size(size_in_bytes: int) -> str:
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 ** 2:
        return f"{size_in_bytes / 1024:.2f} KB"
    else:
        return f"{size_in_bytes / (1024 ** 2):.2f} MB"
    

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")
# なるべく均等にN分割する関数
def split_evenly(
    data: Union[List[T], Dict[K, V]],
    n: int
) -> Union[List[List[T]], List[Dict[K, V]]]:
    if isinstance(data, dict):
        items = list(data.items())
        is_dict = True
    elif isinstance(data, list):
        items = data
        is_dict = False
    else:
        raise TypeError("data must be a list or dict")

    length = len(items)
    base_size = length // n
    remainder = length % n

    result = []
    start = 0
    for i in range(n):
        size = base_size + (1 if i < remainder else 0)
        chunk = cast(List[Tuple[K, V]], items[start:start + size])
        if is_dict:
            result.append(dict(chunk))
        else:
            result.append(chunk)
        start += size

    return result


# スネークケースに変換
def to_snake_case(key: str) -> str:
    return re.sub(r'[^a-z0-9]', '_', key.lower())


def find_project_root(markers: list[str] = ["pyproject.toml", ".git", "requirements.txt"]) -> Path:
    """
    カレントディレクトリまたは上位ディレクトリから、
    指定されたマーカー（例: 'pyproject.toml', '.git'）を探索し、
    最初に見つかったディレクトリを「プロジェクトルート」として返す。
    """
    current = Path.cwd().resolve()

    for parent in [current, *current.parents]:
        for marker in markers:
            if (parent / marker).exists():
                return parent

    raise FileNotFoundError(f"プロジェクトルートを判定できませんでした（マーカー: {markers}）")