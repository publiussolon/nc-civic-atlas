(() => {
'use strict';

const STYLE = 'https://tiles.openfreemap.org/styles/dark';
const NC_BOUNDS = [[-84.42, 33.80], [-75.40, 36.62]];
const PRECINCT_ZOOM = 8;
const MEMBERS_AS_OF = 'November 24, 2026';
const COLORS = {
  r: ['#e8a29b', '#d4605a', '#a8302f'],
  d: ['#9cc3e4', '#4f8fc9', '#245f9e'],
  tie: '#9b7bb5', none: '#5b6676'
};
const POP_SHADES = ['#284264', '#35678b', '#297c95', '#218e96', '#159c94'];
const POP_STEPS = [50000, 100000, 250000, 500000];
const PARTY_FILL = {Republican: '#b8423f', Democratic: '#3f7fba'};
const CHAMBERS = {
  house: {label: 'NC House', noun: 'House District', seats: 120},
  senate: {label: 'NC Senate', noun: 'Senate District', seats: 50},
  congress: {label: 'U.S. House', noun: 'Congressional District', seats: 14}
};
const COUNTY_LAYERS = ['results', 'chairs', 'population', 'government'];
const CHAIR_SHADES = ['#4a3440', '#7a3040', '#a8333f', '#d9434c'];
const CHAIR_STEPS = [.10, .25, .50];
const METHOD_LABEL = {roster: 'Committee roster', election_results: 'Official committee results', candidate_listing: 'Candidate listing', none_found: 'No public record found'};
let committee = {total: {}, counties: {}};
const emptyOf = c => (c?.empty || 0) + (c?.empty_no_filer || 0);
const knownOf = c => (c?.filled || 0) + emptyOf(c);

const $ = id => document.getElementById(id);
const slug = name => name.toLowerCase().replaceAll(' ', '-');
const fmt = n => n == null ? '—' : n.toLocaleString('en-US');
const pct = (n, d) => n == null || !d ? '—' : (100 * n / d).toFixed(1) + '%';
const compact = new Intl.NumberFormat('en', {notation: 'compact', maximumFractionDigits: 1});
const desktop = matchMedia('(min-width: 861px)');

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e[k] = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  e.append(...kids.flat(Infinity).filter(k => k != null && k !== false));
  return e;
}
async function json(url) {
  const r = await fetch(url);
  if (!r.ok) throw Error(url);
  return r.json();
}
function once(fn) {
  let p;
  return () => p ||= fn().catch(e => { p = null; throw e; });
}

/* ---------- Geometry ---------- */
function ringArea(ring) {
  let a = 0;
  for (let i = 1; i < ring.length; i++) a += (ring[i - 1][0] * ring[i][1]) - (ring[i][0] * ring[i - 1][1]);
  return a / 2;
}
function inRing([x, y], ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
const polygonsOf = g => g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
function inGeometry(pt, g) {
  return polygonsOf(g).some(([outer, ...holes]) => inRing(pt, outer) && !holes.some(r => inRing(pt, r)));
}
function bboxOf(g) {
  const b = [Infinity, Infinity, -Infinity, -Infinity];
  for (const poly of polygonsOf(g)) for (const [x, y] of poly[0]) {
    if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y;
    if (x > b[2]) b[2] = x; if (y > b[3]) b[3] = y;
  }
  return b;
}
const unionBox = boxes => boxes.reduce((a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])]);
const inBox = ([x, y], b) => x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3];
// A point guaranteed to sit inside the largest polygon: midpoint of the widest scanline span.
function interiorPoint(g) {
  let best = null, area = -1;
  for (const p of polygonsOf(g)) { const a = Math.abs(ringArea(p[0])); if (a > area) { area = a; best = p; } }
  let lo = Infinity, hi = -Infinity;
  for (const [, y] of best[0]) { lo = Math.min(lo, y); hi = Math.max(hi, y); }
  let point = best[0][0], width = -1;
  for (const f of [.5, .4, .6, .3, .7, .2, .8]) {
    const y = lo + (hi - lo) * f, xs = [];
    for (const ring of best) for (let i = 1; i < ring.length; i++) {
      const [x1, y1] = ring[i - 1], [x2, y2] = ring[i];
      if ((y1 > y) !== (y2 > y)) xs.push(x1 + (y - y1) * (x2 - x1) / (y2 - y1));
    }
    xs.sort((a, b) => a - b);
    for (let i = 0; i + 1 < xs.length; i += 2) {
      if (xs[i + 1] - xs[i] > width) { width = xs[i + 1] - xs[i]; point = [(xs[i] + xs[i + 1]) / 2, y]; }
    }
  }
  return point;
}
// County JSON stores display paths projected as x = 760(lon + 85), y = 1000(37 − lat).
function pathToGeometry(d) {
  const rings = [];
  for (const part of d.split(/[MmZz]/)) {
    const n = part.match(/-?\d*\.?\d+/g);
    if (!n || n.length < 6) continue;
    const ring = [];
    for (let i = 0; i + 1 < n.length; i += 2) ring.push([+(n[i] / 760 - 85).toFixed(6), +(37 - n[i + 1] / 1000).toFixed(6)]);
    const a = ring[0], b = ring[ring.length - 1];
    if (a[0] !== b[0] || a[1] !== b[1]) ring.push([a[0], a[1]]);
    if (ring.length >= 4) rings.push(ring);
  }
  const depth = rings.map((r, i) => rings.reduce((n, o, j) => n + (j !== i && inRing(r[0], o) ? 1 : 0), 0));
  const outers = new Map();
  rings.forEach((r, i) => { if (depth[i] % 2 === 0) outers.set(i, [ringArea(r) < 0 ? r.reverse() : r]); });
  rings.forEach((r, i) => {
    if (depth[i] % 2 === 0) return;
    let host = null, size = Infinity;
    for (const [o, [outer]] of outers) if (inRing(r[0], outer)) { const s = Math.abs(ringArea(outer)); if (s < size) { size = s; host = o; } }
    if (host != null) outers.get(host).push(ringArea(r) > 0 ? r.reverse() : r);
  });
  const polys = [...outers.values()];
  return polys.length === 1 ? {type: 'Polygon', coordinates: polys[0]} : {type: 'MultiPolygon', coordinates: polys};
}

/* ---------- Results helpers ---------- */
function marginOf(p) {
  return p.trump == null || p.harris == null || !p.total ? null : (p.trump - p.harris) / p.total;
}
function colorFor(m) {
  if (m == null) return COLORS.none;
  if (m === 0) return COLORS.tie;
  const s = Math.abs(m) >= .3 ? 2 : Math.abs(m) >= .1 ? 1 : 0;
  return (m > 0 ? COLORS.r : COLORS.d)[s];
}
function marginText(m) {
  if (m == null) return 'Counts unavailable';
  if (m === 0) return 'Tied';
  return (m > 0 ? 'Trump +' : 'Harris +') + (Math.abs(m) * 100).toFixed(1);
}
const leadClass = m => m == null || m === 0 ? '' : m > 0 ? 'r' : 'd';
const partyClass = p => p === 'Republican' ? 'r' : p === 'Democratic' ? 'd' : 'x';

