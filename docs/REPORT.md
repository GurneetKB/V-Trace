# V-Trace – Final Project Report (template)

**Project:** V-Trace | Multi-Attribute Vehicle Re-Identification System
**Group 21:** Gurneet Kaur Bhuller (A0354164E)
**Course:** Pattern Recognition Systems – Practice Module

> Fill each section, then paste the tables from `python scripts/export_tables.py` into Section 6.

## 1. Background and problem
- A plate is a strong identifier, but CCTV plates are often blurred, too small, occluded or facing away.
- Investigators often start with incomplete descriptions (colour, type, partial plate, distinctive cue).
- Goal: rank likely sightings for human review, not make a definitive identity claim.

## 2. Objective and scope
- Objective (from proposal): …
- In scope: uploaded videos, detection, tracking, tracklets, descriptors, description search, confirmation, SOM, fusion, cross-video Re-ID, ranked results.
- Out of scope: live CCTV, owner records, facial recognition, forensic identification, training large networks from scratch.

## 3. System design
Upload → Detect (YOLO11) → Track (ByteTrack) → Describe (ResNet-50, CLIP, HSV, EasyOCR) → Index →
Stage 1 description search → Human confirmation → Stage 2 Re-ID (SOM pre-filter, weighted fusion / Random Forest) → Ranked sightings

- 3.1 Video ingestion, detection and tracking (`vtrace/video.py`)
- 3.2 Vehicle representation and indexing (`vtrace/features.py`, `vtrace/index.py`)
- 3.3 Stage 1 – description-to-vehicle retrieval (`vtrace/search.py`)
- 3.4 Stage 2 – confirmed-candidate cross-camera Re-ID (`vtrace/reid.py`)
- 3.5 Unsupervised SOM (`vtrace/som.py`)
- 3.6 Streamlit interface (`app.py`) – add screenshots of each tab

## 4. Technique group mapping
| Technique group | Implementation | Evidence |
|---|---|---|
| Supervised / unsupervised | RF same/different matcher, colour/type linear probe; SOM over embeddings | RF metrics, probe accuracy, SOM purity / pre-filter |
| Machine / deep learning | YOLO11, ResNet-50 embeddings, CLIP, EasyOCR | appearance-only Rank-1/5, mAP |
| Hybrid / ensemble | Random Forest vs weighted fusion | ablation + plate robustness |
| Intelligent sensing | video → tracks → descriptors → candidates → sightings | end-to-end demo |

## 5. Data
- VeRi-776 subset (identity-disjoint train/test; images grouped by vehicle+camera into tracklets).
- Synthetic plate strings per identity (VeRi has no plate text), degraded clear / partial / blurred / hidden.
- Demo clips: list sources, number of videos, durations.

## 6. Results
### 6.1 Attribute recognition
### 6.2 Stage 1 – description search
### 6.3 Stage 2 – Re-ID ablation (single cues vs weighted fusion vs Random Forest)
### 6.4 Plate-degradation robustness  *(insert `results/plate_robustness.png`)*
### 6.5 SOM analysis  *(insert `results/som_umatrix.png`)*
### 6.6 Tracking (manually checked demo clips – from the Track review tab)

## 7. Discussion and failure analysis
- Where did fusion help / not help? Feature importances (`results/rf_importance.png`).
- Failure cases: viewpoint change, night, occlusion, near-identical vehicles, OCR errors, track fragmentation.

## 8. Limitations and future work
- Live-stream ingestion, fine-tuned Re-ID backbone, better plate detector, larger benchmark subsets.

## 9. Conclusion

## References
- Liu et al., VeRi-776 – https://github.com/VehicleReId/VeRi
- Zhang et al. (2022), ByteTrack, ECCV
- Radford et al. (2021), CLIP
- Ultralytics tracking docs – https://docs.ultralytics.com/modes/track/

## AI declaration
