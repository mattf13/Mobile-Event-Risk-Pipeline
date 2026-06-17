from fastapi import FastAPI, status
from shared.schemas import MobileEvent

app = FastAPI(title="Ingestion API")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/events", status_code=status.HTTP_201_CREATED)
async def ingest_event(event: MobileEvent):
    # This will later publish to RabbitMQ
    print(f"Ingested event {event.event_id} of type {event.event_type}")
    return {"message": "Event accepted", "event_id": event.event_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
