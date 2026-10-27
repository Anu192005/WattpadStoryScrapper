#!/usr/bin/env python3
"""
download_story.py — Standalone Wattpad Story Downloader
--------------------------------------------------------
Downloads a single Wattpad story and saves it in one or more formats.

Usage:
    python download_story.py <story_url> [options]

Options:
    --format    Output format: epub, pdf, md, txt, html, all  (default: pdf)
    --output    Output directory                               (default: ./downloads)
    --delay-min Minimum delay between chapters in seconds      (default: 1.5)
    --delay-max Maximum delay between chapters in seconds      (default: 2.5)

Examples:
    python download_story.py https://www.wattpad.com/story/299520008
    python download_story.py https://www.wattpad.com/story/299520008 --format pdf
    python download_story.py https://www.wattpad.com/story/299520008 --format all
    python download_story.py https://www.wattpad.com/story/299520008 --format md --output ./my_books
"""

import os
import re
import sys
import time
import random
import zipfile
import argparse

from scraper import WattpadScraper
from epub_builder import EPUBBuilder
from pdf_builder import PDFBuilder


def sanitize_slug(title: str) -> str:
    """Convert a story title into a safe filename slug."""
    return re.sub(r'[\W_]+', '_', title.lower()).strip('_')


def build_markdown(metadata: dict, chapters: list) -> str:
    clean_desc = metadata['description'].replace('\n', '\n>')
    content = f"# {metadata['title']}\n\n**Author:** {metadata['author']}\n\n"
    content += f"**Description:**\n>{clean_desc}\n\n---\n\n"
    for ch in chapters:
        content += f"## {ch['title']}\n\n{ch['markdown']}\n\n"
    return content


def build_plain_text(metadata: dict, chapters: list) -> str:
    content = f"{metadata['title']}\nBy {metadata['author']}\n\nDescription:\n{metadata['description']}\n\n"
    content += "=" * 40 + "\n\n"
    for ch in chapters:
        content += f"--- {ch['title']} ---\n\n{ch['text']}\n\n"
    return content


def build_html(metadata: dict, chapters: list) -> str:
    content = "<!DOCTYPE html>\n<html>\n<head>\n"
    content += f'<meta charset="UTF-8">\n<title>{metadata["title"]}</title>\n'
    content += "<style>body{font-family:sans-serif;max-width:700px;margin:40px auto;padding:0 20px;line-height:1.6;}h1{text-align:center;}h2{margin-top:40px;border-bottom:1px solid #ddd;padding-bottom:10px;}</style>\n"
    content += "</head>\n<body>\n"
    content += f"<h1>{metadata['title']}</h1>\n"
    content += f"<p><strong>Author:</strong> {metadata['author']}</p>\n"
    content += f"<p><strong>Description:</strong> {metadata['description']}</p>\n"
    content += "<hr/>\n"
    for ch in chapters:
        content += f"<h2>{ch['title']}</h2>\n{ch['xhtml']}\n"
    content += "</body>\n</html>"
    return content


def save_epub(metadata: dict, chapters: list, output_path: str):
    builder = EPUBBuilder(metadata, chapters)
    builder.build(output_path)


def save_pdf(metadata: dict, chapters: list, output_path: str):
    builder = PDFBuilder(metadata, chapters)
    builder.build(output_path)


