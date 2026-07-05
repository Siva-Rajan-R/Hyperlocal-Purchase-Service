from fastapi import APIRouter, Depends
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from infras.primary_db.main import get_pg_async_session
from schemas.v1.request_schemas.customfield_schema import (
    CreateCustomFieldSchema, UpdateCustomFieldSchema,
    CreateCustomFieldValueSchema, BulkCreateCustomFieldValuesSchema
)
from api.handlers.customfield_handler import CustomFieldsHandler

router = APIRouter(prefix="/custom-fields", tags=["Custom Fields"])
PG_ASYNC_SESSION=Annotated[AsyncSession,Depends(get_pg_async_session)]

@router.post("")
async def create_field(shop_id: str, data: CreateCustomFieldSchema, session: AsyncSession = Depends(PG_ASYNC_SESSION)):
    return await CustomFieldsHandler.create_field(shop_id=shop_id, data=data, session=session)

@router.get("")
async def get_all_fields(shop_id: str, session: AsyncSession = Depends(PG_ASYNC_SESSION)):
    return await CustomFieldsHandler.get_all_fields(shop_id=shop_id, session=session)

@router.get("/{field_id}")
async def get_field(field_id: str, shop_id: str, session: AsyncSession = Depends(PG_ASYNC_SESSION)):
    return await CustomFieldsHandler.get_field(field_id=field_id, shop_id=shop_id, session=session)

@router.put("/{field_id}")
async def update_field(field_id: str, shop_id: str, data: UpdateCustomFieldSchema, session: AsyncSession = Depends(PG_ASYNC_SESSION)):
    return await CustomFieldsHandler.update_field(field_id=field_id, shop_id=shop_id, data=data, session=session)

@router.delete("/{field_id}")
async def delete_field(field_id: str, shop_id: str, session: AsyncSession = Depends(PG_ASYNC_SESSION)):
    return await CustomFieldsHandler.delete_field(field_id=field_id, shop_id=shop_id, session=session)


@router.post("/values")
async def upsert_value(shop_id: str, data: CreateCustomFieldValueSchema, session: AsyncSession = Depends(PG_ASYNC_SESSION)):
    return await CustomFieldsHandler.upsert_value(shop_id=shop_id, data=data, session=session)

@router.post("/values/bulk")
async def bulk_upsert_values(shop_id: str, data: BulkCreateCustomFieldValuesSchema, session: AsyncSession = Depends(PG_ASYNC_SESSION)):
    return await CustomFieldsHandler.bulk_upsert_values(shop_id=shop_id, data=data, session=session)

@router.get("/values/{purchase_id}")
async def get_values_by_purchase(purchase_id: str, shop_id: str, session: AsyncSession = Depends(PG_ASYNC_SESSION)):
    return await CustomFieldsHandler.get_values_by_purchase(purchase_id=purchase_id, shop_id=shop_id, session=session)
