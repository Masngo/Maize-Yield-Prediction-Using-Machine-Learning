/* Live date and time in the header (Zimbabwe time, CAT = UTC+2), with the day number of the year.
   Uses the device clock, ticking every second. */
(() => {
    const box = document.getElementById('live-clock');
    if (!box) return;
    const dateEl = document.getElementById('clock-date');
    const timeEl = document.getElementById('clock-time');
    const dayEl = document.getElementById('clock-day');
    const zone = 'Africa/Harare';
    const dateFormat = new Intl.DateTimeFormat('en-GB', { timeZone: zone, weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
    const timeFormat = new Intl.DateTimeFormat('en-GB', { timeZone: zone, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    const partsFormat = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' });

    const isLeap = (y) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;

    const tick = () => {
        const now = new Date();
        const p = Object.fromEntries(partsFormat.formatToParts(now).map((x) => [x.type, x.value]));
        const year = Number(p.year);
        const dayOfYear = Math.round((Date.UTC(year, Number(p.month) - 1, Number(p.day)) - Date.UTC(year, 0, 0)) / 86400000);
        dateEl.textContent = dateFormat.format(now);
        timeEl.textContent = `${timeFormat.format(now)} CAT`;
        dayEl.textContent = `Day ${dayOfYear} of ${isLeap(year) ? 366 : 365}`;
        box.setAttribute('data-date', `${p.year}-${p.month}-${p.day}`);
    };

    tick();
    setInterval(tick, 1000);
})();
