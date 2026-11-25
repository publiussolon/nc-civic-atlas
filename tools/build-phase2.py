#!/usr/bin/env python3
"""Build Phase 2 data from official NCGA, Census ACS, house.gov, senate.gov, NCSBE, and OSBM sources."""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from html import unescape
from pathlib import Path

import shapefile

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("/workspace/nc-home-data/phase2")
CHECKED = "2026-11-24"
ACS_YEAR = 2024

PARTY = {"D": "Democratic", "R": "Republican", "DEM": "Democratic", "REP": "Republican", "LIB": "Libertarian", "UNA": "Unaffiliated"}


def load_map():
    return json.loads((ROOT / "map-data.json").read_text())


def fips_to_county(map_data):
    out = {}
    for name, rec in map_data["counties"].items():
        out[rec["fips"]] = name
        out[rec["fips"][2:]] = name
    return out


def clean(html_fragment: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html_fragment))).replace("\xa0", " ").strip()


def parse_member_table(path: Path, chamber: str):
    t = path.read_text(errors="replace")
    table = re.search(r"<table[\s\S]*?</table>", t, re.I).group(0)
    rows = re.findall(r"<tr[\s\S]*?</tr>", table, re.I)[1:]
    current, former = [], []
    for row in rows:
        cells = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row, re.I)
        texts = [clean(c) for c in cells]
        member_cell = cells[4] if len(cells) > 4 else ""
        county_cell = cells[5] if len(cells) > 5 else ""
        bio = re.search(r'href="([^"]*Biography[^"]*)"', member_cell)
        counties = [clean(a) for a in re.findall(r'/Members/CountyRepresentation/([^"]+)', county_cell)]
        # fallback if links missed (shouldn't)
        if not counties and texts[5:]:
            counties = [p.strip() for p in re.split(r",", texts[5]) if p.strip()]
        rec = {
            "district": int(texts[1]),
            "name": re.sub(r"\s*\((Resigned|Appointed|Deceased)[^)]*\)\s*", "", texts[4]).strip(),
            "party": PARTY.get(texts[0], texts[0]),
            "party_code": texts[0],
            "profile_url": "https://www.ncleg.gov" + bio.group(1) if bio else None,
            "counties": counties,
            "roster_label": "Representative" if chamber == "H" else "Senator",
            "raw_listing": texts[4],
        }
        status = re.search(r"\((Resigned|Appointed|Deceased) ([^)]+)\)", texts[4])
        if status:
            rec["status_note"] = f"{status.group(1)} {status.group(2)}"
            if status.group(1) in {"Resigned", "Deceased"}:
                former.append(rec)
                continue
            rec["roster_label"] = rec["roster_label"] + f" (appointed {status.group(2)})"
        current.append(rec)
    return current, former


def parse_us_house(path: Path):
    t = path.read_text(errors="replace")
    m = re.search(r"North Carolina\s*</caption>[\s\S]*?</table>", t, re.I)
    if not m:
        raise SystemExit("Could not find North Carolina table on house.gov")
    rows = re.findall(r"<tr[\s\S]*?</tr>", m.group(0), re.I)[1:]
    members = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row, re.I)
        texts = [clean(c) for c in cells]
        href = re.search(r'href="(https://[^"]+)"', row)
        dist = int(re.match(r"(\d+)", texts[0]).group(1))
        # house.gov lists "Last, First"
        last, first = [p.strip() for p in texts[1].split(",", 1)]
        members.append({
            "district": dist,
            "name": f"{first} {last}",
            "party": PARTY.get(texts[2], texts[2]),
            "profile_url": href.group(1) if href else "https://www.house.gov/representatives",
            "roster_label": "U.S. Representative",
        })
    if len(members) != 14:
        raise SystemExit(f"Expected 14 U.S. House members, got {len(members)}")
    return members


def congress_counties(fips_map):
    reader = shapefile.Reader(str(DATA / "cd119_county/cb_2024_us_county_within_cd119_500k.shp"))
    fields = [f[0] for f in reader.fields[1:]]
    by_cd = defaultdict(list)
    by_county = defaultdict(list)
    for rec in reader.iterRecords():
        d = dict(zip(fields, rec))
        if str(d["STATEFP"]) != "37":
            continue
        fips = str(d["STATEFP"]) + str(d["COUNTYFP"]).zfill(3)
        county = fips_map[fips]
        cd = int(d["CD119FP"])
        part = d["PARTFLG"] == "Y"
        item = {"county": county, "district": cd, "county_split": part, "fips": fips}
        by_cd[cd].append(item)
        by_county[county].append(item)
    return by_cd, by_county


