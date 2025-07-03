import time
import traceback

# システム環境変数読込
from app_config.config_loader import ConfigLoader
from app_config.logger_manager import LoggerManager
from util import load_config

ConfigLoader.initialize()
# ログ設定
LoggerManager.setup(ConfigLoader.LOG_FILE_PATH, ConfigLoader.LOG_LEVEL)
logger = LoggerManager.get_logger(__name__)

# 環境変数読込(TODO: ログ出力するため、ログ設定後に呼び出すこと)
load_config()


# 指定秒数後に自動終了する関数
def _auto_exit_after_delay(seconds: int = 3, message: str = ""):
    if not message:
        message = "自動終了します"
    if seconds > 0:
        print(message, end="", flush=True)
        for _ in range(seconds):
            time.sleep(1)
            print(".", end="", flush=True)
        # ここで改行のみ（終了メッセージや追加のprintはしない）
        print()


def _get_original_func_name(func) -> str:
    """
    ラップされた関数でも、元の関数名を安全に取得する。
    """
    seen = set()
    while hasattr(func, "__wrapped__") and func not in seen:
        seen.add(func)
        func = func.__wrapped__

    if hasattr(func, "__name__"):
        return func.__name__

    if hasattr(func, "__class__"):
        return func.__class__.__name__

    return str(func)


def run(handler, *args, **kwargs):
    handler_name = _get_original_func_name(handler)
    try:
        logger.info(f"処理を開始します: {handler_name}")
        handler(*args, **kwargs)
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        logger.debug(f"エラー詳細: {traceback.format_exc()}")
    finally:
        logger.info(f"処理を終了します: {handler_name}")
        _auto_exit_after_delay(ConfigLoader.EXIT_DELAY_SECONDS)  # N秒後に自動終了
