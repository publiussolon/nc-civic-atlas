# Repository instructions

This repository is the North Carolina Civic Atlas static site (a port of the public YoungRepublicansOfPA/Home GitHub Pages site).

## Branding

Edit `site-config.js` to change the site name, disclaimer, and badge/banner paths. Do not reintroduce the upstream Pennsylvania badge or banner images.

## Data integrity

- County officeholders, party control, budget figures, and agenda items require a source URL and checked date before publication.
- Distinguish official directory links from verified facts. Keep missing values visibly unverified or marked TODO.
- Never invent figures, names, or links. Never display Pennsylvania records as North Carolina records.
- If New York Times precinct data is added later, keep the NYT C-UDA non-commercial terms and attribution.

## Deploy

Do not push until the owner has connected GitHub and asked for a specific remote. Preview locally with `python3 -m http.server`.
