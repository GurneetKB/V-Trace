"""V-Trace Streamlit app: find a vehicle, see where else it was seen, follow its route.

Run with:  streamlit run app.py

Two pages:
  Search    - 1 find the vehicle (describe it, or pick it from a camera)
              2 where else was it seen (ranked matches per camera, confirm with one click)
              3 its route across cameras (timeline of confirmed sightings)
  Analysis  - benchmark results (VeRi-776), SOM, manual tracking check, matching settings explained
"""
import hmac
import json
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
        st.markdown(":green[**DESCRIBE → SEARCH → CONFIRM → RE-IDENTIFY**]")
        st.caption("Multi-attribute vehicle search & re-identification · admin access only")
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
@st.cache_resource(show_spinner="Loading vision models (first run downloads weights)...")
def get_extractor():
    from vtrace.features import FeatureExtractor
    return FeatureExtractor()


@st.cache_resource
def get_rf():
    return reid.load_rf()


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


def set_cameras(names):
    """Make `names` the videos searched in this session; earlier selections no longer apply."""
    st.session_state.active = list(names)
    for key in ("stage1", "query", "hops"):
        st.session_state.pop(key, None)


index = get_index()                                   # on-disk cache of every video ever processed (hidden)
if "active" not in st.session_state:                 # start with the demo cameras loaded
    st.session_state.active = load_demo_cameras(index)
active = st.session_state.active
if "view" not in st.session_state or st.session_state.get("view_for") != active:
    st.session_state.view, st.session_state.view_for = index.subset(active), list(active)
view = st.session_state.view                          # all searching / Re-ID happens on these videos only
rf = get_rf()

# matching settings (sidebar, shared by both pages)
SETTINGS = {"method": "random forest" if rf else "weighted fusion", "same_clock": True, "gap": 10, "min_score": 0.5}
for k, v in SETTINGS.items():
    st.session_state.setdefault(f"set_{k}", v)


def setting(name):
    return st.session_state[f"set_{name}"]


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
    return f"{fmt_time(t['start_t'])}–{fmt_time(t['end_t'])}"


# ------------------------------------------------------------------ sidebar
def sidebar():
    with st.sidebar:
        st.image(logo(), width="stretch")
        st.markdown(f"**Cameras in this search** · {len(view)} vehicles")
        for v in active:
            st.markdown(f"- {v} · {sum(t['video'] == v for t in view.tracklets)} vehicles")
        if not active:
            st.caption("No cameras loaded yet.")

        with st.expander("Use your own videos"):
            files = st.file_uploader("Camera videos (one file = one camera)", type=VIDEO_TYPES,
                                     accept_multiple_files=True)
            fast = st.toggle("Fast processing", value=True,
                             help="Analyse every 5th frame without plate OCR (about 3× quicker). "
                                  "Off: every 3rd frame with plate OCR.")
            if st.button("Process videos", type="primary", disabled=not files, width="stretch"):
                stride, use_ocr = (5, False) if fast else (config.FRAME_STRIDE, config.ENABLE_OCR)
                names = []
                for f in files:
                    dest = config.VIDEO_DIR / f.name
                    dest.write_bytes(f.getbuffer())
                    if not index.is_processed(dest, stride, use_ocr):
                        bar = st.progress(0.0, text=f"Processing {f.name}")
                        index.add_video(dest, get_extractor(), stride=stride, read_plate=use_ocr,
                                        progress=lambda x, b=bar: b.progress(min(x, 1.0)))
                    names.append(dest.stem)
                index.save()
                set_cameras(names)
                st.rerun()
            if active != load_demo_cameras(index) and st.button("Back to the demo cameras", width="stretch"):
                set_cameras(load_demo_cameras(index))
                st.rerun()

        with st.expander("Matching settings"):
            st.selectbox("Matcher", reid.METHODS, key="set_method",
                         help="Random Forest and weighted fusion combine all evidence; the other two are baselines.")
            st.toggle("Cameras share a clock", key="set_same_clock",
                      help="Only match sightings close in time (turn off for videos recorded at different times).")
            st.slider("Max time gap between cameras (s)", 1, 60, key="set_gap", disabled=not setting("same_clock"))
            st.slider("Minimum score for a suggestion", 0.0, 1.0, step=0.05, key="set_min_score")

        st.divider()
        st.caption(f"Signed in as **{st.session_state.admin_user}**")
        if st.button("Sign out", width="stretch"):
            st.session_state.clear()
            st.rerun()


