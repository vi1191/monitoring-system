// src/routes.js
import { MACHINES, STREETS } from './data.js';
import { confirmAction, notify, requestText } from './dialogs.js';
import { esc, lineLength, polygonArea, isYardObject, offsetPolyline, inferAreaFromName } from './utils.js';
import * as L from 'leaflet';
import { saveData } from './ui-controls.js';
import { 
  rbRoutesByVehicle, activeRouteIndex, miniRouteVehicle,
  getRouteColor,
  setMiniRouteVehicle, setActiveVehicle, setActiveRouteIndex,
  pushUndo, routeLayerGroup, map, getYardColor, pinnedRouteIndexByVehicle,
  setPinnedRouteIndexByVehicle
} from './state.js';

let hoveredPlate = null;
let hoveredCategory = null;
let pinnedCategory = null;
let hoveredArea = null;
let pinnedArea = null;
let routeEditing = false;
export function isRouteEditing() { return routeEditing && !!miniRouteVehicle; }
export function setHoveredRoutePlate(plate) { hoveredPlate = plate; renderRouteOnMap(); }
export function setHoveredRouteCategory(cat) { hoveredCategory = cat; renderRouteOnMap(); }
export function setHoveredRouteArea(area) { hoveredArea = area; renderRouteOnMap(); }
export function setPinnedRouteArea(area) { pinnedArea = area; renderRouteOnMap(); }
export function getPinnedRouteIndex(plate) {
  const routes = rbRoutesByVehicle[plate] || [];
  const idx = pinnedRouteIndexByVehicle[plate];
  return Number.isInteger(idx) && routes[idx]?.items?.length ? idx : routes.findIndex(r => r?.items?.length);
}
export function pinVehicleRoute(plate, idx) {
  if (!rbRoutesByVehicle[plate]?.[idx]?.items?.length) return;
  pushUndo('закрепление маршрута');
  setPinnedRouteIndexByVehicle({ ...pinnedRouteIndexByVehicle, [plate]: idx });
  saveData(false);
  window.renderList?.();
  renderRouteOnMap();
}
export function refreshRouteOnMap() { renderRouteOnMap(); }
export function togglePinnedRouteCategory(cat) {
  pinnedCategory = pinnedCategory === cat ? null : cat;
  document.querySelectorAll('.cat-tab').forEach(b => {
    const pressed = b.dataset.cat === pinnedCategory;
    b.classList.toggle('routes-pinned', pressed);
    b.setAttribute('aria-pressed-routes', String(pressed));
  });
  renderRouteOnMap();
}
function categoryPlates(cat) {
  return MACHINES.filter(m => cat === 'odh' ? m.isODH : cat === 'dvory' ? m.isDvory : true).map(m => m.plate);
}
function shapesForItem(item) {
  const street = STREETS.find(s => s.name === item.name && isYardObject(s) === (item.type === 'yard'));
  if (Array.isArray(item.shapes)) return item.shapes;
  return (street ? [street.coords, ...(street.extraPolygons || [])] : [item.coords]).filter(c => Array.isArray(c) && c.length >= 2)
    .map(coords => ({ coords, polygon: item.type === 'yard' && coords.length >= 3 }));
}
function editableShapes(item) {
  if (!Array.isArray(item.shapes)) item.shapes = shapesForItem(item).map(shape => ({ coords: shape.coords.map(p => [...p]), polygon: shape.polygon }));
  return item.shapes;
}
export function toggleRouteEditing() {
  if (!miniRouteVehicle) return;
  routeEditing = !routeEditing;
  if (!routeEditing) { map?.pm?.disableDraw(); map?.pm?.disableGlobalEditMode(); map?.pm?.disableGlobalDragMode(); map?.pm?.disableGlobalRemovalMode(); }
  document.getElementById('route-edit-btn')?.classList.toggle('active', routeEditing);
  const hint = document.getElementById('route-edit-hint');
  if (hint) hint.hidden = !routeEditing;
  renderRouteOnMap();
}

// === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ===
function ensureRoutes(plate) {
  if (!rbRoutesByVehicle[plate]) {
    rbRoutesByVehicle[plate] = [];
    for (let i = 0; i < 5; i++) {
      rbRoutesByVehicle[plate].push({ items: [], color: null, name: 'М' + (i + 1), ts: null });
    }
  } else {
    while (rbRoutesByVehicle[plate].length < 5) {
      rbRoutesByVehicle[plate].push({ items: [], color: null, name: 'М' + (rbRoutesByVehicle[plate].length + 1), ts: null });
    }
    rbRoutesByVehicle[plate].forEach((r, i) => {
      if (!r.name) r.name = 'М' + (i + 1);
    });
  }
  return rbRoutesByVehicle[plate];
}

// === ОТКРЫТИЕ / ЗАКРЫТИЕ ===
export async function openMiniRoute(plate) {
  if (routeEditing && miniRouteVehicle !== plate) toggleRouteEditing();
  const m = MACHINES.find(x => x.plate === plate);
  if (!m) { await notify('Машина не найдена: ' + plate); return; }
  setMiniRouteVehicle(plate);
  setActiveVehicle(plate);
  ensureRoutes(plate);
  renderRouteTabs();
  renderMiniRoute();
  document.getElementById('mini-route').classList.add('open');
  renderRouteOnMap();
  console.log('openMiniRoute (routes.js):', plate);
}

export function closeMiniRoute() {
  if (routeEditing) toggleRouteEditing();
  setMiniRouteVehicle(null);
  document.getElementById('mini-route').classList.remove('open');
  closePicker();
  renderRouteOnMap();
}

export function renderRouteOnMap() {
  if (!routeLayerGroup) return;
  // Rebuild only the route overlays; the shared street geometry remains untouched.
  routeLayerGroup.clearLayers();
  const area = hoveredArea || (hoveredCategory ? null : pinnedArea);
  const category = hoveredCategory || pinnedCategory;
  const plates = new Set(area ? MACHINES.filter(m => m.area === area).map(m => m.plate) : category ? categoryPlates(category) : []);
  if (hoveredPlate) plates.add(hoveredPlate);
  if (miniRouteVehicle) plates.add(miniRouteVehicle);
  const entries = [];
  plates.forEach(plate => {
    const routeIdx = miniRouteVehicle === plate && !category && !area ? activeRouteIndex : getPinnedRouteIndex(plate);
    const route = rbRoutesByVehicle[plate]?.[routeIdx];
    if (route?.items?.length) entries.push({ plate, route, routeIdx });
  });
  const machinesByObject = new Map();
  entries.forEach(({ plate, route }) => route.items.forEach(item => {
    const key = item.type + ':' + item.name;
    if (!machinesByObject.has(key)) machinesByObject.set(key, new Set());
    machinesByObject.get(key).add(plate);
  }));
  entries.forEach(({ plate, route, routeIdx }, lane) => {
    const focused = plate === miniRouteVehicle && routeIdx === activeRouteIndex && !category && !area;
    const color = route.color || getRouteColor(plate, routeIdx);
    route.items.forEach((item, itemIdx) => {
      shapesForItem(item).forEach((shape, shapeIdx) => {
        const editable = isRouteEditing() && focused;
        // Parallel offsets keep coincident paths visible, without changing stored coordinates.
        const coords = shape.polygon || editable ? shape.coords : offsetPolyline(shape.coords, (lane - (entries.length - 1) / 2) * 4 / 111320);
        const yardColor = shape.polygon && item.type === 'yard' ? getYardColor(STREETS.find(s => s.name === item.name) || item) : color;
        const options = { color, fillColor: yardColor,
          weight: focused ? 5 : 3, opacity: 0.85, fillOpacity: shape.polygon ? 0.13 : 0,
          dashArray: shape.polygon && entries.length > 1 ? ['10,4', '5,5', '2,5'][lane % 3] : undefined,
          pmIgnore: !editable };
        const layer = shape.polygon && shape.coords.length >= 3 ? L.polygon(coords, options) : L.polyline(coords, options);
        layer._routeShape = { plate, routeIdx, itemIdx, shapeIdx };
        const platesHere = [...machinesByObject.get(item.type + ':' + item.name)];
        layer.bindTooltip(esc(item.name) + ' · Техника: ' + platesHere.map(esc).join(', '));
        layer.on('click', () => {
          if (miniRouteVehicle !== plate) openMiniRoute(plate);
          else if (activeRouteIndex !== routeIdx) switchRoute(routeIdx);
          else if (editable && !map.pm.globalEditModeEnabled() && !map.pm.globalDragModeEnabled() && !map.pm.globalRemovalModeEnabled()) layer.pm.enable({ snappable: true });
        });
        layer.addTo(routeLayerGroup);
      });
      if (focused) {
        const first = shapesForItem(item).find(s => s.coords?.length >= 2);
        if (first) L.marker(first.coords[0], { icon: L.divIcon({ className: 'route-order-icon', html: String(itemIdx + 1), iconSize: [22, 22] }), interactive: false, pmIgnore: true }).addTo(routeLayerGroup);
      }
    });
  });
  if (area) {
    STREETS.filter(s => isYardObject(s) && (s.area || inferAreaFromName(s.name)) === area).forEach(s => {
      [s.coords, ...(s.extraPolygons || [])].forEach(coords => {
        if (coords.length < 3) return;
        L.polygon(coords, { color: getYardColor(s), weight: 5, fillOpacity: 0.3, interactive: false, pmIgnore: true }).addTo(routeLayerGroup);
      });
    });
  }
}

