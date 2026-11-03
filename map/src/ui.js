// src/ui.js
import { MACHINES, SUBTYPE_ORDER } from './data.js';
import { esc, escAttr } from './utils.js';
import { requestText, notify } from './dialogs.js';
import { saveData } from './ui-controls.js';
import { clearMachineFilters } from './ui-controls.js';
import { openAddToSubtype, removeFromSubtype } from './machine-actions.js';
import { setHoveredRoutePlate, setHoveredRouteCategory, setHoveredRouteArea, togglePinnedRouteCategory, getPinnedRouteIndex, pinVehicleRoute, renderRouteOnMap } from './routes.js';
import { 
  currentCategory, activeUchastok, selectedForShow, 
  routeFilterActive, explicitlyExpanded, subtypesCollapsedByDefault,
  collapsedSubtypes, activeVehicle, hoveredVehicle, setHoveredVehicle,
  getBaseColor, setCurrentCategory, rbRoutesByVehicle
} from './state.js';

// === ВЫЗОВ СТАРЫХ ФУНКЦИЙ ИЗ index.html ===
export function toggleForShow(plate) { if (typeof window.toggleForShow === 'function') window.toggleForShow(plate); }
export function openMiniRoute(plate) { if (typeof window.openMiniRoute === 'function') window.openMiniRoute(plate); }
export function showSubtypeMenu(plate, x, y) { if (typeof window.showSubtypeMenu === 'function') window.showSubtypeMenu(plate, x, y); }
export function renameSubtype(subtype, machines, triggerEl) { if (typeof window.renameSubtype === 'function') window.renameSubtype(subtype, machines, triggerEl); }
export function highlightVehicleOnMap(plate) { if (typeof window.highlightVehicleOnMap === 'function') window.highlightVehicleOnMap(plate); }

// === РЕАЛЬНАЯ hasAnyItems ===
export function hasAnyItems(plate) {
  return (rbRoutesByVehicle[plate] || []).some(r => r?.items?.length > 0);
}

// === РЕАЛЬНАЯ updateCategoryCounts ===
export function updateCategoryCounts() {
  const odh = document.getElementById('cnt-odh');
  const dvo = document.getElementById('cnt-dvory');
  const oth = document.getElementById('cnt-other');
  if (odh) odh.textContent = MACHINES.filter(m => m.isODH).length;
  if (dvo) dvo.textContent = MACHINES.filter(m => m.isDvory).length;
  if (oth) oth.textContent = MACHINES.length;
}

// === ОСНОВНАЯ renderList ===
export function getVisibleMachines() {
  const search = (document.getElementById('search').value || '').toLowerCase();
  let catMachines = getCategoryMachines(currentCategory);
  if (activeUchastok !== null) catMachines = catMachines.filter(m => m.area === activeUchastok + 'уч');
  if (routeFilterActive) catMachines = catMachines.filter(m => hasAnyItems(m.plate));

  return catMachines.filter(m => {
    if (search && m.plate.toLowerCase().indexOf(search) < 0 && (m.model || '').toLowerCase().indexOf(search) < 0 && (m.vid || '').toLowerCase().indexOf(search) < 0 && (m.subtype || '').toLowerCase().indexOf(search) < 0) return false;
    return true;
  });
}

