# V-Trace – Final Project Report (draft)

**Project:** V-Trace | Multi-Attribute Vehicle Re-Identification System
**Group 21:** Gurneet Kaur Bhuller (A0354164E)
**Course:** Pattern Recognition Systems – Practice Module

> **Draft status.** Sections 1–5, 7 and 8 are drafted from the proposal and the implemented system.
> Items marked **TODO** need the VeRi-776 run (`python scripts/train_eval.py`, issue #4) or the real-clip demo (issue #5).
> Paste the tables from `python scripts/export_tables.py` into Section 6.

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
- **TODO:** state the final subset sizes, e.g. 150 train / 100 test vehicles.

**Re-ID protocol.**
- Each test tracklet is a query.
- The gallery is every test tracklet from other cameras.
- A match is relevant if it has the same vehicle id.
- Metrics: Rank-1, Rank-5 and mAP.

**Random Forest training.**
- Positives: all same-vehicle, different-camera tracklet pairs (capped).
- Negatives: three times as many as positives. Half are random different-vehicle pairs; half are *hard* negatives with the same predicted colour and type.

**Plate robustness.**
- VeRi has no plate text, so each identity gets a synthetic Singapore-style plate.
- That plate is degraded per observation at four levels:
  - *clear*: occasional single OCR slip;
  - *partial*: about 45% of characters unknown;
  - *blurred*: about 45% confusable substitutions, sometimes a dropped character;
  - *hidden*: no plate.
- The RF is trained on a mixture of all four levels.
- Testing is done at each level separately, which isolates the main hypothesis.

**Demo clips.** **TODO:** list the sources, number of cameras and clip durations. Tracking quality on these clips is checked manually in the Track review tab.

## 6. Results

> **TODO:** run `python scripts/train_eval.py`, then `python scripts/export_tables.py`, and paste the output here.

### 6.1 Attribute recognition (colour, type: zero-shot vs linear probe)
### 6.2 Stage 1 – description search (colour + type / partial plate / both)
### 6.3 Stage 2 – Re-ID ablation (single cues vs weighted fusion vs Random Forest)
### 6.4 Plate-degradation robustness – insert `results/plate_robustness.png`
### 6.5 SOM – purity and pre-filter trade-off – insert `results/som_umatrix.png`
### 6.6 Tracking on demo clips – % clean tracklets from the Track review tab

## 7. Discussion and failure analysis

**What to look for in the results**
- *Plate robustness:* plate-only retrieval should collapse as plates degrade, while appearance-only stays flat. The hypothesis holds if the fused methods stay at or above appearance-only at every level.
- *Feature importance* (`results/rf_importance.png`) shows which evidence the Random Forest actually relies on.
- *SOM pre-filter:* the trade-off between candidates removed and true matches lost. Shrinking the candidate list without losing recall is useful even if it doesn't improve mAP.

**Expected failure modes**
- **Viewpoint change:** front vs rear views of the same vehicle give dissimilar appearance embeddings.
- **Near-identical vehicles:** same make, model and colour, e.g. fleet taxis. This is where plate evidence matters most.
- **Night, low resolution and occlusion:** these degrade colour probabilities and OCR.
- **Track fragmentation and ID switches:** a fragmented track splits one vehicle into several tracklets; an ID switch mixes two vehicles in one tracklet. Low track consistency flags the latter.
- **Distinctive cues:** CLIP cue scores are coarse and viewpoint-dependent, so they are treated as weak supporting evidence only.

**TODO:** add 2–3 concrete failure examples from the demo with frame screenshots.

## 8. Limitations and future work
- The appearance backbone is ImageNet-pretrained, not fine-tuned for Re-ID. Fine-tuning on VeRi training identities (e.g. with triplet loss) is the clearest accuracy gain.
- The plate experiment uses synthetic plate strings. A dataset with real plate text would strengthen it.
- OCR runs on whole-vehicle crops. A dedicated plate detector before OCR would improve read rates.
- There is no spatio-temporal reasoning between cameras (travel-time constraints). This is a natural extra evidence feature.
- Live-stream ingestion: the pipeline works on frames, so files can be replaced with RTSP streams without changing recognition.

## 9. Conclusion
V-Trace starts from incomplete information about a vehicle, retrieves likely candidates, keeps a human confirmation step,
and then re-identifies the confirmed vehicle across the remaining footage using several complementary sources of evidence.
**TODO:** one or two sentences summarising the headline numbers from Section 6.

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
