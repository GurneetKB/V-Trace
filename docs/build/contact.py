"""Tile rendered slide PNGs into contact sheets (2 x 3 per sheet) for visual QA."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
src, out = Path(sys.argv[1]), Path(sys.argv[2])
files = sorted(src.glob("slide-*.png"))
for k in range(0, len(files), 6):
    sheet = Image.new("RGB", (2 * 1000 + 30, 3 * 562 + 40), "white")
    for j, f in enumerate(files[k:k + 6]):
        im = Image.open(f).convert("RGB").resize((1000, 562))
        x, y = 10 + (j % 2) * 1010, 10 + (j // 2) * 572
        sheet.paste(im, (x, y))
        ImageDraw.Draw(sheet).rectangle([x, y, x + 999, y + 561], outline="gray")
    sheet.save(out / f"sheet-{k // 6 + 1}.jpg", quality=85)
    print(out / f"sheet-{k // 6 + 1}.jpg")
