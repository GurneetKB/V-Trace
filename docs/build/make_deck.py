"""Build the final presentation deck (deliverables/V-Trace_Final_Presentation.pptx).

The design follows the first-presentation deck: dark title/closing slides with the teal wave artwork and the
V-Trace logo, white content slides with a bold title, a one-line subtitle over a thin teal rule, the NUS-ISS logo
top-right, pastel cards with coloured numbers, teal chevrons and a navy key-message box (Aptos Display / Aptos).

All numbers come from results/metrics.json (VeRi-776) and results/demo_eval.json (demo cameras); screenshots from
docs/screenshots/. Speaker notes hold the script for the recorded 10-15 minute video.

    python docs/build/make_deck.py
"""
import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
RES, SHOTS, FIGS = ROOT / "results", ROOT / "docs" / "screenshots", ROOT / "docs" / "figures"
ART = ROOT / "docs" / "build" / "assets"
OUT = ROOT / "deliverables" / "V-Trace_Final_Presentation.pptx"
LOGO_DARK = ROOT / "assets" / "vtrace_logo_dark.png"
NUS = ART / "nus_iss_logo.png"

# palette of the first-presentation deck
INK, BODY_C, MUTED, RULE, BORDER = "161B22", "2B333C", "5C6670", "4FB3AE", "D6DEE6"
TEAL, TEAL_D, GREEN, GREEN_D, NAVY_BOX = "12A7A1", "0E8782", "5DC55B", "3E8E3A", "15324B"
MINT_T = "B8E9E6"
BLUE, PEACH, LAV, MINT, LGREEN, GREY, CREAM = "EAF1F8", "F4E9E0", "E9E7F5", "E9F5F3", "EFF5E8", "F3F5F7", "FDF4E8"
N_TEAL, N_ORANGE, N_PURPLE = "4FA5B5", "D08A55", "7E6DB8"
HEAD, BODY = "Aptos Display", "Aptos"

M = json.loads((RES / "metrics.json").read_text())
D = json.loads((RES / "demo_eval.json").read_text())


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


