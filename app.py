"""V-Trace Streamlit app:  Upload -> Describe -> Search -> Confirm -> Re-identify.

Run with:  streamlit run app.py
"""
import json
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from vtrace import config, reid, search
from vtrace.index import VehicleIndex
from vtrace.video import fmt_time

st.set_page_config(page_title="V-Trace", page_icon="🚗", layout="wide")


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


def top_label(probs, vocab):
    probs = np.asarray(probs)
    return f"{vocab[probs.argmax()]} ({probs.max():.0%})" if probs.max() > 0 else "-"


def describe_tracklet(t):
    return (f"**{t['camera']}** · track {t['track_id']} · {fmt_time(t['start_t'])}–{fmt_time(t['end_t'])}  \n"
            f"{t['yolo_class']} · colour {top_label(t['color_probs'], config.COLORS)} · "
            f"type {top_label(t['type_probs'], config.TYPES)} · plate `{t['plate'] or 'unread'}`")



index = get_index()

with st.sidebar:
    st.header("V-Trace status")
    st.metric("Indexed tracklets", len(index))
    st.write(f"**Videos / cameras:** {', '.join(index.videos()) or 'none yet'}")
    st.write(f"**Stage 2 matcher:** {'Random Forest (trained)' if get_rf() else 'weighted fusion (RF not trained yet)'}")
    st.write(f"**Colour/type model:** {'supervised probe' if config.ATTR_PROBE_PATH.exists() else 'CLIP zero-shot'}")
    st.write(f"**Plate OCR:** {'on' if config.ENABLE_OCR else 'off'}")
    st.write(f"**Confirmed target:** {st.session_state.get('confirmed', '-')}")
    st.divider()
    st.caption("Workflow: 1 upload → 2 describe & search → confirm → 3 re-identify")

st.title("🚗 V-Trace")
st.caption("Multi-attribute vehicle search & re-identification · **Describe → Search → Confirm → Re-identify** · "
           "Results are ranked candidates for human review, not definitive identification.")

tabs = st.tabs(["1 · Upload & index", "2 · Describe & search", "3 · Confirm & re-identify",
                "Track review", "SOM (unsupervised)", "Evaluation"])

