# Individual Project Report

## 1. My contribution to the project

V-Trace was a one-person project (Group 21), so I was responsible for every part of it:

- **Problem framing and proposal.** I defined the *describe → rank → select → trace* workflow, the scope (short
  uploaded or demo videos, ranked results for a person to review, no identity claims) and the evaluation plan, and
  presented it in the first presentation.
- **Choosing and integrating pretrained models.** Rather than training my own networks, I selected published models for
  each step and connected them into one pipeline: YOLO11 detection and ByteTrack tracking to turn video into sightings,
  CLIP zero-shot scoring for colour, type, distinctive features and free text, EasyOCR for plates with wildcard
  matching, and the FastReID VeRi-776 Re-ID model released by the VeRi authors' team for cross-camera matching. I wrote
  a small loader so the FastReID checkpoint runs with plain PyTorch, and checked that it reproduces its published
  accuracy.
- **Search and matching logic.** I designed the description score (only the fields the user gives are used), and the
  rule that decides whether a vehicle was seen in a camera: a similarity threshold chosen from the VeRi-776 score
  distributions, a ratio test against the second-best candidate, and a time window for cameras that share a clock.
- **Demo data and evaluation.** I built multi-camera demo footage on which the same cars really pass three cameras,
  a pseudo-ground-truth evaluation of tracking and Re-ID on it, and the VeRi-776 benchmark run.
- **Application and engineering.** I built the Streamlit app (admin sign-in, demo or uploaded videos, dark/light
  theme), unit and app tests, and managed the work through GitHub branches and pull requests.
- **Documentation.** I wrote the final report, both presentations and the demo guide, and recorded the video.

## 2. What I learned that is most useful to me

**Use what already exists, and check it.** A pretrained, published model (FastReID on VeRi-776) was far stronger
than anything I could train in ten days. The important work was integrating it correctly and verifying it: re-running
the official benchmark showed the weights load and behave as published, before trusting them on my own footage.

**Benchmarks do not transfer automatically.** The same model that is excellent on VeRi-776 is much weaker on my street
footage, where vehicles are small and seen from different angles. Measuring this on my own data, instead of quoting the
benchmark, changed the design: I added the ratio test and the time window, which raised the share of correct cameras
from about 40% to about 70% without any training.

**Decision rules matter as much as scores.** A similarity score alone does not say "same vehicle". Turning it into a
decision needs a threshold justified by data, a check for ambiguity (two candidates almost equally similar) and context
such as time. When the answer is ambiguous, the honest output is to show the candidates and let a person decide.

**Keeping a human in the loop is a design decision, not a weakness.** Returning ranked candidates with frames,
timestamps and scores made the results explainable and made errors cheap to catch.

## 3. Applying these skills in other situations and workplaces

- **Building AI systems from pretrained components** is how most industry projects start: choosing suitable models,
  integrating them, and validating them on the target data before relying on them.
- **Domain-shift checks.** Re-measuring a model on the data it will actually see, not only on its benchmark, applies to
  any deployed ML system.
- **Video analytics and smart-city systems.** The detection → tracking → description → retrieval chain transfers to
  traffic monitoring, parking and logistics yards, or retail footfall analysis, with privacy-preserving defaults such as
  ranked candidates instead of identity claims, and access control.
- **Human-in-the-loop decision support.** Showing ranked options with their evidence, rather than a single automatic
  answer, is how I would design AI tools for any high-stakes setting, from investigations to quality inspection.
- **Engineering practice.** Small pull requests, automated tests, cached processing and reproducible evaluation scripts
  made a ten-day project manageable; I will use the same workflow on future team projects.
