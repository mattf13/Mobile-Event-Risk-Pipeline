FROM python:3.11-slim
# Install libpq for Postgres connection
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/risk_scorer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/risk_scorer/main.py .
COPY shared/ shared/
ENV PYTHONPATH=/app
CMD ["python", "main.py"]