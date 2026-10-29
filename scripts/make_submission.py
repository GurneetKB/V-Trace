"""Package the Canvas submission ZIP (one ZIP per team; the individual report is submitted separately).

    python scripts/make_submission.py

Creates submission/Group21_V-Trace_Submission.zip with:
  code/          every git-tracked file (source, tests, docs, results, trained models, demo bundle)
  datasets/      the four demo camera videos (VeRi-776 must be requested from its authors; see README)
  deliverables/  final report (.docx/.pdf), final + first presentation slides, demo guide, video (*.mp4) if present
"""
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vtrace import config  # noqa: E402

OUT = ROOT / "submission" / "Group21_V-Trace_Submission.zip"
DEMO = ["camA_west.mp4", "camB_centre.mp4", "camC_east.mp4", "camD_other_road.mp4"]


def main():
    OUT.parent.mkdir(exist_ok=True)
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    entries = [(ROOT / f, f"code/{f}") for f in tracked if f and (ROOT / f).is_file()]
    entries += [(config.VIDEO_DIR / n, f"datasets/demo_cameras/{n}") for n in DEMO if (config.VIDEO_DIR / n).exists()]
    for p in sorted((ROOT / "deliverables").glob("*")):
        if p.is_file() and "Individual_Report" not in p.name:
            entries.append((p, f"deliverables/{p.name}"))
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in entries:
            z.write(src, f"Group21_V-Trace/{arc}")
    missing = [n for n in DEMO if not (config.VIDEO_DIR / n).exists()]
    have = {Path(a).name for _, a in entries}
    for want in ("V-Trace_Final_Report.pdf", "V-Trace_Final_Presentation.pptx", "V-Trace_First_Presentation.pptx"):
        if want not in have:
            missing.append(want)
    if not any(n.endswith(".mp4") for n in have if not n.startswith("cam")):
        missing.append("video presentation (.mp4) in deliverables/")
    print(f"{OUT}  ({OUT.stat().st_size / 1e6:.0f} MB, {len(entries)} files)")
    if missing:
        print("Not included yet:", ", ".join(missing))


if __name__ == "__main__":
    main()
