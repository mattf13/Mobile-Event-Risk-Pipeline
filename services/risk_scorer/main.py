from __future__ import annotations
import os
import sys
import time
import logging
import pika
import psycopg2
import psycopg2.pool
from pydantic import ValidationError
from shared.schemas import MobileEvent

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("risk_scorer")


class RiskScorer:
    """
    Consumer service that processes mobile events from RabbitMQ,
    applies hybrid risk scoring, and persists results to PostgreSQL.
    """

    def __init__(self):
        self.db_pool = None
        self.connection = None
        self.channel = None

        # Mandatory Infrastructure Configuration
        try:
            self.db_config = {
                "host": os.getenv("POSTGRES_HOST", "db"),
                "dbname": self._get_env("POSTGRES_DB"),
                "user": self._get_env("POSTGRES_USER"),
                "password": self._get_env("POSTGRES_PASSWORD"),
            }
            self.rmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
            self.rmq_user = self._get_env("RABBITMQ_USER")
            self.rmq_pass = self._get_env("RABBITMQ_PASS")
        except EnvironmentError as e:
            logger.critical("Configuration error: %s", e)
            sys.exit(1)

    @staticmethod
    def _get_env(key: str) -> str:
        """Helper to fetch mandatory environment variables."""
        value = os.getenv(key)
        if not value:
            raise EnvironmentError(f"Mandatory variable {key} is not set.")
        return value

    def init_infrastructure(self):
        """Initializes database connection pool and schema."""
        try:
            self.db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **self.db_config)
            logger.info("Database connection pool established.")
        except psycopg2.Error as e:
            logger.critical("Failed to initialize DB pool: %s", e)
            sys.exit(1)

        self._init_db_schema()

    def _init_db_schema(self):
        """Creates the necessary database tables with idempotent logic."""
        for attempt in range(1, 11):
            conn = None
            try:
                conn = self.db_pool.getconn()
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
                self.db_pool.putconn(conn)
                logger.info("Database schema initialized and ready.")
                return
            except psycopg2.OperationalError as e:
                logger.warning("Database not ready (Attempt %s/10): %s", attempt, e)
                if conn:
                    self.db_pool.putconn(conn)
                time.sleep(5)
        sys.exit(1)

    @staticmethod
    def analyze_risk_stage_1(event: MobileEvent) -> tuple[int, str]:
        """
        Stage 1: Deterministic rule-based scoring.
        Handles high-speed filtering of obvious anomalies.
        """
        score = 0
        rationale = "Event analyzed: parameters within safety limits."

        if event.amount > 900:
            score, rationale = 95, "CRITICAL: Transaction exceeds safety threshold."
        elif event.amount > 450:
            score, rationale = 40, "WARNING: Elevated transaction value."

        if event.event_type == "login" and score < 10:
            score, rationale = 10, "Routine login monitoring."

        return score, rationale

    @staticmethod
    def analyze_risk_stage_2_mock_llm(event: MobileEvent) -> tuple[int, str]:
        """
        Stage 2: Simulated LLM Analysis for complex behavioral patterns.
        """
        # Simulation: detect patterns like 'impossible travel' or 'bot-like' device strings
        if "device_999" in event.device_id:
            return (
                85,
                "LLM_REPORT: Behavioral pattern matches known botnet fingerprints.",
            )
        return 0, ""

    def on_message_received(self, _ch, method, _properties, body):
        """
        Callback triggered upon receiving a message from RabbitMQ.
        Performs Zero-Trust validation and dual-stage risk analysis.
        """
        db_conn = None
        try:
            # 1. Zero-Trust Schema Validation
            event = MobileEvent.model_validate_json(body)

            # 2. Hybrid Risk Analysis
            score, rationale = self.analyze_risk_stage_1(event)

            # Trigger Stage 2 if Stage 1 is inconclusive (Low/Mid risk)
            if score < 50:
                llm_score, llm_rationale = self.analyze_risk_stage_2_mock_llm(event)
                if llm_score > score:
                    score, rationale = llm_score, llm_rationale

            label = "RED" if score >= 70 else "YELLOW" if score >= 30 else "GREEN"

            # 3. Secure Persistence
            db_conn = self.db_pool.getconn()
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

            _ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(
                "Processed & Stored: %s | Final Score: %s", event.event_id, score
            )

        except ValidationError as ve:
            logger.error("Security Alert: Malformed message discarded. Error: %s", ve)
            _ch.basic_ack(delivery_tag=method.delivery_tag)
        except (psycopg2.Error, pika.exceptions.AMQPError) as net_err:
            logger.error("Infrastructure Error (Re-queueing): %s", net_err)
            _ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        finally:
            if db_conn:
                self.db_pool.putconn(db_conn)

    def start(self):
        """Starts the consumer service and listens for events."""
        self.init_infrastructure()

        credentials = pika.PlainCredentials(self.rmq_user, self.rmq_pass)
        params = pika.ConnectionParameters(
            host=self.rmq_host, credentials=credentials, heartbeat=600
        )

        try:
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue="mobile_events", durable=True)

            # Ensure fair workload distribution
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue="mobile_events", on_message_callback=self.on_message_received
            )

            logger.info("Risk Scorer active. Monitoring mobile event stream...")
            self.channel.start_consuming()
        except pika.exceptions.AMQPError as e:
            logger.critical("Broker connection failed: %s", e)
            if self.db_pool:
                self.db_pool.closeall()
            sys.exit(1)


if __name__ == "__main__":
    scorer = RiskScorer()
    try:
        scorer.start()
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
        sys.exit(0)
