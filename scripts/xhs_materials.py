#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from markdown import markdown
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
import glob


DEFAULT_ICLOUD_ROOT = "~/Library/Mobile Documents/com~apple~CloudDocs/Documents"
DEFAULT_CARD_WIDTH = 1080
DEFAULT_CARD_HEIGHT = 1440
DEFAULT_MARGIN = 96
DEFAULT_SCALE = 2
BACKGROUND_RGB = (251, 251, 249)


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root {{
      --bg: #fbfbf9;
      --ink: #1f2220;
      --muted: #5e6460;
      --border: #e2e5df;
      --accent: #445d52;
      --code-bg: #f3f4f1;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Avenir Next", "PingFang SC", "Hiragino Sans GB",
        "Microsoft YaHei", "Noto Sans CJK SC", "Helvetica", Arial, sans-serif;
      line-height: 1.8;
    }}
    .page {{
      width: {width}px;
      padding: {margin}px {margin}px {margin_bottom}px;
      margin: 0 auto;
      background: var(--bg);
    }}
    h1 {{
      font-size: 54px;
      line-height: 1.2;
      margin: 0 0 32px;
      letter-spacing: -0.02em;
    }}
    h2 {{
      font-size: 34px;
      margin: 40px 0 18px;
    }}
    h3 {{
      font-size: 26px;
      margin: 28px 0 14px;
    }}
    p {{
      font-size: 24px;
      margin: 0 0 18px;
      color: var(--muted);
    }}
    hr {{
      border: none;
      border-top: 1px solid var(--border);
      margin: 40px 0;
    }}
    blockquote {{
      margin: 28px 0;
      padding: 18px 22px;
      border-left: 4px solid var(--border);
      background: #f7f8f5;
      color: #4c534d;
    }}
    code, pre {{
      font-family: "SFMono-Regular", "Menlo", "Consolas", monospace;
      font-size: 20px;
      background: var(--code-bg);
    }}
    pre {{
      padding: 16px 18px;
      border-radius: 12px;
      overflow-x: auto;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    ul, ol {{
      margin: 0 0 18px;
      padding-left: 26px;
      color: var(--muted);
      font-size: 24px;
    }}
    .footer {{
      margin-top: 48px;
      padding-top: 20px;
      border-top: 1px solid var(--border);
      font-size: 20px;
      color: #7a807a;
    }}
  </style>
</head>
<body>
  <div class="page">
    {content}
    <div class="footer">
      原文见链接 · AI Capriccio
    </div>
  </div>
</body>
</html>
"""


def slug_from_title(title: str) -> str:
    title = title.strip()
    ascii_words = re.findall(r"[A-Za-z0-9]+", title)
    if ascii_words:
        abbr = "".join(w[0] for w in ascii_words).lower()
        abbr = abbr[:12]
    else:
        compact = "".join(ch for ch in title if not ch.isspace())
        abbr = compact[:8]
    abbr = re.sub(r'[\\/:*?"<>|]+', "_", abbr)
    abbr = abbr.strip("._-")
    if not abbr:
        abbr = dt.datetime.now().strftime("%H%M%S")
    return abbr


def parse_markdown(md_path: Path) -> tuple[str, str]:
    raw = md_path.read_text(encoding="utf-8")
    title = None
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            front = parts[1]
            body = parts[2].lstrip()
            for line in front.splitlines():
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip()
                    break
        else:
            body = raw
    else:
        body = raw

    if not title:
        match = re.search(r"^#\s+(.+)$", body, flags=re.MULTILINE)
        title = match.group(1).strip() if match else md_path.stem

    html = markdown(
        body,
        extensions=["fenced_code", "tables", "sane_lists"],
        output_format="html5",
    )
    return title, html


def render_html_to_image(html: str, output_path: Path, scale: int) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": DEFAULT_CARD_WIDTH, "height": DEFAULT_CARD_HEIGHT},
            device_scale_factor=scale,
        )
        page.set_content(html, wait_until="networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path=str(output_path), full_page=True, type="png")
        browser.close()


def find_safe_cut(image: Image.Image, target_y: int, window: int = 40) -> int:
    width, height = image.size
    start = max(0, target_y - window)
    end = min(height - 1, target_y + window)
    best_y = target_y
    best_score = -1

    for y in range(start, end + 1):
        row = image.crop((0, y, width, y + 1))
        pixels = list(row.getdata())
        match = 0
        for r, g, b in pixels:
            if abs(r - BACKGROUND_RGB[0]) < 6 and abs(g - BACKGROUND_RGB[1]) < 6 and abs(b - BACKGROUND_RGB[2]) < 6:
                match += 1
        score = match / width
        if score > best_score:
            best_score = score
            best_y = y

    return best_y


def slice_image(
    full_image_path: Path,
    output_dir: Path,
    base_name: str,
    card_height: int,
) -> list[Path]:
    image = Image.open(full_image_path)
    width, height = image.size
    pages = (height + card_height - 1) // card_height
    outputs = []

    cursor = 0
    for i in range(pages):
        top = cursor
        tentative_bottom = min(top + card_height, height)
        if tentative_bottom < height:
            bottom = find_safe_cut(image, tentative_bottom)
        else:
            bottom = tentative_bottom
        crop = image.crop((0, top, width, bottom))
        if crop.height < card_height:
            canvas = Image.new("RGB", (width, card_height), "#fbfbf9")
            canvas.paste(crop, (0, 0))
        else:
            canvas = crop

        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 26
            )
        except OSError:
            font = ImageFont.load_default()
        label = f"{i + 1}/{pages}"
        draw.text((width - 90, card_height - 44), label, fill="#9aa09a", font=font)

        out_path = output_dir / f"{base_name}{i + 1:02d}.png"
        canvas.save(out_path, "PNG")
        outputs.append(out_path)
        cursor = bottom

    return outputs


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def import_to_photos(
    image_paths: list[Path],
    folder_name: str,
    album_name: str,
    timeout_seconds: int = 300,
) -> None:
    if not image_paths:
        return
    files_list = ", ".join(f'POSIX file "{p}"' for p in image_paths)
    script = f'''
    with timeout of {timeout_seconds} seconds
    tell application "Photos"
        activate
        set targetFolder to missing value
        repeat with f in folders
            if name of f is "{folder_name}" then
                set targetFolder to f
                exit repeat
            end if
        end repeat
        if targetFolder is missing value then
            set targetFolder to make new folder named "{folder_name}"
        end if

        set targetAlbum to missing value
        repeat with a in albums of targetFolder
            if name of a is "{album_name}" then
                set targetAlbum to a
                exit repeat
            end if
        end repeat
        if targetAlbum is missing value then
            set targetAlbum to make new album named "{album_name}" at targetFolder
        end if

        set importedItems to import {{{files_list}}}
        repeat with anItem in importedItems
            add anItem to targetAlbum
        end repeat
    end tell
    end timeout
    '''
    subprocess.run(["osascript", "-e", script], check=True)


def ensure_photos_album(folder_name: str, album_name: str, timeout_seconds: int = 60) -> None:
    script = f'''
    with timeout of {timeout_seconds} seconds
    tell application "Photos"
        activate
        set targetFolder to missing value
        repeat with f in folders
            if name of f is "{folder_name}" then
                set targetFolder to f
                exit repeat
            end if
        end repeat
        if targetFolder is missing value then
            set targetFolder to make new folder named "{folder_name}"
        end if

        set targetAlbum to missing value
        repeat with a in albums of targetFolder
            if name of a is "{album_name}" then
                set targetAlbum to a
                exit repeat
            end if
        end repeat
        if targetAlbum is missing value then
            set targetAlbum to make new album named "{album_name}" at targetFolder
        end if
    end tell
    end timeout
    '''
    subprocess.run(["osascript", "-e", script], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Xiaohongshu images from a markdown file."
    )
    parser.add_argument("--input", help="Markdown file path")
    parser.add_argument("--title", help="Override title")
    parser.add_argument(
        "--site-url",
        default="https://fanqi1909.github.io/ai-capriccio",
        help="Base site URL for original link",
    )
    parser.add_argument(
        "--output-dir",
        default="out/xhs",
        help="Output directory for generated images (subfolder per article)",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=DEFAULT_SCALE,
        help="Device scale factor for sharper rendering (default 2)",
    )
    parser.add_argument(
        "--icloud-root",
        default=DEFAULT_ICLOUD_ROOT,
        help="iCloud Drive root path",
    )
    parser.add_argument(
        "--photos",
        action="store_true",
        help="Import generated images into Apple Photos",
    )
    parser.add_argument(
        "--import-only",
        nargs="+",
        help="Only import existing image paths into Apple Photos",
    )
    parser.add_argument(
        "--album",
        help="Override Photos album name for import-only mode",
    )
    parser.add_argument(
        "--create-album-only",
        action="store_true",
        help="Only create Photos folder/album without importing images",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of images to import into Photos",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="AppleScript timeout seconds for Photos import",
    )
    parser.add_argument(
        "--photos-folder",
        default="XHS_Materials",
        help="Photos folder name to group albums",
    )
    args = parser.parse_args()

    if args.import_only:
        expanded = []
        for pattern in args.import_only:
            expanded.extend(glob.glob(os.path.expanduser(pattern)))
        image_paths = [Path(p) for p in expanded if Path(p).exists()]
        if args.limit:
            image_paths = image_paths[: args.limit]
        if not image_paths:
            print("No valid images to import.")
            return 1
        if args.album:
            album_name = args.album
        else:
            parent = image_paths[0].parent.name
            album_name = parent or "import"
        if args.create_album_only:
            ensure_photos_album(args.photos_folder, album_name, args.timeout)
            print(f"Created album: {args.photos_folder}/{album_name}")
            return 0
        import_to_photos(image_paths, args.photos_folder, album_name, args.timeout)
        print(f"Imported: {len(image_paths)} images")
        return 0

    if not args.input:
        print("--input is required unless using --import-only")
        return 1

    md_path = Path(args.input).expanduser()
    if not md_path.exists():
        print(f"Markdown file not found: {md_path}")
        return 1

    title, html_body = parse_markdown(md_path)
    if args.title:
        title = args.title

    html = HTML_TEMPLATE.format(
        content=html_body,
        width=DEFAULT_CARD_WIDTH,
        margin=DEFAULT_MARGIN,
        margin_bottom=DEFAULT_MARGIN + 40,
    )

    base_name = slug_from_title(title)
    output_root = Path(args.output_dir)
    output_dir = output_root / base_name
    ensure_dir(output_dir)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_html = Path(tmp_dir) / "xhs.html"
        tmp_png = Path(tmp_dir) / "xhs_full.png"
        tmp_html.write_text(html, encoding="utf-8")
        render_html_to_image(html, tmp_png, args.scale)

        slices = slice_image(
            tmp_png, output_dir, base_name, DEFAULT_CARD_HEIGHT
        )

    icloud_root = Path(os.path.expanduser(args.icloud_root))
    target_dir = icloud_root / "XHS_Materials" / f"{dt.datetime.now():%Y%m%d}_{base_name}"
    ensure_dir(target_dir)

    for img in slices:
        shutil.copy2(img, target_dir / img.name)

    if args.photos:
        album_name = f"{dt.datetime.now():%Y%m%d}_{base_name}"
        slices_to_import = slices
        if args.limit:
            slices_to_import = slices[: args.limit]
        import_to_photos(slices_to_import, args.photos_folder, album_name, args.timeout)

    rel_path = None
    if md_path.parts and md_path.parts[0] == "docs":
        rel_path = f"/docs/{md_path.stem}.html"
    else:
        rel_path = f"/{md_path.stem}.html"
    original_url = args.site_url.rstrip("/") + rel_path
    caption = "\n".join(
        [
            title,
            "",
            f"原文链接：{original_url}",
            "",
            "#AI #Agent #工程实践 #工作流 #小红书笔记",
        ]
    )

    caption_path = output_dir / f"{base_name}_caption.txt"
    caption_path.write_text(caption, encoding="utf-8")
    shutil.copy2(caption_path, target_dir / caption_path.name)

    print(f"Title: {title}")
    print(f"Generated: {len(slices)} images")
    print(f"Output: {output_dir}")
    print(f"iCloud: {target_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
