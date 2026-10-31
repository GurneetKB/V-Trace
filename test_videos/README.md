# V-Trace upload test pack

Seven short clips to try **Upload new videos** in the app. Each file is one camera. Upload a set's files together
(you can add `set3_bukit_timah.mp4` to either set as a distractor camera). With the file names unchanged, the camera
location and recording start fill in automatically, and the real-world time limit is switched on.

| File | Camera location (curated) | Recording start (curated) | Length |
|---|---|---|---|
| `set1_orchard_west.mp4` | Orchard Road, west of Scotts Road · Singapore | Fri 30 Oct 2026, 17:45:01 | 22 s |
| `set1_orchard_scotts.mp4` | Orchard Road at the Scotts Road junction · Singapore | Fri 30 Oct 2026, 17:45:01 | 22 s |
| `set1_orchard_east.mp4` | Orchard Road, east of Scotts Road · Singapore | Fri 30 Oct 2026, 17:45:01 | 22 s |
| `set2_orchard_west.mp4` | Orchard Road, west of Scotts Road · Singapore | Fri 30 Oct 2026, 17:45:23 | 22 s |
| `set2_orchard_scotts.mp4` | Orchard Road at the Scotts Road junction · Singapore | Fri 30 Oct 2026, 17:45:23 | 22 s |
| `set2_orchard_east.mp4` | Orchard Road, east of Scotts Road · Singapore | Fri 30 Oct 2026, 17:45:23 | 22 s |
| `set3_bukit_timah.mp4` | Bukit Timah Road near Newton Circus · Singapore | Fri 30 Oct 2026, 17:48:00 | 20 s |

**Where the clips come from.** They are cut from two openly licensed street recordings (Wikimedia Commons, CC BY 3.0,
"Sounds of Changes"; see `docs/DEMO_DATA.md`). The three `orchard` clips of a set are three zones of one wide shot,
so the same vehicles pass west → Scotts → east (or the reverse). Set 1 covers the first 22 s and set 2 the next 22 s,
so the two sets show mostly different vehicles. Set 3 is a different road. The recordings carry no location or clock
metadata, so the Singapore locations and times are curated (`vtrace/cameras.py`); edit them on the **Cameras** page.

**Processing time.** With *Fast processing* on (the default, sidebar → Settings), each clip takes about as long as it
plays: around 20–25 s per clip on a laptop CPU. On Streamlit Community Cloud allow about a minute per clip.

## Results to expect (Fast processing on)

Checked against a reference tracking of the full recording (`scripts/demo_eval.py` method).

| Upload | Describe | Select | *Where this vehicle was seen* |
|---|---|---|---|
| Set 1 (+ set 3) | Colour **gray**, Type **suv** | #1, west camera, 17:45:04.0 | Route: west 17:45:04.0 → (+3.2 s) Scotts junction 17:45:07.2 (similarity 0.58) |
| Set 1 (+ set 3) | Colour **green**, Type **sedan** | #1, west camera, 17:45:02.2 | Route: west 17:45:02.2 → (+6.0 s) Scotts junction 17:45:08.2 (similarity 0.53) |
| Set 2 (+ set 3) | Colour **red**, Type **suv** | #3, Scotts junction, 17:45:43.2 | Route: west 17:45:37.6 → (+5.6 s) Scotts junction 17:45:43.2 (similarity 0.61) |
| any set + set 3 | anything | any Orchard Road vehicle | Bukit Timah Road is listed under *Not seen in*: it was recorded about 3 minutes later, outside the 10 s limit |

In each case the east camera is listed under *Not seen in* with its three closest vehicles: either the car was seen
there too briefly to keep at the Fast setting, or no candidate was a confident match. That is the system being
cautious, not a crash. On these sets about 71–75% of the cameras V-Trace reports are correct, and it reports about a
third of the cameras each vehicle really passed through.

**Things to try:** turn off *Limit by real-world time* (Settings) and see how many more candidates appear; change a
camera's recording start on the **Cameras** page (for example set the east camera 1 minute earlier) and watch the
route re-order; upload your own short dash-cam or traffic clips and enter their location and start time.

Rebuild the pack with `python scripts/make_test_videos.py` (needs the two raw recordings, see `docs/DEMO_DATA.md`).
