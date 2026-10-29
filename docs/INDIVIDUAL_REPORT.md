# Individual Project Report

## 1. My contribution to the project

V-Trace was a one-person project (Group 21), so I was responsible for every part of it:

- **Problem framing and proposal.** I defined the two-stage *describe → search → confirm → re-identify* workflow,
  the scope (uploaded videos, ranked results for human review, no identity claims) and the evaluation plan, and
  presented it in the first presentation.
- **Recognition pipeline.** I built video ingestion with YOLO11 detection and ByteTrack tracking, turned tracks into
  tracklets with quality-based crop selection, and computed six complementary descriptors per tracklet: ResNet-50 and
  CLIP embeddings, colour/type probabilities, an HSV histogram, EasyOCR plate text with wildcard matching, and
  CLIP-scored distinctive cues.
- **Learning components.** I trained a supervised colour/type probe on VeRi-776 labels, a Random Forest
  same/different-vehicle matcher over a ten-feature evidence vector, and an unsupervised Self-Organizing Map, and
  compared them against appearance-only and weighted-fusion baselines.
- **Path tracing.** I added a path-growing method that follows a confirmed vehicle from camera to camera and built
  multi-camera demo footage on which the same cars really appear in three cameras.
- **Evaluation.** I designed an identity-disjoint VeRi-776 protocol, a plate-degradation experiment, ablations, and a
  pseudo-ground-truth evaluation of tracking and path tracing on the demo cameras.
- **Application and engineering.** I built the Streamlit app (admin sign-in, dark/light theme, six tabs), unit and
  app tests with GitHub Actions CI, and managed the work through GitHub issues, branches and pull requests.
- **Documentation.** I wrote the final report, both presentations and the demo guide, and recorded the video.

## 2. What I learned that is most useful to me

**Evaluation discipline matters as much as the model.** My first Random Forest ranked *worse* than a single
appearance cue. The cause was not the algorithm but the data feeding it: the colour/type features for its training
pairs came from a classifier fitted on the same vehicles, so they were unrealistically accurate and the forest learned
to over-trust them. Out-of-fold features fixed it. Finding this taught me to ask, for every feature, "would this value
look the same on data the model has never seen?" — the same question behind identity-disjoint splits.

**Combining weak evidence is powerful, but a learned combiner needs care.** No single cue was reliable: plates
disappear, colour labels are wrong a quarter of the time, appearance changes with viewpoint. Together they were
robust. I also learned that a learned fusion is not automatically better than a transparent one: the hand-set
weighted fusion beat the Random Forest with blurred plates, and monotonic constraints were needed so that more
similarity could never mean a lower score.

**Keeping a human in the loop is a design decision, not a weakness.** Making the system return ranked candidates
with the evidence for each, and requiring a human confirmation between the two stages, made the results explainable
and made errors cheap to catch.

**Reporting negative results honestly.** The SOM pre-filter lowered accuracy. Reporting that clearly, together with
the caveat that one modelling choice was informed by test queries, made the work more credible, not less.

## 3. Applying these skills in other situations and workplaces

- **Any multi-source matching problem** follows the same pattern as V-Trace: record linkage across databases,
  fraud detection across transactions, or matching products, documents or customers across systems. Each has several
  weak, partly missing signals that are stronger together, and benefits from a transparent baseline next to a learned model.
- **Leakage checks in any ML pipeline.** Stacked models, target encoding and features computed from labels are common in
  industry; out-of-fold features and grouped cross-validation are directly reusable.
- **Video analytics and smart-city systems.** The detection → tracking → description → retrieval chain transfers to
  traffic monitoring, parking and logistics yards, or retail footfall analysis, with privacy-preserving defaults such
  as ranked candidates instead of identity claims and access control.
- **Human-in-the-loop decision support.** Showing ranked options with their evidence, rather than a single automatic
  answer, is how I would design AI tools for any high-stakes setting, from investigations to quality inspection.
- **Engineering practice.** Small pull requests, automated tests and CI, cached processing and reproducible
  experiment scripts made a ten-day project manageable; I will use the same workflow on future team projects.
