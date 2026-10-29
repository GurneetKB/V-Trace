# V-Trace demo & assessor guide

This guide has three parts: how to start V-Trace, a scripted demo for the presentation (with the results you should
see), and things an assessor can try for themselves.

## 1. Start the app

**Option A – hosted (no install).** Open the Streamlit Community Cloud link shared with the submission and sign in
with the assessor account provided with it. The hosted app runs on a small CPU, so use the **▶ Quick demo** button
(the demo cameras are pre-processed) rather than uploading long videos.

**Option B – local (Windows, Python 3.11).**
1. `python -m venv .venv` and `.venv\Scripts\pip install -r requirements.txt`
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set a username and password.
3. Put the trained models in `models/` and the four demo videos in `data/videos/` (both are in the submission ZIP).
4. `.venv\Scripts\python -m streamlit run app.py`, open http://localhost:8501 and sign in.

The app opens in dark mode; switch with ⋮ (top right) → Settings → Theme.

## 2. Presentation demo (about 4 minutes)

**The cameras.** `camA_west`, `camB_centre` and `camC_east` are three cameras along one street, so the same cars pass
A → B → C (near lane) or C → B → A (far lane). `camD_other_road` is a different road whose vehicles never appear in
A–C, so it must never be chosen.

Sign in, open tab **1 · Upload videos** and click **▶ Quick demo**. The four cameras load (instantly if they were
processed before, or from the pre-processed demo bundle on the hosted app). The sidebar shows **187 vehicles**.

**Scenario A – trace a car by confirming each camera (main demo, about 2 minutes)**
1. Tab **2 · Describe & search**: Colour **red**, Vehicle type **sedan**, click **Search**.
   *Expect:* #1 is **camA_west · track 481** (00:40.80–00:42.24), a red Citroën.
2. Click **✅ Confirm this vehicle** on it, then open tab **3 · Confirm & re-identify**.
3. Under *Trace this vehicle's route*, the **suggested route** already adds **camB_centre** (⭐ on track 156,
   00:42.00–00:43.56). In the camB_centre box click **✓ Same vehicle** on track 156.
4. The camC_east candidates are re-scored against both confirmed views. Click **✓ Same vehicle** on
   **track 294** (00:43.56–00:44.16; it is among the top three).
5. *Expect:* **Confirmed route camA_west → camB_centre → camC_east** at 0:41 → 0:42 → 0:43.6, with the red Citroën in
   all three crops. Scroll down to show the ranked candidates with their evidence vectors and frames.

**Scenario B – a fully automatic route**
- Same search (red + sedan); confirm **#2 camA_west · track 36** (00:00.96–00:06.72).
- *Expect:* the suggested route alone is camA → camB_centre (track 18) → camC_east (track 55), in time order.
- Honest talking point: this tracklet's middle crop on the search card shows a green car. The tracker briefly
  switched identities between two cars; the evidence frame and the crops are how a reviewer spots that.

**Scenario C – confirming one camera fixes the next (and ignoring a look-alike)**
- Search Colour **white**, Vehicle type **sedan**; confirm **camA_west · track 1** (00:00.00–00:08.20, a silver
  Citroën; it is around #9 in the list).
- *Expect:* the suggestion adds camB_centre track 25. Confirm it with **✓ Same vehicle**: the true camC_east sighting
  (track 70) then moves to **#1** in the camC_east box.
- The camD_other_road box shows a similar white Citroën (track 14). It is on a different road, so it must not be
  confirmed. This is the failure case in the report (Figure 8): a look-alike is why the human confirms each hop.


**Talking points while it runs**
- Stage 1 uses only the fields you fill in; a missing field is ignored rather than counted as a mismatch.
- The confirm step is deliberate: V-Trace never claims an identity on its own.
- In tab 3, the traced path is built by scoring each remaining camera against *every* sighting already on the path,
  so the middle camera bridges the far, small view and the near, large view.
- Each ranked candidate shows its eleven-number evidence vector and the evidence frame, so a reviewer can see *why* it
  was ranked there.
- Switch the matcher to **appearance only** to show the fused evidence doing better on the same query.

## 3. Things to try (assessors)

| Try this | Where | What it shows |
|---|---|---|
| Search with only a colour, then add the type | tab 2 | each extra cue narrows the candidate list |
| Type a partial plate with wildcards, e.g. `SGX1?3?` | tab 2 | wildcard plate matching (plates are rarely readable in the demo footage, so unread plates get a neutral score instead of being excluded) |
| Add a distinctive cue or free text, e.g. "bus" or "car with a roof rack" | tab 2 | CLIP text–image scoring |
| Confirm a car, then change the matcher (appearance only / weighted fusion / Random Forest) | tab 3 | how the fused evidence changes the ranking |
| Raise the minimum match score, or untick "Cameras share a clock" | tab 3 | how strict path tracing is; the time window rejects impossible jumps |
| Tick "SOM candidate pre-filter" | tab 3 | the unsupervised pre-filter (it speeds up search but can drop true matches, as the report discusses) |
| Upload your own two short traffic clips (10–30 s each) | tab 1 | the full pipeline on new footage; use the **Fast** preset on the hosted app |
| Open the Track review, SOM and Evaluation tabs | tabs 4–6 | manual tracking check, the unsupervised map, and the VeRi-776 benchmark results |

**Known limitations to keep in mind:** plates are not readable at this camera distance; colour labels are unreliable
for silver/grey cars; a car seen very small in one camera may not reach the minimum score, so its path can stop
early; results are ranked candidates for human review, never identity claims.