# ------------------------------------------------------------------ primitives
def text(slide, x, y, w, h, runs, size=16, color=BODY_C, bold=False, font=BODY, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=6, name=None):
    """runs: str, or list of paragraphs; a paragraph is a str, a list of (text, {opts}) runs, or
    {"bullet": True, "text": ...}."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, para in enumerate(runs if isinstance(runs, list) else [runs]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(spacing)
        bullet = isinstance(para, dict) and para.get("bullet")
        if isinstance(para, dict):
            para = para["text"]
        for j, (txt, o) in enumerate([(para, {})] if isinstance(para, str) else para):
            r = p.add_run()
            r.text = ("•  " if bullet and j == 0 else "") + txt
            r.font.name = o.get("font", font)
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.italic = o.get("italic", False)
            r.font.color.rgb = rgb(o.get("color", color))
    return tb


def box(slide, x, y, w, h, fill, line=BORDER, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.035):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(0.75)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def label(shape, lines, size=14, color="FFFFFF", bold=True, align=PP_ALIGN.CENTER, font=BODY):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, line in enumerate(lines.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.name, r.font.size, r.font.bold = font, Pt(size if i == 0 else size - 2), bold and i == 0
        r.font.color.rgb = rgb(color)


def chevron(slide, x, y, w=0.32, h=0.5, color=TEAL):
    s = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(color)
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def picture(slide, path, x, y, w=None, h=None):
    if not Path(path).exists():
        ph = box(slide, x, y, w or 4, h or 3, GREY)
        label(ph, f"[missing image]\n{Path(path).name}", 12, MUTED, bold=False)
        return ph
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)


def fit_picture(slide, path, x, y, w, h):
    from PIL import Image
    if not Path(path).exists():
        return picture(slide, path, x, y, w, h)
    iw, ih = Image.open(path).size
    s = min(w / iw, h / ih)
    return picture(slide, path, x + (w - iw * s) / 2, y + (h - ih * s) / 2, iw * s, ih * s)


NO = [0]


def content_slide(title, subtitle, notes):
    s = prs.slides.add_slide(BLANK)
    NO[0] += 1
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb("FFFFFF")
    text(s, 0.45, 0.3, 10.6, 0.7, title, 30, INK, bold=True, font=HEAD, name="Title")
    text(s, 0.47, 0.98, 11, 0.3, subtitle, 12, BODY_C, name="Subtitle")
    line = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.45), Inches(1.33), Inches(13.0), Inches(1.33))
    line.line.color.rgb = rgb(RULE)
    line.line.width = Pt(0.75)
    picture(s, NUS, 11.4, 0.16, w=1.85)
    text(s, 12.55, 7.05, 0.45, 0.25, str(NO[0]), 9, BODY_C, align=PP_ALIGN.RIGHT, name="Slide number")
    s.notes_slide.notes_text_frame.text = notes
    return s


def dark_slide(art, notes):
    s = prs.slides.add_slide(BLANK)
    NO[0] += 1
    picture(s, art, 0, 0, w=13.333, h=7.5)
    picture(s, NUS, 11.4, 0.16, w=1.85)
    s.notes_slide.notes_text_frame.text = notes
    return s


def key_box(slide, x, y, w, h, msg, size=17):
    b = box(slide, x, y, w, h, NAVY_BOX, line=None, radius=0.12)
    label(b, msg, size, "FFFFFF", font=HEAD)


def style_chart(chart, colors, legend=True, fmt="0", size=12):
    chart.font.name, chart.font.size = BODY, Pt(size)
    chart.font.color.rgb = rgb(BODY_C)
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)
    for s, c in zip(chart.plots[0].series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(c)
    plot = chart.plots[0]
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = fmt, False
    dl.font.size, dl.font.color.rgb = Pt(size - 1), rgb(BODY_C)
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    va = chart.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb("E6EBEF")
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(size - 1)
    chart.category_axis.format.line.color.rgb = rgb(BORDER)
    chart.category_axis.tick_labels.font.size = Pt(size)


def add_chart(slide, kind, cats, series, x, y, w, h, colors, **kw):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, [round(v, 1) for v in vals])
    chart = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    style_chart(chart, colors, **kw)
    return chart


# ================================================================== 1 title
s = dark_slide(ART / "bg_title.png",
    "Hello, I'm Gurneet Kaur Bhuller from Group 21. This is V-Trace, a multi-attribute vehicle re-identification "
    "system. In the next twelve minutes I'll recap the problem, explain how V-Trace works, show how I evaluated it on "
    "the VeRi-776 benchmark and on multi-camera demo footage, share what I learned, and then demonstrate the app.")
picture(s, LOGO_DARK, 0.55, 1.15, w=8.6)
text(s, 0.75, 4.25, 9, 0.5, "DESCRIBE  →  SEARCH  →  CONFIRM  →  RE-IDENTIFY  →  TRACE", 22, GREEN, bold=True, font=HEAD)
text(s, 0.75, 5.05, 9, 0.5, "Multi-Attribute Vehicle Re-Identification System", 26, MINT_T)
text(s, 0.75, 5.95, 9, 0.4, "Gurneet Kaur Bhuller  |  Group 21", 17, "FFFFFF")
text(s, 0.75, 6.45, 9, 0.3, "Pattern Recognition Systems · Final Presentation", 12, "AEB8C2")

# ================================================================== 2 problem
plate = M["reid"]
s = content_slide("The Problem",
                  "A plate is powerful evidence — but CCTV does not always give us a readable plate.",
    "Quick recap of the problem. A licence plate is the strongest single clue, but CCTV often can't read it: too "
    "small, blurred, occluded or facing away. On the VeRi-776 benchmark a plate-only search is perfect with clear "
    "plates, drops to 30 percent mean average precision with partial plates, and to 3.6 percent when the plate is "
    "hidden. Investigators also start from a partial description, not a clean image. So the objective stays the same "
    "as in my proposal: search and re-identify a vehicle using all available evidence, with a human in the loop.")
cards = [("CLEAR PLATE", "Strong identifier", plate["clear"]["plate_sim"]["mAP"], BLUE, N_TEAL),
         ("PARTIAL PLATE", "Useful, but not enough alone", plate["partial"]["plate_sim"]["mAP"], PEACH, N_ORANGE),
         ("NO PLATE", "Only appearance remains: colour · type · shape · cues", plate["hidden"]["plate_sim"]["mAP"], LAV, N_PURPLE)]
for i, (h, d, v, fill, nc) in enumerate(cards):
    x = 0.6 + i * 4.15
    box(s, x, 1.75, 3.85, 3.3, fill)
    text(s, x + 0.25, 1.95, 3.4, 0.45, f"{i + 1:02d}", 20, nc, bold=True, font=HEAD)
    text(s, x + 0.25, 2.5, 3.4, 0.5, h, 20, INK, bold=True, font=HEAD)
    text(s, x + 0.25, 3.1, 3.4, 0.8, d, 15, BODY_C)
    text(s, x + 0.25, 4.0, 3.4, 0.6, [[(f"{v:.1f}%", {"size": 28, "bold": True, "color": nc, "font": HEAD}),
                                        ("  plate-only mAP", {"size": 12, "color": MUTED})]], 12)
text(s, 0.6, 5.45, 1.6, 0.5, "Objective", 18, TEAL, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
text(s, 2.2, 5.35, 10.5, 0.8, "Search and re-identify a target vehicle across multiple camera recordings using all "
                              "available visual evidence.", 20, INK, bold=True, font=HEAD)
text(s, 2.2, 6.45, 10.5, 0.4, "V-Trace ranks potential matches for human review — it does not claim definitive "
                              "forensic identity.", 13, INK, bold=True)

# ================================================================== 3 how the user uses it
s = content_slide("How the User Uses V-Trace",
                  "The user starts with what they know — and confirms each step, from the first match to the full route.",
    "This is the workflow, as in the proposal, now with a sixth step. Upload the camera videos, or use the one-click "
    "demo. Describe the vehicle with whatever is known. Stage one ranks every tracked vehicle. The user confirms the "
    "right candidate, which becomes the visual query. Stage two re-identifies it in the other cameras. And the new "
    "trace step suggests the route and lets the user confirm the sighting in each camera with one click.")
steps = [("1  UPLOAD", "Camera A.mp4\nCamera B.mp4\nCamera C.mp4\n(or Quick demo)", MINT, INK),
         ("2  DESCRIBE", "Red sedan\nPlate: SGX12??\nRoof rack", LAV, INK),
         ("3  SEARCH", "#1  camA · 0:41\n#2  camA · 0:01\n#3  camC · 0:03", BLUE, INK),
         ("4  CONFIRM", "User selects the most plausible candidate", LGREEN, GREEN_D),
         ("5  RE-IDENTIFY", "Ranked sightings in other videos + frames + timestamps", "E8F3E8", GREEN_D),
         ("6  TRACE", "Route camA → camB → camC, confirmed per camera", "E3F1EF", TEAL_D)]
for i, (h, d, fill, hc) in enumerate(steps):
    x = 0.45 + i * 2.14
    box(s, x, 1.75, 1.82, 3.6, fill)
    text(s, x + 0.17, 1.93, 1.55, 0.7, h, 17, hc, bold=True, font=HEAD)
    text(s, x + 0.17, 2.95, 1.55, 2.2, d.split("\n"), 14, BODY_C, spacing=2)
    if i < 5:
        chevron(s, x + 1.87, 3.3, 0.22, 0.45)
for x1, x2, c, lab in ((1.0, 6.35, TEAL, "DESCRIPTION-TO-VEHICLE RETRIEVAL"), (7.0, 12.6, GREEN, "VEHICLE-TO-VEHICLE Re-ID + ROUTE")):
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(5.75), Inches(x2), Inches(5.75))
    ln.line.color.rgb, ln.line.width = rgb(c), Pt(1.5)
    ln.line.dash_style = 3
    text(s, x1, 6.0, x2 - x1, 0.4, lab, 13, c, bold=True, font=HEAD, align=PP_ALIGN.CENTER)

# ================================================================== 4 system design
s = content_slide("System Design",
                  "Raw videos become searchable vehicle tracks, then ranked sightings and a confirmed route.",
    "Here is the system as built. Each uploaded video is one camera. YOLO11 detects vehicles and ByteTrack links "
    "them into tracks; each track becomes a tracklet with four good crops and an evidence frame. From the crops "
    "V-Trace computes its descriptors, including a learned re-identification metric. The user's description is "
    "matched in stage one; after confirmation, stage two compares the confirmed vehicle with every tracklet in the "
    "other cameras using an eleven-feature evidence vector, and the route view links the sightings across cameras. "
    "Everything runs in a Streamlit app with an admin sign-in.")
pipe = [("VIDEOS", "Uploaded camera footage\n(one video = one camera)", BLUE),
        ("DETECT + TRACK", "YOLO11n + ByteTrack\n→ tracklets", BLUE),
        ("REPRESENT", "ResNet-50 · CLIP\nlearned metric (LDA)\ncolour · type · plate", MINT),
        ("INDEX + SEARCH", "User description\n→ ranked candidates", "E6F2E9"),
        ("CONFIRM", "Selected candidate becomes the visual query", "FDF1E3"),
        ("Re-ID + FUSION", "11 evidence features\nfusion / Random Forest", "DDE7EC"),
        ("TRACE ROUTE", "Top-3 per camera\nconfirmed hop by hop", "E3F1EF")]
for i, (h, d, fill) in enumerate(pipe):
    x = 0.4 + i * 1.84
    box(s, x, 1.75, 1.6, 3.9, fill)
    text(s, x + 0.15, 1.93, 1.35, 0.8, h, 15, INK, bold=True, font=HEAD)
    text(s, x + 0.15, 3.0, 1.35, 2.5, d.split("\n"), 13, BODY_C, spacing=3)
    if i < 6:
        chevron(s, x + 1.63, 3.45, 0.18, 0.4)
text(s, 0.45, 6.05, 12.4, 0.6, "Tracklet = observations of one tracked vehicle while it is visible in one video",
     14, INK, bold=True, align=PP_ALIGN.CENTER)
text(s, 0.45, 6.45, 12.4, 0.4, "Streamlit app: sign-in · upload · search · re-identify · route · track review · SOM · evaluation",
     12, MUTED, align=PP_ALIGN.CENTER)

# ================================================================== 5 descriptors
s = content_slide("Vehicle Representation",
                  "Every tracklet gets several complementary descriptors — no single cue is required.",
    "Each tracklet gets several descriptors. ResNet-50 and CLIP embeddings describe its appearance, and a projection "
    "learned from VeRi vehicle identities with linear discriminant analysis turns them into the main "
    "re-identification cue: it keeps what separates two cars and suppresses viewpoint and lighting. Colour and type "
    "come from a supervised probe on CLIP; an HSV histogram is a hand-crafted colour cue; EasyOCR reads plates only "
    "when confident, with question marks as wildcards; and CLIP scores distinctive cues such as a roof rack or decal.")
desc = [("LEARNED Re-ID METRIC", "PCA + LDA on [ResNet | CLIP], trained on VeRi vehicle identities — the main Re-ID cue", BLUE, N_TEAL),
        ("APPEARANCE", "ResNet-50 (2048-d) + CLIP ViT-B/32 (512-d) embeddings, averaged over 4 crops", MINT, N_TEAL),
        ("COLOUR & TYPE", "Supervised linear probe on CLIP (10 colours · 9 types); zero-shot fallback", PEACH, N_ORANGE),
        ("HSV HISTOGRAM", "16×4×4 hand-crafted colour histogram of the vehicle centre", CREAM, N_ORANGE),
        ("LICENCE PLATE", "EasyOCR on the largest crops; wildcard (?) Levenshtein matching", LAV, N_PURPLE),
        ("DISTINCTIVE CUES", "CLIP text–image score: roof rack · spoiler · dent · decal · roof cargo", "EFEDF8", N_PURPLE)]
for i, (h, d, fill, nc) in enumerate(desc):
    x, y = 0.6 + (i % 3) * 4.15, 1.7 + (i // 3) * 2.6
    box(s, x, y, 3.85, 2.35, fill)
    text(s, x + 0.25, y + 0.2, 3.4, 0.4, f"{i + 1:02d}", 18, nc, bold=True, font=HEAD)
    text(s, x + 0.25, y + 0.68, 3.4, 0.45, h, 16, INK, bold=True, font=HEAD)
    text(s, x + 0.25, y + 1.2, 3.4, 1.1, d, 14, BODY_C)

# ================================================================== 6 re-id + route
s = content_slide("Re-Identification & Route Tracing",
                  "Pairwise evidence is fused into one score; the route is suggested, then confirmed camera by camera.",
    "For the confirmed vehicle and every candidate in another camera, V-Trace builds an eleven-number evidence "
    "vector. Four scorers are compared: appearance only, the learned metric, a transparent weighted fusion, and a "
    "Random Forest with monotonic constraints. Route tracing suggests one sighting per camera only when it clearly "
    "beats that camera's runner-up, and shows the top three per camera so the user confirms each hop. Every confirmed "
    "sighting joins the query set, so the middle camera bridges a far, small view and a near, large view. When the "
    "cameras share a clock, a time window rejects impossible jumps.")
feats = ["learned-metric cosine", "ResNet cosine", "CLIP cosine", "HSV histogram", "colour agreement", "type agreement",
         "plate similarity", "both plates read", "cue agreement", "track quality / consistency"]
box(s, 0.6, 1.7, 5.6, 4.6, GREY)
text(s, 0.85, 1.9, 5.1, 0.4, "EVIDENCE VECTOR (11 FEATURES)", 15, INK, bold=True, font=HEAD)
for i, f in enumerate(feats):
    x, y = 0.85 + (i % 2) * 2.62, 2.45 + (i // 2) * 0.55
    c = box(s, x, y, 2.48, 0.44, "FFFFFF", radius=0.3)
    label(c, f, 12, BODY_C, bold=False)
text(s, 0.85, 5.3, 5.1, 0.9, [[("Scorers  ", {"bold": True, "color": TEAL_D}),
                               ("appearance only · learned metric · weighted fusion · Random Forest (monotonic)", {})]], 13)
box(s, 6.6, 1.7, 6.15, 4.6, "E3F1EF")
text(s, 6.85, 1.9, 5.6, 0.4, "ROUTE TRACING", 15, INK, bold=True, font=HEAD)
for i, (c_, d_) in enumerate((("camA", "far · small"), ("camB", "mid"), ("camC", "near · large"))):
    x = 6.95 + i * 1.95
    b = box(s, x, 2.45, 1.55, 0.95, TEAL if i == 0 else NAVY_BOX, line=None, radius=0.1)
    label(b, f"{c_}\n{d_}", 15)
    if i < 2:
        chevron(s, x + 1.6, 2.72, 0.25, 0.4, GREEN)
text(s, 6.85, 3.7, 5.7, 2.5, [
    {"bullet": True, "text": [("Score each camera's tracklets against ", {}), ("all", {"bold": True}), (" known views of the car", {})]},
    {"bullet": True, "text": "Suggest a camera only if its best clearly beats its runner-up"},
    {"bullet": True, "text": "Show the top 3 per camera — the user confirms each hop in one click"},
    {"bullet": True, "text": "Each confirmation re-scores the rest; a time window rejects impossible jumps"}], 14)
key_box(s, 0.6, 6.5, 12.15, 0.55, "EVERY STEP IS A RANKED CANDIDATE FOR HUMAN REVIEW", 15)

# ================================================================== 7 technique groups
s = content_slide("Technique Groups",
                  "All four technique groups are implemented, each with a distinct role in the same pipeline.",
    "The module asks for at least three of four technique groups; V-Trace integrates all four. Supervised: LDA metric "
    "learning on vehicle identities, the Random Forest matcher and the colour-type probe. Unsupervised: a "
    "Self-Organising Map of the embeddings. Deep learning: YOLO11, ResNet-50, CLIP and EasyOCR. Hybrid and ensemble: "
    "fusion of eleven evidence features. Intelligent sensing and sense-making: the chain from raw video to a confirmed route.")
groups = [("1  SUPERVISED / UNSUPERVISED", "Supervised: LDA metric learning · Random Forest same/different matcher · colour/type probe\nUnsupervised: Self-Organising Map (+ PCA) of vehicle embeddings", BLUE),
          ("2  MACHINE / DEEP LEARNING", "YOLO11n vehicle detection + ByteTrack\nResNet-50 / CLIP embeddings · EasyOCR plates", MINT),
          ("3  HYBRID / ENSEMBLE", "Random Forest / weighted fusion combine metric + appearance + colour + type + plate + track evidence", "FDF1E3"),
          ("4  INTELLIGENT SENSING / SENSE-MAKING", "Raw video → detections → tracks → descriptors → candidates → confirmed target → route", LGREEN)]
for i, (h, d, fill) in enumerate(groups):
    x, y = 0.6 + (i % 2) * 6.2, 1.7 + (i // 2) * 2.65
    box(s, x, y, 5.95, 2.35, fill)
    text(s, x + 0.25, y + 0.25, 5.5, 0.45, h, 17, INK, bold=True, font=HEAD)
    text(s, x + 0.25, y + 1.0, 5.5, 1.3, d.split("\n"), 15, BODY_C, spacing=4)

# ================================================================== 8 data
st_ = M["setup"]
s = content_slide("Data & Evaluation Protocol",
                  "Benchmark data measures Re-ID performance; multi-camera footage tests the complete workflow.",
    "Two kinds of data, as planned. VeRi-776 answers whether the method works: images of one vehicle passing one "
    "camera are grouped into tracklets, the same unit my video pipeline produces, with 150 training and 100 test "
    "vehicles that never overlap. The demo footage answers whether the software works end to end: an openly licensed "
    "street recording is cut into three camera zones along the road, so the same cars really pass camera A, then B, "
    "then C, and a fourth camera on another road is a distractor. A reference tracking of the full frame gives "
    "pseudo ground truth for measuring the demo.")
box(s, 0.6, 1.7, 5.0, 4.6, LAV)
text(s, 0.85, 1.9, 4.5, 0.4, "BENCHMARK  |  VeRi-776", 16, INK, bold=True, font=HEAD)
text(s, 0.85, 2.5, 4.5, 3.6, ["50K+ images · 776 vehicles · 20 cameras",
                              f"{st_['train_ids']} train / {st_['test_ids']} test vehicles (identity-disjoint)",
                              f"{st_['n_train_tracklets']:,} / {st_['n_test_tracklets']:,} tracklets · {st_['max_queries']} Re-ID queries",
                              "", "Used for:",
                              {"bullet": True, "text": "learned metric, probes and Random Forest"},
                              {"bullet": True, "text": "Rank-1 / Rank-5 / mAP · plate degradation"},
                              {"bullet": True, "text": "attribute accuracy · SOM purity"}], 14, spacing=3)
box(s, 6.0, 1.7, 6.75, 4.6, BLUE)
text(s, 6.25, 1.9, 6.3, 0.4, "VIDEO DEMONSTRATION  |  4 CAMERAS", 16, INK, bold=True, font=HEAD)
fit_picture(s, FIGS / "demo_zones.jpg", 6.25, 2.4, 6.25, 3.0)
text(s, 6.25, 5.5, 6.3, 0.7, f"3 zones of one CC BY 3.0 street clip (same cars pass A → B → C) + camD on another road · "
                             f"{sum(D['tracklets'].values())} tracklets · pseudo ground truth from full-frame tracking", 12, BODY_C)
text(s, 0.6, 6.55, 12.15, 0.4, "Benchmark = “Does the Re-ID method work?”    |    Videos = “Does the software workflow work?”",
     15, NAVY_BOX, bold=True, font=HEAD, align=PP_ALIGN.CENTER)

# ================================================================== 9 attributes + stage 1
a, ds = M["attributes"], M["description_search"]
s = content_slide("Results: Attributes & Description Search",
                  "Supervision doubles type accuracy; combined cues put the right vehicle in the top 5 for 84% of queries.",
    "First results. Colour and type on 830 VeRi test tracklets: zero-shot CLIP gets 67 percent on colour but only 38 "
    "on type, because it confuses sedan, hatchback and estate; a linear probe trained on VeRi labels reaches 73 and 79. "
    "Stage one description search: each cue alone is weak, but colour plus type plus a partial plate puts the right "
    "vehicle in the top five for 84 percent of queries — exactly what a human needs to confirm from a short list.")
box(s, 0.6, 1.7, 5.95, 4.95, GREY)
text(s, 0.85, 1.88, 5.5, 0.4, "ATTRIBUTE ACCURACY (%)", 15, INK, bold=True, font=HEAD)
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, ["Colour", "Type"],
          [("CLIP zero-shot", [a["color"]["zero_shot_acc"], a["type"]["zero_shot_acc"]]),
           ("Supervised probe", [a["color"]["linear_probe_acc"], a["type"]["linear_probe_acc"]])],
          0.75, 2.35, 5.65, 4.2, ["B9C3CC", TEAL])
box(s, 6.8, 1.7, 5.95, 4.95, GREY)
text(s, 7.05, 1.88, 5.5, 0.4, "STAGE 1 DESCRIPTION SEARCH (%)", 15, INK, bold=True, font=HEAD)
cats = list(ds)
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, ["colour + type", "partial plate", "colour + type\n+ partial plate"],
          [("Rank-1", [ds[c]["rank1"] for c in cats]), ("Rank-5", [ds[c]["rank5"] for c in cats])],
          6.95, 2.35, 5.65, 4.2, [NAVY_BOX, GREEN])

# ================================================================== 10 plate robustness
lv = ["clear", "partial", "blurred", "hidden"]
s = content_slide("Results: Plate Robustness",
                  "Plate-only search collapses as plates degrade; fused evidence holds up — the main hypothesis.",
    "This tests the main hypothesis. VeRi has no plate text, so each vehicle gets a synthetic plate that is degraded "
    "per sighting: clear, partial, blurred or hidden. Plate-only search falls from 100 to 3.6 percent mean average "
    "precision. Appearance alone is flat at 27. Fused evidence stays far above it at every level, and the transparent "
    "weighted fusion is the best fusion everywhere, ahead of the Random Forest. One honest twist: with no plate at "
    "all, the learned metric on its own is best, at 48, because colour and type are already inside the learned "
    "embedding and the attribute guesses add noise.")
meth = [("Plate only", "plate_sim", "E39B57"), ("Appearance only", "appearance only", "B9C3CC"),
        ("Learned metric", "learned metric", GREEN), ("Weighted fusion", "weighted fusion", TEAL),
        ("Random Forest", "random forest", NAVY_BOX)]
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, [l.capitalize() for l in lv],
          [(n, [M["reid"][l][k]["mAP"] for l in lv]) for n, k, _ in meth], 0.6, 1.6, 8.6, 4.75, [c for *_, c in meth])
callouts = [("100 → 3.6", "plate-only mAP, clear → hidden", N_ORANGE, PEACH),
            (f"{M['reid']['partial']['weighted fusion']['mAP']:.1f}", "weighted fusion mAP, partial plates", TEAL_D, MINT),
            (f"{M['reid']['blurred']['weighted fusion']['mAP']:.1f}", "weighted fusion mAP, blurred plates", TEAL_D, MINT)]
for i, (v, l, c, fill) in enumerate(callouts):
    y = 1.7 + i * 1.55
    box(s, 9.55, y, 3.2, 1.38, fill)
    text(s, 9.8, y + 0.15, 2.8, 0.6, v, 28, c, bold=True, font=HEAD)
    text(s, 9.8, y + 0.85, 2.8, 0.45, l, 12, BODY_C)
key_box(s, 0.6, 6.5, 12.15, 0.55, "HYPOTHESIS SUPPORTED: MULTI-EVIDENCE RETRIEVAL DEGRADES GRACEFULLY WHEN THE PLATE FAILS", 14)

# ================================================================== 11 ablation
hid = M["reid"]["hidden"]
s = content_slide("Results: Which Cues Matter?",
                  "With plates hidden, supervised metric learning is the biggest single gain.",
    "With plates hidden, which cues matter? The generic ResNet and CLIP embeddings reach about 60 percent rank-one. "
    "Learning a projection from just 150 labelled VeRi vehicles lifts that to 77 percent and nearly doubles mean "
    "average precision, from 27 to 48. Colour, type and distinctive cues are far too coarse to rank on their own. The "
    "Random Forest puts almost half its importance on the learned metric.")
order = [("Learned metric", "learned metric"), ("Weighted fusion", "weighted fusion"), ("Random Forest", "random forest"),
         ("ResNet appearance", "appearance only"), ("CLIP cosine", "clip_cos"), ("HSV histogram", "color_hist"),
         ("Distinctive cues", "cue_sim"), ("Type agreement", "type_agree"), ("Colour agreement", "color_agree")]
add_chart(s, XL_CHART_TYPE.BAR_CLUSTERED, [n for n, _ in order][::-1],
          [("Rank-1", [hid[k]["rank1"] for _, k in order][::-1]), ("mAP", [hid[k]["mAP"] for _, k in order][::-1])],
          0.6, 1.55, 8.6, 5.4, [NAVY_BOX, TEAL])
imp = sorted(M["rf_feature_importance"].items(), key=lambda kv: -kv[1])[:4]
box(s, 9.55, 1.7, 3.2, 3.15, GREY)
text(s, 9.78, 1.88, 2.8, 0.4, "RANDOM FOREST IMPORTANCE", 12, INK, bold=True, font=HEAD)
for i, (f, v) in enumerate(imp):
    y = 2.35 + i * 0.62
    text(s, 9.78, y, 2.8, 0.3, f.replace("_", " "), 12, BODY_C)
    box(s, 9.78, y + 0.3, 2.2 * v / imp[0][1], 0.2, TEAL, line=None, shape=MSO_SHAPE.RECTANGLE)
    text(s, 9.85 + 2.2 * v / imp[0][1], y + 0.24, 0.6, 0.3, f"{v:.2f}", 11, INK, bold=True)
box(s, 9.55, 5.05, 3.2, 1.8, MINT)
text(s, 9.78, 5.2, 2.8, 0.6, f"{hid['appearance only']['mAP']:.0f} → {hid['learned metric']['mAP']:.0f}", 28, TEAL_D, bold=True, font=HEAD)
text(s, 9.78, 5.9, 2.8, 0.8, "Re-ID mAP after learning a metric from 150 vehicles", 12, BODY_C)

# ================================================================== 12 demo footage
rfm, app = D["methods"]["random forest"], D["methods"]["appearance only"]
s = content_slide("Results: Multi-Camera Demo Footage",
                  "On real video the fused matcher traces vehicles camera to camera, with the user confirming each hop.",
    "Back to real video. On the four demo cameras I measured re-identification against a reference: the uncropped "
    "clip is tracked once and every camera tracklet is mapped back onto it, so these numbers are pseudo ground truth. "
    "Here fusion beats appearance alone and the learned metric alone, because colour and type reject look-alike cars. "
    "The automatic route suggestion is conservative: when it suggests a camera it is right 70 percent of the time. "
    "With one click per camera the right car is among the three shown for about two thirds of hops, and the "
    "screenshot shows the red Citroën confirmed in cameras A, B and C, in time order.")
stats = [(f"{rfm['Rank-1']:.0f}%", f"Rank-1, fused (appearance only {app['Rank-1']:.0f}%)", BLUE, N_TEAL),
         (f"{rfm['camera_hit@3']:.0f}%", "right car among the 3 shown per camera", MINT, TEAL_D),
         (f"{rfm['route_precision']:.0f}%", "of suggested route steps are correct", LGREEN, GREEN_D),
         (f"{D['tracking']['clean_tracklets_%']:.0f}%", "of tracklets are clean (no ID switch)", PEACH, N_ORANGE)]
for i, (v, l, fill, c) in enumerate(stats):
    y = 1.7 + i * 1.22
    box(s, 0.6, y, 3.6, 1.05, fill)
    text(s, 0.82, y + 0.12, 3.2, 0.5, v, 26, c, bold=True, font=HEAD)
    text(s, 0.82, y + 0.65, 3.2, 0.35, l, 12, BODY_C)
fit_picture(s, SHOTS / "path.png", 4.55, 1.7, 8.2, 5.15)

# ================================================================== 13 SOM
som = M["som"]
s = content_slide("Results: Unsupervised SOM",
                  "The map organises vehicles by type and colour — useful for exploration, not as a Re-ID filter.",
    "The Self-Organising Map is trained without labels. Its nodes are fairly pure for type and colour but not for "
    "identity. Used as a candidate pre-filter it removes 70 to 94 percent of candidates but drops too many true "
    "matches, so accuracy goes down. That is a useful negative result: the SOM is good for exploring the footage, "
    "not for filtering re-identification candidates at this scale.")
fit_picture(s, RES / "som_umatrix.png", 0.6, 1.6, 5.2, 5.3)
box(s, 6.2, 1.7, 6.55, 2.2, GREY)
text(s, 6.45, 1.88, 6, 0.4, "NODE PURITY (10×10 MAP)", 14, INK, bold=True, font=HEAD)
for i, (n, v) in enumerate((("type", som["purity_type"]), ("colour", som["purity_color"]), ("vehicle ID", som["purity_vehicle_id"]))):
    y = 2.4 + i * 0.48
    text(s, 6.45, y, 1.4, 0.35, n, 13, BODY_C)
    box(s, 7.9, y + 0.05, 4.0 * v, 0.26, TEAL if v > 0.5 else "E39B57", line=None, shape=MSO_SHAPE.RECTANGLE)
    text(s, 8.0 + 4.0 * v, y, 0.7, 0.35, f"{v:.2f}", 13, INK, bold=True)
pf = som["prefilter"]
rows = [("SOM radius", "candidates kept", "true matches kept", "mAP")] + [
    (r.split("_")[1], f"{v['candidates_kept_%']:.0f}%", f"{v['true_match_recall_%']:.0f}%", f"{v['mAP']:.1f}") for r, v in pf.items()] + [
    ("no filter", "100%", "100%", f"{hid['random forest']['mAP']:.1f}")]
tbl = s.shapes.add_table(len(rows), 4, Inches(6.2), Inches(4.15), Inches(6.55), Inches(0.42 * len(rows))).table
for r_, row in enumerate(rows):
    for c_, v in enumerate(row):
        cell = tbl.cell(r_, c_)
        cell.text = v
        run = cell.text_frame.paragraphs[0].runs[0]
        run.font.size, run.font.name, run.font.bold = Pt(13), BODY, r_ == 0 or r_ == len(rows) - 1
        run.font.color.rgb = rgb("FFFFFF" if r_ == 0 else INK)
        cell.fill.solid()
        cell.fill.fore_color.rgb = rgb(NAVY_BOX if r_ == 0 else (MINT if r_ == len(rows) - 1 else ("FFFFFF" if r_ % 2 else GREY)))

# ================================================================== 14 lessons
s = content_slide("Lessons Learned",
                  "Two pitfalls found — and fixed — while evaluating the learned components.",
    "Two lessons. First, a stacking leak: the forest was trained on colour and type probabilities from a probe "
    "fitted on the same vehicles, so they looked almost perfect and the forest over-trusted them; on new vehicles it "
    "ranked worse than appearance alone. Out-of-fold features grouped by vehicle fixed it, and I applied the same rule "
    "to the learned metric. Second, the forest learned splits where higher similarity lowered the score; monotonic "
    "constraints fixed that. That second choice was informed by test queries, so the forest-versus-fusion comparison "
    "is indicative, and a validation split is the proper next step.")
pit = [("STACKING LEAK", "Colour/type features for the Random Forest came from a probe fitted on the same vehicles — near-perfect, so over-trusted.",
        "Out-of-fold probabilities and LDA projections (GroupKFold by vehicle)", "Rank-1, plates hidden: 38 → 56", PEACH, N_ORANGE),
       ("NON-MONOTONIC SPLITS", "Under large viewpoint changes, a higher similarity could lower the match score.",
        "Monotonic constraints on every similarity feature", "mAP, plates hidden: 21 → 30", LAV, N_PURPLE)]
for i, (h, prob, fix, gain, fill, nc) in enumerate(pit):
    x = 0.6 + i * 6.2
    box(s, x, 1.7, 5.95, 4.0, fill)
    text(s, x + 0.25, 1.9, 5.5, 0.45, f"{i + 1:02d}", 20, nc, bold=True, font=HEAD)
    text(s, x + 0.25, 2.45, 5.5, 0.5, h, 19, INK, bold=True, font=HEAD)
    text(s, x + 0.25, 3.1, 5.5, 2.5, [[("Problem  ", {"bold": True, "color": nc}), (prob, {})], "",
                                      [("Fix  ", {"bold": True, "color": TEAL_D}), (fix, {})]], 15, spacing=4)
    key_box(s, x, 5.9, 5.95, 0.8, gain, 18)

# ================================================================== 15 demo
s = content_slide("Live Demo",
                  "Describe → search → confirm → re-identify → trace, in the Streamlit app.",
    "Now the app. After the admin signs in, the quick demo loads the four cameras. I describe the target as a red "
    "sedan; the red Citroën in camera A is ranked first and I confirm it. In step three the route view already "
    "suggests camera B; I confirm it, camera C is re-scored against both views, and I confirm the sighting there — "
    "giving the full route from camera A to B to C in time order, with the evidence for every step.")
for i, (f, cap) in enumerate((("search.png", "Stage 1 · “red + sedan” → ranked candidates → confirm"),
                              ("path.png", "Stage 2 · route confirmed camA → camB → camC"))):
    x = 0.6 + i * 6.2
    box(s, x, 1.7, 5.95, 4.45, GREY)
    fit_picture(s, SHOTS / f, x + 0.15, 1.85, 5.65, 4.15)
    text(s, x, 6.3, 5.95, 0.35, cap, 14, INK, bold=True, font=HEAD, align=PP_ALIGN.CENTER)

# ================================================================== 16 limitations
s = content_slide("Limitations & Next Steps",
                  "A focused proof of concept — the clearest next steps follow from the results.",
    "Limitations. The learned metric is linear and trained on only 150 vehicles; using all VeRi training identities "
    "or fine-tuning the backbone with a triplet loss is the clearest gain. Plates in the benchmark are synthetic and "
    "OCR runs on whole-vehicle crops. The forest optimises pair classification rather than ranking. The demo cameras "
    "are zones of one recording, not separate physical cameras. And the pipeline works frame by frame, so live "
    "camera streams are a small change.")
text(s, 0.75, 1.65, 5.5, 0.5, "LIMITATIONS", 20, "D45F5F", bold=True, font=HEAD)
text(s, 7.05, 1.65, 5.5, 0.5, "NEXT", 20, GREEN, bold=True, font=HEAD)
lim = [("Linear metric, 150 training vehicles", "all 576 VeRi identities · triplet-loss fine-tuning"),
       ("Synthetic plates; OCR on whole crops", "plate detector + real plate data"),
       ("RF optimises pair classification", "learning-to-rank · validation split for model choice"),
       ("Demo cameras = zones of one recording", "separate physical cameras (e.g. CityFlow) · travel-time priors"),
       ("Recorded videos only", "live RTSP camera streams")]
for i, (l, n) in enumerate(lim):
    y = 2.3 + i * 0.82
    text(s, 0.75, y, 5.6, 0.6, "×  " + l, 17, BODY_C, anchor=MSO_ANCHOR.MIDDLE)
    b = box(s, 7.05, y, 5.7, 0.6, "EFF7F6")
    label(b, n, 14, INK, bold=False, align=PP_ALIGN.LEFT)
key_box(s, 2.3, 6.55, 8.75, 0.5, "MVP: recorded-video proof of concept  →  future extension: live camera streams", 14)

# ================================================================== 17 conclusion + thank you
s = dark_slide(ART / "bg_end.png",
    "To conclude: V-Trace starts from incomplete information, retrieves likely candidates, keeps a human confirmation "
    "step, and then re-identifies and traces the vehicle across cameras using several complementary kinds of evidence, "
    "with the user confirming each hop. Plate-only search collapses when plates degrade, while fused evidence holds up. "
    "Description search finds the right vehicle in the top five for 84 percent of queries, and learning a metric from "
    "150 vehicles nearly doubles re-identification mAP. Thank you — I'm happy to take questions.")
picture(s, LOGO_DARK, 0.6, 0.45, w=4.2)
concl = [(f"{ds['colour + type + partial plate']['rank5']:.0f}%", "right vehicle in the top 5 from colour + type + partial plate"),
         ("100 → 3.6", "plate-only mAP as plates degrade; fusion stays far above appearance"),
         (f"{hid['appearance only']['mAP']:.0f} → {hid['learned metric']['mAP']:.0f}", "Re-ID mAP, plates hidden, with a learned metric")]
for i, (v, l) in enumerate(concl):
    x = 0.75 + i * 3.9
    text(s, x, 2.0, 3.6, 0.7, v, 34, GREEN if i != 1 else "E39B57", bold=True, font=HEAD)
    text(s, x, 2.8, 3.4, 0.8, l, 14, "D9E2E8")
text(s, 0, 3.75, 13.333, 1.2, "Thank you!", 72, TEAL, bold=True, font=HEAD, align=PP_ALIGN.CENTER)
text(s, 0.55, 6.25, 12.25, 1.0,
     "In the preparation of this project, AI-based tools including Claude, ChatGPT and Gemini were used in a supporting "
     "capacity to assist with tasks such as drafting and refining text, organising content, implementation and general "
     "research support. All ideas, analysis, technical design decisions and conclusions are the work of the project team.",
     11, "FFFFFF", bold=True)

OUT.parent.mkdir(exist_ok=True)
prs.save(OUT)
print(f"saved {OUT} ({NO[0]} slides)")
