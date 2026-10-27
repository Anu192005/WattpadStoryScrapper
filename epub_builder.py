import os
import zipfile
import uuid
import requests
from xml.sax.saxutils import escape as xml_escape

class EPUBBuilder:
    def __init__(self, metadata, chapters):
        self.metadata = metadata
        self.chapters = chapters
        self.book_id = str(uuid.uuid4())

    def download_cover(self):
        """Downloads the cover image and returns its raw bytes and extension."""
        cover_url = self.metadata.get('cover_url')
        if not cover_url:
            return None, None
        
        try:
            print(f"Downloading cover image: {cover_url}")
            # Wattpad covers are usually JPEGs
            r = requests.get(cover_url, timeout=10)
            if r.status_code == 200:
                # Deduce extension, default to .jpg
                ext = 'jpg'
                if '.png' in cover_url.lower():
                    ext = 'png'
                return r.content, ext
        except Exception as e:
            print(f"Failed to download cover image: {e}")
        return None, None

    def build(self, output_path):
        """Builds a valid EPUB archive at the target output path."""
        # 1. Download cover if available
        cover_bytes, cover_ext = self.download_cover()
        cover_filename = f"cover.{cover_ext}" if cover_bytes else None

        with zipfile.ZipFile(output_path, 'w') as epub:
            # A. The mimetype file must be the first file in the archive and stored (uncompressed)
            epub.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)

            # B. Write META-INF/container.xml
            container_xml = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
            epub.writestr('META-INF/container.xml', container_xml, compress_type=zipfile.ZIP_DEFLATED)

            # C. Write OEBPS/stylesheet.css
            stylesheet = """body {
    font-family: serif;
    margin: 10%;
    line-height: 1.5;
}
h1, h2, h3 {
    font-family: sans-serif;
    text-align: center;
}
h1 {
    margin-top: 20%;
    margin-bottom: 5%;
}
.author {
    text-align: center;
    font-style: italic;
    font-size: 1.2em;
    margin-bottom: 30%;
}
.description {
    margin-top: 10%;
    font-size: 0.95em;
    border-top: 1px solid #ccc;
    padding-top: 15px;
    text-align: justify;
}
p {
    text-indent: 1.5em;
    margin: 0 0 0.5em 0;
}
p:first-of-type {
    text-indent: 0;
}
.cover-img {
    display: block;
    margin: 0 auto;
    max-width: 100%;
    height: auto;
}"""
            epub.writestr('OEBPS/stylesheet.css', stylesheet, compress_type=zipfile.ZIP_DEFLATED)

            # D. Write Title Page
            title_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
  <title>{xml_escape(self.metadata['title'])}</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
</head>
<body>
  <h1>{xml_escape(self.metadata['title'])}</h1>
  <div class="author">By {xml_escape(self.metadata['author'])}</div>
"""
            if cover_filename:
                title_xhtml += f'  <div style="text-align: center;"><img class="cover-img" src="{cover_filename}" alt="Cover"/></div>\n'

            clean_desc_html = xml_escape(self.metadata['description']).replace('\n', '<br/>')
            title_xhtml += f"""  <div class="description">
    <strong>Description:</strong><br/>
    {clean_desc_html}
  </div>
</body>
</html>"""
            epub.writestr('OEBPS/title.xhtml', title_xhtml, compress_type=zipfile.ZIP_DEFLATED)

            # E. Write Chapters
            manifest_items = []
            spine_items = []
            
            # Setup metadata items for manifest
            manifest_items.append('<item id="stylesheet" href="stylesheet.css" media-type="text/css"/>')
            manifest_items.append('<item id="titlepage" href="title.xhtml" media-type="application/xhtml+xml"/>')
            
            spine_items.append('<itemref idref="titlepage"/>')

            if cover_bytes and cover_filename:
                # Add cover to ZIP
                epub.writestr(f"OEBPS/{cover_filename}", cover_bytes, compress_type=zipfile.ZIP_DEFLATED)
                mime = "image/jpeg" if cover_ext == 'jpg' else "image/png"
                manifest_items.append(f'<item id="cover-image" href="{cover_filename}" media-type="{mime}"/>')
                # Declare cover metadata property
                cover_meta = f'<meta name="cover" content="cover-image"/>'
            else:
                cover_meta = ''

            # Write each chapter file and record manifest/spine
            for idx, ch in enumerate(self.chapters):
                ch_filename = f"chapter_{idx+1}.xhtml"
                ch_id = f"chap_{idx+1}"
                
                ch_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
  <title>{xml_escape(ch['title'])}</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
</head>
<body>
  <h2>{xml_escape(ch['title'])}</h2>
  {ch['xhtml']}
</body>
</html>"""
                epub.writestr(f"OEBPS/{ch_filename}", ch_xhtml, compress_type=zipfile.ZIP_DEFLATED)
                
                manifest_items.append(f'<item id="{ch_id}" href="{ch_filename}" media-type="application/xhtml+xml"/>')
                spine_items.append(f'<itemref idref="{ch_id}"/>')

            # Add Table of Contents NCX item
            manifest_items.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')

            # F. Write toc.ncx
            toc_ncx_entries = []
            # Index 1 is title page
            toc_ncx_entries.append(f"""    <navPoint id="titlepage" playOrder="1">
      <navLabel><text>Title Page</text></navLabel>
      <content src="title.xhtml"/>
    </navPoint>""")
            
            for idx, ch in enumerate(self.chapters):
                play_order = idx + 2
                toc_ncx_entries.append(f"""    <navPoint id="chap_{idx+1}" playOrder="{play_order}">
      <navLabel><text>{xml_escape(ch['title'])}</text></navLabel>
      <content src="chapter_{idx+1}.xhtml"/>
    </navPoint>""")

            toc_ncx_entries_str = "\n".join(toc_ncx_entries)
            toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{self.book_id}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{xml_escape(self.metadata['title'])}</text>
  </docTitle>
  <navMap>
{toc_ncx_entries_str}
  </navMap>
</ncx>"""
            epub.writestr('OEBPS/toc.ncx', toc_ncx, compress_type=zipfile.ZIP_DEFLATED)

            # G. Write OEBPS/content.opf
            manifest_items_str = "\n    ".join(manifest_items)
            spine_items_str = "\n    ".join(spine_items)
            content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookID" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{xml_escape(self.metadata['title'])}</dc:title>
    <dc:creator opf:role="aut">{xml_escape(self.metadata['author'])}</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="BookID" opf:scheme="UUID">{self.book_id}</dc:identifier>
    {cover_meta}
  </metadata>
  <manifest>
    {manifest_items_str}
  </manifest>
  <spine toc="ncx">
    {spine_items_str}
  </spine>
</package>"""
            epub.writestr('OEBPS/content.opf', content_opf, compress_type=zipfile.ZIP_DEFLATED)
