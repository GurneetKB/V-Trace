# V-Trace: Multi-Attribute Vehicle Re-Identification System

**Describe → Search → Confirm → Re-identify**

V-Trace takes uploaded traffic/CCTV videos (one video = one camera) and turns them into a searchable index of
tracked vehicles. You describe the target with whatever you know (colour, type, full or partial plate,
distinctive cues), confirm the most plausible candidate, and V-Trace then searches the other videos for that
vehicle. It combines appearance, colour, type, plate and track evidence and returns **ranked sightings with
frames and timestamps for a person to review**. It does not claim a definitive identification.

```
Videos ─► YOLO detection ─► ByteTrack tracking ─► tracklets ─► descriptors (CNN, CLIP, HSV, OCR) ─► index
                                                                                                 │
 User description ─► Stage 1 ranked candidates ─► human CONFIRM ─► Stage 2 cross-video Re-ID ◄───┘
                                                                     (SOM pre-filter, weighted fusion / Random Forest)
                                                                                 │
                                                       ranked sightings + frames + timestamps
```

---

## 1. Setup (Windows + VS Code)

1. Open the `V-Trace` folder in VS Code (**File → Open Folder…**).
2. Open a terminal (**Terminal → New Terminal**) and create the environment. You only do this once:

```bash
py -3.11 -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

3. When VS Code asks, select the interpreter `.venv` (or use **Ctrl+Shift+P → Python: Select Interpreter**).
   You also need the **Python** extension from Microsoft.

> The `.venv` is already set up on this machine, so you can skip step 2 here. PyTorch is pinned to 2.5.1
> because Windows Smart App Control blocks the DLLs of the newest PyTorch release.

The first run downloads the pretrained weights automatically: YOLO11n (~6 MB), ResNet-50 (~100 MB),
CLIP ViT-B/32 (~350 MB) and EasyOCR (~100 MB). A GPU is optional; on a CPU, processing a short clip takes a
few minutes.

## 2. Run the app

From the VS Code **Run and Debug** panel, choose **"V-Trace: Streamlit app"** and press ▶. You can also run:

```bash
.venv\Scripts\python -m streamlit run app.py
```

A browser tab opens at http://localhost:8501.

**Admin sign-in.** The app opens on a sign-in page. Set the admin account once:

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Then edit `username` and `password` in `.streamlit/secrets.toml`. This file is git-ignored, so the password never reaches GitHub.
You can also set the `VTRACE_ADMIN_USER` and `VTRACE_ADMIN_PASSWORD` environment variables instead.
With no account configured, the app stays locked and says how to set one up. **Sign out** is at the top of the sidebar.

**Theme.** The app uses the teal/navy palette from the proposal deck and opens in **dark mode**.
To switch to light (or back), use the **⋮** menu (top right) → **Settings** → **Theme**. The browser remembers the choice.

| Tab | What it does |
|---|---|
| **1 · Upload videos** | Upload or select the camera videos for this session and click **Process videos**. Only these videos are searched in steps 2–3. A video already processed with the same speed setting loads instantly from the cache in `data/index/`. |
| **2 · Describe & search** | **Stage 1.** Enter colour, type, partial plate (`?` = unknown character), cues and free text. You get ranked candidate tracklets with the evidence for each field. Click **Confirm** on one. |
| **3 · Confirm & re-identify** | **Stage 2.** The confirmed tracklet becomes the visual query. Ranked sightings from the other videos, with the method (appearance only / weighted fusion / Random Forest), an optional SOM pre-filter, timestamps, the pairwise evidence and the frame. |
| **Track review** | Tick the clean tracklets (no ID switch) to get a manually checked tracking accuracy for the demo clips. |
| **SOM (unsupervised)** | U-matrix of the vehicle embeddings, with crops grouped by map node. |
| **Evaluation** | Benchmark results produced by `scripts/train_eval.py`. |

**Processing speed.** Tab 1 has three presets. Times are for a 30 s, 720p clip on an 8-core laptop CPU:

| Preset | Frames analysed | Plate OCR | Time |
|---|---|---|---|
| Fast | every 5th | off | ~20 s |
| Balanced (default) | every 3rd | only on vehicles wide enough for a legible plate | ~40 s |
| Detailed | every 2nd | on | slowest |

On the command line, the equivalent is `python scripts/build_index.py --stride 5 --no-ocr`.

### Deploy the demo on Streamlit Community Cloud (optional)

The repo is ready for https://share.streamlit.io. It includes `requirements.txt` (CPU-only PyTorch), `packages.txt`
(the system libraries OpenCV needs) and `.streamlit/config.toml`.

1. Push the repo to GitHub.
2. On share.streamlit.io, click **Create app** and pick the repo, branch `main` and main file `app.py`.
3. Under **Advanced settings**, choose Python **3.11**. If the app runs out of memory, add `VTRACE_OCR = "0"`
   under Secrets/Environment to turn EasyOCR off.
4. Under **Secrets**, paste the `[admin]` block from `.streamlit/secrets.toml.example` with your own username and
   password. Without it, the deployed app stays locked.
5. Click **Deploy**. The first boot installs PyTorch and downloads the model weights, which takes a few minutes.

Community Cloud runs on a small CPU, so keep demo clips short (10–30 s). Processing locally and presenting from
`localhost` is the most reliable option for a live demo.

**Quick smoke test without real footage:** in tab 1, click **"Generate two sample camera clips"**, or run `python scripts/make_sample_videos.py`, then process
`sample_camA.mp4` and `sample_camB.mp4` in tab 1.

**Real-footage demo:** follow [docs/DEMO_DATA.md](docs/DEMO_DATA.md) to download two CC-BY Ljubljana traffic
clips, then run:

```bash
.venv\Scripts\python scripts/prepare_demo_clips.py
```

```bash
.venv\Scripts\python scripts/build_index.py data/videos/camA_main_road.mp4 data/videos/camB_second_view.mp4 data/videos/camC_other_road.mp4
```

```bash
.venv\Scripts\python scripts/demo_walkthrough.py --color white --cue "sticker / decal" --confirm-video camA_main_road
```

The last command saves a scripted Describe → Search → Confirm → Re-identify run to `results/demo/`, including
the evidence images and a Markdown summary for the report.

**Troubleshooting (Windows):** an error saying *"An Application Control policy has blocked this file"* comes from
Windows Smart App Control. It is sometimes intermittent; run the command again. If it keeps happening for one
package, reinstall an older, widely used version of that package.

## 3. Benchmark data (VeRi-776) and training

1. Request VeRi-776 from https://github.com/VehicleReId/VeRi (a mirror is also on Kaggle).
2. Unzip it so you get `image_train/`, `image_test/`, `train_label.xml` and `test_label.xml` inside one folder.
   V-Trace looks for that folder in this order:
   - the `VTRACE_VERI_DIR` environment variable;
   - `data/VeRi/`;
   - `C:\Users\<you>\VeRi`.

   Keeping it outside the project avoids syncing ~1–2 GB if the project is in OneDrive.
3. Run (or use the **"V-Trace: train + evaluate on VeRi-776"** launch config):

```bash
.venv\Scripts\python scripts/train_eval.py
```

The defaults use a manageable subset: 150 training and 100 test vehicles, identity-disjoint. Increase them with
`--train-ids` and `--test-ids`. Features are cached in `data/cache/`, so re-runs are quick. The script writes:

* `models/rf_matcher.joblib`: the Random Forest same/different-vehicle matcher. The app uses it automatically.
* `models/attr_probe.joblib`: the supervised colour/type classifier (a linear probe on CLIP embeddings).
* `results/metrics.json` and plots: `plate_robustness.png`, `ablation.png`, `rf_importance.png`, `som_umatrix.png`.

Without VeRi the app still runs. It uses CLIP zero-shot attributes and the weighted-fusion matcher.

### Experiments (all from the proposal)

| # | Experiment | Metric |
|---|---|---|
| 1 | Attribute recognition: CLIP zero-shot vs supervised linear probe | colour/type accuracy |
| 2 | Stage-1 description search (colour + type, partial plate, both) | Rank-1, Rank-5, mAP |
| 3 | Cross-camera Re-ID: each single cue vs weighted fusion vs Random Forest (ablation) | Rank-1, Rank-5, mAP |
| 4 | Plate robustness: clear → partial → blurred → hidden | mAP per level |
| 5 | SOM: cluster purity (ID/colour/type) and pre-filter recall vs candidate reduction | purity, recall, mAP |

*Note:* VeRi-776 has no plate text, so every vehicle identity gets a synthetic plate string, which is then
degraded per observation. This isolates the hypothesis that multi-evidence retrieval degrades more gracefully
when plate evidence fails. Real plates in the demo videos come from EasyOCR.

### Unit tests

The matching logic (plate matching, Stage-1 search, pairwise features, fusion, Random Forest, SOM) is tested on
synthetic tracklets, so the tests need no models or downloads:

```bash
.venv\Scripts\python -m pytest -q
```

## 4. How the four technique groups are covered

| Technique group | Where in the code |
|---|---|
| **Supervised / unsupervised learning** | Random Forest same/different matcher and the colour/type linear probe (`vtrace/reid.py`, `scripts/train_eval.py`). SOM + PCA over embeddings (`vtrace/som.py`). |
| **Machine / deep learning** | YOLO11 detector (`vtrace/video.py`), ResNet-50 appearance embeddings, CLIP vision-language cues, EasyOCR (`vtrace/features.py`) |
| **Hybrid / ensemble** | Random Forest fuses appearance, CLIP, colour histogram, colour/type agreement, plate, cue and track features. The weighted fusion baseline is in `vtrace/reid.py`. |
| **Intelligent sensing / sense-making** | Raw video → detections → tracks → tracklets → descriptors → candidates → confirmed target → sightings (`vtrace/video.py`, `vtrace/index.py`, `app.py`) |

## 5. Project structure

```
V-Trace/
├── app.py                    Streamlit UI (admin sign-in + the whole human-in-the-loop workflow)
├── assets/                   NUS-ISS logo shown on the sign-in page and sidebar
├── vtrace/
│   ├── config.py             all settings, vocabularies, fusion weights
│   ├── video.py              ingestion, YOLO detection, ByteTrack tracking, tracklets + evidence frames
│   ├── features.py           ResNet-50, CLIP colour/type/cues, HSV histogram, EasyOCR plate
│   ├── index.py              searchable vehicle index (save/load, SOM fitting)
│   ├── search.py             Stage 1: description-to-vehicle retrieval
│   ├── reid.py               Stage 2: pairwise evidence, weighted fusion, Random Forest
│   ├── som.py                Self-Organizing Map (unsupervised)
│   ├── plate.py              plate normalisation, wildcard matching, degradation simulation
│   └── veri.py               VeRi-776 loader (images grouped into tracklets)
├── scripts/
│   ├── build_index.py        index videos from the command line
│   ├── train_eval.py         train RF + probe, run all experiments
│   └── make_sample_videos.py synthetic smoke-test clips
├── data/videos/              your input videos
├── models/  results/         generated
├── .streamlit/               theme (light + dark), server settings, secrets.toml.example
└── .vscode/                  launch configs + interpreter setting
```

## 6. Scope and limitations

**In scope:** uploaded videos, detection, tracking, tracklets, colour/type/plate/appearance/cue descriptors,
description search, human confirmation, SOM, fusion, cross-video Re-ID, and ranked results with frames and timestamps.
**Out of scope:** live CCTV networks, owner records, facial recognition, definitive forensic identification,
and training large networks from scratch.

Known failure modes: viewpoint change (front vs rear), night scenes, low resolution, occlusion, near-identical
vehicles, unreadable plates and OCR errors, detector misses and track fragmentation. Distinctive cues (dents,
decals) come from CLIP text-image similarity over a small controlled vocabulary. They are supporting evidence
only and are never guaranteed detections. A frame-based pipeline could later take live stream frames in place
of files.