function getEditedShape(layer) {
  const ref = layer?._routeShape;
  if (!ref || !isRouteEditing() || ref.plate !== miniRouteVehicle || ref.routeIdx !== activeRouteIndex) return null;
  const item = rbRoutesByVehicle[ref.plate]?.[ref.routeIdx]?.items?.[ref.itemIdx];
  if (!item) return null;
  return { item, ref };
}
function layerShape(layer) {
  const points = layer.getLatLngs();
  const ring = Array.isArray(points[0]) ? points[0] : points;
  return { coords: ring.map(ll => [ll.lat, ll.lng]), polygon: layer instanceof L.Polygon };
}
export function onRouteCreate(e) {
  const route = rbRoutesByVehicle[miniRouteVehicle]?.[activeRouteIndex];
  const shape = layerShape(e.layer);
  map.removeLayer(e.layer);
  if (!route || shape.coords.length < (shape.polygon ? 3 : 2)) return;
  pushUndo('новая фигура маршрута');
  route.items.push({ name: 'Своя фигура ' + (route.items.length + 1), type: shape.polygon ? 'yard' : 'street', shapes: [shape] });
  renderMiniRoute(); renderRouteTabs(); saveData(false); window.renderList?.();
}
export function onRouteRemove(e) {
  const found = getEditedShape(e.layer);
  if (!found) return;
  pushUndo('удаление линии маршрута');
  const shapes = editableShapes(found.item);
  shapes.splice(found.ref.shapeIdx, 1);
  if (!shapes.length) rbRoutesByVehicle[found.ref.plate][found.ref.routeIdx].items.splice(found.ref.itemIdx, 1);
  renderMiniRoute(); renderRouteTabs(); saveData(false); window.renderList?.();
}
export function onRouteEdit(e) {
  const found = getEditedShape(e.layer);
  if (!found) return;
  const shape = layerShape(e.layer);
  if (shape.coords.length < (shape.polygon ? 3 : 2)) return;
  const original = shapesForItem(found.item)[found.ref.shapeIdx];
  if (JSON.stringify(original) === JSON.stringify(shape)) return;
  pushUndo('правка точек маршрута');
  editableShapes(found.item)[found.ref.shapeIdx] = shape;
  renderMiniRoute(); saveData(false);
}
export function onRouteDragEnd(e) { onRouteEdit(e); }

