#!/usr/bin/env python
from bootstrap import run
from core.handler import emailbox_list_handler


def main():
    run(emailbox_list_handler)


# メイン処理
if __name__ == "__main__":
    main()