export function renderList() {
  const filtered = getVisibleMachines();
  document.getElementById('total-count').textContent = MACHINES.length;
  document.getElementById('on-route-count').textContent = 'С маршрутом: ' + MACHINES.filter(m => hasAnyItems(m.plate)).length;
  document.getElementById('shown-count').textContent = filtered.length;
  const all = document.querySelector('.btn-all');
  if (all) {
    const selected = filtered.filter(m => selectedForShow.has(m.plate)).length;
    all.textContent = selected === filtered.length && filtered.length ? '☐ Снять с найденных' : '☑️ Выбрать найденные';
    all.disabled = !filtered.length;
    all.title = `Отмечено ${selected} из ${filtered.length} найденных (включая свёрнутые группы)`;
  }

  const list = document.getElementById('machine-list');
  document.querySelectorAll('.cat-actions .btn-add, .cat-actions .btn-rem').forEach(el => {
    el.disabled = currentCategory === 'other' && activeUchastok === null;
    el.title = currentCategory === 'other' ? 'Сначала выберите участок 1–6' : 'Добавить или убрать технику';
  });
  list.innerHTML = '';
  if (filtered.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'list-empty';
    empty.textContent = document.getElementById('search').value ? 'По запросу и выбранным фильтрам ничего не найдено.' : routeFilterActive ? 'Нет техники с маршрутом по выбранным фильтрам.' : 'В этой категории или на участке нет техники.';
    const reset = document.createElement('button');
    reset.type = 'button';
    reset.textContent = 'Сбросить фильтры';
    reset.onclick = () => { document.getElementById('search').value = ''; window.clearMachineFilters(); };
    empty.appendChild(reset);
    list.appendChild(empty);
    updateCategoryCounts();
    return;
  }

  const groups = {};
  const noSubtype = [];
  const order = SUBTYPE_ORDER[currentCategory] || [];
  filtered.forEach(m => {
    const st = (currentCategory === 'other' && m.group) ? m.group : m.subtype;
    if (st) { if (!groups[st]) groups[st] = []; groups[st].push(m); }
    else noSubtype.push(m);
  });

  order.forEach(subtype => {
    if (groups[subtype] && groups[subtype].length > 0) { renderSubtypeGroup(subtype, groups[subtype], list); delete groups[subtype]; }
  });
  Object.keys(groups).forEach(subtype => renderSubtypeGroup(subtype, groups[subtype], list));
  if (noSubtype.length > 0) renderSubtypeGroup('', noSubtype, list, true);
  updateCategoryCounts();
}

function getCategoryMachines(cat) {
  if (cat === 'odh') return MACHINES.filter(m => m.isODH);
  if (cat === 'dvory') return MACHINES.filter(m => m.isDvory);
  return MACHINES;
}

function renderSubtypeGroup(subtype, machines, container, isNoSubtype) {
  const groupKey = currentCategory + '#' + (subtype || '__none__');
  const isCollapsed = subtypesCollapsedByDefault ? !explicitlyExpanded.has(groupKey) : collapsedSubtypes.has(groupKey);
  const groupDiv = document.createElement('div');
  groupDiv.className = 'subtype-group';

  const header = document.createElement('div');
  header.className = 'subtype-header' + (isNoSubtype ? ' no-subtype' : '');
  header.setAttribute('role', 'button');
  header.tabIndex = 0;
  header.setAttribute('aria-expanded', String(!isCollapsed));
  if (!isNoSubtype) header.dataset.subtype = subtype;
  header.innerHTML = '<span class="arrow">' + (isCollapsed ? '▶' : '▼') + '</span>' +
    '<span class="st-name">' + esc(isNoSubtype ? 'БЕЗ ПОДТИПА' : subtype) + '</span>' +
    '<span class="st-count">' + machines.length + '</span>' +
    (isNoSubtype || currentCategory === 'other' ? '' : '<button type="button" class="st-edit" title="Переименовать подтип" aria-label="Переименовать подтип ' + escAttr(subtype) + '">✏️</button>');
  header.onclick = () => {
    if (subtypesCollapsedByDefault) {
      if (isCollapsed) explicitlyExpanded.add(groupKey);
      else explicitlyExpanded.delete(groupKey);
    } else {
      if (isCollapsed) collapsedSubtypes.delete(groupKey);
      else collapsedSubtypes.add(groupKey);
    }
    renderList();
  };
  header.onkeydown = e => { if (e.target === header && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); header.click(); } };
  if (!isNoSubtype && currentCategory !== 'other') {
    header.ondblclick = (e) => { e.stopPropagation(); renameSubtype(subtype, machines, e.currentTarget); };
    const editBtn = header.querySelector('.st-edit');
    if (editBtn) editBtn.onclick = (e) => { e.stopPropagation(); renameSubtype(subtype, machines, e.currentTarget); };
  }
  groupDiv.appendChild(header);

  if (!isCollapsed) {
    const body = document.createElement('div');
    body.className = 'subtype-body';
    machines.forEach(m => body.appendChild(createMachineCard(m)));
    if (!isNoSubtype) {
      const add = document.createElement('button');
      add.type = 'button'; add.className = 'subtype-add'; add.textContent = '➕ Добавить технику в подтип';
      add.onclick = () => openAddToSubtype(subtype);
      body.appendChild(add);
    }
    groupDiv.appendChild(body);
  }
  container.appendChild(groupDiv);
}

