# Mobile Event Risk Pipeline

Microservices pipeline for real-time mobile event analytics and LLM-based anomaly detection.

## Overview
This system processes a high-volume stream of mobile user events (logins, transactions, location updates) to detect risk and fraud. It employs a two-stage scoring mechanism: a deterministic rule-based engine for high-speed filtering and an LLM-based analyzer for complex behavioral pattern recognition.

## Architecture
The system consists of the following decoupled components:
- Event Generator: Simulates mobile application traffic and anomalous patterns.
- Ingestion API: RESTful endpoint for event entry and validation.
- Message Broker: RabbitMQ for asynchronous event distribution.
- Risk Scorer: Hybrid service combining logic-based filters and LLM analysis.
- Data Store: PostgreSQL for persistent storage of events and risk metadata.

## Technical Stack
- Language: Python 3.11+
- Framework: FastAPI
- Messaging: RabbitMQ
- Database: PostgreSQL
- Infrastructure: Docker, Docker Compose
- CI/CD: GitHub Actions
- Testing: Pytest

## Setup and Configuration
The system uses environment variables for configuration. A `.env` file must be created in the root directory. 
Example configuration:
- RABBITMQ_USER: Username for the message broker.
- RABBITMQ_PASS: Password for the message broker.
- INGESTION_API_URL: Endpoint for the event generator.

## How to Run
python manage.py up
python manage.py logs