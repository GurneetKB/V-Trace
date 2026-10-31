# Demo video data

The end-to-end demo uses openly licensed traffic recordings from Wikimedia Commons. The videos themselves are
not committed (see `.gitignore`). Download them into `data/videos/raw/` with the names below, then run
`python scripts/prepare_demo_clips.py`.

| Saved as | Commons file | Licence | Author |
|---|---|---|---|
| `ljubljana_a.webm` | [Road traffic in Ljubljana.webm](https://commons.wikimedia.org/wiki/File:Road_traffic_in_Ljubljana.webm) | CC BY 3.0 | Sounds of Changes |
| `ljubljana_b.webm` | [Road traffic in Ljubljana – soundscape 1.webm](https://commons.wikimedia.org/wiki/File:Road_traffic_in_Ljubljana_%E2%80%93_soundscape_1.webm) | CC BY 3.0 | Sounds of Changes |

## Demo cameras

Clip A is a wide 1080p shot of a street that vehicles cross from one side to the other in 5–10 s. It is cut into
three non-overlapping zones along the road, with gaps between them, and each zone gets its own exposure, colour cast
and sharpness, like three cameras placed along the street (`docs/figures/demo_zones.jpg`).

| Camera | Built from | Purpose |
|---|---|---|
| `camA_west` | clip A, 1–46 s, left zone (x 0–560, y 380–940) | reference camera |
| `camB_centre` | clip A, middle zone (x 680–1240); darker, colder, slightly soft | second camera on the same street |
| `camC_east` | clip A, right zone (x 1360–1920); warmer, higher contrast | third camera on the same street |
| `camD_other_road` | clip B, 1–31 s, 720p | a different road: distractor camera, its vehicles never appear in A–C |

A car on the near lane is seen in camA, then camB, then camC (far lane: C → B → A), with real changes in scale and
viewpoint, so the app's **traced path** can follow it camera by camera.

Public multi-camera traffic datasets with re-appearing vehicles (e.g. CityFlow) require a data-use request, so the
three cameras are zones of one recording. This is stated wherever demo results are reported. The VeRi-776 benchmark
provides the separate-camera evaluation.

## Curated camera details

The clips carry no location or clock metadata, so the demo cameras get curated details placed in Singapore
(`vtrace/cameras.py`, editable on the app's **Cameras** page). camA–camC are zones of one recording, so they share one
clock and are placed about 80 m apart along Orchard Road; camD is a different road and is given a later recording
start. The upload test pack (`test_videos/`, `scripts/make_test_videos.py`) is cut from the same recordings and gets
curated details the same way.

| Camera | Location (curated) | Recording start (curated) |
|---|---|---|
| `camA_west` | Orchard Road, west of Scotts Road · Singapore | Wed 28 Oct 2026, 08:15:00 |
| `camB_centre` | Orchard Road at the Scotts Road junction · Singapore | Wed 28 Oct 2026, 08:15:00 |
| `camC_east` | Orchard Road, east of Scotts Road · Singapore | Wed 28 Oct 2026, 08:15:00 |
| `camD_other_road` | Bukit Timah Road near Newton Circus · Singapore | Wed 28 Oct 2026, 08:17:30 |

A sighting's real-world time = the camera's recording start + its position in the video.

## Demo evaluation

`python scripts/demo_eval.py` tracks the uncropped clip once, maps every camera tracklet back onto it by box overlap
(pseudo ground truth), and reports tracking quality, cross-camera Re-ID and path-tracing accuracy in
`results/demo_eval.json`, together with the best demo vehicles (`docs/DEMO_GUIDE.md` uses them).
