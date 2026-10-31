"""V-Trace Streamlit app: describe a vehicle, pick it from the ranked matches, see every camera it was seen in.

Run with:  streamlit run app.py

  1 Videos     - the demo cameras already on the platform, or upload your own short clips (one video = one camera);
                 each video is processed into tracklets (YOLO11 detection + ByteTrack tracking)
  2 Describe   - colour, type, plate, distinctive features, free text  -> ranked best matches (CLIP zero-shot + OCR)
  3 Select     - pick the right vehicle
  4 Seen in    - every camera where the pretrained FastReID (VeRi-776) model finds the same vehicle,
                 with the time span and one frame from each sighting
"""
import hmac
import json
import os

import numpy as np
import streamlit as st
from PIL import Image

from vtrace import config, reid, search
from vtrace.index import VehicleIndex
from vtrace.video import fmt_time

st.set_page_config(page_title="V-Trace", page_icon=str(config.ROOT / "assets" / "vtrace_icon.png"), layout="wide")

# Dark is the default theme. Streamlit otherwise follows the OS setting (and stores "System" on first load), so on
# a viewer's first visit we store "Dark" as their theme choice and reload once; our own marker makes sure this
# happens only once, so a later choice in ⋮ → Settings → Theme is respected.
st.iframe("""<script>
try {
  const w = window.parent, s = w.localStorage, key = "stActiveTheme-" + w.location.pathname + "-v2";
  if (!s.getItem("vtrace-dark-default")) {
    s.setItem("vtrace-dark-default", "1");
    if (s.getItem(key) !== JSON.stringify("Dark")) { s.setItem(key, JSON.stringify("Dark")); w.location.reload(); }
  }
} catch (e) {}
</script>""", height=1)
st.html("<style>[data-testid=stElementContainer][height='1px']:has(iframe) {display: none}</style>")  # hide the helper

ASSETS = config.ROOT / "assets"
DEMO_CAMERAS = ["camA_west", "camB_centre", "camC_east", "camD_other_road"]   # scripts/prepare_demo_clips.py
VIDEO_TYPES = ["mp4", "avi", "mov", "mkv"]


def logo():
    """The V-Trace logo for the active theme (white lettering on dark, navy on light)."""
    return str(ASSETS / ("vtrace_logo_light.png" if st.context.theme.type == "light" else "vtrace_logo_dark.png"))


# ------------------------------------------------------------------ sign-in
def admin_credentials():
    """Admin username/password from .streamlit/secrets.toml ([admin]) or VTRACE_ADMIN_USER / VTRACE_ADMIN_PASSWORD."""
    try:
        sec = st.secrets.get("admin", {})
    except Exception:                                # no secrets file at all
        sec = {}
    return (sec.get("username") or os.environ.get("VTRACE_ADMIN_USER", ""),
            sec.get("password") or os.environ.get("VTRACE_ADMIN_PASSWORD", ""))


def require_admin():
    """Admin sign-in page. Everything below this call only runs once the admin is signed in."""
    if st.session_state.get("admin_user"):
        return
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.image(logo(), width="stretch")
        st.markdown(":green[**DESCRIBE → RANK → SELECT → TRACE**]")
        st.caption("Vehicle search & re-identification across cameras · admin access only")
        user, pwd = admin_credentials()
        if not (user and pwd):
            st.error("No admin account is configured. Add an `[admin]` section with `username` and `password` "
                     "to `.streamlit/secrets.toml` (see `secrets.toml.example`), or to the app's Secrets on "
                     "Streamlit Cloud, then reload.")
            st.stop()
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", type="primary", width="stretch"):
                if hmac.compare_digest(u.strip(), user) and hmac.compare_digest(p, pwd):
                    st.session_state.admin_user = user
                    st.rerun()
                st.error("Incorrect username or password.")
    st.stop()


require_admin()


