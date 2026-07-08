from fastapi import APIRouter, Depends
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from infras.primary_db.main import get_pg_async_session
from schemas.v1.request_schemas.customfield_schema import (
    CreateCustomFieldSchema, UpdateCustomFieldSchema,
    CreateCustomFieldValueSchema, BulkCreateCustomFieldValuesSchema,DeleteCustomFieldSchema,GetFieldById,GetFieldByName,GetFieldByShopIdSchema,GetValueByIdName,GetvaluesByCustomerId
)
from api.handlers.customfield_handler import CustomFieldsHandler

router = APIRouter(prefix="/custom-fields", tags=["Custom Fields"])

PG_ASYNC_SESSION=Annotated[AsyncSession,Depends(get_pg_async_session)]

@router.post("")
async def create_field(data: CreateCustomFieldSchema, session:PG_ASYNC_SESSION):
    return await CustomFieldsHandler.create_field(data=data, session=session)

@router.get("")
async def get_all_fields(session:PG_ASYNC_SESSION):
    return await CustomFieldsHandler.get_all_fields(session=session)

@router.get("/{shop_id}")
async def get_field_by_shop(session:PG_ASYNC_SESSION,data:GetFieldByShopIdSchema=Depends()):
    return await CustomFieldsHandler.get_field_by_shop_id(data=data,session=session)

@router.get("/{shop_id}/{id}")
async def get_field_by_shop(session:PG_ASYNC_SESSION,data:GetFieldById=Depends()):
    return await CustomFieldsHandler.get_field_by_id(data=data,session=session)

@router.put("")
async def update_field(data: UpdateCustomFieldSchema, session:PG_ASYNC_SESSION):
    return await CustomFieldsHandler.update_field(data=data, session=session)

@router.delete("/{shop_id}/{id}")
async def delete_field(session:PG_ASYNC_SESSION,data:DeleteCustomFieldSchema=Depends()):
    return await CustomFieldsHandler.delete_field(data=data,session=session)


@router.post("/values")
async def upsert_value(data: CreateCustomFieldValueSchema, session:PG_ASYNC_SESSION):
    return await CustomFieldsHandler.upsert_value(data=data, session=session)

@router.get("/values/{shop_id}/{id}")
async def get_values_by_purchase(session:PG_ASYNC_SESSION,data:GetvaluesByCustomerId=Depends()):
    return await CustomFieldsHandler.get_values_by_purchase(data=data,session=session)
