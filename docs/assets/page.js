// Two interactive versions of poster figures: every animal behind Fig. 3, and the animals behind each cell of the
// correlation matrix.
const NS = 'http://www.w3.org/2000/svg';
const INTENSITY = ['#D3A15F', '#B8582F', '#6E1F2B'];
const COMPONENTS = [['total', 'Total', '#22211E'], ['evoked', 'Evoked', '#1F6F78'], ['induced', 'Induced', '#B58A55']];
const CORR_STOPS = [[0, '#1F5F6B'], [0.25, '#8DB5BA'], [0.5, '#F4F1EA'], [0.75, '#D9A27E'], [1, '#8E2F2A']];
const RATIO = [0.75, 3];
const TOP = 64, BOTTOM = 400;
const WAVE = { left: 618, right: 950, top: 64, bottom: 400 };
const T0 = -150, T1 = 550;
// Each figure is two SVGs in one coordinate space, side by side on wide screens and stacked on phones.
const narrow = matchMedia('(max-width: 719px)');
const stripLayout = () => narrow.matches
  ? { left: 70, right: 400, columns: [120, 235, 350], square: 42, view: '0 0 420 456' }
  : { left: 80, right: 520, columns: [160, 300, 440], square: 52, view: '0 0 560 456' };

const el = (name, attrs = {}, parent) => {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.append(node);
  return node;
};
const text = (parent, x, y, content, attrs = {}) => { const node = el('text', { x, y, ...attrs }, parent); node.textContent = content; return node; };
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
function colour(u, stops) {
  u = Math.max(0, Math.min(1, u));
  let i = 0;
  while (i < stops.length - 2 && u > stops[i + 1][0]) i++;
  const [a, ca] = stops[i], [b, cb] = stops[i + 1], f = (u - a) / (b - a);
  const [x, y] = [hex(ca), hex(cb)];
  return `rgb(${x.map((v, k) => Math.round(v + f * (y[k] - v))).join(',')})`;
}
const times = r => `${r.toFixed(2)}×`;
const minus = v => String(v).replace('-', '−');
const niceStep = span => [0.001, 0.002, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5].find(s => span / s <= 5) ?? 10;

const data = await (await fetch('data/page.json')).json();

// ---------------------------------------------------------------- each animal behind Fig. 3
const left = document.getElementById('strip-plot');
const right = document.getElementById('trace-plot');
const readout = document.getElementById('readout');
const state = { region: 0, contrast: 1, pinned: null, hover: null };
const groups = {};
let STRIP = stripLayout();
const animalName = a => `Animal ${Number(data.animals[a])}`;

const yRatio = r => BOTTOM - Math.log(Math.min(Math.max(r, RATIO[0]), RATIO[1]) / RATIO[0]) / Math.log(RATIO[1] / RATIO[0]) * (BOTTOM - TOP);
const xWave = t => WAVE.left + (t - T0) / (T1 - T0) * (WAVE.right - WAVE.left);
// Spread the animals sideways within a column by rank, so equal values do not hide each other.
const spread = values => {
  const order = values.map((v, i) => [v, i]).filter(([v]) => v !== null).sort((a, b) => a[0] - b[0]);
  const offsets = new Array(values.length).fill(0);
  order.forEach(([, i], k) => { offsets[i] = ((k % 5) - 2) * 9 + (Math.floor(k / 5) % 2 ? 4 : -4); });
  return offsets;
};

function build() {
  STRIP = stripLayout();
  left.setAttribute('viewBox', STRIP.view);
  left.replaceChildren();
  right.replaceChildren();
  text(left, STRIP.left, 22, 'Each animal’s power ratio, higher ÷ lower intensity', { class: 'head' });
  STRIP.columns.forEach((x, k) => text(left, x, 50, COMPONENTS[k][1], { 'text-anchor': 'middle', class: 'column', style: `fill:${COMPONENTS[k][2]}` }));
  el('line', { x1: STRIP.left, x2: STRIP.right, y1: yRatio(1), y2: yRatio(1), class: 'unity' }, left);
  el('path', { d: `M${STRIP.left},${TOP - 4}V${BOTTOM}`, class: 'axis' }, left);
  [0.8, 1, 1.5, 2, 3].forEach(v => text(left, STRIP.left - 6, yRatio(v) + 4, v, { 'text-anchor': 'end' }));
  groups.strips = el('g', {}, left);
  groups.counts = el('g', {}, left);
  groups.waveHead = text(right, WAVE.left, 22, '', { class: 'head' });
  groups.waveLegend = el('g', {}, right);
  groups.waves = el('g', {}, right);
  update(true);
}

