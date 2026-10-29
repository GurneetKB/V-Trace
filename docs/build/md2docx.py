"""Minimal Markdown -> styled .docx for the project documents (python-docx; no pandoc needed).

Supports: # / ## / ### headings, paragraphs, - bullets (2-space nesting), 1. numbered lists, > notes,
| tables |, ![caption](path) images, ``` code blocks, inline **bold**, *italic*, `code`, and a
title page (logo, title, subtitle lines). Colours follow the proposal deck (navy / teal).
"""
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

NAVY, TEAL, SLATE, MIST = RGBColor(0x11, 0x18, 0x20), RGBColor(0x0E, 0x87, 0x82), RGBColor(0x34, 0x45, 0x4D), "EAF7F6"
INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)")


def _shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def _runs(par, text, size=None, color=None, bold=False):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = par.add_run(part[2:-2]); r.bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = par.add_run(part[1:-1]); r.font.name = "Consolas"; r.font.size = Pt((size or 11) - 1)
            r.font.color.rgb = TEAL
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            r = par.add_run(part[1:-1]); r.italic = True
        else:
            r = par.add_run(part)
        if bold:
            r.bold = True
        if size and not part.startswith("`"):
            r.font.size = Pt(size)
        if color is not None and not part.startswith("`"):
            r.font.color.rgb = color


def _base_styles(doc):
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.12
    for lvl, size, color in ((1, 17, NAVY), (2, 13.5, TEAL), (3, 12, NAVY)):
        h = doc.styles[f"Heading {lvl}"]
        h.font.name, h.font.size, h.font.bold, h.font.color.rgb = "Calibri", Pt(size), True, color
        h.element.rPr.rFonts.set(qn("w:asciiTheme"), "") if False else None
        rf = h.element.rPr.rFonts
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rf.set(qn(a), "Calibri")
        h.paragraph_format.space_before = Pt(14 if lvl == 1 else 10)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True


def _footer(section, text):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _runs(p, text + "  ·  page ", 9, SLATE)
    r = p.add_run()
    for kind, val in (("begin", None), ("instr", "PAGE"), ("end", None)):
        if kind == "instr":
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = val
        else:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
        r._r.append(el)
    r.font.size = Pt(9); r.font.color.rgb = SLATE


def _toc(doc):
    p = doc.add_paragraph()
    r = p.add_run()
    for kind, val in (("begin", None), ("instr", 'TOC \\o "1-2" \\h \\z \\u'), ("separate", None), ("end", None)):
        if kind == "instr":
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = val
        else:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
        r._r.append(el)


def convert(md_path, out_path, root, title=None, subtitle_lines=(), logo=None, footer="", toc=False,
            margins_cm=2.2):
    md = Path(md_path).read_text(encoding="utf-8").splitlines()
    doc = Document()
    _base_styles(doc)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(margins_cm))
    width = sec.page_width - sec.left_margin - sec.right_margin

    if title:                                                     # title page
        if logo and Path(logo).exists():
            doc.add_paragraph().add_run().add_picture(str(logo), width=Cm(6))
        for _ in range(3):
            doc.add_paragraph()
        p = doc.add_paragraph(); _runs(p, title, 30, NAVY, bold=True)
        for i, line in enumerate(subtitle_lines):
            p = doc.add_paragraph(); _runs(p, line, 15 if i == 0 else 12, TEAL if i == 0 else SLATE, bold=i == 0)
        if toc:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            h = doc.add_paragraph(); _runs(h, "Contents", 17, NAVY, bold=True)
            _toc(doc)
        sec = doc.add_section(WD_SECTION.NEW_PAGE)
    if footer:
        _footer(doc.sections[-1], footer)
        doc.sections[-1].footer.is_linked_to_previous = False
        if title:                                                 # no footer on the title page
            doc.sections[0].footer.is_linked_to_previous = False

    i, first_h1 = 0, True
    while i < len(md):
        line = md[i]
        s = line.strip()
        if not s or s == "---":
            i += 1; continue
        if s.startswith("```"):
            i += 1
            block = []
            while i < len(md) and not md[i].strip().startswith("```"):
                block.append(md[i]); i += 1
            i += 1
            t = doc.add_table(rows=1, cols=1); c = t.cell(0, 0); _shade(c, "F4F7F8")
            c.paragraphs[0].text = ""
            for j, b in enumerate(block):
                p = c.paragraphs[0] if j == 0 else c.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                r = p.add_run(b); r.font.name = "Consolas"; r.font.size = Pt(8.5)
            doc.add_paragraph()
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if m:
            lvl = len(m.group(1))
            if lvl == 1 and title and first_h1:              # the document's own H1 is replaced by the title page
                first_h1 = False; i += 1; continue
            doc.add_heading("", level=lvl)
            _runs(doc.paragraphs[-1], m.group(2))
            i += 1; continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)", s)
        if m:
            img = (Path(root) / m.group(2)).resolve()
            if img.exists():
                p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                from PIL import Image
                iw, ih = Image.open(img).size
                w = min(width, int(Cm(13) * iw / ih)) if ih > iw * 0.9 else width
                p.add_run().add_picture(str(img), width=w)
            else:
                p = doc.add_paragraph(); _runs(p, f"[missing figure: {m.group(2)}]", 10, SLATE)
            if m.group(1):
                c = doc.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _runs(c, m.group(1), 9.5, SLATE)
                c.runs[0].italic = True if c.runs else None
            i += 1; continue
        if s.startswith("|"):
            rows = []
            while i < len(md) and md[i].strip().startswith("|"):
                cells = [c.strip() for c in md[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            ncol = max(len(r) for r in rows)
            t = doc.add_table(rows=len(rows), cols=ncol)
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for r_, row in enumerate(rows):
                for c_ in range(ncol):
                    cell = t.cell(r_, c_)
                    cell.paragraphs[0].paragraph_format.space_after = Pt(0)
                    _runs(cell.paragraphs[0], row[c_] if c_ < len(row) else "", 9.5,
                          RGBColor(0xFF, 0xFF, 0xFF) if r_ == 0 else None, bold=r_ == 0)
                    if r_ == 0:
                        _shade(cell, "34454D")
                    elif r_ % 2 == 0:
                        _shade(cell, MIST)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue
        if s.startswith(">"):
            t = doc.add_table(rows=1, cols=1); c = t.cell(0, 0); _shade(c, MIST)
            text = []
            while i < len(md) and md[i].strip().startswith(">"):
                text.append(md[i].strip().lstrip(">").strip()); i += 1
            c.paragraphs[0].paragraph_format.space_after = Pt(0)
            _runs(c.paragraphs[0], " ".join(text), 10.5, SLATE)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", line)
        if m:
            depth = len(m.group(1)) // 2
            numbered = m.group(2)[0].isdigit()
            style = ("List Number" if numbered else "List Bullet") + (f" {depth + 1}" if depth else "")
            p = doc.add_paragraph(style=style)
            p.paragraph_format.space_after = Pt(3)
            _runs(p, m.group(3))
            i += 1; continue
        para = [s]                                                # paragraph: join wrapped lines
        i += 1
        while i < len(md) and md[i].strip() and not re.match(r"^(#|\||>|!\[|```|\s*([-*]|\d+\.)\s)", md[i]):
            para.append(md[i].strip()); i += 1
        p = doc.add_paragraph()
        _runs(p, " ".join(para))
    doc.save(out_path)
    return out_path
