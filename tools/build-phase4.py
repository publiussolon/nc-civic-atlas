#!/usr/bin/env python3
"""Build compact North Carolina research tables from official public sources."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import openpyxl
import xlrd

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("/workspace/nc-home-data")
PHASE4 = DATA / "phase4"
OUT = ROOT / "research"

YEARS_1790_1990 = list(range(1790, 2000, 10))


def parse_count(val):
    if val is None:
        return None
    if isinstance(val, float):
        if val != val:
            return None
        return int(val)
    s = str(val).strip().replace(",", "")
    if s in ("", "---", "—", ".", "NA", "N/A"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def load_forstall_nc():
    wb = xlrd.open_workbook(PHASE4 / "population_partiii.xls")
    sh = wb.sheet_by_index(0)
    start = None
    for r in range(sh.nrows):
        if str(sh.cell_value(r, 0)).strip() == "POPULATION OF COUNTIES -- NORTH CAROLINA: 1790-1990":
            start = r
            break
    if start is None:
        raise SystemExit("North Carolina table not found in Forstall Part III")
    # header row has years
    header_row = None
    years = []
    for r in range(start, start + 6):
        vals = [sh.cell_value(r, c) for c in range(min(22, sh.ncols))]
        maybe = []
        for v in vals[1:]:
            if isinstance(v, float) and 1790 <= v <= 1990:
                maybe.append(int(v))
        if maybe and maybe[0] == 1990 and maybe[-1] == 1790:
            header_row = r
            years = maybe
            break
    if not years:
        raise SystemExit("Could not read NC year header")
    records = {}
    notes = {}
    r = header_row + 1
    while r < sh.nrows:
        name = str(sh.cell_value(r, 0)).strip()
        if name.upper() == "NORTH CAROLINA NOTES" or name.startswith("POPULATION OF COUNTIES"):
            break
        if not name:
            r += 1
            continue
        counts = {}
        for i, year in enumerate(years):
            counts[year] = parse_count(sh.cell_value(r, i + 1))
        note = " ".join(
            str(sh.cell_value(r, c)).strip()
            for c in range(1 + len(years), sh.ncols)
            if str(sh.cell_value(r, c)).strip()
        )
        key = "North Carolina" if name.upper() == "NORTH CAROLINA" else name.strip()
        records[key] = counts
        if note:
            notes[key] = note
        r += 1
    # collect state notes following the table
    state_notes = []
    while r < sh.nrows:
        val = str(sh.cell_value(r, 0)).strip()
        if val.startswith("POPULATION OF COUNTIES"):
            break
        if val:
            state_notes.append(val)
        r += 1
        if len(state_notes) > 30:
            break
    return years, records, notes, state_notes


def load_2000():
    out = {}
    with (PHASE4 / "co-est00int-tot.csv").open(encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f):
            if row["STNAME"] != "North Carolina":
                continue
            if row["SUMLEV"] == "40":
                name = "North Carolina"
            else:
                name = row["CTYNAME"].replace(" County", "").strip()
            out[name] = parse_count(row["ESTIMATESBASE2000"])
    return out


def load_2010():
    out = {}
    with (PHASE4 / "co-est2020-alldata.csv").open(encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f):
            if row["STNAME"] != "North Carolina":
                continue
            if row["SUMLEV"] == "040":
                name = "North Carolina"
            elif row["SUMLEV"] == "050":
                name = row["CTYNAME"].replace(" County", "").strip()
            else:
                continue
            out[name] = parse_count(row["CENSUS2010POP"])
    return out


def load_2020_2025():
    base2020, est2025 = {}, {}
    wb = openpyxl.load_workbook(DATA / "co-est2025-pop-37.xlsx", data_only=True)
    ws = wb.active
    for row in ws.iter_rows(min_row=5, values_only=True):
        label = str(row[0] or "").strip()
        if not label or label.startswith("Note") or label.startswith("Suggested") or label.startswith("Source"):
            continue
        if label == "North Carolina":
            name = "North Carolina"
        else:
            name = label.lstrip(".").replace(" County, North Carolina", "").replace(" County", "").strip()
        base2020[name] = parse_count(row[1])
        est2025[name] = parse_count(row[7])
    return base2020, est2025


def build_population():
    years_hist, hist, notes, state_notes = load_forstall_nc()
    # Forstall Part III lists years newest-to-oldest; store chronological.
    if years_hist and years_hist[0] > years_hist[-1]:
        years_hist = list(reversed(years_hist))
        for name, counts in hist.items():
            hist[name] = {year: counts[year] for year in years_hist}
    y2000 = load_2000()
    y2010 = load_2010()
    y2020, y2025 = load_2020_2025()
    meta = json.loads((ROOT / "map-data.json").read_text())
    counties = list(meta["counties"].keys())
    years = years_hist + [2000, 2010, 2020, 2025]
    places = {}
    missing = []
    for name in ["North Carolina"] + counties:
        series = []
        src = hist.get(name)
        if name != "North Carolina" and src is None:
            # try loose match
            for k in hist:
                if k.lower() == name.lower():
                    src = hist[k]
                    break
        for year in years_hist:
            series.append(None if src is None else src.get(year))
        series.append(y2000.get(name))
        series.append(y2010.get(name))
        series.append(y2020.get(name))
        series.append(y2025.get(name))
        if name != "North Carolina" and series[-1] is None:
            missing.append(name)
        places[name] = series
    if missing:
        raise SystemExit(f"Missing 2025 estimates for {missing}")
    # sanity: 1990 county sum vs state if complete
    payload = {
        "years": years,
        "places": places,
        "county_notes": {k: v for k, v in notes.items() if k in places},
        "state_notes": state_notes[:12],
        "as_of": "2026-11-24",
        "sources": [
            {
                "id": "forstall_1790_1990",
                "title": "U.S. Census Bureau, Population of States and Counties of the United States: 1790 to 1990, Part III, North Carolina",
                "url": "https://www2.census.gov/programs-surveys/decennial/tables/1990/population-of-states-and-counties-us-1790-1990/population_partiii.xls",
                "pdf": "https://www2.census.gov/library/publications/decennial/1990/population-of-states-and-counties-us-1790-1990/population-of-states-and-counties-of-the-united-states-1790-1990.pdf",
                "years": "1790-1990 decennial counts",
                "note": "Counts are those published for the county boundaries of each census. A missing value means the county is not reported in that census (usually because it had not yet been created). Some historical counties that no longer exist, such as the 1810 Walton listing discussed in the Census notes, are omitted from the current 100-county list.",
            },
            {
                "id": "census_2000_estimates_base",
                "title": "U.S. Census Bureau, intercensal county estimates 2000-2010, ESTIMATESBASE2000",
                "url": "https://www2.census.gov/programs-surveys/popest/datasets/2000-2010/intercensal/county/co-est00int-tot.csv",
                "years": "2000",
                "note": "April 1, 2000 estimates base, not a reprint of the originally published Census 2000 count.",
            },
            {
                "id": "census_2010",
                "title": "U.S. Census Bureau, 2010 Census county population (CENSUS2010POP) in the 2010-2020 county totals file",
                "url": "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/counties/totals/co-est2020-alldata.csv",
                "years": "2010",
            },
            {
                "id": "census_2020_base_2025_estimate",
                "title": "U.S. Census Bureau, Annual Estimates of the Resident Population for Counties in North Carolina: April 1, 2020 to July 1, 2025 (CO-EST2025-POP-37)",
                "url": "https://www2.census.gov/programs-surveys/popest/tables/2020-2025/counties/totals/co-est2025-pop-37.xlsx",
                "years": "2020 estimates base; July 1, 2025 estimate",
                "note": "The 2020 column is the April 1, 2020 estimates base. The 2025 column is the July 1, 2025 county estimate already used on the atlas map.",
            },
        ],
        "notes": [
            "Decennial counts, the 2000 and 2020 estimates bases, and the 2025 estimate are different kinds of official figures. Do not treat the last three points as additional decennial censuses.",
            "County values may not sum exactly to the state total in every historical year because of territorial notes in the Census publication, including a small 1890 prison population not reported by county.",
        ],
    }
    (OUT / "county-pop-history.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
    with (OUT / "county-pop-history.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["place"] + [str(y) for y in years])
        for name in ["North Carolina"] + counties:
            w.writerow([name] + [("" if v is None else v) for v in places[name]])
    return payload


def build_taxes():
    wb = openpyxl.load_workbook(PHASE4 / "STC-Historical-DB.xlsx", data_only=True, read_only=True)
    ws = wb.active
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0 or i == 1:
            continue
        name = str(row[2] or "")
        if name != "NC STATE GOVT":
            continue
        year = int(row[0])
        total = parse_count(row[4])  # C105 Total Taxes, thousands of dollars
        fy = row[3]
        rows.append({"year": year, "fy_ending_code": fy, "total_taxes_thousands_usd": total})
    rows.sort(key=lambda r: r["year"])
    # NCpedia / State Library chronology, 20th-21st century names as published (calendar years)
    governors = [
        {"name": "Clyde Roark Hoey", "start": 1937, "end": 1941, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Joseph Melville Broughton", "start": 1941, "end": 1945, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Robert Gregg Cherry", "start": 1945, "end": 1949, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "William Kerr Scott", "start": 1949, "end": 1953, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "William Bradley Umstead", "start": 1953, "end": 1954, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Luther Hartwell Hodges", "start": 1954, "end": 1961, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Terry Sanford", "start": 1961, "end": 1965, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Dan Killian Moore", "start": 1965, "end": 1969, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Robert Walter Scott", "start": 1969, "end": 1973, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "James Eubert Holshouser, Jr.", "start": 1973, "end": 1977, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "James Baxter Hunt, Jr.", "start": 1977, "end": 1985, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "James Grubbs Martin", "start": 1985, "end": 1993, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "James Baxter Hunt, Jr.", "start": 1993, "end": 2001, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Michael F. Easley", "start": 2001, "end": 2009, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Beverly Eaves Perdue", "start": 2009, "end": 2012, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Patrick McCrory", "start": 2013, "end": 2016, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Roy Cooper", "start": 2017, "end": 2024, "source": "https://www.ncpedia.org/biography/governors"},
        {"name": "Josh Stein", "start": 2025, "end": None, "source": "https://www.ncpedia.org/biography/governors"},
    ]
    payload = {
        "as_of": "2026-11-24",
        "units": "Thousands of dollars, Census State Tax Collections field C105 (Total Taxes).",
        "fy_note": "Census FY ending codes of the form 630YY mean a fiscal year ending June 30. Attribution to a governor uses the calendar-year ranges published by NCpedia (State Library of North Carolina / Office of Archives and History). Mid-year inaugurations are not dated in that list, so a fiscal year may overlap more than one governor.",
        "series": rows,
        "governors": governors,
        "sources": [
            {
                "title": "U.S. Census Bureau, State Tax Collections Historical Database (2025)",
                "url": "https://www2.census.gov/programs-surveys/stc/datasets/historical/STC-Historical-DB.xlsx",
                "page": "https://www.census.gov/programs-surveys/stc/data/datasets.html",
            },
            {
                "title": "Chronology of North Carolina Governors, NCpedia, revised September 2025",
                "url": "https://www.ncpedia.org/biography/governors",
                "publisher": "State Library of North Carolina, Government & Heritage Library",
            },
        ],
    }
    (OUT / "nc-tax-collections.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def build_migration():
    def load(path, dest_key, origin_key, name_key, agi_key="AGI"):
        rows = []
        with Path(path).open(encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            # normalize field names
            fieldmap = {k.lower().lstrip("\ufeff"): k for k in r.fieldnames}
            for row in r:
                rec = {k.lower().lstrip("\ufeff"): v for k, v in row.items()}
                rows.append(rec)
        return rows

    # 2023-2024 inflow to NC (y2=37)
    in_rows = load(PHASE4 / "stateinflow2324.csv", "y2_statefips", "y1_statefips", "y1_state_name", "agi")
    out_rows = None
    out_path = PHASE4 / "stateoutflow2324.csv"
    # may not have been downloaded successfully earlier
    inflow = []
    for rec in in_rows:
        if rec.get("y2_statefips", "").zfill(2) != "37":
            continue
        inflow.append({
            "from_fips": rec.get("y1_statefips"),
            "from_abbr": rec.get("y1_state"),
            "from_name": rec.get("y1_state_name"),
            "returns": parse_count(rec.get("n1")),
            "exemptions": parse_count(rec.get("n2")),
            "agi_thousands_usd": parse_count(rec.get("agi") or rec.get("AGI")),
        })
    # outflow 2223 if 2324 missing; try 2324 else 2223
    outflow = []
    out_file = PHASE4 / "stateoutflow2324.csv"
    year_label = "Filing years 2023-2024"
    if not out_file.exists() or out_file.stat().st_size < 1000:
        out_file = PHASE4 / "stateoutflow2223.csv"
        # if inflow is 2324 and outflow is 2223, keep both labeled separately
        year_out = "Filing years 2022-2023"
    else:
        year_out = year_label
    with out_file.open(encoding="utf-8-sig", newline="") as f:
        for rec in csv.DictReader(f):
            rec = {k.lower().lstrip("\ufeff"): v for k, v in rec.items()}
            if rec.get("y1_statefips", "").zfill(2) != "37":
                continue
            outflow.append({
                "to_fips": rec.get("y2_statefips"),
                "to_abbr": rec.get("y2_state"),
                "to_name": rec.get("y2_state_name"),
                "returns": parse_count(rec.get("n1")),
                "exemptions": parse_count(rec.get("n2")),
                "agi_thousands_usd": parse_count(rec.get("agi") or rec.get("AGI")),
            })
    payload = {
        "as_of": "2026-11-24",
        "inflow_period": "IRS SOI state-to-state migration, inflows to North Carolina, filing years 2023-2024",
        "outflow_period": "IRS SOI state-to-state migration, outflows from North Carolina, " + year_out,
        "inflow": inflow,
        "outflow": outflow,
        "sources": [
            {
                "title": "IRS Statistics of Income, state-to-state migration data",
                "url": "https://www.irs.gov/statistics/soi-tax-stats-migration-data",
                "inflow_file": "https://www.irs.gov/pub/irs-soi/stateinflow2324.csv",
                "outflow_file": "https://www.irs.gov/pub/irs-soi/stateoutflow2324.csv" if year_out.startswith("Filing years 2023") else "https://www.irs.gov/pub/irs-soi/stateoutflow2223.csv",
                "note": "n1 is the number of returns, n2 the number of exemptions, and AGI is reported in thousands of dollars. Totals include U.S. and foreign aggregates as published in the file. These are tax-return-based flows, not a Census migration estimate.",
            }
        ],
    }
    (OUT / "nc-migration-irs.json").write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return payload


def build_acs_and_health():
    def acs_row(path, geo="0400000US37"):
        with Path(path).open(encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.DictReader(f, delimiter="|"):
                if row["GEO_ID"] == geo:
                    return row
        raise SystemExit(f"No {geo} row in {path}")

    birth = acs_row(PHASE4 / "acsdt5y2024-b05002.dat")
    lang = acs_row(PHASE4 / "acsdt5y2024-b16001.dat")
    total = parse_count(birth["B05002_E001"])
    native = parse_count(birth["B05002_E002"])
    foreign = parse_count(birth["B05002_E013"])
    lang_total = parse_count(lang["B16001_E001"])
    english_only = parse_count(lang["B16001_E002"])
    acs = {
        "period": "2024 ACS 5-year estimates (2019-2024 pooled)",
        "as_of": "2026-11-24",
        "place_of_birth": {
            "table": "B05002",
            "total": total,
            "native": native,
            "foreign_born": foreign,
            "foreign_born_moe_90pct": parse_count(birth["B05002_M013"]),
            "foreign_born_share": None if not total else round(foreign / total, 4),
        },
        "language": {
            "table": "B16001",
            "universe": "Population 5 years and over",
            "total": lang_total,
            "speak_only_english": english_only,
            "speak_only_english_moe_90pct": parse_count(lang["B16001_M002"]),
            "language_other_than_english": lang_total - english_only if lang_total is not None and english_only is not None else None,
            "language_other_than_english_share": None if not lang_total else round((lang_total - english_only) / lang_total, 4),
        },
        "sources": [
            {
                "title": "U.S. Census Bureau, 2024 ACS 5-year summary file, tables B05002 and B16001",
                "urls": [
                    "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b05002.dat",
                    "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b16001.dat",
                ],
                "note": "Five-year pooled estimates, not a single calendar-year value. Estimates have margins of error. Do not splice these ACS figures into a continuous line with decennial census nativity or language counts.",
            }
        ],
    }
    (OUT / "nc-acs-benchmarks.json").write_text(json.dumps(acs, indent=2) + "\n")

    health = {
        "as_of": "2026-11-24",
        "resident_abortion_counts_schs": {
            "series": "North Carolina resident induced abortions, SCHS Reported Pregnancies 2023, Table 8",
            "unit": "count",
            "points": [
                {"year": 2018, "value": 23018},
                {"year": 2019, "value": 23495},
                {"year": 2020, "value": 25058},
                {"year": 2021, "value": 27305},
                {"year": 2022, "value": 28855},
                {"year": 2023, "value": 27146},
            ],
            "source": "https://schs.dph.ncdhhs.gov/data/vital/pregnancies/2023/Table8-2018-2023-AbortionsByRaceEthnicity.pdf",
            "note": "Race-specific counts in the source may not sum to the total because of unknown race. These are resident counts, not procedures performed in the state regardless of residence.",
        },
        "resident_abortion_rate_schs": {
            "series": "Abortion rate, North Carolina residents, SCHS Reported Pregnancies 2023, Table 1",
            "unit": "per 1,000 females age 15-44",
            "points": [
                {"year": 2018, "value": 11.3},
                {"year": 2019, "value": 11.4},
                {"year": 2020, "value": 12.3},
                {"year": 2021, "value": 13.1},
                {"year": 2022, "value": 13.7},
                {"year": 2023, "value": 12.7},
            ],
            "source": "https://schs.dph.ncdhhs.gov/data/vital/pregnancies/2023/Table1-2018-2023-PregnancyFertilityAbortionFetalDeathRates.pdf",
            "note": "The source cautions that rates may differ from earlier publications because of revised population estimates.",
        },
        "resident_fertility_rate_schs": {
            "series": "Fertility rate, North Carolina residents, SCHS Reported Pregnancies 2023, Table 1",
            "unit": "per 1,000 females age 15-44",
            "points": [
                {"year": 2018, "value": 58.4},
                {"year": 2019, "value": 57.8},
                {"year": 2020, "value": 57.1},
                {"year": 2021, "value": 57.9},
                {"year": 2022, "value": 57.6},
                {"year": 2023, "value": 56.0},
            ],
            "source": "https://schs.dph.ncdhhs.gov/data/vital/pregnancies/2023/Table1-2018-2023-PregnancyFertilityAbortionFetalDeathRates.pdf",
        },
        "reported_terminations_2024_ncdhhs": {
            "series": "Intentional terminations of pregnancy reported to NCDHHS, January 1-December 31, 2024, G.S. 90-21.93 report",
            "value": 39315,
            "source": "https://www.ncdhhs.gov/ncgs-90-2193-care-women-children-and-families-act-0/download?attachment=",
            "date": "February 26, 2026",
            "note": "This statutory report is a count of reported procedures, not the SCHS resident-abortion series above. Do not plot it as the 2024 point on the 2018-2023 resident series.",
        },
        "todo": [
            "County-level resident deaths, suicides, and homicides from SCHS Vital Statistics Volume 1 are not extracted in this release. Use the official county tables: https://schs.dph.ncdhhs.gov/data/vital/volume1/2023/",
            "A comparable long historical death series was not compiled for this release.",
        ],
        "portals": [
            {"title": "NC SCHS vital statistics", "url": "https://schs.dph.ncdhhs.gov/data/vital.cfm"},
            {"title": "NC SCHS Reported Pregnancies 2023", "url": "https://schs.dph.ncdhhs.gov/data/vital/pregnancies/2023/"},
        ],
    }
    (OUT / "nc-health-sourced.json").write_text(json.dumps(health, indent=2) + "\n")
    return acs, health


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pop = build_population()
    tax = build_taxes()
    mig = build_migration()
    acs, health = build_acs_and_health()
    print("places", len(pop["places"]), "years", pop["years"])
    print("NC 1790/1990/2025", pop["places"]["North Carolina"][0], pop["places"]["North Carolina"][pop["years"].index(1990)], pop["places"]["North Carolina"][-1])
    print("Alamance last 4", pop["places"]["Alamance"][-4:])
    print("tax years", tax["series"][0]["year"], tax["series"][-1]["year"], "n", len(tax["series"]))
    print("inflow rows", len(mig["inflow"]), "outflow", len(mig["outflow"]))
    print("foreign born", acs["place_of_birth"]["foreign_born"], "share", acs["place_of_birth"]["foreign_born_share"])
    print("done")


if __name__ == "__main__":
    main()
