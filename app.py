import os
import io
import sys
import time
import random
import threading
import streamlit as st

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WattpadStoryScrapper",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ── Premium CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif !important;
    background-color: #0e0e0f;
    color: #f0f0f0;
}

#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}

/* ── Page background ── */
.stApp {
    background: radial-gradient(ellipse at 20% 10%, rgba(255,75,31,0.12) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 90%, rgba(255,144,104,0.08) 0%, transparent 60%),
                #0e0e0f;
    min-height: 100vh;
}

/* ── Hero Header ── */
.hero {
    text-align: center;
    padding: 50px 20px 30px;
}
.hero-badge {
    display: inline-block;
    background: rgba(255,75,31,0.15);
    border: 1px solid rgba(255,75,31,0.4);
    color: #ff7a52;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 5px 14px;
    border-radius: 20px;
    margin-bottom: 18px;
}
.hero-title {
    font-size: 3.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #ff4b1f 0%, #ff9068 50%, #ffb347 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 12px;
    line-height: 1.1;
}
.hero-sub {
    font-size: 1.05rem;
    color: #888;
    font-weight: 300;
    max-width: 500px;
    margin: 0 auto;
    line-height: 1.6;
}

/* ── Card ── */
.card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 28px 32px;
    margin: 20px 0;
    backdrop-filter: blur(10px);
}

/* ── Input label override ── */
.stTextInput label, .stSelectbox label, .stSlider label {
    color: #bbb !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.5px !important;
}

/* ── Text input ── */
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 12px !important;
    color: #f0f0f0 !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 1rem !important;
    padding: 14px 16px !important;
    transition: border 0.2s ease !important;
}
.stTextInput > div > div > input:focus {
    border: 1px solid rgba(255,75,31,0.6) !important;
    box-shadow: 0 0 0 3px rgba(255,75,31,0.1) !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 12px !important;
    color: #f0f0f0 !important;
}

