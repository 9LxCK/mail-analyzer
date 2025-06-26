import os

import pytest

from app_config.fernet_cipher import FernetCipher


# テスト前に共通準備したい処理
@pytest.fixture
def cipher(tmp_path):
    # tmp_path は pytest 組み込みの一時フォルダ（ファイルが残らない）
    key_path = tmp_path / "secret.key"
    print(f"using key path: {os.path.abspath(key_path)}")
    return FernetCipher(str(key_path))


def test_encrypt_and_decrypt(cipher):
    original = "supersecret"
    encrypted = cipher.encrypt(original)
    print(f"encrypted: {encrypted}")
    decrypted = cipher.decrypt(encrypted)
    print(f"decrypted: {decrypted}")
    assert decrypted == original