# ------------------------------------------------------------------ data
@st.cache_resource(show_spinner="Loading the pretrained models (first run downloads the weights)...")
def get_extractor():
    from vtrace.features import FeatureExtractor
    return FeatureExtractor()


def get_index():
    if "index" not in st.session_state:
        st.session_state.index = VehicleIndex.load()
    return st.session_state.index


def load_demo_cameras(index):
    """The demo cameras, from the local index if processed here, otherwise from the pre-processed demo bundle."""
    missing = [c for c in DEMO_CAMERAS if c not in index.videos()]
    from_bundle = [c for c in missing if c in VehicleIndex.bundled_videos()]
    if from_bundle:
        index.import_bundle(from_bundle)
    return [c for c in DEMO_CAMERAS if c in index.videos()]


def set_cameras(names, same_clock):
    """Make `names` the videos searched in this session; earlier results no longer apply. The demo cameras are cut
    from one recording (same clock); uploaded videos are assumed to be recorded at different times."""
    st.session_state.active = list(names)
    st.session_state.same_clock = same_clock
    for key in ("results", "query"):
        st.session_state.pop(key, None)


index = get_index()                                   # on-disk cache of every video ever processed
if "active" not in st.session_state:                 # start with the demo cameras loaded
    st.session_state.active = load_demo_cameras(index)
active = st.session_state.active
if st.session_state.get("view_for") != active:
    st.session_state.view, st.session_state.view_for = index.subset(active), list(active)
view = st.session_state.view                          # all searching happens on these videos only
for key, value in (("threshold", config.MATCH_THRESHOLD), ("same_clock", True), ("max_gap", config.MAX_GAP_S)):
    st.session_state.setdefault(key, value)


def top_label(probs, vocab):
    probs = np.asarray(probs)
    return vocab[probs.argmax()] if probs.max() > 0 else "-"


@st.cache_data(show_spinner=False, max_entries=3000)
def thumb(path, w=320, h=240):
    """Every crop in the same 4:3 frame, so result cards line up."""
    im = Image.open(path).convert("RGB")
    scale = min(w / im.width, h / im.height)                  # scale small crops up as well as large ones down
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), (30, 38, 46))
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return canvas


def when(t):
    return f"{fmt_time(t['start_t'])} – {fmt_time(t['end_t'])}"


