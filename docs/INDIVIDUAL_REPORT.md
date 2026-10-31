# Individual Project Report

## 1. Your personal contribution to the project.

V-Trace was a one-person project (Group 21), so I was responsible for every part of it, from the proposal to the
deployed application.

- **Problem framing.** I defined the describe → rank → select → trace workflow, the scope (short demo or uploaded
  videos, ranked results for a person to review, never an identity claim) and the evaluation plan, and presented them
  in the first presentation.
- **Pipeline from pretrained models.** I chose a published model for each step and connected them: YOLO11 detection
  and ByteTrack tracking turn video into sightings; CLIP zero-shot scoring and EasyOCR make each sighting searchable
  by colour, type, distinctive features, free text and plate; and the FastReID VeRi-776 model released by the VeRi
  authors' team matches a vehicle across cameras. I wrote a small loader so its checkpoint runs with plain PyTorch, and
  re-ran the official VeRi-776 benchmark (Rank-1 97.0%, mAP 81.6%) to check it behaves as published.
- **Search and matching logic.** I designed the description score (only the fields the user gives are used) and the
  rule that decides whether a vehicle was seen in a camera: a similarity threshold chosen from the VeRi-776 score
  distributions, a ratio test against the second-best candidate, and a real-world time window built from each camera's
  location and recording start.
- **Data and evaluation.** I built the multi-camera demo footage and an upload test pack, placed the cameras at curated
  Singapore locations with recording times, and evaluated tracking and re-identification on the footage with a pseudo
  ground truth.
- **Application and delivery.** I built the Streamlit app (admin sign-in, demo or uploaded videos, Cameras page,
  dark/light theme), the unit and end-to-end tests, and managed the work through GitHub branches and pull requests. I
  wrote the report, both presentations and the demo guide, and recorded the video.

## 2. What you have learnt from the project.

**Use what already exists, and verify it.** A published model trained by the dataset's own authors was far stronger
than anything I could have trained in ten days. The real work was integrating it correctly and checking it: re-running
the official benchmark showed that the weights load and behave as published before I trusted them on my own footage.

**Benchmarks do not transfer automatically.** The same model that ranks the right vehicle first 97% of the time on
VeRi-776 does so for about a third of queries on my street footage, where vehicles are small and seen from very
different angles. Measuring this on my own data, rather than quoting the benchmark, changed the design.

**Decision rules matter as much as scores.** A similarity score does not say "same vehicle" by itself. Turning it into a
decision needed a threshold justified by data, a check for ambiguity and real-world context such as time and place.
These raised the share of correct cameras from about a quarter to over 80% without any training, and when the answer is
ambiguous, the honest output is to show the candidates and let a person decide.

**Context makes results usable.** Showing each sighting with its location, real-world time and a frame turned a list of
scores into evidence a person can check, which is what an investigator actually needs.

## 3. How you can apply this in future work-related projects.

- **Building AI systems from pretrained components.** Most industry projects start by choosing suitable published
  models, integrating them and validating them on the target data before relying on them. I will keep that order:
  reproduce the published result first, then measure on our own data.
- **Checking for domain shift.** Re-measuring a model on the data it will actually see applies to any deployed system,
  from document processing to quality inspection, and it is cheap compared with a failure in production.
- **Designing decisions, not just models.** Thresholds, ambiguity checks and business context (time, location, rules)
  turn model scores into decisions people can defend; I will design and test these as carefully as the model itself.
- **Video analytics and smart-city systems.** The detection → tracking → description → retrieval chain transfers to
  traffic monitoring, car parks, logistics yards and retail footfall analysis, with privacy-preserving defaults such as
  ranked candidates instead of identity claims, and access control.
- **Engineering practice.** Small pull requests, automated tests, reproducible evaluation scripts and clear
  documentation made a ten-day project manageable, and I will use the same workflow in team projects at work.
