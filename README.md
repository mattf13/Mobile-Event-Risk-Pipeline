# Mobile Event Risk Pipeline

A microservices architecture for real-time mobile event ingestion and hybrid risk analysis.

## Overview
This project is a simulation of a mobile event risk pipeline, where data is ingested into a message broker, processed by a hybrid risk analysis engine that applies deterministic rules and AI analysis while persisting the results which are then aggregated and stored in a secure database.

## System Architecture
The pipeline consists of four main components orchestrated via Docker Compose:

- **Event Generator (Python)**: A mock event generator for simulating incoming events.
- **Ingestion API (FastAPI):** A high-speed REST endpoint utilizing lifespan management to maintain persistent RabbitMQ connections, reducing latency during event spikes.
- **Message Queue (RabbitMQ):** An asynchronous layer that decouples data entry from analysis, providing system resilience and backpressure management.
- **Risk Scorer (Python):** A hybrid analysis engine featuring two distinct processing stages:
    - **Stage 1 (Deterministic Rules):** A rule-based filter for sub-millisecond detection of known fraud patterns.
    - **Stage 2 (AI Analysis):** Advanced behavioral analysis powered by Llama 3.1 via Groq (OpenAI-compatible API). This stage includes exponential backoff for API resilience and a graceful fallback to deterministic logic.
- **Persistence Layer (PostgreSQL):** Secure storage for analysis results using connection pooling and parameterized queries to mitigate SQL injection risks.

## Technical Stack
- **Languages:** Python 3.11
- **Frameworks:** FastAPI, Pydantic v2
- **Infrastructure:** RabbitMQ, PostgreSQL, Docker
- **Testing & Quality:** Pytest (Unit & Integration), Pylint (10/10 rating), GitHub Actions (CI)

## Key Features
- **Real-time Ingestion:** Efficiently processes mobile events in real-time, ensuring near-real-time risk analysis.
- **Hybrid Analysis:** Combines deterministic rules and AI analysis for enhanced risk detection.
- **Database Persistence:** Secure storage for analysis results, mitigating SQL injection risks.
- **Docker Compose:** Simplified orchestration for local development and production deployments.
- **CI/CD:** Automated testing, linting, and deployment via GitHub Actions.
- **Modularity:** Separation of concerns for maintainability and scalability.

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