def build_legislators(map_data, fips_map):
    house, house_former = parse_member_table(DATA / "house_table.html", "H")
    senate, senate_former = parse_member_table(DATA / "senate_table.html", "S")
    us_house = parse_us_house(DATA / "house_nc.html")
    by_cd, cd_by_county = congress_counties(fips_map)

    if len(house) != 120:
        raise SystemExit(f"Expected 120 seated House members, got {len(house)}")
    if len(senate) != 50:
        raise SystemExit(f"Expected 50 seated Senate members, got {len(senate)}")
    if {m["district"] for m in house} != set(range(1, 121)):
        raise SystemExit("House districts are not 1-120 unique")
    if {m["district"] for m in senate} != set(range(1, 51)):
        raise SystemExit("Senate districts are not 1-50 unique")

    # County lists from official member tables
    house_by_county = defaultdict(list)
    for m in house:
        for c in m["counties"]:
            house_by_county[c].append({
                "district": m["district"],
                "name": m["name"],
                "party": m["party"],
                "profile_url": m["profile_url"],
                "counties": m["counties"],
                "roster_label": m["roster_label"],
            })
    senate_by_county = defaultdict(list)
    for m in senate:
        for c in m["counties"]:
            senate_by_county[c].append({
                "district": m["district"],
                "name": m["name"],
                "party": m["party"],
                "profile_url": m["profile_url"],
                "counties": m["counties"],
                "roster_label": m["roster_label"],
            })

    missing_h = sorted(set(map_data["counties"]) - set(house_by_county))
    missing_s = sorted(set(map_data["counties"]) - set(senate_by_county))
    extra_h = sorted(set(house_by_county) - set(map_data["counties"]))
    extra_s = sorted(set(senate_by_county) - set(map_data["counties"]))
    if missing_h or missing_s or extra_h or extra_s:
        raise SystemExit(f"County name mismatch house missing={missing_h} extra={extra_h} senate missing={missing_s} extra={extra_s}")

    us_by_county = defaultdict(list)
    for mem in us_house:
        geos = sorted(by_cd[mem["district"]], key=lambda x: x["county"])
        counties = [g["county"] for g in geos]
        splits = {g["county"] for g in geos if g["county_split"]}
        for g in geos:
            us_by_county[g["county"]].append({
                "district": mem["district"],
                "name": mem["name"],
                "party": mem["party"],
                "profile_url": mem["profile_url"],
                "counties": counties,
                "county_is_split": g["county"] in splits,
                "roster_label": mem["roster_label"],
                "geography_source": "Census Cartographic Boundary File 2024, counties within 119th Congressional Districts (cb_2024_us_county_within_cd119_500k)",
            })

    counties = []
    for name in sorted(map_data["counties"]):
        counties.append({
            "county": name,
            "house": sorted(house_by_county[name], key=lambda x: x["district"]),
            "senate": sorted(senate_by_county[name], key=lambda x: x["district"]),
            "congress": sorted(us_by_county[name], key=lambda x: x["district"]),
        })

    return {
        "as_of": CHECKED,
        "scope": "Seated 2025-2026 North Carolina General Assembly roster as shown on the official NCGA member tables, plus sitting U.S. House members of the 119th Congress as listed on house.gov. November 2026 election winners are not assumed seated before the next term in January 2027.",
        "sources": {
            "house_roster": "https://www.ncleg.gov/Members/MemberTable/H",
            "senate_roster": "https://www.ncleg.gov/Members/MemberTable/S",
            "house_by_county": "https://www.ncleg.gov/Members/RepresentationByCounty/H",
            "senate_by_county": "https://www.ncleg.gov/Members/RepresentationByCounty/S",
            "address_lookup": "https://www.ncleg.gov/FindYourLegislators",
            "us_house_roster": "https://www.house.gov/representatives",
            "us_senate_roster": "https://www.senate.gov/states/NC/intro.htm",
            "us_house_address_lookup": "https://www.house.gov/representatives/find-your-representative",
            "congressional_county_geography": "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_within_cd119_500k.zip",
        },
        "us_senate": [
            {"name": "Thom Tillis", "party": "Republican", "profile_url": "https://www.senate.gov/states/NC/intro.htm", "roster_label": "U.S. Senator", "source": "https://www.senate.gov/states/NC/intro.htm"},
            {"name": "Ted Budd", "party": "Republican", "profile_url": "https://www.senate.gov/states/NC/intro.htm", "roster_label": "U.S. Senator", "source": "https://www.senate.gov/states/NC/intro.htm"},
        ],
        "notes": [
            "A county can contain parts of several House, Senate, or congressional districts. Use a street address and the official lookup tools to identify a resident’s members.",
            "The NCGA tables list 2025-2026 session members. Where a member resigned or died, only the successor who is still listed as appointed or seated is included.",
            "U.S. House county coverage comes from the Census 2024 county-within-119th-Congressional-District cartographic file, including counties that are only partly in a district.",
            "Sitting U.S. senators for North Carolina, as listed on senate.gov on the as-of date, are Thom Tillis and Ted Budd.",
        ],
        "former_members_listed_on_roster": {
            "house": [{"district": m["district"], "name": m["name"], "status_note": m["status_note"]} for m in house_former],
            "senate": [{"district": m["district"], "name": m["name"], "status_note": m["status_note"]} for m in senate_former],
        },
        "counts": {
            "counties": len(counties),
            "house_districts": 120,
            "senate_districts": 50,
            "congressional_districts": 14,
        },
        "counties": counties,
    }


