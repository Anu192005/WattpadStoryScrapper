#!/usr/bin/env python3
"""
pdf_builder.py — Wattpad Story PDF Builder
-------------------------------------------
Generates a beautiful, novel-style PDF from scraped Wattpad story data.

Features:
  - Full-page cover image (fetched from Wattpad)
  - Styled title page (title + author)
  - Table of Contents with page numbers
  - 12pt Times-Roman body text, justified, with first-line indent
  - Chapter title headers on new pages
  - 1-inch margins — standard novel layout
"""

import io
import requests

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    Paragraph, Spacer, PageBreak, Image,
    SimpleDocTemplate, KeepTogether
)
from reportlab.platypus.flowables import Flowable


# ── Constants ────────────────────────────────────────────────────────────────

PAGE_WIDTH, PAGE_HEIGHT = A4   # 595 x 842 pts
MARGIN = 1.1 * inch            # Standard novel margin
GUTTER = 0.9 * inch           # Slightly smaller inner margin

BODY_FONT       = "Times-Roman"
BODY_FONT_BOLD  = "Times-Bold"
BODY_FONT_ITALIC= "Times-Italic"
BODY_SIZE       = 12           # pt  — comfortable reading size
LINE_LEADING    = 18           # pt  — 1.5× leading for easy reading
INDENT          = 22           # pt  — first-line indent (~1.5em)

ACCENT = HexColor("#FF6B35")   # Wattpad-inspired warm orange


# ── Custom Flowables ──────────────────────────────────────────────────────────

class HorizontalRule(Flowable):
    """A thin decorative rule."""
    def __init__(self, width, thickness=0.5, color=colors.lightgrey):
        Flowable.__init__(self)
        self.width = width
        self.thickness = thickness
        self.color = color
        self.height = thickness + 4

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.thickness / 2, self.width, self.thickness / 2)


def _draw_cover_on_canvas(canvas, cover_bytes):
    """Draw the cover image directly onto the canvas page (absolute A4 coords)."""
    pw, ph = A4
    canvas.saveState()
    # Black bleed background
    canvas.setFillColor(black)
    canvas.rect(0, 0, pw, ph, fill=1, stroke=0)
    if cover_bytes:
        from reportlab.lib.utils import ImageReader
        reader = ImageReader(io.BytesIO(cover_bytes))
        img_w, img_h = reader.getSize()
        scale = max(pw / img_w, ph / img_h)
        drawn_w = img_w * scale
        drawn_h = img_h * scale
        x = (pw - drawn_w) / 2
        y = (ph - drawn_h) / 2
        canvas.drawImage(reader, x, y, drawn_w, drawn_h, preserveAspectRatio=True)
    else:
        # Text fallback on dark background
        canvas.setFillColor(white)
        canvas.setFont(BODY_FONT_BOLD, 28)
        canvas.drawCentredString(pw / 2, ph / 2 + 20, "Wattpad Story")
    canvas.restoreState()


# ── Style Sheet ───────────────────────────────────────────────────────────────

