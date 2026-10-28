# V-Trace – Final Project Report (draft)

**Project:** V-Trace | Multi-Attribute Vehicle Re-Identification System
**Group 21:** Gurneet Kaur Bhuller (A0354164E)
**Course:** Pattern Recognition Systems – Practice Module

> **Draft status.** Sections 1–5, 7 and 8 are drafted from the proposal and the implemented system.
> VeRi-776 results (Section 6) are from `python scripts/train_eval.py` (PR #16; all tables in `results/tables.md`).
> Remaining **TODO**s: app screenshots, the manual tracking check (Track review tab) and demo failure screenshots.

---

## 1. Background and problem

Vehicle re-identification (Re-ID) means deciding whether a vehicle seen by one camera is likely the same vehicle seen by another.
A licence plate is the strongest single identifier, but CCTV footage often can't read it: the plate may be too small,
blurred by motion, occluded, badly lit or facing away from the camera. Investigators also rarely start with a clean image.
They usually start with a partial description, such as "a white SUV, plate starting SGX12, dent on the rear door".

V-Trace treats vehicle search as a **two-stage, multi-evidence pattern-recognition problem**. It uses the plate when
the plate is readable, but never depends on it alone.

## 2. Objective and scope

**Objective.** Build a runnable system that:
- processes uploaded traffic/CCTV videos;
- lets a user describe a target with whatever cues they have (colour, type, full or partial plate, distinctive cues);
- returns ranked candidate vehicles;
- after the user confirms a candidate, re-identifies that vehicle across the other videos, with video, timestamp and frame evidence.

The system demonstrates all four Practice Module technique groups.

| In scope | Out of scope |
|---|---|
| Uploaded multi-camera videos; detection; within-video tracking; tracklets | Operational live CCTV networks |
| Colour / type / plate / appearance / distinctive-cue descriptors | Vehicle-owner records |
| Description-based retrieval; human confirmation | Facial recognition of occupants |
| SOM, weighted fusion, Random Forest, cross-video Re-ID | Definitive forensic identification |
| Ranked results with frames and timestamps in a Streamlit app | Training large detection / Re-ID networks from scratch |

The output is always a **ranked list for human review**, never an identity claim.

## 3. System design

```
Videos ─► YOLO11 detection ─► ByteTrack tracking ─► tracklets ─► descriptors ─► vehicle index
                                                                                     │
User description ─► Stage 1 ranked candidates ─► human CONFIRM ─► Stage 2 Re-ID ◄────┘
                                                   (SOM pre-filter · weighted fusion / Random Forest)
                                                                     │
                                          ranked sightings + frames + timestamps
```

### 3.1 Video ingestion, detection and tracking (`vtrace/video.py`)
- Each uploaded video is treated as one camera.
- A pretrained YOLO11n detector (COCO classes car, motorcycle, bus, truck) runs on every second frame.
- ByteTrack links detections into tracks within each video.
- Tracks with fewer than 4 detections are discarded as noise.
- For each **tracklet**, V-Trace keeps four high-quality crops that are spread out in time. Quality is box area × confidence, halved when the box is cut off by the frame edge.
- It also saves one annotated evidence frame per tracklet, showing camera, track id and timestamp.

### 3.2 Vehicle representation and indexing (`vtrace/features.py`, `vtrace/index.py`)
Each tracklet is summarised by complementary descriptors averaged over its crops:

| Descriptor | Model | Role |
|---|---|---|
| Appearance embedding (2048-d) | ResNet-50, ImageNet-pretrained | main visual Re-ID cue |
| CLIP image embedding (512-d) | CLIP ViT-B/32 | second appearance cue; basis for colour, type and cues |
| Colour & type probabilities | CLIP zero-shot, or a supervised linear probe trained on VeRi labels | description search; attribute agreement |
| HSV colour histogram (16×4×4) | hand-crafted | colour similarity |
| Distinctive-cue scores | CLIP text-image similarity over a controlled vocabulary (roof rack, spoiler, dent, decal, roof cargo) | optional supporting evidence |
| Plate text | EasyOCR, kept only when confidently read | strong evidence when available |
| Track consistency | mean cosine of crops to the tracklet centroid | track-level reliability |

No single descriptor is required. A missing descriptor lowers confidence but never blocks a search.

### 3.3 Stage 1 – description-to-vehicle retrieval (`vtrace/search.py`)
- Each field the user provides gets a score in [0, 1]:
  - colour and type probability, relative to the tracklet's top class;
  - wildcard-aware plate similarity: `?` stands for an unknown character, and partial plates are matched against any part of the plate;
  - CLIP cue scores and free-text scores.
- The final score is a weighted mean **over the provided fields only**.
- A tracklet whose plate could not be read gets a neutral plate score rather than zero, so it is not excluded.

### 3.4 Stage 2 – confirmed-candidate cross-camera Re-ID (`vtrace/reid.py`)
After confirmation, the selected tracklet becomes the visual query. For every tracklet in the other videos, V-Trace
computes a 10-dimensional pairwise evidence vector:
- appearance cosine;
- CLIP cosine;
- colour-histogram intersection;
- colour agreement and type agreement;
- plate similarity, plus a flag for whether both plates were read;
- cue agreement;
- track quality and track consistency.

Three scorers are compared:
1. **Appearance only** (baseline): ResNet-50 cosine.
2. **Weighted fusion** (transparent baseline): fixed weights. The plate weight is used only when both plates were read.
3. **Random Forest** (ensemble): 300 trees, class-balanced, trained on labelled same/different-vehicle pairs.

### 3.5 Unsupervised SOM (`vtrace/som.py`)
- Appearance embeddings are reduced with PCA (32-d) and mapped onto a Self-Organizing Map. Grid size follows the 5√N heuristic.
- No identity labels are used.
- The SOM is used to (a) visualise groups of similar vehicles (U-matrix) and (b) optionally pre-filter Re-ID candidates to map nodes near the query's best-matching unit.

### 3.6 Streamlit interface (`app.py`)
The app has six tabs:
1. **Upload & index:** upload videos and build the index.
2. **Describe & search:** Stage 1 search, ending with a **Confirm** button on each candidate.
3. **Confirm & re-identify:** Stage 2 results, with a method selector, the SOM pre-filter, the evidence table and the frame.
4. **Track review:** manual tracking check.
5. **SOM:** the map of similar vehicles.
6. **Evaluation:** the benchmark results.

A sidebar shows the system status. **TODO:** add one screenshot per tab.

## 4. Technique group mapping

| Technique group | Implementation in V-Trace | Evidence |
|---|---|---|
| 1. Supervised / unsupervised learning | Random Forest same/different-vehicle matcher; supervised colour/type linear probe on CLIP embeddings; unsupervised SOM (+ PCA) over appearance embeddings | RF retrieval metrics; probe vs zero-shot accuracy; SOM purity and pre-filter recall |
| 2. Machine / deep learning | YOLO11 detector, ResNet-50 embeddings, CLIP vision-language model, EasyOCR | appearance-only Rank-1/5, mAP; attribute accuracy |
| 3. Hybrid / ensemble | Random Forest fusing 10 evidence features vs weighted fusion vs single cues | ablation; plate-degradation robustness |
| 4. Intelligent sensing / sense-making | raw video → detections → tracks → tracklets → descriptors → candidates → confirmed target → sightings | end-to-end Streamlit demo |

## 5. Data and experimental protocol

**VeRi-776** (Liu et al.) is the benchmark. It has more than 50,000 images of 776 vehicles from 20 cameras, with colour and type labels.
- Images of the same vehicle in the same camera are consecutive frames of one pass, so they are grouped into **tracklets**, the same unit the video pipeline produces.
- For each tracklet, four images are sampled evenly.
- Training uses identities from `image_train`; testing uses identities from `image_test`. The two sets are **identity-disjoint**, which prevents data leakage.
- Subset: **150 training vehicles (1,290 tracklets)** and **100 test vehicles (830 tracklets)**, chosen at random with seed 0.

**Re-ID protocol.**
- Each test tracklet is a query.
- The gallery is every test tracklet from other cameras.
- A match is relevant if it has the same vehicle id.
- Metrics: Rank-1, Rank-5 and mAP.

**Random Forest training.**
- Positives: all same-vehicle, different-camera tracklet pairs (capped).
- Negatives: three times as many as positives. Half are random different-vehicle pairs; half are *hard* negatives with the same predicted colour and type.
- 6,000 positive and 18,000 negative pairs in total.
- Colour/type probabilities for the training pairs come from **out-of-fold** probes (5-fold `GroupKFold` by vehicle). See Section 7 for why.
- The forest uses **monotonic constraints**: a higher similarity on any cue can never lower the match score.

**Plate robustness.**
- VeRi has no plate text, so each identity gets a synthetic Singapore-style plate.
- That plate is degraded per observation at four levels:
  - *clear*: occasional single OCR slip;
  - *partial*: about 45% of characters unknown;
  - *blurred*: about 45% confusable substitutions, sometimes a dropped character;
  - *hidden*: no plate.
- The RF is trained on a mixture of all four levels.
- Testing is done at each level separately, which isolates the main hypothesis.

**Demo clips** (`docs/DEMO_DATA.md`).
- Source: two CC BY 3.0 Ljubljana road-traffic recordings from Wikimedia Commons.
- Three 30 s, 720p cameras:
  - camA: real footage.
  - camB: a **simulated** second viewpoint of the same road (re-framed, darker, colder colours, 1.5 s offset).
  - camC: a different road, used as a distractor.
- Tracking quality is checked manually in the Track review tab.

## 6. Results

All numbers are for the VeRi-776 test subset (100 vehicles, 830 tracklets). Re-ID uses 300 query tracklets.

### 6.1 Attribute recognition (accuracy %, 830 test tracklets)
| Attribute | CLIP zero-shot | Supervised linear probe |
|---|---|---|
| Colour | 67.0 | **72.9** |
| Type | 38.3 | **79.3** |

The supervised probe roughly doubles type accuracy. Zero-shot CLIP confuses sedan, hatchback and estate.

### 6.2 Stage 1 – description search (query = a test vehicle's true attributes)
| Query | Rank-1 | Rank-5 | mAP |
|---|---|---|---|
| colour + type | 16.0 | 45.0 | 19.1 |
| partial plate only | 21.0 | 49.0 | 21.6 |
| colour + type + partial plate | **58.0** | **84.0** | **40.9** |

Each cue alone is weak, but together they put the right vehicle in the top 5 for 84% of queries. That's what Stage 1 needs: a short list for the human to confirm from.

### 6.3 Stage 2 – Re-ID ablation, plates hidden
| Method | Rank-1 | Rank-5 | mAP |
|---|---|---|---|
| Random Forest (all cues) | 56.0 | 79.0 | **29.7** |
| CLIP cosine only | 58.3 | 75.7 | 28.2 |
| Weighted fusion | 54.7 | 74.7 | 27.8 |
| ResNet-50 appearance only | **61.3** | **79.3** | 27.1 |
| HSV colour histogram only | 24.0 | 44.3 | 12.7 |
| colour agreement only | 5.3 | 16.3 | 11.3 |
| type agreement only | 7.0 | 18.0 | 10.3 |
| distinctive-cue agreement only | 13.0 | 30.7 | 9.1 |

Appearance embeddings carry most of the signal. Colour, type and cues are too coarse to rank on their own.

### 6.4 Plate-degradation robustness (mAP %)
| Method | Clear | Partial | Blurred | Hidden |
|---|---|---|---|---|
| Appearance only | 27.1 | 27.1 | 27.1 | 27.1 |
| Plate only | 100.0 | 30.2 | 44.8 | 3.6 |
| Weighted fusion | 99.0 | 48.2 | **58.2** | 27.8 |
| Random Forest | 98.9 | **50.7** | 37.3 | **29.7** |

*Insert `results/plate_robustness.png`.* Plate-only retrieval collapses as plates degrade (100 → 3.6 mAP). The fused methods stay at or above appearance-only at every level, which **supports the main hypothesis**. Which fusion is best depends on the level:
- **Partial plates:** the Random Forest is best.
- **Blurred plates:** the transparent weighted fusion is clearly best.
- **Hidden plates:** the Random Forest has the best mAP, but appearance alone has the best Rank-1.

### 6.5 SOM (10×10, unsupervised)
- **Purity:** vehicle ID 0.27, colour 0.67, type 0.75. *Insert `results/som_umatrix.png`.* The map organises vehicles by **type and colour**, not identity.
- **As a pre-filter** (plates hidden, Random Forest):

| Radius | Candidates kept | True matches kept | Rank-1 | mAP |
|---|---|---|---|---|
| 1 | 6.6% | 31.9% | 49.7 | 21.6 |
| 2 | 17.0% | 43.7% | 53.7 | 23.7 |
| 3 | 29.5% | 53.8% | 54.7 | 25.1 |

It removes 70–94% of candidates but loses too many true matches, so it lowers accuracy. This is a useful negative result: the SOM is good for visual exploration, but at this scale it shouldn't filter Re-ID candidates.

### 6.6 Tracking and demo
- **Demo run** (`results/demo/`, 173 tracklets across 3 cameras):
  - Stage 1 (*white* + *sticker/decal*) ranked the white estate car with the "PRVA" logo first.
  - After confirmation, Stage 2 returned the same car in camB as the #1 sighting (score 0.70, against 0.60–0.64 for the next candidates).
- **TODO:** % clean tracklets from the Track review tab.

## 7. Discussion and failure analysis

**Two pitfalls found during evaluation**

1. **Stacking leak.** The RF's training pairs first used colour/type probabilities from a probe fitted on the *same* training vehicles.
   - On those vehicles the attributes were near-perfect, so the forest relied on colour/type agreement, at a combined importance of 0.33.
   - On unseen vehicles the probe is only 73% (colour) and 79% (type) accurate, so the RF ranked worse than appearance alone: hidden plates, Rank-1 38 vs 59.
   - Out-of-fold attribute probabilities gave the training features realistic noise.
2. **Non-monotonic splits.** VeRi has large viewpoint changes, and the unconstrained forest still learned splits where *higher* similarity could *lower* the score.
   - Monotonic constraints fixed this (hidden plates: mAP 21 → 30).
   - Caveat: this choice came from a diagnostic on test queries, so the RF-vs-fusion comparison is indicative, not a tuned final number. A proper validation split would be the next step.

**Fusion: learned vs hand-set.** The Random Forest wins with partial plates, but the simple weighted fusion wins with blurred plates (58.2 vs 37.3 mAP).
- The forest's importances put plate similarity (0.25) and colour agreement (0.21) on top. ResNet appearance gets 0.05, even though it is the best single cue.
- The likely reason: the forest learns from a balanced pair set, so it optimises *same vs different classification*, not *ranking within one gallery*.
- A ranking objective, such as learning-to-rank or calibrating per query, is the clear next step.
- With a small training set, the transparent baseline is competitive. That's useful to know for a system where users must understand the scores.

**Expected failure modes**
- **Viewpoint change:** front vs rear views of the same vehicle give dissimilar appearance embeddings.
- **Near-identical vehicles:** same make, model and colour, e.g. fleet taxis. This is where plate evidence matters most.
- **Night, low resolution and occlusion:** these degrade colour probabilities and OCR.
- **Track fragmentation and ID switches:** a fragmented track splits one vehicle into several tracklets; an ID switch mixes two vehicles in one tracklet. Low track consistency flags the latter.
- **Distinctive cues:** CLIP cue scores are coarse and viewpoint-dependent, so they are treated as weak supporting evidence only.

**Observed in the demo** (`results/demo/`; add screenshots):
- **Attribute error:** CLIP labels the estate car as an "mpv".
- **Track fragmentation:** the yellow Post van and the "Alan Ford" bus are each split into several tracklets when occluded or at the frame edge.
- **Background tracklets:** partly occluded parked cars give blurry, low-information crops.
- **No plates:** none were readable at this camera distance. This is exactly the setting V-Trace targets.

## 8. Limitations and future work
- The appearance backbone is ImageNet-pretrained, not fine-tuned for Re-ID. Fine-tuning on VeRi training identities (e.g. with triplet loss) is the clearest accuracy gain.
- The plate experiment uses synthetic plate strings. A dataset with real plate text would strengthen it.
- OCR runs on whole-vehicle crops. A dedicated plate detector before OCR would improve read rates.
- There is no spatio-temporal reasoning between cameras (travel-time constraints). This is a natural extra evidence feature.
- Live-stream ingestion: the pipeline works on frames, so files can be replaced with RTSP streams without changing recognition.

## 9. Conclusion
V-Trace starts from incomplete information about a vehicle, retrieves likely candidates, keeps a human confirmation step,
and then re-identifies the confirmed vehicle across the remaining footage using several complementary sources of evidence.
On VeRi-776, plate-only retrieval collapses from 100% to 3.6% mAP as plates degrade. Multi-evidence fusion stays at or above appearance-only throughout, at 48–58% mAP with partial or blurred plates.
Description search with colour, type and a partial plate puts the right vehicle in the top 5 for 84% of queries.
The SOM reveals type/colour structure but is not a reliable candidate filter. A learned fusion needs care (leak-free features, monotonic constraints), and is not automatically better than a transparent one.

## References
- Liu, X., Liu, W., Mei, T., & Ma, H. VeRi-776 vehicle re-identification dataset. https://github.com/VehicleReId/VeRi
- Zhang, Y. et al. (2022). ByteTrack: Multi-Object Tracking by Associating Every Detection Box. ECCV.
- Radford, A. et al. (2021). Learning Transferable Visual Models From Natural Language Supervision (CLIP).
- He, K. et al. (2016). Deep Residual Learning for Image Recognition (ResNet). CVPR.
- Kohonen, T. (1990). The Self-Organizing Map. Proceedings of the IEEE.
- Breiman, L. (2001). Random Forests. Machine Learning.
- Ultralytics. Multi-Object Tracking documentation. https://docs.ultralytics.com/modes/track/

## AI declaration
In preparing this project, AI-based tools including Claude, ChatGPT and Gemini were used to support drafting and
refining text, organising content, implementation and general research support. All ideas, analysis, technical
design decisions and conclusions are the work of the project team.