/* ---------- State ---------- */
const state = {layer: 'results', county: null, precinct: null, district: null, muni: '', sort: 'harris', filter: ''};
let counties = [], countyByName = new Map(), countyInfo = {}, places = null;
const loadedPrecincts = new Map();
const precinctCache = new Map();
let map, popup, marker, hovered = null, renderToken = 0;

const loadMeta = once(() => json('../map-data.json'));
const loadMembers = once(() => json('districts/members.json'));
const districtFiles = {};
function loadDistricts(kind) {
  districtFiles[kind] ||= once(async () => {
    const [geo, roster] = await Promise.all([json('districts/' + kind + '.geojson'), loadMembers()]);
    for (const f of geo.features) {
      const d = f.properties.district, m = roster[kind][d];
      Object.assign(f.properties, {
        kind, member: m?.name || '', party: m?.party || '', url: m?.url || '',
        fill: PARTY_FILL[m?.party] || '#59687a'
      });
      f.bbox = bboxOf(f.geometry);
    }
    geo.features.sort((a, b) => a.properties.district - b.properties.district);
    return geo;
  });
  return districtFiles[kind]();
}
const HAS_MUNIS = false; // TODO: official municipal outlines are not in this release.
const loadMunis = name => HAS_MUNIS ? json('municipalities/' + slug(name) + '.geojson') : Promise.resolve({type: 'FeatureCollection', features: []});
const loadPlaces = once(() => json('place-index.json'));

function loadCounty(name) {
  if (!precinctCache.has(name)) precinctCache.set(name, json('data/' + slug(name) + '.json').then(d => {
    const features = d.precincts.map(p => {
      const m = marginOf(p);
      return {type: 'Feature', properties: {
        id: p.id, name: p.name, municipality: p.municipality, county: name,
        trump: p.trump, harris: p.harris, other: p.other, total: p.total, margin: m, fill: colorFor(m)
      }, geometry: pathToGeometry(p.path)};
    });
    loadedPrecincts.set(name, features);
    queuePrecinctRefresh();
    return {features, byId: new Map(features.map(f => [f.properties.id, f]))};
  }).catch(e => { precinctCache.delete(name); throw e; }));
  return precinctCache.get(name);
}
let refreshQueued = false;
function queuePrecinctRefresh() {
  if (refreshQueued) return;
  refreshQueued = true;
  requestAnimationFrame(() => {
    refreshQueued = false;
    map.getSource('precincts')?.setData({type: 'FeatureCollection', features: [...loadedPrecincts.values()].flat()});
  });
}

/* ---------- Map ---------- */
function padding() {
  return desktop.matches ? {top: 80, bottom: 80, left: 410, right: 70} : {top: 24, bottom: 24, left: 24, right: 24};
}
function fit(box, maxZoom = 12.5) {
  map.fitBounds([[box[0], box[1]], [box[2], box[3]]], {padding: padding(), maxZoom, duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 900});
}
class HomeControl {
  onAdd() {
    this.el = h('div', {class: 'maplibregl-ctrl maplibregl-ctrl-group'},
      h('button', {type: 'button', class: 'maplibregl-ctrl-home', title: 'Show all of North Carolina', 'aria-label': 'Show all of North Carolina', onclick: goHome, text: '⌂'}));
    return this.el;
  }
  onRemove() { this.el.remove(); }
}

function addLayers() {
  const before = map.getLayer('highway_name_other') ? 'highway_name_other' : undefined;
  const empty = {type: 'FeatureCollection', features: []};
  map.addSource('counties', {type: 'geojson', data: {type: 'FeatureCollection', features: counties}, promoteId: 'county'});
  map.addSource('county-labels', {type: 'geojson', data: {type: 'FeatureCollection', features: counties.map(f => ({type: 'Feature', properties: {county: f.properties.county}, geometry: {type: 'Point', coordinates: f.labelPoint}}))}});
  map.addSource('precincts', {type: 'geojson', data: empty, promoteId: 'id', tolerance: .25});
  map.addSource('munis', {type: 'geojson', data: empty});
  map.addSource('districts', {type: 'geojson', data: empty, promoteId: 'district'});
  map.addSource('district-labels', {type: 'geojson', data: empty});

  const hover = (on, off) => ['case', ['boolean', ['feature-state', 'hover'], false], on, off];
  const nearOrSelected = (sel, far) => ['interpolate', ['linear'], ['zoom'], PRECINCT_ZOOM - .4, ['case', sel, 1, far], PRECINCT_ZOOM + .2, 1];
  const isSelCounty = ['==', ['get', 'county'], ''];

  map.addLayer({id: 'counties-fill', type: 'fill', source: 'counties', paint: {'fill-color': ['get', 'fill_results'], 'fill-opacity': .7}}, before);
  map.addLayer({id: 'precincts-fill', type: 'fill', source: 'precincts', paint: {
    'fill-color': ['get', 'fill'],
    'fill-opacity': ['interpolate', ['linear'], ['zoom'], PRECINCT_ZOOM - .4, ['case', isSelCounty, .78, 0], PRECINCT_ZOOM + .2, .66, 12, .55]
  }}, before);
  map.addLayer({id: 'precincts-line', type: 'line', source: 'precincts', paint: {
    'line-color': '#0a1424', 'line-width': ['interpolate', ['linear'], ['zoom'], 8, .3, 13, 1.2],
    'line-opacity': nearOrSelected(isSelCounty, 0)
  }}, before);
  map.addLayer({id: 'precincts-hover', type: 'line', source: 'precincts', paint: {'line-color': '#ffffff', 'line-width': 1.6, 'line-opacity': hover(.9, 0)}}, before);
  map.addLayer({id: 'districts-fill', type: 'fill', source: 'districts', paint: {'fill-color': ['get', 'fill'], 'fill-opacity': hover(.78, .55)}}, before);
  map.addLayer({id: 'districts-line', type: 'line', source: 'districts', paint: {'line-color': '#0a1424', 'line-width': ['interpolate', ['linear'], ['zoom'], 6, .6, 11, 1.6]}}, before);
  map.addLayer({id: 'munis-line', type: 'line', source: 'munis', paint: {'line-color': '#efe6c4', 'line-width': 1, 'line-opacity': .65, 'line-dasharray': [3, 2]}}, before);
  map.addLayer({id: 'counties-line', type: 'line', source: 'counties', paint: {
    'line-color': '#d4dcea', 'line-width': ['interpolate', ['linear'], ['zoom'], 6, .6, 10, 1.8], 'line-opacity': .55
  }}, before);
  map.addLayer({id: 'counties-hover', type: 'line', source: 'counties', paint: {'line-color': '#ffffff', 'line-width': 2, 'line-opacity': hover(1, 0)}}, before);
  map.addLayer({id: 'districts-selected', type: 'line', source: 'districts', filter: ['==', ['get', 'district'], -1], paint: {'line-color': '#ffffff', 'line-width': 3}}, before);
  map.addLayer({id: 'counties-selected', type: 'line', source: 'counties', filter: ['==', ['get', 'county'], ''], paint: {'line-color': '#f07a80', 'line-width': 2.6}}, before);
  map.addLayer({id: 'precincts-selected', type: 'line', source: 'precincts', filter: ['==', ['get', 'id'], ''], paint: {'line-color': '#fff484', 'line-width': 3}}, before);
  const label = {'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-letter-spacing': .04};
  const labelPaint = {'text-color': '#e9eef7', 'text-halo-color': '#0a1424', 'text-halo-width': 1.6};
  map.addLayer({id: 'county-labels', type: 'symbol', source: 'county-labels', minzoom: 6.4, maxzoom: PRECINCT_ZOOM + .5, layout: {...label, 'text-field': ['get', 'county']}, paint: labelPaint});
  map.addLayer({id: 'district-labels', type: 'symbol', source: 'district-labels', minzoom: 6.2, layout: {...label, 'text-field': ['get', 'district'], 'text-size': 12}, paint: labelPaint});
}

