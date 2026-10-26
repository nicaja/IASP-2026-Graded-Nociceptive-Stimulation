// Interactive figure: response, total-power difference map and power ratios for S1, PFC and ACC.
const NS = 'http://www.w3.org/2000/svg';
const INTENSITY = ['#D3A15F', '#B8582F', '#6E1F2B'];
const REGION = { S1: '#3E7F62', PFC: '#2F7DAB', ACC: '#795098' };
const COMPONENTS = [['total', 'Total', '#22211E'], ['evoked', 'Evoked', '#1F6F78'], ['induced', 'Induced', '#B58A55']];
const STOPS = [[0, '#2E6F86'], [0.25, '#9DBDC6'], [0.5, '#F4F1EA'], [2 / 3, '#E2B48F'], [5 / 6, '#B8582F'], [1, '#6E1F2B']];
const ROW = 190, TOP = 62, WAVE = [62, 540], MAP = [590, 790], POWER = [858, 950], PLOT_H = 128;
const T0 = -150, T1 = 550;

const el = (name, attrs = {}, parent) => {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.append(node);
  return node;
};
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
function colour(u) {
  u = Math.max(0, Math.min(1, u));
  let i = 0;
  while (i < STOPS.length - 2 && u > STOPS[i + 1][0]) i++;
  const [a, ca] = STOPS[i], [b, cb] = STOPS[i + 1], f = (u - a) / (b - a);
  const [x, y] = [hex(ca), hex(cb)];
  return `rgb(${x.map((v, k) => Math.round(v + f * (y[k] - v))).join(',')})`;
}

const data = await (await fetch('data/page.json')).json();
const svg = document.getElementById('explorer');
const readout = document.getElementById('readout');
let contrast = 1, now = 400, timer = null;

const xWave = t => WAVE[0] + (t - T0) / (T1 - T0) * (WAVE[1] - WAVE[0]);
const tWave = x => T0 + (x - WAVE[0]) / (WAVE[1] - WAVE[0]) * (T1 - T0);
const xMap = t => MAP[0] + t / 400 * (MAP[1] - MAP[0]);
const tMap = x => (x - MAP[0]) / (MAP[1] - MAP[0]) * 400;
const yFreq = (f, top) => top + PLOT_H - Math.log(f / 20) / Math.log(10) * PLOT_H;
const xRatio = r => POWER[0] + Math.log(r / 0.8) / Math.log(2.4 / 0.8) * (POWER[1] - POWER[0]);

// Static layer: headings, waveforms and axes.
el('text', { x: WAVE[0], y: 18, class: 'head' }, svg).textContent = 'Stimulation-locked response (µV)';
const mapHead = el('text', { x: MAP[0], y: 18, class: 'head' }, svg);
el('text', { x: 812, y: 18, class: 'head' }, svg).textContent = 'Power ratio';
['2× MT', '10× MT', '20× MT'].forEach((label, c) => {
  const x = 300 + c * 80;
  el('line', { x1: x, x2: x + 18, y1: 14, y2: 14, stroke: INTENSITY[c], 'stroke-width': 2.5 }, svg);
  el('text', { x: x + 23, y: 18 }, svg).textContent = label;
});