def _to_int(val):
    if val in (None, "", "."):
        return None
    n = int(float(val))
    # Census ACS suppression / not-available sentinels are large negative integers.
    if n <= -100000:
        return None
    return n


def build_affordability(fips_map):
    # Stream official table-based summary files; keep county summary-level rows for NC only.
    income = {}
    with (DATA / "acsdt5y2024-b19013.dat").open(encoding="utf-8", errors="replace", newline="") as f:
        r = csv.DictReader(f, delimiter="|")
        for row in r:
            geo = row["GEO_ID"]
            if geo.startswith("0500000US37"):
                income[geo[-5:]] = {
                    "usd_2024": _to_int(row["B19013_E001"]),
                    "moe_usd_2024_90pct": _to_int(row["B19013_M001"]),
                    "acs_variable": "B19013_001",
                }
    rent = {}
    with (DATA / "acsdt5y2024-b25070.dat").open(encoding="utf-8", errors="replace", newline="") as f:
        r = csv.DictReader(f, delimiter="|")
        for row in r:
            geo = row["GEO_ID"]
            if not geo.startswith("0500000US37"):
                continue
            total = _to_int(row["B25070_E001"])
            not_computed = _to_int(row["B25070_E011"])
            parts = [_to_int(row[f"B25070_E{i:03d}"]) for i in (7, 8, 9, 10)]
            if None in parts or total is None or not_computed is None:
                rent[geo[-5:]] = None
                continue
            denom = total - not_computed
            num = sum(parts)
            rent[geo[-5:]] = {
                "households": num,
                "denominator_households": denom,
                "share_percent": round(100.0 * num / denom, 1) if denom else None,
                "total_renter_households": total,
                "not_computed_households": not_computed,
                "numerator_variables": ["B25070_007", "B25070_008", "B25070_009", "B25070_010"],
                "denominator_definition": "B25070_001 minus B25070_011 (not computed)",
                "component_moe_90pct": {
                    "B25070_001": _to_int(row["B25070_M001"]),
                    "B25070_007": _to_int(row["B25070_M007"]),
                    "B25070_008": _to_int(row["B25070_M008"]),
                    "B25070_009": _to_int(row["B25070_M009"]),
                    "B25070_010": _to_int(row["B25070_M010"]),
                    "B25070_011": _to_int(row["B25070_M011"]),
                },
                "derived_share_moe": None,
            }
    commute = {}
    with (DATA / "acsdt5y2024-b08303.dat").open(encoding="utf-8", errors="replace", newline="") as f:
        r = csv.DictReader(f, delimiter="|")
        for row in r:
            geo = row["GEO_ID"]
            if not geo.startswith("0500000US37"):
                continue
            denom = _to_int(row["B08303_E001"])
            parts = [_to_int(row[f"B08303_E{i:03d}"]) for i in range(8, 14)]
            if denom is None or None in parts:
                commute[geo[-5:]] = None
                continue
            num = sum(parts)
            commute[geo[-5:]] = {
                "persons": num,
                "denominator_persons": denom,
                "share_percent": round(100.0 * num / denom, 1) if denom else None,
                "numerator_variables": [f"B08303_{i:03d}" for i in range(8, 14)],
                "denominator_variable": "B08303_001",
                "component_moe_90pct": {f"B08303_{i:03d}": _to_int(row[f"B08303_M{i:03d}"]) for i in [1] + list(range(8, 14))},
                "derived_share_moe": None,
            }

    counties = []
    for fips, name in sorted(((k, v) for k, v in fips_map.items() if len(k) == 5), key=lambda x: x[1]):
        if fips not in income or income[fips] is None:
            raise SystemExit(f"Missing ACS income for {name} {fips}")
        if rent.get(fips) is None or commute.get(fips) is None:
            raise SystemExit(f"Missing ACS rent/commute for {name} {fips}")
        counties.append({
            "county": name,
            "county_fips": fips,
            "median_household_income": income[fips],
            "renter_households_gross_rent_30pct_plus": rent[fips],
            "commuters_30_minutes_plus": commute[fips],
        })
    if len(counties) != 100:
        raise SystemExit(f"Expected 100 ACS counties, got {len(counties)}")
    return {
        "title": "North Carolina county income, rent burden, and commute estimates, 2024 ACS 5-year",
        "period": "20120-2024"[:0] + "2020-2024",
        "release_year": ACS_YEAR,
        "checked_at": CHECKED,
        "source": {
            "agency": "U.S. Census Bureau",
            "dataset": "2024 American Community Survey 5-year Detailed Tables",
            "summary_file_url": "https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html",
            "table_urls": [
                "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b19013.dat",
                "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25070.dat",
                "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b08303.dat",
            ],
            "documentation_url": "https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html",
            "variable_definitions": [
                "https://api.census.gov/data/2024/acs/acs5/groups/B19013.html",
                "https://api.census.gov/data/2024/acs/acs5/groups/B25070.html",
                "https://api.census.gov/data/2024/acs/acs5/groups/B08303.html",
            ],
        },
        "definitions": {
            "income": "Median household income in past 12 months, 2024 inflation-adjusted dollars. Margin of error is the published ACS 90% MOE.",
            "rent_burden": "Share of renter-occupied units paying gross rent of at least 30% of household income, excluding units where ratio was not computed. Gross rent includes contract rent plus utilities/fuels.",
            "commute": "Share of workers age 16+ who did not work from home and traveled 30 minutes or longer to work. This is commute time, not financial cost of commuting.",
            "uncertainty": "Published component 90% margins of error are included. Derived-share MOEs were not calculated; differences between counties or years should not be treated as statistically meaningful without a proper MOE calculation.",
        },
        "counties": counties,
    }


