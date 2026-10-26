// Interactive figure: every animal's change in total, evoked and induced power, linked to its own waveforms.
const NS = 'http://www.w3.org/2000/svg';
const INTENSITY = ['#D3A15F', '#B8582F', '#6E1F2B'];
const COMPONENTS = [['total', 'Total', '#22211E'], ['evoked', 'Evoked', '#1F6F78'], ['induced', 'Induced', '#B58A55']];
const STOPS = [[0, '#2E6F86'], [0.25, '#9DBDC6'], [0.5, '#F4F1EA'], [2 / 3, '#E2B48F'], [5 / 6, '#B8582F'], [1, '#6E1F2B']];
const STRIP = { top: 64, bottom: 404, columns: [160, 300, 440] };
const RATIO = [0.75, 3];
const WAVE = { left: 618, right: 950, top: 64, bottom: 214 };
const MAP = { left: 618, right: 818, top: 288, bottom: 404 };
const T0 = -150, T1 = 550;

const el = (name, attrs = {}, parent) => {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.append(node);
  return node;
};
const text = (parent, x, y, content, attrs = {}) => { const node = el('text', { x, y, ...attrs }, parent); node.textContent = content; return node; };
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
function colour(u) {
  u = Math.max(0, Math.min(1, u));
  let i = 0;
  while (i < STOPS.length - 2 && u > STOPS[i + 1][0]) i++;
  const [a, ca] = STOPS[i], [b, cb] = STOPS[i + 1], f = (u - a) / (b - a);
  const [x, y] = [hex(ca), hex(cb)];
  return `rgb(${x.map((v, k) => Math.round(v + f * (y[k] - v))).join(',')})`;
}
const times = r => `${r.toFixed(2)}×`;

const data = await (await fetch('data/page.json')).json();
const svg = document.getElementById('explorer');
const readout = document.getElementById('readout');
const state = { region: 0, contrast: 1, pinned: null, hover: null };
const animalName = a => `Animal ${Number(data.animals[a])}`;

const yRatio = r => STRIP.bottom - Math.log(Math.min(Math.max(r, RATIO[0]), RATIO[1]) / RATIO[0]) / Math.log(RATIO[1] / RATIO[0]) * (STRIP.bottom - STRIP.top);
const xWave = t => WAVE.left + (t - T0) / (T1 - T0) * (WAVE.right - WAVE.left);
const xMap = t => MAP.left + t / 400 * (MAP.right - MAP.left);
const yFreq = f => MAP.bottom - Math.log(f / 20) / Math.log(10) * (MAP.bottom - MAP.top);
// Spread the animals sideways within a column by rank, so equal values do not hide each other.
const spread = values => {
  const order = values.map((v, i) => [v, i]).filter(([v]) => v !== null).sort((a, b) => a[0] - b[0]);
  const offsets = new Array(values.length).fill(0);
  order.forEach(([, i], k) => { offsets[i] = ((k % 5) - 2) * 9 + (Math.floor(k / 5) % 2 ? 4 : -4); });
  return offsets;
};

// Static frame.
text(svg, 80, 22, 'Change in each animal: power ratio, higher ÷ lower intensity', { class: 'head' });
STRIP.columns.forEach((x, k) => text(svg, x, 50, COMPONENTS[k][1], { 'text-anchor': 'middle', class: 'column', style: `fill:${COMPONENTS[k][2]}` }));
el('line', { x1: 80, x2: 520, y1: yRatio(1), y2: yRatio(1), class: 'unity' }, svg);
el('path', { d: `M80,${STRIP.top - 4}V${STRIP.bottom}`, class: 'axis' }, svg);
[0.8, 1, 1.5, 2, 3].forEach(v => text(svg, 74, yRatio(v) + 4, v, { 'text-anchor': 'end' }));
const strips = el('g', {}, svg);
const counts = el('g', {}, svg);
const waveHead = text(svg, WAVE.left, 22, '', { class: 'head' });
const waveLegend = el('g', {}, svg);
const waves = el('g', {}, svg);
const mapHead = text(svg, MAP.left, 274, '', { class: 'head' });
const maps = el('g', {}, svg);
el('path', { d: `M${MAP.left},${MAP.top}V${MAP.bottom}H${MAP.right}`, class: 'axis' }, svg);
[20, 50, 100, 200].forEach(f => text(svg, MAP.left - 6, yFreq(f) + 4, f === 200 ? '200 Hz' : f, { 'text-anchor': 'end' }));
[0, 200, 400].forEach(v => text(svg, xMap(v), MAP.bottom + 16, v, { 'text-anchor': 'middle' }));
text(svg, (MAP.left + MAP.right) / 2, MAP.bottom + 34, 'Time (ms)', { 'text-anchor': 'middle' });
const legendHeight = (MAP.bottom - MAP.top) / 40;
for (let i = 0; i < 40; i++) el('rect', { x: 846, y: MAP.bottom - (i + 1) * legendHeight, width: 8, height: legendHeight + 0.5, fill: colour(i / 39) }, svg);
text(svg, 860, MAP.top + 8, `+${data.map.limit}`);
text(svg, 860, (MAP.top + MAP.bottom) / 2 + 4, '0');
text(svg, 860, MAP.bottom, `−${data.map.limit}`);
text(svg, 846, MAP.bottom + 16, 'log10 power');