function setVisible(id, on) { map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); }
function applyLayerStyle() {
  const l = state.layer, district = !!CHAMBERS[l], results = l === 'results';
  ['precincts-fill', 'precincts-line', 'precincts-hover', 'precincts-selected', 'munis-line'].forEach(id => setVisible(id, results));
  ['districts-fill', 'districts-line', 'districts-selected', 'district-labels'].forEach(id => setVisible(id, district));
  setVisible('counties-fill', !district);
  setVisible('county-labels', !district);
  setVisible('counties-hover', !district);
  map.setPaintProperty('counties-fill', 'fill-color', ['get', 'fill_' + (district ? 'results' : l)]);
  map.setPaintProperty('counties-fill', 'fill-opacity', results
    ? ['interpolate', ['linear'], ['zoom'], PRECINCT_ZOOM - .4, .72, PRECINCT_ZOOM + .2, .06]
    : hover(.85, .72));
  map.setPaintProperty('counties-line', 'line-opacity', district ? .35 : .55);
  function hover(on, off) { return ['case', ['boolean', ['feature-state', 'hover'], false], on, off]; }
}
function applySelection() {
  const sel = state.county || '';
  map.setFilter('counties-selected', ['==', ['get', 'county'], CHAMBERS[state.layer] ? '' : sel]);
  map.setFilter('precincts-selected', ['==', ['get', 'id'], state.precinct || '']);
  map.setFilter('districts-selected', ['==', ['get', 'district'], state.district ?? -1]);
  const isSel = ['==', ['get', 'county'], sel];
  map.setPaintProperty('precincts-fill', 'fill-opacity', ['interpolate', ['linear'], ['zoom'], PRECINCT_ZOOM - .4, ['case', isSel, .78, 0], PRECINCT_ZOOM + .2, .66, 12, .55]);
  map.setPaintProperty('precincts-line', 'line-opacity', ['interpolate', ['linear'], ['zoom'], PRECINCT_ZOOM - .4, ['case', isSel, 1, 0], PRECINCT_ZOOM + .2, 1]);
}
const precinctsVisible = county => state.layer === 'results' && (map.getZoom() >= PRECINCT_ZOOM - .2 || county === state.county);

function loadVisibleCounties() {
  if (state.layer !== 'results' || map.getZoom() < PRECINCT_ZOOM - .3) return;
  const b = map.getBounds(), view = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
  for (const f of counties) {
    const c = f.bbox;
    if (c[0] <= view[2] && c[2] >= view[0] && c[1] <= view[3] && c[3] >= view[1]) loadCounty(f.properties.county).catch(() => {});
  }
}

function pick(point) {
  const layers = CHAMBERS[state.layer] ? ['districts-fill'] : state.layer === 'results' ? ['precincts-fill', 'counties-fill'] : ['counties-fill'];
  for (const f of map.queryRenderedFeatures(point, {layers})) {
    if (f.layer.id === 'precincts-fill' && !precinctsVisible(f.properties.county)) continue;
    return f;
  }
  return null;
}
function setHover(f) {
  const key = f ? {source: f.source, id: f.id} : null;
  if (hovered && (!key || hovered.source !== key.source || hovered.id !== key.id)) map.setFeatureState(hovered, {hover: false});
  if (key && key.id != null) map.setFeatureState(key, {hover: true});
  hovered = key;
}
function tooltip(f) {
  const p = f.properties;
  if (f.source === 'precincts') {
    return [p.name, (p.municipality ? p.municipality + ' · ' : '') + (p.margin === 'null' || p.margin == null ? 'Counts unavailable' :
      marginText(+p.margin) + ' · Trump ' + fmt(+p.trump) + ', Harris ' + fmt(+p.harris))];
  }
  if (f.source === 'districts') return [CHAMBERS[p.kind].noun + ' ' + p.district, p.member ? p.member + ' (' + (p.party[0] || '?') + ')' : 'Member unavailable'];
  const c = countyByName.get(p.county).properties;
  if (state.layer === 'chairs') {
    const ch = committee.counties[p.county];
    return [p.county + ' County', !ch || !knownOf(ch) ? (committee.status === 'todo' ? 'Committee seats not compiled in this release' : 'No public record found') : fmt(emptyOf(ch)) + ' empty of ' + fmt(ch.seats) + ' seats · ' + fmt(ch.unknown) + ' unknown'];
  }
  if (state.layer === 'population') return [p.county + ' County', fmt(c.population) + ' residents'];
  if (state.layer === 'government') return [p.county + ' County', 'Governing majority: ' + (c.party_control || 'unverified')];
  return [p.county + ' County', marginText(c.margin) + ' · ' + fmt(c.harris_led) + ' of ' + fmt(c.precincts) + ' precincts Harris-led'];
}
function onMove(e) {
  const f = pick(e.point);
  setHover(f);
  map.getCanvas().style.cursor = f ? 'pointer' : '';
  if (!f || !matchMedia('(hover: hover)').matches) { popup.remove(); return; }
  const [title, detail] = tooltip(f);
  popup.setLngLat(e.lngLat).setDOMContent(h('div', {}, h('strong', {text: title}), h('span', {text: detail}))).addTo(map);
}
function onClick(e) {
  const f = pick(e.point);
  if (!f) return;
  popup.remove();
  const p = f.properties;
  if (f.source === 'precincts') selectPrecinct(p.county, p.id, {fly: false});
  else if (f.source === 'districts') selectDistrict(state.layer, p.district);
  else selectCounty(p.county);
}

