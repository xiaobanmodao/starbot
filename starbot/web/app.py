import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from ..agent import Agent, Event

app = FastAPI()
_agent: Agent | None = None
_static = Path(__file__).parent / "static"


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "clear":
                _agent.reset()
                await ws.send_json({"type": "cleared"})
                continue
            if data.get("type") == "confirm":
                _agent.confirm(data.get("approved", False))
                continue

            user_input = data.get("content", "")
            if not user_input:
                continue

            async for event in _agent.run(user_input):
                msg = {"type": event.type, **event.data}
                await ws.send_json(msg)

            await ws.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass


@app.get("/")
async def index():
    return FileResponse(_static / "index.html")


app.mount("/static", StaticFiles(directory=str(_static)), name="static")


def run_web(cfg: dict):
    import uvicorn
    global _agent
    _agent = Agent(cfg)
    uvicorn.run(app, host=cfg["web"]["host"], port=cfg["web"]["port"])
