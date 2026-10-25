/* Live weather: polls /api/weather every minute (the server caches Open-Meteo for 10 minutes).
   - User dashboard: details for the selected district + temperature heat-map tiles (click to select).
   - Expert dashboard: temperature heat-map tiles + a coordinate "weather map" bubble chart. */
(() => {
    const M = window.MaizeCharts;
    const root = document.getElementById('weather-panel') || document.getElementById('weather');
    if (!root || !M) return;

    const { el, makeChart, setData, TEXT } = M;
    const POLL_MS = 60000;
    const tilesBox = el('wx-tiles');
    const statusPill = el('wx-status');
    const selectedBox = el('wx-selected');
    const districtLabel = el('wx-district');
    const areaSelect = el('Area');
    let latest = null;

    /* cold (blue) -> hot (red-orange) */
    const heat = (temp, lo, hi) => {
        const k = hi > lo ? (temp - lo) / (hi - lo) : 0.5;
        return { colour: `hsl(${210 - k * 195} 65% 42%)`, k };
    };
    const num = (v, digits = 1) => (v == null ? '\u2013' : Number(v).toFixed(digits));

    /* Bubble "map": x = longitude, y = latitude, labels drawn next to each bubble. */
    const labelPlugin = {
        id: 'districtLabels',
        afterDatasetsDraw(chart) {
            const { ctx } = chart;
            const meta = chart.getDatasetMeta(0);
            ctx.save();
            ctx.fillStyle = '#10331a';
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'center';
            meta.data.forEach((point, i) => {
                const raw = chart.data.datasets[0].data[i];
                if (raw) ctx.fillText(raw.area, point.x, point.y - point.options.radius - 4);
            });
            ctx.restore();
        },
    };
    const map = makeChart('wx-map', {
        type: 'bubble', data: { datasets: [] }, plugins: [labelPlugin],
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                x: { title: { display: true, text: 'Longitude (\u00b0E)', color: TEXT }, ticks: { color: TEXT }, grace: '8%' },
                y: { title: { display: true, text: 'Latitude (\u00b0)', color: TEXT }, ticks: { color: TEXT }, grace: '8%' },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (c) => `${c.raw.area}: ${num(c.raw.temp)} \u00b0C, ${c.raw.summary}, wind ${num(c.raw.wind, 0)} km/h`,
                    },
                },
            },
        },
    });

    const selectedArea = () => (areaSelect ? areaSelect.value : null);

    const renderSelected = () => {
        if (!latest || !selectedBox) return;
        const d = latest.districts.find((x) => x.area === selectedArea());
        if (districtLabel && d) districtLabel.textContent = d.area;
        if (!d) { selectedBox.textContent = '\u2013'; return; }
        const item = (value, label) => {
            const wrap = document.createElement('div');
            wrap.className = 'wx-item';
            const big = document.createElement('span');
            big.textContent = value;
            const small = document.createElement('small');
            small.textContent = label;
            wrap.append(big, small);
            return wrap;
        };
        const main = document.createElement('div');
        main.className = 'wx-item';
        const big = document.createElement('span');
        big.className = 'wx-big';
        big.textContent = `${num(d.temp)} \u00b0C`;
        const sm = document.createElement('small');
        sm.textContent = d.summary;
        main.append(big, sm);
        selectedBox.replaceChildren(main, item(`${num(d.humidity, 0)} %`, 'humidity'), item(`${num(d.wind, 0)} km/h`, 'wind'),
            item(`${num(d.rain)} mm`, 'rain right now'));
    };

    const renderTiles = () => {
        if (!latest || !tilesBox) return;
        const temps = latest.districts.map((d) => d.temp).filter((v) => v != null);
        const lo = Math.min(...temps);
        const hi = Math.max(...temps);
        const fragment = document.createDocumentFragment();
        latest.districts.forEach((d) => {
            const tile = document.createElement('div');
            tile.className = 'tile' + (d.area === selectedArea() ? ' selected' : '');
            tile.style.backgroundColor = d.temp == null ? '#999' : heat(d.temp, lo, hi).colour;
            tile.style.color = '#fff';
            const name = document.createElement('span');
            name.className = 'tile-name';
            name.textContent = d.area;
            const value = document.createElement('span');
            value.className = 'tile-value';
            value.textContent = d.temp == null ? '\u2013' : `${num(d.temp)}\u00b0`;
            const detail = document.createElement('span');
            detail.className = 'tile-count';
            detail.textContent = `${d.summary} \u00b7 ${num(d.humidity, 0)}%`;
            tile.append(name, value, detail);
            if (areaSelect) {
                tile.addEventListener('click', () => {
                    areaSelect.value = d.area;
                    areaSelect.dispatchEvent(new Event('change', { bubbles: true }));   // also refreshes the live what-if
                });
            }
            fragment.appendChild(tile);
        });
        tilesBox.replaceChildren(fragment);
    };

    const renderMap = () => {
        if (!latest || !map) return;
        const temps = latest.districts.map((d) => d.temp).filter((v) => v != null);
        const lo = Math.min(...temps);
        const hi = Math.max(...temps);
        setData(map, null, [{
            data: latest.districts.map((d) => ({
                x: d.lon, y: d.lat, r: Math.max(7, Math.min(20, 6 + (d.wind ?? 0) / 2)),
                area: d.area, temp: d.temp, wind: d.wind, summary: d.summary,
            })),
            backgroundColor: latest.districts.map((d) => (d.temp == null ? '#999' : heat(d.temp, lo, hi).colour)),
            borderColor: '#fff',
        }]);
    };

    const setStatus = (text, cls) => {
        if (!statusPill) return;
        statusPill.textContent = text;
        statusPill.className = `live-pill ${cls}`.trim();
    };

    const refresh = async () => {
        try {
            const response = await fetch(root.dataset.endpoint, { headers: { Accept: 'application/json' } });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error ?? response.status);
            latest = data;
            renderTiles();
            renderSelected();
            renderMap();
            const time = new Date(data.updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            setStatus(data.stale ? `last reading ${time} (service unreachable)` : `updated ${time}`, data.stale ? 'stale' : '');
        } catch {
            if (!latest) setStatus('weather unavailable', 'offline');
            else setStatus('reconnecting\u2026', 'stale');
        }
    };

    if (areaSelect) areaSelect.addEventListener('change', () => { renderSelected(); renderTiles(); });

    refresh();
    let timer = setInterval(refresh, POLL_MS);
    document.addEventListener('visibilitychange', () => {
        clearInterval(timer);
        if (!document.hidden) { refresh(); timer = setInterval(refresh, POLL_MS); }
    });
})();