# ------------------------------------------------------------------ 1. upload
with tabs[0]:
    st.subheader("Upload camera videos")
    st.write("Each video is treated as one camera. Vehicles are detected (YOLO), tracked within the video "
             "(ByteTrack) and every tracklet is described (CNN appearance, CLIP colour/type/cues, HSV colour, plate OCR).")
    files = st.file_uploader("Videos", type=["mp4", "avi", "mov", "mkv"], accept_multiple_files=True)
    if st.button("No footage? Generate two sample camera clips"):
        from vtrace.samples import make_sample_videos
        made = make_sample_videos()
        st.success(f"Created {', '.join(p.name for p in made)} – select them below and click Process.")
    existing = sorted(p for p in config.VIDEO_DIR.iterdir() if p.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"})
    use_existing = st.multiselect("…or process videos already in data/videos", [p.name for p in existing])
    presets = {"Fast": (5, False), "Balanced": (config.FRAME_STRIDE, config.ENABLE_OCR), "Detailed": (2, config.ENABLE_OCR)}
    speed = st.radio("Processing speed", list(presets), index=1, horizontal=True,
                     help="Fast: every 5th frame, no plate OCR (about 3x quicker; good for a live demo). "
                          "Balanced: every 3rd frame + OCR on large vehicles. Detailed: every 2nd frame + OCR.")
    stride, use_ocr = presets[speed]
    st.caption(f"Analyses every {stride}{'nd' if stride == 2 else 'rd' if stride == 3 else 'th'} frame · "
               f"plate OCR {'on' if use_ocr else 'off'}")
    if st.button("Process videos", type="primary", disabled=not (files or use_existing)):
        import time
        t0 = time.time()
        paths = []
        for f in files or []:
            dest = config.VIDEO_DIR / f.name
            dest.write_bytes(f.getbuffer())
            paths.append(dest)
        paths += [config.VIDEO_DIR / n for n in use_existing if config.VIDEO_DIR / n not in paths]
        fe = get_extractor()
        for p in paths:
            bar = st.progress(0.0, text=f"Processing {p.name}")
            n = index.add_video(p, fe, progress=lambda x, b=bar, name=p.name: b.progress(
                min(x, 1.0), text=f"Processing {name} – {'detecting & tracking' if x < 0.8 else 'describing vehicles'}"),
                stride=stride, read_plate=use_ocr)
            bar.progress(1.0, text=f"{p.name}: {n} vehicle tracklets")
        index.fit_som()
        index.save()
        st.success(f"Index now holds {len(index)} tracklets from {len(index.videos())} videos "
                   f"(processed in {time.time() - t0:.0f} s).")

    if len(index):
        st.subheader("Current vehicle index")
        rows = [{"video / camera": t["camera"], "track": t["track_id"], "class": t["yolo_class"],
                 "colour": top_label(t["color_probs"], config.COLORS), "type": top_label(t["type_probs"], config.TYPES),
                 "plate": t["plate"] or "-", "start": fmt_time(t["start_t"]), "end": fmt_time(t["end_t"]),
                 "detections": t["n_obs"]} for t in index.tracklets]
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        c1, c2 = st.columns(2)
        drop = c1.selectbox("Remove a video from the index", ["-"] + index.videos())
        if c2.button("Remove") and drop != "-":
            index.remove_video(drop)
            index.fit_som()
            index.save()
            st.rerun()
    else:
        st.info("The index is empty - upload videos to begin.")

# ------------------------------------------------------------------ 2. describe & search
with tabs[1]:
    st.subheader("Stage 1 – describe the target vehicle")
    st.write("Fill in only what you know. Missing fields are ignored; use `?` for unknown plate characters (e.g. `SGX12??`).")
    c1, c2, c3 = st.columns(3)
    color = c1.selectbox("Colour", ["(unknown)"] + config.COLORS)
    vtype = c2.selectbox("Vehicle type", ["(unknown)"] + config.TYPES)
    plate = c3.text_input("Full / partial plate")
    c4, c5 = st.columns(2)
    cues = c4.multiselect("Distinctive cues", list(config.CUES))
    free_text = c5.text_input("Other description (free text, CLIP)", placeholder="e.g. taxi with roof sign")
    videos = st.multiselect("Search in videos (default: all)", index.videos())
    top_k = st.slider("Candidates to show", 4, 40, 12, 4)

    if st.button("Search", type="primary", disabled=not len(index)):
        st.session_state.stage1 = search.describe_search(
            index, color if color != "(unknown)" else None, vtype if vtype != "(unknown)" else None,
            plate or None, cues, free_text or None, get_extractor() if free_text else None, videos or None, top_k)

    for row_start in range(0, len(st.session_state.get("stage1", [])), 4):
        cols = st.columns(4)
        for i, (col, (score, t, ev)) in enumerate(zip(cols, st.session_state.stage1[row_start:row_start + 4])):
            with col, st.container(border=True):
                st.image(t["crop_paths"][len(t["crop_paths"]) // 2])
                st.markdown(f"#{row_start + i + 1} · **score {score:.0%}**")
                st.markdown(describe_tracklet(t))
                if ev:
                    st.caption(" · ".join(f"{k}: {v:.0%}" for k, v in ev.items()))
                with st.expander("Frame evidence"):
                    st.image(t["frame_path"])
                if st.button("✅ Confirm this vehicle", key=f"confirm_{t['uid']}"):
                    st.session_state.confirmed = t["uid"]
                    st.success("Confirmed – open tab 3 to re-identify it in the other videos.")

# ------------------------------------------------------------------ 3. re-identify
with tabs[2]:
    st.subheader("Stage 2 – cross-video re-identification of the confirmed vehicle")
    uid = st.session_state.get("confirmed")
    if not uid or uid not in {t["uid"] for t in index.tracklets}:
        st.info("Confirm a candidate in tab 2 first.")
    else:
        q = index.get(uid)
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("**Confirmed target (visual query)**")
            st.image(q["crop_paths"], width=110)
            st.markdown(describe_tracklet(q))
        with c2:
            st.image(q["frame_path"])
        rf = get_rf()
        c1, c2, c3, c4 = st.columns(4)
        method = c1.selectbox("Matching method", reid.METHODS, index=2 if rf else 1,
                              help="Random Forest needs models/rf_matcher.joblib (scripts/train_eval.py); "
                                   "otherwise it falls back to weighted fusion.")
        use_som = c2.checkbox("SOM candidate pre-filter", value=False)
        radius = c3.slider("SOM radius", 1, 4, 2, disabled=not use_som)
        same_video = c4.checkbox("Include same video", value=False)
        if method == "random forest" and rf is None:
            st.warning("No trained Random Forest found – using weighted fusion. Run `python scripts/train_eval.py`.")

        hits = reid.reid_search(index, q, method, rf, use_som, radius, same_video, top_k=20)
        if not hits:
            st.warning("No candidate tracklets in the other videos.")
        for rank, (score, t, f) in enumerate(hits, 1):
            with st.container(border=True):
                a, b, c = st.columns([2, 2, 3])
                a.markdown(f"### #{rank} · {score:.0%}")
                a.markdown(describe_tracklet(t))
                a.caption(f"Best view at {fmt_time(t['best_t'])} (frame {int(t['best_t'] * t['fps'])})")
                b.image(t["crop_paths"], width=90)
                ev = pd.DataFrame({"evidence": list(f), "value": [round(v, 3) for v in f.values()]})
                c.dataframe(ev, hide_index=True, height=200)
                with st.expander("Frame evidence"):
                    st.image(t["frame_path"])

# ------------------------------------------------------------------ track review
with tabs[3]:
    st.subheader("Manual tracking check")
    st.write("Tick tracklets that contain a single vehicle with no ID switch. This gives the manually checked "
             "tracking accuracy reported for the demo clips (proposal: Data Sources and Known Limitations).")
    if len(index):
        vid = st.selectbox("Video", index.videos(), key="review_video")
        ts = [t for t in index.tracklets if t["video"] == vid]
        review_file = config.RESULTS_DIR / f"tracking_review_{vid}.csv"
        prev = pd.read_csv(review_file).set_index("uid")["clean"].to_dict() if review_file.exists() else {}
        for row_start in range(0, len(ts), 8):
            for col, t in zip(st.columns(8), ts[row_start:row_start + 8]):
                col.image(t["crop_paths"][0], caption=f"track {t['track_id']}")
        df = pd.DataFrame([{"uid": t["uid"], "track": t["track_id"], "detections": t["n_obs"],
                            "duration_s": round(t["end_t"] - t["start_t"], 1), "clean": bool(prev.get(t["uid"], True))}
                           for t in ts])
        edited = st.data_editor(df, hide_index=True, disabled=["uid", "track", "detections", "duration_s"],
                                key=f"editor_{vid}")
        if st.button("Save review"):
            edited[["uid", "clean"]].to_csv(review_file, index=False)
            st.success(f"Saved {review_file.name}: {edited['clean'].mean():.0%} of {len(edited)} tracklets are clean.")

# ------------------------------------------------------------------ SOM
with tabs[4]:
    st.subheader("Self-Organizing Map of vehicle appearance embeddings")
    st.write("Unsupervised: no identity labels are used. Nearby nodes hold visually similar vehicles; "
             "darker U-matrix cells mark boundaries between groups.")
    if index.som is None:
        st.info("Needs at least 4 tracklets in the index.")
    else:
        som = index.som
        bmus = som.bmus(index.matrix("app_emb"))
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.imshow(som.u_matrix().T, cmap="bone_r", origin="lower")
        rng = np.random.default_rng(0)
        for (i, j), t in zip(bmus, index.tracklets):
            ax.scatter(i + rng.uniform(-.3, .3), j + rng.uniform(-.3, .3), s=25, edgecolors="k",
                       c=config.COLORS[int(np.argmax(t["color_probs"]))].replace("golden", "goldenrod"))
        ax.set_title(f"{som.grid}x{som.grid} SOM · dots = tracklets (predicted colour)")
        c1, c2 = st.columns([1, 1])
        c1.pyplot(fig)
        nodes = defaultdict(list)
        for b, t in zip(bmus, index.tracklets):
            nodes[b].append(t)
        with c2:
            for node, members in sorted(nodes.items(), key=lambda kv: -len(kv[1]))[:10]:
                st.markdown(f"**Node {node}** – {len(members)} tracklets")
                st.image([m["crop_paths"][0] for m in members[:8]], width=70)

# ------------------------------------------------------------------ evaluation
with tabs[5]:
    st.subheader("Benchmark evaluation (VeRi-776)")
    mfile = config.RESULTS_DIR / "metrics.json"
    if not mfile.exists():
        st.info("Run `python scripts/train_eval.py` after downloading VeRi-776 to data/VeRi (see README).")
    else:
        m = json.loads(mfile.read_text())
        st.caption(f"Setup: {m['setup']}")
        if m.get("attributes"):
            st.markdown("**Attribute recognition accuracy (%)** – CLIP zero-shot vs supervised linear probe")
            st.dataframe(pd.DataFrame(m["attributes"]).T.round(1))
        if m.get("description_search"):
            st.markdown("**Stage 1 – description search** (query = true attributes of a test vehicle)")
            st.dataframe(pd.DataFrame(m["description_search"]).T.round(1))
        st.markdown("**Stage 2 – cross-camera Re-ID by plate visibility** (Rank-1 / Rank-5 / mAP %)")
        level = st.radio("Plate visibility", list(m["reid"]), horizontal=True)
        st.dataframe(pd.DataFrame(m["reid"][level]).T.round(1).sort_values("mAP", ascending=False))
        st.markdown("**SOM** – purity and candidate pre-filtering (plates hidden, Random Forest)")
        st.json(m["som"], expanded=False)
        imgs = [p for p in ("plate_robustness.png", "ablation.png", "rf_importance.png", "som_umatrix.png")
                if (config.RESULTS_DIR / p).exists()]
        for col, p in zip(st.columns(2) * 2, imgs):
            col.image(str(config.RESULTS_DIR / p))
