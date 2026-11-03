// src/state.js
import { hslToHex, inferAreaFromName } from './utils.js';
import { MACHINES, SUBTYPE_ORDER, YARD_BOUNDARIES, STREETS, setStreets } from './data.js';

// === ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ===
export let currentCategory = 'dvory';
export let activeUchastok = null;
export let pinnedRouteIndexByVehicle = {};
export let rbRoutesByVehicle = {};
export let activeRouteIndex = 0;
export let activeVehicle = null;
export let map;
export let routeLayerGroup = null;
export let yardLayerGroup = null;
export let overlapLayerGroup = null;
export let previewLayerGroup = null;
export let streetLayerGroup = null;
export let routeLayersByPlate = new Map();
export let miniRouteVehicle = null;
export let pickerVehicle = null;
export let saveTimer = null;
export let selectedForShow = new Set();
export let editorOpen = false;
export let routeFilterActive = false;
export let showMode = 'active';
export let showOverlaps = false;

export let editingStreetIdx = -1;
export let editingObjectOnMap = null;
export let editingHandles = [];
export let editObjectMode = false;
export let editingExtraLayers = [];
export let drawingMode = false;
export let connectMode = false;
export let connectSource = null;
export let connectSourceMarker = null;

export let collapsedSubtypes = new Set();
export let subtypesCollapsedByDefault = true;
export let explicitlyExpanded = new Set();
export let sidebarExpanded = false;

export let editMode = false;
export let history = [];
export let searchDebounceTimer = null;
export let lastSaveTime = null;

export let undoStack = [];
export let undoInProgress = false;

export let hoveredVehicle = null;

// === СЕТТЕРЫ ===
export function setCurrentCategory(v) { currentCategory = v; }
export function setActiveUchastok(v) { activeUchastok = v; }
export function setPinnedRouteIndexByVehicle(v) { pinnedRouteIndexByVehicle = v; }
export function setRbRoutesByVehicle(v) { rbRoutesByVehicle = v; }
export function setActiveRouteIndex(v) { activeRouteIndex = v; }
export function setActiveVehicle(v) { activeVehicle = v; }
export function setMap(v) { map = v; }
export function setRouteLayerGroup(v) { routeLayerGroup = v; }
export function setYardLayerGroup(v) { yardLayerGroup = v; }
export function setOverlapLayerGroup(v) { overlapLayerGroup = v; }
export function setPreviewLayerGroup(v) { previewLayerGroup = v; }
export function setStreetLayerGroup(v) { streetLayerGroup = v; }
export function setRouteLayersByPlate(v) { routeLayersByPlate = v; }
export function setMiniRouteVehicle(v) { miniRouteVehicle = v; }
export function setPickerVehicle(v) { pickerVehicle = v; }
export function setSaveTimer(v) { saveTimer = v; }
export function setSelectedForShow(v) { selectedForShow = v; }
export function setEditorOpen(v) { editorOpen = v; }
export function setRouteFilterActive(v) { routeFilterActive = v; }
export function setShowMode(v) { showMode = v; }
export function setShowOverlaps(v) { showOverlaps = v; }
export function setEditingStreetIdx(v) { editingStreetIdx = v; }
export function setEditingObjectOnMap(v) { editingObjectOnMap = v; }
export function setEditingHandles(v) { editingHandles = v; }
export function setEditObjectMode(v) { editObjectMode = v; }
export function setEditingExtraLayers(v) { editingExtraLayers = v; }
export function setDrawingMode(v) { drawingMode = v; }
export function setConnectMode(v) { connectMode = v; }
export function setConnectSource(v) { connectSource = v; }
export function setConnectSourceMarker(v) { connectSourceMarker = v; }
export function setCollapsedSubtypes(v) { collapsedSubtypes = v; }
export function setSubtypesCollapsedByDefault(v) { subtypesCollapsedByDefault = v; }
export function setExplicitlyExpanded(v) { explicitlyExpanded = v; }
export function setSidebarExpanded(v) { sidebarExpanded = v; }
export function setEditMode(v) { editMode = v; }
export function setHistory(v) { history = v; }
export function setSearchDebounceTimer(v) { searchDebounceTimer = v; }
export function setLastSaveTime(v) { lastSaveTime = v; }
export function setUndoStack(v) { undoStack = v; }
export function setUndoInProgress(v) { undoInProgress = v; }
export function setHoveredVehicle(v) { hoveredVehicle = v; }

