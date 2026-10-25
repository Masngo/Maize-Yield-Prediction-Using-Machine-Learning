"""Training and inference for the maize yield model.

The whole preprocessing + estimator chain lives in one scikit-learn ``Pipeline``,
so training and serving can never drift apart (the old app re-implemented the
encoding and scaling by hand and applied them inconsistently).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeRegressor

TARGET = "hg/ha_yield"
NUMERIC = ["Year", "Average_Rainfall_mm_per_year", "Pesticides_Tonnes", "Avg_Temp"]
CATEGORICAL = ["Area"]
FEATURES = NUMERIC + CATEGORICAL
RANDOM_STATE = 42


def load_data(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df = df.drop(columns=["Item"], errors="ignore").dropna()
    return df


def _pipeline(estimator) -> Pipeline:
    preprocess = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ]
    )
    return Pipeline([("preprocess", preprocess), ("model", estimator)])


def candidate_models() -> dict[str, Pipeline]:
    return {
        "Baseline (mean)": _pipeline(DummyRegressor()),
        "Ridge regression": _pipeline(Ridge()),
        "Decision tree": _pipeline(DecisionTreeRegressor(max_depth=8, min_samples_leaf=50, random_state=RANDOM_STATE)),
        "Random forest": _pipeline(
            RandomForestRegressor(n_estimators=300, min_samples_leaf=50, n_jobs=-1, random_state=RANDOM_STATE)
        ),
        "Gradient boosting": _pipeline(
            HistGradientBoostingRegressor(max_depth=4, learning_rate=0.05, max_iter=200, random_state=RANDOM_STATE)
        ),
    }


@dataclass
class TrainingResult:
    best_model: str
    metrics: dict[str, dict[str, float]]


def train(data_path: str | Path, model_path: str | Path) -> TrainingResult:
    """Compare candidate models, refit the best on all data and save it.

    Rows are split *by Area+Year group*, so a model is always scored on
    region-years it has never seen; this is the realistic use case and avoids
    the optimistic scores a purely random row split gives.
    """
    df = load_data(data_path)
    X, y = df[FEATURES], df[TARGET]
    groups = df["Area"] + "-" + df["Year"].astype(str)

    train_idx, test_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_STATE).split(X, y, groups)
    )
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    metrics: dict[str, dict[str, float]] = {}
    cv = GroupKFold(n_splits=5)
    for name, pipe in candidate_models().items():
        cv_r2 = cross_val_score(pipe, X_train, y_train, cv=cv, groups=groups.iloc[train_idx], scoring="r2")
        pred = pipe.fit(X_train, y_train).predict(X_test)
        metrics[name] = {
            "cv_r2": float(cv_r2.mean()),
            "test_r2": float(r2_score(y_test, pred)),
            "test_rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
            "test_mae": float(mean_absolute_error(y_test, pred)),
        }

    best = max(metrics, key=lambda n: metrics[n]["cv_r2"])  # select on CV, never on the test set
    final = candidate_models()[best].fit(X, y)

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": final,
            "areas": sorted(df["Area"].unique()),
            "year_range": [int(df["Year"].min()), int(df["Year"].max())],
            "model_name": best,
            "metrics": metrics,
        },
        model_path,
    )
    model_path.with_suffix(".metrics.json").write_text(json.dumps({"best": best, "metrics": metrics}, indent=2))
    return TrainingResult(best_model=best, metrics=metrics)


class Predictor:
    """Thin wrapper that loads the saved pipeline once and validates inputs."""

    def __init__(self, model_path: str | Path):
        bundle = joblib.load(model_path)
        self.pipeline: Pipeline = bundle["pipeline"]
        self.areas: list[str] = bundle["areas"]
        self.model_name: str = bundle["model_name"]
        self.metrics: dict = bundle["metrics"]

    def predict(self, *, year: int, rainfall: float, pesticides: float, temp: float, area: str) -> float:
        row = pd.DataFrame(
            [
                {
                    "Year": year,
                    "Average_Rainfall_mm_per_year": rainfall,
                    "Pesticides_Tonnes": pesticides,
                    "Avg_Temp": temp,
                    "Area": area,
                }
            ]
        )[FEATURES]
        return max(0.0, float(self.pipeline.predict(row)[0]))

    def what_if(
        self,
        *,
        year: int,
        rainfall: float,
        pesticides: float,
        temp: float,
        area: str,
        rain_range: tuple[float, float],
        curve_points: int = 15,
        heat_levels: int = 5,
    ) -> dict:
        """Everything the live predictor panel shows, from ONE batched model call.

        - ``prediction``: the yield for exactly these inputs
        - ``curve``: yield as rainfall varies (other inputs fixed)
        - ``by_area``: yield for every district at these inputs
        - ``heatmap``: yield for every district at several rainfall levels
        All values are hg/ha.
        """
        low, high = rain_range
        curve_x = [float(v) for v in np.linspace(low, high, curve_points).round(0)]
        heat_x = [float(v) for v in np.linspace(low, high, heat_levels).round(0)]
        base = {
            "Year": year,
            "Average_Rainfall_mm_per_year": rainfall,
            "Pesticides_Tonnes": pesticides,
            "Avg_Temp": temp,
            "Area": area,
        }
        rows = [base]
        rows += [{**base, "Average_Rainfall_mm_per_year": x} for x in curve_x]
        rows += [{**base, "Area": a} for a in self.areas]
        rows += [{**base, "Area": a, "Average_Rainfall_mm_per_year": x} for a in self.areas for x in heat_x]

        values = np.clip(self.pipeline.predict(pd.DataFrame(rows)[FEATURES]), 0, None).astype(float)
        n_curve, n_areas = len(curve_x), len(self.areas)
        curve = values[1 : 1 + n_curve]
        by_area = values[1 + n_curve : 1 + n_curve + n_areas]
        grid = values[1 + n_curve + n_areas :].reshape(n_areas, len(heat_x))
        return {
            "prediction": float(values[0]),
            "curve": {"x": curve_x, "y": curve.tolist()},
            "by_area": [{"area": a, "value": float(v)} for a, v in zip(self.areas, by_area, strict=True)],
            "heatmap": {"areas": list(self.areas), "rainfall": heat_x, "values": grid.tolist()},
        }
