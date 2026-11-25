# North Carolina Civic Atlas

An independent, open-source county atlas for North Carolina. This project is not a government office and is not affiliated with NCGOP or any chartered Young Republican organization.

The site is a port of the public [YoungRepublicansOfPA/Home](https://github.com/YoungRepublicansOfPA/Home) civic-records app. Code and structured-data ideas are used under the MIT license. Placeholder badge and banner images in `assets/` were generated for this edition and do not use the upstream project’s artwork (those images were excluded from the MIT license).

**Phase 4 (current):** Phase 3 plus research pages rebuilt from official North Carolina and federal sources: county population history (Census 1790–2025), state tax collections, ACS and IRS migration benchmarks, SCHS/NCDHHS pregnancy statistics, and constitutional voting sources. County board party control, committee vacancies, municipal outlines, organization funding, church directories, and historical county benefit-spending tables remain unverified or TODO.

Live preview: run `python3 -m http.server 8000` in this directory, then open `http://localhost:8000/`. There is no build step. On GitHub Pages the site is served from `main` at the `/nc-civic-atlas/` subpath; keep links and data fetches relative.

## Branding

Change the site name, disclaimer, and asset paths in `site-config.js`. That is the single place to update placeholder branding.

## Phase 1 sources

- County boundaries: [U.S. Census Bureau Cartographic Boundary File, 1:500,000, 2024](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html), file [`cb_2024_us_county_500k.zip`](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip), filtered to state FIPS 37.
- Population: Census Vintage 2025 county estimates as of July 1, 2025, [CO-EST2025-POP-37](https://www2.census.gov/programs-surveys/popest/tables/2020-2025/counties/totals/co-est2025-pop-37.xlsx) and the [county totals landing page](https://www.census.gov/data/datasets/time-series/demo/popest/2020s-counties-total.html).
- County websites: [County Government Websites | nc.gov](https://www.nc.gov/your-government/county-government-websites), retrieved November 24, 2026. URLs are directory listings, not a verification of current officeholders or budgets.

- N.C. General Assembly member tables: [House](https://www.ncleg.gov/Members/MemberTable/H), [Senate](https://www.ncleg.gov/Members/MemberTable/S), and [representation by county](https://www.ncleg.gov/Members/RepresentationByCounty/H) (2025-2026 session, retrieved November 24, 2026). Successors are included; resigned or deceased members are not treated as seated.
- U.S. House: [house.gov Representatives directory](https://www.house.gov/representatives) (119th Congress, sitting members). County coverage from the [Census 2024 county-within-CD119 cartographic file](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_within_cd119_500k.zip). U.S. Senate: [senate.gov North Carolina](https://www.senate.gov/states/NC/intro.htm).
- Affordability: Census 2024 ACS 5-year detailed tables B19013, B25070, and B08303 ([summary files](https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html)).
- 2026 county commissioner contests: [NCSBE historical results](https://www.ncsbe.gov/results-data/election-results/historical-election-results-data), file `results_pct_20261103.zip`. These totals are not used to assign full-board party control.
- Meetings: official [NCGA legislative calendar](https://www.ncleg.gov/LegislativeCalendar) event pages, checked November 24, 2026.
- State budget links: [OSBM Certified Budget, FY 2026-27](https://www.osbm.nc.gov/budget/certified-budget). No dollar figures are copied into the site.


Rebuild the map and county JSON with `tools/build-county-map.py` (requires `pyshp`). Rebuild placeholder images with `tools/build-placeholder-assets.py`.


## Phase 3 sources (War Map)

- Precinct polygons and 2024 presidential totals: [2024 Precinct-Level Election Results, The New York Times](https://www.nytimes.com/interactive/2025/us/elections/2024-election-map-precinct-results.html), North Carolina file. Redistributed under the [NYT C-UDA](war_map/data/NYT-LICENSE.txt). NYT documents these North Carolina shapes as official boundaries.
- Official comparison file: NCSBE `results_pct_20241105.zip` from [historical election results](https://www.ncsbe.gov/results-data/election-results/historical-election-results-data). A compact US President extract is `war_map/data/state-reported-2024.csv`.
- Districts: Census 2024 cartographic boundary files for [SLDL](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_37_sldl_500k.zip), [SLDU](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_37_sldu_500k.zip), and [CD119](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip).
- Officeholders: `nc-legislators.json` (see Phase 2 sources). Confirm a residence with [Find Your Legislators](https://www.ncleg.gov/FindYourLegislators).
- Polling place lookup (not hosted here): [NCSBE polling place search](https://vt.ncsbe.gov/PPLkup/).

Rebuild War Map data with `tools/build-war-map.py` (requires `pyshp` and `shapely`). Details are in `war_map/README.md` and `war_map/data/README.md`.


## Phase 4 sources (research pages)

- County population 1790–1990: [Census Forstall Part III spreadsheet](https://www2.census.gov/programs-surveys/decennial/tables/1990/population-of-states-and-counties-us-1790-1990/population_partiii.xls). 2000 estimates base, 2010 Census, 2020 estimates base, and July 1, 2025 estimates from Census county totals files; see `research/county-pop-history.json`.
- State tax collections: [Census STC historical database](https://www2.census.gov/programs-surveys/stc/datasets/historical/STC-Historical-DB.xlsx). Governor year ranges: [NCpedia chronology](https://www.ncpedia.org/biography/governors) (State Library of North Carolina, revised September 2025).
- ACS 2024 five-year tables [B05002](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b05002.dat) and [B16001](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b16001.dat).
- IRS SOI [state-to-state migration](https://www.irs.gov/statistics/soi-tax-stats-migration-data), filing years 2023–2024.
- Pregnancy and abortion: [SCHS Reported Pregnancies 2023](https://schs.dph.ncdhhs.gov/data/vital/pregnancies/2023/) tables 1 and 8, and the [G.S. 90-21.93 report](https://www.ncdhhs.gov/ncgs-90-2193-care-women-children-and-families-act-0/download?attachment=) (February 26, 2026). These are distinct series.
- Voting rules: [official N.C. Constitution](https://www.ncleg.gov/EnactedLegislation/Constitution/NCConstitution.html) and NCGA Library historical compilations.

Rebuild compact research tables with `tools/build-phase4.py`.

## Contributing records

For a correction or a new record, include the county or jurisdiction, a primary-source link, the document date, and the date you checked it. Do not invent figures, names, or links. Leave gaps marked as TODO.

## License

The MIT license covers the code and most structured data in this repository. Include the original copyright notice. Placeholder images in `assets/` were generated for this project.

The 2024 precinct polygons and vote totals in `war_map/data/` are redistributed under the New York Times Computational Use of Data Agreement (non-commercial, with attribution). See `war_map/data/NYT-LICENSE.txt`. Do not use that dataset commercially.