/* ---------- Navigation ---------- */
function updateURL() {
  const q = new URLSearchParams();
  if (state.layer !== 'results') q.set('layer', state.layer);
  if (state.district != null) q.set('district', state.district);
  else if (state.county) q.set('county', state.county);
  if (state.precinct) q.set('precinct', state.precinct);
  history.replaceState(null, '', location.pathname + (q.size ? '?' + q : ''));
}
function clearMarker() { marker?.remove(); marker = null; }
function setTabs() {
  document.querySelectorAll('[data-layer]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.layer === state.layer)));
}
async function setLayer(layer, {keep = false} = {}) {
  const wasCounty = COUNTY_LAYERS.includes(state.layer);
  state.layer = layer;
  state.precinct = null;
  state.district = null;
  if (!keep && !(wasCounty && COUNTY_LAYERS.includes(layer))) { state.county = null; clearMarker(); }
  setTabs();
  applyLayerStyle();
  legend();
  if (CHAMBERS[layer]) {
    $('panel').replaceChildren(h('p', {class: 'lede', text: 'Loading ' + CHAMBERS[layer].label + ' districts…'}));
    try {
      const geo = await loadDistricts(layer);
      if (state.layer !== layer) return;
      map.getSource('districts').setData(geo);
      map.getSource('district-labels').setData({type: 'FeatureCollection', features: geo.features.map(f => ({type: 'Feature', properties: {district: String(f.properties.district)}, geometry: {type: 'Point', coordinates: interiorPoint(f.geometry)}}))});
    } catch {
      if (state.layer === layer) $('panel').replaceChildren(h('p', {class: 'lede', text: 'District records could not load. Select the tab again to retry.'}));
      return;
    }
  }
  applySelection();
  if (state.county && COUNTY_LAYERS.includes(layer)) { renderCounty(); if (layer === 'results') openCountyPrecincts(state.county); }
  else if (!keep) renderHome();
  updateURL();
}
function goHome() {
  state.county = state.precinct = state.district = null;
  state.muni = '';
  clearMarker();
  map.getSource('munis').setData({type: 'FeatureCollection', features: []});
  applySelection();
  fit([NC_BOUNDS[0][0], NC_BOUNDS[0][1], NC_BOUNDS[1][0], NC_BOUNDS[1][1]]);
  renderHome();
  updateURL();
}
let muniFeatures = [];
async function openCountyPrecincts(name) {
  try {
    const [, munis] = await Promise.all([loadCounty(name), loadMunis(name)]);
    if (state.county !== name) return;
    muniFeatures = munis.features.sort((a, b) => a.properties.name.localeCompare(b.properties.name));
    map.getSource('munis').setData(munis);
    renderCountyPrecincts();
  } catch {
    if (state.county === name) $('chips')?.replaceChildren(h('p', {class: 'note', text: 'Precinct records could not load. Select the county again to retry.'}));
  }
}
function selectCounty(name, {fly = true} = {}) {
  if (CHAMBERS[state.layer]) { state.layer = 'results'; setTabs(); applyLayerStyle(); legend(); }
  const changed = state.county !== name;
  state.county = name;
  state.precinct = state.district = null;
  if (changed) { state.muni = ''; clearMarker(); map.getSource('munis').setData({type: 'FeatureCollection', features: []}); }
  applySelection();
  if (fly) fit(countyByName.get(name).bbox, 11);
  renderCounty();
  updateURL();
  if (state.layer === 'results') return openCountyPrecincts(name);
}
async function selectPrecinct(county, id, {fly = true, address = null} = {}) {
  if (state.layer !== 'results') { state.layer = 'results'; setTabs(); applyLayerStyle(); legend(); }
  if (state.county !== county) {
    state.county = county; state.muni = ''; muniFeatures = [];
    map.getSource('munis').setData({type: 'FeatureCollection', features: []});
    openCountyPrecincts(county);
  }
  if (!address) clearMarker();
  const token = ++renderToken;
  state.precinct = id;
  state.district = null;
  applySelection();
  updateURL();
  $('panel').replaceChildren(h('p', {class: 'lede', text: 'Loading precinct…'}));
  let data;
  try { data = await loadCounty(county); } catch {
    if (token === renderToken) $('panel').replaceChildren(h('p', {class: 'lede', text: 'Precinct records could not load. Try again.'}));
    return;
  }
  if (token !== renderToken) return;
  const f = data.byId.get(id);
  if (!f) {
    state.precinct = null; applySelection(); updateURL(); renderCounty();
    status('That precinct is not in the ' + county + ' County map.');
    return;
  }
  if (fly) fit(bboxOf(f.geometry), 13.5);
  renderPrecinct(f, address, token);
}
function selectDistrict(kind, d) {
  state.district = Number(d);
  state.county = state.precinct = null;
  applySelection();
  updateURL();
  loadDistricts(kind).then(geo => {
    const f = geo.features.find(x => x.properties.district === state.district);
    if (!f || state.layer !== kind) return;
    fit(f.bbox, 12);
    renderDistrict(kind, f);
  });
}

/* ---------- Panel ---------- */
function status(text) { $('search-status').textContent = text || ''; }
function head({eyebrow, title, back, lede}) {
  const text = h('div', {}, h('p', {class: 'eyebrow', text: eyebrow}), h('h2', {text: title}));
  return [
    back ? h('div', {class: 'head'}, h('button', {type: 'button', class: 'back', 'aria-label': back.label, title: back.label, onclick: back.go, text: '←'}), text) : text,
    lede ? h('p', {class: 'lede', text: lede}) : null
  ];
}
function voteBar(trump, harris, total) {
  return [
    h('div', {class: 'bar', role: 'img', 'aria-label': 'Trump ' + pct(trump, total) + ', Harris ' + pct(harris, total)},
      h('span', {style: 'width:' + (100 * trump / total || 0) + '%'}), h('span', {style: 'width:' + (100 * harris / total || 0) + '%'})),
    h('div', {class: 'bar-key'}, h('span', {}, h('b', {text: 'Trump '}), pct(trump, total)), h('span', {}, h('b', {text: 'Harris '}), pct(harris, total)))
  ];
}
const SORTS = {
  harris: ['Most Harris-led precincts', (a, b) => b.harris_led - a.harris_led || a.county.localeCompare(b.county)],
  close: ['Closest margin', (a, b) => Math.abs(a.margin) - Math.abs(b.margin)],
  trump: ['Largest Trump margin', (a, b) => b.margin - a.margin],
  votes: ['Most votes', (a, b) => b.total - a.total],
  name: ['A–Z', (a, b) => a.county.localeCompare(b.county)]
};
function renderHome() {
  renderToken++;
  status('');
  const l = state.layer;
  if (CHAMBERS[l]) return renderDistrictHome(l);
  const all = counties.map(f => f.properties);
  let headBlock, sortOptions, metric;
  if (l === 'results') {
    const t = all.reduce((n, c) => n + c.trump_led, 0), d = all.reduce((n, c) => n + c.harris_led, 0), n = all.reduce((s, c) => s + c.precincts, 0);
    headBlock = head({eyebrow: '2024 President · Precinct results', title: 'Trump led ' + fmt(t) + ' of ' + fmt(n) + ' North Carolina precincts',
      lede: 'Harris led ' + fmt(d) + '. Pick a county to see every precinct, or zoom in to see precinct lines statewide.'});
    sortOptions = ['harris', 'close', 'trump', 'votes', 'name'];
    metric = c => state.sort === 'close' || state.sort === 'trump'
      ? [marginText(c.margin), leadClass(c.margin), fmt(c.harris_led) + ' of ' + fmt(c.precincts) + ' precincts Harris-led']
      : state.sort === 'votes' ? [compact.format(c.total), '', marginText(c.margin) + ' · ' + fmt(c.total) + ' votes']
      : [fmt(c.harris_led), 'd', 'of ' + fmt(c.precincts) + ' precincts Harris-led · ' + marginText(c.margin)];
  } else if (l === 'chairs') {
    const t = committee.total || {};
    const todo = committee.status === 'todo' || !knownOf(t);
    headBlock = head({eyebrow: 'County committee seats', title: todo ? 'County committee vacancies are not yet compiled' : 'At least ' + fmt(emptyOf(t)) + ' committee seats are empty',
      lede: todo
        ? 'TODO: a complete official public roster of county party committee seats was not found for this release, and no vacancy counts are estimated. Counties are shown in gray until a sourced roster is added.'
        : fmt(t.empty) + ' had no winner and ' + fmt(t.empty_no_filer) + ' had no Republican filer, out of ' + fmt(t.seats) + ' seats on record. Another ' + fmt(t.unknown) + ' are unknown: write-in wins, filed candidates with no posted result, and counties with no public record. Pick a county for its sources.'});
    sortOptions = null;
    metric = c => {
      const ch = committee.counties[c.county];
      if (!ch || !knownOf(ch)) return ['—', '', committee.status === 'todo' ? 'Not compiled in this release' : 'No public record found'];
      return [fmt(emptyOf(ch)), 'r', 'empty of ' + fmt(ch.seats) + ' seats · ' + fmt(ch.unknown) + ' unknown · ' + (METHOD_LABEL[ch.method] || ch.method)];
    };
  } else if (l === 'population') {
    const total = all.reduce((n, c) => n + c.population, 0);
    headBlock = head({eyebrow: 'Population · ' + countyInfo.population_year, title: compact.format(total) + ' North Carolinians in 100 counties',
      lede: 'Estimates as of ' + countyInfo.population_as_of + '. Pick a county for its civic profile.'});
    sortOptions = null;
    metric = c => [compact.format(c.population), '', fmt(c.population) + ' residents'];
  } else {
    const verified = all.filter(c => c.party_control);
    headBlock = head({eyebrow: 'County government', title: 'Governing majorities verified in ' + verified.length + ' of 100 counties',
      lede: 'Gray counties have no verified record yet. Records checked ' + countyInfo.checked_at + '.'});
    sortOptions = null;
    metric = c => [c.party_control ? c.party_control[0] : '—', partyClass(c.party_control), c.party_control ? c.party_control + ' majority' : 'Unverified'];
  }
  const sorter = l === 'chairs' ? (a, b) => emptyOf(committee.counties[b.county]) - emptyOf(committee.counties[a.county]) || a.county.localeCompare(b.county)
    : l === 'population' ? (a, b) => b.population - a.population
    : l === 'government' ? (a, b) => (!!b.party_control - !!a.party_control) || a.county.localeCompare(b.county)
    : SORTS[state.sort][1];
  const list = h('ul', {class: 'rows'});
  const draw = () => {
    const q = state.filter.trim().toLowerCase();
    list.replaceChildren(...all.filter(c => c.county.toLowerCase().includes(q)).sort(sorter).map(c => {
      const [num, cls, sub] = metric(c);
      return h('li', {}, h('button', {type: 'button', onclick: () => selectCounty(c.county)},
        h('strong', {text: c.county + ' County'}), h('span', {class: 'num ' + cls, text: num}), h('small', {text: sub})));
    }));
    if (!list.children.length) list.append(h('li', {}, h('p', {class: 'note', text: 'No county matches.'})));
  };
  const filter = h('input', {type: 'search', placeholder: 'Filter counties', 'aria-label': 'Filter counties', value: state.filter, oninput: e => { state.filter = e.target.value; draw(); }});
  const controls = h('div', {class: 'controls'}, filter, sortOptions && h('select', {'aria-label': 'Sort counties', onchange: e => { state.sort = e.target.value; draw(); }},
    sortOptions.map(k => h('option', {value: k, selected: state.sort === k, text: SORTS[k][0]}))));
  draw();
  $('panel').replaceChildren(...headBlock, controls, list);
}
function renderCounty() {
  renderToken++;
  const c = countyByName.get(state.county).properties;
  const profile = h('a', {class: 'link', href: '../index.html#county-' + slug(c.county), text: 'Representatives, budgets and docket →'});
  const back = {label: 'Back to North Carolina', go: goHome};
  if (state.layer === 'chairs') {
    const ch = committee.counties[c.county];
    const seg = (n, color) => h('span', {style: 'background:' + color + ';width:' + (100 * n / (ch?.seats || 1)) + '%'});
    $('panel').replaceChildren(
      ...head({eyebrow: 'Republican committee seats', title: c.county + ' County', back,
        lede: !ch || !knownOf(ch) ? 'No public roster, results or candidate listing was found for this county. Every seat is unknown.'
          : fmt(emptyOf(ch)) + ' of ' + fmt(ch.seats) + ' seats are empty across ' + fmt(ch.precincts) + ' precincts.'}),
      ch && ch.seats ? h('div', {class: 'bar', role: 'img', 'aria-label': fmt(ch.filled) + ' filled, ' + fmt(emptyOf(ch)) + ' empty, ' + fmt(ch.unknown) + ' unknown'},
        seg(ch.filled, '#5f9e6e'), seg(ch.empty, CHAIR_SHADES[3]), seg(ch.empty_no_filer, CHAIR_SHADES[1]), seg(ch.unknown, '#4b5568')) : null,
      ch ? h('table', {class: 'votes'}, h('tbody', {},
        [['Filled', ch.filled, '#5f9e6e'], ['Empty: no winner', ch.empty, CHAIR_SHADES[3]], ['Empty: no Republican filed', ch.empty_no_filer, CHAIR_SHADES[1]], ['Unknown', ch.unknown, '#4b5568']]
          .map(([k, v, col]) => h('tr', {}, h('td', {}, h('span', {class: 'dot', style: 'background:' + col}), k), h('td', {text: fmt(v)}), h('td', {text: pct(v, ch.seats)}))))) : null,
      ch ? h('p', {class: 'note', text: (METHOD_LABEL[ch.method] || ch.method) + (ch.election ? ' · ' + ch.election : '') + (ch.as_of ? ' · as of ' + ch.as_of : '') + ' · checked ' + ch.checked_at + '. Appointments made since then are not counted.'}) : null,
      ch && ch.sources.length ? h('ul', {class: 'reps'}, ch.sources.map(s => h('li', {}, h('a', {href: s.url, text: s.title || s.url})))) : null,
      h('p', {class: 'note', text: !ch ? 'TODO: committee-seat vacancies are not compiled in this release. See committee/README.md.' : ''}),
      h('div', {class: 'actions'}, h('button', {type: 'button', class: 'btn', onclick: () => setLayer('results', {keep: true}), text: 'See precinct results'})),
      profile);
    return;
  }
  if (state.layer !== 'results') {
    $('panel').replaceChildren(
      ...head({eyebrow: state.layer === 'population' ? 'Population' : 'County government', title: c.county + ' County', back,
        lede: fmt(c.population) + ' residents (' + countyInfo.population_as_of + ') · Governing majority: ' + (c.party_control || 'unverified')}),
      h('div', {class: 'actions'}, h('button', {type: 'button', class: 'btn', onclick: () => setLayer('results', {keep: true}), text: 'See precinct results'})),
      profile);
    return;
  }
  $('panel').replaceChildren(
    ...head({eyebrow: '2024 President · Precinct results', title: c.county + ' County', back,
      lede: fmt(c.harris_led) + ' of ' + fmt(c.precincts) + ' precincts led by Harris · ' + marginText(c.margin)}),
    ...voteBar(c.trump, c.harris, c.total),
    h('div', {class: 'bar-key'}, h('span', {text: fmt(c.trump) + ' votes'}), h('span', {text: fmt(c.harris) + ' votes'})),
    h('div', {class: 'actions'}, profile),
    h('section', {class: 'section'},
      h('h3', {}, 'Precincts', h('small', {id: 'chip-count', text: fmt(c.precincts)})),
      h('div', {class: 'controls'},
        h('input', {type: 'search', id: 'chip-filter', placeholder: 'Filter precincts', 'aria-label': 'Filter precincts', oninput: renderChips}),
        h('select', {id: 'muni-select', 'aria-label': 'Municipality', onchange: e => chooseMuni(e.target.value)}, h('option', {value: '', text: 'All municipalities'}))),
      h('div', {class: 'chips', id: 'chips'}, h('p', {class: 'note', text: 'Loading precincts…'}))));
  if (precinctCache.has(c.county) && loadedPrecincts.has(c.county)) renderCountyPrecincts();
}
function renderCountyPrecincts() {
  const select = $('muni-select');
  if (!select) return;
  const names = [...new Set(loadedPrecincts.get(state.county).map(f => f.properties.municipality).filter(Boolean))].sort();
  select.hidden = !names.length;
  select.replaceChildren(h('option', {value: '', text: 'All municipalities'}), ...names.map(n => h('option', {value: n, selected: n === state.muni, text: n})));
  renderChips();
}
function chooseMuni(name) {
  state.muni = name;
  renderChips();
  const f = muniFeatures.filter(m => m.properties.name === name);
  const own = (loadedPrecincts.get(state.county) || []).filter(p => p.properties.municipality === name);
  const boxes = (f.length ? f : own).map(x => bboxOf(x.geometry));
  fit(name && boxes.length ? unionBox(boxes) : countyByName.get(state.county).bbox, name ? 13 : 11);
}
function renderChips() {
  const box = $('chips');
  if (!box || !loadedPrecincts.has(state.county)) return;
  const q = ($('chip-filter')?.value || '').trim().toLowerCase();
  const rows = loadedPrecincts.get(state.county).filter(f => (!state.muni || f.properties.municipality === state.muni) &&
    (!q || (f.properties.name + ' ' + f.properties.municipality).toLowerCase().includes(q)))
    .sort((a, b) => a.properties.name.localeCompare(b.properties.name, 'en', {numeric: true}));
  $('chip-count').textContent = fmt(rows.length);
  box.replaceChildren(...rows.map(f => {
    const p = f.properties;
    return h('button', {type: 'button', class: leadClass(p.margin), title: p.name + (p.municipality ? ' · ' + p.municipality : '') + ' · ' + marginText(p.margin),
      onclick: () => selectPrecinct(state.county, p.id), text: p.name});
  }));
  if (!rows.length) box.append(h('p', {class: 'note', text: 'No precinct matches.'}));
}
async function representatives(point) {
  const kinds = Object.keys(CHAMBERS);
  const geos = await Promise.all(kinds.map(loadDistricts));
  return kinds.map((kind, i) => {
    const hits = geos[i].features.filter(f => inBox(point, f.bbox) && inGeometry(point, f.geometry));
    return [kind, hits.length === 1 ? hits[0].properties : null];
  });
}
function repList(rows) {
  return h('ul', {class: 'reps'}, rows.map(([kind, p]) => h('li', {},
    h('span', {}, CHAMBERS[kind].label + (p ? ' · District ' + p.district : ' · Boundary unresolved')),
    p && h('span', {class: 'party ' + partyClass(p.party), text: p.party ? p.party[0] : '?'}),
    p && p.member && h('small', {}, h('a', {href: p.url, text: p.member})))));
}
function renderPrecinct(f, address, token) {
  const p = f.properties, county = p.county;
  const share = new URL(location.pathname, location.origin);
  share.searchParams.set('county', county);
  share.searchParams.set('precinct', p.id);
  const copy = h('button', {type: 'button', class: 'btn ghost', text: 'Copy link', onclick: async () => {
    try { await navigator.clipboard.writeText(share.href); copy.textContent = 'Link copied'; }
    catch { copy.textContent = 'Copy from address bar'; }
  }});
  const rows = [['Donald Trump', p.trump, COLORS.r[1]], ['Kamala Harris', p.harris, COLORS.d[1]], ['Other votes combined', p.other, '#8a94a6']];
  const reps = h('section', {class: 'section'}, h('h3', {text: address ? 'Your representatives' : 'Representatives'}), h('p', {class: 'note', text: 'Finding districts…'}));
  $('panel').replaceChildren(
    ...head({eyebrow: county + ' County' + (p.municipality ? ' · ' + p.municipality : ''), title: p.name,
      back: {label: 'Back to ' + county + ' County', go: () => selectCounty(county)},
      lede: address ? 'Your address: ' + address.label : marginText(p.margin) + ' · U.S. president · November 5, 2024'}),
    ...(p.total ? voteBar(p.trump, p.harris, p.total) : []),
    h('table', {class: 'votes', 'aria-label': 'Presidential votes in ' + p.name},
      h('thead', {}, h('tr', {}, h('th', {scope: 'col', text: 'Candidate'}), h('th', {scope: 'col', text: 'Votes'}), h('th', {scope: 'col', text: 'Share'}))),
      h('tbody', {}, rows.map(([name, v, c]) => h('tr', {}, h('td', {}, h('span', {class: 'dot', style: 'background:' + c}), name), h('td', {text: v == null ? 'Unavailable' : fmt(v)}), h('td', {text: pct(v, p.total)}))),
        h('tr', {class: 'total'}, h('td', {text: 'Total votes reported'}), h('td', {text: fmt(p.total)}), h('td', {text: ''}))
      )),
    h('div', {class: 'actions'}, copy, h('a', {class: 'btn ghost', href: 'https://vt.ncsbe.gov/PPLkup/', text: 'Polling place'})),
    h('a', {class: 'link', href: 'data/' + slug(county) + '.json', text: 'Source: mapped county returns (JSON)'}),
    reps);
  const point = address ? address.point : interiorPoint(f.geometry);
  representatives(point).then(r => {
    if (token !== renderToken) return;
    reps.replaceChildren(h('h3', {text: address ? 'Your representatives' : 'Representatives'}), repList(r),
      h('p', {class: 'note', text: (address ? 'Matched at your address' : 'Matched at a point inside this precinct') + '. Serving members as of ' + MEMBERS_AS_OF + '. Simplified boundaries; near a line, confirm with the '},
        h('a', {href: 'https://www.ncleg.gov/FindYourLegislators', text: 'N.C. General Assembly district finder'}), '.'));
  }).catch(() => { if (token === renderToken) reps.replaceChildren(h('p', {class: 'note', text: 'District records could not load.'})); });
}
async function renderDistrictHome(kind) {
  const token = renderToken;
  const geo = await loadDistricts(kind);
  if (token !== renderToken) return;
  const all = geo.features.map(f => f.properties);
  const r = all.filter(p => p.party === 'Republican').length, d = all.filter(p => p.party === 'Democratic').length;
  const list = h('ul', {class: 'rows'});
  const draw = () => {
    const q = state.filter.trim().toLowerCase();
    list.replaceChildren(...all.filter(p => !q || String(p.district) === q || p.member.toLowerCase().includes(q)).map(p => h('li', {},
      h('button', {type: 'button', onclick: () => selectDistrict(kind, p.district)},
        h('strong', {text: 'District ' + p.district}), h('span', {class: 'num ' + partyClass(p.party), text: p.party ? p.party[0] : '—'}),
        h('small', {text: p.member || 'Member unavailable'})))));
  };
  draw();
  $('panel').replaceChildren(
    ...head({eyebrow: CHAMBERS[kind].label, title: 'Republicans hold ' + r + ' of ' + all.length + ' seats',
      lede: 'Democrats hold ' + d + '. Serving members as of ' + MEMBERS_AS_OF + '. Pick a district, or search your address to find yours.'}),
    h('div', {class: 'controls'}, h('input', {type: 'search', placeholder: 'District number or member', 'aria-label': 'Filter districts', value: state.filter, oninput: e => { state.filter = e.target.value; draw(); }})),
    list);
}
function renderDistrict(kind, f) {
  renderToken++;
  const p = f.properties;
  $('panel').replaceChildren(
    ...head({eyebrow: CHAMBERS[kind].label, title: CHAMBERS[kind].noun + ' ' + p.district,
      back: {label: 'All ' + CHAMBERS[kind].label + ' districts', go: () => { state.district = null; applySelection(); updateURL(); renderHome(); fit([NC_BOUNDS[0][0], NC_BOUNDS[0][1], NC_BOUNDS[1][0], NC_BOUNDS[1][1]]); }}}),
    h('ul', {class: 'reps'}, h('li', {}, h('span', {}, p.member ? h('a', {href: p.url, text: p.member}) : 'Member unavailable'),
      h('span', {class: 'party ' + partyClass(p.party), text: p.party || 'Unknown'}))),
    h('p', {class: 'note', text: 'Serving member as of ' + MEMBERS_AS_OF + '. Boundaries for the 2025–2026 session from the Census 2024 cartographic boundary files.'}),
    h('div', {class: 'actions'}, h('a', {class: 'btn ghost', href: 'https://www.ncleg.gov/FindYourLegislators', text: 'Confirm by address'})));
}

function legend() {
  const sw = (color, text) => h('span', {class: 'sw'}, h('i', {style: 'background:' + color}), text);
  const ramp = (colors, text) => h('span', {class: 'sw'}, h('span', {class: 'ramp'}, colors.map(c => h('i', {style: 'background:' + c}))), text);
  const l = state.layer, el = $('legend');
  if (l === 'results') {
    const zoomHint = map.getZoom() < PRECINCT_ZOOM - .2 && !state.county;
    el.replaceChildren(ramp(COLORS.r, 'Trump lead'), ramp(COLORS.d, 'Harris lead'), h('span', {class: 'hint', text: 'Darker: 10+ and 30+ pt margins'}),
      ...(zoomHint ? [h('span', {class: 'hint', text: 'Zoom in to see precincts'})] : []));
  } else if (l === 'chairs') {
    el.replaceChildren(ramp(CHAIR_SHADES, 'Share of seats empty: under 10% → 50%+'), sw('#455467', 'No public record'), h('span', {class: 'hint', text: 'Unknown seats not counted as empty'}));
  } else if (l === 'population') {
    el.replaceChildren(ramp(POP_SHADES, 'Population: under 50k → 500k+'), h('span', {class: 'hint', text: 'July 1, 2025 estimates'}));
  } else if (l === 'government') {
    el.replaceChildren(sw(PARTY_FILL.Republican, 'Republican'), sw(PARTY_FILL.Democratic, 'Democratic'), sw('#455467', 'Unverified'));
  } else {
    el.replaceChildren(sw(PARTY_FILL.Republican, 'Republican member'), sw(PARTY_FILL.Democratic, 'Democratic member'), h('span', {class: 'hint', text: CHAMBERS[l].label + ' · 2025–2026'}));
  }
}

/* ---------- Search ---------- */
const searchInput = $('search-input'), list = $('suggestions');
let suggestions = [], active = -1, geocoding;
const normalize = s => s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '')
  .replace(/\btwp\b/g, 'township').replace(/\bboro\b/g, 'borough').replace(/[^a-z0-9]+/g, ' ').trim();
