# Mobile Event Risk Pipeline

**A high-performance microservices pipeline for real-time mobile event analytics and LLM-based fraud detection.**

## Overview
This project simulates a fintech mobile environment where millions of user events (transactions, logins, pings) are ingested, processed, and scored for risk in real-time. It uses a hybrid approach: a high-speed rule-based engine for immediate filtering and an LLM-based analyzer for complex pattern recognition.

### Key Features
- **Event-Driven Architecture**: Decoupled microservices using RabbitMQ.
- **Hybrid Risk Scoring**: Rule-based (FastAPI) + AI-powered (Claude/OpenAI) anomaly detection.
- **Production-Ready**: Fully containerized with Docker, includes CI/CD pipelines and unit testing.
- **Data Integrity**: Enforced schemas and persistence in PostgreSQL.

## Architecture
```text
[Event Generator] -> [Ingestion API] -> [RabbitMQ] -> [Risk Scorer (Rule + LLM)] -> [Postgres]