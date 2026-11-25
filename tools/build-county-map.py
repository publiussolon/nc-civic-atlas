#!/usr/bin/env python3
"""Build North Carolina county SVG and Phase 1 JSON from official public sources."""
from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from pathlib import Path

try:
    import shapefile  # pyshp
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pyshp is required: pip install pyshp") from exc

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("/workspace/nc-home-data")
SHP = DATA / "cb_2024_us_county_500k" / "cb_2024_us_county_500k.shp"
POP_CSV = DATA / "co-est2025-alldata.csv"
SITES = DATA / "nc-county-websites.json"

WIDTH = 1000
PAD = 18
# Spherical Albers (meters). Standard parallels sit near NC's south and north edges.
LON0, LAT0, LAT1, LAT2 = -79.9, 34.8, 34.333, 36.166
R = 6378137.0

CHECKED = "2026-11-24"
POP_YEAR = 2025
POP_AS_OF = "2025-07-01"
POP_SOURCE = "https://www2.census.gov/programs-surveys/popest/tables/2020-2025/counties/totals/co-est2025-pop-37.xlsx"
POP_SOURCE_PAGE = "https://www.census.gov/data/datasets/time-series/demo/popest/2020s-counties-total.html"
BOUNDARY_PAGE = "https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html"
BOUNDARY_FILE = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
DIRECTORY = "https://www.nc.gov/your-government/county-government-websites"


def albers(lon: float, lat: float) -> tuple[float, float]:
    phi, lam = math.radians(lat), math.radians(lon)
    phi0, phi1, phi2, lam0 = map(math.radians, (LAT0, LAT1, LAT2, LON0))
    n = 0.5 * (math.sin(phi1) + math.sin(phi2))
    c = math.cos(phi1) ** 2 + 2 * n * math.sin(phi1)
    rho = R * math.sqrt(c - 2 * n * math.sin(phi)) / n
    rho0 = R * math.sqrt(c - 2 * n * math.sin(phi0)) / n
    theta = n * (lam - lam0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def load_sites() -> dict[str, str]:
    rows = json.loads(SITES.read_text())
    return {row["county"]: row["government_url"] for row in rows}


def load_population() -> dict[str, dict]:
    text = POP_CSV.read_text(encoding="latin-1")
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row["STATE"] != "37" or row["COUNTY"] in {"000", "0"}:
            continue
        name = row["CTYNAME"].removesuffix(" County")
        out[name] = {
            "population": int(row["POPESTIMATE2025"]),
            "fips": row["STATE"] + row["COUNTY"].zfill(3),
        }
    return out


def shape_rings(shape) -> list[list[tuple[float, float]]]:
    pts = list(shape.points)
    parts = list(shape.parts) + [len(pts)]
    rings = []
    for i in range(len(parts) - 1):
        ring = pts[parts[i] : parts[i + 1]]
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def path_d(rings, to_svg) -> str:
    parts = []
    for ring in rings:
        coords = [to_svg(x, y) for x, y in ring]
        # drop closing duplicate if present
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]
        if len(coords) < 3:
            continue
        d = "M" + " ".join(f"{x:.1f},{y:.1f}" for x, y in coords) + "Z"
        parts.append(d)
    return " ".join(parts)


def build_svg(counties_geom: list[dict]) -> str:
    xs, ys = [], []
    for rec in counties_geom:
        for ring in rec["rings"]:
            for lon, lat in ring:
                x, y = albers(lon, lat)
                xs.append(x)
                ys.append(y)
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    span_x = maxx - minx
    span_y = maxy - miny
    inner_w = WIDTH - 2 * PAD
    scale = inner_w / span_x
    inner_h = span_y * scale
    height = inner_h + 2 * PAD

    def to_svg(lon, lat):
        x, y = albers(lon, lat)
        sx = PAD + (x - minx) * scale
        sy = PAD + (maxy - y) * scale  # SVG y-down
        return sx, sy

    paths = []
    for rec in sorted(counties_geom, key=lambda r: r["name"]):
        d = path_d(rec["rings"], to_svg)
        if not d:
            raise SystemExit(f"No path for {rec['name']}")
        name = rec["name"]
        paths.append(
            f'<path data-county="{name}" fill-rule="evenodd" d="{d}">'
            f"<title>{name} County</title></path>"
        )
    label = "Interactive map of North Carolina counties"
    desc = (
        "County boundaries from the U.S. Census Bureau Cartographic Boundary File, "
        "1:500,000, 2024 (cb_2024_us_county_500k), filtered to state FIPS 37. "
        "Select a county to see its civic profile."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH:.0f} {height:.1f}" '
        f'role="img" aria-label="{label}">\n'
        f"<desc>{desc}</desc>\n"
        + "\n".join(paths)
        + "\n</svg>\n"
    )


def main() -> None:
    sites = load_sites()
    pop = load_population()
    if len(sites) != 100 or len(pop) != 100:
        raise SystemExit(f"Expected 100 counties, got sites={len(sites)} pop={len(pop)}")
    missing_pop = sorted(set(sites) - set(pop))
    missing_sites = sorted(set(pop) - set(sites))
    if missing_pop or missing_sites:
        raise SystemExit(f"Name mismatch pop-only={missing_pop} sites-only={missing_sites}")

    reader = shapefile.Reader(str(SHP))
    fields = [f[0] for f in reader.fields[1:]]
    geom = []
    for sr in reader.iterShapeRecords():
        rec = dict(zip(fields, sr.record))
        if str(rec.get("STATEFP")) != "37":
            continue
        name = str(rec["NAME"])
        geom.append({"name": name, "geoid": str(rec["GEOID"]), "rings": shape_rings(sr.shape)})
    if len(geom) != 100:
        raise SystemExit(f"Expected 100 NC shapes, got {len(geom)}")
    names = {g["name"] for g in geom}
    if names != set(sites):
        raise SystemExit(f"Shapefile name mismatch: {sorted(names ^ set(sites))}")

    svg = build_svg(geom)
    (ROOT / "county-map.svg").write_text(svg, encoding="utf-8")

    map_data = {
        "population_year": POP_YEAR,
        "population_as_of": POP_AS_OF,
        "population_source": POP_SOURCE,
        "population_source_page": POP_SOURCE_PAGE,
        "population_also_published_as": "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv",
        "boundary_source": BOUNDARY_FILE,
        "boundary_source_page": BOUNDARY_PAGE,
        "boundary_vintage": "Census Cartographic Boundary File 2024, 1:500,000, state FIPS 37",
        "party_control_definition": "Majority party of the county board of commissioners, not how the county voted in an election. Not yet verified for any North Carolina county in this Phase 1 release.",
        "checked_at": CHECKED,
        "counties": {
            name: {
                "fips": pop[name]["fips"],
                "population": pop[name]["population"],
                "party_control": None,
                "party_control_as_of": None,
                "party_source": None,
            }
            for name in sorted(sites)
        },
    }
    (ROOT / "map-data.json").write_text(json.dumps(map_data, indent=2) + "\n", encoding="utf-8")

    seed = {
        "schema_version": "0.1",
        "retrieved_at": CHECKED,
        "description": "Official North Carolina county government websites copied from the NC.gov county website directory. A directory listing does not establish current officeholders, budget amounts, or meeting records.",
        "verification_labels": {
            "source_directory_verified": "The URL was copied from the official NC.gov county government website directory on the retrieval date; the linked site can change, and individual records such as budgets and agendas have not yet been ingested."
        },
        "directory_source": {
            "title": "County Government Websites | nc.gov",
            "url": DIRECTORY,
        },
        "counties": [
            {
                "county": name,
                "government_url": url,
                "sources": [
                    {
                        "category": "county_website",
                        "title": f"{name} County government website",
                        "url": url,
                        "description": "Official county website as listed on the NC.gov county government website directory.",
                        "retrieved_at": CHECKED,
                        "verification": "source_directory_verified",
                    }
                ],
            }
            for name, url in sorted(sites.items())
        ],
    }
    (ROOT / "seed-records.json").write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote SVG ({(ROOT / 'county-map.svg').stat().st_size} bytes), map-data.json, seed-records.json")
    print(f"Counties: {len(sites)}; statewide 2025 pop from county file is not summed here.")
    print("First three:", list(sorted(sites))[:3], pop[sorted(sites)[0]])


if __name__ == "__main__":
    main()
