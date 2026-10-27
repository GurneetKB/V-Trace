# Demo video data

The end-to-end demo uses openly licensed traffic recordings from Wikimedia Commons. The videos themselves are
not committed (see `.gitignore`). Download them into `data/videos/raw/` with the names below, then run
`python scripts/prepare_demo_clips.py`.

| Saved as | Commons file | Licence | Author |
|---|---|---|---|
| `ljubljana_a.webm` | [Road traffic in Ljubljana.webm](https://commons.wikimedia.org/wiki/File:Road_traffic_in_Ljubljana.webm) | CC BY 3.0 | Sounds of Changes |
| `ljubljana_b.webm` | [Road traffic in Ljubljana – soundscape 1.webm](https://commons.wikimedia.org/wiki/File:Road_traffic_in_Ljubljana_%E2%80%93_soundscape_1.webm) | CC BY 3.0 | Sounds of Changes |

## Demo cameras

| Camera | Built from | Purpose |
|---|---|---|
| `camA_main_road` | clip A, 1–31 s | real footage, main camera |
| `camB_second_view` | clip A, 2.5–32.5 s, re-framed (crop + zoom), darker, colder colours | **simulated** second viewpoint of the same road: the same vehicles reappear, so cross-camera Re-ID has a true match |
| `camC_other_road` | clip B, 1–31 s | real footage of a different road: distractor camera |

Public multi-camera traffic datasets with re-appearing vehicles (e.g. CityFlow) require a data-use request, so
the second viewpoint is simulated. This is stated wherever demo results are reported. Quantitative cross-camera
Re-ID performance comes from VeRi-776, not from these clips.

## Demo run (results/demo/)

`python scripts/demo_walkthrough.py --color white --cue "sticker / decal" --confirm-video camA_main_road`
on 173 tracklets (camA 71, camB 70, camC 32). No Random Forest is trained yet, so Stage 2 uses weighted fusion.

- **Stage 1:** the top candidate is the white estate car with the "PRVA" logo decal in camA (score 0.98: colour 1.00, decal cue 0.93). See `stage1.jpg`.
- **Stage 2:** after confirming it, the #1 sighting is the same car in camB (fusion 0.70, ResNet cosine 0.89, CLIP cosine 0.88). The next candidates are visibly different vehicles (scores 0.60–0.64). See `stage2.jpg`.
- **Observed failure modes** (for the report):
  - *Attribute error:* CLIP labels the estate car as an "mpv".
  - *Track fragmentation:* one vehicle is split into several tracklets when it is occluded by buses or by the frame edge. Examples: the yellow Post van and the "Alan Ford" bus in `tracklets_camA_main_road.jpg`.
  - *Background tracklets:* parked cars that are partly occluded give blurry, low-information crops.
  - *Plates:* no plate was read at this distance, so plate evidence was unavailable. This is the scenario V-Trace is designed for.
- **Manual tracking check:** tick the clean tracklets in the app's *Track review* tab. The contact sheets `tracklets_*.jpg` show the first crop of every tracklet.