// === КОНСТАНТЫ ===
export const CATEGORY_LABELS = { odh: "ОДХ", dvory: "Дворы", other: "Вся техника" };
export const ROUTE_SHADES = [0, 15, 30, 45, 60];
export const MAX_UNDO = 30;
export const STORAGE_KEY = 'zhilischnik_v45';
export const METERS_PER_DEG_LAT = 111320;
export const DASH_PATTERNS = ['12,6', '6,4', '2,4', '16,4,2,4', '8,3'];
export const LINE_SPACING_M = 5;

// === ЦВЕТА ===
const _colorCache = new Map();

export function getBaseColor(plate) {
  if (_colorCache.has(plate)) return _colorCache.get(plate);
  let hash = 0;
  for (let i = 0; i < plate.length; i++) hash = ((hash << 5) - hash + plate.charCodeAt(i)) | 0;
  const hue = Math.abs(hash) % 360;
  const color = hslToHex(hue, 65, 50);
  _colorCache.set(plate, color);
  return color;
}

export function getRouteColor(plate, routeIdx) {
  if (routeIdx === undefined || routeIdx === null) return getBaseColor(plate);
  let hash = 0;
  for (const ch of plate) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return hslToHex((hash * 137.508 + routeIdx * 71) % 360, 76, 41);
}

export function getUchastokColor(area) {
  const c = {'1уч': '#e74c3c', '2уч': '#2980b9', '3уч': '#27ae60', '4уч': '#e67e22', '5уч': '#8e44ad', '6уч': '#1abc9c'};
  return c[area] || null;
}

export function getYardColor(s) {
  let c = s.area ? getUchastokColor(s.area) : null;
  if (!c && s.name) {
    const inferred = inferAreaFromName(s.name);
    if (inferred) c = getUchastokColor(inferred);
  }
  return c || '#8e44ad';
}

// === UNDO ===
export function snapshotState() {
  return {
    rbRoutesByVehicle: JSON.parse(JSON.stringify(rbRoutesByVehicle)),
    pinnedRouteIndexByVehicle: { ...pinnedRouteIndexByVehicle },
    streets: JSON.parse(JSON.stringify(STREETS.map(({ _layer, ...street }) => street))),
    yardBoundaries: JSON.parse(JSON.stringify(YARD_BOUNDARIES)),
    subtypeOrder: JSON.parse(JSON.stringify(SUBTYPE_ORDER)),
    overrides: MACHINES.map(m => ({plate: m.plate, isODH: m.isODH, isDvory: m.isDvory, area: m.area, subtype: m.subtype, group: m.group}))
  };
}

export function updateUndoButton() {
  const btn = document.getElementById('undo-btn');
  if (!btn) return;
  if (undoStack.length === 0) {
    btn.disabled = true;
    btn.style.opacity = '0.4';
    btn.title = 'Нечего отменять';
  } else {
    btn.disabled = false;
    btn.style.opacity = '1';
    const last = undoStack[undoStack.length - 1];
    btn.title = 'Отменить: ' + (last.label || 'действие') + ' (' + undoStack.length + ')';
  }
}

export function pushUndo(label) {
  if (undoInProgress) return;
  undoStack.push({ label, snap: snapshotState(), time: new Date() });
  if (undoStack.length > MAX_UNDO) undoStack.shift();
  updateUndoButton();
}

export function restoreSnapshot(snap) {
  undoInProgress = true;
  try {
    rbRoutesByVehicle = JSON.parse(JSON.stringify(snap.rbRoutesByVehicle));
    pinnedRouteIndexByVehicle = { ...(snap.pinnedRouteIndexByVehicle || {}) };
    if (snap.streets) setStreets(JSON.parse(JSON.stringify(snap.streets)));
    Object.keys(YARD_BOUNDARIES).forEach(k => delete YARD_BOUNDARIES[k]);
    Object.keys(snap.yardBoundaries).forEach(k => { YARD_BOUNDARIES[k] = snap.yardBoundaries[k]; });
    Object.keys(SUBTYPE_ORDER).forEach(k => delete SUBTYPE_ORDER[k]);
    Object.keys(snap.subtypeOrder).forEach(k => { SUBTYPE_ORDER[k] = snap.subtypeOrder[k]; });
    snap.overrides.forEach(o => {
      const m = MACHINES.find(x => x.plate === o.plate);
      if (m) { m.isODH = o.isODH; m.isDvory = o.isDvory; m.area = o.area; m.subtype = o.subtype; m.group = o.group; }
    });
  } finally {
    undoInProgress = false;
  }
}