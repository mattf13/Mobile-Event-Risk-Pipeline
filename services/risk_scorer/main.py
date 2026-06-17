import os
import sys
import time
import logging
import pika
import psycopg2
from psycopg2 import pool
from pydantic import ValidationError
from shared.schemas import MobileEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("risk_scorer")


class RiskScorer:
    def __init__(self):
        self.db_pool = None
        self.connection = None
        self.channel = None

        # Mandatory Configuration
        self.db_config = {
            "host": os.getenv("POSTGRES_HOST", "db"),
            "dbname": self._get_env("POSTGRES_DB"),
            "user": self._get_env("POSTGRES_USER"),
            "password": self._get_env("POSTGRES_PASSWORD"),
        }
        self.rmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.rmq_user = self._get_env("RABBITMQ_USER")
        self.rmq_pass = self._get_env("RABBITMQ_PASS")

    @staticmethod
    def _get_env(key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise EnvironmentError(f"Mandatory variable {key} not set.")
        return value

    def init_infrastructure(self):
        # Initialize Database Pool
        try:
            self.db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **self.db_config)
            logger.info("Database pool established.")
        except Exception as e:
            logger.critical("Failed to start DB pool: %s", e)
            sys.exit(1)

        # Initialize Schema with retry logic
        self._init_db_schema()

    def _init_db_schema(self):
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
                logger.info("Database schema ready.")
                return
            except Exception as e:
                logger.warning("DB not ready (Attempt %s/10): %s", attempt, e)
                if conn:
                    self.db_pool.putconn(conn)
                time.sleep(5)
        sys.exit(1)

    @staticmethod
    def analyze_risk_stage_1(event: MobileEvent) -> tuple[int, str]:
        score = 0
        rationale = "Event analyzed: parameters within safety limits."
        if event.amount > 900:
            score, rationale = 95, "CRITICAL: Transaction exceeds safety threshold."
        elif event.amount > 450:
            score, rationale = 40, "WARNING: Elevated transaction value."

        if event.event_type == "login" and score < 10:
            score, rationale = 10, "Routine login monitoring."
        return score, rationale

    def on_message_received(self, _ch, method, _properties, body):
        db_conn = None
        try:
            # 1. Validation
            event = MobileEvent.model_validate_json(body)

            # 2. Logic
            score, rationale = self.analyze_risk_stage_1(event)
            label = "RED" if score >= 70 else "YELLOW" if score >= 30 else "GREEN"

            # 3. Persistence
            if self.db_pool:
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
            logger.info("Processed: %s | Score: %s", event.event_id, score)

        except ValidationError as ve:
            logger.error("Security Alert: Malformed message dropped. Error: %s", ve)
            _ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error("Processing Error: %s", e)
            _ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        finally:
            if db_conn:
                self.db_pool.putconn(db_conn)

    def start(self):
        self.init_infrastructure()

        credentials = pika.PlainCredentials(self.rmq_user, self.rmq_pass)
        params = pika.ConnectionParameters(host=self.rmq_host, credentials=credentials)

        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="mobile_events", durable=True)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue="mobile_events", on_message_callback=self.on_message_received
        )

        logger.info("Risk Scorer active. Listening for events...")
        self.channel.start_consuming()


if __name__ == "__main__":
    scorer = RiskScorer()
    scorer.start()
