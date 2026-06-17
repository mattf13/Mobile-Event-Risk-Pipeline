# python image
FROM python:3.11-slim

# working directory
WORKDIR /app

# copy and install requirements
COPY services/ingestion_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy api code and shared
COPY services/ingestion_api/ services/ingestion_api/
COPY shared/ shared/

# set python path
ENV PYTHONPATH=/app

# expose port
EXPOSE 8000

# start api
CMD ["python", "services/ingestion_api/main.py"]