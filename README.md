# North Carolina Civic Atlas

An independent, open-source county atlas for North Carolina. This project is not a government office and is not affiliated with NCGOP or any chartered Young Republican organization.

The site is a port of the public [YoungRepublicansOfPA/Home](https://github.com/YoungRepublicansOfPA/Home) civic-records app. Code and structured-data ideas are used under the MIT license. Placeholder badge and banner images in `assets/` were generated for this edition and do not use the upstream project’s artwork (those images were excluded from the MIT license).

**Phase 2 (current):** Phase 1 plus the seated N.C. General Assembly and U.S. House rosters, 2024 ACS affordability estimates, official NCGA calendar meetings, and official state budget document links. County board party control is not assigned.

Later phases: War Map (NCSBE precincts and districts); research pages.

Live preview: run `python3 -m http.server 8000` in this directory, then open `http://localhost:8000/`. There is no build step. GitHub Pages can publish the repository root from `main` once a remote is connected.

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

## Contributing records

For a correction or a new record, include the county or jurisdiction, a primary-source link, the document date, and the date you checked it. Do not invent figures, names, or links. Leave gaps marked as TODO.

## License

The MIT license covers the code and structured data in this repository. Include the original copyright notice. Placeholder images in `assets/` were generated for this project.
