"""Build the report deliverables: .docx (python-docx) and .pdf (styled HTML printed by headless Edge).

    python docs/build/make_reports.py

docs/REPORT.md            -> deliverables/V-Trace_Final_Report.docx/.pdf    ({{...}} filled from results/demo_eval.json)
docs/INDIVIDUAL_REPORT.md -> deliverables/V-Trace_Individual_Report_Gurneet_Kaur_Bhuller.docx/.pdf
docs/DEMO_GUIDE.md        -> deliverables/V-Trace_Demo_Guide.docx/.pdf
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from md2docx import convert  # noqa: E402
import md2pdf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DOCS, OUT, RES = ROOT / "docs", ROOT / "deliverables", ROOT / "results"
LOGO = ROOT / "assets" / "nus_iss_logo.png"
AUTHOR = "Gurneet Kaur Bhuller (A0354164E) · Group 21"
COURSE = "Graduate Certificate in Pattern Recognition Systems · Practice Module"


def _table(header, rows):
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] +
                     ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def fill(md):
    m = json.loads((RES / "metrics.json").read_text())
    d = json.loads((RES / "demo_eval.json").read_text())
    f1 = lambda v: f"{v:.1f}"
    vals = {}
    for prefix, methods in (("", d["methods"]), ("nw", d["methods_no_window"])):
        for key, name in (("rf", "random forest"), ("app", "appearance only"), ("lm", "learned metric"), ("wf", "weighted fusion")):
            vals.update({f"{key}{prefix}.{k}": v for k, v in methods[name].items()})
    vals.update({f"tracking.{k}": v for k, v in d["tracking"].items()})
    vals.update({k: d[k] for k in ("vehicles_in_2plus_cameras", "vehicles_in_all_3")})
    vals["tracklets_total"] = sum(d["tracklets"].values())
    vals["tracklets_by_camera"] = ", ".join(f"{k} {v}" for k, v in d["tracklets"].items())
    vals["fail.score"] = f"{d['failure_example']['score']:.2f}"
    hid = m["reid"]["hidden"]
    vals.update({"veri.metric.r1": f1(hid["learned metric"]["rank1"]), "veri.metric.map": f1(hid["learned metric"]["mAP"]),
                 "veri.app.r1": f1(hid["appearance only"]["rank1"]), "veri.app.map": f1(hid["appearance only"]["mAP"])})
    vals.update({f"imp.{k}": f"{v:.2f}" for k, v in m["rf_feature_importance"].items()})
    som = m["som"]
    vals.update({"som.id": f"{som['purity_vehicle_id']:.2f}", "som.colour": f"{som['purity_color']:.2f}",
                 "som.type": f"{som['purity_type']:.2f}"})

    a = m["attributes"]
    vals["table.attributes"] = _table(["Attribute", "CLIP zero-shot", "Supervised linear probe"],
        [[k.capitalize() if k == "type" else "Colour", f1(v["zero_shot_acc"]), f"**{f1(v['linear_probe_acc'])}**"] for k, v in a.items()])
    vals["table.description"] = _table(["Query", "Rank-1", "Rank-5", "mAP"],
        [[k, f1(v["rank1"]), f1(v["rank5"]), f1(v["mAP"])] for k, v in m["description_search"].items()])
    names = {"learned metric": "Learned metric (LDA) only", "weighted fusion": "Weighted fusion (all cues)",
             "random forest": "Random Forest (all cues)", "clip_cos": "CLIP cosine only",
             "appearance only": "ResNet-50 appearance only", "color_hist": "HSV colour histogram only",
             "color_agree": "colour agreement only", "type_agree": "type agreement only",
             "cue_sim": "distinctive-cue agreement only"}
    order = sorted(names, key=lambda k: -hid[k]["mAP"])
    vals["table.ablation"] = _table(["Method", "Rank-1", "Rank-5", "mAP"],
        [[names[k], f1(hid[k]["rank1"]), f1(hid[k]["rank5"]), f1(hid[k]["mAP"])] for k in order])
    levels = ["clear", "partial", "blurred", "hidden"]
    pm = [("Appearance only", "appearance only"), ("Learned metric only", "learned metric"), ("Plate only", "plate_sim"),
          ("Weighted fusion", "weighted fusion"), ("Random Forest", "random forest")]
    best = {l: max(m["reid"][l][k]["mAP"] for _, k in pm if k != "plate_sim") for l in levels}
    vals["table.plates"] = _table(["Method"] + [l.capitalize() for l in levels],
        [[n] + [(f"**{f1(m['reid'][l][k]['mAP'])}**" if k != "plate_sim" and m["reid"][l][k]["mAP"] == best[l]
                 else f1(m["reid"][l][k]["mAP"])) for l in levels] for n, k in pm])
    vals["table.som"] = _table(["Radius", "Candidates kept", "True matches kept", "Rank-1", "mAP"],
        [[r.split("_")[1], f"{v['candidates_kept_%']:.1f}%", f"{v['true_match_recall_%']:.1f}%", f1(v["rank1"]), f1(v["mAP"])]
         for r, v in som["prefilter"].items()] + [["no pre-filter", "100%", "100%", f1(hid["random forest"]["rank1"]),
                                                   f1(hid["random forest"]["mAP"])]])
    cols = ["Rank-1", "Rank-5", "mAP", "route_precision", "route_recall", "camera_hit@1", "camera_hit@3"]
    head = ["Method", "Rank-1", "Rank-5", "mAP", "Route precision", "Route recall", "Camera hit@1", "Camera hit@3"]
    for key, methods in (("table.demo", d["methods"]), ("table.demo_nowindow", d["methods_no_window"])):
        vals[key] = _table(head, [[n.capitalize()] + [f1(v[c]) for c in cols] for n, v in methods.items()])

    def sub(mt):
        k = mt.group(1).strip()
        v = vals[k]
        if isinstance(v, float):
            if "purity" in k:
                return f"{v:.2f}"
            if "per_vehicle" in k:
                return f"{v:.2f}"
            return f"{v:.0f}"
        return str(v)
    out = re.sub(r"\{\{([^}]+)\}\}", sub, md)
    left = re.findall(r"\{\{[^}]+\}\}", out)
    assert not left, left
    return out


def main():
    OUT.mkdir(exist_ok=True)
    tmp = DOCS / "_REPORT.filled.md"
    tmp.write_text(fill((DOCS / "REPORT.md").read_text(encoding="utf-8")), encoding="utf-8")
    jobs = [
        (tmp, "V-Trace_Final_Report.docx", "V-Trace: Final Project Report",
         ["Multi-Attribute Vehicle Re-Identification System", AUTHOR, COURSE, "31 October 2026"], True),
        (DOCS / "INDIVIDUAL_REPORT.md", "V-Trace_Individual_Report_Gurneet_Kaur_Bhuller.docx", None, [], False),
        (DOCS / "DEMO_GUIDE.md", "V-Trace_Demo_Guide.docx", "V-Trace: Demo & Assessor Guide",
         ["How to run, sign in and try V-Trace", AUTHOR], False),
    ]
    for md, name, title, sub, toc in jobs:
        if not md.exists():
            print("skip (missing)", md.name)
            continue
        if title is None:                          # individual report: compact header, no title page
            text = md.read_text(encoding="utf-8").replace(
                "# Individual Project Report",
                f"# Individual Project Report\n\n**{AUTHOR}** · V-Trace: Multi-Attribute Vehicle Re-Identification System  \n{COURSE}", 1)
            md2 = DOCS / "_INDIVIDUAL.filled.md"
            md2.write_text(text, encoding="utf-8")
            md = md2
        out = convert(md, OUT / name, DOCS, title=title, subtitle_lines=sub, logo=LOGO,
                      footer="V-Trace · Group 21", toc=toc, margins_cm=2.2 if title else 2.0)
        print("saved", out)
        pdf = md2pdf.convert(md.read_text(encoding="utf-8"), out.with_suffix(".pdf"), DOCS, title=title,
                             subtitle_lines=sub, logo=LOGO, toc=toc)
        print("saved", pdf)
    for f in DOCS.glob("_*.filled.md"):
        f.unlink()


if __name__ == "__main__":
    main()
