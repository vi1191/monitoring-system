import assert from 'node:assert/strict';
import { getDistance, analyzeWsData } from './ws-analysis.js';

const config = {
    BASE_LAT: 55.673,
    BASE_LON: 37.455,
    MAX_DISTANCE_KM: 100,
    MAX_SPEED_KMH: 150,
};

const farCoords = [56.673, 37.455];
const farDistance = getDistance(config.BASE_LAT, config.BASE_LON, ...farCoords);
assert.ok(farDistance > config.MAX_DISTANCE_KM);
assert.equal(getDistance(null, config.BASE_LON, ...farCoords), 0);

const wsData = {
    fast: [{ speed: 200, coords: [55.673, 37.455] }],
    far: [{ speed: 40, coords: farCoords }],
    normal: [{ speed: 50, coords: [55.674, 37.456] }],
};

assert.equal(analyzeWsData({ fast: wsData.fast }, config), 'Срыв трека (скорость 200 км/ч)');
assert.equal(analyzeWsData({ far: wsData.far }, config),
    `Машина далеко от базы (${farDistance.toFixed(1)} км)`);
assert.equal(analyzeWsData({ normal: wsData.normal }, config), '');
assert.equal(analyzeWsData(wsData, config),
    `Срыв трека (скорость 200 км/ч); Машина далеко от базы (${farDistance.toFixed(1)} км)`);
assert.equal(analyzeWsData({}, config), '');
assert.equal(analyzeWsData({ broken: [null, {}, { coords: [null, 37] }], empty: null }, config), '');

console.log('Проверки WebSocket-анализа пройдены.');