const rows = data.regions.map((region, r) => {
  const top = TOP + r * ROW, bottom = top + PLOT_H;
  const mean = data.trace.mean[r], se = data.trace.se[r], t = data.trace.t;
  const lo = Math.min(...mean.map((m, c) => Math.min(...m.map((v, i) => v - se[c][i]))));
  const hi = Math.max(...mean.map((m, c) => Math.max(...m.map((v, i) => v + se[c][i]))));
  const y = v => bottom - (v - lo) / (hi - lo) * PLOT_H;
  el('rect', { x: WAVE[0], y: top - 26, width: 10, height: 10, fill: REGION[region] }, svg);
  el('text', { x: WAVE[0] + 15, y: top - 17, class: 'region' }, svg).textContent = `${region}  (n = ${data.n[r]})`;
  el('rect', { x: xWave(T0), y: top, width: xWave(0) - xWave(T0), height: PLOT_H, fill: '#EAE5DA' }, svg);
  el('line', { x1: WAVE[0], x2: WAVE[1], y1: y(0), y2: y(0), class: 'zero' }, svg);
  const step = 2;
  mean.forEach((m, c) => {
    const upper = [], lower = [];
    for (let i = 0; i < t.length; i += step) { upper.push(`${xWave(t[i]).toFixed(1)},${y(m[i] + se[c][i]).toFixed(1)}`); lower.unshift(`${xWave(t[i]).toFixed(1)},${y(m[i] - se[c][i]).toFixed(1)}`); }
    el('path', { d: `M${upper.join('L')}L${lower.join('L')}Z`, fill: INTENSITY[c], opacity: 0.18 }, svg);
    const line = [];
    for (let i = 0; i < t.length; i += step) line.push(`${xWave(t[i]).toFixed(1)},${y(m[i]).toFixed(1)}`);
    el('path', { d: `M${line.join('L')}`, stroke: INTENSITY[c], 'stroke-width': 1.4, fill: 'none' }, svg);
  });
  el('path', { d: `M${WAVE[0]},${top}V${bottom}H${WAVE[1]}`, class: 'axis' }, svg);
  const spacing = [5, 10, 20, 25, 50, 100].find(s => (hi - lo) / s <= 4);
  const ticks = [];
  for (let v = Math.ceil(lo / spacing) * spacing; v <= hi; v += spacing) ticks.push(v);
  ticks.forEach(v => { el('text', { x: WAVE[0] - 6, y: y(v) + 4, 'text-anchor': 'end' }, svg).textContent = v; });
  const mapGroup = el('g', {}, svg);
  el('path', { d: `M${MAP[0]},${top}V${bottom}H${MAP[1]}`, class: 'axis' }, svg);
  [20, 50, 100, 200].forEach(f => { el('text', { x: MAP[0] - 6, y: yFreq(f, top) + 4, 'text-anchor': 'end' }, svg).textContent = f === 200 ? '200 Hz' : f; });
  const powerGroup = el('g', {}, svg);
  const cursors = [el('line', { y1: top, y2: bottom, class: 'cursor' }, svg), el('line', { y1: top, y2: bottom, class: 'cursor' }, svg)];
  el('rect', { x: WAVE[0], y: top, width: WAVE[1] - WAVE[0], height: PLOT_H, class: 'hit', 'data-kind': 'wave', 'data-row': r }, svg);
  el('rect', { x: MAP[0], y: top, width: MAP[1] - MAP[0], height: PLOT_H, class: 'hit', 'data-kind': 'map', 'data-row': r }, svg);
  return { top, bottom, mapGroup, powerGroup, cursors };
});

const axisY = TOP + 2 * ROW + PLOT_H;
[-150, 0, 200, 400, 550].forEach(v => { el('text', { x: xWave(v), y: axisY + 18, 'text-anchor': 'middle' }, svg).textContent = v; });
el('text', { x: (WAVE[0] + WAVE[1]) / 2, y: axisY + 38, 'text-anchor': 'middle' }, svg).textContent = 'Time from stimulation (ms)';
[0, 200, 400].forEach(v => { el('text', { x: xMap(v), y: axisY + 18, 'text-anchor': 'middle' }, svg).textContent = v; });
el('text', { x: (MAP[0] + MAP[1]) / 2, y: axisY + 38, 'text-anchor': 'middle' }, svg).textContent = 'Time (ms)';
[1, 1.5, 2].forEach(v => { el('text', { x: xRatio(v), y: axisY + 18, 'text-anchor': 'middle' }, svg).textContent = v; });