function drawStrips() {
  groups.strips.replaceChildren();
  groups.counts.replaceChildren();
  const key = data.contrasts[state.contrast][0], region = data.regions[state.region];
  const change = data.change[key][region], model = data.model[key][region];
  const ratios = COMPONENTS.map(([k]) => change[k].map(v => v === null ? null : 10 ** v));
  const offsets = ratios.map(spread);
  const lines = el('g', {}, groups.strips), dots = el('g', {}, groups.strips), hits = el('g', {}, groups.strips);
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
    const [ratio, low, high, p] = model[k], x = STRIP.columns[c] + STRIP.square;
    el('line', { x1: x, x2: x, y1: yRatio(low), y2: yRatio(high), stroke: hue, 'stroke-width': 2 }, groups.strips);
    el('rect', { x: x - 5, y: yRatio(ratio) - 5, width: 10, height: 10, fill: p < 0.05 ? hue : '#F4F1EA', stroke: hue, 'stroke-width': 1.6 }, groups.strips)
      .append(Object.assign(document.createElementNS(NS, 'title'), { textContent: `${label}: model estimate ${times(ratio)} (95% CI ${times(low)}–${times(high)}), Holm P = ${p}` }));
    const valid = ratios[c].filter(v => v !== null);
    text(groups.counts, STRIP.columns[c], BOTTOM + 22, `${valid.filter(v => v > 1).length} of ${valid.length} higher`, { 'text-anchor': 'middle' });
  });
}

function drawWaves() {
  groups.waves.replaceChildren();
  groups.waveLegend.replaceChildren();
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
  el('rect', { x: xWave(T0), y: WAVE.top, width: xWave(0) - xWave(T0), height: WAVE.bottom - WAVE.top, fill: '#EAE5DA' }, groups.waves);
  if (lo < 0 && hi > 0) el('line', { x1: WAVE.left, x2: WAVE.right, y1: y(0), y2: y(0), class: 'zero' }, groups.waves);
  groups.waveHead.textContent = own ? `${animalName(a)}, ${region}` : `Mean ± SE of ${data.n[state.region]} animals, ${region}`;
  pair.forEach((c, i) => {
    if (!own) {
      const upper = mean[c].map((v, k) => `${xWave(t[k]).toFixed(1)},${y(v + se[c][k]).toFixed(1)}`);
      const lower = mean[c].map((v, k) => `${xWave(t[k]).toFixed(1)},${y(v - se[c][k]).toFixed(1)}`).reverse();
      el('path', { d: `M${upper.join('L')}L${lower.join('L')}Z`, fill: INTENSITY[c], opacity: 0.2 }, groups.waves);
    }
    el('path', { d: path(lines[i]), stroke: INTENSITY[c], 'stroke-width': 1.5, fill: 'none' }, groups.waves);
  });
  el('path', { d: `M${WAVE.left},${WAVE.top}V${WAVE.bottom}H${WAVE.right}`, class: 'axis' }, groups.waves);
  const spacing = [5, 10, 20, 25, 50, 100, 200, 500].find(s => (hi - lo) / s <= 5);
  for (let v = Math.ceil(lo / spacing) * spacing; v <= hi; v += spacing) text(groups.waves, WAVE.left - 6, y(v) + 4, minus(v), { 'text-anchor': 'end' });
  text(groups.waves, WAVE.left - 6, WAVE.top - 14, 'µV', { 'text-anchor': 'end' });
  [-150, 0, 200, 400].forEach(v => text(groups.waves, xWave(v), WAVE.bottom + 16, minus(v), { 'text-anchor': 'middle' }));
  text(groups.waves, (WAVE.left + WAVE.right) / 2, WAVE.bottom + 34, 'Time from stimulation (ms)', { 'text-anchor': 'middle' });
  pair.forEach((c, i) => {
    const x = WAVE.right - 140 + i * 74;
    el('line', { x1: x, x2: x + 16, y1: 39, y2: 39, stroke: INTENSITY[c], 'stroke-width': 2.5 }, groups.waveLegend);
    text(groups.waveLegend, x + 21, 43, data.conditions[c].replace('x', '×'));
  });
}

function highlight() {
  const a = state.hover ?? state.pinned;
  left.classList.toggle('focused', a !== null);
  groups.strips.querySelectorAll('[data-animal]').forEach(node => node.classList.toggle('active', Number(node.dataset.animal) === a));
  groups.strips.querySelectorAll('.animal-line.active, .animal-dot.active').forEach(node => node.parentNode.append(node));
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
  readout.textContent = `${animalName(a)}, ${region}, ${label}: ` + COMPONENTS.map(([k, name]) => `${name.toLowerCase()} ${times(10 ** change[k][a])}`).join(', ');
}

