import { confirmAction, requestText, notify } from './dialogs.js';
﻿import { STREETS } from './data.js';
import { 
  editingStreetIdx, setEditingStreetIdx, pushUndo, 
  streetLayerGroup, map, getYardColor
} from './state.js'; 
import { esc, isYardObject } from './utils.js';
import { rbRoutesByVehicle } from './state.js';
import { renderRouteOnMap, renderPicker, onRouteCreate, onRouteRemove, onRouteEdit, isRouteEditing, getPinnedRouteIndex } from './routes.js';

const STREET_STORAGE_KEY = 'zhilischnik_v45_streets';
export function persistStreets() {
  localStorage.setItem(STREET_STORAGE_KEY, JSON.stringify({ streets: STREETS.map(({ _layer, ...s }) => s) }));
}

function showToast(msg, type = 'info') {
  if (typeof window.toast === 'function') window.toast(msg, type);
  else console.log('Toast:', msg);
}

export function saveCurrentObject() {
  if (editingStreetIdx < 0 || !STREETS[editingStreetIdx]) {
    showToast('Сначала выберите объект в списке', 'error');
    return;
  }
  try {
    persistStreets();
    if (typeof window.saveData === 'function') window.saveData(false);
    showToast('Геометрия сохранена в браузере!', 'success');
    renderEditorStreets();
  } catch (e) {
    console.error('ОШИБКА СОХРАНЕНИЯ:', e);
    showToast('Ошибка: ' + e.message, 'error');
  }
}

export function loadStreetsFromStorage() {
  const raw = localStorage.getItem(STREET_STORAGE_KEY);
  if (raw) {
    try {
      const data = JSON.parse(raw);
      if (data.streets && Array.isArray(data.streets)) {
        // A complete saved list also preserves additions, removals, renames and order.
        STREETS.splice(0, STREETS.length, ...data.streets);
      }
    } catch(e) { console.error('Ошибка загрузки', e); }
  }
  renderStreetLayer();
}

const drawnLayers = new Map();
const drawnSignatures = new Map();
function updateStreetLayer(s, idx) {
  if (!streetLayerGroup) return;
  const signature = JSON.stringify([s.coords, s.extraPolygons, editingStreetIdx === idx, !!s.polygon]);
  if (drawnSignatures.get(s.name) === signature) {
    s._layer = drawnLayers.get(s.name)?.[0] || null;
    return;
  }
  (drawnLayers.get(s.name) || []).forEach(layer => streetLayerGroup.removeLayer(layer));
  const layers = [];
  const isEditing = editingStreetIdx === idx;
  const color = isEditing ? '#e74c3c' : (s.polygon || s.isYard ? getYardColor(s) : '#2980b9');
  const options = { color, weight: isEditing ? 4 : 2.5, opacity: isEditing ? 1 : 0.7,
    fillColor: color, fillOpacity: isEditing ? 0.3 : 0.1, pmIgnore: !isEditing };
  s._layer = null;
  [s.coords, ...(s.extraPolygons || [])].forEach((coords, shapeIdx) => {
    if (!Array.isArray(coords) || coords.length < 2) return;
    const poly = !!s.polygon && coords.length >= 3;
    const layer = poly ? L.polygon(coords, options) : L.polyline(coords, { ...options, fillOpacity: 0 });
    layer._streetName = s.name;
    layer._shapeIdx = shapeIdx;
    layer.on('mouseover', () => {
      const plates = Object.entries(rbRoutesByVehicle).filter(([plate, routes]) => {
        const idx = getPinnedRouteIndex(plate);
        return routes[idx]?.items?.some(item => item.name === s.name);
      }).map(([plate]) => plate);
      if (plates.length) layer.bindTooltip(esc(s.name) + ' · Техника: ' + plates.map(esc).join(', ')).openTooltip();
      else layer.unbindTooltip();
    });
    layer.addTo(streetLayerGroup);
    layers.push(layer);
    if (shapeIdx === 0) s._layer = layer;
  });
  drawnLayers.set(s.name, layers);
  drawnSignatures.set(s.name, signature);
}

export function renderStreetLayer() {
  if (!streetLayerGroup || !map) return;
  // Existing layers of unchanged streets remain on the map.
  STREETS.forEach(updateStreetLayer);
  for (const name of drawnLayers.keys()) {
    if (!STREETS.some(s => s.name === name)) {
      drawnLayers.get(name).forEach(layer => streetLayerGroup.removeLayer(layer));
      drawnLayers.delete(name);
      drawnSignatures.delete(name);
    }
  }
  renderRouteOnMap();
}

