#!/usr/bin/env python3
"""Generate neutral placeholder badge and banner (not copied from the PA artwork)."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import shapefile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SHP = Path("/workspace/nc-home-data/cb_2024_us_county_500k/cb_2024_us_county_500k.shp")
NAVY = (16, 42, 67)
NAVY_DEEP = (10, 28, 46)
GOLD = (215, 166, 79)
CREAM = (247, 242, 232)
INK = (23, 38, 56)

LON0, LAT0, LAT1, LAT2 = -79.9, 34.8, 34.333, 36.166
R = 6378137.0


def albers(lon, lat):
    phi, lam = math.radians(lat), math.radians(lon)
    phi0, phi1, phi2, lam0 = map(math.radians, (LAT0, LAT1, LAT2, LON0))
    n = 0.5 * (math.sin(phi1) + math.sin(phi2))
    c = math.cos(phi1) ** 2 + 2 * n * math.sin(phi1)
    rho = R * math.sqrt(c - 2 * n * math.sin(phi)) / n
    rho0 = R * math.sqrt(c - 2 * n * math.sin(phi0)) / n
    theta = n * (lam - lam0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def county_projected():
    reader = shapefile.Reader(str(SHP))
    fields = [f[0] for f in reader.fields[1:]]
    rings = []
    for sr in reader.iterShapeRecords():
        rec = dict(zip(fields, sr.record))
        if str(rec.get("STATEFP")) != "37":
            continue
        pts = list(sr.shape.points)
        parts = list(sr.shape.parts) + [len(pts)]
        for i in range(len(parts) - 1):
            ring = pts[parts[i] : parts[i + 1]]
            if len(ring) >= 4:
                rings.append([albers(lon, lat) for lon, lat in ring])
    return rings


def fit(rings, w, h, pad):
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    scale = min((w - 2 * pad) / (maxx - minx), (h - 2 * pad) / (maxy - miny))
    # center
    ox = (w - (maxx - minx) * scale) / 2 - minx * scale
    oy = (h - (maxy - miny) * scale) / 2

    def tx(x, y):
        return x * scale + ox, (maxy - y) * scale + oy - (maxy - maxy) * 0

    # redo oy properly
    def tx2(x, y):
        sx = (x - minx) * scale + (w - (maxx - minx) * scale) / 2
        sy = (maxy - y) * scale + (h - (maxy - miny) * scale) / 2
        return sx, sy

    return [[tx2(x, y) for x, y in ring] for ring in rings]


def write_badge():
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((16, 16, size - 17, size - 17), fill=NAVY)
    d.ellipse((48, 48, size - 49, size - 49), outline=GOLD, width=28)
    d.ellipse((88, 88, size - 89, size - 89), outline=(229, 200, 139), width=4)
    # small gold bars
    d.rectangle((320, 250, 704, 262), fill=GOLD)
    d.rectangle((320, 760, 704, 772), fill=GOLD)
    f = font(320, bold=True)
    text = "NC"
    bbox = d.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) / 2 - bbox[0], 300), text, font=f, fill=CREAM)
    f2 = font(72, bold=True)
    label = "CIVIC ATLAS"
    bbox = d.textbbox((0, 0), label, font=f2)
    tw = bbox[2] - bbox[0]
    d.text(((size - tw) / 2 - bbox[0], 670), label, font=f2, fill=GOLD)
    out = ASSETS / "nc-badge.png"
    img.save(out, "PNG")
    # also a simple SVG sibling for crisp favicons
    (ASSETS / "nc-badge.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" role="img" aria-label="North Carolina Civic Atlas placeholder badge">
<circle cx="128" cy="128" r="124" fill="#102a43"/>
<circle cx="128" cy="128" r="112" fill="none" stroke="#d7a64f" stroke-width="8"/>
<circle cx="128" cy="128" r="102" fill="none" stroke="#e5c88b" stroke-width="1.5"/>
<rect x="78" y="64" width="100" height="3" fill="#d7a64f"/>
<text x="128" y="148" text-anchor="middle" font-family="Georgia, serif" font-size="86" font-weight="700" fill="#f7f2e8">NC</text>
<text x="128" y="186" text-anchor="middle" font-family="Georgia, serif" font-size="16" font-weight="700" letter-spacing="2" fill="#d7a64f">CIVIC ATLAS</text>
<rect x="78" y="198" width="100" height="3" fill="#d7a64f"/>
</svg>
""",
        encoding="utf-8",
    )
    print("badge", out, out.stat().st_size)


def write_banner():
    w, h = 1920, 720
    img = Image.new("RGB", (w, h), NAVY_DEEP)
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        r = int(NAVY_DEEP[0] * (1 - t) + 20 * t)
        g = int(NAVY_DEEP[1] * (1 - t) + 52 * t)
        b = int(NAVY_DEEP[2] * (1 - t) + 74 * t)
        for x in range(w):
            # subtle left-to-right warmth
            s = x / (w - 1)
            px[x, y] = (
                min(255, r + int(8 * s)),
                min(255, g + int(6 * s)),
                min(255, b),
            )
    rings = fit(county_projected(), w, h, pad=70)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for ring in rings:
        if len(ring) >= 4:
            od.polygon(ring, fill=(215, 166, 79, 28), outline=(215, 166, 79, 90))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    # gold hairline at bottom
    d = ImageDraw.Draw(img)
    d.rectangle((0, h - 16, w, h), fill=GOLD)
    out = ASSETS / "nc-banner.jpg"
    img.save(out, "JPEG", quality=90)
    print("banner", out, out.stat().st_size)


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    write_badge()
    write_banner()
