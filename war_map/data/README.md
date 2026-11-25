# War Map precinct data

## Sources

Presidential precinct polygons and vote totals come from the New York Times [2024 Precinct-Level Election Results](https://www.nytimes.com/interactive/2025/us/elections/2024-election-map-precinct-results.html) North Carolina file. NYT documents the North Carolina shapes as official boundaries. The dataset is redistributed here under the [NYT Computational Use of Data Agreement (non-commercial, with attribution)](NYT-LICENSE.txt).

“2024 Precinct-Level Election Results.” *New York Times*, https://www.nytimes.com/interactive/2025/us/elections/2024-election-map-precinct-results.html. Accessed 2026-11-24.

Official November 5, 2024 precinct-level returns for US President were downloaded from the [North Carolina State Board of Elections historical results](https://www.ncsbe.gov/results-data/election-results/historical-election-results-data) file `results_pct_20241105.zip` (also published at https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/results_pct_20241105.zip). A compact extract of that contest is in [state-reported-2024.csv](state-reported-2024.csv).

County outlines on the map are dissolved from the [Census 2024 cartographic county file](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip).

## Matching and coverage

- The NYT file contains **2655** precinct polygons in all **100** counties. Every NYT precinct identifier matched an official NCSBE precinct code (3 Union County identifiers differed only by leading zeros).
- The official results file reports **2658** rows with Real Precinct = Y and **250** administrative reporting units (Real Precinct = N), such as early-voting sites and absentee/provisional tallies.
- Official Real Precinct = Y rows generally do **not** include early, absentee, or provisional ballots when those ballots are reported in the administrative units. Mapping only the Y rows would omit about 1,775,402 votes. The map therefore uses the NYT precinct vote totals, which nearly match the official statewide US President total.
- Official statewide US President totals: Trump 2,898,423, Harris 2,715,375, other 85,343, total 5,699,141.
- Mapped (NYT) totals: Trump 2,896,574, Harris 2,712,787, other 86,471, total 5,695,832.
- Difference (official minus mapped): 3,309 votes. Three official real precincts are absent from the NYT polygons: Henderson CV (457 votes), Wake 07-07A (378 votes), Wake 01-07A (106 votes). Those three account for 941 of the gap. The remainder is not assigned to a mapped polygon.

## Municipal outlines

TODO: a compact official municipal-boundary layer is not included in this release. Address search uses Esri’s geocoder biased to North Carolina; county and precinct names are searched locally.

## File format

Each `data/{county-slug}.json` file stores simplified SVG-style paths projected as `x = 760(lon + 85)`, `y = 1000(37 − lat)`, plus Trump, Harris, other, and total votes. Identifiers are NYT GEOIDs; display names are the official NCSBE precinct codes.