def download_story(story_url: str, fmt: str, output_dir: str, delay_min: float, delay_max: float):
    os.makedirs(output_dir, exist_ok=True)

    scraper = WattpadScraper(delay_min=delay_min, delay_max=delay_max)

    # ── Step 1: Fetch metadata ───────────────────────────────────────────────
    print(f"\n📖  Fetching story metadata...")
    try:
        metadata = scraper.fetch_story_metadata(story_url)
    except Exception as e:
        print(f"❌  Failed to fetch story metadata: {e}")
        sys.exit(1)

    print(f"    Title   : {metadata['title']}")
    print(f"    Author  : {metadata['author']} (@{metadata['author_username']})")
    print(f"    Chapters: {len(metadata['chapters'])}")
    print(f"    Status  : {'Completed' if metadata['completed'] else 'Ongoing'}")
    print()

    story_slug = sanitize_slug(metadata['title'])

    # ── Step 2: Fetch all chapters ───────────────────────────────────────────
    chapters_content = []
    total = len(metadata['chapters'])

    for idx, ch in enumerate(metadata['chapters']):
        pct = int((idx + 1) / total * 100)
        bar_len = 30
        filled = int(bar_len * (idx + 1) / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {pct:3d}%  Chapter {idx+1}/{total}: {ch['title'][:50]}", end="", flush=True)

        try:
            html_content = scraper.fetch_chapter_html(ch['id'])
            cleaned = scraper.clean_chapter_text(html_content)
            chapters_content.append({
                'id': ch['id'],
                'title': ch['title'],
                'url': ch['url'],
                'text': cleaned['text'],
                'markdown': cleaned['markdown'],
                'xhtml': cleaned['xhtml']
            })
        except Exception as e:
            print(f"\n⚠️  Failed to fetch chapter '{ch['title']}': {e}")
            continue

        if idx < total - 1:
            time.sleep(random.uniform(delay_min, delay_max))

    print(f"\n\n✅  Downloaded {len(chapters_content)}/{total} chapters.\n")

    if not chapters_content:
        print("❌  No chapters were downloaded. Exiting.")
        sys.exit(1)

    # ── Step 3: Write output files ───────────────────────────────────────────
    saved_files = []

    def _save_pdf():
        path = os.path.join(output_dir, f"{story_slug}.pdf")
        print(f"  📖  Building PDF (novel style)...")
        save_pdf(metadata, chapters_content, path)
        saved_files.append(path)

    def _save_epub():
        path = os.path.join(output_dir, f"{story_slug}.epub")
        print(f"  📦  Building EPUB...")
        save_epub(metadata, chapters_content, path)
        saved_files.append(path)

    def _save_md():
        path = os.path.join(output_dir, f"{story_slug}.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(build_markdown(metadata, chapters_content))
        saved_files.append(path)

    def _save_txt():
        path = os.path.join(output_dir, f"{story_slug}.txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(build_plain_text(metadata, chapters_content))
        saved_files.append(path)

    def _save_html():
        path = os.path.join(output_dir, f"{story_slug}.html")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(build_html(metadata, chapters_content))
        saved_files.append(path)

    if fmt == "pdf":
        _save_pdf()
    elif fmt == "epub":
        _save_epub()
    elif fmt == "md":
        _save_md()
    elif fmt == "txt":
        _save_txt()
    elif fmt == "html":
        _save_html()
    elif fmt == "all":
        print("  📁  Saving all formats...")
        _save_pdf()
        _save_epub()
        _save_md()
        _save_txt()
        _save_html()

        zip_path = os.path.join(output_dir, f"{story_slug}_all.zip")
        print(f"\n  🗜️   Zipping all formats into archive...")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for fp in saved_files:
                zf.write(fp, os.path.basename(fp))
                os.remove(fp)
        saved_files.clear()
        saved_files.append(zip_path)

    # ── Done ─────────────────────────────────────────────────────────────────
    print("\n🎉  Done! Files saved:")
    for fp in saved_files:
        print(f"    → {os.path.abspath(fp)}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Download a Wattpad story to PDF, EPUB, Markdown, Plain Text, HTML, or all formats.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("story_url", help="Full Wattpad story URL (e.g. https://www.wattpad.com/story/123456)")
    parser.add_argument("--format", dest="fmt", default="pdf",
                        choices=["pdf", "epub", "md", "txt", "html", "all"],
                        help="Output format (default: pdf)")
    parser.add_argument("--output", dest="output_dir", default="./downloads",
                        help="Directory to save the output (default: ./downloads)")
    parser.add_argument("--delay-min", dest="delay_min", type=float, default=1.5,
                        help="Minimum delay (seconds) between chapter fetches (default: 1.5)")
    parser.add_argument("--delay-max", dest="delay_max", type=float, default=2.5,
                        help="Maximum delay (seconds) between chapter fetches (default: 2.5)")

    args = parser.parse_args()

    if args.delay_max < args.delay_min:
        args.delay_max = args.delay_min + 0.5
        print(f"⚠️  delay-max was less than delay-min; adjusted to {args.delay_max}s")

    download_story(
        story_url=args.story_url,
        fmt=args.fmt,
        output_dir=args.output_dir,
        delay_min=args.delay_min,
        delay_max=args.delay_max
    )


if __name__ == "__main__":
    main()
