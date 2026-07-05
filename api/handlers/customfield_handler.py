from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from infras.primary_db.services.customfield_service import CustomFieldsService
from schemas.v1.request_schemas.customfield_schema import (
    CreateCustomFieldSchema, UpdateCustomFieldSchema,
    CreateCustomFieldValueSchema, BulkCreateCustomFieldValuesSchema
)

class CustomFieldsHandler:
    
    @staticmethod
    async def create_field(shop_id: str, data: CreateCustomFieldSchema, session: AsyncSession):
        service = CustomFieldsService(session)
        return await service.create_field(shop_id=shop_id, data=data)

    @staticmethod
    async def update_field(field_id: str, shop_id: str, data: UpdateCustomFieldSchema, session: AsyncSession):
        service = CustomFieldsService(session)
        return await service.update_field(field_id=field_id, shop_id=shop_id, data=data)

    @staticmethod
    async def delete_field(field_id: str, shop_id: str, session: AsyncSession):
        service = CustomFieldsService(session)
        return await service.delete_field(field_id=field_id, shop_id=shop_id)

    @staticmethod
    async def get_all_fields(shop_id: str, session: AsyncSession):
        service = CustomFieldsService(session)
        return await service.get_all_fields(shop_id=shop_id)

    @staticmethod
    async def get_field(field_id: str, shop_id: str, session: AsyncSession):
        service = CustomFieldsService(session)
        return await service.get_field(field_id=field_id, shop_id=shop_id)

    @staticmethod
    async def upsert_value(shop_id: str, data: CreateCustomFieldValueSchema, session: AsyncSession):
        service = CustomFieldsService(session)
        return await service.upsert_value(shop_id=shop_id, data=data)

    @staticmethod
    async def bulk_upsert_values(shop_id: str, data: BulkCreateCustomFieldValuesSchema, session: AsyncSession):
        service = CustomFieldsService(session)
        return await service.bulk_upsert_values(shop_id=shop_id, data=data)

    @staticmethod
    async def get_values_by_purchase(purchase_id: str, shop_id: str, session: AsyncSession):
        service = CustomFieldsService(session)
        return await service.get_values_by_purchase(purchase_id=purchase_id, shop_id=shop_id)
