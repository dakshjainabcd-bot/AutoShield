"""AutoShield backend (roadmap steps 2.6 to 2.8).

Run from the repository root:
    python -m uvicorn backend.main:app --port 8000

Settings (environment variables, all optional):
    AUTOSHIELD_SPEED   simulation speed, 1 = real time (default 1)
    AUTOSHIELD_SEED    random seed of the simulated vehicle (default 1)
    AUTOSHIELD_DB      path of the SQLite file (default autoshield.db in the repo root)
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.gateway import BenchError, VirtualGateway
from backend.hub import Hub
from backend.store import Store
from core.model import MODEL_PATH, SvmModel

log = logging.getLogger("autoshield")

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


class InjectBody(BaseModel):
    fault: Literal["flood", "hang", "drift", "faulty_fw"]
    duration_ms: Optional[int] = Field(None, ge=1, le=60000)
    slope: Optional[float] = Field(None, ge=-1000, le=1000)


class ControlBody(BaseModel):
    cmd: Literal["auto_recovery", "reset_bench", "test_burst"]
    on: Optional[bool] = None
    ms: Optional[int] = Field(None, ge=1, le=60000)


class RunStartBody(BaseModel):
    label: str = Field("run", max_length=80)


async def gateway_loop(app, speed):
    """Steps the virtual gateway in real time and publishes every message."""
    gw, hub, store = app.state.gw, app.state.hub, app.state.store
    period = gw.step_s / speed
    loop = asyncio.get_running_loop()
    next_t = loop.time()
    n = 0
    while True:
        try:
            tel, events = await asyncio.to_thread(gw.step)   # never block the event loop
            store.add_telemetry(tel)
            hub.latest = tel
            await hub.broadcast(tel)
            for ev in events:
                store.add_event(ev)
                hub.events.append(ev)
                await hub.broadcast(ev)
            n += 1
            if n % 10 == 0:                                   # about once per second
                await asyncio.to_thread(store.flush)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("gateway step failed; retrying in 1 s")
            await asyncio.sleep(1.0)
            next_t = loop.time()
            continue
        next_t += period
        delay = next_t - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
        else:                                                 # we are behind: do not burst
            next_t = loop.time()
            await asyncio.sleep(0)


def create_app(speed=None, db_path=None, seed=None, model_path=None, autostart=True):
    speed = float(speed if speed is not None else os.environ.get("AUTOSHIELD_SPEED", "1"))
    seed = int(seed if seed is not None else os.environ.get("AUTOSHIELD_SEED", "1"))
    db_path = db_path or os.environ.get("AUTOSHIELD_DB") or str(ROOT / "autoshield.db")
    model_path = Path(model_path or MODEL_PATH)

    @asynccontextmanager
    async def lifespan(app):
        model = None
        if model_path.exists():
            model = SvmModel.load(model_path)
        else:
            log.warning("no model file at %s: running WITHOUT the SVM (run python -m ml.train)",
                        model_path)
        store = Store(db_path)
        gw = VirtualGateway(seed=seed, model=model, mode="sim")
        app.state.store, app.state.gw, app.state.hub = store, gw, Hub()
        gw.set_run_id(store.start_run("live", gw.mode, gw.model_version, gw.config_summary()))
        task = asyncio.create_task(gateway_loop(app, speed)) if autostart else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            store.stop_run()
            store.close()

    app = FastAPI(title="AutoShield backend", version="2.0", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/state")
    def state():
        if app.state.hub.latest is None:
            raise HTTPException(404, "no telemetry yet")
        return app.state.hub.latest

    @app.get("/api/events")
    def events(limit: int = Query(100, ge=1, le=1000)):
        return list(app.state.hub.events)[-limit:]

    @app.post("/api/inject")
    def inject(body: InjectBody):
        params = {}
        if body.fault == "flood":
            params["duration_s"] = (body.duration_ms or 5000) / 1000.0     # ms in the API, s in the simulator
        elif body.fault == "drift":
            params["slope"] = body.slope if body.slope is not None else 50.0
        try:
            app.state.gw.apply(body.fault, **params)
        except BenchError as e:
            raise HTTPException(409, str(e))
        return {"ok": True, "fault": body.fault, "params": params}

    @app.post("/api/control")
    def control(body: ControlBody):
        gw = app.state.gw
        if body.cmd == "auto_recovery":
            if body.on is None:
                raise HTTPException(422, "auto_recovery needs \"on\": true or false")
            gw.set_auto_recovery(body.on)
        elif body.cmd == "reset_bench":
            gw.reset_bench()
        else:
            gw.apply("test_burst", duration_s=(body.ms or 2000) / 1000.0)
        return {"ok": True, "cmd": body.cmd}

    @app.get("/api/runs")
    def runs():
        return app.state.store.list_runs()

    @app.post("/api/runs/start")
    def runs_start(body: RunStartBody):
        gw, store = app.state.gw, app.state.store
        run_id = store.start_run(body.label, gw.mode, gw.model_version, gw.config_summary())
        gw.set_run_id(run_id)
        return {"run_id": run_id}

    @app.post("/api/runs/stop")
    def runs_stop():
        stopped = app.state.store.stop_run()
        app.state.gw.set_run_id(0)
        return {"stopped_run_id": stopped}

    @app.get("/api/export.csv")
    def export_csv(run_id: int = Query(..., ge=1), what: Literal["telemetry", "events"] = "telemetry"):
        store = app.state.store
        if not store.run_exists(run_id):
            raise HTTPException(404, f"no run with id {run_id}")
        return Response(store.export_csv(run_id, what), media_type="text/csv",
                        headers={"Content-Disposition":
                                 f'attachment; filename="run{run_id}_{what}.csv"'})

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        hub = app.state.hub
        await hub.connect(ws)
        try:
            while True:
                await ws.receive_text()        # the browser sends nothing; this notices a disconnect
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(ws)

    if WEB_DIR.is_dir():                        # LAST: static files must not shadow the API routes
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app


app = create_app()
