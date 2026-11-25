#!/usr/bin/env python3
"""Build North Carolina War Map data from official public sources and the NYT 2024 precinct dataset."""

from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import shapefile
from shapely import make_valid
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("/workspace/nc-home-data")
PHASE3 = DATA / "phase3"
OUT_WM = ROOT / "war_map"
OUT_DATA = OUT_WM / "data"
OUT_DIST = OUT_WM / "districts"
OUT_COMM = OUT_WM / "committee"

# Display paths use x = 760(lon + 85), y = 1000(37 − lat). Keep in sync with war-map.js.
LON0 = 85.0
LAT0 = 37.0
SX = 760.0
SY = 1000.0
SIMPLIFY_DEG = 0.0003
COORD_QUANT = 6

CREDIT = (
    "2024 Precinct-Level Election Results, The New York Times; "
    "precinct identifiers cross-checked against the North Carolina State Board of Elections "
    "November 5, 2024 precinct results file. See README.md and NYT-LICENSE.txt. "
    "Redistribution subject to NYT C-UDA."
)

TRUMP_NAMES = ("Donald J. Trump",)
HARRIS_NAMES = ("Kamala D. Harris",)


def title_county(name: str, lookup: dict[str, str]) -> str:
    key = name.strip().upper()
    if key not in lookup:
        raise SystemExit(f"Unknown county in official results: {name}")
    return lookup[key]


def project(lon: float, lat: float) -> tuple[float, float]:
    return (SX * (lon + LON0), SY * (LAT0 - lat))


def fmt_num(n: float) -> str:
    s = f"{n:.2f}"
    if s.endswith("0"):
        s = s[:-1]
    if s.endswith("0"):
        s = s[:-1]
    if s.endswith("."):
        s = s[:-1]
    return s


def polygonal(geom):
    geom = make_valid(geom)
    if geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return geom
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, GeometryCollection):
        polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon)) and not g.is_empty]
        if not polys:
            return None
        merged = unary_union(polys)
        return polygonal(merged)
    # try to extract
    try:
        merged = unary_union([g for g in getattr(geom, "geoms", []) if g.geom_type in {"Polygon", "MultiPolygon"}])
        return polygonal(merged) if not merged.is_empty else None
    except Exception:
        return None


def simplify_geom(geom, tol: float):
    g = polygonal(geom)
    if g is None:
        return None
    s = polygonal(g.simplify(tol, preserve_topology=True))
    if s is None or s.is_empty or s.area == 0:
        s = polygonal(g.simplify(tol / 3, preserve_topology=True))
    if s is None or s.is_empty or s.area == 0:
        return g
    return s


def rings_of(geom):
    geoms = [geom] if isinstance(geom, Polygon) else list(geom.geoms)
    rings = []
    for poly in geoms:
        ext = list(poly.exterior.coords)
        rings.append(ext)
        for hole in poly.interiors:
            rings.append(list(hole.coords))
    return rings


def path_from_geom(geom) -> str:
    parts = []
    for ring in rings_of(geom):
        pts = [project(x, y) for x, y in ring]
        if len(pts) >= 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            continue
        parts.append("M" + " ".join(f"{fmt_num(x)},{fmt_num(y)}" for x, y in pts) + "Z")
    return " ".join(parts)


def match_official_precinct(pid: str, targets: dict) -> str | None:
    if pid in targets:
        return pid
    upper = {p.upper(): p for p in targets}
    if pid.upper() in upper:
        return upper[pid.upper()]
    for t in targets:
        if pid.lstrip("0") and pid.lstrip("0") == t.lstrip("0"):
            return t
        if pid == t.split(".")[0] or t == pid.split(".")[0]:
            return t
    return None


def load_map_meta():
    return json.loads((ROOT / "map-data.json").read_text())