let placeRows = null;
async function placeIndex() {
  if (placeRows) return placeRows;
  const src = await loadPlaces();
  const rows = counties.map(f => ({type: 'County', name: f.properties.county + ' County', county: f.properties.county, context: 'North Carolina'}));
  for (const [county, {places, precincts}] of Object.entries(src)) {
    places.forEach(name => rows.push({type: 'Municipality', name, county, context: county + ' County'}));
    precincts.forEach(([name, municipality, id]) => rows.push({type: 'Precinct', name, county, id, context: (municipality ? municipality + ' · ' : '') + county + ' County'}));
  }
  rows.forEach(r => { r.key = normalize(r.name); r.text = normalize(r.name + ' ' + r.context); });
  return placeRows = rows;
}
const looksLikeAddress = q => /^\d+[\w-]*\s+\S/.test(q) || /^\d{5}(-\d{4})?$/.test(q);
function closeList() { list.hidden = true; searchInput.setAttribute('aria-expanded', 'false'); searchInput.removeAttribute('aria-activedescendant'); active = -1; }
function highlight(i) {
  active = i;
  [...list.children].forEach((li, j) => li.setAttribute('aria-selected', String(j === i)));
  if (i >= 0) { searchInput.setAttribute('aria-activedescendant', list.children[i].id); list.children[i].scrollIntoView({block: 'nearest'}); }
}
async function suggest() {
  const raw = searchInput.value.trim(), q = normalize(raw);
  if (q.length < 2 || looksLikeAddress(raw)) { suggestions = []; closeList(); return; }
  let rows;
  try { rows = await placeIndex(); } catch { return; }
  if (normalize(searchInput.value) !== q) return;
  const words = q.split(' ');
  const rank = r => (r.key === q ? 0 : r.key.startsWith(q) ? 1 : r.key.includes(q) ? 2 : 3) + (r.type === 'County' ? 0 : r.type === 'Municipality' ? .1 : .2);
  suggestions = rows.filter(r => words.every(w => r.text.includes(w))).sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name)).slice(0, 8);
  list.replaceChildren(...suggestions.map((r, i) => h('li', {id: 'sg-' + i, role: 'option', 'aria-selected': 'false',
    onmousedown: e => { e.preventDefault(); choose(r); }}, r.name, h('small', {text: r.type + ' · ' + r.context}))));
  list.hidden = !suggestions.length;
  searchInput.setAttribute('aria-expanded', String(!!suggestions.length));
  active = -1;
}
async function choose(r) {
  closeList();
  searchInput.value = r.name;
  status('');
  if (r.type === 'County') return selectCounty(r.county);
  if (r.type === 'Precinct') return selectPrecinct(r.county, r.id);
  if (!COUNTY_LAYERS.includes(state.layer) || state.layer !== 'results') { state.layer = 'results'; setTabs(); applyLayerStyle(); legend(); }
  await selectCounty(r.county, {fly: false});
  state.muni = r.name;
  renderChips();
  if ($('muni-select')) $('muni-select').value = r.name;
  chooseMuni(r.name);
}
async function geocode(text) {
  geocoding?.abort();
  const controller = geocoding = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  status('Finding ' + text + '…');
  try {
    const query = new URLSearchParams({SingleLine: /\bNC\b|north carolina/i.test(text) ? text : text + ', NC', sourceCountry: 'USA',
      searchExtent: '-87.5,31.5,-72.5,38.8', outFields: 'Addr_type,RegionAbbr', outSR: '4326', maxLocations: '6', f: 'json'});
    const r = await fetch('https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?' + query,
      {signal: controller.signal, credentials: 'omit', referrerPolicy: 'no-referrer'});
    if (!r.ok) throw Error('geocode');
    const result = await r.json();
    if (controller !== geocoding) return;
    const found = (result.candidates || []).filter(c => c.attributes?.RegionAbbr === 'NC' && Number.isFinite(c.location?.x) && Number.isFinite(c.location?.y))
      .sort((a, b) => b.score - a.score);
    const best = found[0];
    if (!best || best.score < 90) { status('No confident North Carolina match. Include the city and ZIP code.'); return; }
    const street = ['Subaddress', 'PointAddress', 'StreetAddress'].includes(best.attributes.Addr_type);
    const point = [best.location.x, best.location.y];
    if (!street) {
      clearMarker();
      marker = new maplibregl.Marker({element: h('div', {class: 'marker'})}).setLngLat(point).addTo(map);
      map.flyTo({center: point, zoom: Math.max(map.getZoom(), 11.5), padding: padding()});
      if (state.layer !== 'results') await setLayer('results');
      status('Showing ' + best.address + '. Enter a street address to find your precinct and representatives.');
      return;
    }
    if (best.score < 98 || found.some(c => c.score === best.score && c !== best && (Math.abs(c.location.x - best.location.x) > .00005 || Math.abs(c.location.y - best.location.y) > .00005))) {
      status('More than one address matched. Add the city and ZIP code.');
      return;
    }
    const candidates = counties.filter(f => inBox(point, f.bbox)).map(f => f.properties.county);
    const hits = (await Promise.all(candidates.map(async c => (await loadCounty(c)).features
      .filter(f => inGeometry(point, f.geometry)).map(f => f.properties)))).flat();
    if (controller !== geocoding) return;
    clearMarker();
    marker = new maplibregl.Marker({element: h('div', {class: 'marker'})}).setLngLat(point).addTo(map);
    if (hits.length !== 1) {
      map.flyTo({center: point, zoom: 13, padding: padding()});
      status('Matched ' + best.address + ', but no single mapped precinct contains it.');
      return;
    }
    await selectPrecinct(hits[0].county, hits[0].id, {fly: false, address: {label: best.address, point}});
    map.flyTo({center: point, zoom: Math.max(map.getZoom(), 13.5), padding: padding()});
    status(best.attributes.Addr_type === 'StreetAddress' ? 'Position estimated along the street.' : '');
  } catch (e) {
    if (controller === geocoding) status(e.name === 'AbortError' ? 'Address lookup timed out. Try again.' : 'Address lookup is unavailable. Pick your county on the map.');
  } finally { clearTimeout(timer); }
}
function wireSearch() {
  searchInput.addEventListener('focus', () => { placeIndex().catch(() => {}); });
  searchInput.addEventListener('input', suggest);
  searchInput.addEventListener('blur', () => setTimeout(closeList, 120));
  searchInput.addEventListener('keydown', e => {
    if (list.hidden) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); highlight(Math.min(active + 1, suggestions.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); highlight(Math.max(active - 1, -1)); }
    else if (e.key === 'Escape') closeList();
  });
  $('search').addEventListener('submit', async e => {
    e.preventDefault();
    const text = searchInput.value.trim();
    if (!text) return;
    if (active >= 0 && suggestions[active]) return choose(suggestions[active]);
    if (looksLikeAddress(text)) return geocode(text);
    if (!suggestions.length) await suggest();
    if (suggestions.length) return choose(suggestions[0]);
    geocode(text);
  });
}