export function openPicker() {
  if (!miniRouteVehicle) return;
  document.getElementById('picker')?.classList.add('open');
  renderPicker();
  document.getElementById('picker-search')?.focus();
}

export function closePicker() { document.getElementById('picker')?.classList.remove('open'); }

export function renderPicker() {
  const container = document.getElementById('picker-streets');
  if (!container || !miniRouteVehicle) return;
  const query = document.getElementById('picker-search')?.value.trim().toLocaleLowerCase() || '';
  const hideEmpty = document.getElementById('picker-hide-empty')?.checked;
  const active = ensureRoutes(miniRouteVehicle)[activeRouteIndex];
  container.replaceChildren();
  STREETS.forEach((street, idx) => {
    if (query && !street.name.toLocaleLowerCase().includes(query)) return;
    const hasGeometry = (street.coords?.length >= 2) || street.extraPolygons?.some(c => c.length >= 2);
    if (hideEmpty && !hasGeometry) return;
    const type = isYardObject(street) ? 'yard' : 'street';
    const label = document.createElement('label');
    if (type === 'yard') label.classList.add('polygon');
    if (!hasGeometry) label.classList.add('empty');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = active.items.some(it => it.name === street.name && it.type === type);
    checkbox.setAttribute('aria-label', street.name);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked === active.items.some(it => it.name === street.name && it.type === type)) return;
      pushUndo(checkbox.checked ? 'добавление объекта' : 'удаление объекта');
      if (checkbox.checked) active.items.push({ name: street.name, type, coords: street.coords || [] });
      else active.items = active.items.filter(it => !(it.name === street.name && it.type === type));
      renderMiniRoute();
      renderRouteTabs();
      window.renderList?.();
      saveData(false);
    });
    const name = document.createElement('span');
    name.textContent = (type === 'yard' ? '🏠 ' : '🛣 ') + street.name + (hasGeometry ? '' : ' · нет геометрии');
    label.append(checkbox, name);
    const edit = document.createElement('button');
    edit.type = 'button'; edit.className = 'draw-btn'; edit.textContent = '✏️ Геометрия';
    edit.title = 'Открыть объект в редакторе';
    edit.onclick = e => { e.preventDefault(); closePicker(); window.toggleEditor?.(idx); };
    label.appendChild(edit);
    container.appendChild(label);
  });
}

// === ВКЛАДКИ ===
export function renderRouteTabs() {
  const container = document.getElementById('route-tabs');
  if (!container) return;
  container.innerHTML = '';

  if (!miniRouteVehicle) return;
  const routes = ensureRoutes(miniRouteVehicle);

  routes.forEach((route, idx) => {
    const tab = document.createElement('div');
    const hasItems = route.items && route.items.length > 0;
    const color = getRouteColor(miniRouteVehicle, idx);
    tab.className = 'route-tab' + (idx === activeRouteIndex ? ' active' : '');
    tab.dataset.idx = idx;
    tab.style.borderTopColor = color;
    tab.style.borderTopWidth = '3px';

    const dot = hasItems ? '<span class="tab-dot"></span>' : '';
    tab.innerHTML = dot +
      '<span class="tab-name">' + esc(route.name || ('М' + (idx + 1))) + '</span>' +
      '<span class="tab-arrows">' +
        (idx > 0 ? '<span class="tab-left">◀</span>' : '') +
        (idx < routes.length - 1 ? '<span class="tab-right">▶</span>' : '') +
      '</span>';

    tab.onclick = (e) => {
      if (e.target.closest('.tab-arrows')) return;
      switchRoute(idx);
    };

    const left = tab.querySelector('.tab-left');
    if (left) left.onclick = (e) => { e.stopPropagation(); moveTab(idx, -1); };
    const right = tab.querySelector('.tab-right');
    if (right) right.onclick = (e) => { e.stopPropagation(); moveTab(idx, 1); };

    container.appendChild(tab);
  });
}

