document.addEventListener('DOMContentLoaded', function() {
    const predictForm = document.getElementById('predict-form');
    const predictionResult = document.getElementById('prediction-result');

    if (predictForm) {
        predictForm.addEventListener('submit', function(event) {
            event.preventDefault();

            const formData = new FormData(predictForm);
            const data = {};

            formData.forEach((value, key) => {
                data[key] = value;
            });

            fetch('/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.prediction) {
                    predictionResult.textContent = `Predicted Yield: ${result.prediction}`;
                    predictionResult.classList.add('alert-success');
                    predictionResult.classList.remove('alert-error');
                    predictionResult.style.display = 'block';
                } else {
                    predictionResult.textContent = 'Error in prediction';
                    predictionResult.classList.add('alert-error');
                    predictionResult.classList.remove('alert-success');
                    predictionResult.style.display = 'block';
                }
            })
            .catch(error => {
                predictionResult.textContent = 'An error occurred';
                predictionResult.classList.add('alert-error');
                predictionResult.classList.remove('alert-success');
                predictionResult.style.display = 'block';
            });
        });
    }
});