def _make_styles():
    styles = {}

    styles['cover_title'] = ParagraphStyle(
        'cover_title',
        fontName=BODY_FONT_BOLD,
        fontSize=28,
        leading=34,
        textColor=white,
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    styles['cover_author'] = ParagraphStyle(
        'cover_author',
        fontName=BODY_FONT_ITALIC,
        fontSize=16,
        leading=20,
        textColor=HexColor("#DDDDDD"),
        alignment=TA_CENTER,
    )

    styles['title_page_title'] = ParagraphStyle(
        'title_page_title',
        fontName=BODY_FONT_BOLD,
        fontSize=26,
        leading=32,
        textColor=black,
        alignment=TA_CENTER,
        spaceBefore=80,
        spaceAfter=20,
    )

    styles['title_page_author'] = ParagraphStyle(
        'title_page_author',
        fontName=BODY_FONT_ITALIC,
        fontSize=14,
        leading=18,
        textColor=HexColor("#444444"),
        alignment=TA_CENTER,
        spaceAfter=30,
    )

    styles['title_page_label'] = ParagraphStyle(
        'title_page_label',
        fontName=BODY_FONT,
        fontSize=10,
        leading=14,
        textColor=HexColor("#888888"),
        alignment=TA_CENTER,
    )

    styles['description_heading'] = ParagraphStyle(
        'description_heading',
        fontName=BODY_FONT_BOLD,
        fontSize=11,
        leading=15,
        textColor=HexColor("#444444"),
        alignment=TA_LEFT,
        spaceBefore=20,
        spaceAfter=6,
    )

    styles['description_body'] = ParagraphStyle(
        'description_body',
        fontName=BODY_FONT_ITALIC,
        fontSize=10,
        leading=15,
        textColor=HexColor("#555555"),
        alignment=TA_JUSTIFY,
        spaceAfter=4,
    )

    styles['toc_heading'] = ParagraphStyle(
        'toc_heading',
        fontName=BODY_FONT_BOLD,
        fontSize=18,
        leading=24,
        textColor=black,
        alignment=TA_CENTER,
        spaceBefore=40,
        spaceAfter=24,
    )

    styles['toc_entry'] = ParagraphStyle(
        'toc_entry',
        fontName=BODY_FONT,
        fontSize=11,
        leading=20,
        textColor=HexColor("#222222"),
        alignment=TA_LEFT,
    )

    styles['chapter_heading'] = ParagraphStyle(
        'chapter_heading',
        fontName=BODY_FONT_BOLD,
        fontSize=18,
        leading=26,
        textColor=black,
        alignment=TA_CENTER,
        spaceBefore=60,
        spaceAfter=6,
    )

    styles['chapter_number'] = ParagraphStyle(
        'chapter_number',
        fontName=BODY_FONT,
        fontSize=10,
        leading=14,
        textColor=ACCENT,
        alignment=TA_CENTER,
        spaceAfter=30,
    )

    styles['body'] = ParagraphStyle(
        'body',
        fontName=BODY_FONT,
        fontSize=BODY_SIZE,
        leading=LINE_LEADING,
        textColor=HexColor("#1A1A1A"),
        alignment=TA_JUSTIFY,
        firstLineIndent=INDENT,
        spaceAfter=0,
        spaceBefore=0,
    )

    styles['body_no_indent'] = ParagraphStyle(
        'body_no_indent',
        fontName=BODY_FONT,
        fontSize=BODY_SIZE,
        leading=LINE_LEADING,
        textColor=HexColor("#1A1A1A"),
        alignment=TA_JUSTIFY,
        firstLineIndent=0,
        spaceAfter=0,
        spaceBefore=0,
    )

    return styles


# ── Page Number Canvas ────────────────────────────────────────────────────────

class NumberedCanvas:
    """Mixin-style helper — we use onPage callbacks instead."""
    pass


def _header_footer(canvas, doc):
    """Draw running header and page number on content pages."""
    canvas.saveState()
    title = getattr(doc, '_story_title', '')
    author = getattr(doc, '_story_author', '')

    page_num = canvas.getPageNumber()

    # Skip cover page (page 1)
    if page_num <= 1:
        canvas.restoreState()
        return

    # Light grey thin rule at top
    canvas.setStrokeColor(HexColor("#CCCCCC"))
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN, PAGE_HEIGHT - MARGIN * 0.65,
                PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN * 0.65)

    # Running header: title on even pages, author on odd pages
    canvas.setFont(BODY_FONT_ITALIC, 8)
    canvas.setFillColor(HexColor("#888888"))
    if page_num % 2 == 0:
        canvas.drawString(MARGIN, PAGE_HEIGHT - MARGIN * 0.55, title)
    else:
        canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN * 0.55, author)

    # Page number at bottom centre
    canvas.setFont(BODY_FONT, 9)
    canvas.setFillColor(HexColor("#888888"))
    canvas.drawCentredString(PAGE_WIDTH / 2, MARGIN * 0.4, str(page_num - 1))  # -1 to hide cover page from count

    canvas.restoreState()


# ── Main Builder Class ────────────────────────────────────────────────────────

