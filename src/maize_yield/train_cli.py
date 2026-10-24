"""``python -m maize_yield.train_cli`` - train the model without starting the web app."""

from .config import Config
from .ml import train

if __name__ == "__main__":
    result = train(Config.DATA_PATH, Config.MODEL_PATH)
    print(f"Saved model: {result.best_model}")
