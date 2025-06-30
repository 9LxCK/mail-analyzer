#!/usr/bin/env python
import argparse
import os
from getpass import getpass
from pathlib import Path

from dotenv import set_key

from app_config.config_loader import ConfigLoader
from app_config.constants import EnvKey
from app_config.env_config import EnvConfig
from app_config.fernet_cipher import FernetCipher
from app_config.logger_manager import LoggerManager
from util import get_script_name, load_config, to_snake_case

ENV_PATH = ".env"
KEY_FILE = "secret.key"
# LOG_FORMAT = "%(asctime)s [%(levelname)s] %(funcName)s - %(message)s"
MASKED_KEYS = {"IMAP_PASS"}  # マスキング対象キーを定義


# システム環境変数読込
ConfigLoader.initialize()
# ログ設定
dir_path = os.path.dirname(ConfigLoader.LOG_FILE_PATH)
LoggerManager.setup(os.path.join(dir_path, f"{get_script_name(__file__, False)}.log"), ConfigLoader.LOG_LEVEL)
logger = LoggerManager.get_logger(__name__)


# 環境変数読込(TODO: ログ出力するため、ログ設定後に呼び出すこと)
# 当該ファイルから2階層上のディレクトリを取得
two_levels_up = Path(__file__).resolve().parents[2]
load_config(str(two_levels_up))


def encrypt_and_store(f: FernetCipher, host: str | None = None, user: str | None = None, password: str | None = None):
    param_map = {
        EnvKey.IMAP_HOST: host,
        EnvKey.IMAP_USER: user,
        EnvKey.IMAP_PASS: password,
    }

    updated = False
    for key_name, plain_value in param_map.items():
        if plain_value is not None:
            encrypted = f.encrypt(plain_value)
            set_key(ENV_PATH, key_name, encrypted)
            logger.info(f"{key_name} を更新しました。")
            updated = True

    if not updated:
        logger.warning("更新対象がありません。--host, --user, --pass のいずれかを指定してください。")


def mask_value(value: str, visible: int = 2) -> str:
    """
    値の一部をマスキングする。
    先頭visible文字だけ表示し、残りを*に置き換える。

    Args:
        value (str): マスキング対象の文字列
        visible (int): 可視部分の文字数（デフォルト2）

    Returns:
        str: マスキング済み文字列（例: ab******）
    """
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)


def show_decrypted_values(f: FernetCipher):
    print("=== 復号結果 ===")
    for key, _ in vars(EnvKey).items():
        if key.startswith("__"):
            continue
        try:
            encrypted = str(_call_env_method_by(key))
            if encrypted:
                decrypted = f.decrypt(encrypted)

                if key in MASKED_KEYS:
                    masked = mask_value(decrypted)
                    print(f"{key} : {masked}")
                else:
                    print(f"{key} : {decrypted}")
            else:
                print(f"{key} : [未設定]")
        except Exception as e:
            logger.error(f"復号に失敗しました ({key}): {e}")
            return


def _call_env_method_by(key: str):
    method_name = to_snake_case(key)
    method = getattr(EnvConfig, method_name, None)

    if callable(method):
        return method()
    else:
        raise AttributeError(f"EnvConfigにメソッド '{method_name}' が定義されていません。")


def main():
    parser = argparse.ArgumentParser(description=".env に暗号化ユーザー情報を追加/表示", allow_abbrev=False)
    parser.add_argument("--host", help="ホスト名（例: smtp.example.com）")
    parser.add_argument("--user", help="ユーザー名")
    parser.add_argument("--pass", dest="password", help="パスワード（未指定で対話入力）")
    parser.add_argument("--show", action="store_true", help=".env に保存された暗号化情報を復号して表示")

    args = parser.parse_args()
    f = FernetCipher.get_instance(logger=logger)

    # パスワードが未指定なら安全な対話入力
    try:
        if args.password is None and args.user:
            args.password = getpass("パスワードを入力してください（非表示）: ")

        if args.show:
            show_decrypted_values(f)
        else:
            encrypt_and_store(f, args.host, args.user, args.password)
    except KeyboardInterrupt:
        print("\n入力をキャンセルしました。")
        return
    except Exception as e:
        logger.error(f"処理中に予期しない例外が発生しました: {e}")
        return


if __name__ == "__main__":
    main()
