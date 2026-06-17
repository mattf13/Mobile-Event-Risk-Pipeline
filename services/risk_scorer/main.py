import pika
import json
import os
import time
import logging
import psycopg2
from psycopg2 import pool
from pydantic import ValidationError
from shared.schemas import MobileEvent

# Professional Logging Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("risk_scorer")


#  Configuration & Environment Validation 
def get_env_mandatory(key: str) -> str:
    """Ensures mandatory environment variables are present."""
    value = os.getenv(key)
    if not value:
        logger.critical(f"MANDATORY_ENV_MISSING: {key}")
        raise EnvironmentError(f"Variable {key} must be set in the environment.")
    return value


# Database Configuration
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "db"),
    "dbname": get_env_mandatory("POSTGRES_DB"),
    "user": get_env_mandatory("POSTGRES_USER"),
    "password": get_env_mandatory("POSTGRES_PASSWORD"),
}

# RabbitMQ Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = get_env_mandatory("RABBITMQ_USER")
RABBITMQ_PASS = get_env_mandatory("RABBITMQ_PASS")
QUEUE_NAME = "mobile_events"

#  Infrastructure Setup 

# Initialize Global Database Pool for thread-safety and performance
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **DB_CONFIG)
    logger.info("Database connection pool established.")
except Exception as e:
    logger.critical(f"Failed to initialize DB pool: {e}")
    exit(1)


def init_db_schema():
    """Initializes the PostgreSQL schema with retry logic for high availability."""
    for attempt in range(1, 11):
        conn = None
        try:
            conn = db_pool.getconn()
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS risk_analysis (
                        event_id UUID PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        event_type VARCHAR(25),
                        score INTEGER CHECK (score >= 0 AND score <= 100),
                        label VARCHAR(10),
                        rationale TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_user_risk ON risk_analysis(user_id);
                """)
                conn.commit()
            logger.info("Database schema is ready.")
            db_pool.putconn(conn)
            return
        except Exception as e:
            logger.warning(f"Database not ready (Attempt {attempt}/10). Error: {e}")
            if conn:
                db_pool.putconn(conn)
            time.sleep(5)
    exit(1)


#  Risk Analysis Logic 


def analyze_risk_stage_1(event: MobileEvent) -> tuple[int, str]:
    """
    Deterministic rule-based risk scoring.
    Stage 1: High-speed filtering of obvious anomalies.
    """
    score = 0
    rationale = "Event analyzed: parameters within safety limits."

    # Rule: High Transaction Value
    if event.amount > 900:
        score, rationale = 95, "CRITICAL: Transaction amount exceeds safety threshold."
    elif event.amount > 450:
        score, rationale = 40, "WARNING: Elevated transaction value."

    # Rule: Event type base risk
    if event.event_type == "login" and score < 10:
        score, rationale = 10, "Routine login monitoring."

    return score, rationale


#  Message Consumption 


def on_message_received(ch, method, properties, body):
    """
    Main consumer callback.
    Implements Zero-Trust validation and secure persistence.
    """
    db_conn = None
    try:
        # 1. Zero-Trust Validation: Re-validate schema using shared Pydantic models
        try:
            event = MobileEvent.model_validate_json(body)
        except ValidationError as ve:
            logger.error(
                f"SECURITY_ALERT: Dropping malformed message. Validation error: {ve}"
            )
            # Acknowledge but discard to prevent "Poison Pill" loops
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # 2. Logic: Apply Rule-Based Engine
        score, rationale = analyze_risk_stage_1(event)
        label = "RED" if score >= 70 else "YELLOW" if score >= 30 else "GREEN"

        # 3. Persistence: Parameterized SQL to prevent SQL Injection
        db_conn = db_pool.getconn()
        with db_conn.cursor() as cur:
            cur.execute(
                """INSERT INTO risk_analysis (event_id, user_id, event_type, score, label, rationale) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    event.event_id,
                    event.user_id,
                    event.event_type,
                    score,
                    label,
                    rationale,
                ),
            )
            db_conn.commit()

        # 4. Acknowledgment: Confirm message processing ONLY after DB commit
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Verified & Stored: Event {event.event_id} | Score: {score}")

    except Exception as e:
        logger.error(f"PROCESS_ERROR: Failed to process event. Re-queueing. Error: {e}")
        # Re-queue the message if it's a transient error (e.g., DB disconnected)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    finally:
        if db_conn:
            db_pool.putconn(db_conn)


def main():
    """Service entry point: Connects to RabbitMQ and starts consuming."""
    init_db_schema()

    # Establish secure connection to Message Broker
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=credentials,
        heartbeat=600,  # Ensure connection stability
    )

    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)

        # Fair Dispatch: Prevent a single worker from being overloaded
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message_received)

        logger.info("Risk Scorer is active. Awaiting mobile events...")
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Service shutting down manually.")
        db_pool.closeall()
    except Exception as e:
        logger.critical(f"FATAL: Service encountered an unrecoverable error: {e}")
        db_pool.closeall()
        exit(1)


if __name__ == "__main__":
    main()
