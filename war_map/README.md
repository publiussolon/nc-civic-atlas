# North Carolina War Map

An interactive map of North Carolina 2024 presidential results by precinct, county population, and current legislative and congressional districts. Open `index.html` from the repository root via a local static server, or the GitHub Pages `/nc-civic-atlas/war_map/` path. All asset and data fetches are relative.

## What is included

- 2,655 precinct polygons and 2024 presidential vote totals, from the New York Times 2024 precinct dataset (official North Carolina boundaries). Redistributed under the [NYT C-UDA](data/NYT-LICENSE.txt).
- Official NCSBE November 5, 2024 US President precinct returns for comparison ([data/state-reported-2024.csv](data/state-reported-2024.csv)).
- County outlines from the Census 2024 cartographic county file.
- N.C. House (120), N.C. Senate (50), and U.S. House (14) districts from Census 2024 cartographic boundary files, with seated 2025–2026 officeholders from `../nc-legislators.json`.
- Address search through Esri’s public geocoder, biased to North Carolina (`RegionAbbr = NC` and an NC search extent).
- County population from the atlas’s Vintage 2025 estimates.

## TODO

- County party committee seat vacancies are not compiled. See [committee/README.md](committee/README.md).
- Municipal outlines are not included.
- County board of commissioners party control is not assigned. See `../map-data.json`.

## Rebuild

From the repository root, with `pyshp` and `shapely` installed:

```
python3 tools/build-war-map.py
```

The script reads official and NYT source files from `/workspace/nc-home-data/phase3` on the build machine. It does not download new data unless those files are already present. Rebuild inputs are not stored in the git repository.