function update(redraw) {
  const total = data.change[data.contrasts[state.contrast][0]][data.regions[state.region]].total;
  if (state.pinned !== null && total[state.pinned] === null) state.pinned = null;
  if (redraw) drawStrips();
  highlight(); drawWaves(); describe();
  document.querySelectorAll('#regions button').forEach((b, i) => b.setAttribute('aria-pressed', String(i === state.region)));
  document.querySelectorAll('#contrasts button').forEach((b, i) => b.setAttribute('aria-pressed', String(i === state.contrast)));
}

left.addEventListener('pointerover', event => {
  const a = event.target.dataset?.animal;
  if (a === undefined || Number(a) === state.hover) return;
  state.hover = Number(a); update(false);
});
left.addEventListener('pointerout', event => {
  const a = event.target.dataset?.animal;
  if (a === undefined || event.relatedTarget?.dataset?.animal === a) return;
  state.hover = null; update(false);
});
left.addEventListener('click', event => {
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

const tabs = (id, labels, onPick) => {
  const group = document.getElementById(id);
  labels.forEach((label, i) => {
    const button = Object.assign(document.createElement('button'), { type: 'button', textContent: label });
    button.addEventListener('click', () => onPick(i));
    group.append(button);
  });
};
tabs('regions', data.regions, i => { state.region = i; state.hover = null; update(true); });
tabs('contrasts', data.contrasts.map(c => c[1]), i => { state.contrast = i; state.hover = null; update(true); });
build();
narrow.addEventListener('change', build);

// ---------------------------------------------------------------- correlation matrix with the animals behind each cell
const corr = data.correlation;
const matrix = document.getElementById('matrix-plot');
const scatter = document.getElementById('scatter-plot');
const N = corr.measures.length * data.regions.length;
const CELL = 17, GAP = 5, X0 = 172, Y0 = 34;
const cellPos = i => i * CELL + Math.floor(i / corr.measures.length) * GAP;
const measureName = i => `${data.regions[Math.floor(i / corr.measures.length)]} ${corr.measures[i % corr.measures.length][0]}`;
const cstate = { contrast: 1, pinned: [2, 0], hover: null };

function buildMatrix() {
  matrix.replaceChildren();
  const span = cellPos(N - 1) + CELL;
  for (let i = 0; i < N; i++) {
    text(matrix, X0 - 6, Y0 + cellPos(i) + CELL / 2 + 4, corr.measures[i % corr.measures.length][0], { 'text-anchor': 'end' });
    const x = X0 + cellPos(i) + CELL / 2 + 4, y = Y0 + span + 8;
    text(matrix, x, y, corr.measures[i % corr.measures.length][0], { 'text-anchor': 'end', transform: `rotate(-90 ${x} ${y})` });
  }
  data.regions.forEach((region, g) => {
    const middle = cellPos(g * corr.measures.length) + (corr.measures.length * CELL) / 2;
    text(matrix, 14, Y0 + middle + 5, region, { class: 'region' });
    text(matrix, X0 + middle, Y0 + span + 152, region, { class: 'region', 'text-anchor': 'middle' });
  });
  const key = el('g', {}, matrix), kx = X0 + span - 170, ky = Y0 + 6;
  for (let i = 0; i < 60; i++) el('rect', { x: kx + i * 2.5, y: ky + 18, width: 2.8, height: 9, fill: colour(i / 59, CORR_STOPS) }, key);
  text(key, kx, ky + 8, 'Spearman ρ across animals', { class: 'head' });
  [[-1, '−1'], [0, '0'], [1, '1']].forEach(([v, label]) => text(key, kx + (v + 1) / 2 * 150, ky + 42, label, { 'text-anchor': 'middle' }));
  matrix.cells = el('g', {}, matrix);
  matrix.marker = el('rect', { width: CELL, height: CELL, class: 'cell-marker' }, matrix);
  drawMatrix();
}

function drawMatrix() {
  matrix.cells.replaceChildren();
  const rho = corr.rho[cstate.contrast];
  for (let r = 0; r < N; r++) for (let c = 0; c <= r; c++) {
    el('rect', { x: X0 + cellPos(c), y: Y0 + cellPos(r), width: CELL - 1, height: CELL - 1, fill: colour((rho[r][c] + 1) / 2, CORR_STOPS),
      class: 'cell', 'data-row': r, 'data-col': c }, matrix.cells);
  }
  drawScatter();
}

function drawScatter() {
  const [r, c] = cstate.hover ?? cstate.pinned;
  matrix.marker.setAttribute('x', X0 + cellPos(c) - 0.5);
  matrix.marker.setAttribute('y', Y0 + cellPos(r) - 0.5);
  scatter.replaceChildren();
  const values = corr.change[cstate.contrast], rho = corr.rho[cstate.contrast][r][c];
  const xs = values.map(v => v[c]), ys = values.map(v => v[r]);
  const box = { left: 640, right: 940, top: 92, bottom: 392 };
  const range = list => { let lo = Math.min(0, ...list), hi = Math.max(0, ...list); const pad = 0.08 * (hi - lo || 1); return [lo - pad, hi + pad]; };
  const [xlo, xhi] = range(xs), [ylo, yhi] = range(ys);
  const sx = v => box.left + (v - xlo) / (xhi - xlo) * (box.right - box.left);
  const sy = v => box.bottom - (v - ylo) / (yhi - ylo) * (box.bottom - box.top);
  const label = corr.contrasts[cstate.contrast][1];
  text(scatter, box.left - 50, 22, r === c ? measureName(r) : `${measureName(r)} and ${measureName(c)}`, { class: 'head-ink' });
  text(scatter, box.left - 50, 44, `ρ = ${minus(rho.toFixed(2))} across ${values.length} animals, changes ${label.replace(' vs ', ' − ')}`, { class: 'head' });
  el('line', { x1: sx(0), x2: sx(0), y1: box.top, y2: box.bottom, class: 'unity' }, scatter);
  el('line', { x1: box.left, x2: box.right, y1: sy(0), y2: sy(0), class: 'unity' }, scatter);
  el('path', { d: `M${box.left},${box.top}V${box.bottom}H${box.right}`, class: 'axis' }, scatter);
  const xstep = niceStep(xhi - xlo), ystep = niceStep(yhi - ylo);
  const fmt = (v, step) => minus(Number(v.toFixed(Math.max(0, -Math.floor(Math.log10(step)) + 1))).toString());
  for (let v = Math.ceil(xlo / xstep) * xstep; v <= xhi; v += xstep) text(scatter, sx(v), box.bottom + 16, fmt(v, xstep), { 'text-anchor': 'middle' });
  for (let v = Math.ceil(ylo / ystep) * ystep; v <= yhi; v += ystep) text(scatter, box.left - 6, sy(v) + 4, fmt(v, ystep), { 'text-anchor': 'end' });
  const unit = i => corr.measures[i % corr.measures.length][1];
  text(scatter, (box.left + box.right) / 2, box.bottom + 36, `${measureName(c)}, change (${unit(c)})`, { 'text-anchor': 'middle' });
  const ly = (box.top + box.bottom) / 2;
  text(scatter, box.left - 46, ly, `${measureName(r)}, change (${unit(r)})`, { 'text-anchor': 'middle', transform: `rotate(-90 ${box.left - 46} ${ly})` });
  const name = el('text', { class: 'dot-label' }, scatter);
  values.forEach((_, a) => {
    const dot = el('circle', { cx: sx(xs[a]), cy: sy(ys[a]), r: 4.5, class: 'scatter-dot' }, scatter);
    dot.append(Object.assign(document.createElementNS(NS, 'title'), { textContent: `Animal ${Number(corr.animals[a])}` }));
    dot.addEventListener('pointerover', () => { name.textContent = `Animal ${Number(corr.animals[a])}`; name.setAttribute('x', sx(xs[a]) + 8); name.setAttribute('y', sy(ys[a]) - 8); });
    dot.addEventListener('pointerout', () => { name.textContent = ''; });
  });
  document.querySelectorAll('#corr-contrasts button').forEach((b, i) => b.setAttribute('aria-pressed', String(i === cstate.contrast)));
}

const cellOf = target => target.classList?.contains('cell') ? [Number(target.dataset.row), Number(target.dataset.col)] : null;
matrix.addEventListener('pointerover', event => { const cell = cellOf(event.target); if (cell) { cstate.hover = cell; drawScatter(); } });
matrix.addEventListener('pointerleave', () => { cstate.hover = null; drawScatter(); });
matrix.addEventListener('click', event => { const cell = cellOf(event.target); if (cell) { cstate.pinned = cell; cstate.hover = null; drawScatter(); } });
tabs('corr-contrasts', corr.contrasts.map(c => c[1]), i => { cstate.contrast = i; drawMatrix(); });
buildMatrix();
