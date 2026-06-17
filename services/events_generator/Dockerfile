FROM python:3.11-slim

WORKDIR /app

# Copy requirements from the specific service folder
COPY services/events_generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the service logic
COPY services/events_generator/main.py .

CMD ["python", "main.py"]