class PDFBuilder:
    """
    Builds a beautiful novel-style PDF for a Wattpad story.

    Parameters
    ----------
    metadata : dict
        Keys: title, author, description, cover_url, completed, chapters
    chapters : list
        Each item: dict with keys title, text (plain text paragraphs)
    """

    def __init__(self, metadata: dict, chapters: list):
        self.metadata = metadata
        self.chapters = chapters
        self.styles = _make_styles()

    # ── Cover Image ───────────────────────────────────────────────────────────

    def _fetch_cover(self):
        """Download and return raw bytes of the cover image, or None."""
        cover_url = self.metadata.get('cover_url', '')
        if not cover_url:
            return None
        try:
            print(f"  🖼️   Fetching cover image...")
            r = requests.get(cover_url, timeout=15)
            if r.status_code == 200:
                return r.content
        except Exception as e:
            print(f"  ⚠️   Could not fetch cover image: {e}")
        return None

    # ── Text Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _escape(text: str) -> str:
        """Escape XML special chars for ReportLab Paragraph."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))

    def _paragraphs_from_text(self, text: str):
        """Split plain text into Paragraph flowables with novel-style indent."""
        paras = []
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            safe = self._escape(line)
            style = self.styles['body_no_indent'] if i == 0 else self.styles['body']
            paras.append(Paragraph(safe, style))
        return paras

    # ── Story Sections ────────────────────────────────────────────────────────

    def _build_cover_section(self):
        """Return flowables for the cover page (just a PageBreak — cover drawn via canvas callback)."""
        # The cover image is drawn directly in the onFirstPage canvas callback,
        # so all we need here is a PageBreak to advance past page 1.
        return [PageBreak()]

    def _build_title_page(self):
        """Return flowables for the title/info page."""
        story = []
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph(self._escape(self.metadata['title']),
                                self.styles['title_page_title']))
        story.append(Paragraph(f"by {self._escape(self.metadata['author'])}",
                                self.styles['title_page_author']))
        story.append(HorizontalRule(PAGE_WIDTH - 2 * MARGIN, thickness=0.7,
                                     color=HexColor("#CCCCCC")))

        # Description
        desc = self.metadata.get('description', '').strip()
        if desc:
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph("Description", self.styles['description_heading']))
            for line in desc.split('\n'):
                if line.strip():
                    story.append(Paragraph(self._escape(line.strip()),
                                            self.styles['description_body']))

        # Status
        story.append(Spacer(1, 0.3 * inch))
        status = "Completed" if self.metadata.get('completed') else "Ongoing"
        story.append(Paragraph(f"Status: {status}  •  Chapters: {len(self.chapters)}",
                                self.styles['title_page_label']))
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("Downloaded via WattpadStoryScrapper",
                                self.styles['title_page_label']))
        story.append(PageBreak())
        return story

    def _build_toc(self):
        """Return a simple, manually-built Table of Contents page."""
        story = []
        story.append(Paragraph("Contents", self.styles['toc_heading']))
        story.append(HorizontalRule(PAGE_WIDTH - 2 * MARGIN, thickness=0.5,
                                     color=HexColor("#DDDDDD")))
        story.append(Spacer(1, 0.2 * inch))

        for i, ch in enumerate(self.chapters, 1):
            entry_text = f"{i}.&nbsp;&nbsp;{self._escape(ch['title'])}"
            story.append(Paragraph(entry_text, self.styles['toc_entry']))

        story.append(PageBreak())
        return story

    def _build_chapters(self):
        """Return flowables for all chapters."""
        story = []
        for i, ch in enumerate(self.chapters, 1):
            # Chapter number label
            story.append(Paragraph(f"Chapter {i}", self.styles['chapter_number']))
            # Chapter title
            story.append(Paragraph(self._escape(ch['title']),
                                    self.styles['chapter_heading']))
            story.append(Spacer(1, 0.12 * inch))
            story.append(HorizontalRule(2 * inch, thickness=1.0, color=ACCENT))
            story.append(Spacer(1, 0.3 * inch))

            # Chapter body
            body_paras = self._paragraphs_from_text(ch.get('text', ''))
            if not body_paras:
                body_paras = [Paragraph("[No content]", self.styles['body'])]
            story.extend(body_paras)

            story.append(PageBreak())

        return story

    # ── Build PDF ─────────────────────────────────────────────────────────────

    def build(self, output_path: str):
        """Build and save the PDF to output_path."""
        print(f"  📄  Building novel-style PDF...")

        cover_bytes = self._fetch_cover()

        # Document setup
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
            title=self.metadata.get('title', 'Story'),
            author=self.metadata.get('author', ''),
            subject="Downloaded from Wattpad via WattpadStoryScrapper",
        )

        # Attach metadata for running headers
        doc._story_title = self.metadata.get('title', '')
        doc._story_author = self.metadata.get('author', '')

        # Build onFirstPage callback: draws cover image directly on canvas then runs header/footer
        def _first_page(canvas, doc):
            _draw_cover_on_canvas(canvas, cover_bytes)
            _header_footer(canvas, doc)

        # Assemble all flowables
        flowables = []
        flowables += self._build_cover_section()   # just a PageBreak
        flowables += self._build_title_page()
        flowables += self._build_toc()
        flowables += self._build_chapters()

        doc.build(flowables, onFirstPage=_first_page, onLaterPages=_header_footer)
        print(f"  ✅  PDF saved to: {output_path}")
