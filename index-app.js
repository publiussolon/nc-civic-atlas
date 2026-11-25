/* Homepage atlas: county map, profiles, and sourced directory links. */
(function () {
  const counties = window.COUNTY_INDEX.names;
  const countySites = window.COUNTY_INDEX.sites;
  const site = window.SITE;

  const links = {
    state_legislators: [
      'Find N.C. House and Senate members',
      'https://www.ncleg.gov/FindYourLegislators',
      'Search by address; legislative districts can cross county lines. A county roster of members is not in this Phase 1 release.'
    ],
    us_house: [
      'Find your U.S. House member',
      'https://www.house.gov/representatives/find-your-representative',
      'Find the current member by address or ZIP code.'
    ],
    us_senate: [
      'North Carolina U.S. senators',
      'https://www.senate.gov/states/NC/intro.htm',
      'Current statewide senators and official contact information.'
    ],
    elections: [
      'County boards of elections',
      'https://www.ncsbe.gov/about-elections/county-boards-elections',
      'Official North Carolina State Board of Elections directory of county boards.'
    ],
    county: [
      'County government website directory',
      'https://www.nc.gov/your-government/county-government-websites',
      'Official NC.gov directory of county government websites.'
    ],
    budget: [
      'State budget office',
      'https://www.osbm.nc.gov/budget',
      'North Carolina Office of State Budget and Management. County budgets are published by each county; a compiled county budget table is not in this Phase 1 release.'
    ],
    bills: [
      'N.C. General Assembly legislation',
      'https://www.ncleg.gov/Legislation',
      'Search bills, actions, and legislative text on the official General Assembly site.'
    ],
    calendar: [
      'N.C. General Assembly',
      'https://www.ncleg.gov/',
      'Check the official General Assembly site for session information and calendars.'
    ]
  };

  let current = 'Alamance';
  let tab = 'overview';
  const list = document.getElementById('county-list');
  const search = document.getElementById('county-search');
  const detail = document.getElementById('county-detail');

  function linkCard(key) {
    let [title, url, desc] = links[key];
    if (key === 'county' && countySites[current]) {
      title = current + ' County government';
      url = countySites[current];
      desc = 'Official county website as listed on the NC.gov directory. Look there for budgets, commissioners, agendas, and minutes.';
    }
    const div = document.createElement('div');
    div.className = 'source-card';
    const strong = document.createElement('strong');
    strong.textContent = title;
    const p = document.createElement('p');
    p.textContent = desc;
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = 'Open source';
    div.append(strong, p, a);
    return div;
  }

  function renderList() {
    const q = search.value.trim().toLowerCase();
    list.replaceChildren();
    const matches = counties.filter((c) => c.toLowerCase().includes(q));
    if (!matches.length) {
      const p = document.createElement('p');
      p.className = 'empty';
      p.textContent = 'No matching county';
      list.append(p);
      return;
    }
    for (const c of matches) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = c + ' County';
      b.setAttribute('aria-current', String(c === current));
      b.addEventListener('click', () => {
        current = c;
        history.replaceState(null, '', '#county-' + c.toLowerCase().replaceAll(' ', '-'));
        renderList();
        renderDetail();
        paintMap();
        document.getElementById('county-title').focus();
      });
      list.append(b);
    }
  }

  function renderDetail() {
    const drilldown = document.getElementById('county-drilldown');
    document.getElementById('county-history').href = 'demographics.html?county=' + encodeURIComponent(current);
    drilldown.href = 'history.html?county=' + encodeURIComponent(current) + '#county-spending';
    drilldown.textContent = 'Explore ' + current + ' County records →';
    document.getElementById('county-title').textContent = current + ' County';
    const info = mapData?.counties?.[current] || {};
    document.getElementById('county-subtitle').textContent =
      'Population: ' +
      (Number.isFinite(info.population)
        ? info.population.toLocaleString() + ' (2025 Census estimate)'
        : 'pending') +
      ' · governing majority: ' +
      (info.party_control || 'unverified');
    detail.replaceChildren();
    const h = document.createElement('h4');
    const p = document.createElement('p');
    const grid = document.createElement('div');
    grid.className = 'source-grid';
    let selected = [];
    if (tab === 'overview') {
      h.textContent = 'Start with the primary sources';
      p.textContent =
        'Use these official directories to locate ' +
        current +
        ' County records. Statewide directory links may require you to select the county on the destination site.';
      selected = ['elections', 'county', 'budget'];
    }
    if (tab === 'offices') {
      h.textContent = 'Elected and appointed offices';
      p.textContent =
        'A North Carolina General Assembly roster mapped to counties will be added in Phase 2. Use the official address finder for your own members. County officeholder rosters have not been verified in this release.';
      selected = ['state_legislators', 'us_house', 'us_senate', 'county', 'elections'];
    }
    if (tab === 'living') {
      h.textContent = 'Income, rent and travel';
      p.textContent =
        'Comparable American Community Survey estimates for all 100 North Carolina counties will be added in Phase 2. No income, rent, or commute figures are shown until those Census tables are loaded.';
      selected = [];
    }
    if (tab === 'money') {
      h.textContent = 'Budgets and spending';
      p.textContent =
        'Checked county budget figures are not in this Phase 1 release. Start with the county website and the state budget office; budgeted amounts and actual spending are different measures.';
      selected = ['budget', 'county'];
    }
    if (tab === 'docket') {
      h.textContent = 'Meetings and measures';
      p.textContent =
        'County commissioner agendas and minutes are published by counties. Checked items and a tracked General Assembly docket will be added in a later phase.';
      selected = ['county', 'bills', 'calendar'];
    }
    detail.append(h, p, grid);
    selected.forEach((k) => grid.append(linkCard(k)));
    const note = document.createElement('div');
    note.className = 'note';
    note.innerHTML =
      '<strong>Verification status:</strong> official county website listed from the NC.gov directory; additional county facts (officeholders, budgets, agendas) are not yet checked.';
    detail.append(note);

    if (tab === 'offices') {
      const rec = legislatorsData?.counties?.find((x) => x.county === current);
      if (rec) {
        const context = document.createElement('p');
        context.className = 'meta';
        context.textContent =
          'N.C. General Assembly roster checked ' +
          legislatorsData.as_of +
          '. These districts intersect the county; use the address finder above to identify your own member.';
        detail.append(context);
        for (const [headingText, people] of [
          ['N.C. House districts', rec.house],
          ['N.C. Senate districts', rec.senate]
        ]) {
          const heading = document.createElement('h4');
          heading.textContent = headingText;
          detail.append(heading);
          const cards = document.createElement('div');
          cards.className = 'source-grid';
          for (const person of people) {
            const card = document.createElement('div');
            card.className = 'source-card';
            const name = document.createElement('strong');
            name.textContent = 'District ' + person.district + ' · ' + person.name;
            const description = document.createElement('p');
            description.textContent = person.party + ' · ' + person.roster_label;
            const link = document.createElement('a');
            link.href = person.profile_url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.textContent = 'Official profile';
            card.append(name, description, link);
            cards.append(card);
          }
          detail.append(cards);
        }
      }
    }

    if (tab === 'living') {
      const rec = countyWork?.counties?.find((x) => x.county === current);
      if (rec) {
        const cards = document.createElement('div');
        cards.className = 'source-grid';
        const entries = [
          [
            'Median household income',
            '$' + rec.median_household_income.usd_2024.toLocaleString(),
            '2024 inflation-adjusted dollars · 90% margin of error ±$' +
              rec.median_household_income.moe_usd_2024_90pct.toLocaleString()
          ],
          [
            'Rent burden',
            rec.renter_households_gross_rent_30pct_plus.share_percent.toFixed(1) + '%',
            'Renter households spending at least 30% of income on gross rent · ' +
              rec.renter_households_gross_rent_30pct_plus.households.toLocaleString() +
              ' of ' +
              rec.renter_households_gross_rent_30pct_plus.denominator_households.toLocaleString() +
              ' with computed ratios'
          ],
          [
            'Longer commute',
            rec.commuters_30_minutes_plus.share_percent.toFixed(1) + '%',
            'Workers whose travel to work is 30 minutes or more · ' +
              rec.commuters_30_minutes_plus.persons.toLocaleString() +
              ' of ' +
              rec.commuters_30_minutes_plus.denominator_persons.toLocaleString() +
              ' commuters'
          ]
        ];
        for (const [title, value, description] of entries) {
          const card = document.createElement('div');
          card.className = 'source-card';
          const heading = document.createElement('strong');
          heading.textContent = title;
          const number = document.createElement('div');
          number.className = 'number';
          number.textContent = value;
          const para = document.createElement('p');
          para.textContent = description;
          card.append(heading, number, para);
          cards.append(card);
        }
        detail.append(cards);
      } else {
        const todo = document.createElement('div');
        todo.className = 'todo';
        todo.innerHTML =
          '<strong>TODO (Phase 2):</strong> Census ACS affordability tables for North Carolina counties have not been loaded yet.';
        detail.append(todo);
      }
    }

    const record = seedRecords?.counties?.find((x) => x.county === current);
    if (record) {
      const heading = document.createElement('h4');
      heading.textContent = 'Direct county records';
      heading.style.marginTop = '25px';
      detail.append(heading);
      const rg = document.createElement('div');
      rg.className = 'source-grid';
      const wanted =
        tab === 'offices'
          ? ['elected_offices', 'elections', 'county_website']
          : tab === 'money'
            ? ['budget', 'budget_detail', 'county_website']
            : tab === 'docket'
              ? ['agenda', 'minutes', 'legislation', 'county_website']
              : null;
      for (const src of record.sources) {
        if (wanted && !wanted.includes(src.category)) continue;
        const card = document.createElement('div');
        card.className = 'source-card';
        const title = document.createElement('strong');
        title.textContent = src.title;
        const description = document.createElement('p');
        description.textContent =
          src.description +
          ' · Checked ' +
          src.retrieved_at +
          ' · ' +
          (src.verification === 'source_link_verified' ? 'link verified' : 'source directory verified');
        const a = document.createElement('a');
        a.href = src.url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = 'Open county record';
        card.append(title, description, a);
        rg.append(card);
      }
      if (rg.childElementCount) detail.append(rg);
    }
  }

  let mapSvg = null;
  let mapMode = 'population';
  let mapData = null;
  let seedRecords = null;
  let docketData = null;
  let budgetData = null;
  let expandedDocket = null;
  let countyWork = null;
  let legislatorsData = null;

  function paintMap() {
    if (!mapSvg) return;
    for (const path of mapSvg.querySelectorAll('path[data-county]')) {
      const name = path.dataset.county;
      const info = mapData?.counties?.[name] || {};
      path.classList.toggle('selected', name === current);
      path.setAttribute('tabindex', '0');
      path.setAttribute('role', 'button');
      path.setAttribute('aria-label', name + ' County');
      let color = '#c9dce7';
      if (mapMode === 'population' && Number.isFinite(info.population)) {
        const v = Math.min(1, Math.log10(Math.max(1, info.population) / 10000) / 2.4);
        color = `hsl(204 45% ${87 - v * 43}%)`;
      }
      if (mapMode === 'income' && countyWork) {
        const rec = countyWork.counties.find((x) => x.county === name);
        if (rec) {
          const income = rec.median_household_income.usd_2024;
          const v = Math.max(0, Math.min(1, (income - 40000) / 70000));
          color = `hsl(36 58% ${87 - v * 39}%)`;
        }
      }
      if (mapMode === 'control') {
        color =
          info.party_control === 'Republican'
            ? '#b95650'
            : info.party_control === 'Democratic'
              ? '#4d75a2'
              : info.party_control === 'Mixed/Other'
                ? '#a078a5'
                : '#cbd5dc';
      }
      path.style.fill = color;
      let title = path.querySelector('title');
      if (!title) {
        title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        path.prepend(title);
      }
      title.textContent =
        name +
        ' County' +
        (Number.isFinite(info.population)
          ? ' · ' + info.population.toLocaleString() + ' residents (' + (mapData.population_year || 'year unknown') + ')'
          : '') +
        (mapMode === 'control' ? ' · ' + (info.party_control || 'leadership not verified') : '');
    }
    let labels = mapSvg.querySelector('#county-data-labels');
    if (!labels) {
      labels = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      labels.id = 'county-data-labels';
      mapSvg.append(labels);
    }
    labels.replaceChildren();
    if (mapMode === 'population' || mapMode === 'income' || mapMode === 'control') {
      for (const path of mapSvg.querySelectorAll('path[data-county]')) {
        const name = path.dataset.county;
        const info = mapData?.counties?.[name] || {};
        const box = path.getBBox();
        if (box.width < 27 || box.height < 17) continue;
        const work = countyWork?.counties?.find((x) => x.county === name);
        const value =
          mapMode === 'income' && work
            ? '$' + Math.round(work.median_household_income.usd_2024 / 1000) + 'k'
            : mapMode === 'population' && Number.isFinite(info.population)
              ? info.population >= 1000000
                ? (info.population / 1000000).toFixed(1) + 'm'
                : Math.round(info.population / 1000) + 'k'
              : mapMode === 'control'
                ? info.party_control === 'Republican'
                  ? 'R'
                  : info.party_control === 'Democratic'
                    ? 'D'
                    : info.party_control === 'Mixed/Other'
                      ? 'M'
                      : '?'
                : '';
        if (!value) continue;
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.classList.add('map-label');
        if (box.width < 42) label.classList.add('small');
        label.setAttribute('x', (box.x + box.width / 2).toFixed(1));
        label.setAttribute('y', (box.y + box.height / 2).toFixed(1));
        label.textContent = value;
        labels.append(label);
      }
    }
    const info = mapData?.counties?.[current] || {};
    document.getElementById('map-status').textContent =
      current +
      ' County' +
      (Number.isFinite(info.population)
        ? ' · ' + info.population.toLocaleString() + ' residents (Census estimate ' + mapData.population_year + ')'
        : ' · population pending') +
      (mapMode === 'control' ? ' · governing majority: ' + (info.party_control || 'not yet verified') : '');
    const provenance = document.getElementById('map-provenance');
    provenance.replaceChildren();
    const popLink = document.createElement('a');
    popLink.href = mapData?.population_source_page || 'https://www.census.gov/';
    popLink.target = '_blank';
    popLink.rel = 'noopener noreferrer';
    popLink.textContent = 'Census population source';
    provenance.append(popLink);
    if (mapMode === 'control' && info.party_source) {
      provenance.append(document.createTextNode(' · '));
      const partyLink = document.createElement('a');
      partyLink.href = info.party_source;
      partyLink.target = '_blank';
      partyLink.rel = 'noopener noreferrer';
      partyLink.textContent = 'County leadership source';
      provenance.append(partyLink);
    }
    const legend = document.getElementById('map-legend');
    legend.replaceChildren();
    const items =
      mapMode === 'control'
        ? [
            ['#b95650', 'Republican'],
            ['#4d75a2', 'Democratic'],
            ['#a078a5', 'Mixed / other'],
            ['#cbd5dc', 'Unverified']
          ]
        : mapMode === 'population'
          ? [
              ['#c9dce7', 'No population figure yet'],
              ['#5c8dad', 'Darker = more residents; labels = 2025 population']
            ]
          : mapMode === 'income'
            ? [
                ['#f1d69d', 'Lower median household income'],
                ['#a4632d', 'Higher median household income; ACS estimate (not yet loaded)']
              ]
            : [
                ['#c9dce7', 'County boundary'],
                ['#d7a64f', 'Hover or select']
              ];
    for (const [color, label] of items) {
      const item = document.createElement('span');
      const sw = document.createElement('i');
      sw.className = 'swatch';
      sw.style.background = color;
      item.append(sw, document.createTextNode(label));
      legend.append(item);
    }
  }

  async function loadMap() {
    try {
      const fresh = '?updated=' + Date.now();
      const [
        svgResponse,
        dataResponse,
        seedResponse,
        docketResponse,
        budgetResponse,
        expandedResponse,
        workResponse,
        legislatorsResponse
      ] = await Promise.all([
        fetch('county-map.svg' + fresh, { cache: 'no-store' }),
        fetch('map-data.json' + fresh, { cache: 'no-store' }),
        fetch('seed-records.json' + fresh, { cache: 'no-store' }),
        fetch('docket-records.json' + fresh, { cache: 'no-store' }),
        fetch('budget-records.json' + fresh, { cache: 'no-store' }),
        fetch('docket-expanded.json' + fresh, { cache: 'no-store' }),
        fetch('county-work-affordability.json' + fresh, { cache: 'no-store' }),
        fetch('nc-legislators.json' + fresh, { cache: 'no-store' })
      ]);
      if (!svgResponse.ok) throw Error('map file unavailable');
      const svgText = await svgResponse.text();
      const parsed = new DOMParser().parseFromString(svgText, 'image/svg+xml');
      mapSvg = parsed.documentElement;
      document.getElementById('nc-map').replaceChildren(document.importNode(mapSvg, true));
      mapSvg = document.querySelector('#nc-map svg');
      mapSvg.addEventListener('click', (event) => {
        const path = event.target.closest('path[data-county]');
        if (!path) return;
        current = path.dataset.county;
        history.replaceState(null, '', '#county-' + current.toLowerCase().replaceAll(' ', '-'));
        renderList();
        renderDetail();
        paintMap();
        document.getElementById('county-drilldown').focus();
      });
      mapSvg.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const path = event.target.closest('path[data-county]');
        if (!path) return;
        event.preventDefault();
        path.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });
      if (dataResponse.ok) mapData = await dataResponse.json();
      if (seedResponse.ok) {
        seedRecords = await seedResponse.json();
        document.getElementById('source-county-count').textContent = seedRecords.counties.length;
      }
      if (docketResponse.ok) docketData = await docketResponse.json();
      if (budgetResponse.ok) budgetData = await budgetResponse.json();
      if (expandedResponse.ok) expandedDocket = await expandedResponse.json();
      if (workResponse.ok) countyWork = await workResponse.json();
      if (legislatorsResponse.ok) legislatorsData = await legislatorsResponse.json();
      renderDetail();
      renderDocket();
      paintMap();
    } catch (error) {
      console.error(error);
      document.getElementById('nc-map').textContent = 'County map is being prepared. Use the county list below.';
    }
  }

  function renderDocket() {
    const meetings = document.getElementById('meeting-list');
    const bills = document.getElementById('docket-list');
    meetings.replaceChildren();
    bills.replaceChildren();
    const upcoming = (expandedDocket?.upcoming_meetings || []).filter((rec) => rec.date);
    if (!upcoming.length) {
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML =
        '<h3>No meetings listed yet</h3><p>TODO (Phase 2): sourced North Carolina public meeting listings have not been loaded.</p>';
      meetings.append(card);
    } else {
      for (const rec of upcoming) {
        const card = document.createElement('div');
        card.className = 'card';
        const kicker = document.createElement('div');
        kicker.className = 'kicker';
        kicker.textContent = (rec.county ? rec.county + ' County' : 'State') + ' · ' + rec.date;
        const h = document.createElement('h3');
        h.textContent = rec.body;
        const p = document.createElement('p');
        p.textContent = rec.topic || '';
        card.append(kicker, h, p);
        meetings.append(card);
      }
    }
    const tracked = expandedDocket?.tracked_bills || [];
    if (!tracked.length) {
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML =
        '<h3>No bills tracked yet</h3><p>TODO (Phase 2): a sourced N.C. General Assembly docket has not been loaded.</p>';
      bills.append(card);
    } else {
      for (const rec of tracked) {
        const card = document.createElement('div');
        card.className = 'card';
        const strong = document.createElement('h3');
        strong.textContent = rec.body;
        const p = document.createElement('p');
        p.textContent = (rec.topic || '') + (rec.vote_status ? ' · ' + rec.vote_status : '');
        card.append(strong, p);
        bills.append(card);
      }
    }
  }

  document.querySelectorAll('[data-mapmode]').forEach((button) =>
    button.addEventListener('click', () => {
      mapMode = button.dataset.mapmode;
      document.querySelectorAll('[data-mapmode]').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
      paintMap();
    })
  );
  search.addEventListener('input', renderList);
  document.querySelectorAll('[data-tab]').forEach((b) =>
    b.addEventListener('click', () => {
      tab = b.dataset.tab;
      document.querySelectorAll('[data-tab]').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
      renderDetail();
    })
  );
  const hash = location.hash.match(/^#county-([a-z-]+)$/);
  if (hash) {
    const found = counties.find((c) => c.toLowerCase().replaceAll(' ', '-') === hash[1]);
    if (found) current = found;
  }
  renderList();
  renderDetail();
  loadMap();
})();
