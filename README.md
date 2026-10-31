# V-Trace: Multi-Attribute Vehicle Re-Identification System

**Describe → Rank → Select → Trace**

V-Trace processes short dash-cam / traffic-cam videos (one video = one camera) into *sightings*: every vehicle is
detected, followed while it stays in view, and described. You then describe the vehicle you are looking for (colour,
type, plate, distinctive features, free text), pick it from a ranked list of best matches, and V-Trace shows every
camera it was seen in, with the time span and one frame from each sighting.

V-Trace uses **only pretrained, published models**. Nothing is trained for this project.

```
Videos ─► YOLO11 detection ─► ByteTrack tracking ─► sightings (tracklets) ─► descriptors ─► index
                                                                              │
          FastReID VeRi-776 Re-ID embedding · CLIP zero-shot colour/type/features · EasyOCR plate
                                                                              │
 Description ─► ranked best matches ─► user selects one ─► same vehicle in every camera (FastReID similarity)
                                                            ─► camera, time span and a frame per sighting
```

| Step | Model | Source |
|---|---|---|
| Detect vehicles | YOLO11n, COCO classes car / motorcycle / bus / truck | Ultralytics |
| Follow a vehicle while it is in view | ByteTrack | Ultralytics |
| Colour, type, distinctive features, free text | CLIP ViT-B/32, zero-shot | OpenAI, via open_clip |
| Licence plate | EasyOCR | JaidedAI |
| Same vehicle in another camera | FastReID SBS(R50-ibn), trained on VeRi-776 | [JDAI-CV/fast-reid](https://github.com/JDAI-CV/fast-reid) (released by the VeRi-776 authors' team) |

---

## 1. Setup (Windows + VS Code)

```bash
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

The first run downloads the pretrained weights automatically: YOLO11n (~6 MB), the FastReID VeRi-776 checkpoint
(~200 MB, into `models/`), CLIP ViT-B/32 (~350 MB) and EasyOCR (~100 MB). A GPU is optional.

## 2. Run the app

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml     # then set the admin username / password
.venv\Scripts\python -m streamlit run app.py
```

Open http://localhost:8501 and sign in. The app opens in dark mode (⋮ → Settings → Theme to switch).

1. **Videos (sidebar).** *Demo videos* are already processed: four cameras, three along one street (so the same
   cars pass A → B → C) and one on another road. *Upload new videos* takes your own short clips; **Process videos**
   runs detection, tracking and description (*Fast processing* = every 5th frame, no plate OCR).
2. **Describe the vehicle.** Colour, type, plate (`?` = unknown character), distinctive features, free text. Any
   field can be left empty. **Search** returns the best-matching sightings, ranked.
3. **Select** the right one.
4. **Where this vehicle was seen** lists every camera: the time span, a crop and one full frame of each sighting, plus
   the route in time order. Cameras where nothing passed the Re-ID threshold show the closest vehicle and its score.
   The threshold is in the sidebar under *Settings*.

The **How it works** page lists the models and the benchmark numbers.

### Deploy on Streamlit Community Cloud

The repo includes `requirements.txt` (CPU PyTorch), `packages.txt` and the pre-processed demo cameras
(`demo_bundle/`), so the hosted app shows the demo instantly. On share.streamlit.io create an app from
`GurneetKB/V-Trace`, branch `main`, file `app.py`, Python 3.11, and paste the `[admin]` block from
`.streamlit/secrets.toml.example` into **Secrets**. If it runs out of memory, add `VTRACE_OCR = "0"`.

## 3. Evaluation

**VeRi-776 benchmark (the Re-ID model as published, no training).** Download VeRi-776
(https://github.com/VehicleReId/VeRidataset) to `C:\Users\<you>\VeRi` (or set `VTRACE_VERI_DIR`), then:

```bash
.venv\Scripts\python scripts/eval_veri.py        # Rank-1 / Rank-5 / mAP -> results/veri_eval.json
```

**Demo cameras.** `scripts/demo_eval.py` builds a pseudo ground truth (the three street cameras are crops of one
video, so tracking the full video gives each vehicle one identity) and measures Re-ID ranking and whether each
vehicle is reported in exactly the right cameras → `results/demo_eval.json`.

```bash
.venv\Scripts\python scripts/build_index.py data/videos/cam*.mp4    # process the demo cameras
.venv\Scripts\python scripts/demo_eval.py
.venv\Scripts\python scripts/export_demo_bundle.py                   # refresh the bundle used by the app
```

Unit tests (synthetic data, no models): `.venv\Scripts\python -m pytest -q`.

## 4. Project structure

```
V-Trace/
├── app.py                 Streamlit UI: sign-in, videos, describe → ranked matches → where seen
├── vtrace/
│   ├── config.py          settings and vocabularies
│   ├── video.py           YOLO11 detection + ByteTrack tracking → sightings, crops, evidence frames
│   ├── fastreid.py        loads the FastReID VeRi-776 checkpoint with plain PyTorch, crop → embedding
│   ├── features.py        Re-ID embedding, CLIP zero-shot colour/type/features, EasyOCR plate
│   ├── index.py           searchable index of sightings (save/load, demo bundle)
│   ├── search.py          description → ranked sightings
│   ├── reid.py            selected sighting → same vehicle in every camera
│   └── plate.py           plate normalisation and wildcard matching
├── scripts/               build_index, eval_veri, demo_eval, prepare_demo_clips, export_demo_bundle, ...
├── demo_bundle/           pre-processed demo cameras
└── data/videos/           input videos
```

## 5. Scope and limitations

Results are ranked candidates for a person to review, not a definitive identification. Known failure modes:
very small or distant vehicles, strong viewpoint changes, night scenes, occlusion, near-identical vehicles, plates
too small to read, and tracks that break or switch between two vehicles. Colour and type come from CLIP zero-shot
and can be wrong for silver/grey cars; distinctive features (spoiler, dent, decal) are a soft hint, never a guarantee.
