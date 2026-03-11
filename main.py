import sys
import asyncio

if sys.platform == "win32":
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)

import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from agent import run_agent

load_dotenv()

app = FastAPI(title="ShopSight")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "ShopSight running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.websocket("/ws/search")
async def websocket_search(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        payload = json.loads(data)
        product = payload.get("product", "").strip()

        if not product:
            await websocket.send_text(json.dumps({"type": "error", "message": "No product specified"}))
            return

        async def send_event(event: dict):
            try:
                await websocket.send_text(json.dumps(event))
            except Exception:
                pass

        await run_agent(product, send_event)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass