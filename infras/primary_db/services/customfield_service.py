from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from schemas.v1.request_schemas.customfield_schema import (
    CreateCustomFieldSchema, UpdateCustomFieldSchema,
    CreateCustomFieldValueSchema, UpdateCustomFieldValueSchema,
    BulkCreateCustomFieldValuesSchema
)
from schemas.v1.db_schemas.customfield_schema import CreateCustomFieldDbSchema, CreateCustomFieldValueDbSchema
from ..repos.customfield_repo import CustomFieldsRepo

class CustomFieldsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CustomFieldsRepo(session)

    async def create_field(self, shop_id: str, data: CreateCustomFieldSchema) -> dict:
        existing = await self.repo.get_field_by_name(field_name=data.field_name, shop_id=shop_id)
        if existing:
            raise HTTPException(status_code=400, detail="Custom field with this name already exists")

        field_id = generate_uuid()
        db_data = CreateCustomFieldDbSchema(
            id=field_id,
            shop_id=shop_id,
            **data.model_dump()
        )
        
        await self.repo.create_field(db_data)
        return {"success": True, "id": field_id}

    async def update_field(self, field_id: str, shop_id: str, data: UpdateCustomFieldSchema) -> dict:
        existing = await self.repo.get_field_by_id(field_id=field_id, shop_id=shop_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Custom field not found")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return {"success": True, "message": "No fields to update"}
            
        updated_id = await self.repo.update_field(field_id=field_id, shop_id=shop_id, update_data=update_data)
        if not updated_id:
            raise HTTPException(status_code=500, detail="Failed to update custom field")
            
        return {"success": True, "id": updated_id}

    async def delete_field(self, field_id: str, shop_id: str) -> dict:
        existing = await self.repo.get_field_by_id(field_id=field_id, shop_id=shop_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Custom field not found")
            
        success = await self.repo.delete_field(field_id=field_id, shop_id=shop_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete custom field")
            
        return {"success": True}

    async def get_all_fields(self, shop_id: str) -> list:
        return await self.repo.get_all_fields(shop_id=shop_id)

    async def get_field(self, field_id: str, shop_id: str) -> dict:
        field = await self.repo.get_field_by_id(field_id=field_id, shop_id=shop_id)
        if not field:
            raise HTTPException(status_code=404, detail="Custom field not found")
        return field

    # --- Values ---

    async def upsert_value(self, shop_id: str, data: CreateCustomFieldValueSchema) -> dict:
        field = await self.repo.get_field_by_id(field_id=data.field_id, shop_id=shop_id)
        if not field:
            raise HTTPException(status_code=404, detail=f"Custom field {data.field_id} not found")
            
        value_id = generate_uuid()
        db_data = CreateCustomFieldValueDbSchema(
            id=value_id,
            shop_id=shop_id,
            **data.model_dump()
        )
        
        await self.repo.upsert_field_value(db_data)
        return {"success": True}

    async def bulk_upsert_values(self, shop_id: str, data: BulkCreateCustomFieldValuesSchema) -> dict:
        for val in data.values:
            field_id = val.get("field_id")
            value = val.get("value")
            if not field_id or not value:
                continue
                
            field = await self.repo.get_field_by_id(field_id=field_id, shop_id=shop_id)
            if not field:
                raise HTTPException(status_code=404, detail=f"Custom field {field_id} not found")
                
            db_data = CreateCustomFieldValueDbSchema(
                id=generate_uuid(),
                shop_id=shop_id,
                purchase_id=data.purchase_id,
                field_id=field_id,
                value=value
            )
            await self.repo.upsert_field_value(db_data)
            
        return {"success": True}

    async def get_values_by_purchase(self, purchase_id: str, shop_id: str) -> list:
        return await self.repo.get_values_by_purchase_id(purchase_id=purchase_id, shop_id=shop_id)