export function onGeomanCreate(e) {
  if (isRouteEditing()) { onRouteCreate(e); return; }
  if (editingStreetIdx < 0) {
    showToast('Сначала выберите объект в списке справа!', 'error');
    if (map) map.removeLayer(e.layer);
    return;
  }
  
  const s = STREETS[editingStreetIdx];
  if (!s) return;

  let coords = [];
  if (e.shape === 'Polygon' || e.shape === 'Rectangle') {
    const latlngs = e.layer.getLatLngs();
    coords = (Array.isArray(latlngs[0]) ? latlngs[0] : latlngs).map(ll => [ll.lat, ll.lng]);
  } else if (e.shape === 'Line' || e.shape === 'Polyline') {
    coords = e.layer.getLatLngs().map(ll => [ll.lat, ll.lng]);
  }

  if (coords.length < 2) { map.removeLayer(e.layer); return; }

  pushUndo('рисование ' + e.shape);
  if (!s.extraPolygons) s.extraPolygons = [];
  s.extraPolygons.push(coords);

  map.removeLayer(e.layer);
  
  updateStreetLayer(s, editingStreetIdx);
  renderRouteOnMap();
  renderEditorStreets();
  renderPicker();
  persistStreets();
  showToast('Фигура добавлена и сохранена', 'success');
}

export function onGeomanRemove(e) {
  if (e.layer._routeShape) { onRouteRemove(e); return; }
  const layer = e.layer;
  const s = STREETS.find(street => street.name === layer._streetName);
  if (!s || s !== STREETS[editingStreetIdx]) return;
  const shapeIdx = layer._shapeIdx;
  if (shapeIdx === 0 || shapeIdx > 0 && s.extraPolygons?.[shapeIdx - 1]) {
    pushUndo('удаление фигуры');
    if (shapeIdx === 0) s.coords = [];
    else s.extraPolygons.splice(shapeIdx - 1, 1);
    updateStreetLayer(s, editingStreetIdx);
    renderRouteOnMap();
    renderEditorStreets();
    renderPicker();
    persistStreets();
    showToast('Фигура удалена и сохранена', 'info');
  }
}

export function onGeomanEdit(e) {
  if (e.layer._routeShape) { onRouteEdit(e); return; }
  const layer = e.layer;
  const s = STREETS.find(street => street.name === layer._streetName);
  if (!s || s !== STREETS[editingStreetIdx]) return;
  const points = layer.getLatLngs();
  const coords = (Array.isArray(points[0]) ? points[0] : points).map(ll => [ll.lat, ll.lng]);
  if (coords.length < 2) return;
  const old = layer._shapeIdx === 0 ? s.coords : s.extraPolygons?.[layer._shapeIdx - 1];
  if (JSON.stringify(old) === JSON.stringify(coords)) return;
  pushUndo('изменение геометрии');
  if (layer._shapeIdx === 0) s.coords = coords;
  else s.extraPolygons[layer._shapeIdx - 1] = coords;
  updateStreetLayer(s, editingStreetIdx);
  renderRouteOnMap();
  renderEditorStreets();
  renderPicker();
  persistStreets();
  showToast('Геометрия изменена и сохранена', 'info');
}

function refreshObjects() {
  persistStreets();
  renderEditorStreets();
  renderStreetLayer();
  renderPicker();
  document.getElementById('ed-info').textContent = editingStreetIdx < 0 ?
    'Выберите объект из списка, чтобы изменить его геометрию.' : 'Выбран объект: ' + STREETS[editingStreetIdx].name;
}

export async function addEditorObject(polygon) {
  const name = (await requestText(polygon ? 'Название нового участка:' : 'Название новой улицы:'))?.trim();
  if (!name) return;
  if (STREETS.some(s => s.name.toLowerCase() === name.toLowerCase())) { await notify('Такое название уже есть.'); return; }
  pushUndo('добавление объекта');
  STREETS.push({ name, coords: [], polygon, isYard: polygon, extraPolygons: [], ...(polygon ? { area: '' } : {}) });
  setEditingStreetIdx(STREETS.length - 1);
  refreshObjects();
}

export async function renameEditorObject(idx) {
  const street = STREETS[idx];
  if (!street) return;
  const name = (await requestText('Новое название объекта:', street.name))?.trim();
  if (!name || name === street.name) return;
  if (STREETS.some((s, i) => i !== idx && s.name.toLowerCase() === name.toLowerCase())) { await notify('Такое название уже есть.'); return; }
  pushUndo('переименование объекта');
  const previous = street.name;
  Object.values(rbRoutesByVehicle).forEach(routes => routes?.forEach(route => route?.items?.forEach(item => {
    if (item.name === previous && isYardObject(street) === (item.type === 'yard')) item.name = name;
  })));
  street.name = name;
  // Remove old keyed layers so renaming cannot leave a ghost behind.
  refreshObjects();
  window.saveData?.(false);
  window.renderList?.();
  window.renderMiniRoute?.();
}

export async function deleteEditorObject(idx) {
  const street = STREETS[idx];
  if (!street || !await confirmAction('Удалить объект «' + street.name + '» из списка? Существующие маршруты останутся без изменений.')) return;
  pushUndo('удаление объекта');
  STREETS.splice(idx, 1);
  if (editingStreetIdx === idx) { map?.pm?.disableDraw(); setEditingStreetIdx(-1); }
  else if (editingStreetIdx > idx) setEditingStreetIdx(editingStreetIdx - 1);
  refreshObjects();
}