def crop(t):
    return thumb(t["crop_paths"][len(t["crop_paths"]) // 2])


# ------------------------------------------------------------------ sidebar: which videos
def process(files, fast):
    stride, use_ocr = (5, False) if fast else (config.FRAME_STRIDE, config.ENABLE_OCR)
    names = []
    for f in files:
        dest = config.VIDEO_DIR / f.name
        dest.write_bytes(f.getbuffer())
        if not index.is_processed(dest, stride, use_ocr):
            bar = st.progress(0.0, text=f"Processing {f.name}: detecting, tracking and describing vehicles")
            index.add_video(dest, get_extractor(), stride=stride, read_plate=use_ocr,
                            progress=lambda x, b=bar: b.progress(min(x, 1.0)))
        names.append(dest.stem)
    index.save()
    set_cameras(names, same_clock=False)


def sidebar():
    with st.sidebar:
        st.image(logo(), width="stretch")
        source = st.radio("Videos", ["Demo videos", "Upload new videos"], key="source")
        if source == "Demo videos":
            demo = load_demo_cameras(index)
            if active != demo:
                set_cameras(demo, same_clock=True)
                st.rerun()
        else:
            files = st.file_uploader("Short dash-cam / traffic-cam clips (one file = one camera)", type=VIDEO_TYPES,
                                     accept_multiple_files=True)
            fast = st.toggle("Fast processing", value=True,
                             help="Every 5th frame without plate OCR (about 3× quicker). Off: every 3rd frame with OCR.")
            if st.button("Process videos", type="primary", disabled=not files, width="stretch"):
                process(files, fast)
                st.rerun()

        st.markdown(f"**Processed cameras** · {len(view)} vehicle sightings")
        for v in active:
            st.markdown(f"- {v} · {sum(t['video'] == v for t in view.tracklets)}")
        if not active:
            st.caption("Nothing processed yet.")

        with st.expander("Settings"):
            st.slider("Same-vehicle threshold (Re-ID similarity)", 0.2, 0.9, step=0.05, key="threshold",
                      help="The best sighting in another camera counts as the selected vehicle when its FastReID "
                           "similarity is at least this value and clearly above the camera's next-best sighting.")
            st.toggle("Videos were recorded at the same time", key="same_clock",
                      help="Then a vehicle can only reappear within a few seconds in another camera. Turn off for "
                           "videos recorded at different times.")
            st.slider("Max seconds between cameras", 2, 60, key="max_gap", disabled=not st.session_state.same_clock)
        st.divider()
        st.caption(f"Signed in as **{st.session_state.admin_user}**")
        if st.button("Sign out", width="stretch"):
            st.session_state.clear()
            st.rerun()


# ------------------------------------------------------------------ search page
def describe():
    st.subheader("1 · Describe the vehicle")
    with st.form("describe"):
        c1, c2, c3 = st.columns(3)
        color = c1.selectbox("Colour", ["any"] + config.COLORS)
        vtype = c2.selectbox("Type", ["any"] + config.TYPES)
        plate = c3.text_input("Licence plate (full or partial, ? = unknown)", placeholder="e.g. SGX12??")
        c4, c5 = st.columns(2)
        cues = c4.multiselect("Distinctive features", list(config.CUES))
        free_text = c5.text_input("Anything else", placeholder="e.g. taxi with a roof sign")
        go = st.form_submit_button("Search", type="primary")
    if go:
        st.session_state.query = None
        st.session_state.results = search.describe_search(
            view, None if color == "any" else color, None if vtype == "any" else vtype, plate or None, cues,
            free_text or None, get_extractor() if free_text else None, None, 12)


def matches():
    results = st.session_state.get("results")
    if not results:
        return
    st.subheader("2 · Best matches")
    st.caption("Ranked by how well each tracked vehicle fits the description. Select the one you are looking for.")
    for start in range(0, len(results), 6):
        for col, (rank, (score, t, _)) in zip(st.columns(6), enumerate(results[start:start + 6], start + 1)):
            with col.container(border=True):
                st.image(crop(t), width="stretch")
                st.markdown(f"**#{rank} · {t['camera']}**  \n{when(t)}")
                st.caption(f"{top_label(t['color_probs'], config.COLORS)} · {top_label(t['type_probs'], config.TYPES)}"
                           f"{' · ' + t['plate'] if t.get('plate') else ''} · match {score:.0%}")
                selected = st.session_state.get("query") == t["uid"]
                st.button("✓ Selected" if selected else "Select", key=f"sel_{t['uid']}", width="stretch",
                          type="primary" if selected else "secondary",
                          on_click=st.session_state.__setitem__, args=("query", t["uid"]))


def seen_in(q):
    st.subheader("3 · Where this vehicle was seen")
    gap = st.session_state.max_gap if st.session_state.same_clock else None
    seen = reid.where_seen(view, q, st.session_state.threshold, max_gap_s=gap)
    route = reid.route(seen)
    st.markdown("**Route:** " + "  →  ".join(f"{t['camera']} ({fmt_time(t['start_t'])})" for t in route))
    st.caption(f"Seen in {len(route)} of {len(seen)} cameras. Similarity is the FastReID (VeRi-776) Re-ID score "
               "against the selected vehicle.")

    for t in route:
        score = seen[t["video"]]["match"][0]
        with st.container(border=True):
            a, b, c = st.columns([1.3, 1, 1.7], vertical_alignment="center")
            with a:
                st.markdown(f"#### {t['camera']}")
                st.markdown(f"🕒 **{when(t)}**  \n({t['end_t'] - t['start_t']:.1f} s on camera)")
                st.caption("🎯 the vehicle you selected" if t["uid"] == q["uid"] else f"✅ same vehicle · similarity {score:.2f}")
            b.image(crop(t), width="stretch")
            c.image(t["frame_path"], width="stretch", caption=f"{t['camera']} at {fmt_time(t['best_t'])}")

    missing = [(v, s) for v, s in seen.items() if not s["match"]]
    if missing:
        st.markdown("**Not seen in**")
        for video, s in missing:
            with st.container(border=True):
                a, *slots = st.columns([1.2, 1, 1, 1], vertical_alignment="center")
                a.markdown(f"**{video}**")
                if not s["candidates"]:
                    a.caption("no vehicle in the time window")
                    continue
                a.caption("no confident match; closest vehicles →")
                for slot, (score, t) in zip(slots, s["candidates"]):
                    slot.image(crop(t), width="stretch")
                    slot.caption(f"{when(t)} · similarity {score:.2f}")


def search_page():
    st.title("Find a vehicle across cameras")
    st.markdown(":green[**DESCRIBE → RANK → SELECT → TRACE**]")
    st.caption("Results are ranked candidates for a person to review, not a definitive identification.")
    if not len(view):
        st.info("No processed videos. Choose the demo videos or upload your own in the sidebar.")
        return
    describe()
    matches()
    uids = {t["uid"] for t in view.tracklets}
    if st.session_state.get("query") in uids:
        seen_in(view.get(st.session_state.query))


# ------------------------------------------------------------------ about page
def about_page():
    st.title("How V-Trace works")
    st.markdown("""
V-Trace uses **only pretrained, published models** - nothing is trained for this project.

| Step | Model | Source |
|---|---|---|
| Detect vehicles in every frame | YOLO11n (COCO: car, motorcycle, bus, truck) | Ultralytics |
| Follow each vehicle while it stays in view (one *sighting*) | ByteTrack | Ultralytics |
| Colour, type, distinctive features, free text | CLIP ViT-B/32, zero-shot | OpenAI / open_clip |
| Licence plate | EasyOCR | JaidedAI |
| Same vehicle in another camera | FastReID SBS(R50-ibn) trained on VeRi-776 | JDAI-CV (VeRi-776 authors' team) |

**Same vehicle in another camera?** For the selected sighting, each other camera's most similar sighting counts as the
same vehicle when its Re-ID similarity is at least the threshold (default 0.40), it clearly beats that camera's
second-best sighting (by 0.08; otherwise the answer is ambiguous and the closest vehicles are shown instead) and, for
videos recorded at the same time, it is within 10 s.
""")
    st.subheader("Re-ID model on the VeRi-776 benchmark")
    mfile = config.RESULTS_DIR / "veri_eval.json"
    if mfile.exists():
        m = json.loads(mfile.read_text())
        c1, c2, c3 = st.columns(3)
        c1.metric("Rank-1", f"{m['rank1']:.1f}%")
        c2.metric("Rank-5", f"{m['rank5']:.1f}%")
        c3.metric("mAP", f"{m['mAP']:.1f}%")
        st.caption(f"Our run of the published checkpoint on the official VeRi-776 split ({m['queries']} queries, "
                   f"{m['gallery']} gallery images). FastReID reports Rank-1 97.0 %, mAP 81.9 %.")
    else:
        st.info("Run `python scripts/eval_veri.py` with VeRi-776 downloaded to reproduce the benchmark numbers.")
    demo = config.RESULTS_DIR / "demo_eval.json"
    if demo.exists():
        st.subheader("On the demo cameras")
        st.json(json.loads(demo.read_text()), expanded=False)


sidebar()
st.navigation([st.Page(search_page, title="Search", icon=":material/search:", default=True),
               st.Page(about_page, title="How it works", icon=":material/info:")]).run()