function createMachineCard(m) {
  const hasRoutes = hasAnyItems(m.plate);
  const baseColor = hasRoutes ? getBaseColor(m.plate) : null;
  const isChecked = selectedForShow.has(m.plate);
  const isActive = activeVehicle === m.plate;
  const photo = m.photo && typeof m.photo === 'string' ? m.photo : '';
  const modelText = (m.model || '').toString();

  const card = document.createElement('div');
  card.className = 'machine-card' + (isActive ? ' active' : '') + (hasRoutes ? ' has-route' : '');
  card.dataset.plate = m.plate;
  if (baseColor) card.style.borderLeftColor = baseColor;

  card.innerHTML =
    (photo ? '<img class="tech-icon" src="' + escAttr(photo) + '" alt="" onerror="this.style.display=\'none\'" />' : '') +
    '<input type="checkbox" class="chk" aria-label="Выбрать ' + escAttr(m.plate) + '" ' + (isChecked ? 'checked' : '') + ' />' +
    (baseColor ? '<span class="color-dot" style="background:' + baseColor + ';"></span>' : '') +
    '<div class="card-content">' +
      '<div class="plate">' + esc(m.plate) + (hasRoutes ? '<span class="route-badge">● маршрут</span>' : '') + '</div>' +
      '<div class="model">' + esc(modelText) + (m.year ? ' (' + esc(m.year) + ')' : '') + '</div>' +
      '<div class="meta"><span>' + esc(m.area || '') + '</span><span class="badge">' + esc(m.cat_b || '') + '</span></div>' +
    '</div>' +
    '<button type="button" class="card-photo-url" title="Изменить фото по ссылке" aria-label="Изменить фото ' + escAttr(m.plate) + ' по ссылке">🔗</button>' +
    '<button type="button" class="card-photo-file" title="Загрузить фото с устройства" aria-label="Загрузить фото ' + escAttr(m.plate) + '">📷</button>' +
    '<button class="card-more" title="Действия">⋯</button>';
  if (currentCategory === 'other' ? m.group : m.subtype) {
    const remove = document.createElement('button');
    remove.type = 'button'; remove.className = 'card-remove-subtype';
    remove.textContent = '− подтип'; remove.title = 'Убрать из подтипа';
    remove.onclick = e => { e.stopPropagation(); removeFromSubtype(m.plate); };
    card.querySelector('.card-content').appendChild(remove);
  }

  if (hasRoutes) {
    const picker = document.createElement('select');
    picker.className = 'card-route-select';
    picker.setAttribute('aria-label', 'Закреплённый маршрут ' + m.plate);
    (rbRoutesByVehicle[m.plate] || []).forEach((route, idx) => {
      if (!route?.items?.length) return;
      const option = document.createElement('option');
      option.value = String(idx);
      option.textContent = route.name || 'М' + (idx + 1);
      picker.appendChild(option);
    });
    picker.value = String(getPinnedRouteIndex(m.plate));
    picker.onclick = e => e.stopPropagation();
    picker.onchange = e => { e.stopPropagation(); pinVehicleRoute(m.plate, Number(picker.value)); };
    card.querySelector('.card-content').appendChild(picker);
  }

  const chk = card.querySelector('.chk');
  chk.onclick = (e) => { e.stopPropagation(); toggleForShow(m.plate); };
  card.onclick = (e) => { if (e.target.closest('input, button, select')) return; openMiniRoute(m.plate); };
  const changePhoto = async (value) => {
    const old = m.photo;
    m.photo = value;
    if (!saveData(false)) { m.photo = old; return; }
    renderList();
  };
  card.querySelector('.card-photo-url').onclick = async (e) => {
    e.stopPropagation();
    const value = await requestText('Ссылка на фото (пустое поле уберёт фото):', m.photo?.startsWith('data:') ? '' : m.photo || '');
    if (value === null) return;
    const url = value.trim();
    if (url && !/^https?:\/\//i.test(url)) { await notify('Укажите ссылку http:// или https://'); return; }
    await changePhoto(url);
  };
  card.querySelector('.card-photo-file').onclick = (e) => {
    e.stopPropagation();
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'image/*';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) { await notify('Выберите файл изображения.'); return; }
      if (file.size > 800000) { await notify('Изображение слишком большое для хранения в браузере (максимум 800 КБ).'); return; }
      const reader = new FileReader();
      reader.onload = () => changePhoto(reader.result);
      reader.onerror = () => notify('Не удалось прочитать изображение.');
      reader.readAsDataURL(file);
    };
    input.click();
  };
  card.oncontextmenu = (e) => { if (currentCategory !== 'other') { e.preventDefault(); showSubtypeMenu(m.plate, e.clientX, e.clientY); } };
  const more = card.querySelector('.card-more');
  if (currentCategory === 'other') more.remove();
  else more.onclick = (e) => { e.stopPropagation(); showSubtypeMenu(m.plate, e.clientX, e.clientY); };

  card.addEventListener('mouseenter', () => {
    if (hasRoutes) {
      setHoveredVehicle(m.plate);
      setHoveredRoutePlate(m.plate);
      highlightVehicleOnMap(m.plate);
    }
  });
  card.addEventListener('mouseleave', () => {
    if (hoveredVehicle === m.plate) {
      setHoveredVehicle(null);
      setHoveredRoutePlate(null);
      highlightVehicleOnMap(null);
    }
  });

  const photoImg = card.querySelector('.tech-icon');
  if (photoImg) {
    photoImg.addEventListener('click', function(e) {
      e.stopPropagation();
      if (!this.src) return;
      const overlay = document.createElement('div');
      overlay.className = 'photo-overlay';
      const bigImg = document.createElement('img');
      bigImg.src = this.src;
      overlay.appendChild(bigImg);
      overlay.addEventListener('click', function() { this.classList.remove('show'); setTimeout(() => this.remove(), 200); });
      document.body.appendChild(overlay);
      requestAnimationFrame(() => overlay.classList.add('show'));
    });
  }

  return card;
}

export function setCategory(cat, pin = true) {
  if (cat !== currentCategory && activeUchastok !== null) clearMachineFilters();
  if (pin) togglePinnedRouteCategory(cat);
  setCurrentCategory(cat);
  document.querySelectorAll('.cat-tab').forEach(el => el.classList.toggle('active', el.dataset.cat === cat));
  document.querySelectorAll('.cat-tab').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.cat === cat)));
  renderList();
  renderRouteOnMap();
}
export function bindCategoryRouteHover() {
  document.querySelectorAll('.cat-tab').forEach(tab => {
    tab.addEventListener('mouseenter', () => setHoveredRouteCategory(tab.dataset.cat));
    tab.addEventListener('mouseleave', () => setHoveredRouteCategory(null));
  });
  document.querySelectorAll('.uch-btn').forEach(button => {
    button.addEventListener('mouseenter', () => setHoveredRouteArea(button.dataset.u + 'уч'));
    button.addEventListener('mouseleave', () => setHoveredRouteArea(null));
  });
}
export function onSearchInput() { renderList(); }