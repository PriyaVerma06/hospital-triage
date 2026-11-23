"""
WebSocket demo client for monitoring hospital emergency triage live updates.
Authenticates via OAuth2 login endpoint and connects to /ws?token=<jwt> to stream real-time events.
"""

import argparse
import asyncio
import json
import sys
import httpx
import websockets


def get_auth_token(api_url: str, username: str, password: str) -> str:
    """Log in via OAuth2 form endpoint and retrieve JWT access token."""
    login_url = f"{api_url.rstrip('/')}/auth/login"
    print(f"Authenticating as '{username}' at {login_url}...")
    try:
        response = httpx.post(
            login_url,
            data={"username": username, "password": password},
            timeout=10.0,
        )
        if response.status_code != 200:
            print(f"Login failed [{response.status_code}]: {response.text}")
            sys.exit(1)
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        print(f"✓ Logged in as: {user.get('full_name')} ({user.get('username')}) - Role: {user.get('role')}")
        return token
    except Exception as e:
        print(f"Authentication connection error: {e}")
        sys.exit(1)


async def listen(ws_base_url: str, token: str):
    """Connect to authenticated WebSocket endpoint and stream incoming events."""
    full_ws_url = f"{ws_base_url.rstrip('/')}?token={token}"
    print(f"Connecting to WebSocket at: {ws_base_url}?token=***")
    try:
        async with websockets.connect(full_ws_url) as ws:
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
    parser = argparse.ArgumentParser(description="Hospital Triage WebSocket Demo Client")
    parser.add_argument("-u", "--username", default="nurse1", help="Username for authentication (default: nurse1)")
    parser.add_argument("-p", "--password", default="demo123", help="Password for authentication (default: demo123)")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="HTTP API base URL (default: http://127.0.0.1:8000)")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/ws", help="Base WebSocket URL (default: ws://127.0.0.1:8000/ws)")
    args = parser.parse_args()

    token = get_auth_token(api_url=args.api_url, username=args.username, password=args.password)
    try:
        asyncio.run(listen(args.ws_url, token))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
