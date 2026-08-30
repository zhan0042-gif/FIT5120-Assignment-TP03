FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY data/__init__.py ./data/__init__.py
COPY data/scripts/__init__.py data/scripts/location_context.py data/scripts/fire_history_lookup.py ./data/scripts/
COPY data/processed/bpa.parquet data/processed/fire_district.parquet data/processed/fire_history_lightweight.parquet ./data/processed/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
