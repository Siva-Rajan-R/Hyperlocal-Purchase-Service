from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from infras.primary_db.services.customfield_service import CustomFieldsService
from schemas.v1.request_schemas.customfield_schema import (
    CreateCustomFieldSchema, UpdateCustomFieldSchema,
    CreateCustomFieldValueSchema, BulkCreateCustomFieldValuesSchema,DeleteCustomFieldSchema,GetFieldById,GetFieldByName,GetFieldByShopIdSchema,GetValueByIdName,GetvaluesByCustomerId
)
from hyperlocal_platform.core.models.req_res_models import SuccessResponseTypDict,ErrorResponseTypDict,BaseResponseTypDict
from typing import Optional,List

class CustomFieldsHandler:
    
    @staticmethod
    async def create_field(data: CreateCustomFieldSchema, session: AsyncSession):
        service = CustomFieldsService(session)
        res = await service.create_bulk_field(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                msg="Fields created Successfully",
                success=True
            ),
            data=res
        )

    @staticmethod
    async def update_field(session: AsyncSession, data:UpdateCustomFieldSchema):
        service = CustomFieldsService(session)
        res = await service.update_field(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                msg="Field Updated Successfully",
                success=True
            ),
            data=res
        )

    @staticmethod
    async def delete_field(session: AsyncSession,data:DeleteCustomFieldSchema):
        service = CustomFieldsService(session)
        res = await service.delete_field(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                msg="Field delteted Successfully",
                success=True
            ),
            data=res
        )

    @staticmethod
    async def get_all_fields(session: AsyncSession):
        service = CustomFieldsService(session)
        res = await service.get_all_fields()
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                msg="Fields Fetched Successfully",
                success=True
            ),
            data=res
        )

    @staticmethod
    async def get_field_by_shop_id(session: AsyncSession,data:GetFieldByShopIdSchema):
        service = CustomFieldsService(session)
        res = await service.get_field_by_shop_id(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                msg="Fields Fetched Successfully",
                success=True
            ),
            data=res
        )
    
    @staticmethod
    async def get_field_by_id(session:AsyncSession,data:GetFieldById):
        service = CustomFieldsService(session)
        res = await service.get_field_by_id(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                msg="Fields Fetched Successfully",
                success=True
            ),
            data=res
        )

    @staticmethod
    async def upsert_value(data: CreateCustomFieldValueSchema, session: AsyncSession):
        service = CustomFieldsService(session)
        res = await service.upsert_values(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                msg="Field values addedd Successfully",
                success=True
            ),
            data=res
        )


    @staticmethod
    async def get_values_by_purchase(data:GetvaluesByCustomerId,session: AsyncSession):
        service = CustomFieldsService(session)
        res = await service.get_values_by_purchase(data=data)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                msg="Field values Fetched Successfully",
                success=True
            ),
            data=res
        )
