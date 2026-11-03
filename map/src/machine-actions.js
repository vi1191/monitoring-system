import { MACHINES, SUBTYPE_ORDER } from './data.js';
import { currentCategory, activeUchastok, selectedForShow, pushUndo } from './state.js';
import { renderList, getVisibleMachines } from './ui.js';
import { confirmAction, notify, requestText } from './dialogs.js';
import { saveData } from './ui-controls.js';
import { refreshRouteOnMap } from './routes.js';

let menuPlate = null;
let targetSubtype = null;

export function getMachineOverrides() {
  return MACHINES.map(({ plate, isODH, isDvory, area, subtype, group, photo }) => ({ plate, isODH, isDvory, area, subtype, group, photo }));
}

export function applyMachineOverrides(data) {
  if (Array.isArray(data.machineOverrides)) {
    const byPlate = new Map(MACHINES.map(m => [m.plate, m]));
    data.machineOverrides.forEach(o => {
      const m = byPlate.get(o.plate);
      if (!m) return;
      if (typeof o.isODH === 'boolean') m.isODH = o.isODH;
      if (typeof o.isDvory === 'boolean') m.isDvory = o.isDvory;
      if (typeof o.area === 'string') m.area = o.area;
      if (typeof o.subtype === 'string') m.subtype = o.subtype;
      if (typeof o.group === 'string') m.group = o.group;
      if (typeof o.photo === 'string') m.photo = o.photo;
    });
  }
  if (data.subtypeOrder && typeof data.subtypeOrder === 'object') {
    ['odh', 'dvory', 'other'].forEach(cat => {
      if (Array.isArray(data.subtypeOrder[cat])) {
        SUBTYPE_ORDER[cat] = data.subtypeOrder[cat].filter(s => typeof s === 'string');
      }
    });
  }
}

function refresh() { renderList(); refreshRouteOnMap(); saveData(false); }
function inCategory(m) { return currentCategory === 'odh' ? m.isODH : m.isDvory; }

export function openAddToCategory() {
  if (currentCategory === 'other' && activeUchastok === null) return;
  targetSubtype = null;
  document.getElementById('modal-title').textContent = currentCategory === 'other' ? 'Назначить технику участку' : 'Добавить в категорию «' + (currentCategory === 'odh' ? 'ОДХ' : 'Дворы') + '»';
  document.getElementById('modal-search').value = '';
  document.getElementById('modal-overlay').classList.add('open');
  renderModalList('');
}
export function openAddToSubtype(subtype) {
  if (currentCategory === 'other') {
    document.getElementById('modal-search').value = '';
    document.getElementById('modal-overlay').classList.add('open');
  } else openAddToCategory();
  targetSubtype = subtype;
  document.getElementById('modal-title').textContent = 'Добавить в подтип «' + subtype + '»';
  renderModalList('');
}

export function renderModalList(query = '') {
  const list = document.getElementById('modal-list');
  list.replaceChildren();
  const matches = MACHINES.filter(m => (targetSubtype ? (currentCategory === 'other' ? m.group !== targetSubtype : m.subtype !== targetSubtype) : currentCategory === 'other' ? m.area !== activeUchastok + 'уч' : !inCategory(m)) &&
    (m.plate + ' ' + m.model).toLowerCase().includes(query.toLowerCase().trim()));
  if (!matches.length) { list.textContent = 'Подходящей техники нет'; return; }
  matches.forEach(m => {
    const row = document.createElement('div');
    row.className = 'copy-item';
    row.textContent = m.plate + ' · ' + (m.model || '');
    row.onclick = () => {
      pushUndo('добавление в категорию');
      if (currentCategory === 'odh') m.isODH = true;
      else if (currentCategory === 'dvory') m.isDvory = true;
      else if (activeUchastok !== null && !targetSubtype) m.area = activeUchastok + 'уч';
      if (targetSubtype) {
        if (currentCategory === 'other') m.group = targetSubtype;
        else m.subtype = targetSubtype;
      }
      refresh();
      renderModalList(document.getElementById('modal-search').value);
    };
    list.appendChild(row);
  });
}

export async function removeFromCategory() {
  if (currentCategory === 'other' && activeUchastok === null) return;
  const machines = getVisibleMachines().filter(m => selectedForShow.has(m.plate) && (currentCategory === 'other' || inCategory(m)));
  if (!machines.length) { await notify('Отметьте технику в текущей выдаче.'); return; }
  if (!await confirmAction('Убрать отмеченные машины (' + machines.length + ') из категории?')) return;
  pushUndo('удаление из категории');
  machines.forEach(m => {
    if (currentCategory === 'odh') m.isODH = false;
    else if (currentCategory === 'dvory') m.isDvory = false;
    else m.area = '';
    selectedForShow.delete(m.plate);
  });
  refresh();
}
export function removeFromSubtype(plate) {
  const m = MACHINES.find(m => m.plate === plate);
  if (!m || !(currentCategory === 'other' ? m.group : m.subtype)) return;
  pushUndo('удаление из подтипа');
  if (currentCategory === 'other') m.group = '';
  else m.subtype = '';
  refresh();
}

export function showSubtypeMenu(plate, x, y) {
  menuPlate = plate;
  const menu = document.getElementById('subtype-context-menu');
  const items = document.getElementById('scm-items');
  items.replaceChildren();
  [...new Set([...SUBTYPE_ORDER[currentCategory] || [], ...MACHINES.map(m => m.subtype).filter(Boolean)])].forEach(name => {
    const row = document.createElement('div');
    row.textContent = name;
    row.style.cssText = 'padding:5px 12px;cursor:pointer;font-size:12px';
    row.onclick = () => scmAssignSubtype(name);
    items.appendChild(row);
  });
  document.getElementById('scm-new-input').value = '';
  menu.style.display = 'block';
  menu.style.left = Math.max(0, Math.min(x, window.innerWidth - menu.offsetWidth)) + 'px';
  menu.style.top = Math.max(0, Math.min(y, window.innerHeight - menu.offsetHeight)) + 'px';
}

function changeSubtype(name) {
  const m = MACHINES.find(m => m.plate === menuPlate);
  if (!m) return;
  pushUndo('изменение подтипа');
  m.subtype = name;
  document.getElementById('subtype-context-menu').style.display = 'none';
  refresh();
}

export function scmAssignSubtype(name) { changeSubtype(name); }
export async function scmCreateNew() {
  const name = document.getElementById('scm-new-input').value.trim();
  if (!name) { await notify('Введите название подтипа.'); return; }
  changeSubtype(name);
  if (!SUBTYPE_ORDER[currentCategory].includes(name)) SUBTYPE_ORDER[currentCategory].push(name);
  saveData(false);
}
export function scmRemoveSubtype() { changeSubtype(''); }

export async function renameSubtype(subtype, machines) {
  const name = (await requestText('Новое название подтипа:', subtype))?.trim();
  if (!name || name === subtype) return;
  pushUndo('переименование подтипа');
  machines.forEach(m => { m.subtype = name; });
  const order = SUBTYPE_ORDER[currentCategory];
  const idx = order.indexOf(subtype);
  if (idx >= 0) order[idx] = name;
  refresh();
}

document.addEventListener('click', e => {
  if (!e.target.closest('#subtype-context-menu, .card-more')) {
    document.getElementById('subtype-context-menu')?.style.setProperty('display', 'none');
  }
});