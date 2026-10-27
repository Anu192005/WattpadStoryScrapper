# 📚 WattpadStoryScrapper

A Python tool to **download Wattpad stories** and export them as beautiful, novel-style **PDFs**, EPUBs, Markdown, plain text, or HTML.

---

## ✨ Features

- 📖 **Novel-style PDF** — 12pt serif font, justified text, 1-inch margins, chapter headers, and a full-page cover image from the Wattpad story
- 🗂️ **Table of Contents** with chapter list
- 📚 **EPUB** export for e-readers
- 📝 Markdown, plain text, and HTML export
- 🖼️ **Cover image** automatically fetched from Wattpad and placed on the PDF cover page
- 🚀 Handles multi-chapter stories with polite rate-limiting

---

## 🛠️ Installation

```bash
pip install -r requirements.txt
```

---

## 🚀 Usage

```bash
# Download as PDF (default)
python download_story.py https://www.wattpad.com/story/299520008

# Download as EPUB
python download_story.py https://www.wattpad.com/story/299520008 --format epub

# Download all formats (zipped)
python download_story.py https://www.wattpad.com/story/299520008 --format all

# Custom output directory
python download_story.py https://www.wattpad.com/story/299520008 --output ./my_books
```

### Available Formats

| Flag | Output |
|------|--------|
| `--format pdf` | Novel-style PDF with cover image *(default)* |
| `--format epub` | EPUB for Kindle/Kobo/e-readers |
| `--format md` | Markdown |
| `--format txt` | Plain text |
| `--format html` | HTML |
| `--format all` | All formats bundled in a ZIP |

---

## 📄 PDF Output Details

The PDF is designed to look and feel like a **real printed novel**:

| Property | Value |
|----------|-------|
| Font | Times-Roman (serif) |
| Body size | 12 pt |
| Line spacing | 18 pt (1.5×) |
| Margins | 1.1 inch |
| Text alignment | Justified |
| First-line indent | ~1.5 em |
| Cover page | Full-page Wattpad story cover image |
| Title page | Title, author, description, status |
| TOC | Chapter list |
| Headers | Running title/author header on each page |
| Page numbers | Bottom centre |

---

## 📁 File Structure

```
WattpadStoryScrapper/
├── download_story.py   # Main entry point
├── scraper.py          # Wattpad HTML scraper
├── epub_builder.py     # EPUB assembler
├── pdf_builder.py      # Novel-style PDF builder (ReportLab)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## ⚠️ Disclaimer

This tool is for **personal, non-commercial use only**. Please respect Wattpad's Terms of Service and the intellectual property rights of story authors.
