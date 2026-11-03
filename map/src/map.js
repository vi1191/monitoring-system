import * as L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';

import { onGeomanCreate, onGeomanRemove, onGeomanEdit } from './editor.js';
import { onRouteDragEnd } from './routes.js';
import { 
  setMap, setRouteLayerGroup, setYardLayerGroup, 
  setOverlapLayerGroup, setPreviewLayerGroup, setStreetLayerGroup
} from './state.js';

export function initMap() {
  const bounds = L.latLngBounds([55.620,37.425],[55.705,37.555]);
  const newMap = L.map('map', {zoomControl:true, maxBounds:bounds, maxBoundsViscosity:0.7, minZoom:12, maxZoom:19}).setView([55.655,37.485], 14);
  setMap(newMap);
  
  if (newMap.pm) {
    newMap.pm.setLang('ru');
    // Keep drawing controls, but do not obscure the map with the cursor hint.
    newMap.pm.setGlobalOptions({ tooltips: false });
    
    // Включаем кнопки: Линия, Полигон, Редактировать, Удалить
    newMap.pm.addControls({
      position: 'topleft',
      drawMarker: false,
      drawCircleMarker: false,
      drawPolyline: true,   // Линия
      drawPolygon: true,    // Полигон (должен быть включен)
      drawRectangle: false,
      drawCircle: false,
      drawText: false,
      editMode: true,
      dragMode: true,
      cutPolygon: false,
      removalMode: true,
      rotateMode: false,
      snappingOption: true,
    });
    const undoControl = L.control({ position: 'topleft' });
    undoControl.onAdd = () => {
      const wrapper = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
      const button = L.DomUtil.create('button', '', wrapper);
      button.id = 'undo-btn';
      button.type = 'button';
      button.textContent = '↶';
      button.title = 'Нечего отменять';
      button.disabled = true;
      button.style.cssText = 'width:30px;height:30px;background:white;border:0;cursor:pointer;font-size:21px;opacity:.4';
      L.DomEvent.disableClickPropagation(wrapper);
      L.DomEvent.on(button, 'click', () => window.undoLastAction());
      return wrapper;
    };
    undoControl.addTo(newMap);

    // Событие создания фигуры
    newMap.on('pm:create', (e) => {
      onGeomanCreate(e);
    });

    // Событие удаления фигуры
    newMap.on('pm:remove', (e) => {
      onGeomanRemove(e);
    });
    newMap.on('pm:edit', onGeomanEdit);
    newMap.on('pm:dragend', onRouteDragEnd);
  }

  const baseLayers = {
    'Схема': L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {subdomains:'abc', attribution:'&copy; OpenStreetMap France', maxZoom:20}),
    'Спутник': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {attribution:'&copy; Esri', maxZoom:19})
  };
  baseLayers['Схема'].addTo(newMap);
  L.control.layers(baseLayers, null, {position:'topright', collapsed:false}).addTo(newMap);

  const streetLg = L.layerGroup().addTo(newMap);
  const yardLg = L.layerGroup().addTo(newMap);
  const routeLg = L.layerGroup().addTo(newMap);
  const overlapLg = L.layerGroup().addTo(newMap);
  const previewLg = L.layerGroup().addTo(newMap);

  setStreetLayerGroup(streetLg);
  setYardLayerGroup(yardLg);
  setRouteLayerGroup(routeLg);
  setOverlapLayerGroup(overlapLg);
  setPreviewLayerGroup(previewLg);

  setTimeout(() => newMap.invalidateSize(), 200);
}