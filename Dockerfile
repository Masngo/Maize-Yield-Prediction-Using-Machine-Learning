FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data
# Editable install keeps the data/ and models/ paths resolvable; the model is trained at build time.
RUN pip install --no-cache-dir -e ".[postgres]" && python -m maize_yield.train_cli

RUN useradd --create-home appuser && mkdir -p /app/instance && chown -R appuser /app
USER appuser

EXPOSE 8000
# One worker + threads keeps memory low enough for 512 MB hosts. $PORT is set by most platforms.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 120 'maize_yield:create_app()'"]
