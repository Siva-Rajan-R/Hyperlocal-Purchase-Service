from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from ...handlers.purchase_handler import HandlePurchaseRequest
from fastapi import APIRouter,Query,Depends
from infras.primary_db.main import AsyncSession,get_pg_async_session
from typing import Optional,Annotated,List
from schemas.v1.purchase_schemas.request_schema import CreatePurchaseSchema,UpdatePurchaseSchema,DeletePurchaseSchema,GetPurchaseByIdSchema,GetPurchaseByShopIdSchema,GetAllPurchaseSchemas,GetPurchaseByProductIdSchema,GetPurchaseBySupplierIdSchema
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