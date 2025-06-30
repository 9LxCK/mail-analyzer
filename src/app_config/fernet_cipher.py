import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from util import get_fallback_logger

_DEFAULT_KEY_PATH = "secret.key"


class FernetCipher:
    _instances: dict[str, "FernetCipher"] = {}

    def __init__(self, key_path: str, logger: logging.Logger | None = None):
        self.key_path = key_path
        self.logger = logger or get_fallback_logger(__name__)
        self.fernet = self._load_or_create_key()

    @classmethod
    def get_instance(cls, key_path: str | None = None, logger: logging.Logger | None = None):
        resolved_path = key_path or _DEFAULT_KEY_PATH
        if resolved_path not in cls._instances:
            cls._instances[resolved_path] = cls(resolved_path, logger)
        return cls._instances[resolved_path]

    def _load_or_create_key(self) -> Fernet:
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                key = f.read()
            self.logger.info(f"鍵ファイルを読み込みました: {os.path.abspath(self.key_path)}")
        else:
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as f:
                f.write(key)
            self.logger.info(f"鍵ファイルを新規作成しました: {os.path.abspath(self.key_path)}")
        return Fernet(key)

    def encrypt(self, plain_text: str) -> str:
        try:
            return self.fernet.encrypt(plain_text.encode()).decode()
        except Exception as e:
            self.logger.error(f"暗号化に失敗しました: {e}")
            raise

    def decrypt(self, encrypted_text: str) -> str:
        try:
            return self.fernet.decrypt(encrypted_text.encode()).decode()
        except InvalidToken:
            self.logger.error("復号に失敗しました。キーが異なるか、トークンが破損している可能性があります。")
            raise
        except Exception as e:
            self.logger.error(f"復号処理で予期しないエラーが発生しました: {e}")
            raise
