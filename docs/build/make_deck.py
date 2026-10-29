"""Build the final presentation deck (deliverables/V-Trace_Final_Presentation.pptx).

All numbers are read from results/metrics.json (VeRi-776) and results/demo_eval.json (demo cameras), and the
screenshots from docs/screenshots/, so re-running the experiments and this script keeps the deck in sync.
Speaker notes hold the script for the recorded 10-15 minute video presentation.

    python docs/build/make_deck.py
"""
import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
RES, SHOTS, FIGS = ROOT / "results", ROOT / "docs" / "screenshots", ROOT / "docs" / "figures"
OUT = ROOT / "deliverables" / "V-Trace_Final_Presentation.pptx"
LOGO = ROOT / "assets" / "nus_iss_logo.png"

NAVY, SLATE, TEAL, TEAL_D = "111820", "34454D", "12A7A1", "0E8782"
GREEN, MINT, MIST, LIGHT = "65C95A", "B8E9E6", "EAF7F6", "F4F7F8"
GREY, LINE, WHITE, AMBER = "60727C", "D3DEE2", "FFFFFF", "F2A33A"
FONT = "Calibri"

M = json.loads((RES / "metrics.json").read_text())
D = json.loads((RES / "demo_eval.json").read_text()) if (RES / "demo_eval.json").exists() else None


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = 13.333, 7.5


# ------------------------------------------------------------------ primitives
def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = rgb(color)


def text(slide, x, y, w, h, runs, size=16, color=NAVY, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         name=None, spacing=6):
    """runs: str, or list of paragraphs; a paragraph is str or list of (text, {opts}) runs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(spacing)
        bullet = False
        if isinstance(para, dict):
            bullet, para = para.get("bullet", False), para["text"]
        for j, (txt, o) in enumerate([(para, {})] if isinstance(para, str) else para):
            r = p.add_run()
            r.text = ("•  " if bullet and j == 0 else "") + txt
            r.font.name = FONT
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.italic = o.get("italic", False)
            r.font.color.rgb = rgb(o.get("color", color))
    return tb


def box(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08, name=None, shadow=False):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    if not shadow:
        s.shadow.inherit = False
    if name:
        s.name = name
    s.text_frame.margin_left = s.text_frame.margin_right = Inches(0.12)
    return s


def label(shape, txt, size=14, color=WHITE, bold=True, align=PP_ALIGN.CENTER):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    lines = txt.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        r.font.name, r.font.size, r.font.bold = FONT, Pt(size if i == 0 else size - 3), bold if i == 0 else False
        r.font.color.rgb = rgb(color)


def circle_num(slide, x, y, d, n, fill=TEAL, color=WHITE, size=16):
    c = box(slide, x, y, d, d, fill, shape=MSO_SHAPE.OVAL)
    label(c, str(n), size=size, color=color)
    return c


def arrow(slide, x1, y1, x2, y2, color=GREY, width=2):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"})
    ln.append(tail)
    return c


def picture(slide, path, x, y, w=None, h=None, name=None):
    if not Path(path).exists():
        ph = box(slide, x, y, w or 4, h or 3, MIST, line=LINE)
        label(ph, f"[missing image]\n{Path(path).name}", 12, GREY, bold=False)
        return ph
    p = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    if name:
        p.name = name
    return p


def fit_picture(slide, path, x, y, w, h):
    """Largest picture that fits the w x h box, centred."""
    from PIL import Image
    if not Path(path).exists():
        return picture(slide, path, x, y, w, h)
    iw, ih = Image.open(path).size
    s = min(w / iw, h / ih)
    return picture(slide, path, x + (w - iw * s) / 2, y + (h - ih * s) / 2, iw * s, ih * s)


SLIDE_NO = [0]


def content_slide(title, kicker=None, notes=""):
    s = prs.slides.add_slide(BLANK)
    SLIDE_NO[0] += 1
    bg(s, WHITE)
    if kicker:
        text(s, 0.6, 0.38, 9, 0.3, kicker.upper(), 12, TEAL_D, bold=True, name="Kicker")
    text(s, 0.6, 0.66, 10.4, 0.9, title, 30, NAVY, bold=True, name="Title")
    picture(s, LOGO, 11.35, 0.32, w=1.45, name="Logo")
    text(s, 0.6, 7.05, 6, 0.3, "V-Trace · Group 21 · Gurneet Kaur Bhuller", 10, GREY, name="Footer")
    text(s, 12.2, 7.05, 0.55, 0.3, str(SLIDE_NO[0]), 10, GREY, align=PP_ALIGN.RIGHT, name="Slide number")
    s.notes_slide.notes_text_frame.text = notes
    return s


def dark_slide(notes=""):
    s = prs.slides.add_slide(BLANK)
    SLIDE_NO[0] += 1
    bg(s, NAVY)
    s.notes_slide.notes_text_frame.text = notes
    return s


def chart_style(chart, colors, legend=True, number_format='0', size=12, labels=True):
    chart.font.name, chart.font.size = FONT, Pt(size)
    chart.font.color.rgb = rgb(SLATE)
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)
    for s, c in zip(chart.plots[0].series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = rgb(c)
    plot = chart.plots[0]
    if labels:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format, dl.number_format_is_linked = number_format, False
        dl.font.size, dl.font.color.rgb = Pt(size - 1), rgb(SLATE)
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
    va = chart.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb("E3EAED")
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(size - 1)
    ca = chart.category_axis
    ca.format.line.color.rgb = rgb(LINE)
    ca.tick_labels.font.size = Pt(size)


def add_chart(slide, kind, cats, series, x, y, w, h, colors, **kw):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, [round(v, 1) for v in vals])
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    chart = gf.chart
    chart_style(chart, colors, **kw)
    return chart


DEMO_ROUTE = ["camA_west#481", "camB_centre#156", "camC_east#294"]   # the scripted demo car (DEMO_GUIDE.md)


def pick_demo():
    """The demo car's route as [(uid, score, start_s, end_s)], with times from the demo bundle."""
    import joblib
    bundle = ROOT / "demo_bundle" / "tracklets.joblib"
    if not bundle.exists():
        return None
    ts = {t["uid"]: t for t in joblib.load(bundle)}
    return {"path": [(u, 1.0, ts[u]["start_t"], ts[u]["end_t"]) for u in DEMO_ROUTE if u in ts]}


