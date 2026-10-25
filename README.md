# Maize Yield Prediction (Zimbabwe)

[![CI](https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/actions/workflows/ci.yml/badge.svg)](https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)

A Flask web app that predicts maize yield (hg/ha) for 15 districts in Zimbabwe from rainfall, temperature, pesticide use, year and district. It has three roles: **Users** request predictions, **Experts** review every prediction made, and **Admins** manage accounts.

![Login](docs/screenshots/GUI-%20login.PNG)

## Tech stack

| Area | Tools |
|---|---|
| Web | Flask 3 (app factory + blueprint), Flask-Login, Flask-SQLAlchemy 3, Flask-WTF (CSRF) |
| ML | scikit-learn `Pipeline` (`ColumnTransformer` + estimator), pandas, joblib |
| Quality | pytest, Ruff, GitHub Actions (Python 3.10 - 3.13), Dependabot |
| Deployment | Gunicorn, Docker |
| Packaging | `pyproject.toml`, `src/` layout |

## Live charts

All charts update on their own: the expert and admin pages check for new data every 5 seconds (and pause in background tabs), and the user page refreshes right after each prediction.

- **Expert dashboard:** gauge of predicted vs historical yield; pie, bar and trend charts; a district heat map; predicted vs historical by district; radar profile of the top districts; predictions by input year; yield histogram; predictions per user; scatter plot (switchable between rainfall, temperature and pesticides); a rainfall x temperature x yield bubble chart; a live "this session" chart; and a highlighted activity feed.
- **Admin dashboard:** user and prediction totals, users by role, most active users, a polar-area chart of predictions by district, and a live feed.
- **User dashboard:** gauge of your latest prediction vs the district average, rainfall vs yield scatter, comparison with historical averages, your yield trend, and your predictions by district.
- Charts use [Chart.js](https://www.chartjs.org) (MIT), bundled in `static/vendor/`, so no external CDN is needed.

## Live predictions and weather

- **Live what-if (user dashboard):** as you type, the page asks the model for a fresh estimate (nothing is saved until you press Predict) and redraws a line graph of yield against rainfall, a bar chart of the same inputs in every district, and a district x rainfall heat map.
- **Live weather:** current temperature, humidity, wind and rain for every district, shown as a temperature heat map (click a tile to select that district) and, on the expert dashboard, a coordinate-based weather map. It refreshes every minute.
- Weather comes from [Open-Meteo](https://open-meteo.com/) (free for non-commercial use, no API key). The server calls it once per 10 minutes for all districts and serves the cached reading to everyone; if the service is unreachable the last reading is shown and marked. District coordinates in `src/maize_yield/weather.py` are approximate centres.
- Live weather is context only: the model is trained on yearly averages, so today's weather is not a model input.

## Quick start

```bash
git clone https://github.com/Masngo/Maize-Yield-Prediction-Using-Machine-Learning.git
cd Maize-Yield-Prediction-Using-Machine-Learning

python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env                                     # then set SECRET_KEY
flask --app maize_yield create-user admin --role Admin   # prompts for a password
flask --app maize_yield run --debug
```

Open http://127.0.0.1:5000/login. The model trains automatically on first start if `models/maize_yield_model.joblib` does not exist; retrain any time with `flask --app maize_yield train-model`.

### Docker

```bash
docker build -t maize-yield .
docker run -p 8000:8000 -e SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") maize-yield
```

## Deploy to Render (free)

1. Push this repo to GitHub, then in Render choose **New + > Blueprint** and select it (it reads `render.yaml`).
2. When asked, enter an `ADMIN_PASSWORD` (8+ characters). The `admin` account is created automatically on startup.
3. Open the `https://...onrender.com/login` URL Render gives you.

Free-tier caveats: the service sleeps after ~15 minutes idle (first visit then takes about a minute), and its disk is wiped on restart, so with the default SQLite database only the admin account survives. To keep users and predictions, create a Postgres database on Render and set `DATABASE_URL` to its *Internal Database URL* (free Postgres expires after roughly 30 days; check Render's current terms).

## Project layout

```
src/maize_yield/     app factory, routes, models, ML pipeline, templates, static files
data/                yield_maize_df.csv
notebooks/           original exploration and training notebooks
tests/               pytest suite (auth, roles, validation, prediction, ML)
docs/screenshots/    UI and EDA screenshots
```

## Model and honest results

Five models are compared with 5-fold `GroupKFold` cross-validation (grouped by district-year, so a model is always scored on district-years it has not seen). The best by CV score is refit on all data. Latest run on a held-out 20% of district-years:

| Model | CV R² | Test R² | RMSE (hg/ha) | MAE (hg/ha) |
|---|---|---|---|---|
| Baseline (predict the mean) | -0.001 | -0.001 | 88,020 | 66,155 |
| Ridge regression | 0.047 | 0.047 | 85,909 | 65,900 |
| Decision tree | 0.123 | 0.099 | 83,532 | 63,933 |
| Random forest | 0.135 | 0.124 | 82,359 | 63,468 |
| **Gradient boosting** | **0.136** | 0.119 | 82,608 | 63,816 |

**Please note:** earlier versions of this README claimed R² = 0.89 for Random Forest. That figure does not reproduce with the dataset in this repo; with a proper split the best models explain roughly 12 - 14% of the variance. Within a single district and year the dataset contains many different yields (typically 40+ distinct values) for nearly identical weather inputs, so these five features carry limited signal on their own. Predictions should be treated as rough district-level estimates, not field-level forecasts. Better features (soil, planting date, seed variety, satellite NDVI) are the most promising route to improvement.

## What changed in v2

- Restructured into an installable package (`src/` layout, app factory, blueprint).
- The model is a single scikit-learn pipeline, so training and serving use identical preprocessing. This fixes the old app, where the scaler was fitted with the target column (so it could not be applied to three features) and predictions were multiplied by -1.
- Removed the committed virtualenv (`env/`, ~350 MB), pickles, SQLite databases and duplicate data file.
- Security: secret key from the environment, no default `admin/admin` account (use the `create-user` command), CSRF protection, role-based 403s, input validation, password hashes never rendered, passwords hashed with Werkzeug's current default (scrypt) instead of the removed `sha256` method.
- Fixed Flask 3 incompatibilities (`before_first_request`, `Query.get`) and the dropdown, which only listed 3 of 15 districts.
- Added tests, Ruff, CI, Dependabot and Docker.

## Development

```bash
ruff check .
pytest -q
```

## License

MIT, see [LICENSE](LICENSE).