function drawStrips() {
  strips.replaceChildren(); counts.replaceChildren();
  const key = data.contrasts[state.contrast][0], region = data.regions[state.region];
  const change = data.change[key][region], model = data.model[key][region];
  const ratios = COMPONENTS.map(([k]) => change[k].map(v => v === null ? null : 10 ** v));
  const offsets = ratios.map(spread);
  const lines = el('g', {}, strips), dots = el('g', {}, strips), hits = el('g', {}, strips);
  data.animals.forEach((_, a) => {
    if (ratios[0][a] === null) return;
    const points = STRIP.columns.map((x, k) => [x + offsets[k][a], yRatio(ratios[k][a])]);
    el('polyline', { points: points.map(p => p.join(',')).join(' '), class: 'animal-line', 'data-animal': a }, lines);
    points.forEach(([x, y], k) => {
      if (ratios[k][a] > RATIO[1]) el('path', { d: `M${x - 4},${y + 3}L${x},${y - 4}L${x + 4},${y + 3}Z`, fill: COMPONENTS[k][2], class: 'animal-dot', 'data-animal': a }, dots);
      else el('circle', { cx: x, cy: y, r: 3.4, fill: COMPONENTS[k][2], class: 'animal-dot', 'data-animal': a }, dots);
      el('circle', { cx: x, cy: y, r: 8, class: 'hit', 'data-animal': a }, hits);
    });
    el('polyline', { points: points.map(p => p.join(',')).join(' '), class: 'hit-line', 'data-animal': a }, hits);
  });
  COMPONENTS.forEach(([k, label, hue], c) => {
    const [ratio, low, high, p] = model[k], x = STRIP.columns[c] + 52;
    el('line', { x1: x, x2: x, y1: yRatio(low), y2: yRatio(high), stroke: hue, 'stroke-width': 2 }, strips);
    el('rect', { x: x - 5, y: yRatio(ratio) - 5, width: 10, height: 10, fill: p < 0.05 ? hue : '#F4F1EA', stroke: hue, 'stroke-width': 1.6 }, strips)
      .append(Object.assign(document.createElementNS(NS, 'title'), { textContent: `${label}: model estimate ${times(ratio)} (95% CI ${times(low)}–${times(high)}), Holm P = ${p}` }));
    const valid = ratios[c].filter(v => v !== null);
    text(counts, STRIP.columns[c], STRIP.bottom + 22, `${valid.filter(v => v > 1).length} of ${valid.length} higher`, { 'text-anchor': 'middle' });
  });
}

function drawMap() {
  maps.replaceChildren();
  const { f, fEdges, tEdges, effect, mask, limit } = data.map;
  const values = effect[state.contrast][state.region], corrected = mask[state.contrast][state.region];
  const yEdge = fEdges.map(v => yFreq(Math.min(200, Math.max(20, v))));
  for (let i = 0; i < f.length; i++) for (let j = 0; j < tEdges.length - 1; j++) {
    el('rect', { x: xMap(tEdges[j]).toFixed(2), y: yEdge[i + 1].toFixed(2), width: (xMap(tEdges[j + 1]) - xMap(tEdges[j]) + 0.4).toFixed(2),
      height: (yEdge[i] - yEdge[i + 1] + 0.4).toFixed(2), fill: colour((values[i][j] / limit + 1) / 2) }, maps);
  }
  let d = '';
  for (let i = 0; i < f.length; i++) for (let j = 0; j < tEdges.length - 1; j++) {
    if (!corrected[i][j]) continue;
    const [x0, x1, y0, y1] = [xMap(tEdges[j]), xMap(tEdges[j + 1]), yEdge[i], yEdge[i + 1]];
    if (j === 0 || !corrected[i][j - 1]) d += `M${x0},${y0}V${y1}`;
    if (j === tEdges.length - 2 || !corrected[i][j + 1]) d += `M${x1},${y0}V${y1}`;
    if (i === 0 || !corrected[i - 1][j]) d += `M${x0},${y0}H${x1}`;
    if (i === f.length - 1 || !corrected[i + 1][j]) d += `M${x0},${y1}H${x1}`;
  }
  if (d) el('path', { d, class: 'outline' }, maps);
  mapHead.textContent = `Total power, mean of ${data.n[state.region]} animals` + (d ? '; outline: corrected' : '; no corrected region');
}

