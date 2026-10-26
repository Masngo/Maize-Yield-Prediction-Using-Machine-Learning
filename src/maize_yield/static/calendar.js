/* Year calendar heat map: one cell for every day of the year for the selected district.
   Past days are observed/analysed weather, the next ~2 weeks are forecast, later days are empty.
   Today is outlined and the grid refreshes itself when the date changes. */
(() => {
    const W = window.MaizeWeather;
    const root = document.getElementById('year-calendar');
    if (!W || !root) return;

    const { METRICS, ramp, scale, num } = W;
    const el = (id) => document.getElementById(id);
    const grid = el('cal-grid');
    const detail = el('cal-detail');
    const status = el('cal-status');
    const legend = el('cal-legend');
    const stats = el('cal-stats');
    const metricSelect = el('cal-metric');
    const districtSelect = el('Area') || el('cal-district');
    const REFRESH_MS = 10 * 60 * 1000;
    const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    /* Which field of a day feeds each metric */
    const FIELD = { temp: 'temp', rain: 'rain', humidity: 'humidity', pressure: 'pressure', wind: 'wind', wind_pressure: 'wind_pressure' };

    let data = null;
    let controller = null;

    const harareToday = () => {
        const p = Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Harare', year: 'numeric', month: '2-digit', day: '2-digit' })
            .formatToParts(new Date()).map((x) => [x.type, x.value]));
        return `${p.year}-${p.month}-${p.day}`;
    };

    const describe = (d) => {
        const date = new Date(`${d.date}T12:00:00Z`).toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
        if (!d.kind) return `${date} (day ${d.doy}): no data yet`;
        const range = d.tmin != null && d.tmax != null ? ` (${num(d.tmin)}\u2013${num(d.tmax)})` : '';
        return `${date} (day ${d.doy}, ${d.kind}): ${num(d.temp)} \u00b0C${range}, humidity ${num(d.humidity, 0)} %, `
            + `pressure ${num(d.pressure)} hPa, wind ${num(d.wind, 0)} km/h, wind pressure ${num(d.wind_pressure)} Pa, rain ${num(d.rain)} mm`;
    };

    const showDetail = (d) => { if (detail) detail.textContent = describe(d); };

    const renderStats = () => {
        if (!stats) return;
        const seen = data.days.filter((d) => d.kind === 'observed');
        const rain = seen.reduce((sum, d) => sum + (d.rain ?? 0), 0);
        const temps = seen.map((d) => d.temp).filter((v) => v != null);
        const hottest = seen.reduce((best, d) => (d.tmax != null && (!best || d.tmax > best.tmax) ? d : best), null);
        const wettest = seen.reduce((best, d) => (d.rain != null && (!best || d.rain > best.rain) ? d : best), null);
        const card = (label, value) => {
            const wrap = document.createElement('div');
            wrap.className = 'stat-card';
            const l = document.createElement('span');
            l.className = 'stat-label';
            l.textContent = label;
            const v = document.createElement('span');
            v.className = 'stat-value';
            v.textContent = value;
            wrap.append(l, v);
            return wrap;
        };
        const short = (d) => (d ? new Date(`${d.date}T12:00:00Z`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' }) : '');
        const doy = data.days.find((d) => d.date === data.today)?.doy ?? '\u2013';
        stats.replaceChildren(
            card('Today', `Day ${doy} of ${data.days.length}`),
            card('Rain so far this year', `${Math.round(rain).toLocaleString()} mm`),
            card('Average temperature so far', temps.length ? `${num(temps.reduce((a, b) => a + b, 0) / temps.length)} \u00b0C` : '\u2013'),
            card('Hottest day', hottest ? `${num(hottest.tmax)} \u00b0C (${short(hottest)})` : '\u2013'),
            card('Wettest day', wettest && wettest.rain > 0 ? `${num(wettest.rain)} mm (${short(wettest)})` : '\u2013'),
        );
    };

    const render = () => {
        if (!data) return;
        const m = metricSelect ? metricSelect.value : 'temp';
        const field = FIELD[m];
        const byDate = new Map(data.days.map((d) => [d.date, d]));
        const { lo, hi } = scale(data.days.map((d) => d[field]));
        const year = data.year;
        const fragment = document.createDocumentFragment();

        const corner = document.createElement('span');
        corner.className = 'cal-label';
        fragment.appendChild(corner);
        for (let day = 1; day <= 31; day += 1) {
            const head = document.createElement('span');
            head.className = 'cal-head';
            head.textContent = day === 1 || day % 5 === 0 ? String(day) : '';
            fragment.appendChild(head);
        }
        MONTHS.forEach((name, month) => {
            const label = document.createElement('span');
            label.className = 'cal-label';
            label.textContent = name;
            fragment.appendChild(label);
            const length = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
            for (let day = 1; day <= 31; day += 1) {
                const cell = document.createElement('button');
                cell.type = 'button';
                if (day > length) { cell.className = 'cal-day blank'; cell.disabled = true; cell.tabIndex = -1; fragment.appendChild(cell); continue; }
                const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                const d = byDate.get(key);
                const value = d?.[field];
                cell.className = 'cal-day' + (d?.kind === 'forecast' ? ' forecast' : '') + (value == null ? ' nodata' : '') + (key === data.today ? ' today' : '');
                if (value != null) cell.style.backgroundColor = ramp(m, value, lo, hi).background;
                const text = describe(d);
                cell.title = text;
                cell.setAttribute('aria-label', text);
                cell.addEventListener('click', () => showDetail(d));
                cell.addEventListener('mouseenter', () => showDetail(d));
                fragment.appendChild(cell);
            }
        });
        grid.replaceChildren(fragment);

        if (legend) {
            legend.replaceChildren();
            const low = document.createElement('span');
            low.textContent = Number.isFinite(lo) ? `${num(lo, METRICS[m].digits)} ${METRICS[m].unit}` : '';
            const bar = document.createElement('span');
            bar.className = 'cal-ramp';
            bar.style.background = `linear-gradient(90deg, ${METRICS[m].colour(0)}, ${METRICS[m].colour(0.5)}, ${METRICS[m].colour(1)})`;
            const high = document.createElement('span');
            high.textContent = Number.isFinite(hi) ? `${num(hi, METRICS[m].digits)} ${METRICS[m].unit}` : '';
            legend.append(low, bar, high);
        }
        renderStats();
        const today = byDate.get(data.today);
        if (today && detail && !detail.textContent) showDetail(today);
    };

    const load = async () => {
        const area = districtSelect ? districtSelect.value : '';
        if (!area) return;
        if (controller) controller.abort();
        controller = new AbortController();
        status.textContent = 'loading the year\u2026 (the first load can take a few seconds)';
        status.className = 'live-pill stale';
        try {
            const response = await fetch(`${root.dataset.endpoint}?area=${encodeURIComponent(area)}`, { headers: { Accept: 'application/json' }, signal: controller.signal });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.error ?? response.status);
            data = payload;
            if (detail) detail.textContent = '';
            render();
            const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            status.textContent = payload.partial ? `${area}: partly loaded at ${time}` : `${area}: updated ${time}`;
            status.className = `live-pill${payload.partial ? ' stale' : ''}`;
        } catch (error) {
            if (error.name === 'AbortError') return;
            status.textContent = data ? 'could not refresh' : 'day-by-day weather unavailable';
            status.className = `live-pill ${data ? 'stale' : 'offline'}`;
        }
    };

    if (districtSelect) districtSelect.addEventListener('change', load);
    if (metricSelect) metricSelect.addEventListener('change', render);
    load();
    setInterval(load, REFRESH_MS);
    setInterval(() => { if (data && harareToday() !== data.today) load(); }, 60000);   // a new day has started
})();
