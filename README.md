# Mobile Event Risk Pipeline

High-performance microservices architecture for real-time mobile event ingestion and hybrid risk analysis.

## Overview
This project demonstrates a production-ready data pipeline designed to handle high-frequency mobile events such as transactions, logins, and system pings. The system architecture emphasizes decoupling, security, and the integration of large language models (LLMs) into real-time decision-making workflows.

## System Architecture
The pipeline consists of four main components orchestrated via Docker Compose:

- **Ingestion API (FastAPI):** A high-speed REST endpoint utilizing lifespan management to maintain persistent RabbitMQ connections, reducing latency during event spikes.
- **Message Broker (RabbitMQ):** An asynchronous layer that decouples data entry from analysis, providing system resilience and backpressure management.
- **Risk Scorer (Python):** A hybrid analysis engine featuring two distinct processing stages:
    - **Stage 1 (Deterministic Rules):** A rule-based filter for sub-millisecond detection of known fraud patterns.
    - **Stage 2 (AI Analysis):** Advanced behavioral analysis powered by Llama 3.1 via Groq (OpenAI-compatible API). This stage includes exponential backoff for API resilience and a graceful fallback to deterministic logic.
- **Persistence Layer (PostgreSQL):** Secure storage for analysis results using connection pooling and parameterized queries to mitigate SQL injection risks.

## Technical Stack
- **Languages:** Python 3.11 (Engineered for backward compatibility with Python 3.8+)
- **Frameworks:** FastAPI, Pydantic v2
- **Infrastructure:** RabbitMQ, PostgreSQL, Docker
- **Testing & Quality:** Pytest (Unit & Integration), Pylint (10/10 rating), GitHub Actions (CI)

## Engineering Highlights
- **Zero-Trust Validation:** Every microservice independently re-validates incoming data schemas using shared Pydantic models to ensure data integrity across the broker.
- **Hybrid Inference Strategy:** AI analysis is triggered selectively based on transaction value thresholds or rule-based ambiguity, optimizing for both inference costs and pipeline throughput.
- **Resilience and Fault Tolerance:** The system implements exponential backoff for external AI dependencies and handles automatic message re-queueing (nack/ack) on database or network failures.
- **Resource Efficiency:** Utilizes database connection pooling and persistent broker channels to minimize overhead in high-concurrency environments.

## How to Run

### 1. Environment Setup
Create a `.env` file in the root directory and populate it with the following mandatory variables:
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `RABBITMQ_USER`, `RABBITMQ_PASS`
- `GROQ_API_KEY` (Optional: If missing, the system defaults to mock AI logic)

### 2. Orchestration
Use the provided Python management script to build and start the services:

```bash
# Build the images without cache
python manage.py build

# Start the pipeline in detached mode
python manage.py up