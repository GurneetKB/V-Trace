# V-Trace demo walkthrough

Index: 173 tracklets from camA_main_road, camB_second_view, camC_other_road

- `camA_main_road`: 71 tracklets, contact sheet `tracklets_camA_main_road.jpg`
- `camB_second_view`: 70 tracklets, contact sheet `tracklets_camB_second_view.jpg`
- `camC_other_road`: 32 tracklets, contact sheet `tracklets_camC_other_road.jpg`

## Stage 1 - description search

Query: color=white, cues=['sticker / decal']

| # | tracklet | camera | time | label | score | evidence |
|---|---|---|---|---|---|---|
| 1 | camA_main_road#83 | camA_main_road | 00:04.32-00:16.32 | white mpv | 0.98 | color 1.00, cues 0.93 |
| 2 | camB_second_view#186 | camB_second_view | 00:19.44-00:19.76 | white van | 0.96 | color 1.00, cues 0.85 |
| 3 | camB_second_view#206 | camB_second_view | 00:22.40-00:27.44 | white van | 0.93 | color 1.00, cues 0.74 |
| 4 | camA_main_road#306 | camA_main_road | 00:21.04-00:29.92 | white mpv | 0.93 | color 1.00, cues 0.73 |
| 5 | camB_second_view#202 | camB_second_view | 00:21.20-00:26.64 | white bus | 0.93 | color 1.00, cues 0.71 |
| 6 | camB_second_view#100 | camB_second_view | 00:10.32-00:10.64 | white bus | 0.92 | color 1.00, cues 0.69 |
| 7 | camB_second_view#157 | camB_second_view | 00:16.16-00:17.76 | white bus | 0.92 | color 1.00, cues 0.68 |
| 8 | camA_main_road#234 | camA_main_road | 00:16.08-00:22.72 | white van | 0.92 | color 1.00, cues 0.68 |
| 9 | camA_main_road#364 | camA_main_road | 00:26.16-00:28.96 | white van | 0.92 | color 1.00, cues 0.68 |
| 10 | camA_main_road#216 | camA_main_road | 00:12.80-00:19.36 | white bus | 0.90 | color 1.00, cues 0.62 |
| 11 | camB_second_view#192 | camB_second_view | 00:19.92-00:20.96 | white van | 0.90 | color 1.00, cues 0.60 |
| 12 | camB_second_view#196 | camB_second_view | 00:20.16-00:21.20 | white van | 0.90 | color 1.00, cues 0.58 |

## Confirm

Confirmed **camA_main_road#83** (white mpv, 00:04.32-00:16.32)

## Stage 2 - cross-video Re-ID (weighted fusion)

| # | tracklet | camera | best view | label | score | app_cos | clip_cos | colour | type |
|---|---|---|---|---|---|---|---|---|---|
| 1 | camB_second_view#83 | camB_second_view | 00:12.24 | white mpv | 0.70 | 0.89 | 0.88 | 0.44 | 0.35 |
| 2 | camB_second_view#54 | camB_second_view | 00:08.24 | white hatchback | 0.64 | 0.86 | 0.83 | 0.29 | 0.23 |
| 3 | camB_second_view#154 | camB_second_view | 00:18.08 | gray hatchback | 0.63 | 0.87 | 0.82 | 0.20 | 0.19 |
| 4 | camB_second_view#50 | camB_second_view | 00:08.16 | white sedan | 0.62 | 0.82 | 0.83 | 0.27 | 0.23 |
| 5 | camB_second_view#175 | camB_second_view | 00:18.32 | white sedan | 0.61 | 0.82 | 0.83 | 0.37 | 0.11 |
| 6 | camC_other_road#21 | camC_other_road | 00:07.04 | white suv | 0.61 | 0.73 | 0.84 | 0.35 | 0.16 |
| 7 | camC_other_road#65 | camC_other_road | 00:10.16 | gray hatchback | 0.60 | 0.68 | 0.82 | 0.27 | 0.18 |
| 8 | camC_other_road#95 | camC_other_road | 00:10.56 | white van | 0.60 | 0.74 | 0.80 | 0.30 | 0.11 |
| 9 | camB_second_view#206 | camB_second_view | 00:27.12 | white van | 0.60 | 0.81 | 0.81 | 0.30 | 0.16 |
| 10 | camB_second_view#237 | camB_second_view | 00:29.44 | gray hatchback | 0.60 | 0.82 | 0.83 | 0.12 | 0.23 |