def build_commissioner_results(map_data):
    """Aggregate official NCSBE precinct results for county board of commissioners contests.

    This is not a complete sitting-board majority. Many boards have seats that were not
    on the November 3, 2026 ballot.
    """
    path = DATA / "results_20261103/results_pct_20261103.txt"
    totals = defaultdict(lambda: defaultdict(lambda: {"party": None, "votes": 0, "vote_for": None}))
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            contest = row["Contest Name"]
            if not re.search(r"COUNTY (BOARD|BD) OF COMMISSIONERS", contest, re.I):
                continue
            if re.match(r"^(CITY|TOWN|VILLAGE|MUNICIPAL)\b", contest, re.I):
                continue
            county = row["County"].title() if row["County"].isupper() else row["County"]
            # NCSBE uses ALL CAPS county names
            county = row["County"].strip().title()
            if county == "Mcdowell":
                county = "McDowell"
            key = (county, contest)
            choice = row["Choice"].strip()
            rec = totals[key][choice]
            rec["party"] = PARTY.get(row["Choice Party"].strip(), row["Choice Party"].strip() or None)
            rec["votes"] += int(row["Total Votes"] or 0)
            rec["vote_for"] = int(row["Vote For"] or 0)

    known = set(map_data["counties"])
    by_county = defaultdict(list)
    for (county, contest), choices in totals.items():
        if county not in known:
            # skip if we somehow caught a city
            continue
        vote_for = next(iter(choices.values()))["vote_for"]
        ranked = sorted(choices.items(), key=lambda kv: (-kv[1]["votes"], kv[0]))
        winners = [
            {"name": name, "party": rec["party"], "total_votes": rec["votes"]}
            for name, rec in ranked[:vote_for]
        ]
        by_county[county].append({
            "contest": contest,
            "vote_for": vote_for,
            "choices": [
                {"name": name, "party": rec["party"], "total_votes": rec["votes"]}
                for name, rec in ranked
            ],
            "apparent_winners_by_total_votes": winners,
        })

    return {
        "election": "November 3, 2026 General Election",
        "election_date": "2026-11-03",
        "checked_at": CHECKED,
        "source": "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2026_11_03/results_pct_20261103.zip",
        "source_page": "https://www.ncsbe.gov/results-data/election-results/historical-election-results-data",
        "layout": "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/layout_results_pct.txt",
        "certification_note": "The State Board of Elections certified the November 3, 2026 general election on November 24, 2026, except for contests still under recount, including N.C. House District 62. See https://www.ncsbe.gov/news/press-releases/2026/11/24/state-board-unanimously-certifies-midterm-elections",
        "limitation": "These are official vote totals for county board of commissioners contests on the November 3, 2026 ballot, aggregated from the NCSBE precinct results file (all precinct rows, including administrative precincts). They are not a complete roster of the sitting board and are not used to assign county party control, because most boards have members whose seats were not up in this election.",
        "counties_with_commissioner_contests": len(by_county),
        "counties": {
            name: {"contests": sorted(by_county.get(name, []), key=lambda c: c["contest"])}
            for name in sorted(map_data["counties"])
        },
    }