/* ── Main CTA Button ── */
.stButton > button {
    width: 100%;
    background: linear-gradient(135deg, #ff4b1f 0%, #ff9068 100%);
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 20px !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    font-family: 'Outfit', sans-serif !important;
    letter-spacing: 0.5px !important;
    cursor: pointer;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 20px rgba(255,75,31,0.35) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(255,75,31,0.5) !important;
}
.stButton > button:active {
    transform: translateY(0px) !important;
}

/* ── Download button ── */
.stDownloadButton > button {
    width: 100% !important;
    background: linear-gradient(135deg, #00b894 0%, #00cec9 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 20px !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    font-family: 'Outfit', sans-serif !important;
    box-shadow: 0 4px 20px rgba(0,184,148,0.35) !important;
    transition: all 0.25s ease !important;
}
.stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(0,184,148,0.5) !important;
}

/* ── Progress bar ── */
.stProgress > div > div {
    background: linear-gradient(90deg, #ff4b1f, #ff9068) !important;
    border-radius: 10px !important;
}
.stProgress > div {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
}

/* ── Metadata card ── */
.meta-card {
    background: rgba(255,75,31,0.06);
    border: 1px solid rgba(255,75,31,0.2);
    border-radius: 14px;
    padding: 20px 24px;
    margin: 16px 0;
    display: flex;
    gap: 20px;
    align-items: flex-start;
}
.meta-cover {
    width: 80px;
    min-width: 80px;
    height: 110px;
    object-fit: cover;
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}
.meta-info h3 {
    margin: 0 0 4px;
    font-size: 1.1rem;
    font-weight: 700;
    color: #f0f0f0;
}
.meta-info p {
    margin: 3px 0;
    font-size: 0.85rem;
    color: #999;
}
.meta-badge {
    display: inline-block;
    background: rgba(255,75,31,0.2);
    color: #ff7a52;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 20px;
    margin-top: 6px;
    margin-right: 4px;
}
.meta-badge.green {
    background: rgba(0,184,148,0.2);
    color: #00cec9;
}

/* ── Divider ── */
.divider {
    height: 1px;
    background: rgba(255,255,255,0.07);
    margin: 24px 0;
}

/* ── Step label ── */
.step-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: #ff7a52;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 8px;
}

/* ── Format pills ── */
.format-pill {
    display: inline-block;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    color: #aaa;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 4px 12px;
    border-radius: 20px;
    margin-right: 6px;
}
.format-pill.active {
    background: rgba(255,75,31,0.2);
    border-color: rgba(255,75,31,0.5);
    color: #ff7a52;
}

/* ── Success box ── */
.success-box {
    background: rgba(0,184,148,0.08);
    border: 1px solid rgba(0,184,148,0.3);
    border-radius: 14px;
    padding: 20px 24px;
    text-align: center;
    margin: 16px 0;
}
.success-box .icon { font-size: 2.5rem; }
.success-box h3 { color: #00b894; margin: 8px 0 4px; font-size: 1.2rem; }
.success-box p { color: #888; font-size: 0.9rem; margin: 0; }

/* ── Alert boxes ── */
div[data-testid="stAlert"] {
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_to_path():
    """Make sure the scraper/builder modules are importable."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

_add_to_path()


def _build_pdf_bytes(metadata, chapters):
    """Run PDFBuilder and return the PDF as raw bytes."""
    from pdf_builder import PDFBuilder
    buf = io.BytesIO()

    # Monkey-patch to write into a BytesIO buffer
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = tmp.name

    builder = PDFBuilder(metadata, chapters)
    builder.build(tmp_path)

    with open(tmp_path, "rb") as f:
        data = f.read()
    _os.unlink(tmp_path)
    return data


def _build_epub_bytes(metadata, chapters):
    """Run EPUBBuilder and return the EPUB as raw bytes."""
    from epub_builder import EPUBBuilder
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
        tmp_path = tmp.name

    builder = EPUBBuilder(metadata, chapters)
    builder.build(tmp_path)

    with open(tmp_path, "rb") as f:
        data = f.read()
    _os.unlink(tmp_path)
    return data


def sanitize_slug(title):
    import re
    return re.sub(r'[\W_]+', '_', title.lower()).strip('_')


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-badge">📖 Wattpad Story Downloader</div>
    <div class="hero-title">WattpadStoryScrapper</div>
    <div class="hero-sub">Paste any Wattpad story link and download it as a beautiful novel-style PDF or EPUB — with cover image, table of contents, and proper formatting.</div>
</div>
""", unsafe_allow_html=True)

# ── Input Card ────────────────────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="step-label">Step 1 — Story URL</div>', unsafe_allow_html=True)

story_url = st.text_input(
    label="Wattpad Story URL",
    placeholder="https://www.wattpad.com/story/123456-story-name",
    label_visibility="collapsed"
)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="step-label">Step 2 — Download Format</div>', unsafe_allow_html=True)

col_fmt1, col_fmt2 = st.columns(2)
with col_fmt1:
    fmt = st.selectbox(
        "Format",
        options=["PDF (Novel Style)", "EPUB (e-Reader)", "Both (PDF + EPUB)"],
        label_visibility="collapsed"
    )

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="step-label">⚙️ Advanced Settings</div>', unsafe_allow_html=True)

adv_col1, adv_col2 = st.columns(2)
with adv_col1:
    delay_min = st.slider("Delay Min (s)", 0.5, 5.0, 1.5, 0.5,
                          help="Minimum wait time between chapter fetches")
with adv_col2:
    delay_max = st.slider("Delay Max (s)", 0.5, 6.0, 2.5, 0.5,
                          help="Maximum wait time between chapter fetches")

st.markdown('</div>', unsafe_allow_html=True)  # close card

# ── Download Button ───────────────────────────────────────────────────────────
go_btn = st.button("🚀  Download Story", use_container_width=True)

# ── Main Logic ────────────────────────────────────────────────────────────────
if go_btn:
    if not story_url.strip():
        st.error("⚠️  Please enter a Wattpad story URL first.")
        st.stop()

    if "wattpad.com/story" not in story_url:
        st.error("⚠️  That doesn't look like a valid Wattpad story URL. Example: `https://www.wattpad.com/story/299520008`")
        st.stop()

    if delay_max < delay_min:
        delay_max = delay_min + 0.5

    # ── Step 1: Fetch metadata ────────────────────────────────────────────────
    status_box = st.empty()
    prog = st.empty()

    with status_box.container():
        st.info("🔍  Fetching story metadata...")

    try:
        from scraper import WattpadScraper
        scraper = WattpadScraper(delay_min=delay_min, delay_max=delay_max)
        metadata = scraper.fetch_story_metadata(story_url.strip())
    except Exception as e:
        status_box.empty()
        st.error(f"❌  Failed to fetch story metadata: {e}")
        st.stop()

    status_box.empty()

    # ── Metadata card ─────────────────────────────────────────────────────────
    cover_url = metadata.get('cover_url', '')
    completed_badge = '<span class="meta-badge green">✅ Completed</span>' if metadata.get('completed') else '<span class="meta-badge">🔄 Ongoing</span>'
    chapter_count = len(metadata.get('chapters', []))

    st.markdown(f"""
    <div class="meta-card">
        {'<img class="meta-cover" src="' + cover_url + '" />' if cover_url else '<div style="width:80px;min-width:80px;height:110px;background:rgba(255,75,31,0.15);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:2rem;">📚</div>'}
        <div class="meta-info">
            <h3>{metadata['title']}</h3>
            <p>✍️ {metadata['author']} (@{metadata.get('author_username','?')})</p>
            <p>📚 {chapter_count} chapter{'s' if chapter_count != 1 else ''}</p>
            <div>{completed_badge}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Step 2: Fetch chapters ────────────────────────────────────────────────
    st.markdown('<div class="step-label">Downloading Chapters...</div>', unsafe_allow_html=True)
    progress_bar = st.progress(0)
    chapter_status = st.empty()

    chapters_content = []
    total = len(metadata['chapters'])
    failed = 0

    for idx, ch in enumerate(metadata['chapters']):
        pct = int((idx + 1) / total * 100)
        progress_bar.progress(pct)
        chapter_status.markdown(
            f"<p style='color:#888;font-size:0.85rem;margin:4px 0;'>📄 {idx+1}/{total} — {ch['title'][:60]}</p>",
            unsafe_allow_html=True
        )

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
        except Exception:
            failed += 1
            continue

        if idx < total - 1:
            time.sleep(random.uniform(delay_min, delay_max))

    progress_bar.progress(100)
    chapter_status.empty()

    if not chapters_content:
        st.error("❌  No chapters could be downloaded. The story may be private or deleted.")
        st.stop()

    # ── Success banner ────────────────────────────────────────────────────────
    fail_note = f" ({failed} failed)" if failed else ""
    st.markdown(f"""
    <div class="success-box">
        <div class="icon">🎉</div>
        <h3>Downloaded {len(chapters_content)}/{total} chapters{fail_note}</h3>
        <p>Now building your file — this may take a moment for long stories...</p>
    </div>
    """, unsafe_allow_html=True)

    slug = sanitize_slug(metadata['title'])

    # ── Step 3: Build & offer download ───────────────────────────────────────
    st.markdown('<div class="step-label">Step 3 — Download Your File</div>', unsafe_allow_html=True)

    with st.spinner("Building file(s)..."):
        if "PDF" in fmt:
            try:
                pdf_bytes = _build_pdf_bytes(metadata, chapters_content)
                st.download_button(
                    label="⬇️  Download PDF (Novel Style)",
                    data=pdf_bytes,
                    file_name=f"{slug}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_pdf"
                )
            except Exception as e:
                st.error(f"❌  PDF build failed: {e}")

        if "EPUB" in fmt:
            try:
                epub_bytes = _build_epub_bytes(metadata, chapters_content)
                st.download_button(
                    label="⬇️  Download EPUB (e-Reader)",
                    data=epub_bytes,
                    file_name=f"{slug}.epub",
                    mime="application/epub+zip",
                    use_container_width=True,
                    key="dl_epub"
                )
            except Exception as e:
                st.error(f"❌  EPUB build failed: {e}")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;margin-top:60px;padding-bottom:20px;">
    <p style="color:#444;font-size:0.78rem;">WattpadStoryScrapper · For personal use only · Respect authors' rights 📚</p>
</div>
""", unsafe_allow_html=True)
