import os
import sys
import time
import pika
import uvicorn
from fastapi import FastAPI, status, HTTPException
from shared.schemas import MobileEvent

app = FastAPI(title="Ingestion API")

# Load configuration from environment variables
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
QUEUE_NAME = "mobile_events"


def get_rabbitmq_connection():
    """
    Tries to connect to RabbitMQ with a retry mechanism.
    This prevents the API from crashing during the initial boot of the stack.
    """
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)

    for attempt in range(10):
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            return connection, channel
        except pika.exceptions.AMQPConnectionError:
            print(f"RabbitMQ not ready. Retrying in 5s... (Attempt {attempt+1}/10)")
            time.sleep(5)
    return None, None


@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}


@app.post("/events", status_code=status.HTTP_201_CREATED)
async def ingest_event(event: MobileEvent):
    """
    Receives a MobileEvent, validates it, and pushes it to the RabbitMQ queue.
    """
    conn, ch = get_rabbitmq_connection()
    if not ch:
        raise HTTPException(status_code=503, detail="Message broker unavailable")

    try:
        # Serialize Pydantic model to JSON
        message = event.model_dump_json()

        ch.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2),  # Persistent messages
        )
        conn.close()
        return {"message": "Event accepted", "event_id": event.event_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
