Setup: `{'train_ids': 150, 'test_ids': 100, 'max_queries': 300, 'max_pos': 6000, 'neg_ratio': 3, 'seed': 0, 'n_train_tracklets': 1290, 'n_test_tracklets': 830}`

### Attribute recognition accuracy (%)

| attribute | zero_shot_acc | linear_probe_acc | n_test |
|---|---|---|---|
| color | 67.0 | 72.9 | 830 |
| type | 38.3 | 79.3 | 830 | 

### Stage 1 - description search (%)

| query | rank1 | rank5 | mAP |
|---|---|---|---|
| colour + type | 16.0 | 45.0 | 19.1 |
| partial plate only | 21.0 | 49.0 | 21.6 |
| colour + type + partial plate | 58.0 | 84.0 | 40.9 | 

### Stage 2 - Re-ID ablation, plates hidden (%)

| method | rank1 | rank5 | mAP |
|---|---|---|---|
| metric_cos | 77.0 | 91.3 | 48.0 |
| learned metric | 77.0 | 91.3 | 48.0 |
| weighted fusion | 71.3 | 88.7 | 43.3 |
| random forest | 69.7 | 88.3 | 42.4 |
| clip_cos | 58.3 | 75.7 | 28.2 |
| app_cos | 61.3 | 79.3 | 27.1 |
| appearance only | 61.3 | 79.3 | 27.1 |
| color_hist | 24.0 | 44.3 | 12.7 |
| color_agree | 5.3 | 16.3 | 11.3 |
| type_agree | 7.0 | 18.0 | 10.3 |
| cue_sim | 13.0 | 30.7 | 9.1 |
| plate_sim | 1.0 | 1.0 | 3.6 |
| track_consist | 0.7 | 5.3 | 3.5 |
| track_quality | 0.7 | 1.7 | 3.4 | 

### Plate robustness - mAP (%) by plate visibility

| method | clear | partial | blurred | hidden |
|---|---|---|---|---|
| appearance only | 27.1 | 27.1 | 27.1 | 27.1 |
| plate_sim | 100.0 | 30.2 | 44.8 | 3.6 |
| weighted fusion | 99.3 | 63.5 | 69.5 | 43.3 |
| random forest | 88.1 | 59.3 | 48.2 | 42.4 | 

### SOM (10x10)

Purity - vehicle ID 0.27, colour 0.67, type 0.75

| pre-filter | candidates_kept_% | true_match_recall_% | rank1 | rank5 | mAP |
|---|---|---|---|---|---|
| radius_1 | 6.6 | 31.9 | 59.7 | 74.0 | 24.6 |
| radius_2 | 17.0 | 43.7 | 66.3 | 81.3 | 28.9 |
| radius_3 | 29.5 | 53.8 | 68.3 | 83.3 | 31.7 |
