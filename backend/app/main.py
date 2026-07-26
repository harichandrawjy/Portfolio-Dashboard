import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import engine
from app.routers import auth, health, performance, portfolios, securities
from app.scheduler import create_scheduler
from app.sync.catchup import run_catch_up_after_startup

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    # Scheduled jobs only fire while we are running; this replays whatever
    # was missed while the machine was off (see app/sync/catchup.py).
    catch_up = asyncio.create_task(run_catch_up_after_startup())
    yield
    catch_up.cancel()
    scheduler.shutdown(wait=False)
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(portfolios.router)
    app.include_router(performance.router)
    app.include_router(securities.router)
    return app


app = create_app()