def crop_for(uid):
    video, tid = uid.split("#")
    p = ROOT / "data" / "index" / "crops" / video / f"{tid}_0.jpg"
    return p


# ================================================================== slides
# 1 ---- title
s = dark_slide(
    "Hello, I'm Gurneet Kaur Bhuller from Group 21. This is V-Trace, a multi-attribute vehicle re-identification "
    "system. In the next twelve minutes I'll explain the problem, how V-Trace works, how I evaluated it on the "
    "VeRi-776 benchmark and on multi-camera demo footage, what I learned, and then show the working Streamlit app.")
card = box(s, 0.7, 0.6, 2.75, 0.9, WHITE, radius=0.18)
picture(s, LOGO, 0.78, 0.66, w=2.6)
text(s, 0.7, 2.05, 7.5, 1.1, "V-Trace", 66, WHITE, bold=True)
text(s, 0.72, 3.15, 7.6, 0.6, "Multi-Attribute Vehicle Re-Identification System", 24, MINT)
text(s, 0.72, 3.95, 7.6, 0.4, "DESCRIBE  →  SEARCH  →  CONFIRM  →  RE-IDENTIFY  →  TRACE", 16, GREEN, bold=True)
text(s, 0.72, 5.55, 7.6, 1.1, ["Final presentation · Gurneet Kaur Bhuller (A0354164E) · Group 21",
                               "Graduate Certificate in Pattern Recognition Systems · Practice Module"], 14, LINE)
demo = pick_demo()
if demo:                                          # the traced vehicle, camera by camera
    steps = demo["path"][:3]
    for k, (uid, score, t0, t1) in enumerate(steps):
        y = 1.0 + k * 1.95
        c = box(s, 9.0, y, 3.55, 1.6, "1B2830", line=SLATE, radius=0.1)
        fit_picture(s, crop_for(uid), 9.12, y + 0.12, 1.7, 1.36)
        text(s, 10.95, y + 0.22, 1.5, 1.2, [[(uid.split("#")[0], {"bold": True, "color": WHITE, "size": 13})],
                                           [(f"{t0:.1f}–{t1:.1f} s", {"color": MINT, "size": 12})]], 12)
        if k < len(steps) - 1:
            arrow(s, 10.78, y + 1.62, 10.78, y + 1.93, TEAL, 2.5)

# 2 ---- problem
s = content_slide("The plate is the best identifier — and it's often unreadable",
                  "The problem",
                  "Vehicle re-identification means deciding whether a vehicle seen by one camera is likely the same "
                  "vehicle seen by another. A licence plate is the strongest single clue, but on real CCTV footage it "
                  "is often too small, blurred, occluded, badly lit or facing away. Investigators also rarely start "
                  "with a clean image; they start with a partial description from a witness. On the VeRi-776 benchmark "
                  "a plate-only search drops from perfect to 3.6 percent mean average precision once the plate is hidden. "
                  "So a useful system must combine whatever evidence exists, and keep a human in the loop.")
reasons = ["Too small at distance", "Motion blur", "Occluded or dirty", "Glare or night", "Facing away from camera"]
text(s, 0.6, 1.85, 5.6, 0.4, "Why plates fail on CCTV", 18, NAVY, bold=True)
for i, r in enumerate(reasons):
    y = 2.4 + i * 0.68
    circle_num(s, 0.6, y, 0.46, i + 1, size=14)
    text(s, 1.25, y + 0.06, 4.8, 0.4, r, 17, SLATE, anchor=MSO_ANCHOR.MIDDLE)
q = box(s, 0.6, 5.95, 5.6, 0.85, MIST, radius=0.12)
label(q, "What investigators actually have:  “white SUV, plate starts SGX12…, dent on the rear door”",
      14, NAVY, bold=False, align=PP_ALIGN.LEFT)