def load_official_president(name_upper: dict[str, str]):
    z = zipfile.ZipFile(PHASE3 / "results_pct_20241105.zip")
    text = z.read("results_pct_20241105.txt").decode("utf-8-sig", "replace")
    rows = csv.DictReader(io.StringIO(text), delimiter="\t")
    agg = defaultdict(lambda: {"trump": 0, "harris": 0, "other": 0, "total": 0})
    for row in rows:
        if (row.get("Contest Name") or "").strip() != "US PRESIDENT":
            continue
        county = title_county(row.get("County") or "", name_upper)
        precinct = (row.get("Precinct") or "").strip()
        real = (row.get("Real Precinct") or "").strip()
        choice = (row.get("Choice") or "").strip()
        tot = int(row.get("Total Votes") or 0)
        rec = agg[(county, precinct, real)]
        rec["total"] += tot
        if any(choice == n or n in choice for n in TRUMP_NAMES) or choice.startswith("Donald J. Trump"):
            rec["trump"] += tot
        elif any(choice == n or n in choice for n in HARRIS_NAMES) or "Harris" in choice and "Kamala" in choice:
            rec["harris"] += tot
        else:
            rec["other"] += tot
    return agg


def write_official_csv(agg, path: Path):
    rows = []
    for (county, precinct, real), v in sorted(agg.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        rows.append({
            "county": county,
            "precinct": precinct,
            "real_precinct": real,
            "trump": v["trump"],
            "harris": v["harris"],
            "other": v["other"],
            "total": v["total"],
        })
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


def iter_nyt_features():
    path = PHASE3 / "NC-precincts-with-results.geojson.gz"
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    for feat in data["features"]:
        yield feat


def shapefile_to_geojson(shp_path: Path, district_field: str, state_fips: str | None, keep_props):
    r = shapefile.Reader(str(shp_path))
    features = []
    for sr in r.iterShapeRecords():
        rec = sr.record.as_dict()
        if state_fips and rec.get("STATEFP") != state_fips:
            continue
        geom = shape(sr.shape.__geo_interface__)
        geom = simplify_geom(geom, 0.0004)
        if geom is None:
            continue
        # quantize
        gj = mapping(geom)
        def q(coords):
            if coords and isinstance(coords[0], (int, float)):
                return [round(coords[0], 5), round(coords[1], 5)]
            return [q(c) for c in coords]
        gj["coordinates"] = q(gj["coordinates"])
        raw = rec[district_field]
        district = int(str(raw).lstrip("0") or "0")
        features.append({
            "type": "Feature",
            "properties": {"district": district},
            "geometry": gj,
        })
    features.sort(key=lambda f: f["properties"]["district"])
    return {"type": "FeatureCollection", "features": features}


def county_polygons():
    r = shapefile.Reader(str(DATA / "cb_2024_us_county_500k/cb_2024_us_county_500k.shp"))
    out = {}
    minx = miny = 1e9
    maxx = maxy = -1e9
    for sr in r.iterShapeRecords():
        rec = sr.record.as_dict()
        if rec["STATEFP"] != "37":
            continue
        name = rec["NAME"]
        geom = shape(sr.shape.__geo_interface__)
        geom = simplify_geom(geom, 0.0004) or geom
        b = geom.bounds
        minx, miny = min(minx, b[0]), min(miny, b[1])
        maxx, maxy = max(maxx, b[2]), max(maxy, b[3])
        gj = mapping(geom)
        def q(coords):
            if coords and isinstance(coords[0], (int, float)):
                return [round(coords[0], 5), round(coords[1], 5)]
            return [q(c) for c in coords]
        gj["coordinates"] = q(gj["coordinates"])
        out[name] = gj
    return out, [minx, miny, maxx, maxy]


def build_members():
    src = json.loads((ROOT / "nc-legislators.json").read_text())
    members = {"house": {}, "senate": {}, "congress": {}}
    for county in src["counties"]:
        for chamber in members:
            for m in county[chamber]:
                d = str(m["district"])
                entry = {"name": m["name"], "url": m["profile_url"], "party": m["party"]}
                if d in members[chamber] and members[chamber][d] != entry:
                    raise SystemExit(f"Conflicting members for {chamber} {d}")
                members[chamber][d] = entry
    expected = {"house": 120, "senate": 50, "congress": 14}
    for chamber, n in expected.items():
        have = {int(k) for k in members[chamber]}
        missing = [i for i in range(1, n + 1) if i not in have]
        if missing:
            raise SystemExit(f"{chamber} missing districts: {missing}")
    (OUT_DIST / "members.json").write_text(json.dumps(members, indent=2, ensure_ascii=False) + "\n")
    (OUT_DIST / "members-source.md").write_text(
        f"""# North Carolina district officeholders

Checked {src['as_of']}. The map lists the officeholders in the published 2025–2026 North Carolina General Assembly and the 119th U.S. House directories. Each entry links to the official member profile or office website. Party is the affiliation listed by that chamber.

| Chamber | Districts listed | Directory |
| --- | ---: | --- |
| North Carolina House | 120 | [House Members](https://www.ncleg.gov/Members/MemberList/H) |
| North Carolina Senate | 50 | [Senate Members](https://www.ncleg.gov/Members/MemberList/S) |
| U.S. House, North Carolina delegation | 14 | [U.S. House Directory of Representatives](https://www.house.gov/representatives) |

The district lists use the atlas’s [{src['as_of']} state roster](../../nc-legislators.json). Members serving more than one county are counted once by district. The federal list uses the North Carolina table in the U.S. House directory. Each directory supplied an officeholder for every numbered district at the time checked.

{src['scope']}

Sitting officeholders can differ from November 2026 election winners. The map uses this dated roster alongside the November 5, 2024 presidential election.
"""
    )
    (OUT_DIST / "README.md").write_text(
        """# District boundaries and officeholders

State House, State Senate, and U.S. House district polygons are from the U.S. Census Bureau Cartographic Boundary Files, 2024, 1:500,000:

- [State legislative districts (lower chamber)](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_37_sldl_500k.zip)
- [State legislative districts (upper chamber)](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_37_sldu_500k.zip)
- [119th Congressional Districts](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip) (North Carolina features only)

The Census publication page is [Cartographic Boundary Files](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html). Geometries were slightly simplified for web display. Near a district line, confirm a resident’s district with the [N.C. General Assembly Find Your Legislators](https://www.ncleg.gov/FindYourLegislators) tool or the [U.S. House](https://www.house.gov/representatives/find-your-representative) lookup.

Officeholders are documented in [members-source.md](members-source.md).
"""
    )
    return members


def write_committee_stub():
    summary = {
        "status": "todo",
        "note": "County party committee seat vacancies have not been compiled from a complete official public source in this release. No counts are estimated.",
        "as_of": None,
        "total": {},
        "counties": {},
    }
    (OUT_COMM / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT_COMM / "README.md").write_text(
        """# Committee seats (TODO)

The Pennsylvania War Map layered “empty chairs” for county party committee seats from public rosters and election results. A comparable, complete official public dataset for North Carolina county party committee seats was not located for this release.

This folder holds only a stub `summary.json` so the map can load without inventing vacancy counts. Counties are shown in gray on the Empty chairs layer until a sourced roster is added.

Do not infer vacancies from unofficial lists or from election results that do not identify committee seats.
"""
    )


def write_data_readme(report: dict):
    (OUT_DATA / "README.md").write_text(
        f"""# War Map precinct data

## Sources

Presidential precinct polygons and vote totals come from the New York Times [2024 Precinct-Level Election Results](https://www.nytimes.com/interactive/2025/us/elections/2024-election-map-precinct-results.html) North Carolina file. NYT documents the North Carolina shapes as official boundaries. The dataset is redistributed here under the [NYT Computational Use of Data Agreement (non-commercial, with attribution)](NYT-LICENSE.txt).

“2024 Precinct-Level Election Results.” *New York Times*, https://www.nytimes.com/interactive/2025/us/elections/2024-election-map-precinct-results.html. Accessed 2026-11-24.

Official November 5, 2024 precinct-level returns for US President were downloaded from the [North Carolina State Board of Elections historical results](https://www.ncsbe.gov/results-data/election-results/historical-election-results-data) file `results_pct_20241105.zip` (also published at https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/results_pct_20241105.zip). A compact extract of that contest is in [state-reported-2024.csv](state-reported-2024.csv).

County outlines on the map are dissolved from the [Census 2024 cartographic county file](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip).

## Matching and coverage

- The NYT file contains **{report['nyt_precincts']}** precinct polygons in all **100** counties. Every NYT precinct identifier matched an official NCSBE precinct code (3 Union County identifiers differed only by leading zeros).
- The official results file reports **{report['official_real_precincts']}** rows with Real Precinct = Y and **{report['official_admin_units']}** administrative reporting units (Real Precinct = N), such as early-voting sites and absentee/provisional tallies.
- Official Real Precinct = Y rows generally do **not** include early, absentee, or provisional ballots when those ballots are reported in the administrative units. Mapping only the Y rows would omit about {report['official_admin_votes']:,} votes. The map therefore uses the NYT precinct vote totals, which nearly match the official statewide US President total.
- Official statewide US President totals: Trump {report['official_all']['trump']:,}, Harris {report['official_all']['harris']:,}, other {report['official_all']['other']:,}, total {report['official_all']['total']:,}.
- Mapped (NYT) totals: Trump {report['nyt_votes']['trump']:,}, Harris {report['nyt_votes']['harris']:,}, other {report['nyt_votes']['other']:,}, total {report['nyt_votes']['total']:,}.
- Difference (official minus mapped): {report['vote_gap']:,} votes. Three official real precincts are absent from the NYT polygons: {report['unmapped_official']}. Those three account for {report['unmapped_official_votes']:,} of the gap. The remainder is not assigned to a mapped polygon.

## Municipal outlines

TODO: a compact official municipal-boundary layer is not included in this release. Address search uses Esri’s geocoder biased to North Carolina; county and precinct names are searched locally.

## File format

Each `data/{{county-slug}}.json` file stores simplified SVG-style paths projected as `x = 760(lon + 85)`, `y = 1000(37 − lat)`, plus Trump, Harris, other, and total votes. Identifiers are NYT GEOIDs; display names are the official NCSBE precinct codes.
"""
    )


def main():
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_DIST.mkdir(parents=True, exist_ok=True)
    OUT_COMM.mkdir(parents=True, exist_ok=True)

    meta = load_map_meta()
    name_to_fips = {n: c["fips"] for n, c in meta["counties"].items()}
    fips_to_name = {c["fips"]: n for n, c in meta["counties"].items()}
    name_upper = {n.upper(): n for n in name_to_fips}

    print("Loading official US President results…", flush=True)
    official = load_official_president(name_upper)
    official_rows = write_official_csv(official, OUT_DATA / "state-reported-2024.csv")

    off_by_fips = defaultdict(dict)
    official_all = {"trump": 0, "harris": 0, "other": 0, "total": 0}
    official_real = official_admin = official_admin_votes = official_real_n = 0
    for (county, precinct, real), v in official.items():
        for k in official_all:
            official_all[k] += v[k]
        if real == "Y":
            official_real_n += 1
            off_by_fips[name_to_fips[county]][precinct] = (precinct, v, real)
        else:
            official_admin += 1
            official_admin_votes += v["total"]

    print("Loading NYT precinct GeoJSON (this can take a minute)…", flush=True)
    by_county = defaultdict(list)
    nyt_votes = {"trump": 0, "harris": 0, "other": 0, "total": 0}
    match_fuzzy = []
    unmatched = []
    official_boundary_flags = defaultdict(int)
    n_features = 0
    for feat in iter_nyt_features():
        n_features += 1
        p = feat["properties"]
        fips, pid = p["GEOID"].split("-", 1)
        county = fips_to_name[fips]
        official_boundary_flags[bool(p.get("official_boundary"))] += 1
        found = match_official_precinct(pid, off_by_fips[fips])
        display = found if found else pid
        if found and found != pid:
            match_fuzzy.append((county, pid, found))
        if not found:
            unmatched.append((county, pid))
        trump = int(p["votes_rep"])
        harris = int(p["votes_dem"])
        total = int(p["votes_total"])
        other = total - trump - harris
        nyt_votes["trump"] += trump
        nyt_votes["harris"] += harris
        nyt_votes["other"] += other
        nyt_votes["total"] += total
        geom = simplify_geom(shape(feat["geometry"]), SIMPLIFY_DEG)
        if geom is None:
            raise SystemExit(f"Empty geometry after simplify: {p['GEOID']}")
        path = path_from_geom(geom)
        if not path:
            raise SystemExit(f"Empty path after project: {p['GEOID']}")
        by_county[county].append({
            "id": p["GEOID"],
            "name": display,
            "municipality": "",
            "path": path,
            "trump": trump,
            "harris": harris,
            "other": other,
            "total": total,
        })

    if unmatched:
        raise SystemExit(f"Unmatched NYT precincts: {unmatched}")

    # Official real precincts not in the map
    nyt_ids = {rec["name"].upper() for recs in by_county.values() for rec in recs}
    # also include original pid variants from fuzzy
    nyt_raw = set()
    # Use ids too
    unmapped = []
    unmapped_votes = 0
    mapped_official_names = {rec["name"] for recs in by_county.values() for rec in recs}
    for fips, targets in off_by_fips.items():
        county = fips_to_name[fips]
        for precinct, (_p, v, real) in targets.items():
            if precinct in mapped_official_names:
                continue
            # maybe this official code is a leading-zero variant already stored as display name
            if any(match_official_precinct(precinct, {rec["name"]: rec}) for rec in by_county[county]):
                continue
            unmapped.append({"county": county, "precinct": precinct, **v})
            unmapped_votes += v["total"]

    place_index = {}
    county_stats = {}
    for county, recs in by_county.items():
        recs.sort(key=lambda r: r["name"])
        slug = county.lower().replace(" ", "-")
        payload = {"county": county, "credit": CREDIT, "precincts": recs}
        (OUT_DATA / f"{slug}.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
        place_index[county] = {
            "places": [],
            "precincts": [[r["name"], r["municipality"], r["id"]] for r in recs],
        }
        trump = sum(r["trump"] for r in recs)
        harris = sum(r["harris"] for r in recs)
        total = sum(r["total"] for r in recs)
        county_stats[county] = {
            "precincts": len(recs),
            "trump": trump,
            "harris": harris,
            "total": total,
            "trump_led": sum(1 for r in recs if r["trump"] > r["harris"]),
            "harris_led": sum(1 for r in recs if r["harris"] > r["trump"]),
        }

    print("Building county outlines…", flush=True)
    outlines, bbox = county_polygons()
    missing = [n for n in name_to_fips if n not in outlines]
    if missing:
        raise SystemExit(f"County outline missing: {missing}")
    county_fc = {"type": "FeatureCollection", "features": []}
    for county in sorted(name_to_fips):
        props = {"county": county, **county_stats[county]}
        county_fc["features"].append({"type": "Feature", "properties": props, "geometry": outlines[county]})
    (OUT_WM / "counties.geojson").write_text(json.dumps(county_fc, separators=(",", ":"), ensure_ascii=False) + "\n")
    (OUT_WM / "place-index.json").write_text(json.dumps(place_index, separators=(",", ":"), ensure_ascii=False) + "\n")

    print("Building district GeoJSON…", flush=True)
    house = shapefile_to_geojson(PHASE3 / "sldl/cb_2024_37_sldl_500k.shp", "SLDLST", "37", None)
    senate = shapefile_to_geojson(PHASE3 / "sldu/cb_2024_37_sldu_500k.shp", "SLDUST", "37", None)
    congress = shapefile_to_geojson(PHASE3 / "cd119/cb_2024_us_cd119_500k.shp", "CD119FP", "37", None)
    if len(house["features"]) != 120 or len(senate["features"]) != 50 or len(congress["features"]) != 14:
        raise SystemExit(
            f"Unexpected district counts: house {len(house['features'])}, senate {len(senate['features'])}, congress {len(congress['features'])}"
        )
    (OUT_DIST / "house.geojson").write_text(json.dumps(house, separators=(",", ":")) + "\n")
    (OUT_DIST / "senate.geojson").write_text(json.dumps(senate, separators=(",", ":")) + "\n")
    (OUT_DIST / "congress.geojson").write_text(json.dumps(congress, separators=(",", ":")) + "\n")
    build_members()
    write_committee_stub()

    report = {
        "nyt_precincts": n_features,
        "official_real_precincts": official_real_n,
        "official_admin_units": official_admin,
        "official_admin_votes": official_admin_votes,
        "official_all": official_all,
        "nyt_votes": nyt_votes,
        "vote_gap": official_all["total"] - nyt_votes["total"],
        "unmapped_official": ", ".join(f"{u['county']} {u['precinct']} ({u['total']} votes)" for u in unmapped) or "none",
        "unmapped_official_votes": unmapped_votes,
        "fuzzy_matches": match_fuzzy,
        "official_boundary_flags": dict(official_boundary_flags),
        "bbox": bbox,
        "counties": len(by_county),
    }
    write_data_readme(report)
    (OUT_WM / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    # sizes
    data_bytes = sum(p.stat().st_size for p in OUT_DATA.glob("*.json"))
    print(f"Per-county JSON bytes: {data_bytes:,}")
    print(f"counties.geojson: {(OUT_WM / 'counties.geojson').stat().st_size:,}")
    for name in ("house", "senate", "congress"):
        print(f"{name}.geojson: {(OUT_DIST / (name + '.geojson')).stat().st_size:,}")


if __name__ == "__main__":
    sys.exit(main())