/* ---------- Start ---------- */
async function start() {
  const [geo, meta, chairs] = await Promise.all([json('counties.geojson'), loadMeta(), json('committee/summary.json').catch(() => null)]);
  if (chairs) committee = chairs;
  countyInfo = meta;
  counties = geo.features;
  for (const f of counties) {
    const p = f.properties, c = meta.counties[p.county] || {};
    p.margin = (p.trump - p.harris) / p.total;
    p.population = c.population;
    p.party_control = c.party_control || '';
    p.fill_results = colorFor(p.margin);
    p.fill_population = POP_SHADES[POP_STEPS.filter(n => c.population >= n).length];
    p.fill_government = PARTY_FILL[c.party_control] || '#455467';
    const ch = committee.counties[p.county];
    p.chairs_empty = emptyOf(ch);
    p.fill_chairs = !ch || !knownOf(ch) ? '#455467' : CHAIR_SHADES[CHAIR_STEPS.filter(n => emptyOf(ch) / ch.seats >= n).length];
    f.bbox = bboxOf(f.geometry);
    f.labelPoint = interiorPoint(f.geometry);
    countyByName.set(p.county, f);
  }
  map = new maplibregl.Map({
    container: 'map', style: STYLE, bounds: NC_BOUNDS, fitBoundsOptions: {padding: padding()},
    minZoom: 5.5, maxZoom: 16, maxBounds: [[-87.5, 31.5], [-72.5, 38.8]], attributionControl: false,
    dragRotate: false, pitchWithRotate: false, touchPitch: false
  });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.AttributionControl({compact: true, customAttribution: 'Results: The New York Times · Boundaries: U.S. Census Bureau'}), 'bottom-right');
  map.addControl(new maplibregl.NavigationControl({showCompass: false}), 'bottom-right');
  map.addControl(new HomeControl(), 'bottom-right');
  popup = new maplibregl.Popup({closeButton: false, closeOnClick: false, offset: 14, maxWidth: '280px'});
  if (!map.isStyleLoaded()) await new Promise(resolve => map.once('style.load', resolve));
  addLayers();
  map.on('mousemove', onMove);
  map.on('mouseout', () => { setHover(null); popup.remove(); });
  map.on('click', onClick);
  map.on('moveend', () => { loadVisibleCounties(); if (state.layer === 'results') legend(); });
  document.querySelectorAll('[data-layer]').forEach(b => b.onclick = () => { state.filter = ''; setLayer(b.dataset.layer); });
  wireSearch();

  const q = new URLSearchParams(location.search);
  const layer = q.get('layer');
  await setLayer(Object.hasOwn(CHAMBERS, layer) || COUNTY_LAYERS.includes(layer) ? layer : 'results');
  if (CHAMBERS[state.layer] && q.has('district')) selectDistrict(state.layer, q.get('district'));
  else if (q.has('county')) {
    const county = q.get('county');
    if (!countyByName.has(county)) status('Unknown county in this link. Pick a county to continue.');
    else if (q.has('precinct') && state.layer === 'results') selectPrecinct(county, q.get('precinct'));
    else selectCounty(county);
  }
}
start().catch(() => {
  $('panel').replaceChildren(h('p', {class: 'lede', text: 'The map could not load. Check your connection and reload to try again.'}));
});
})();