plate = M["reid"]
big = box(s, 6.9, 1.85, 5.85, 4.95, NAVY, radius=0.06)
text(s, 7.3, 2.15, 5.2, 0.4, "Plate-only retrieval on VeRi-776 (mAP)", 16, MINT, bold=True)
for k, (lvl, lab) in enumerate([("clear", "clear"), ("partial", "partial"), ("blurred", "blurred"), ("hidden", "hidden")]):
    v = plate[lvl]["plate_sim"]["mAP"]
    y = 2.75 + k * 0.95
    text(s, 7.3, y, 1.5, 0.6, lab, 16, LINE, anchor=MSO_ANCHOR.MIDDLE)
    barw = 2.55 * v / 100
    if barw > 0.05:
        box(s, 8.75, y + 0.12, barw, 0.4, TEAL if v > 50 else AMBER, shape=MSO_SHAPE.RECTANGLE)
    text(s, 8.85 + barw, y, 1.2, 0.6, f"{v:.1f}%", 18, WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
text(s, 7.3, 6.55 - 0.25, 5.3, 0.4, "→ never depend on the plate alone", 15, GREEN, bold=True)

# 3 ---- approach
s = content_slide("Describe → Search → Confirm → Re-identify → Trace",
                  "The approach",
                  "V-Trace turns this into a two-stage, human-in-the-loop workflow. First the user describes the "
                  "vehicle with whatever they know: colour, type, a full or partial plate with question marks for "
                  "unknown characters, and distinctive cues like a roof rack or a decal. Stage one returns ranked "
                  "candidates. The user confirms the right one — that human step matters, because the system never "
                  "claims an identity on its own. The confirmed tracklet then becomes a visual query: stage two finds "
                  "the same vehicle in the other cameras, and the route view suggests where it went next; the user "
                  "confirms the sighting in each camera with one click, so the route is traced camera by camera.")
steps = [("Describe", "colour · type · partial plate (SGX1?3?) · cues · free text"),
         ("Search", "Stage 1 ranks every tracked vehicle by the fields given"),
         ("Confirm", "a human picks the right candidate: no automatic identity claims"),
         ("Re-identify", "Stage 2 matches the confirmed vehicle in the other cameras"),
         ("Trace", "suggested route + one-click confirmation in each camera")]
for i, (h, d) in enumerate(steps):
    x = 0.6 + i * 2.5
    c = box(s, x, 2.1, 2.2, 3.3, MIST if i != 2 else NAVY, radius=0.08)
    circle_num(s, x + 0.2, 2.3, 0.6, i + 1, fill=TEAL if i != 2 else GREEN, size=18)
    text(s, x + 0.2, 3.1, 1.85, 0.5, h, 20, NAVY if i != 2 else WHITE, bold=True)
    text(s, x + 0.2, 3.65, 1.85, 1.6, d, 14, SLATE if i != 2 else LINE)
    if i < 4:
        arrow(s, x + 2.22, 3.75, x + 2.48, 3.75, TEAL, 2.5)
r = box(s, 0.6, 5.8, 12.15, 0.85, NAVY, radius=0.14)
label(r, "Output is always a ranked list with frames and timestamps for human review — never an identity claim", 16, WHITE)

# 4 ---- architecture
s = content_slide("System architecture", "System design",
                  "Here is the pipeline. Each uploaded video is one camera. A pretrained YOLO11 detector finds cars, "
                  "buses, trucks and motorcycles, and ByteTrack links the detections into tracks. Each track becomes a "
                  "tracklet with four good-quality crops spread over time, plus an evidence frame. From the crops V-Trace "
                  "computes the descriptors and stores everything in a vehicle index. Only the videos processed in the "
                  "current session are searched. The lower row is the user's side: the description goes into stage one, "
                  "the human confirms, stage two re-identifies, and the path is traced. Everything is in a Streamlit app.")
top = [("Camera videos", "one file = one camera"), ("YOLO11n", "vehicle detection"), ("ByteTrack", "within-video tracking"),
       ("Tracklets", "4 crops + evidence frame"), ("Descriptors", "complementary cues + learned metric"), ("Vehicle index", "this session's videos")]
for i, (h, d) in enumerate(top):
    x = 0.6 + i * 2.06
    c = box(s, x, 2.0, 1.8, 1.25, TEAL if i in (1, 2, 4) else SLATE, radius=0.12)
    label(c, f"{h}\n{d}", 15)
    if i < 5:
        arrow(s, x + 1.82, 2.62, x + 2.04, 2.62, GREY)
bottom = [("Description", "colour · type · plate · cues"), ("Stage 1 search", "weighted multi-field score"),
          ("Human confirm", "pick the right candidate"), ("Stage 2 Re-ID", "learned metric + fusion"),
          ("Route tracing", "suggest + confirm per camera")]
for i, (h, d) in enumerate(bottom):
    x = 0.6 + i * 2.48
    c = box(s, x, 4.35, 2.2, 1.25, NAVY if i != 2 else GREEN, radius=0.12)
    label(c, f"{h}\n{d}", 15, WHITE if i != 2 else NAVY)
    if i < 4:
        arrow(s, x + 2.22, 4.97, x + 2.46, 4.97, GREY)
arrow(s, 11.83, 3.27, 8.5, 4.33, TEAL, 2)
text(s, 0.6, 5.95, 12, 0.8, [[("Streamlit app: ", {"bold": True, "color": NAVY}),
                              ("admin sign-in · upload & process · describe & search · confirm & re-identify · track review · SOM · evaluation. "
                               "Optional SOM pre-filter between the index and Stage 2.", {"color": SLATE})]], 15)

# 5 ---- descriptors
s = content_slide("Complementary descriptors per tracklet", "Vehicle representation",
                  "No single cue is reliable, so each tracklet gets several. ResNet-50 and CLIP embeddings describe its "
                  "appearance, and a projection learned from VeRi vehicle identities with linear discriminant analysis "
                  "turns them into the main re-identification cue: it keeps what separates two cars and suppresses "
                  "viewpoint and lighting. CLIP is also the basis for colour, type and distinctive-cue scores. Colour and type come from a supervised linear probe trained on VeRi labels. An HSV colour "
                  "histogram is a hand-crafted colour cue. EasyOCR reads plates only when confident, and plate matching "
                  "accepts question marks as wildcards. A missing cue lowers confidence but never blocks a search.")
cards = [("Learned Re-ID metric", "PCA + LDA on [ResNet | CLIP]", "trained on VeRi identities: main Re-ID cue"),
         ("Appearance", "ResNet-50 + CLIP ViT-B/32", "generic embeddings; CLIP also drives attributes"),
         ("Colour & type", "linear probe on CLIP (VeRi labels)", "10 colours · 9 types; zero-shot fallback"),
         ("HSV histogram", "16×4×4 bins, hand-crafted", "illumination-tolerant colour similarity"),
         ("Licence plate", "EasyOCR + wildcard Levenshtein", "strong evidence only when read"),
         ("Distinctive cues", "CLIP text–image similarity", "roof rack · spoiler · dent · decal · roof cargo")]
for i, (h, m, r) in enumerate(cards):
    x, y = 0.6 + (i % 3) * 4.1, 1.95 + (i // 3) * 2.45
    c = box(s, x, y, 3.85, 2.15, MIST, radius=0.08)
    circle_num(s, x + 0.25, y + 0.25, 0.55, i + 1, size=16)
    text(s, x + 0.95, y + 0.3, 2.8, 0.45, h, 19, NAVY, bold=True)
    text(s, x + 0.25, y + 1.0, 3.4, 1.1, [[(m, {"bold": True, "color": TEAL_D, "size": 14})], [(r, {"color": SLATE, "size": 14})]], 14)

# 6 ---- matching + path
s = content_slide("Stage 2: pairwise evidence, four scorers, route tracing", "Re-identification",
                  "For the confirmed vehicle and every candidate in another camera, V-Trace builds an eleven-number "
                  "evidence vector: the learned-metric similarity, two embedding similarities, colour histogram, colour and type agreement, plate similarity and "
                  "whether both plates were read, cue agreement, and track quality and consistency. Four scorers are "
                  "compared: appearance only, the learned metric, a transparent weighted fusion, and a Random Forest with "
                  "monotonic constraints. Route tracing suggests one sighting per camera, but only when it clearly beats "
                  "that camera's runner-up, and shows the top three per camera so the user confirms each hop. Every "
                  "confirmed sighting is added to the query set, so the middle camera bridges a far, small view and a "
                  "near, large view of the same car. A time window rejects impossible jumps.")
feats = ["learned-metric cosine", "ResNet cosine", "CLIP cosine", "HSV histogram", "colour agreement", "type agreement", "plate similarity",
         "both plates read", "cue agreement", "track quality / consistency"]
text(s, 0.6, 1.85, 4, 0.4, "11-feature evidence vector", 18, NAVY, bold=True)
for i, f in enumerate(feats):
    x, y = 0.6 + (i % 2) * 2.35, 2.4 + (i // 2) * 0.62
    c = box(s, x, y, 2.2, 0.5, MIST, radius=0.3)
    label(c, f, 13, NAVY, bold=False)
text(s, 0.6, 5.65, 4.6, 1.1, [[("Scorers: ", {"bold": True, "color": NAVY}),
                               ("appearance only · learned metric · weighted fusion · Random Forest (monotonic)", {"color": SLATE})]], 15)
pg = box(s, 5.65, 1.85, 7.1, 4.95, NAVY, radius=0.05)
text(s, 6.0, 2.1, 6.4, 0.4, "Route tracing", 18, MINT, bold=True)
cams = [("camA", "far · small"), ("camB", "mid"), ("camC", "near · large")]
for i, (c_, d_) in enumerate(cams):
    x = 6.1 + i * 2.2
    c = box(s, x, 2.85, 1.75, 1.1, TEAL if i == 0 else SLATE, radius=0.12)
    label(c, f"{c_}\n{d_}", 16)
    if i < 2:
        arrow(s, x + 1.77, 3.4, x + 2.18, 3.4, GREEN, 2.5)
text(s, 6.0, 4.3, 6.5, 2.4, [
    {"bullet": True, "text": [("Score each camera's tracklets against ", {}), ("all", {"bold": True}), (" known views of the car", {})]},
    {"bullet": True, "text": [("Suggest a camera only if its best clearly beats its runner-up", {})]},
    {"bullet": True, "text": [("Show the top 3 per camera: the user confirms each hop in one click", {})]},
    {"bullet": True, "text": [("Each confirmation re-scores the rest; a time window rejects impossible jumps", {})]}], 15, LINE)

# 7 ---- technique groups
s = content_slide("All four technique groups are integrated", "Practice module requirements",
                  "The module asks for at least three of four technique groups; V-Trace integrates all four. Supervised "
                  "learning: the Random Forest matcher and the colour-type probe. Unsupervised: a Self-Organising Map over "
                  "appearance embeddings. Deep learning: YOLO11, ResNet-50, CLIP and EasyOCR. Hybrid and ensemble: the "
                  "Random Forest fusing ten evidence features, compared against weighted fusion and single cues. "
                  "Intelligent sensing and sense-making: the whole chain from raw video to a traced route.")
groups = [("Supervised / unsupervised learning", "LDA metric learning on vehicle identities · Random Forest matcher · colour/type probe · Self-Organising Map"),
          ("Machine / deep learning", "YOLO11n detector · ResNet-50 embeddings · CLIP vision-language model · EasyOCR"),
          ("Hybrid / ensemble", "Random Forest and weighted fusion over 11 evidence features vs single cues (ablation)"),
          ("Intelligent sensing / sense-making", "video → detections → tracks → tracklets → descriptors → candidates → confirmed target → route")]
for i, (h, d) in enumerate(groups):
    x, y = 0.6 + (i % 2) * 6.15, 1.95 + (i // 2) * 2.45
    c = box(s, x, y, 5.9, 2.15, MIST if i % 3 else NAVY, radius=0.08)
    dark = not (i % 3)
    circle_num(s, x + 0.3, y + 0.3, 0.6, i + 1, fill=GREEN if dark else TEAL, color=NAVY if dark else WHITE, size=18)
    text(s, x + 1.1, y + 0.35, 4.6, 0.5, h, 19, WHITE if dark else NAVY, bold=True)
    text(s, x + 1.1, y + 0.95, 4.6, 1.1, d, 15, LINE if dark else SLATE)

# 8 ---- data
st_ = M["setup"]
s = content_slide("Evaluation data: benchmark + multi-camera demo", "Data & protocol",
                  "Two kinds of data. For numbers I use VeRi-776: about fifty thousand images of 776 vehicles from 20 "
                  "cameras, with colour and type labels. Images of one vehicle passing one camera are grouped into "
                  "tracklets, the same unit my video pipeline produces. Train and test vehicles are disjoint: 150 "
                  "training and 100 test vehicles. For the end-to-end demo I use an openly licensed 1080p Ljubljana "
                  "street recording, cut into three camera zones along the road with different exposure and colour, so "
                  "the same cars really do pass camera A, then B, then C. A fourth camera on another road is a distractor.")
stats = [("776", "vehicles · 20 cameras\nVeRi-776"), (f"{st_['train_ids']} / {st_['test_ids']}", "train / test vehicles\n(identity-disjoint)"),
         (f"{st_['n_train_tracklets']:,} / {st_['n_test_tracklets']:,}", "train / test tracklets"), (f"{st_['max_queries']}", "Re-ID queries")]
for i, (v, l) in enumerate(stats):
    y = 1.9 + i * 1.22
    text(s, 0.6, y, 2.6, 0.6, v, 30, TEAL_D, bold=True)
    text(s, 3.15, y + 0.05, 2.6, 0.9, l, 13, SLATE)
fit_picture(s, FIGS / "demo_zones.jpg", 6.1, 1.85, 6.65, 3.75)
dt = D["tracklets"] if D else {}
text(s, 6.1, 5.75, 6.65, 1.0, [[("Demo cameras: ", {"bold": True, "color": NAVY}),
                                ("3 zones of one CC BY 3.0 street clip (45 s) + camD on another road as a distractor"
                                 + (f" · {sum(dt.values())} tracklets" if dt else ""), {"color": SLATE})]], 14)

# 9 ---- attributes + stage 1
s = content_slide("Supervised attributes and combined cues work best", "Results · VeRi-776",
                  "On the left, colour and type recognition on 830 test tracklets. Zero-shot CLIP gets 67 percent on "
                  "colour but only 38 percent on type, because it confuses sedan, hatchback and estate. A linear probe "
                  "trained on VeRi labels reaches 73 and 79 percent. On the right, stage one description search. Each cue "
                  "alone is weak, but colour plus type plus a partial plate puts the right vehicle in the top five for "
                  "84 percent of queries — exactly what a human needs to confirm from a short list.")
a = M["attributes"]
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, ["Colour", "Type"],
          [("CLIP zero-shot", [a["color"]["zero_shot_acc"], a["type"]["zero_shot_acc"]]),
           ("Supervised probe", [a["color"]["linear_probe_acc"], a["type"]["linear_probe_acc"]])],
          0.6, 2.25, 5.6, 4.4, [LINE, TEAL])
text(s, 0.6, 1.85, 5.6, 0.4, "Attribute accuracy (%)", 16, NAVY, bold=True)
ds = M["description_search"]
cats = list(ds)
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, ["colour + type", "partial plate", "colour + type\n+ partial plate"],
          [("Rank-1", [ds[c]["rank1"] for c in cats]), ("Rank-5", [ds[c]["rank5"] for c in cats])],
          6.9, 2.25, 5.85, 4.4, [SLATE, TEAL])
text(s, 6.9, 1.85, 5.85, 0.4, "Stage 1 description search (%)", 16, NAVY, bold=True)

# 10 ---- plate robustness
s = content_slide("Plate-only collapses as plates degrade; fusion holds up", "Results · main hypothesis",
                  "This is the main hypothesis test. VeRi has no plate text, so each vehicle gets a synthetic plate that "
                  "is degraded per sighting: clear, partial, blurred or hidden. Plate-only search falls from 100 to 3.6 "
                  "percent mean average precision. Appearance alone is flat at 27. Fused evidence stays far above it at every "
                  "level, and the transparent weighted fusion is the best fusion everywhere, ahead of the Random Forest. "
                  "One honest twist: with no plate at all, the learned metric on its own is best, at 48, because colour "
                  "and type are already inside the learned embedding and the attribute guesses add noise. Combining "
                  "evidence is robust where the plate fails.")
lv = ["clear", "partial", "blurred", "hidden"]
meth = [("Plate only", "plate_sim", AMBER), ("Appearance only", "appearance only", LINE),
        ("Learned metric", "learned metric", GREEN), ("Weighted fusion", "weighted fusion", TEAL),
        ("Random Forest", "random forest", SLATE)]
add_chart(s, XL_CHART_TYPE.COLUMN_CLUSTERED, [l.capitalize() for l in lv],
          [(n, [M["reid"][l][k]["mAP"] for l in lv]) for n, k, _ in meth], 0.6, 2.25, 8.4, 4.5, [c for *_, c in meth])
text(s, 0.6, 1.85, 8.4, 0.4, "Cross-camera Re-ID mAP (%) by plate visibility · 300 queries", 16, NAVY, bold=True)
k = box(s, 9.4, 2.25, 3.35, 4.5, NAVY, radius=0.06)
text(s, 9.7, 2.5, 2.8, 4.2, [[("100 → 3.6", {"size": 34, "bold": True, "color": AMBER})],
                             [("plate-only mAP, clear → hidden", {"size": 13, "color": LINE})],
                             [(f"{M['reid']['partial']['weighted fusion']['mAP']:.1f}", {"size": 34, "bold": True, "color": TEAL})],
                             [("weighted fusion mAP, partial plates", {"size": 13, "color": LINE})],
                             [(f"{M['reid']['blurred']['weighted fusion']['mAP']:.1f}", {"size": 34, "bold": True, "color": GREEN})],
                             [("weighted fusion mAP, blurred plates", {"size": 13, "color": LINE})]], 14, spacing=4)

# 11 ---- ablation
s = content_slide("Metric learning is the biggest single gain", "Results · ablation, plates hidden",
                  "With plates hidden, which cues matter? The generic ResNet and CLIP embeddings reach about 60 percent "
                  "rank-one. Learning a projection from just 150 labelled VeRi vehicles lifts that to 77 percent and nearly "
                  "doubles mean average precision, from 27 to 48. Colour, type and distinctive cues are far too coarse to "
                  "rank on their own. The forest puts almost half its importance on the learned metric.")
hid = M["reid"]["hidden"]
order = [("Learned metric", "learned metric"), ("Weighted fusion", "weighted fusion"), ("Random Forest", "random forest"),
         ("ResNet appearance", "appearance only"),
         ("CLIP cosine", "clip_cos"), ("HSV histogram", "color_hist"), ("Distinctive cues", "cue_sim"),
         ("Type agreement", "type_agree"), ("Colour agreement", "color_agree")]
ch = add_chart(s, XL_CHART_TYPE.BAR_CLUSTERED, [n for n, _ in order][::-1],
               [("Rank-1", [hid[k]["rank1"] for _, k in order][::-1]), ("mAP", [hid[k]["mAP"] for _, k in order][::-1])],
               0.6, 2.25, 8.4, 4.6, [SLATE, TEAL])
text(s, 0.6, 1.85, 8.4, 0.4, "Re-ID with plates hidden (%)", 16, NAVY, bold=True)
imp = M["rf_feature_importance"]
top3 = sorted(imp.items(), key=lambda kv: -kv[1])[:4]
k = box(s, 9.4, 2.25, 3.35, 4.6, MIST, radius=0.06)
text(s, 9.65, 2.45, 2.9, 0.4, "Random Forest importances", 15, NAVY, bold=True)
for i, (f, v) in enumerate(top3):
    y = 3.0 + i * 0.9
    text(s, 9.65, y, 2.9, 0.35, f.replace("_", " "), 13, SLATE)
    box(s, 9.65, y + 0.38, 2.6 * v / top3[0][1], 0.28, TEAL, shape=MSO_SHAPE.RECTANGLE)
    text(s, 9.7 + 2.6 * v / top3[0][1], y + 0.32, 0.6, 0.35, f"{v:.2f}", 12, NAVY, bold=True)

# 12 ---- demo path tracing
s = content_slide("Demo footage: vehicles traced camera to camera", "Results · demo footage",
                  "Back to real video. On the four demo cameras I measured re-identification against a reference: the "
                  "uncropped clip is tracked once and every camera tracklet is mapped back onto it, so these numbers are "
                  "pseudo ground truth. Here fusion beats appearance alone and the learned metric alone, because colour "
                  "and type reject look-alike cars. The automatic route suggestion is conservative: when it suggests a "
                  "camera it is right 70 percent of the time. With one click per camera the right car is among the three "
                  "shown for about two thirds of hops, and the screenshot shows the red Citroën confirmed in cameras A, "
                  "B and C, in time order.")
if D:
    rfm = D["methods"].get("random forest") or list(D["methods"].values())[-1]
    app = D["methods"]["appearance only"]
    stats = [(f"{rfm['Rank-1']:.0f}%", f"Rank-1, fused (appearance only {app['Rank-1']:.0f}%)"),
             (f"{rfm['camera_hit@3']:.0f}%", "right car among the 3 shown per camera"),
             (f"{rfm['route_precision']:.0f}%", "of suggested route steps are correct"),
             (f"{D['vehicles_in_2plus_cameras']}", "vehicles seen in 2+ of cameras A–C")]
    for i, (v, l) in enumerate(stats):
        y = 1.95 + i * 1.2
        text(s, 0.6, y, 2.4, 0.6, v, 32, TEAL_D, bold=True)
        text(s, 0.6, y + 0.62, 3.4, 0.4, l, 13, SLATE)
fit_picture(s, SHOTS / "path.png", 4.4, 1.85, 8.35, 4.95)

# 13 ---- SOM
som = M["som"]
s = content_slide("The SOM organises vehicles by type and colour, not identity", "Results · unsupervised",
                  "The Self-Organising Map is trained without any labels. Its nodes are fairly pure for type and colour "
                  "but not for identity, which is what you would expect from ImageNet features. Used as a candidate "
                  "pre-filter it removes 70 to 94 percent of candidates, but also drops too many true matches, so accuracy "
                  "goes down. That is a useful negative result: the SOM is good for exploring the footage, not for "
                  "filtering Re-ID candidates at this scale.")
fit_picture(s, RES / "som_umatrix.png", 0.6, 1.85, 5.2, 4.95)
pur = [("type", som["purity_type"]), ("colour", som["purity_color"]), ("vehicle ID", som["purity_vehicle_id"])]
text(s, 6.3, 1.85, 6.4, 0.4, "Node purity (10×10 map)", 16, NAVY, bold=True)
for i, (n, v) in enumerate(pur):
    y = 2.4 + i * 0.6
    text(s, 6.3, y, 1.5, 0.4, n, 15, SLATE)
    box(s, 7.8, y + 0.06, 4.2 * v, 0.32, TEAL if v > 0.5 else AMBER, shape=MSO_SHAPE.RECTANGLE)
    text(s, 7.9 + 4.2 * v, y, 0.8, 0.4, f"{v:.2f}", 15, NAVY, bold=True)
text(s, 6.3, 4.4, 6.4, 0.4, "As a Re-ID pre-filter (plates hidden)", 16, NAVY, bold=True)
pf = som["prefilter"]
rows = [("radius", "kept", "true matches kept", "mAP")] + [
    (r.split("_")[1], f"{v['candidates_kept_%']:.0f}%", f"{v['true_match_recall_%']:.0f}%", f"{v['mAP']:.1f}") for r, v in pf.items()]
tbl = s.shapes.add_table(len(rows), 4, Inches(6.3), Inches(4.9), Inches(6.4), Inches(0.4 * len(rows))).table
for r_, row in enumerate(rows):
    for c_, v in enumerate(row):
        cell = tbl.cell(r_, c_)
        cell.text = v
        p = cell.text_frame.paragraphs[0]
        p.runs[0].font.size, p.runs[0].font.name = Pt(14), FONT
        p.runs[0].font.bold = r_ == 0
        p.runs[0].font.color.rgb = rgb(WHITE if r_ == 0 else NAVY)
        cell.fill.solid()
        cell.fill.fore_color.rgb = rgb(SLATE if r_ == 0 else (MIST if r_ % 2 else WHITE))

# 14 ---- pitfalls
s = content_slide("Two pitfalls found — and fixed — during evaluation", "Lessons learned",
                  "Two lessons. First, a stacking leak: the forest was trained on colour and type probabilities from a "
                  "probe fitted on the same training vehicles, so those attributes looked almost perfect and the forest "
                  "over-trusted them. On new vehicles it ranked worse than appearance alone. Out-of-fold probabilities, "
                  "grouped by vehicle, fixed it. Second, the forest learned splits where higher similarity lowered the "
                  "score. Monotonic constraints fixed that. I'm transparent that this second choice was informed by test "
                  "queries, so the forest-versus-fusion comparison is indicative; a separate validation split is the "
                  "proper next step.")
pit = [("Stacking leak", "Colour/type features for RF training came from a probe fitted on the same vehicles → near-perfect, over-trusted.",
        "Out-of-fold probabilities and LDA projections (GroupKFold by vehicle)", "Rank-1, plates hidden: 38 → 56"),
       ("Non-monotonic splits", "Higher similarity could lower the match score under large viewpoint changes.",
        "scikit-learn monotonic constraints on every similarity feature", "mAP, plates hidden: 21 → 30")]
for i, (h, prob, fix, gain) in enumerate(pit):
    x = 0.6 + i * 6.15
    box(s, x, 1.95, 5.9, 4.8, MIST, radius=0.05)
    circle_num(s, x + 0.3, 2.2, 0.6, i + 1, size=18)
    text(s, x + 1.1, 2.27, 4.6, 0.5, h, 22, NAVY, bold=True)
    text(s, x + 0.3, 3.05, 5.3, 1.1, [[("Problem  ", {"bold": True, "color": AMBER}), (prob, {"color": SLATE})]], 15)
    text(s, x + 0.3, 4.2, 5.3, 1.0, [[("Fix  ", {"bold": True, "color": TEAL_D}), (fix, {"color": SLATE})]], 15)
    g = box(s, x + 0.3, 5.45, 5.3, 0.95, NAVY, radius=0.15)
    label(g, gain, 20, GREEN)

# 15 ---- live demo
s = content_slide("Live demo: the Streamlit app", "System demonstration",
                  "Now the app. After the admin signs in, step one processes the four demo cameras; videos already "
                  "processed load instantly. In step two I describe a target — for example a white car — and get ranked "
                  "candidates with the evidence for each field. I confirm one, and step three shows the traced path across "
                  "cameras, followed by every ranked candidate with its evidence vector and frame. The other tabs show the "
                  "manual tracking review, the SOM and the benchmark results.")
shots = [("search.png", "Stage 1 · describe (red + sedan) → ranked candidates → confirm"),
         ("path.png", "Stage 2 · route confirmed in camA → camB → camC")]
for i, (f, cap) in enumerate(shots):
    x = 0.6 + i * 6.15
    fit_picture(s, SHOTS / f, x, 1.95, 5.9, 4.4)
    text(s, x, 6.5, 5.9, 0.3, cap, 13, GREY, align=PP_ALIGN.CENTER)

# 16 ---- limitations
s = content_slide("Limitations and future work", "Looking ahead",
                  "Limitations. The learned metric is linear and trained on only 150 vehicles; using all VeRi training "
                  "identities, or fine-tuning the backbone with a triplet loss, is the clearest accuracy gain. Plates in the benchmark are "
                  "synthetic, and OCR runs on whole-vehicle crops rather than a plate detector. The forest optimises pair "
                  "classification rather than ranking, so learning-to-rank is next. The demo cameras are zones of one "
                  "recording, not separate physical cameras. And the pipeline reads files, but it works frame by frame, so "
                  "live RTSP streams are a small change.")
lim = [("Re-ID metric", "linear LDA on 150 vehicles → all 576 VeRi IDs, triplet-loss fine-tuning"),
       ("Plates", "synthetic plate strings; OCR on whole crops → plate detector + real plate data"),
       ("Learned fusion", "pairwise classifier → learning-to-rank, validation split for model choice"),
       ("Demo footage", "three zones of one recording → separate physical cameras (e.g. CityFlow)"),
       ("Deployment", "uploaded files → live RTSP streams; travel-time priors between cameras")]
for i, (h, d) in enumerate(lim):
    y = 1.95 + i * 0.95
    circle_num(s, 0.6, y, 0.55, i + 1, size=16)
    text(s, 1.4, y + 0.02, 3.2, 0.5, h, 19, NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 4.6, y + 0.02, 8.1, 0.55, d, 16, SLATE, anchor=MSO_ANCHOR.MIDDLE)

# 17 ---- conclusion
s = dark_slide("To conclude: V-Trace starts from incomplete information, retrieves likely candidates, keeps a human "
               "confirmation step, and then re-identifies and traces the vehicle across cameras using several "
               "complementary kinds of evidence, with the user confirming each hop. Plate-only search collapses when plates degrade, while fused evidence "
               "holds up. Description search finds the right vehicle in the top five for 84 percent of queries. And a "
               "learned fusion needs care to be trustworthy. Thank you — I'm happy to take questions.")
box(s, 0.7, 0.6, 2.75, 0.9, WHITE, radius=0.18)
picture(s, LOGO, 0.78, 0.66, w=2.6)
text(s, 0.7, 1.9, 11.5, 0.8, "Conclusion", 40, WHITE, bold=True)
concl = [(f"{M['description_search']['colour + type + partial plate']['rank5']:.0f}%", "right vehicle in the top 5 from colour + type + partial plate"),
         ("100 → 3.6", "plate-only mAP as plates degrade; fusion stays ≥ appearance"),
         ("27 → 48", "Re-ID mAP, plates hidden, after learning a metric from 150 vehicles")]
for i, (v, l) in enumerate(concl):
    x = 0.7 + i * 4.1
    text(s, x, 3.0, 3.8, 0.8, v, 40, GREEN if i != 1 else AMBER, bold=True)
    text(s, x, 3.9, 3.6, 1.0, l, 15, LINE)
text(s, 0.7, 5.5, 11.8, 0.6, "Ranked, evidence-backed sightings for human review — never an identity claim.", 20, MINT, bold=True)
text(s, 0.7, 6.4, 11.8, 0.5, "Thank you · Questions?    github.com/GurneetKB/V-Trace", 16, WHITE)

OUT.parent.mkdir(exist_ok=True)
prs.save(OUT)
print(f"saved {OUT} ({SLIDE_NO[0]} slides)")
