// Функция для расчета расстояния (формула гаверсинуса)
export function getDistance(lat1, lon1, lat2, lon2) {
    if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) {
        return 0;
    }
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

export function analyzeWsData(wsData, config) {
    let speedReason = "";
    let distanceReason = "";

    for (const points of Object.values(wsData || {})) {
        if (!Array.isArray(points)) continue;
        for (const p of points) {
            console.log('WebSocket точка:', { speed: p?.speed, coords: p?.coords });
            if (!p || typeof p !== 'object') continue;

            if (!speedReason && typeof p.speed === 'number' &&
                Number.isFinite(p.speed) && p.speed > config.MAX_SPEED_KMH) {
                speedReason = `Срыв трека (скорость ${p.speed} км/ч)`;
            }
            if (!distanceReason && Array.isArray(p.coords) && p.coords.length === 2 &&
                p.coords.every(coord => typeof coord === 'number' && Number.isFinite(coord))) {
                const dist = getDistance(config.BASE_LAT, config.BASE_LON, p.coords[0], p.coords[1]);
                if (dist > config.MAX_DISTANCE_KM) {
                    distanceReason = `Машина далеко от базы (${dist.toFixed(1)} км)`;
                }
            }
        }
    }

    return [speedReason, distanceReason].filter(Boolean).join('; ');
}