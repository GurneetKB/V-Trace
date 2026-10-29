"""Markdown -> styled A4 PDF via headless Microsoft Edge (no Word or LibreOffice needed).

Same content and colours as the .docx built by md2docx.py; used for the PDF versions of the deliverables.
"""
import re
import subprocess
import tempfile
from pathlib import Path

import markdown

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CSS = """
@page { size: A4; margin: 20mm 19mm 20mm 19mm; }
body { font-family: Calibri, 'Segoe UI', Arial, sans-serif; font-size: 10.6pt; line-height: 1.42; color: #1B2830; }
h1 { color: #111820; font-size: 21pt; margin: 0 0 6pt; break-before: page; }
h1.first { break-before: avoid; }
h2 { color: #0E8782; font-size: 14pt; margin: 16pt 0 5pt; break-after: avoid; }
h3 { color: #111820; font-size: 11.5pt; margin: 11pt 0 4pt; break-after: avoid; }
p { margin: 0 0 6pt; text-align: left; }
ul, ol { margin: 0 0 6pt; padding-left: 18pt; } li { margin: 0 0 2.5pt; }
table { border-collapse: collapse; margin: 4pt auto 10pt; font-size: 9.2pt; break-inside: avoid; }
th { background: #34454D; color: #fff; text-align: left; padding: 3pt 6pt; }
td { border-bottom: 1px solid #D3DEE2; padding: 3pt 6pt; } tr:nth-child(even) td { background: #EAF7F6; }
code { font-family: Consolas, monospace; font-size: 9pt; color: #0E8782; }
pre { background: #F4F7F8; padding: 7pt 9pt; font-size: 8pt; line-height: 1.25; border-radius: 4pt; break-inside: avoid; }
pre code { color: #1B2830; }
blockquote { background: #EAF7F6; margin: 6pt 0; padding: 6pt 10pt; border-radius: 4pt; }
figure { margin: 8pt 0 12pt; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; max-height: 112mm; }
figcaption { font-size: 9pt; color: #60727C; font-style: italic; margin-top: 3pt; }
.title { height: 245mm; display: flex; flex-direction: column; break-after: page; }
.title img { width: 62mm; } .title .t { font-size: 32pt; font-weight: 700; color: #111820; margin-top: 70mm; }
.title .s1 { font-size: 15pt; font-weight: 700; color: #0E8782; margin: 6pt 0 14pt; }
.title .s { font-size: 12pt; color: #34454D; margin: 2pt 0; }
.toc h2 { color: #111820; } .toc ul { list-style: none; padding-left: 0; } .toc li { margin: 3pt 0; }
.toc li li { padding-left: 14pt; font-size: 9.8pt; color: #34454D; }
.header { font-size: 9pt; color: #34454D; margin-bottom: 8pt; }
"""


def _figures(html):
    """<p><img alt=cap></p> -> <figure> with a caption."""
    return re.sub(r'<p><img alt="([^"]*)" src="([^"]*)" ?/?></p>',
                  lambda m: f'<figure><img src="{m.group(2)}"><figcaption>{m.group(1)}</figcaption></figure>', html)


def _normalise_lists(md_text):
    """Python-Markdown needs a blank line before a list and 4-space nesting; the project docs use neither."""
    out, prev = [], ""
    for line in md_text.splitlines():
        item = re.match(r"^(\s*)([-*]|\d+\.)\s", line)
        if item:
            line = " " * (len(item.group(1)) * 2) + line.lstrip()
            if prev.strip() and not re.match(r"^\s*([-*]|\d+\.)\s", prev) and not prev.startswith("    "):
                out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)


def convert(md_text, out_pdf, base_dir, title=None, subtitle_lines=(), logo=None, toc=False):
    base = Path(base_dir).resolve()
    md_text = _normalise_lists(md_text)
    if title:                                         # the document's own H1 is replaced by the title page
        md_text = re.sub(r"^# .*\n", "", md_text, count=1)
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])
    body = re.sub(r'src="(?!http|file:)([^"]+)"', lambda m: f'src="{(base / m.group(1)).resolve().as_uri()}"', body)
    body = _figures(body)
    body = body.replace("<h1", '<h1 class="first"', 1)
    head = ""
    if title:
        subs = "".join(f'<div class="{"s1" if i == 0 else "s"}">{s}</div>' for i, s in enumerate(subtitle_lines))
        head = (f'<div class="title"><img src="{Path(logo).resolve().as_uri()}"><div class="t">{title}</div>{subs}</div>'
                if logo else f'<div class="title"><div class="t">{title}</div>{subs}</div>')
        if toc:
            items = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h\1>', body)
            li, open_sub = [], False
            for lvl, _, txt in items:
                if lvl == "2":
                    li.append(("</ul></li>" if open_sub else "") + f"<li>{txt}")
                    open_sub = False
                else:
                    li.append(("" if open_sub else "<ul>") + f"<li>{txt}</li>")
                    open_sub = True
            head += ('<div class="toc" style="break-after: page"><h2>Contents</h2><ul>' + "".join(li)
                     + ("</ul></li>" if open_sub else "</li>") + "</ul></div>")
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{head}{body}</body></html>"
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "doc.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={Path(tmp) / 'profile'}", f"--print-to-pdf={Path(out_pdf).resolve()}",
                        page.as_uri()], check=True, capture_output=True, timeout=180)
    return out_pdf