function drawContrast() {
  mapHead.textContent = `Total power, ${data.contrasts[contrast][1]}`;
  const { f, fEdges, tEdges, effect, mask, limit } = data.map;
  rows.forEach((row, r) => {
    row.mapGroup.replaceChildren();
    const values = effect[contrast][r], corrected = mask[contrast][r];
    const yEdge = fEdges.map(v => yFreq(Math.min(200, Math.max(20, v)), row.top));
    for (let i = 0; i < f.length; i++) for (let j = 0; j < tEdges.length - 1; j++) {
      el('rect', { x: xMap(tEdges[j]).toFixed(2), y: yEdge[i + 1].toFixed(2), width: (xMap(tEdges[j + 1]) - xMap(tEdges[j]) + 0.4).toFixed(2),
        height: (yEdge[i] - yEdge[i + 1] + 0.4).toFixed(2), fill: colour((values[i][j] / limit + 1) / 2) }, row.mapGroup);
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
    if (d) el('path', { d, class: 'outline' }, row.mapGroup);
    row.powerGroup.replaceChildren();
    el('line', { x1: xRatio(1), x2: xRatio(1), y1: row.top, y2: row.bottom, stroke: '#ABA597', 'stroke-dasharray': '2 3' }, row.powerGroup);
    COMPONENTS.forEach(([key, label, hue], k) => {
      const [ratio, low, high, p] = data.power[contrast][r][key];
      const y = row.top + 26 + k * 38;
      el('line', { x1: xRatio(Math.max(low, 0.8)), x2: xRatio(Math.min(high, 2.4)), y1: y, y2: y, stroke: hue, 'stroke-width': 1.8 }, row.powerGroup);
      el('circle', { cx: xRatio(ratio), cy: y, r: 4.2, fill: p < 0.05 ? hue : '#F4F1EA', stroke: hue, 'stroke-width': 1.5 }, row.powerGroup)
        .append(Object.assign(document.createElementNS(NS, 'title'), { textContent: `${label}: ${ratio.toFixed(2)} (${low.toFixed(2)}–${high.toFixed(2)}), Holm P = ${p}` }));
      el('text', { x: 812, y: y + 4, style: `fill:${hue};font-size:11px` }, row.powerGroup).textContent = label;
    });
  });
  document.querySelectorAll('#contrasts button').forEach((b, i) => b.setAttribute('aria-pressed', String(i === contrast)));
  moveCursor(now);
}

function moveCursor(t) {
  now = Math.max(T0, Math.min(T1, t));
  rows.forEach(row => {
    row.cursors[0].setAttribute('x1', xWave(now)); row.cursors[0].setAttribute('x2', xWave(now));
    const inMap = now >= 0 && now <= 400;
    row.cursors[1].setAttribute('x1', xMap(Math.max(0, Math.min(400, now)))); row.cursors[1].setAttribute('x2', xMap(Math.max(0, Math.min(400, now))));
    row.cursors[1].style.opacity = inMap ? 1 : 0;
  });
  readout.textContent = `${Math.round(now)} ms`;
}

function describe(r, t, y) {
  const { f, tEdges, effect, mask } = data.map;
  const j = tEdges.findIndex((edge, k) => k < tEdges.length - 1 && t >= edge && t < tEdges[k + 1]);
  const freq = 20 * Math.pow(10, (rows[r].bottom - y) / PLOT_H);
  let i = 0;
  while (i < f.length - 1 && Math.abs(Math.log(f[i + 1] / freq)) < Math.abs(Math.log(f[i] / freq))) i++;
  if (j < 0) return '';
  const value = effect[contrast][r][i][j];
  return ` · ${data.regions[r]} ${Math.round(f[i])} Hz, ${Math.round(data.map.t[j])} ms: ${value >= 0 ? '+' : ''}${value.toFixed(3)} log10 power${mask[contrast][r][i][j] ? ' (corrected)' : ''}`;
}

function amplitudes(r) {
  const t = data.trace.t, i = t.findIndex(v => v >= now);
  if (i < 0) return '';
  const values = data.trace.mean[r].map(m => m[i].toFixed(1)).join(' / ');
  return ` · ${data.regions[r]} at 2× / 10× / 20× MT: ${values} µV`;
}

function pointer(event) {
  const target = event.target;
  if (!target.classList?.contains('hit')) return;
  const box = svg.getBoundingClientRect(), scale = 960 / box.width;
  const x = (event.clientX - box.left) * scale, y = (event.clientY - box.top) * scale;
  const kind = target.dataset.kind, r = Number(target.dataset.row);
  stop();
  moveCursor(kind === 'wave' ? tWave(x) : tMap(x));
  readout.textContent += kind === 'map' ? describe(r, tMap(x), y) : amplitudes(r);
}
svg.addEventListener('pointermove', pointer);
svg.addEventListener('pointerdown', pointer);

function stop() { if (timer) cancelAnimationFrame(timer); timer = null; document.getElementById('play').textContent = 'Play'; }
document.getElementById('play').addEventListener('click', () => {
  if (timer) return stop();
  document.getElementById('play').textContent = 'Pause';
  const start = performance.now(), from = now >= T1 - 1 ? T0 : now;
  const tick = time => {
    const t = from + (time - start) / 5000 * (T1 - T0);
    moveCursor(t);
    if (t < T1) timer = requestAnimationFrame(tick); else stop();
  };
  timer = requestAnimationFrame(tick);
});

const tabs = document.getElementById('contrasts');
data.contrasts.forEach(([, label], i) => {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = label;
  button.addEventListener('click', () => { contrast = i; drawContrast(); });
  tabs.append(button);
});
drawContrast();

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
