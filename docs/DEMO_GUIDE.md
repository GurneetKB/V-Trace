# V-Trace demo & assessor guide

This guide has three parts: how to start V-Trace, a scripted demo for the presentation (with the results you should
see), and things an assessor can try for themselves.

## 1. Start the app

**Option A – hosted (no install).** Open the Streamlit Community Cloud link shared with the submission and sign in
with the assessor account provided with it. The four demo cameras load automatically.

**Option B – local (Windows, Python 3.11).**
1. `python -m venv .venv` and `.venv\Scripts\pip install -r requirements.txt`
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set a username and password.
3. `.venv\Scripts\python -m streamlit run app.py`, open http://localhost:8501 and sign in.

The app has two pages (left sidebar): **Search** and **How it works**. It opens in dark mode; switch with ⋮ (top
right) → Settings → Theme.

## 2. Presentation demo (about 4 minutes)

**The videos** (sidebar → *Demo videos*, already processed). `camA_west`, `camB_centre` and `camC_east` are three
cameras along one street, so the same cars pass A → B → C (near lane) or C → B → A (far lane). `camD_other_road` is a
different road whose vehicles never appear in A–C.

The Search page has three steps: **1 Describe the vehicle**, **2 Best matches**, **3 Where this vehicle was seen**.

**Scenario A – find a red car and trace it through three cameras (main demo)**
1. **1 Describe the vehicle**: Colour **red**, Type **suv**, click **Search**.
2. **2 Best matches**: #3 is a red Citroën in **camB_centre, 00:42.00 – 00:43.56**. Click **Select**.
3. *Expect:* **3 Where this vehicle was seen** shows
   **Route: camA_west (00:40.80) → camB_centre (00:42.00) → camC_east (00:43.56)**,
   with one row per camera: the time span, a crop and the full frame with the car boxed. camA scores 0.67 and camC 0.51.
   **camD_other_road** is listed under *Not seen in* ("no vehicle in the time window").

**Scenario B – the same search, an ambiguous result**
- In the same results, select #2 (the same red Citroën in **camA_west, 00:40.80**).
- *Expect:* camB_centre and camC_east are listed under *Not seen in*, each with its three closest vehicles. In camB the
  true car (00:42.00) is first with 0.67, but another red car (00:39.96) scores 0.62, too close to call, so the ratio
  test leaves the choice to the user. Good talking point: the system shows evidence, it does not claim an identity.
  (Searching from the camB sighting, as in Scenario A, gives a clear answer because camB's view of the car is sharper.)

**Scenario C – upload videos**
- Sidebar → **Upload new videos**, add two or three short clips (10–30 s), keep **Fast processing** on, click
  **Process videos**. Each clip becomes one camera; describe and select a vehicle as above. Uploaded videos are assumed
  to be recorded at different times, so the time window is off (Settings).

**Talking points while it runs**
- Every model is pretrained and used as published: YOLO11 + ByteTrack (sightings), CLIP zero-shot (description),
  EasyOCR (plates), and the FastReID VeRi-776 Re-ID model from the VeRi authors' team (same vehicle across cameras).
- A sighting = all frames in which one vehicle is seen continuously in one camera.
- Step 1 uses only the fields you fill in; a missing field is ignored rather than counted as a mismatch.
- A camera counts as "seen" only when its best sighting is similar enough (≥ 0.40) and clearly better than the
  next one; for demo videos it must also be within 10 s.
- **How it works** page: the models and the VeRi-776 benchmark numbers.

## 3. Things to try (assessors)

| Try this | Where | What it shows |
|---|---|---|
| Search with only a colour, then add the type | Search 1 | each extra field narrows the list |
| Type a partial plate with wildcards, e.g. `SGX1?3?` | Search 1 | wildcard plate matching (plates are rarely readable in the demo footage, so unread plates get a neutral score) |
| Pick a distinctive feature or type free text, e.g. "bus" | Search 1 | CLIP text–image scoring |
| Select different vehicles from the results | Search 3 | per-camera sightings, or the closest candidates when there is no confident match |
| Change the threshold or turn off *Videos were recorded at the same time* | sidebar → Settings | stricter / looser matching; the time window |
| *Upload new videos* | sidebar | the full pipeline on new footage |

**Known limitations to keep in mind:** plates are not readable at this camera distance; colour labels are unreliable
for silver/grey cars; a car seen very small or from a very different angle may not be matched; results are ranked
candidates for human review, never identity claims.