// === ПЕРЕКЛЮЧЕНИЕ ВКЛАДКИ ===
export function switchRoute(idx) {
  setActiveRouteIndex(idx);
  renderRouteTabs();
  renderMiniRoute();
  renderPicker();
  saveData(false);
}

// === ПЕРЕСТАНОВКА ВКЛАДОК ===
export function moveTab(idx, dir) {
  if (!miniRouteVehicle) return;
  const routes = ensureRoutes(miniRouteVehicle);
  const ni = idx + dir;
  if (ni < 0 || ni >= routes.length) return;
  pushUndo('перестановка маршрутов');
  const tmp = routes[idx];
  routes[idx] = routes[ni];
  routes[ni] = tmp;
  if (activeRouteIndex === idx) setActiveRouteIndex(ni);
  else if (activeRouteIndex === ni) setActiveRouteIndex(idx);
  renderRouteTabs();
  renderMiniRoute();
  saveData(false);
}

// === СПИСОК ТОЧЕК ===
export function renderMiniRoute() {
  if (!miniRouteVehicle) return;
  const m = MACHINES.find(x => x.plate === miniRouteVehicle);
  if (!m) return;
  renderRouteOnMap();

  const active = ensureRoutes(miniRouteVehicle)[activeRouteIndex];
  let len = 0, areaSum = 0;
  (active && active.items || []).forEach(it => {
    shapesForItem(it).forEach(shape => {
      if (shape.polygon) areaSum += polygonArea(shape.coords);
      else len += lineLength(shape.coords);
    });
  });
  const lenStr = len < 1000 ? Math.round(len) + ' м' : (len / 1000).toFixed(2) + ' км';
  const areaStr = areaSum > 0 ? (' · ' + Math.round(areaSum) + ' м² дворов') : '';

  const infoEl = document.getElementById('mr-info');
  if (infoEl) {
    infoEl.innerHTML =
      '<b>' + esc(m.vid || '') + '</b><br>' + esc(m.model || '') + (m.year ? ' · ' + esc(m.year) : '') + '<br>' +
      'Категория: <b>' + esc(m.cat_b || '—') + '</b>' + (m.area ? ' · ' + esc(m.area) : '') +
      (m.subtype ? '<br>Подтип: <b>' + esc(m.subtype) + '</b>' : '') +
      '<br>Длина: <b>' + lenStr + '</b>' + areaStr;
  }

  const list = document.getElementById('mr-list');
  if (!list) return;
  list.innerHTML = '';
  if (!active || !active.items || active.items.length === 0) {
    list.innerHTML = '<div class="mr-empty">Маршрут пуст.<br>Нажмите «➕ Добавить».</div>';
    return;
  }

  active.items.forEach((s, idx) => {
    const item = document.createElement('div');
    item.className = 'mr-item';
    const icon = s.type === 'yard' ? '🏠' : '🛣';
    item.innerHTML = '<span class="num">' + (idx + 1) + '</span>' +
      '<span class="name">' + icon + ' ' + esc(s.name) + '</span>' +
      '<button class="mv mr-up" title="Вверх" aria-label="Вверх" ' + (idx === 0 ? 'disabled' : '') + '>⬆</button>' +
      '<button class="mv mr-dn" title="Вниз" aria-label="Вниз" ' + (idx === active.items.length - 1 ? 'disabled' : '') + '>⬇</button>' +
      '<button class="rm mr-del" title="Удалить" aria-label="Удалить">✕</button>';
    item.querySelector('.mr-up').onclick = () => moveRoutePoint(idx, -1);
    item.querySelector('.mr-dn').onclick = () => moveRoutePoint(idx, 1);
    item.querySelector('.mr-del').onclick = () => removeFromMiniRoute(idx);
    list.appendChild(item);
  });
}

