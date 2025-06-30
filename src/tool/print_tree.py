#!/usr/bin/env python
import os


def print_tree(directory: str, prefix: str = ""):
    entries = sorted(os.listdir(directory))
    # 「_」または「.」で始まるファイル・フォルダを除外
    entries = [e for e in entries if not e.startswith(("_", "."))]

    for index, entry in enumerate(entries):
        path = os.path.join(directory, entry)
        is_last = index == len(entries) - 1
        connector = "└── " if is_last else "├── "
        print(prefix + connector + entry)
        if os.path.isdir(path):
            extension = "    " if is_last else "│   "
            print_tree(path, prefix + extension)


if __name__ == "__main__":
    print_tree(".")
