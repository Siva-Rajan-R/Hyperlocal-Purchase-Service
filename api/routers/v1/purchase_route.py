from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from ...handlers.purchase_handler import HandlePurchaseRequest
from fastapi import APIRouter,Query,Depends
from infras.primary_db.main import AsyncSession,get_pg_async_session
from typing import Optional,Annotated,List
from schemas.v1.purchase_schemas.request_schema import CreatePurchaseSchema,UpdatePurchaseSchema,DeletePurchaseSchema,GetPurchaseByIdSchema,GetPurchaseByShopIdSchema,GetAllPurchaseSchemas
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums,PurchaseViewsEnums


router=APIRouter(
    tags=["Purchase Crud's"],
    prefix="/purchases"
)

SHOP_ID="37d5519b-51a1-5854-982b-4d6524171017"
ADDED_BY="siva-user"

ASYNC_PG_SESSION=Annotated[AsyncSession,Depends(get_pg_async_session)]

@router.post("")
async def create(data:CreatePurchaseSchema,session:ASYNC_PG_SESSION):
    return await HandlePurchaseRequest(session=session).create(data=data)


@router.put("")
async def update(data:UpdatePurchaseSchema,session:ASYNC_PG_SESSION):
    return await HandlePurchaseRequest(session=session).update(data=data,user_id=ADDED_BY)



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