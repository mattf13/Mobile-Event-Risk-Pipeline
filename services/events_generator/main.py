import os
import time
import random
import uuid
from datetime import datetime, timezone
import requests

# Load configuration from environment
API_URL = os.getenv("INGESTION_API_URL", "http://ingestion_api:8000/events")
USER_IDS = [f"user_{i}" for i in range(1, 15)]
EVENT_TYPES = ["login", "transaction", "location_ping", "screen_view"]


def generate_mock_event():
    """Generates a random dictionary representing a mobile event."""
    return {
        "event_id": str(uuid.uuid4()),
        "user_id": random.choice(USER_IDS),
        "event_type": random.choice(EVENT_TYPES),
        "amount": (
            round(random.uniform(5.0, 1000.0), 2) if random.random() > 0.7 else 0.0
        ),
        "device_id": f"device_{random.randint(10, 99)}",
        "location": f"{random.uniform(-90, 90)},{random.uniform(-180, 180)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def start_simulation():
    """Main loop that sends events to the Ingestion API."""
    print(f"Starting simulation. Target API: {API_URL}")
    # Wait for the API to be fully up
    time.sleep(15)

    while True:
        event_data = generate_mock_event()
        try:
            response = requests.post(API_URL, json=event_data, timeout=5)
            if response.status_code == 201:
                print(
                    f"Success: Sent {event_data['event_type']} for {event_data['user_id']}"
                )
            else:
                print(f"Warning: API responded with {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Connection error: {e}")

        # Random interval between events
        time.sleep(random.uniform(2, 6))


if __name__ == "__main__":
    start_simulation()
