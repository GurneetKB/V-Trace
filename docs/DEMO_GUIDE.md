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

The app has two pages (left sidebar): **Search** and **Analysis**. It opens in dark mode; switch with ⋮ (top right)
→ Settings → Theme.

## 2. Presentation demo (about 4 minutes)

**The cameras** (listed in the sidebar). `camA_west`, `camB_centre` and `camC_east` are three cameras along one
street, so the same cars pass A → B → C (near lane) or C → B → A (far lane). `camD_other_road` is a different road
whose vehicles never appear in A–C, so it should never be confirmed.

The Search page has three steps: **① Find the vehicle**, **② Its route across the cameras**, **③ Where else was it seen?**

**Scenario A – trace a car through three cameras (main demo, about 2 minutes)**
1. **① Find the vehicle → Describe it**: Colour **red**, Type **sedan**, click **Search**.
   *Expect:* #1 is a red Citroën in **camA_west, 00:40.80–00:42.24**.
2. Click **Select** on it.
3. **③ Where else was it seen?** In the camB_centre row, the ⭐ #1 match is the same car (00:42.00–00:43.56).
   Click **✓ Same vehicle**.
4. The camC_east row is re-scored against both confirmed views. Click **✓ Same vehicle** on the red Citroën at
   **00:43.56–00:44.16** (among the four shown).
5. *Expect:* **② Its route across the cameras** shows camA 0:40.8 → camB 0:42.0 → camC 0:43.6, all confirmed.
   Open **Why these matches?** to show the evidence behind each candidate.

**Scenario B – pick a vehicle straight from the footage**
- **① Find the vehicle → Pick it from a camera**, camera **camA_west**: every vehicle in that camera, in order of
  appearance. Select the red car at **00:00.96–00:06.72**.
- *Expect:* the suggested route (⭐) already shows camB_centre and camC_east.
- Honest talking point: this track briefly switched between two cars (one crop is a green car); the crops are how a
  reviewer spots that.

**Scenario C – confirming one camera fixes the next (and ignoring a look-alike)**
- Search Colour **white**, Type **sedan**; select the silver Citroën in **camA_west at 00:00.00–00:08.20** (around #9).
- Confirm its ⭐ camB_centre sighting with **✓ Same vehicle**: the true camC_east sighting then moves to **#1** in its row.
- The camD_other_road row shows a similar white Citroën. It is on a different road, so it must not be confirmed. This is
  the failure case in the report (Figure 8): a look-alike is why the human confirms each step.

**Talking points while it runs**
- Step ① uses only the fields you fill in; a missing field is ignored rather than counted as a mismatch.
- Selecting a vehicle is deliberate: V-Trace never claims an identity on its own.
- Each camera row is a ranked Re-ID result, scored against *every* confirmed view of the vehicle, so the middle camera
  bridges the far, small view and the near, large view.
- **Analysis** page: the VeRi-776 benchmark results, the vehicle map (SOM) and the tracking check.

## 3. Things to try (assessors)

| Try this | Where | What it shows |
|---|---|---|
| Search with only a colour, then add the type | Search ① | each extra cue narrows the list |
| Type a partial plate with wildcards, e.g. `SGX1?3?` | Search ① | wildcard plate matching (plates are rarely readable in the demo footage, so unread plates get a neutral score) |
| **More detail** → a distinctive feature or free text, e.g. "bus" | Search ① | CLIP text–image scoring |
| Pick a vehicle from a camera instead of describing it | Search ① | vehicle-to-vehicle Re-ID from any query |
| Change **Matcher** in *Matching settings* (sidebar) | Search ③ | appearance only vs learned metric vs fused evidence |
| Untick *Cameras share a clock* | sidebar | the time window that rejects impossible jumps |
| *Use your own videos* (sidebar): two short traffic clips, Fast processing on | sidebar | the full pipeline on new footage |
| Open the **Analysis** page | sidebar | benchmark results, SOM vehicle map, tracking check |

**Known limitations to keep in mind:** plates are not readable at this camera distance; colour labels are unreliable
for silver/grey cars; a car seen very small in one camera may rank lower there; results are ranked candidates for human
review, never identity claims.