def build_docket_and_budget():
    meetings = [
        {
            "scope": "state",
            "county": None,
            "body": "North Carolina House of Representatives",
            "date": "2026-11-30",
            "time": "12:00 p.m.",
            "topic": "House: Session Convenes",
            "item_status": "Listed on the official NCGA legislative calendar",
            "vote_status": "A scheduled session is not a verified floor vote on any bill",
            "source_url": "https://www.ncleg.gov/LegislativeCalendarEvent/134621",
        },
        {
            "scope": "state",
            "county": None,
            "body": "Blue Ribbon Commission on Public Education",
            "date": "2026-12-14",
            "time": "10:00 a.m.",
            "topic": "Commission meeting at the Friday Institute for Educational Innovation",
            "item_status": "Listed on the official NCGA legislative calendar",
            "vote_status": "A listed meeting is not a verified vote",
            "source_url": "https://www.ncleg.gov/LegislativeCalendarEvent/134383",
        },
        {
            "scope": "state",
            "county": None,
            "body": "Blue Ribbon Commission on Public Education",
            "date": "2027-01-25",
            "time": "10:00 a.m.",
            "topic": "Commission meeting at the Friday Institute for Educational Innovation",
            "item_status": "Listed on the official NCGA legislative calendar",
            "vote_status": "A listed meeting is not a verified vote",
            "source_url": "https://www.ncleg.gov/LegislativeCalendarEvent/134384",
        },
        {
            "scope": "state",
            "county": None,
            "body": "Blue Ribbon Commission on Public Education",
            "date": "2027-02-22",
            "time": "10:00 a.m.",
            "topic": "Commission meeting at the Friday Institute for Educational Innovation",
            "item_status": "Listed on the official NCGA legislative calendar",
            "vote_status": "A listed meeting is not a verified vote",
            "source_url": "https://www.ncleg.gov/LegislativeCalendarEvent/134385",
        },
    ]
    docket_expanded = {
        "checked_at": CHECKED,
        "session": "2025-2026 Session (current roster); official calendar also lists later dates",
        "status_summary": "The official NCGA legislative calendar, checked November 24, 2026, lists a House session convening on November 30, 2026, and Blue Ribbon Commission on Public Education meetings on December 14, 2026, January 25, 2027, and February 22, 2027. No tracked bill or scheduled floor vote was verified in this release. Calendars can change; check official schedules directly.",
        "status_sources": {
            "legislative_calendar": "https://www.ncleg.gov/LegislativeCalendar",
            "house_current_calendar": "https://calendars.ncleg.gov/CurrentCalendarDoc/H",
            "senate_current_calendar": "https://calendars.ncleg.gov/CurrentCalendarDoc/S",
            "legislation": "https://www.ncleg.gov/Legislation",
        },
        "upcoming_meetings": meetings,
        "tracked_bills": [],
        "county_agenda_sources": [],
        "method_note": "Meetings are copied from official NCGA calendar event pages. Individual bills are not listed until a specific official calendar or bill page is checked. County commissioner agendas are not yet ingested.",
        "machine_readable_sources": [],
    }
    docket_records = {
        "checked_at": CHECKED,
        "session_note": "Phase 2 includes official NCGA calendar meetings only. No individual bill actions were checked.",
        "records": [],
        "county_agenda_checks": [],
    }
    budget = {
        "checked_at": CHECKED,
        "todo": None,
        "note": "No dollar figures are published here. Official state budget documents are linked; county budgets remain on each county website and have not been ingested.",
        "records": [
            {
                "scope": "state",
                "title": "Certified Budget, Fiscal Year 2026-27",
                "publisher": "North Carolina Office of State Budget and Management",
                "url": "https://www.osbm.nc.gov/budget/certified-budget",
                "description": "Official certified agency budget documents for FY 2026-27, as published by OSBM.",
                "checked_at": CHECKED,
            },
            {
                "scope": "state",
                "title": "OSBM Budget office",
                "publisher": "North Carolina Office of State Budget and Management",
                "url": "https://www.osbm.nc.gov/budget",
                "description": "State budget office landing page, including certified budgets, the budget manual, and the Governor's recommendations.",
                "checked_at": CHECKED,
            },
        ],
    }
    return docket_expanded, docket_records, budget


