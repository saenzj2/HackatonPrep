import {normalize, constrain, selectionBounds} from './model.mjs';
const $ = id => document.getElementById(id);
let rect = {x: 35, y: 35, w: 25, h: 25};
let view = {x: 0, y: 0, w: 100, h: 75};
let drawing = false, drag;
function render() {
  rect = constrain(rect);
  $('selection').setAttribute('x', rect.x);
  $('selection').setAttribute('y', rect.y * .75);
  $('selection').setAttribute('width', rect.w);
  $('selection').setAttribute('height', rect.h * .75);
  $('center').setAttribute('cx', rect.x + rect.w / 2);
  $('center').setAttribute('cy', (rect.y + rect.h / 2) * .75);
  $('map').setAttribute('viewBox', `${view.x} ${view.y} ${view.w} ${view.h}`);
  for (const [id, value, max] of [['sx', rect.x, 100 - rect.w], ['sy', rect.y, 100 - rect.h], ['size', rect.w, 100]]) {
    $(id).max = max; $(id).value = value;
  }
  const b = selectionBounds(rect);
  $('coordinates').textContent = `Approximate selection W/S/E/N: ${b.map(n => n.toFixed(5)).join(', ')} · Midpoint: ${((b[1] + b[3]) / 2).toFixed(5)}, ${((b[0] + b[2]) / 2).toFixed(5)}`;
}
function clampView() {
  view.x = Math.max(0, Math.min(100 - view.w, view.x));
  view.y = Math.max(0, Math.min(75 - view.h, view.y));
  render();
}
function zoom(factor) {
  const width = Math.max(12.5, Math.min(100, view.w * factor));
  view.x += (view.w - width) / 2; view.y += (view.h - width * .75) / 2;
  view.w = width; view.h = width * .75; clampView();
}
$('zoom-in').onclick = () => zoom(.7);
$('zoom-out').onclick = () => zoom(1 / .7);
$('reset').onclick = () => {view = {x: 0, y: 0, w: 100, h: 75}; render();};
$('mode').onclick = () => {drawing = !drawing; $('mode').setAttribute('aria-pressed', drawing);};
document.querySelectorAll('[data-pan]').forEach(button => button.onclick = () => {
  const [x, y] = button.dataset.pan.split(',').map(Number);
  view.x += x * view.w / 8; view.y += y * view.h / 8; clampView();
});
for (const id of ['sx', 'sy', 'size']) $(id).oninput = () => {
  if (id === 'sx') rect.x = +$(id).value;
  else if (id === 'sy') rect.y = +$(id).value;
  else rect.w = rect.h = +$(id).value;
  render();
};
function point(event) {
  const p = new DOMPoint(event.clientX, event.clientY).matrixTransform($('map').getScreenCTM().inverse());
  return {x: Math.max(0, Math.min(100, p.x)), y: Math.max(0, Math.min(100, p.y / .75))};
}
$('map').onpointerdown = event => {
  if (event.button !== 0) return;
  drag = {p: point(event), x: event.clientX, y: event.clientY, view: {...view}};
  $('map').setPointerCapture(event.pointerId);
};
$('map').onpointermove = event => {
  if (!drag) return;
  if (drawing) {
    const p = point(event);
    rect = {x: Math.min(p.x, drag.p.x), y: Math.min(p.y, drag.p.y), w: Math.max(1, Math.abs(p.x - drag.p.x)), h: Math.max(1, Math.abs(p.y - drag.p.y))};
    render();
  } else {
    const box = $('map').getBoundingClientRect();
    view.x = drag.view.x - (event.clientX - drag.x) / box.width * view.w;
    view.y = drag.view.y - (event.clientY - drag.y) / box.height * view.h;
    clampView();
  }
};
$('map').onpointerup = $('map').onpointercancel = () => {drag = undefined;};
$('crop').onchange = () => {
  $('crop-note').textContent = $('crop').value ? `${$('crop').selectedOptions[0].text}: user scenario only. Crop-cycle validation and local evidence are missing; no replacement crop is recommended.` : 'No existing crop assumed. This is not an image classification.';
};
function priorities() {
  const values = normalize(['water', 'soil', 'climate'].map(id => +$(id).value));
  $('weights').textContent = values.some(Boolean) ? `Draft normalized weights: water ${values[0].toFixed(2)}, soil ${values[1].toFixed(2)}, climate ${values[2].toFixed(2)}. Not submitted.` : 'Choose at least one nonzero priority. No request is sent.';
}
for (const id of ['water', 'soil', 'climate']) $(id).oninput = priorities;
$('example-toggle').onclick = () => {
  $('example').hidden = !$('example').hidden;
  $('example-toggle').setAttribute('aria-expanded', !$('example').hidden);
};
function paragraph(parent, text) {const p = document.createElement('p'); p.textContent = text; parent.append(p);}
async function loadExamples() {
  try {
    const data = await Promise.all(['/data/example.json', '/data/request.json', '/data/crops.json'].map(async path => {
      const response = await fetch(path); if (!response.ok) throw new Error(`Missing local evidence: ${path}`); return response.json();
    }));
    const [example, request, catalog] = data;
    if (example.location.lat !== 10 || example.location.lon !== -84.2) throw new Error('Example location changed; verify provenance before display.');
    for (const crop of catalog.crops) {const option = document.createElement('option'); option.value = crop.id; option.textContent = `${crop.name} — hypothetical report`; $('crop').append(option);}
    $('example-meta').textContent = `Fixed example generated ${example.generated_at}; method ${example.method_version}. Baseline ${request.current_rotation.join(' → ')}. Fixed priorities ${JSON.stringify(request.priorities)}. Climate: 2001–2025 monthly normals, ~0.5° × 0.625°; not a forecast. Soil: mock in every backend mode. Your draft controls do not alter this example.`;
    for (const rotation of example.rotations) {
      const article = document.createElement('article');
      paragraph(article, `#${rotation.rank} · ${rotation.sequence.map(s => `${s.crop_name} (${s.season})`).join(' → ')} · heuristic score ${rotation.score}`);
      paragraph(article, rotation.explanation);
      for (const key of ['evidence', 'risks', 'data_gaps']) paragraph(article, `${key.replaceAll('_', ' ')}: ${rotation[key].join('; ')}`);
      $('rankings').append(article);
    }
    $('raw').textContent = JSON.stringify(example, null, 2);
  } catch (error) {
    $('rankings').replaceChildren();
    $('raw').textContent = '';
    $('example-meta').textContent = `Example unavailable. ${error.message} No fallback, live request or invented ranking was used.`;
  }
}
render(); priorities(); loadExamples();
