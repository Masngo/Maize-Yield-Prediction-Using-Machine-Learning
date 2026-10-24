import joblib

from maize_yield.ml import FEATURES, Predictor


def test_saved_bundle_contents(app, model_path):
    bundle = joblib.load(model_path)
    assert {"pipeline", "areas", "model_name", "metrics"} <= bundle.keys()
    assert len(bundle["areas"]) == 15


def test_model_beats_the_mean_baseline(model_path):
    metrics = joblib.load(model_path)["metrics"]
    best = joblib.load(model_path)["model_name"]
    assert metrics[best]["test_r2"] > metrics["Baseline (mean)"]["test_r2"]


def test_predictor_is_deterministic(model_path):
    predictor = Predictor(model_path)
    args = dict(year=2020, rainfall=1000.0, pesticides=30000.0, temp=22.0, area="Mazowe")
    assert predictor.predict(**args) == predictor.predict(**args)
    assert FEATURES[-1] == "Area"
