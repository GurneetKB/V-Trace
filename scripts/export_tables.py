"""Turn results/metrics.json into Markdown tables for the report.

    python scripts/export_tables.py > results/tables.md
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vtrace import config


def table(rows, cols, first="", fmt="{:.1f}"):
    out = [f"| {first} | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for name, vals in rows.items():
        out.append(f"| {name} | " + " | ".join(fmt.format(vals[c]) if isinstance(vals.get(c), float)
                                               else str(vals.get(c, "-")) for c in cols) + " |")
    return "\n".join(out)


def main():
    path = config.RESULTS_DIR / "metrics.json"
    if not path.exists():
        sys.exit(f"{path} not found - run scripts/train_eval.py first.")
    m = json.loads(path.read_text())
    metrics = ["rank1", "rank5", "mAP"]

    print(f"Setup: `{m['setup']}`\n")
    if m.get("attributes"):
        print("### Attribute recognition accuracy (%)\n")
        print(table(m["attributes"], ["zero_shot_acc", "linear_probe_acc", "n_test"], "attribute"), "\n")
    if m.get("description_search"):
        print("### Stage 1 - description search (%)\n")
        print(table(m["description_search"], metrics, "query"), "\n")

    print("### Stage 2 - Re-ID ablation, plates hidden (%)\n")
    hidden = dict(sorted(m["reid"]["hidden"].items(), key=lambda kv: -kv[1]["mAP"]))
    print(table(hidden, metrics, "method"), "\n")

    print("### Plate robustness - mAP (%) by plate visibility\n")
    methods = ["appearance only", "plate_sim", "weighted fusion", "random forest"]
    rows = {meth: {lvl: m["reid"][lvl][meth]["mAP"] for lvl in m["reid"]} for meth in methods}
    print(table(rows, list(m["reid"]), "method"), "\n")

    som = m["som"]
    print(f"### SOM ({som['grid']}x{som['grid']})\n")
    print(f"Purity - vehicle ID {som['purity_vehicle_id']:.2f}, colour {som['purity_color']:.2f}, "
          f"type {som['purity_type']:.2f}\n")
    print(table(som["prefilter"], ["candidates_kept_%", "true_match_recall_%"] + metrics, "pre-filter"))


if __name__ == "__main__":
    main()
