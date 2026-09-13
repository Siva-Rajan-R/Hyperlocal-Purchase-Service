from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from schemas.v1.request_schemas.customfield_schema import (
    CreateCustomFieldSchema, UpdateCustomFieldSchema,
    CreateCustomFieldValueSchema, UpdateCustomFieldValueSchema,
    BulkCreateCustomFieldValuesSchema,DeleteCustomFieldSchema,GetFieldById,GetFieldByName,GetFieldByShopIdSchema,GetValueByIdName,GetvaluesByCustomerId
)
from schemas.v1.db_schemas.customfield_schema import CreateCustomFieldDbSchema, CreateCustomFieldValueDbSchema,DeleteCustomFieldDbSchema,UpdateCustomFieldDbSchema
from ..repos.customfield_repo import CustomFieldsRepo
from typing import List

class CustomFieldsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CustomFieldsRepo(session)

    async def create_bulk_field(self, data: CreateCustomFieldSchema) -> dict:
        data_toadd=[]
        names=[]
        shop_id=data.shop_id
        for field_data in data.field_infos:
            field_id = generate_uuid()
            data_toadd.append(
                    CreateCustomFieldDbSchema(
                    id=field_id,
                    shop_id=shop_id,
                    **field_data.model_dump()
                )
            )

            names.append(field_data.field_name)
        
        existing=await self.repo.get_bulk_fields(names=names,shop_id=shop_id)
        if len(existing)>0:
            raise HTTPException(status_code=400, detail="Custom field with this name already exists")
        
        await self.repo.create_all_field(data=data_toadd)
        return {"success": True}
    async def update_field(self, data: UpdateCustomFieldSchema) -> dict:
        field_id = getattr(data, 'id', None) or getattr(data, 'field_id', None)
        if not field_id:
            raise HTTPException(status_code=400, detail="Field ID is required")
        existing = await self.repo.get_field_by_id(GetFieldById(id=field_id, shop_id=data.shop_id))
        if not existing:
            raise HTTPException(status_code=404, detail="Custom field not found")

        value_exists = await self.repo.get_values_by_field_id(field_id=field_id, shop_id=data.shop_id)
        has_data = any(v.get("value") is not None and str(v.get("value")).strip() != "" for v in value_exists)

        if has_data and data.type and data.type != existing.get("type"):
            raise HTTPException(
                status_code=400,
                detail="Field type cannot be changed because this custom field already contains saved values. Only label name and visibility can be updated."
            )

        update_data = data.model_dump(exclude_unset=True, exclude_none=True, exclude=['field_id', 'id', 'shop_id'])
        if has_data and 'type' in update_data:
            del update_data['type']

        if not update_data:
            return {"success": True, "message": "No fields to update"}
            
        updated_id = await self.repo.update_field(data=UpdateCustomFieldDbSchema(id=field_id, shop_id=data.shop_id, **update_data))
        if not updated_id:
            raise HTTPException(status_code=500, detail="Failed to update custom field")
            
        return {"success": True, "id": updated_id}

    async def delete_field(self, data: DeleteCustomFieldSchema) -> dict:
        field_id = getattr(data, 'id', None) or getattr(data, 'field_id', None)
        if not field_id:
            raise HTTPException(status_code=400, detail="Field ID is required")
            
        existing = await self.repo.get_field_by_id(GetFieldById(id=field_id, shop_id=data.shop_id))
        if not existing:
            raise HTTPException(status_code=404, detail="Custom field not found")

        value_exists = await self.repo.get_values_by_field_id(field_id=field_id, shop_id=data.shop_id)
        has_data = any(v.get("value") is not None and str(v.get("value")).strip() != "" for v in value_exists)
        if has_data:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete custom field because it already contains saved values."
            )

        deleted = await self.repo.delete_field(data=DeleteCustomFieldDbSchema(id=field_id, shop_id=data.shop_id))
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete custom field")
            
        return {"success": True, "message": "Custom field deleted successfully"}

    async def get_all_fields(self) -> list:
        return await self.repo.get_fields()

    async def get_field_by_shop_id(self,data:GetFieldByShopIdSchema) -> list:
        field = await self.repo.get_fields_by_shop_id(data=data)
        if not field:
            return []
        return field
    
    async def get_field_by_id(self,data:GetFieldById):
        field = await self.repo.get_field_by_id(data=data)
        if not field:
            return {}
        return field

    # --- Values ---

    async def upsert_values(self, data: CreateCustomFieldValueSchema) -> dict: 
        data_toadd=[]  
        shop_id=data.shop_id
        purchase_id=data.purchase_id
        for d in data.value_infos:
            value_id = generate_uuid()
            data_toadd.append(CreateCustomFieldValueDbSchema(
                id=value_id,
                shop_id=shop_id,
                purchase_id=purchase_id,
                **d.model_dump()
            ))
        
        await self.repo.upsert_field_value(data=data_toadd)
        return {"success": True}

    async def get_values_by_purchase(self,data:GetvaluesByCustomerId) -> list:
        return await self.repo.get_values_by_purchase_id(data=data)
