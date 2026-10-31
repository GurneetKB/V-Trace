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


def fill(md):
    v = json.loads((RES / "veri_eval.json").read_text())
    d = json.loads((RES / "demo_eval.json").read_text())
    r = d["reid"]
    same, diff = v["same_vehicle_similarity_percentiles_10_50_90"], v["different_vehicle_similarity_percentiles_50_99_99.9"]
    th = v[f"threshold_{r['threshold']}"]
    vals = {"veri.rank1": f"{v['rank1']:.1f}", "veri.rank5": f"{v['rank5']:.1f}", "veri.mAP": f"{v['mAP']:.1f}",
            "veri.queries": f"{v['queries']:,}", "veri.gallery": f"{v['gallery']:,}",
            "veri.same10": f"{same[0]:.2f}", "veri.same50": f"{same[1]:.2f}", "veri.diff99": f"{diff[1]:.2f}",
            "veri.keep_same": f"{th['same_vehicle_kept_%']:.0f}", "veri.keep_diff": f"{th['different_vehicle_kept_%']:.1f}",
            "demo.tracklets_total": sum(d["tracklets"].values()),
            "demo.tracklets_by_camera": ", ".join(f"{k} {n}" for k, n in d["tracklets"].items()),
            "demo.vehicles_in_2plus_cameras": d["vehicles_in_2plus_cameras"], "demo.vehicles_in_all_3": d["vehicles_in_all_3"],
            "demo.queries": r["queries"], "demo.Rank-1": f"{r['Rank-1']:.0f}", "demo.Rank-5": f"{r['Rank-5']:.0f}",
            "demo.mAP": f"{r['mAP']:.0f}", "demo.camera_precision": f"{r['same_clock']['camera_precision_%']:.0f}",
            "demo.camera_recall": f"{r['same_clock']['camera_recall_%']:.0f}",
            "demo.false_camD": f"{r['same_clock']['queries_wrongly_seen_in_camD_%']:.0f}",
            "demo.precision_nw": f"{r['no_time_window']['camera_precision_%']:.0f}",
            "demo.recall_nw": f"{r['no_time_window']['camera_recall_%']:.0f}",
            "demo.false_camD_nw": f"{r['no_time_window']['queries_wrongly_seen_in_camD_%']:.0f}",
            "demo.clean": f"{d['tracking']['clean_tracklets_%']:.0f}"}
    out = re.sub(r"\{\{([^}]+)\}\}", lambda mt: str(vals[mt.group(1).strip()]), md)
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
