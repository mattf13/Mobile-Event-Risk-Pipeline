"""Ingestion API service for the Mobile Event Risk Pipeline."""

from __future__ import annotations
import os
import logging
from contextlib import asynccontextmanager
import pika
from fastapi import FastAPI, status, HTTPException
from shared.schemas import MobileEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingestion_api")


class RabbitMQManager:
    """Manages persistent RabbitMQ connections."""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.user = os.getenv("RABBITMQ_USER", "guest")
        self.password = os.getenv("RABBITMQ_PASS", "guest")

    def connect(self):
        """Establish the connection and channel."""
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(host=self.host, credentials=credentials)
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="mobile_events", durable=True)
        logger.info("Persistent RabbitMQ connection established.")

    def publish(self, message: str):
        """Publish a message using the persistent channel."""
        if not self.channel or self.channel.is_closed:
            self.connect()
        self.channel.basic_publish(
            exchange="",
            routing_key="mobile_events",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def close(self):
        """Safely close the connection."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()


rmq = RabbitMQManager()


@asynccontextmanager
async def lifespan(_app: FastAPI):  # Prefix with _ to avoid redefined-outer-name
    """Lifecycle manager for the FastAPI application."""
    try:
        rmq.connect()
    except pika.exceptions.AMQPError as e:
        logger.error(
            "Failed to connect to RabbitMQ at startup: %s", e
        )  # Use % formatting
    yield
    rmq.close()


app = FastAPI(title="Ingestion API", lifespan=lifespan)


@app.get("/health")
def health_check():
    """Service health status endpoint."""
    if rmq.connection and rmq.connection.is_open:
        return {"status": "healthy", "broker": "connected"}
    raise HTTPException(status_code=503, detail="Broker disconnected")


@app.post("/events", status_code=status.HTTP_201_CREATED)
async def ingest_event(event: MobileEvent):
    """Receive and queue a mobile event."""
    try:
        message = event.model_dump_json()
        rmq.publish(message)
        return {"event_id": event.event_id, "status": "accepted"}
    except pika.exceptions.AMQPError as e:
        logger.error("Broker error: %s", e)  # Use % formatting
        raise HTTPException(status_code=503, detail="Message broker unavailable") from e