export function moveEditorObject(idx, direction) {
  const target = idx + direction;
  if (target < 0 || target >= STREETS.length) return;
  pushUndo('перемещение объекта');
  [STREETS[idx], STREETS[target]] = [STREETS[target], STREETS[idx]];
  if (editingStreetIdx === idx) setEditingStreetIdx(target);
  else if (editingStreetIdx === target) setEditingStreetIdx(idx);
  refreshObjects();
}

export function renderEditorStreets() {
  const search = (document.getElementById('ed-street-search')?.value || '').toLowerCase();
  const container = document.getElementById('ed-street-list');
  if (!container) return;
  container.innerHTML = '';
  
  STREETS.forEach((s, idx) => {
    if (search && s.name.toLowerCase().indexOf(search) < 0) return;
    const isEditing = editingStreetIdx === idx;
    
    let totalPts = (s.coords || []).length;
    if (s.extraPolygons) totalPts += s.extraPolygons.reduce((a, b) => a + b.length, 0);
    
    const item = document.createElement('div');
    item.className = 'ed-street-item' + (isEditing ? ' editing' : '');
    item.innerHTML = `<span class="name">${esc(s.name)}</span><span class="pts">${totalPts}т</span><span class="actions"></span>`;
    const actions = item.querySelector('.actions');
    for (const [label, title, handler, disabled] of [
      ['↑', 'Выше', () => moveEditorObject(idx, -1), idx === 0],
      ['↓', 'Ниже', () => moveEditorObject(idx, 1), idx === STREETS.length - 1],
      ['✎', 'Переименовать', () => renameEditorObject(idx), false],
      ['×', 'Удалить объект', () => deleteEditorObject(idx), false]
    ]) {
      const button = document.createElement('button');
      button.type = 'button'; button.textContent = label; button.title = title;
      button.setAttribute('aria-label', title + ' ' + s.name);
      button.disabled = disabled;
      button.addEventListener('click', e => { e.stopPropagation(); handler(); });
      actions.appendChild(button);
    }

    item.addEventListener('click', () => {
      setEditingStreetIdx(idx);
      renderEditorStreets();
      renderStreetLayer();
      
      if (s._layer && map) {
        map.fitBounds(s._layer.getBounds(), { padding: [50, 50], maxZoom: 16 });
      }
      
      const info = document.getElementById('ed-info');
      if (info) info.textContent = 'Выбран объект: ' + s.name;
    });
    container.appendChild(item);
  });
}

export function toggleEditor(streetIdx) {
  const panel = document.getElementById('editor-panel');
  if (panel) {
    if (typeof streetIdx === 'number') {
      panel.classList.add('open');
      setEditingStreetIdx(streetIdx);
    } else panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
      renderEditorStreets();
      renderStreetLayer();
      if (typeof streetIdx === 'number') {
        const s = STREETS[streetIdx];
        document.getElementById('ed-info').textContent = 'Выбран объект: ' + s.name;
        if (s._layer && map) map.fitBounds(s._layer.getBounds(), { padding: [50, 50], maxZoom: 16 });
      }
    } else {
      cancelEditing();
    }
  }
}

export async function clearEditorDraw() {
  if (editingStreetIdx < 0) return;
  if (!await confirmAction('Удалить ВСЕ фигуры (линии и полигоны) этого объекта?')) return;
  pushUndo('очистка');
  STREETS[editingStreetIdx].coords = [];
  STREETS[editingStreetIdx].extraPolygons = [];
  renderStreetLayer();
  renderEditorStreets();
  renderPicker();
  persistStreets();
  showToast('Все фигуры удалены', 'info');
}

export function cancelEditing() {
  map?.pm?.disableDraw();
  setEditingStreetIdx(-1);
  renderEditorStreets();
  renderStreetLayer();
  const info = document.getElementById('ed-info');
  if (info) info.textContent = 'Выберите объект из списка, чтобы изменить его геометрию.';
}

export function startDrawMode(mode) {
  if (!map || !map.pm) {
    showToast('Geoman не инициализирован', 'error');
    return;
  }
  if (editingStreetIdx < 0) {
    showToast('Сначала выберите объект из списка', 'error');
    return;
  }

  map.pm.disableDraw();

  if (mode === 'line') {
    map.pm.enableDraw('Line', { snappable: true, snapDistance: 20 });
    showToast('Рисование линии: кликайте по карте, завершите двойным кликом', 'info');
  } else if (mode === 'polygon') {
    map.pm.enableDraw('Polygon', { snappable: true, snapDistance: 20 });
    showToast('Рисование полигона: кликайте по карте, завершите кликом на первой точке', 'info');
  } else if (mode === 'stop') {
    showToast('Рисование отменено', 'info');
  }
}

export function toggleDrawingMode() { startDrawMode('line'); }
export function updateToolbarButtons() {}
export function saveEditedStreet() { saveCurrentObject(); }
export function addExtraLine() {}
export function toggleConnectMode() {}
export function handleConnectClick() {}
export function insertPointRelative() {}
export function deleteExtraLine() {}
export function clearThisLineGeometry() { clearEditorDraw(); }

