document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('predict-form');
    const result = document.getElementById('prediction-result');
    if (!form || !result) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content ?? '';

    const show = (message, ok) => {
        result.textContent = message;
        result.classList.toggle('alert-success', ok);
        result.classList.toggle('alert-error', !ok);
        result.style.display = 'block';
    };

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const payload = Object.fromEntries(new FormData(form).entries());

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (response.ok && typeof data.prediction === 'number') {
                const formatted = Math.round(data.prediction).toLocaleString();
                show(`Predicted yield: ${formatted} hg/ha (~${(data.prediction / 10000).toFixed(2)} t/ha)`, true);
            } else {
                show(data.error ?? 'Prediction failed.', false);
            }
        } catch {
            show('Network error. Please try again.', false);
        }
    });
});