function drawWaves() {
  waves.replaceChildren(); waveLegend.replaceChildren();
  const [, , high, low] = data.contrasts[state.contrast];
  const a = state.hover ?? state.pinned, region = data.regions[state.region], t = data.trace.t;
  const own = a === null ? null : data.trace.animal[a][state.region];
  const mean = data.trace.mean[state.region], se = data.trace.se[state.region];
  const pair = [low, high];
  const lines = own ? pair.map(c => own[c]) : pair.map(c => mean[c]);
  const bands = own ? lines : pair.flatMap(c => [mean[c].map((v, i) => v - se[c][i]), mean[c].map((v, i) => v + se[c][i])]);
  let lo = Math.min(...bands.flat()), hi = Math.max(...bands.flat());
  const pad = 0.06 * (hi - lo); lo -= pad; hi += pad;
  const y = v => WAVE.bottom - (v - lo) / (hi - lo) * (WAVE.bottom - WAVE.top);
  const path = values => 'M' + values.map((v, i) => `${xWave(t[i]).toFixed(1)},${y(v).toFixed(1)}`).join('L');
  el('rect', { x: xWave(T0), y: WAVE.top, width: xWave(0) - xWave(T0), height: WAVE.bottom - WAVE.top, fill: '#EAE5DA' }, waves);
  if (lo < 0 && hi > 0) el('line', { x1: WAVE.left, x2: WAVE.right, y1: y(0), y2: y(0), class: 'zero' }, waves);
  waveHead.textContent = own ? `${animalName(a)}, ${region}` : `Mean ± SE of ${data.n[state.region]} animals, ${region}`;
  pair.forEach((c, i) => {
    if (!own) {
      const upper = mean[c].map((v, k) => `${xWave(t[k]).toFixed(1)},${y(v + se[c][k]).toFixed(1)}`);
      const lower = mean[c].map((v, k) => `${xWave(t[k]).toFixed(1)},${y(v - se[c][k]).toFixed(1)}`).reverse();
      el('path', { d: `M${upper.join('L')}L${lower.join('L')}Z`, fill: INTENSITY[c], opacity: 0.2 }, waves);
    }
    el('path', { d: path(lines[i]), stroke: INTENSITY[c], 'stroke-width': 1.5, fill: 'none' }, waves);
  });
  el('path', { d: `M${WAVE.left},${WAVE.top}V${WAVE.bottom}H${WAVE.right}`, class: 'axis' }, waves);
  const spacing = [5, 10, 20, 25, 50, 100, 200, 500].find(s => (hi - lo) / s <= 4);
  for (let v = Math.ceil(lo / spacing) * spacing; v <= hi; v += spacing) text(waves, WAVE.left - 6, y(v) + 4, v, { 'text-anchor': 'end' });
  text(waves, WAVE.left - 6, WAVE.top - 14, 'µV', { 'text-anchor': 'end' });
  [-150, 0, 200, 400].forEach(v => text(waves, xWave(v), WAVE.bottom + 16, v, { 'text-anchor': 'middle' }));
  text(waves, (WAVE.left + WAVE.right) / 2, WAVE.bottom + 32, 'Time from stimulation (ms)', { 'text-anchor': 'middle' });
  pair.forEach((c, i) => {
    const x = WAVE.right - 140 + i * 74;
    el('line', { x1: x, x2: x + 16, y1: 39, y2: 39, stroke: INTENSITY[c], 'stroke-width': 2.5 }, waveLegend);
    text(waveLegend, x + 21, 43, data.conditions[c].replace('x', '×'));
  });
}

function highlight() {
  const a = state.hover ?? state.pinned;
  svg.classList.toggle('focused', a !== null);
  strips.querySelectorAll('[data-animal]').forEach(node => node.classList.toggle('active', Number(node.dataset.animal) === a));
  strips.querySelectorAll('.animal-line.active, .animal-dot.active').forEach(node => node.parentNode.append(node));
}

