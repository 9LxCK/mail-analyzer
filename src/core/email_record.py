from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EmailRecord:
    mailbox: str
    uid: int
    internaldate: Optional[datetime] = None
    to: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None

    # プロパティ設定
    def set_props(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        return self

    def get_internaldate_text(self, fmt: str = "%Y-%m-%d %H:%M") -> str:
        """
        internaldate を指定フォーマットで文字列として返す。
        internaldate が None の場合は空文字列を返す。

        :param fmt: datetime.strftime 形式のフォーマット文字列
        :return: フォーマット済み日付文字列 or 空文字列
        """
        return self.internaldate.strftime(fmt) if self.internaldate else ""
