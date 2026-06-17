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

# Global DB pool initialized to None to prevent side effects on import
db_pool = None


# --- Configuration & Environment Validation ---
def get_env_mandatory(key: str) -> str:
    """Ensures mandatory environment variables are present."""
    value = os.getenv(key)
    if not value:
        logger.critical(f"MANDATORY_ENV_MISSING: {key}")
        raise EnvironmentError(f"Variable {key} must be set in the environment.")
    return value


# Load DB config
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "db"),
    "dbname": os.getenv("POSTGRES_DB", "risk_db"),
    "user": os.getenv("POSTGRES_USER", "admin"),
    "password": os.getenv("POSTGRES_PASSWORD", "securepassword"),
}

# --- Risk Analysis Logic (Unit-Testable) ---


def analyze_risk_stage_1(event: MobileEvent) -> tuple[int, str]:
    """
    Deterministic rule-based risk scoring.
    This function is pure logic and can be tested without a database.
    """
    score = 0
    rationale = "Event analyzed: parameters within safety limits."

    # Rule: High Transaction Value
    if event.amount > 900:
        score, rationale = 95, "CRITICAL: Transaction amount exceeds safety threshold."
    elif event.amount > 450:
        score, rationale = 40, "WARNING: Elevated transaction value."

    # Rule: Login events base risk
    if event.event_type == "login" and score < 10:
        score, rationale = 10, "Routine login monitoring."

    return score, rationale


# --- Infrastructure Helpers ---


def init_db_schema():
    """Initializes the PostgreSQL schema using the global connection pool."""
    global db_pool
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
            logger.info("Database schema initialized successfully.")
            db_pool.putconn(conn)
            return
        except Exception as e:
            logger.warning(f"Database not ready (Attempt {attempt}/10). Error: {e}")
            if conn:
                db_pool.putconn(conn)
            time.sleep(5)
    exit(1)


# --- Message Consumption ---


def on_message_received(ch, method, properties, body):
    """
    Consumer callback.
    Implements Zero-Trust validation and parameterized SQL persistence.
    """
    global db_pool
    db_conn = None
    try:
        # 1. Zero-Trust Validation: Re-validate schema using shared models
        try:
            event = MobileEvent.model_validate_json(body)
        except ValidationError as ve:
            logger.error(f"SECURITY_ALERT: Dropping malformed message. Error: {ve}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # 2. Logic: Apply Rule-Based Engine
        score, rationale = analyze_risk_stage_1(event)
        label = "RED" if score >= 70 else "YELLOW" if score >= 30 else "GREEN"

        # 3. Persistence: Only if DB pool is initialized (prevents crash in dry-runs)
        if db_pool:
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

        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Processed: {event.event_id} | Score: {score}")

    except Exception as e:
        logger.error(f"PROCESS_ERROR: {e}")
        # Re-queue for transient errors (e.g. DB connection loss)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    finally:
        if db_conn:
            db_pool.putconn(db_conn)


def main():
    """Service entry point: Infrastructure starts here."""
    global db_pool

    # Mandatory variables check before connecting
    rabbitmq_user = get_env_mandatory("RABBITMQ_USER")
    rabbitmq_pass = get_env_mandatory("RABBITMQ_PASS")
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")

    # 1. Initialize DB Pool
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **DB_CONFIG)
        logger.info("Database pool established.")
    except Exception as e:
        logger.critical(f"Failed to start DB pool: {e}")
        exit(1)

    init_db_schema()

    # 2. Connect to RabbitMQ
    credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
    params = pika.ConnectionParameters(
        host=rabbitmq_host, credentials=credentials, heartbeat=600
    )

    try:
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue="mobile_events", durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue="mobile_events", on_message_callback=on_message_received
        )

        logger.info("Risk Scorer is active. Awaiting mobile events...")
        channel.start_consuming()
    except Exception as e:
        logger.critical(f"FATAL: Service crashed: {e}")
        if db_pool:
            db_pool.closeall()
        exit(1)


if __name__ == "__main__":
    main()