# ------------------------------------------------------------------ search page
def vehicle_card(t, key, button="Select", note=None):
    with st.container(border=True):
        st.image(thumb(t["crop_paths"][len(t["crop_paths"]) // 2]), width="stretch")
        st.markdown(f"**{t['camera']}**  \n{when(t)}")
        st.caption(note or f"{top_label(t['color_probs'], config.COLORS)} · {top_label(t['type_probs'], config.TYPES)}")
        if st.button(button, key=key, width="stretch"):
            st.session_state.query, st.session_state.hops = t["uid"], {}
            st.rerun()


def grid(items, per_row, render):
    for start in range(0, len(items), per_row):
        for col, item in zip(st.columns(per_row), items[start:start + per_row]):
            with col:
                render(item)


def find_vehicle():
    st.subheader("① Find the vehicle")
    how = st.segmented_control("How", ["Describe it", "Pick it from a camera"], default="Describe it",
                               label_visibility="collapsed", key="find_mode")
    if how == "Pick it from a camera":
        cam = st.selectbox("Camera", active, key="pick_camera")
        ts = sorted((t for t in view.tracklets if t["video"] == cam), key=lambda t: t["start_t"])
        st.caption(f"{len(ts)} vehicles in {cam}, in order of appearance.")
        grid(ts, 6, lambda t: vehicle_card(t, f"pick_{t['uid']}"))
        return

    with st.form("describe"):
        c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6], vertical_alignment="bottom")
        color = c1.selectbox("Colour", ["any"] + config.COLORS)
        vtype = c2.selectbox("Type", ["any"] + config.TYPES)
        plate = c3.text_input("Plate (use ? for unknown)", placeholder="e.g. SGX12??")
        go = c4.form_submit_button("Search", type="primary", width="stretch")
        with st.expander("More detail (optional)"):
            cues = st.multiselect("Distinctive features", list(config.CUES))
            free_text = st.text_input("Anything else", placeholder="e.g. taxi with roof sign")
    if go:
        st.session_state.stage1 = search.describe_search(
            view, None if color == "any" else color, None if vtype == "any" else vtype, plate or None, cues,
            free_text or None, get_extractor() if free_text else None, None, 12)
    results = st.session_state.get("stage1", [])
    if results:
        st.caption("Best matches first. Select the right vehicle to see where else it was seen.")
        grid([(i, t) for i, (_, t, _) in enumerate(results, 1)], 6,
             lambda it: vehicle_card(it[1], f"res_{it[1]['uid']}", note=f"#{it[0]} · "
                                     f"{top_label(it[1]['color_probs'], config.COLORS)} · "
                                     f"{top_label(it[1]['type_probs'], config.TYPES)}"))


def where_else(q):
    hops = st.session_state.setdefault("hops", {})
    gap = setting("gap") if setting("same_clock") else None
    method = setting("method")
    members = [q] + [view.get(u) for u in hops.values()]
    suggested = {t["video"]: t["uid"] for _, t in reid.trace_path(view, q, method, rf, setting("min_score"), gap)
                 if t["uid"] != q["uid"]}

    # ---- the query and its route
    st.subheader("② Its route across the cameras")
    route = sorted(members + [view.get(u) for v, u in suggested.items() if v not in hops], key=lambda t: t["start_t"])
    cols = st.columns(max(len(route) * 2 - 1, 1))
    for k, t in enumerate(route):
        with cols[2 * k]:
            with st.container(border=True):
                st.image(thumb(t["crop_paths"][0]), width="stretch")
                st.markdown(f"**{t['camera']}**  \n{when(t)}")
                st.caption("🎯 your vehicle" if t["uid"] == q["uid"] else
                           "✅ confirmed" if t["uid"] in hops.values() else "⭐ suggested – confirm below")
        if k < len(route) - 1:
            cols[2 * k + 1].markdown("<h2 style='text-align:center;margin-top:4rem'>→</h2>", unsafe_allow_html=True)
    if st.button("← Choose a different vehicle"):
        st.session_state.pop("query")
        st.rerun()

    # ---- ranked matches per camera (query + ranked gallery, like a Re-ID result list)
    st.subheader("③ Where else was it seen?")
    st.caption("Best matches in each other camera, ranked by how similar they are to every confirmed view of your "
               "vehicle. Click ✓ on the right one; the other cameras update. ⭐ = suggested.")
    cams = reid.camera_candidates(view, members, method, rf, gap, k=3)
    for video in sorted(set(cams) | set(hops)):
        with st.container(border=True):
            if video in hops:
                t = view.get(hops[video])
                a, b, c = st.columns([1, 4, 1], vertical_alignment="center")
                a.image(thumb(t["crop_paths"][0]), width="stretch")
                b.markdown(f"**{video}** · ✅ confirmed at {when(t)}")
                c.button("Undo", key=f"undo_{video}", on_click=hops.pop, args=(video,), width="stretch")
                continue
            head, *slots = st.columns([1.2, 1, 1, 1], vertical_alignment="center")
            head.markdown(f"**{video}**")
            head.caption("ranked matches →")
            for rank, (slot, (score, t)) in enumerate(zip(slots, cams[video]), 1):
                with slot:
                    st.image(thumb(t["crop_paths"][0]), width="stretch")
                    st.caption(f"{'⭐ ' if suggested.get(video) == t['uid'] else ''}#{rank} · {when(t)} · {score:.0%}")
                    st.button("✓ Same vehicle", key=f"hop_{t['uid']}", on_click=hops.__setitem__,
                              args=(video, t["uid"]), width="stretch")

    with st.expander("Why these matches? (evidence for each candidate)"):
        hits = reid.reid_search(view, q, method, rf, top_k=15, max_gap_s=gap)
        rows = [{"rank": i, "camera": t["camera"], "time": when(t), "score": round(s, 2),
                 **{k: round(v, 2) for k, v in f.items()}} for i, (s, t, f) in enumerate(hits, 1)]
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.caption("Each row is the evidence vector compared by the matcher: learned-metric, ResNet and CLIP "
                   "similarity, colour and type agreement, plate similarity, distinctive cues and track quality.")


def search_page():
    st.title("Find a vehicle across cameras")
    st.markdown(":green[**DESCRIBE → SEARCH → CONFIRM → RE-IDENTIFY → TRACE**]")
    st.caption("Results are ranked candidates for human review, not definitive identification.")
    if not len(view):
        st.info("No cameras loaded. Add your own videos in the sidebar (Use your own videos).")
        return
    q = view.get(st.session_state["query"]) if st.session_state.get("query") in {t["uid"] for t in view.tracklets} else None
    if q is None:
        find_vehicle()
    else:
        where_else(q)


# ------------------------------------------------------------------ analysis page
def analysis_page():
    st.title("Analysis")
    st.caption("How well V-Trace works, and the tools used to check it.")
    tabs = st.tabs(["Benchmark results (VeRi-776)", "Vehicle map (SOM)", "Tracking check"])

    with tabs[0]:
        mfile = config.RESULTS_DIR / "metrics.json"
        if not mfile.exists():
            st.info("Run `python scripts/train_eval.py` after downloading VeRi-776 (see README).")
        else:
            m = json.loads(mfile.read_text())
            hid = m["reid"]["hidden"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Re-ID mAP, plates hidden", f"{hid['learned metric']['mAP']:.0f}%",
                      f"{hid['learned metric']['mAP'] - hid['appearance only']['mAP']:+.0f} vs generic embedding")
            c2.metric("Right vehicle in top 5 (colour + type + partial plate)",
                      f"{m['description_search']['colour + type + partial plate']['rank5']:.0f}%")
            c3.metric("Plate-only mAP, clear → hidden plates",
                      f"{m['reid']['clear']['plate_sim']['mAP']:.0f}% → {hid['plate_sim']['mAP']:.1f}%")
            st.markdown("**Re-ID mAP (%) by plate visibility**")
            names = {"appearance only": "Appearance only", "learned metric": "Learned metric",
                     "plate_sim": "Plate only", "weighted fusion": "Weighted fusion", "random forest": "Random Forest"}
            st.dataframe(pd.DataFrame({lvl: {n: round(m["reid"][lvl][k]["mAP"], 1) for k, n in names.items()}
                                       for lvl in m["reid"]}), width="stretch")
            imgs = [p for p in ("plate_robustness.png", "ablation.png") if (config.RESULTS_DIR / p).exists()]
            for col, p in zip(st.columns(2), imgs):
                col.image(str(config.RESULTS_DIR / p))
            with st.expander("All numbers"):
                st.json(m, expanded=False)

    with tabs[1]:
        st.write("A Self-Organizing Map groups visually similar vehicles without any labels. "
                 "Darker cells mark boundaries between groups.")
        if view.som is None:
            st.info("Needs at least 4 vehicles.")
        else:
            som = view.som
            bmus = som.bmus(view.matrix("app_emb"))
            ink = "#E6EEF0" if st.context.theme.type == "dark" else "#111820"   # match the active app theme
            fig, ax = plt.subplots(figsize=(5, 5))
            fig.patch.set_alpha(0)
            ax.tick_params(colors=ink)
            ax.imshow(som.u_matrix().T, cmap="bone_r", origin="lower")
            rng = np.random.default_rng(0)
            for (i, j), t in zip(bmus, view.tracklets):
                ax.scatter(i + rng.uniform(-.3, .3), j + rng.uniform(-.3, .3), s=25, edgecolors="k",
                           c=config.COLORS[int(np.argmax(t["color_probs"]))].replace("golden", "goldenrod"))
            ax.set_title(f"{som.grid}x{som.grid} SOM · dots = vehicles (predicted colour)", color=ink)
            c1, c2 = st.columns(2)
            c1.pyplot(fig)
            nodes = defaultdict(list)
            for b, t in zip(bmus, view.tracklets):
                nodes[b].append(t)
            with c2:
                for node, group in sorted(nodes.items(), key=lambda kv: -len(kv[1]))[:8]:
                    st.markdown(f"**Group {node}** – {len(group)} vehicles")
                    st.image([g["crop_paths"][0] for g in group[:8]], width=70)

    with tabs[2]:
        st.write("Untick vehicles whose track mixes two vehicles (an ID switch). This gives a manually checked "
                 "tracking accuracy.")
        if len(view):
            vid = st.selectbox("Camera", view.videos(), key="review_video")
            ts = [t for t in view.tracklets if t["video"] == vid]
            review_file = config.RESULTS_DIR / f"tracking_review_{vid}.csv"
            prev = pd.read_csv(review_file).set_index("uid")["clean"].to_dict() if review_file.exists() else {}
            grid(ts, 8, lambda t: st.image(t["crop_paths"][0], caption=f"track {t['track_id']}"))
            df = pd.DataFrame([{"uid": t["uid"], "track": t["track_id"], "time": when(t),
                                "clean": bool(prev.get(t["uid"], True))} for t in ts])
            edited = st.data_editor(df, hide_index=True, disabled=["uid", "track", "time"], key=f"editor_{vid}")
            if st.button("Save check"):
                edited[["uid", "clean"]].to_csv(review_file, index=False)
                st.success(f"Saved: {edited['clean'].mean():.0%} of {len(edited)} tracks are clean.")


sidebar()
st.navigation([st.Page(search_page, title="Search", icon=":material/search:", default=True),
               st.Page(analysis_page, title="Analysis", icon=":material/analytics:")]).run()
