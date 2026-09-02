from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from ...handlers.purchase_handler import HandlePurchaseRequest
from fastapi import APIRouter,Query,Depends
from infras.primary_db.main import AsyncSession,get_pg_async_session
from typing import Optional,Annotated,List
from schemas.v1.purchase_schemas.request_schema import CreatePurchaseSchema,UpdatePurchaseSchema,DeletePurchaseSchema,GetPurchaseByIdSchema,GetPurchaseByShopIdSchema,GetAllPurchaseSchemas,GetPurchaseByProductIdSchema,GetPurchaseBySupplierIdSchema,CancelPurchaseSchema
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums,PurchaseViewsEnums


router=APIRouter(
    tags=["Purchase Crud's"],
    prefix="/purchases"
)

from core.utils.user_info import get_current_user_id

SHOP_ID="37d5519b-51a1-5854-982b-4d6524171017"

ASYNC_PG_SESSION=Annotated[AsyncSession,Depends(get_pg_async_session)]

@router.post("")
async def create(data:CreatePurchaseSchema,session:ASYNC_PG_SESSION,user_id: Optional[str] = Depends(get_current_user_id)):
    return await HandlePurchaseRequest(session=session).create(data=data, executing_user_id=user_id or "")


@router.put("")
async def update(data:UpdatePurchaseSchema,session:ASYNC_PG_SESSION,user_id: Optional[str] = Depends(get_current_user_id)):
    return await HandlePurchaseRequest(session=session).update(data=data,user_id=user_id or "")


@router.post("/cancel")
async def cancel(data: CancelPurchaseSchema, session: ASYNC_PG_SESSION, user_id: Optional[str] = Depends(get_current_user_id)):
    return await HandlePurchaseRequest(session=session).cancel(data=data, executing_user_id=user_id or "")




@router.delete("/{shop_id}/{id}")
async def delete(session:ASYNC_PG_SESSION,data:DeletePurchaseSchema=Depends()):
    return await HandlePurchaseRequest(session=session).delete(data=data)



@router.get("")
async def get(session:ASYNC_PG_SESSION,data:GetAllPurchaseSchemas=Depends()):
    return await HandlePurchaseRequest(session=session).get_purchases(data=data)


@router.get("/by/shop/{shop_id}")
async def search(session:ASYNC_PG_SESSION, data:GetPurchaseByShopIdSchema=Depends()):
    return await HandlePurchaseRequest(session=session).get_purchases_by_shop_id(data=data)

@router.get("/by/id/{shop_id}/{id}")
async def get_supplier_stats(session:ASYNC_PG_SESSION,data:GetPurchaseByIdSchema=Depends()):
    return await HandlePurchaseRequest(session=session).get_purchase_by_id(data=data)

@router.get("/by/product/{shop_id}/{product_id}")
async def get_by_product(session:ASYNC_PG_SESSION, data:GetPurchaseByProductIdSchema=Depends()):
    return await HandlePurchaseRequest(session=session).get_purchases_by_product_id(data=data)

@router.get("/by/supplier/{shop_id}/{supplier_id}")
async def get_by_supplier(session:ASYNC_PG_SESSION, data:GetPurchaseBySupplierIdSchema=Depends()):
    return await HandlePurchaseRequest(session=session).get_purchases_by_supplier_id(data=data)

@router.get("/history/{shop_id}/{id}")
async def get_purchase_history(shop_id: str, id: str, session: ASYNC_PG_SESSION):
    return await HandlePurchaseRequest(session=session).get_purchase_history(shop_id=shop_id, id=id)


# --- Export Routes ---
from schemas.v1.export_schemas import ExportDataRequestSchema
from arq import create_pool
from arq.connections import RedisSettings
import json, os, uuid
from hyperlocal_platform.core.models.req_res_models import SuccessResponseTypDict, BaseResponseTypDict
from fastapi import HTTPException
import redis.asyncio as aioredis

REDIS_URL = os.getenv("PLATFORM_REDIS_URL") or "redis://localhost:6379"

@router.post('/export')
async def export_purchases(data: ExportDataRequestSchema):
    job_id = str(uuid.uuid4())
    payload = data.model_dump()
    payload["job_id"] = job_id
    
    redis = await create_pool(RedisSettings.from_dsn(REDIS_URL))
    await redis.enqueue_job("export_purchases_task", payload, _job_id=job_id, _queue_name="purchase_export_queue")
    await redis.close()

    
    # Store initial state in Redis
    redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.set(
        f"EXPORT_JOB:{job_id}",
        json.dumps({
            "job_id": job_id,
            "entity": "PURCHASE",
            "status": "QUEUED",
            "params": payload
        }),
        ex=86400
    )
    await redis_client.aclose()
    
    return SuccessResponseTypDict(
        detail=BaseResponseTypDict(
            msg="Purchase export job scheduled successfully in the background",
            status_code=202,
            success=True
        ),
        data={
            "job_id": job_id,
            "entity": "PURCHASE",
            "status": "QUEUED"
        }
    )

@router.get('/export/status/{job_id}')
async def get_purchase_export_status(job_id: str):
    redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    raw = await redis_client.get(f"EXPORT_JOB:{job_id}")
    await redis_client.aclose()
    
    if not raw:
        raise HTTPException(status_code=404, detail="Export job not found")
        
    return SuccessResponseTypDict(
        detail=BaseResponseTypDict(
            msg="Export status fetched successfully",
            status_code=200,
            success=True
        ),
        data=json.loads(raw)
    )