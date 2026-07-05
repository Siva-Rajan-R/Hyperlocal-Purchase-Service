from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from icecream import ic
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from ..models.customfield_model import PurchaseCustomFields, PurchaseCustomFieldsValues
from schemas.v1.db_schemas.customfield_schema import CreateCustomFieldDbSchema, CreateCustomFieldValueDbSchema

class CustomFieldsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Custom Fields (Definitions) ---
    
    @start_db_transaction
    async def create_field(self, data: CreateCustomFieldDbSchema) -> bool:
        self.session.add(PurchaseCustomFields(**data.model_dump(mode='json')))
        return True

    @start_db_transaction
    async def update_field(self, field_id: str, shop_id: str, update_data: dict) -> Optional[str]:
        stmt = (
            update(PurchaseCustomFields)
            .where(PurchaseCustomFields.id == field_id, PurchaseCustomFields.shop_id == shop_id)
            .values(**update_data)
            .returning(PurchaseCustomFields.id)
        )
        res = (await self.session.execute(stmt)).scalar_one_or_none()
        return res

    @start_db_transaction
    async def delete_field(self, field_id: str, shop_id: str) -> bool:
        stmt = delete(PurchaseCustomFields).where(
            PurchaseCustomFields.id == field_id,
            PurchaseCustomFields.shop_id == shop_id
        )
        res = await self.session.execute(stmt)
        return res.rowcount > 0

    async def get_field_by_id(self, field_id: str, shop_id: str) -> Optional[dict]:
        stmt = select(PurchaseCustomFields).where(
            PurchaseCustomFields.id == field_id, 
            PurchaseCustomFields.shop_id == shop_id
        )
        res = (await self.session.execute(stmt)).scalars().first()
        if res:
            return {c.name: getattr(res, c.name) for c in res.__table__.columns}
        return None
        
    async def get_field_by_name(self, field_name: str, shop_id: str) -> Optional[dict]:
        stmt = select(PurchaseCustomFields).where(
            PurchaseCustomFields.field_name == field_name, 
            PurchaseCustomFields.shop_id == shop_id
        )
        res = (await self.session.execute(stmt)).scalars().first()
        if res:
            return {c.name: getattr(res, c.name) for c in res.__table__.columns}
        return None

    async def get_all_fields(self, shop_id: str) -> List[dict]:
        stmt = select(PurchaseCustomFields).where(PurchaseCustomFields.shop_id == shop_id)
        res = (await self.session.execute(stmt)).scalars().all()
        return [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in res]

    # --- Custom Fields Values (Assignments) ---
    
    @start_db_transaction
    async def upsert_field_value(self, data: CreateCustomFieldValueDbSchema) -> bool:
        stmt = select(PurchaseCustomFieldsValues).where(
            PurchaseCustomFieldsValues.purchase_id == data.purchase_id,
            PurchaseCustomFieldsValues.field_id == data.field_id,
            PurchaseCustomFieldsValues.shop_id == data.shop_id
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        
        if existing:
            update_stmt = (
                update(PurchaseCustomFieldsValues)
                .where(PurchaseCustomFieldsValues.id == existing.id)
                .values(value=data.value)
            )
            await self.session.execute(update_stmt)
        else:
            self.session.add(PurchaseCustomFieldsValues(**data.model_dump(mode='json')))
            
        return True
        
    async def get_values_by_purchase_id(self, purchase_id: str, shop_id: str) -> List[dict]:
        stmt = select(PurchaseCustomFieldsValues).where(
            PurchaseCustomFieldsValues.purchase_id == purchase_id,
            PurchaseCustomFieldsValues.shop_id == shop_id
        )
        res = (await self.session.execute(stmt)).scalars().all()
        return [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in res]
