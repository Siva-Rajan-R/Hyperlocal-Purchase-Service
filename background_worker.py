import os
from arq.connections import RedisSettings
from infras.primary_db.services.purchase_export_service import process_purchase_export

redis_url = os.getenv("PLATFORM_REDIS_URL") or "redis://localhost:6379"
redis_settings = RedisSettings.from_dsn(redis_url)

async def export_purchases_task(ctx, payload: dict):
    return await process_purchase_export(payload)

async def startup(ctx):
    pass

async def shutdown(ctx):
    pass

class WorkerSettings:
    queue_name = "purchase_export_queue"
    redis_settings = redis_settings
    functions = [export_purchases_task]
    on_startup = startup
    on_shutdown = shutdown

