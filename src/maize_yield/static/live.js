/* Live what-if predictor: as the user types, ask /api/preview (nothing is saved) and redraw
   a rainfall line graph, a per-district bar chart and a district x rainfall heat map. */
(() => {
    const form = document.getElementById('predict-form');
    const panel = document.getElementById('live-panel');
    const M = window.MaizeCharts;
    if (!form || !panel || !M) return;

    const { t, el, makeChart, setData, axes, noLegend, GREEN, GOLD, TEXT } = M;
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content ?? '';
    const estimate = el('live-estimate');

    const curve = makeChart('chart-live-curve', {
        type: 'scatter', data: { datasets: [] },
        options: {
            ...noLegend,
            animation: { duration: 250 },
            scales: axes('Predicted yield (t/ha)', 'Rainfall (mm/year)'),
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.raw.x} mm: ${c.raw.y} t/ha` } } },
        },
    });
    const bars = makeChart('chart-live-areas', {
        type: 'bar', data: { labels: [], datasets: [] }, options: { ...noLegend, animation: { duration: 250 }, scales: axes('t/ha') },
    });

    const renderHeatmap = (heat, selectedArea) => {
        const flat = heat.values.flat();
        const lo = Math.min(...flat);
        const hi = Math.max(...flat);
        const table = el('live-heatmap');
        const head = document.createElement('tr');
        const corner = document.createElement('th');
        corner.className = 'row-name';
        corner.textContent = 'District';
        head.appendChild(corner);
        heat.rainfall.forEach((r) => { const th = document.createElement('th'); th.textContent = `${r} mm`; head.appendChild(th); });
        const rows = [head];
        heat.areas.forEach((area, i) => {
            const tr = document.createElement('tr');
            if (area === selectedArea) tr.className = 'selected';
            const th = document.createElement('th');
            th.className = 'row-name';
            th.textContent = area;
            tr.appendChild(th);
            heat.values[i].forEach((v) => {
                const k = hi > lo ? (v - lo) / (hi - lo) : 0.5;
                const td = document.createElement('td');
                td.textContent = t(v);
                td.style.backgroundColor = `hsl(95 45% ${68 - k * 36}%)`;
                td.style.color = k < 0.35 ? '#10331a' : '#fff';
                tr.appendChild(td);
            });
            rows.push(tr);
        });
        table.replaceChildren(...rows);
    };

    const render = (d, input) => {
        estimate.textContent = `Live estimate: ${t(d.prediction)} t/ha  (${Math.round(d.prediction).toLocaleString()} hg/ha)`;
        panel.style.display = 'block';

        setData(curve, null, [
            { data: d.curve.x.map((x, i) => ({ x, y: t(d.curve.y[i]) })), showLine: true, borderColor: GREEN,
              backgroundColor: GREEN, pointRadius: 2, tension: 0.25 },
            { data: [{ x: input.rainfall, y: t(d.prediction) }], backgroundColor: GOLD, borderColor: '#8a6d00', pointRadius: 8 },
        ]);

        const sorted = [...d.by_area].sort((a, b) => b.value - a.value);
        setData(bars, sorted.map((a) => a.area), [{
            data: sorted.map((a) => t(a.value)),
            backgroundColor: sorted.map((a) => (a.area === input.area ? GOLD : GREEN)),
        }]);
        renderHeatmap(d.heatmap, input.area);
    };

    let timer = null;
    let controller = null;

    const update = async () => {
        const raw = Object.fromEntries(new FormData(form).entries());
        if (Object.values(raw).some((v) => v === '')) {
            estimate.textContent = 'Fill in the form to see a live estimate as you type.';
            panel.style.display = 'none';
            return;
        }
        if (controller) controller.abort();               // a newer edit supersedes the previous request
        controller = new AbortController();
        try {
            const response = await fetch(panel.dataset.endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify(raw),
                signal: controller.signal,
            });
            const data = await response.json();
            if (!response.ok) { estimate.textContent = data.error ?? 'Check the form values.'; return; }
            render(data, { rainfall: Number(raw.Average_Rainfall_mm_per_year), area: raw.Area });
        } catch (error) {
            if (error.name !== 'AbortError') estimate.textContent = 'Live estimate unavailable (network error).';
        }
    };

    const schedule = () => { clearTimeout(timer); timer = setTimeout(update, 300); };
    form.addEventListener('input', schedule);
    form.addEventListener('change', schedule);
})();