function describe() {
  const key = data.contrasts[state.contrast][0], region = data.regions[state.region], a = state.hover ?? state.pinned;
  const label = data.contrasts[state.contrast][1];
  if (a === null) {
    const model = data.model[key][region];
    readout.textContent = `${region}, ${label}, model estimates: ` + COMPONENTS.map(([k, name]) => `${name.toLowerCase()} ${times(model[k][0])}`).join(', ');
    return;
  }
  const change = data.change[key][region];
  readout.textContent = change.total[a] === null ? `${animalName(a)}: no ${region} recording after quality control`
    : `${animalName(a)}, ${region}, ${label}: ` + COMPONENTS.map(([k, name]) => `${name.toLowerCase()} ${times(10 ** change[k][a])}`).join(', ');
}

function update(redraw) {
  const total = data.change[data.contrasts[state.contrast][0]][data.regions[state.region]].total;
  if (state.pinned !== null && total[state.pinned] === null) state.pinned = null;
  if (redraw) { drawStrips(); drawMap(); }
  highlight(); drawWaves(); describe();
  document.querySelectorAll('#regions button').forEach((b, i) => b.setAttribute('aria-pressed', String(i === state.region)));
  document.querySelectorAll('#contrasts button').forEach((b, i) => b.setAttribute('aria-pressed', String(i === state.contrast)));
}

svg.addEventListener('pointerover', event => {
  const a = event.target.dataset?.animal;
  if (a === undefined || Number(a) === state.hover) return;
  state.hover = Number(a); update(false);
});
svg.addEventListener('pointerout', event => {
  const a = event.target.dataset?.animal;
  if (a === undefined || event.relatedTarget?.dataset?.animal === a) return;
  state.hover = null; update(false);
});
svg.addEventListener('click', event => {
  const a = event.target.dataset?.animal;
  state.pinned = a === undefined || Number(a) === state.pinned ? null : Number(a);
  state.hover = null; update(false);
});

function step(direction) {
  const total = data.change[data.contrasts[state.contrast][0]][data.regions[state.region]].total;
  const valid = data.animals.map((_, a) => a).filter(a => total[a] !== null);
  const at = valid.indexOf(state.pinned);
  state.pinned = at < 0 ? valid[direction > 0 ? 0 : valid.length - 1] : valid[(at + direction + valid.length) % valid.length];
  state.hover = null; update(false);
}
document.getElementById('previous').addEventListener('click', () => step(-1));
document.getElementById('next').addEventListener('click', () => step(1));
document.getElementById('all').addEventListener('click', () => { state.pinned = null; state.hover = null; update(false); });

const tabs = (id, labels, keyName) => {
  const group = document.getElementById(id);
  labels.forEach((label, i) => {
    const button = Object.assign(document.createElement('button'), { type: 'button', textContent: label });
    button.addEventListener('click', () => { state[keyName] = i; state.hover = null; update(true); });
    group.append(button);
  });
};
tabs('regions', data.regions, 'region');
tabs('contrasts', data.contrasts.map(c => c[1]), 'contrast');
update(true);

const FIGURES = [
  ['fig3_waveforms', 'Figure 3', 'Stimulation-locked waveforms'],
  ['fig4_power_ratios', 'Figure 4', 'Total, evoked and induced power ratios'],
  ['fig5_corrected_maps', 'Figure 5', 'Corrected total-power maps'],
  ['fig6_aperiodic', 'Figure 6', 'Aperiodic exponent, offset and adjusted power'],
  ['figS1_fraction_common_scale', 'Figure S1', 'Phase-locked fraction of total power'],
  ['figS2_fraction_region_scales', 'Figure S2', 'Phase-locked fraction, region scales'],
  ['figS3_all_maps', 'Figure S3', 'All nine corrected maps'],
  ['figS4_individual_waveforms', 'Figure S4', 'Waveforms of every animal'],
  ['figS5_evoked_fraction', 'Figure S5', 'Evoked-fraction contrasts'],
  ['figS6_spectra', 'Figure S6', 'Static spectra and aperiodic fits'],
  ['figS7_correlations', 'Figure S7', 'Correlations between animal-level responses'],
];
const gallery = document.getElementById('gallery');
for (const [stem, number, title] of FIGURES) {
  const link = Object.assign(document.createElement('a'), { href: `figures/${stem}.pdf` });
  link.innerHTML = `<img src="figures/${stem}.png" alt="${number}: ${title}" loading="lazy"><span><b>${number}.</b> ${title}</span>`;
  gallery.append(link);
}