def main():
    map_data = load_map()
    fips_map = fips_to_county(map_data)

    legislators = build_legislators(map_data, fips_map)
    (ROOT / "nc-legislators.json").write_text(json.dumps(legislators, indent=2) + "\n")

    afford = build_affordability(fips_map)
    (ROOT / "county-work-affordability.json").write_text(json.dumps(afford, indent=2) + "\n")

    comm = build_commissioner_results(map_data)
    (ROOT / "ncsbe-commissioner-contests-2026.json").write_text(json.dumps(comm, indent=2) + "\n")

    # Party control stays unverified; record why.
    map_data["party_control_definition"] = (
        "Majority party of the county board of commissioners, not how the county voted in an election. "
        "Not assigned in this release: official November 3, 2026 NCSBE results cover only the commissioner seats on that ballot, not every sitting member. See ncsbe-commissioner-contests-2026.json."
    )
    map_data["party_control_status"] = "unverified_all_counties"
    map_data["party_control_checked_at"] = CHECKED
    map_data["party_control_source_note"] = comm["limitation"]
    (ROOT / "map-data.json").write_text(json.dumps(map_data, indent=2) + "\n")

    expanded, records, budget = build_docket_and_budget()
    (ROOT / "docket-expanded.json").write_text(json.dumps(expanded, indent=2) + "\n")
    (ROOT / "docket-records.json").write_text(json.dumps(records, indent=2) + "\n")
    (ROOT / "budget-records.json").write_text(json.dumps(budget, indent=2) + "\n")

    print("House members", legislators["counts"]["house_districts"], "Senate", legislators["counts"]["senate_districts"])
    print("Alamance house", [m["name"] for m in legislators["counties"][0]["house"]])
    print("Wake congress", [(m["district"], m["name"]) for c in legislators["counties"] if c["county"]=="Wake" for m in c["congress"]])
    alam = next(c for c in afford["counties"] if c["county"]=="Alamance")
    print("Alamance income", alam["median_household_income"])
    print("Commissioner counties with contests", comm["counties_with_commissioner_contests"])
    print("Meetings", len(expanded["upcoming_meetings"]))


if __name__ == "__main__":
    main()
