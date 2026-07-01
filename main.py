from fastapi import FastAPI
from api.routers.v1 import purchase_route
from contextlib import asynccontextmanager
from icecream import ic
from dotenv import load_dotenv
from core.configs.settings_config import SETTINGS
from infras.primary_db.main import init_inventory_pg_db
from hyperlocal_platform.core.enums.environment_enum import EnvironmentEnum
import os,asyncio
from hyperlocal_platform.infras.saga.main import init_infra_db
from messaging.worker import worker
from infras.caching.main import redis_client,check_redis_health
load_dotenv()


@asynccontextmanager
async def inventory_service_lifespan(app:FastAPI):
    try:
        ic("Starting purchase service...")
        await init_infra_db()
        await init_inventory_pg_db()
        await check_redis_health()
        # await redis_client.flushdb()
        asyncio.create_task(worker())
        yield

    except Exception as e:
        ic(f"Error : Starting purchase service => {e}")

    finally:
        ic("...Stoping purchase Servcie...")

debug=False
openapi_url=None
docs_url=None
redoc_url=None

if SETTINGS.ENVIRONMENT.value==EnvironmentEnum.DEVELOPMENT.value:
    debug=True
    openapi_url="/openapi.json"
    docs_url="/docs"
    redoc_url="/redoc"

app=FastAPI(
    title="Purchase Service",
    description="This service contains all the CRUD operations for purchase service",
    debug=debug,
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=inventory_service_lifespan,
    root_path="/inventories"

)



# Routes to include

app.include_router(purchase_route.router)



