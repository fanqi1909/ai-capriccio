#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import re
import shutil
from pathlib import Path


def slug_from_title(title: str) -> str:
    title = title.strip()
    ascii_words = re.findall(r"[A-Za-z0-9]+", title)
    if ascii_words:
        abbr = "".join(w[0] for w in ascii_words).lower()
        abbr = abbr[:12]
    else:
        compact = "".join(ch for ch in title if not ch.isspace())
        abbr = compact[:8]
    abbr = abbr.replace(" ", "_")
    abbr = re.sub(r'[\\/:*?"<>|]+', "_", abbr)
    abbr = abbr.strip("._-")
    if not abbr:
        abbr = dt.datetime.now().strftime("%H%M%S")
    return abbr


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create XHS materials folder in iCloud Drive and copy files."
    )
    parser.add_argument("--title", required=True, help="Article title")
    parser.add_argument(
        "--icloud-root",
        default="~/Library/Mobile Documents/com~apple~CloudDocs",
        help="iCloud Drive root path",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=[],
        help="Files to copy into the materials folder",
    )
    args = parser.parse_args()

    icloud_root = Path(os.path.expanduser(args.icloud_root))
    base_dir = icloud_root / "XHS_Materials"
    ensure_dir(base_dir)

    date_prefix = dt.datetime.now().strftime("%Y%m%d")
    slug = slug_from_title(args.title)
    target_dir = base_dir / f"{date_prefix}_{slug}"
    ensure_dir(target_dir)

    copied = 0
    for file_path in args.files:
        src = Path(file_path).expanduser()
        if not src.exists():
            print(f"Skip missing file: {src}")
            continue
        dst = target_dir / src.name
        shutil.copy2(src, dst)
        copied += 1

    print(f"Materials folder: {target_dir}")
    print(f"Copied files: {copied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
