/* Live charts. Chart.js is vendored in static/vendor, so no external CDN is needed.
   - Expert dashboard: polls /api/stats every 5 s.
   - Admin dashboard:  polls /api/admin-stats every 5 s.
   - User dashboard:   refreshes /api/my-stats right after each prediction.
   Yields arrive in hg/ha; charts show t/ha (1 t/ha = 10,000 hg/ha). */
(() => {
    if (typeof Chart === 'undefined') return;

    const HG_PER_T = 10000;
    const POLL_MS = 5000;
    const TEXT = '#155724';
    const GREEN = '#6b8e23';
    const GOLD = '#c9a227';
    const GREY = '#e3e6dc';
    const GAUGE_MAX = 150; // gauge dial spans 0-150 % of the historical average

    const t = (hg) => (hg == null ? null : +(hg / HG_PER_T).toFixed(2));
    const palette = (n) => Array.from({ length: n }, (_, i) => `hsl(${(i * 137.5 + 90) % 360} 50% 48%)`);
    const el = (id) => document.getElementById(id);

    const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: TEXT } } },
    };
    const noLegend = { ...baseOptions, plugins: { legend: { display: false } } };
    const axes = (yTitle, xTitle) => ({
        x: { ticks: { color: TEXT }, grid: { display: false }, title: { display: !!xTitle, text: xTitle, color: TEXT } },
        y: { beginAtZero: true, ticks: { color: TEXT }, title: { display: !!yTitle, text: yTitle, color: TEXT } },
    });
    const intAxes = (yTitle) => {
        const a = axes(yTitle);
        a.y.ticks = { ...a.y.ticks, precision: 0 };
        return a;
    };

    const makeChart = (id, config) => {
        const canvas = el(id);
        return canvas ? new Chart(canvas, config) : null;
    };
    const setData = (chart, labels, datasets) => {
        if (!chart) return;
        if (labels) chart.data.labels = labels;
        datasets.forEach((d, i) => {
            if (chart.data.datasets[i]) Object.assign(chart.data.datasets[i], d);
            else chart.data.datasets.push(d);
        });
        chart.data.datasets.length = datasets.length;
        chart.update();
    };
    const lineDataset = (values) => ({
        data: values, borderColor: GREEN, backgroundColor: 'rgba(107,142,35,0.25)', fill: true, tension: 0.25, pointRadius: 3,
    });

    /* Half-circle gauge: shows pct (0-150) of a reference value. */
    const makeGauge = (id) => makeChart(id, {
        type: 'doughnut',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false, rotation: -90, circumference: 180, cutout: '72%',
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
        },
    });
    const setGauge = (chart, pct) => {
        if (!chart) return;
        const shown = Math.max(0, Math.min(GAUGE_MAX, pct));
        const near = Math.abs(pct - 100) <= 15;           // within 15 % of history = green, otherwise gold
        setData(chart, null, [{ data: [shown, GAUGE_MAX - shown], backgroundColor: [near ? GREEN : GOLD, GREY], borderWidth: 0 }]);
    };

    /* Render a newest-first list; entries newer than the previous render get a highlight. */
    const makeFeed = (list) => {
        let lastId = null;
        return (rows) => {
            if (!list) return;
            const fragment = document.createDocumentFragment();
            rows.forEach((r) => {
                const li = document.createElement('li');
                const who = document.createElement('strong');
                who.textContent = r.user;
                li.append(who, ` predicted ${t(r.value)} t/ha for ${r.area} (${r.year})`);
                if (lastId !== null && r.id > lastId) li.classList.add('fresh');
                fragment.appendChild(li);
            });
            list.replaceChildren(fragment);
            if (rows.length) lastId = Math.max(lastId ?? 0, ...rows.map((r) => r.id));
        };
    };

    /* Poll an endpoint, call render(data), and keep the "Live" indicator honest. */
    const livePoll = (endpoint, render) => {
        const status = el('live-status');
        const refresh = async () => {
            try {
                const response = await fetch(endpoint, { headers: { Accept: 'application/json' } });
                if (!response.ok) throw new Error(response.status);
                render(await response.json());
                if (status) {
                    status.textContent = `Live \u00b7 updated ${new Date().toLocaleTimeString()}`;
                    status.classList.remove('offline');
                }
            } catch {
                if (status) { status.textContent = 'Reconnecting\u2026'; status.classList.add('offline'); }
            }
        };
        refresh();
        let timer = setInterval(refresh, POLL_MS);
        document.addEventListener('visibilitychange', () => {   // don't poll from background tabs
            clearInterval(timer);
            if (!document.hidden) { refresh(); timer = setInterval(refresh, POLL_MS); }
        });
    };

    /* ---------------- Expert dashboard ---------------- */
    const expert = el('expert-dashboard');
    if (expert) {
        const gauge = makeGauge('chart-gauge');
        const share = makeChart('chart-share', { type: 'doughnut', data: { labels: [], datasets: [] }, options: baseOptions });
        const average = makeChart('chart-average', {
            type: 'bar', data: { labels: [], datasets: [] }, options: { ...noLegend, scales: axes('t/ha') },
        });
        const trend = makeChart('chart-trend', {
            type: 'line', data: { labels: [], datasets: [] }, options: { ...noLegend, scales: axes('t/ha') },
        });
        const vsHistory = makeChart('chart-vs-history', {
            type: 'bar', data: { labels: [], datasets: [] }, options: { ...baseOptions, scales: axes('t/ha') },
        });
        const radar = makeChart('chart-radar', {
            type: 'radar', data: { labels: [], datasets: [] },
            options: {
                ...baseOptions,
                scales: { r: { beginAtZero: true, ticks: { color: TEXT, backdropColor: 'transparent' }, pointLabels: { color: TEXT } } },
            },
        });
        const years = makeChart('chart-years', {
            type: 'bar', data: { labels: [], datasets: [] }, options: { ...noLegend, scales: intAxes('predictions') },
        });
        const histogram = makeChart('chart-histogram', {
            type: 'bar', data: { labels: [], datasets: [] }, options: { ...noLegend, scales: intAxes('predictions') },
        });
        const users = makeChart('chart-users', {
            type: 'bar', data: { labels: [], datasets: [] },
            options: { ...noLegend, indexAxis: 'y', scales: { x: { ...intAxes().y, beginAtZero: true }, y: { ticks: { color: TEXT } } } },
        });
        const SCATTER_LABELS = { rainfall: 'Rainfall (mm/year)', temp: 'Temperature (\u00b0C)', pesticides: 'Pesticides (tonnes)' };
        const scatter = makeChart('chart-scatter', {
            type: 'scatter', data: { datasets: [] },
            options: {
                ...noLegend,
                scales: axes('Predicted yield (t/ha)', SCATTER_LABELS.rainfall),
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => `${c.raw.area}: ${c.raw.x}, ${c.raw.y} t/ha` } },
                },
            },
        });
        const bubble = makeChart('chart-bubble', {
            type: 'bubble', data: { datasets: [] },
            options: {
                ...noLegend,
                scales: { x: { ...axes(null, 'Rainfall (mm/year)').x }, y: { ...axes('Temperature (\u00b0C)').y, beginAtZero: false } },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => `${c.raw.area}: ${c.raw.v} t/ha (${c.raw.x} mm, ${c.raw.y} \u00b0C)` } },
                },
            },
        });
        const session = makeChart('chart-session', {
            type: 'line', data: { labels: [], datasets: [] },
            options: { ...noLegend, scales: { ...intAxes('total'), y: { ...intAxes('total').y, beginAtZero: false } } },
        });

        const feed = makeFeed(el('feed'));
        const heatmap = el('heatmap');
        const selector = el('scatter-x');
        let latest = null;
        let startTotal = null;
        const sessionLabels = [];
        const sessionTotals = [];

        const renderScatter = () => {
            if (!latest || !scatter) return;
            const key = selector.value;
            scatter.options.scales.x.title.text = SCATTER_LABELS[key];
            setData(scatter, null, [{
                data: latest.points.map((p) => ({ x: p[key], y: t(p.value), area: p.area })),
                backgroundColor: 'rgba(107,142,35,0.65)', pointRadius: 4,
            }]);
        };
        if (selector) selector.addEventListener('change', renderScatter);

        const renderHistogram = (points) => {
            const values = points.map((p) => p.value / HG_PER_T);
            const bins = Math.max(1, Math.ceil(Math.max(0, ...values)));
            const counts = new Array(bins).fill(0);
            values.forEach((v) => { counts[Math.min(bins - 1, Math.floor(v))] += 1; });
            setData(histogram, counts.map((_, i) => `${i}\u2013${i + 1}`), [{ data: counts, backgroundColor: GREEN }]);
        };

        const renderHeatmap = (d) => {
            const byArea = new Map(d.by_area.map((a) => [a.area, a]));
            const values = d.by_area.map((a) => a.average);
            const lo = Math.min(...values);
            const hi = Math.max(...values);
            const fragment = document.createDocumentFragment();
            Object.keys(d.historical).sort().forEach((area) => {
                const info = byArea.get(area);
                const tile = document.createElement('div');
                tile.className = info ? 'tile' : 'tile empty';
                const name = document.createElement('span');
                name.className = 'tile-name';
                name.textContent = area;
                const value = document.createElement('span');
                value.className = 'tile-value';
                value.textContent = info ? t(info.average) : '\u2013';
                const count = document.createElement('span');
                count.className = 'tile-count';
                count.textContent = info ? `${info.count} prediction${info.count === 1 ? '' : 's'}` : 'none yet';
                if (info) {
                    const k = hi > lo ? (info.average - lo) / (hi - lo) : 0.5;   // 0 = lowest, 1 = highest
                    tile.style.backgroundColor = `hsl(95 45% ${68 - k * 36}%)`;
                    tile.style.color = k < 0.35 ? '#10331a' : '#fff';
                }
                tile.append(name, value, count);
                fragment.appendChild(tile);
            });
            heatmap.replaceChildren(fragment);
        };

        const renderSession = (total) => {
            if (startTotal === null) startTotal = total;
            sessionLabels.push(new Date().toLocaleTimeString());
            sessionTotals.push(total);
            if (sessionLabels.length > 60) { sessionLabels.shift(); sessionTotals.shift(); }
            el('session-new').textContent = total - startTotal;
            setData(session, [...sessionLabels], [{ ...lineDataset([...sessionTotals]), stepped: true, tension: 0 }]);
        };

        const renderTable = (rows) => {
            const fragment = document.createDocumentFragment();
            rows.forEach((r) => {
                const tr = document.createElement('tr');
                [r.id, r.user, r.year, r.rainfall, r.pesticides, r.temp, r.area, Math.round(r.value).toLocaleString()]
                    .forEach((v) => { const td = document.createElement('td'); td.textContent = v; tr.appendChild(td); });
                fragment.appendChild(tr);
            });
            el('predictions-body').replaceChildren(fragment);
        };

        livePoll(expert.dataset.endpoint, (d) => {
            latest = d;
            el('stat-total').textContent = d.total.toLocaleString();
            el('stat-average').textContent = d.average == null ? '\u2013' : `${t(d.average)} t/ha`;
            el('stat-top').textContent = d.by_area.length ? d.by_area[0].area : '\u2013';

            if (d.average != null && d.expected_historical) {
                const pct = (d.average / d.expected_historical) * 100;
                el('gauge-value').textContent = `${Math.round(pct)}%`;
                setGauge(gauge, pct);
            } else {
                el('gauge-value').textContent = '\u2013';
                setGauge(gauge, 0);
            }

            const labels = d.by_area.map((a) => a.area);
            setData(share, labels, [{ data: d.by_area.map((a) => a.count), backgroundColor: palette(labels.length) }]);
            setData(average, labels, [{ data: d.by_area.map((a) => t(a.average)), backgroundColor: palette(labels.length) }]);
            setData(trend, d.series.map((s) => `#${s.id}`), [lineDataset(d.series.map((s) => t(s.value)))]);
            setData(vsHistory, labels, [
                { label: 'Average predicted', data: d.by_area.map((a) => t(a.average)), backgroundColor: GREEN },
                { label: 'Historical average', data: labels.map((a) => t(d.historical[a])), backgroundColor: GOLD },
            ]);
            const top = d.by_area.slice(0, 8);
            setData(radar, top.map((a) => a.area), [
                { label: 'Average predicted', data: top.map((a) => t(a.average)), borderColor: GREEN, backgroundColor: 'rgba(107,142,35,0.25)' },
                { label: 'Historical average', data: top.map((a) => t(d.historical[a.area])), borderColor: GOLD, backgroundColor: 'rgba(201,162,39,0.2)' },
            ]);
            setData(years, d.by_year.map((y) => y.year), [{ data: d.by_year.map((y) => y.count), backgroundColor: GREEN }]);
            renderHistogram(d.points);
            setData(users, d.by_user.map((u) => u.user), [{ data: d.by_user.map((u) => u.count), backgroundColor: GREEN }]);
            renderScatter();
            setData(bubble, null, [{
                data: d.points.map((p) => ({ x: p.rainfall, y: p.temp, r: Math.max(3, Math.min(16, (p.value / HG_PER_T) * 1.4)), v: t(p.value), area: p.area })),
                backgroundColor: 'rgba(107,142,35,0.45)', borderColor: GREEN,
            }]);
            renderHeatmap(d);
            renderSession(d.total);
            feed(d.recent.slice(0, 12));
            renderTable(d.recent);
        });
    }

    /* ---------------- Admin dashboard ---------------- */
    const admin = el('admin-dashboard');
    if (admin) {
        const roles = makeChart('chart-roles', { type: 'doughnut', data: { labels: [], datasets: [] }, options: baseOptions });
        const active = makeChart('chart-active', {
            type: 'bar', data: { labels: [], datasets: [] }, options: { ...noLegend, scales: intAxes('predictions') },
        });
        const polar = makeChart('chart-polar', {
            type: 'polarArea', data: { labels: [], datasets: [] },
            options: { ...baseOptions, scales: { r: { ticks: { color: TEXT, backdropColor: 'transparent', precision: 0 } } } },
        });
        const feed = makeFeed(el('feed'));
        livePoll(admin.dataset.endpoint, (d) => {
            el('stat-users').textContent = d.users.toLocaleString();
            el('stat-predictions').textContent = d.predictions.toLocaleString();
            const labels = d.by_role.map((r) => r.role);
            setData(roles, labels, [{ data: d.by_role.map((r) => r.count), backgroundColor: palette(labels.length) }]);
            setData(active, d.per_user.map((u) => u.user), [{ data: d.per_user.map((u) => u.count), backgroundColor: GREEN }]);
            const areas = d.by_area.map((a) => a.area);
            setData(polar, areas, [{ data: d.by_area.map((a) => a.count), backgroundColor: palette(areas.length).map((c) => c.replace(')', ' / 0.75)')) }]);
            feed(d.recent);
        });
    }

    /* ---------------- User dashboard ---------------- */
    const user = el('user-charts');
    if (user) {
        const gauge = makeGauge('chart-my-gauge');
        const compare = makeChart('chart-compare', {
            type: 'bar', data: { labels: [], datasets: [] }, options: { ...baseOptions, scales: axes('t/ha') },
        });
        const myTrend = makeChart('chart-my-trend', {
            type: 'line', data: { labels: [], datasets: [] }, options: { ...noLegend, scales: axes('t/ha') },
        });
        const myScatter = makeChart('chart-my-scatter', {
            type: 'scatter', data: { datasets: [] },
            options: {
                ...noLegend,
                scales: axes('Predicted yield (t/ha)', 'Rainfall (mm/year)'),
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => `${c.raw.area}: ${c.raw.x} mm, ${c.raw.y} t/ha` } },
                },
            },
        });
        const mine = makeChart('chart-mine', { type: 'doughnut', data: { labels: [], datasets: [] }, options: baseOptions });

        window.refreshUserCharts = async () => {
            try {
                const response = await fetch(user.dataset.endpoint, { headers: { Accept: 'application/json' } });
                if (!response.ok) return;
                const d = await response.json();
                if (!d.total) return;
                user.style.display = 'block';

                const last = d.recent[d.recent.length - 1];
                const hist = d.historical[last.area];
                if (hist) {
                    const pct = (last.value / hist) * 100;
                    el('my-gauge-value').textContent = `${Math.round(pct)}%`;
                    el('my-gauge-note').textContent = `of the ${last.area} historical average (${t(hist)} t/ha)`;
                    setGauge(gauge, pct);
                }
                setData(compare, d.recent.map((r) => `#${r.id} ${r.area}`), [
                    { label: 'Your prediction', data: d.recent.map((r) => t(r.value)), backgroundColor: GREEN },
                    { label: 'District historical average', data: d.recent.map((r) => t(d.historical[r.area])), backgroundColor: GOLD },
                ]);
                setData(myTrend, d.series.map((s) => `#${s.id}`), [lineDataset(d.series.map((s) => t(s.value)))]);
                setData(myScatter, null, [{
                    data: d.points.map((p) => ({ x: p.rainfall, y: t(p.value), area: p.area })),
                    backgroundColor: 'rgba(107,142,35,0.7)', pointRadius: 5,
                }]);
                const labels = d.by_area.map((a) => a.area);
                setData(mine, labels, [{ data: d.by_area.map((a) => a.count), backgroundColor: palette(labels.length) }]);
            } catch { /* charts are optional; ignore network errors */ }
        };
        window.refreshUserCharts();
    }
})();