// === УПРАВЛЕНИЕ ТОЧКАМИ ===
export function moveRoutePoint(idx, dir) {
  const active = ensureRoutes(miniRouteVehicle)[activeRouteIndex];
  if (!active || !active.items) return;
  const ni = idx + dir;
  if (ni < 0 || ni >= active.items.length) return;
  pushUndo('перемещение точки');
  const tmp = active.items[idx];
  active.items[idx] = active.items[ni];
  active.items[ni] = tmp;
  renderMiniRoute();
  saveData(false);
}

export function removeFromMiniRoute(idx) {
  const active = ensureRoutes(miniRouteVehicle)[activeRouteIndex];
  if (!active) return;
  pushUndo('удаление точки маршрута');
  active.items.splice(idx, 1);
  renderMiniRoute();
  renderRouteTabs();
  renderPicker();
  saveData(false);
  window.renderList?.();
}

export async function clearActiveRoute() {
  if (!miniRouteVehicle) return;
  const active = ensureRoutes(miniRouteVehicle)[activeRouteIndex];
  if (!active) return;
  if (!await confirmAction('Очистить "' + (active.name || 'М' + (activeRouteIndex + 1)) + '" для ' + miniRouteVehicle + '?')) return;
  pushUndo('очистка маршрута');
  active.items = [];
  active.color = null;
  renderMiniRoute();
  renderRouteTabs();
  renderPicker();
  saveData(false);
  window.renderList?.();
}

export async function copyRouteFrom() {
  if (!miniRouteVehicle) return;
  const source = await requestText('Введите госномер машины-источника:');
  if (!source) return;
  const srcPlate = source.trim().toUpperCase();
  const srcMach = MACHINES.find(m => m.plate.toUpperCase() === srcPlate);
  if (!srcMach) { await notify('Машина не найдена: ' + srcPlate); return; }
  if (!rbRoutesByVehicle[srcPlate]) { await notify('У источника нет маршрута'); return; }
  if (!await confirmAction('Скопировать маршрут с ' + srcPlate + ' на ' + miniRouteVehicle + '?')) return;
  pushUndo('копирование маршрута');
  const srcActive = rbRoutesByVehicle[srcPlate][activeRouteIndex] || rbRoutesByVehicle[srcPlate][0];
  ensureRoutes(miniRouteVehicle)[activeRouteIndex] = JSON.parse(JSON.stringify(srcActive));
  renderMiniRoute();
  renderRouteTabs();
  renderPicker();
  saveData(false);
  window.renderList?.();
}

export function printRoute() {
  if (!miniRouteVehicle) return;
  const route = ensureRoutes(miniRouteVehicle)[activeRouteIndex];
  const area = document.getElementById('print-area');
  if (!area) return;
  area.innerHTML = '<h1>Маршрут ' + esc(route.name) + ' · ' + esc(miniRouteVehicle) + '</h1><table><thead><tr><th>№</th><th>Объект</th></tr></thead><tbody>' +
    route.items.map((item, i) => '<tr><td>' + (i + 1) + '</td><td>' + esc(item.name) + '</td></tr>').join('') + '</tbody></table>';
  window.print();
}

export function printMapOnly() {
  if (!miniRouteVehicle) return;
  const area = document.getElementById('print-area');
  if (!area) return;
  const route = ensureRoutes(miniRouteVehicle)[activeRouteIndex];
  area.innerHTML = '<h1>Карта маршрута ' + esc(route.name) + ' · ' + esc(miniRouteVehicle) + '</h1>';
  // Browser printing of Leaflet tiles from a hidden container is unreliable; print visible map instead.
  document.body.classList.add('printing-route-map');
  window.addEventListener('afterprint', () => document.body.classList.remove('printing-route-map'), { once: true });
  window.print();
}