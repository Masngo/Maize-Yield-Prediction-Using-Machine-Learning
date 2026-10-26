/* Live weather: polls /api/weather every minute (the server caches Open-Meteo for 10 minutes).
   Shows humidity, wind (speed, direction, gusts), air pressure and wind pressure as well as temperature and rain.
   - User dashboard: details for the selected district + heat-map tiles and bar chart (click a tile to select it).
   - Expert dashboard: tiles + bar chart + a coordinate "weather map".
   A metric selector (#wx-metric) switches what the tiles, bars and map show. */
(() => {
    const M = window.MaizeCharts;
    const root = document.getElementById('weather-panel') || document.getElementById('weather');
    if (!M || !root) return;

    const { el, makeChart, setData, TEXT, axes, noLegend } = M;
    const POLL_MS = 60000;

    /* hsl colour ramps: k = 0 (lowest) ... 1 (highest) */
    const METRICS = {
        temp: { label: 'Temperature', unit: '\u00b0C', digits: 1, colour: (k) => `hsl(${210 - k * 195} 65% 42%)` },
        humidity: { label: 'Humidity', unit: '%', digits: 0, colour: (k) => `hsl(195 70% ${72 - k * 42}%)` },
        pressure: { label: 'Air pressure', unit: 'hPa', digits: 1, colour: (k) => `hsl(270 45% ${74 - k * 44}%)` },
        wind: { label: 'Wind speed', unit: 'km/h', digits: 0, colour: (k) => `hsl(170 55% ${72 - k * 44}%)` },
        wind_pressure: { label: 'Wind pressure', unit: 'Pa', digits: 1, colour: (k) => `hsl(28 70% ${74 - k * 42}%)` },
        rain: { label: 'Rain', unit: 'mm', digits: 1, colour: (k) => `hsl(220 70% ${78 - k * 46}%)` },
    };
    const num = (v, digits = 1) => (v == null ? '\u2013' : Number(v).toFixed(digits));
    const scale = (values) => {
        const clean = values.filter((v) => v != null);
        return { lo: Math.min(...clean), hi: Math.max(...clean) };
    };
    const ramp = (metric, value, lo, hi) => {
        if (value == null) return { background: '#999', text: '#fff' };
        const k = hi > lo ? (value - lo) / (hi - lo) : 0.5;
        const background = METRICS[metric].colour(k);
        const lightness = Number(/(\d+(?:\.\d+)?)%\)$/.exec(background)?.[1] ?? 40);
        return { background, text: lightness > 58 ? '#10331a' : '#fff', k };
    };
    window.MaizeWeather = { METRICS, ramp, scale, num };   // shared with calendar.js

    const tilesBox = el('wx-tiles');
    const statusPill = el('wx-status');
    const selectedBox = el('wx-selected');
    const districtLabel = el('wx-district');
    const areaSelect = el('Area');
    const metricSelect = el('wx-metric');
    let latest = null;
    const metric = () => (metricSelect ? metricSelect.value : 'temp');
    const selectedArea = () => (areaSelect ? areaSelect.value : null);
    const fmt = (v, m) => (v == null ? '\u2013' : `${num(v, METRICS[m].digits)}`);

    /* Bar chart of the chosen metric across districts */
    const bars = makeChart('wx-bars', {
        type: 'bar', data: { labels: [], datasets: [] },
        options: { ...noLegend, animation: { duration: 250 }, scales: axes('') },
    });

    /* Bubble "map": x = longitude, y = latitude, names drawn above the bubbles. */
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
                        label: (c) => `${c.raw.area}: ${c.raw.shown} ${METRICS[metric()].unit}, ${c.raw.summary}, wind ${num(c.raw.wind, 0)} km/h`,
                    },
                },
            },
        },
    });

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

    const renderSelected = () => {
        if (!latest || !selectedBox) return;
        const d = latest.districts.find((x) => x.area === selectedArea());
        if (districtLabel && d) districtLabel.textContent = d.area;
        if (!d) { selectedBox.textContent = '\u2013'; return; }
        const main = document.createElement('div');
        main.className = 'wx-item';
        const big = document.createElement('span');
        big.className = 'wx-big';
        big.textContent = `${num(d.temp)} \u00b0C`;
        const sm = document.createElement('small');
        sm.textContent = d.summary;
        main.append(big, sm);
        const wind = d.wind == null ? '\u2013' : `${num(d.wind, 0)} km/h ${d.wind_dir ?? ''}`.trim();
        selectedBox.replaceChildren(
            main,
            item(`${num(d.humidity, 0)} %`, 'humidity'),
            item(wind, d.gust == null ? 'wind' : `wind (gusts ${num(d.gust, 0)} km/h)`),
            item(`${num(d.pressure)} hPa`, 'air pressure'),
            item(`${num(d.wind_pressure)} Pa`, 'wind pressure'),
            item(`${num(d.rain)} mm`, 'rain right now'),
        );
    };

    const renderTiles = () => {
        if (!latest || !tilesBox) return;
        const m = metric();
        const { lo, hi } = scale(latest.districts.map((d) => d[m]));
        const fragment = document.createDocumentFragment();
        latest.districts.forEach((d) => {
            const colours = ramp(m, d[m], lo, hi);
            const tile = document.createElement('div');
            tile.className = 'tile' + (d.area === selectedArea() ? ' selected' : '');
            tile.style.backgroundColor = colours.background;
            tile.style.color = colours.text;
            const name = document.createElement('span');
            name.className = 'tile-name';
            name.textContent = d.area;
            const value = document.createElement('span');
            value.className = 'tile-value';
            value.textContent = `${fmt(d[m], m)} ${d[m] == null ? '' : METRICS[m].unit}`.trim();
            const detail = document.createElement('span');
            detail.className = 'tile-count';
            detail.textContent = d.summary;
            tile.append(name, value, detail);
            if (areaSelect) {
                tile.addEventListener('click', () => {
                    areaSelect.value = d.area;
                    areaSelect.dispatchEvent(new Event('change', { bubbles: true }));   // also refreshes live what-if + calendar
                });
            }
            fragment.appendChild(tile);
        });
        tilesBox.replaceChildren(fragment);
    };

    const renderBars = () => {
        if (!latest || !bars) return;
        const m = metric();
        const { lo, hi } = scale(latest.districts.map((d) => d[m]));
        const rows = [...latest.districts].sort((a, b) => (b[m] ?? -Infinity) - (a[m] ?? -Infinity));
        bars.options.scales.y.title = { display: true, text: `${METRICS[m].label} (${METRICS[m].unit})`, color: TEXT };
        // Temperature and pressure vary in a narrow band, so start the axis a little below the lowest bar
        // (rather than at 0) while still keeping every bar visible; other measures start at zero.
        const narrow = m === 'pressure' || m === 'temp';
        bars.options.scales.y.beginAtZero = !narrow;
        bars.options.scales.y.min = narrow && Number.isFinite(lo) ? Math.floor(lo - (hi - lo) * 0.6) : undefined;
        setData(bars, rows.map((d) => d.area), [{
            data: rows.map((d) => (d[m] == null ? null : Number(num(d[m], METRICS[m].digits)))),
            backgroundColor: rows.map((d) => ramp(m, d[m], lo, hi).background),
        }]);
    };

    const renderMap = () => {
        if (!latest || !map) return;
        const m = metric();
        const { lo, hi } = scale(latest.districts.map((d) => d[m]));
        setData(map, null, [{
            data: latest.districts.map((d) => ({
                x: d.lon, y: d.lat, r: Math.max(7, Math.min(20, 6 + (d.wind ?? 0) / 2)),
                area: d.area, shown: fmt(d[m], m), wind: d.wind, summary: d.summary,
            })),
            backgroundColor: latest.districts.map((d) => ramp(m, d[m], lo, hi).background),
            borderColor: '#fff',
        }]);
    };

    const renderAll = () => { renderTiles(); renderSelected(); renderBars(); renderMap(); };

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
            renderAll();
            const time = new Date(data.updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            setStatus(data.stale ? `last reading ${time} (service unreachable)` : `updated ${time}`, data.stale ? 'stale' : '');
        } catch {
            if (!latest) setStatus('weather unavailable', 'offline');
            else setStatus('reconnecting\u2026', 'stale');
        }
    };

    if (areaSelect) areaSelect.addEventListener('change', () => { renderSelected(); renderTiles(); });
    if (metricSelect) metricSelect.addEventListener('change', renderAll);

    refresh();
    let timer = setInterval(refresh, POLL_MS);
    document.addEventListener('visibilitychange', () => {
        clearInterval(timer);
        if (!document.hidden) { refresh(); timer = setInterval(refresh, POLL_MS); }
    });
})();
