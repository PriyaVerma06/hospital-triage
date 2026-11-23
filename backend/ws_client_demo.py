"""
WebSocket demo client for monitoring hospital emergency triage live updates.
Connects to ws://127.0.0.1:8000/ws?role=nurse and prints all received events.
"""

import asyncio
import json
import sys
import websockets


async def listen(url: str = "ws://127.0.0.1:8000/ws?role=nurse"):
    """Connect to the WebSocket endpoint and stream incoming events."""
    print(f"Connecting to WebSocket at: {url}")
    try:
        async with websockets.connect(url) as ws:
            print("Connected successfully! Listening for live hospital events (Ctrl+C to stop)...")
            print("-" * 60)
            while True:
                msg = await ws.recv()
                try:
                    event = json.loads(msg)
                    event_type = event.get("type", "unknown")
                    print(f"[EVENT: {event_type}] {json.dumps(event)}")
                except Exception:
                    print(f"[MESSAGE] {msg}")
    except KeyboardInterrupt:
        print("\nWebSocket client stopped.")
    except Exception as e:
        print(f"WebSocket connection error: {e}")


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8000/ws?role=nurse"
    try:
        asyncio.run(listen(url))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
