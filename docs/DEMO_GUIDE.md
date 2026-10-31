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

The app has three pages (left sidebar): **Search**, **Cameras** and **How it works**. It opens in dark mode; switch
with ⋮ (top right) → Settings → Theme.

## 2. Presentation demo (about 4 minutes)

**The videos** (sidebar → *Demo videos*, already processed). `camA_west`, `camB_centre` and `camC_east` are three
cameras along one street, so the same cars pass A → B → C (near lane) or C → B → A (far lane). `camD_other_road` is a
different road whose vehicles never appear in A–C.

**Real-world time and location.** Every camera has a location and a recording start (**Cameras** page); a sighting's
real-world time = recording start + its position in the video. The demo videos carry no such metadata, so their details
are curated and placed in Singapore: camA–camC on Orchard Road around the Scotts Road junction, all starting **Wed 28 Oct 2026, 08:15:00** (same clock), and camD
on Bukit Timah Road near Newton Circus, starting **08:17:30** (2.5 min later).

The Search page has three steps: **1 Describe the vehicle**, **2 Best matches**, **3 Where this vehicle was seen**.

**Scenario A – find a red car and trace it through three cameras (main demo)**
1. **1 Describe the vehicle**: Colour **red**, Type **suv**, click **Search**.
2. **2 Best matches**: #3 is a red Citroën in **camB_centre, 08:15:42.0 – 08:15:43.5**. Click **Select**.
3. *Expect:* **3 Where this vehicle was seen** shows
   **Route: camA_west 08:15:40.8 → (+1.2 s) camB_centre 08:15:42.0 → (+1.6 s) camC_east 08:15:43.5**,
   with one row per camera: the location, the real-world date and time span, the time in the video, a crop and the full
   frame with the car boxed, plus a map of the camera locations. camA scores 0.67 and camC 0.51.
   **camD_other_road** is listed under *Not seen in* ("no vehicle within 10.0 s"): it was recorded minutes later.

**Scenario B – the same search, an ambiguous result**
- In the same results, select #2 (the same red Citroën in **camA_west, 08:15:40.8**).
- *Expect:* camB_centre and camC_east are listed under *Not seen in*, each with its three closest vehicles. In camB the
  true car (08:15:42.0) is first with 0.67, but another red car (08:15:39.9) scores 0.62, too close to call, so the ratio
  test leaves the choice to the user. Good talking point: the system shows evidence, it does not claim an identity.
  (Searching from the camB sighting, as in Scenario A, gives a clear answer because camB's view of the car is sharper.)

**Scenario C – real-world time decides (cameras a minute apart)**
- **Cameras** page: change camC_east's recording start to **08:14:00** (1 min earlier) and click **Save camera details**.
- Repeat Scenario A: camC's sighting is now at 08:14:43.5, about a minute before the others, so with the 10 s limit it
  is *Not seen*. Sidebar → Settings → *Max time between cameras* **1 min 00 s**: it is matched again and the route is
  re-ordered in real-world time (camC → camA → camB). camD (recorded from 08:17:30) stays out. Set camC back to
  08:15:00 afterwards.

**Scenario D – upload videos (test pack)**
- Sidebar → **Upload new videos**, add the three `set1_orchard_*.mp4` files from `test_videos/` (optionally also
  `set3_bukit_timah.mp4`) and click **Process videos** (about 20–25 s per clip on a laptop). The location and start time
  fill in automatically for these files, and the real-world time limit is switched on.
- Describe Colour **gray**, Type **suv**, select **#1** (west camera, 17:45:04.0): the route shows the Scotts Road
  junction 3.2 s later. More scenarios with expected results are in `test_videos/README.md`.
- For your own clips, open each file's *location & start time* box and enter them before processing; for uploads with
  unknown clocks the real-world time limit stays off (Settings). Details can be edited later on the **Cameras** page.

**Talking points while it runs**
- Every model is pretrained and used as published: YOLO11 + ByteTrack (sightings), CLIP zero-shot (description),
  EasyOCR (plates), and the FastReID VeRi-776 Re-ID model from the VeRi authors' team (same vehicle across cameras).
- A sighting = all frames in which one vehicle is seen continuously in one camera; its real-world time = camera
  recording start + its position in the video, so cameras can be seconds, minutes or hours apart.
- Step 1 uses only the fields you fill in; a missing field is ignored rather than counted as a mismatch.
- A camera counts as "seen" only when its best sighting is similar enough (≥ 0.40), clearly better than the next one
  and, with the time limit on, close enough in real-world time (default 10 s).
- **How it works** page: the models and the VeRi-776 benchmark numbers.

## 3. Things to try (assessors)

| Try this | Where | What it shows |
|---|---|---|
| Search with only a colour, then add the type | Search 1 | each extra field narrows the list |
| Type a partial plate with wildcards, e.g. `SGX1?3?` | Search 1 | wildcard plate matching (plates are rarely readable in the demo footage, so unread plates get a neutral score) |
| Pick a distinctive feature or type free text, e.g. "bus" | Search 1 | CLIP text–image scoring |
| Select different vehicles from the results | Search 3 | per-camera sightings, or the closest candidates when there is no confident match |
| Change the threshold, the *Max time between cameras* or turn off *Limit by real-world time* | sidebar → Settings | stricter / looser matching; the real-world time window |
| Edit a camera's location or recording start | Cameras page | real-world times and the route update |
| *Upload new videos* with a set from `test_videos/` (see its README) | sidebar | the full pipeline on new footage, with expected results |

**Known limitations to keep in mind:** plates are not readable at this camera distance; colour labels are unreliable
for silver/grey cars; a car seen very small or from a very different angle may not be matched; results are ranked
candidates for human review, never identity claims.
