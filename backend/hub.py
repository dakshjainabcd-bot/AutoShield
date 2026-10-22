"""Broadcast hub: remembers the connected WebSocket clients and sends to all of them."""
import asyncio
import json
from collections import deque


class Hub:
    def __init__(self, max_events=1000, send_timeout_s=1.0):
        self.clients = set()
        self.latest = None                    # last telemetry message
        self.events = deque(maxlen=max_events)
        self.send_timeout_s = send_timeout_s

    async def connect(self, ws):
        await ws.accept()
        self.clients.add(ws)
        if self.latest is not None:           # a new browser sees data immediately
            await self._send(ws, json.dumps(self.latest))

    def disconnect(self, ws):
        self.clients.discard(ws)

    async def _send(self, ws, text):
        try:
            await asyncio.wait_for(ws.send_text(text), timeout=self.send_timeout_s)
        except Exception:                     # closed, or too slow: drop this client
            self.clients.discard(ws)

    async def broadcast(self, msg):
        if not self.clients:
            return
        text = json.dumps(msg)
        await asyncio.gather(*(self._send(ws, text) for ws in list(self.clients)))
