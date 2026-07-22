from models.repo_models.base_repo_model import BaseRepoModel
from models.service_models.base_service_model import BaseServiceModel
from sqlalchemy import select,update,delete,func,or_,and_,String,case,literal,literal_column,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload,load_only
from ..models.purchase_model import Purchase,PurchaseItems,PurchaseItemsPricing,PurchaseItemsStoragelocation,PurchaseItemsReorderPoint
from schemas.v1.purchase_schemas.db_schemas import CreatePurchaseDbSchema,CreatePurchaseItemsDbSchema,UpdatePurchaseDbSchema,UpdatePurchaseItemsDbSchema,DeletePurchaseDbSchema,CreatePurchasePricingDbSchema,CreateStorageLocationDbSchema,UpdatePurchasePricingDbSchema,UpdateStorageLocationDbSchema,UpdateReorderPointDbSchema,CreateReorderPointDbSchema
from schemas.v1.purchase_schemas.request_schema import GetAllPurchaseSchemas,GetPurchaseByIdSchema,GetPurchaseByShopIdSchema
from sqlalchemy.dialects.postgresql import insert
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from typing import Optional,List
from icecream import ic
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums,PurchaseViewsEnums



class PurchaseRepo:
    def __init__(self, session:AsyncSession):
        self.session=session
        self.purchase_cols=(
            Purchase.id,
            Purchase.shop_id,
            Purchase.date,
            Purchase.invoice_no,
            Purchase.type,
            Purchase.purchase_view,
            Purchase.sequence_id,
            Purchase.ui_id,
            Purchase.supplier_id,
            Purchase.gst_infos,
            Purchase.charges_infos,
            Purchase.additional_infos,
            Purchase.item_infos,
            Purchase.calculation_infos,
            Purchase.payment_infos,
            Purchase.version,
            Purchase.created_at,
            Purchase.updated_at
        )

        self.item_cols=(
            PurchaseItems.id,
            PurchaseItems.product_id,
            PurchaseItems.variant_id,
            PurchaseItems.batch_id,
            PurchaseItems.serialno_id,
            PurchaseItems.serial_numbers,
            PurchaseItems.gst,
            PurchaseItems.stocks,
            PurchaseItems.stocks_before,
            PurchaseItems.stocks_after,
        )

        self.pricing_cols=(
            PurchaseItemsPricing.id,
            PurchaseItemsPricing.buy_price,
            PurchaseItemsPricing.sell_price,
        )

        self.stl_cols=(
            PurchaseItemsStoragelocation.id,
            PurchaseItemsStoragelocation.name,
        )

        self.rop_cols=(
            PurchaseItemsReorderPoint.id,
            PurchaseItemsReorderPoint.reorder_point,
        )

    @start_db_transaction
    async def get_next_sequence(self, shop_id: str, start_from: int) -> int:
        from sqlalchemy import text
        seq_name = f"seq_purchase_{shop_id.replace('-', '_').lower()}"
        await self.session.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START WITH {start_from}"))
        res = await self.session.execute(text(f"SELECT nextval('{seq_name}')"))
        return res.scalar_one()

    @start_db_transaction
    async def create_bulk_purchase(self,data:List[Purchase]):
        if data:
            self.session.add_all(data)
        return True
    
    @start_db_transaction
    async def create_bulk_items(self,data:List[PurchaseItems]):
        if data:
            self.session.add_all(data)
        return True
    

    @start_db_transaction
    async def create_bulk_pricing(self,data:List[PurchaseItemsPricing]):
        if data:
            self.session.add_all(data)
        return True
    

    @start_db_transaction
    async def create_bulk_stl(self,data:List[PurchaseItemsStoragelocation]):
        if data:
            self.session.add_all(data)
        return True
    

    @start_db_transaction
    async def create_bulk_rop(self,data:List[PurchaseItemsReorderPoint]):
        if data:
            self.session.add_all(data)
        return True


    @start_db_transaction
    async def update_bulk_purchase(self,data:List[UpdatePurchaseDbSchema]):
        if not data:
            return True
        final_data=[d.model_dump(mode="json",exclude_unset=True,exclude_none=True,exclude=['shop_id']) for d in data]
        await self.session.run_sync(
            lambda session:session.bulk_update_mappings(
                Purchase,
                final_data
            )
        )

        return True

    @start_db_transaction
    async def update_bulk_item(self,data:List[UpdatePurchaseItemsDbSchema]):
        if not data:
            return True
        
        final_data=[d.model_dump(mode="json",exclude_unset=True,exclude_none=True,exclude=['shop_id']) for d in data]
        await self.session.run_sync(
            lambda session:session.bulk_update_mappings(
                PurchaseItems,
                final_data
            )
        )

        return True
    
    @start_db_transaction
    async def update_bulk_pricing(
        self,
        data: list[UpdatePurchasePricingDbSchema]
    ):
        if not data:
            return True

        stmt = (
            PurchaseItemsPricing.__table__.update()
            .where(
                PurchaseItemsPricing.purchase_item_id == bindparam("b_purchase_item_id"),
                PurchaseItemsPricing.purchase_id == bindparam("b_purchase_id"),
            )
       
            .values(
                buy_price=bindparam("buy_price"),
                sell_price=bindparam("sell_price"),
            )
        )

        res=await self.session.execute(
            stmt,
            [
                {
                    "b_purchase_item_id": item.purchase_item_id,
                    "b_purchase_id": item.purchase_id,
                    "buy_price": item.buy_price,
                    "sell_price": item.sell_price,
                }
                for item in data
            ],
        )

        ic(res.rowcount)
        return True
    

    @start_db_transaction
    async def update_bulk_stl(
        self,
        data: list[UpdateStorageLocationDbSchema]
    ):
        if not data:
            return True

        stmt = (
            PurchaseItemsStoragelocation.__table__.update()
            .where(
                PurchaseItemsStoragelocation.purchase_item_id == bindparam("b_purchase_item_id"),
                PurchaseItemsStoragelocation.purchase_id == bindparam("b_purchase_id"),
            )
            .values(
                name=bindparam("name")
            )
           
        )

        res=await self.session.execute(
            stmt,
            [
                {
                    "b_purchase_item_id": item.purchase_item_id,
                    "b_purchase_id": item.purchase_id,
                    "name": item.name
                }
                for item in data
            ],
        )

        ic(res.rowcount)
        return True
    

    @start_db_transaction
    async def update_bulk_rop(
        self,
        data: list[UpdateReorderPointDbSchema]
    ):
        if not data:
            return True

        stmt = (
            PurchaseItemsReorderPoint.__table__.update()
            .where(
                PurchaseItemsReorderPoint.purchase_item_id == bindparam("b_purchase_item_id"),
                PurchaseItemsReorderPoint.purchase_id == bindparam("b_purchase_id"),
            )
            .values(
                reorder_point=bindparam("rop")
            )
           
        )

        res=await self.session.execute(
            stmt,
            [
                {
                    "b_purchase_item_id": item.purchase_item_id,
                    "b_purchase_id": item.purchase_id,
                    "rop": item.reorder_point
                }
                for item in data
            ],
        )

        ic(res.rowcount)
        return True
    
    @start_db_transaction
    async def delete_purchase(self,data:DeletePurchaseDbSchema):
        stmt=(
            delete(
                Purchase
            )
            .where(
                Purchase.id==data.id,
                Purchase.shop_id==data.shop_id
            )
            .returning(*self.purchase_cols)
        )

        res=(await self.session.execute(stmt)).mappings().all()
        ic(res)
        return res
    
    async def get_purchases(self,data:GetAllPurchaseSchemas):
        from datetime import datetime, timezone
        offset=data.offset-1 if data.offset>0 else 0
        cursor=offset*data.limit

        conds = []
        if getattr(data, 'query', None):
            search_term = f"%{data.query}%"
            conds.append(or_(
                Purchase.id.ilike(search_term),
                Purchase.ui_id.ilike(search_term),
                Purchase.invoice_no.ilike(search_term),
                Purchase.supplier_id.ilike(search_term)
            ))
        if getattr(data, 'from_date', None):
            try:
                from_dt = datetime.strptime(data.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                conds.append(Purchase.created_at >= from_dt)
            except Exception:
                pass
        if getattr(data, 'to_date', None):
            try:
                to_date_str = data.to_date
                if len(to_date_str) <= 10:
                    to_date_str += ' 23:59:59'
                to_dt = datetime.strptime(to_date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                conds.append(Purchase.created_at <= to_dt)
            except Exception:
                pass

        stmt = (
            select(Purchase)
            .options(
                load_only(
                    *self.purchase_cols
                ),

                selectinload(Purchase.items)
                .load_only(
                    *self.item_cols
                )
                .selectinload(PurchaseItems.pricing_infos)
                .load_only(
                    *self.pricing_cols
                ),

                selectinload(Purchase.items)
                .selectinload(PurchaseItems.storage_locations)
                .load_only(
                    *self.stl_cols
                ),

                selectinload(Purchase.items)
                .selectinload(PurchaseItems.reorder_point)
                .load_only(
                    *self.rop_cols
                ),
            )
        )
        if conds:
            stmt = stmt.where(and_(*conds))

        stmt = stmt.offset(offset=cursor).limit(limit=data.limit)
        res = (await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res
    
    async def get_purchase_by_shop_id(self,data:GetPurchaseByShopIdSchema):
        from datetime import datetime, timezone
        offset=data.offset-1 if data.offset>0 else 0
        cursor=offset*data.limit

        conds = [Purchase.shop_id == data.shop_id]
        if getattr(data, 'supplier_id', None):
            conds.append(Purchase.supplier_id == data.supplier_id)
        if getattr(data, 'query', None):
            search_term = f"%{data.query}%"
            conds.append(or_(
                Purchase.id.ilike(search_term),
                Purchase.ui_id.ilike(search_term),
                Purchase.invoice_no.ilike(search_term),
                Purchase.supplier_id.ilike(search_term)
            ))
        if getattr(data, 'from_date', None):
            try:
                from_dt = datetime.strptime(data.from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                conds.append(Purchase.created_at >= from_dt)
            except Exception:
                pass
        if getattr(data, 'to_date', None):
            try:
                to_date_str = data.to_date
                if len(to_date_str) <= 10:
                    to_date_str += ' 23:59:59'
                to_dt = datetime.strptime(to_date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                conds.append(Purchase.created_at <= to_dt)
            except Exception:
                pass

        stmt = (
            select(Purchase)
            .where(and_(*conds))
            .options(
                load_only(
                    *self.purchase_cols
                ),

                selectinload(Purchase.items)
                .load_only(
                    *self.item_cols
                )
                .selectinload(PurchaseItems.pricing_infos)
                .load_only(
                    *self.pricing_cols
                ),

                selectinload(Purchase.items)
                .selectinload(PurchaseItems.storage_locations)
                .load_only(
                    *self.stl_cols
                ),

                selectinload(Purchase.items)
                .selectinload(PurchaseItems.reorder_point)
                .load_only(
                    *self.rop_cols
                ),
            )
            .offset(offset=cursor).limit(limit=data.limit)
        )

        res = (await self.session.execute(stmt)).scalars().all()
        ic(res)
        return res
    

    async def get_purchase_by_id(self,data:GetPurchaseByIdSchema):

        stmt = (
            select(Purchase)
            .where(
                Purchase.shop_id==data.shop_id,
                Purchase.id==data.id
            )
            .options(
                load_only(
                    *self.purchase_cols
                ),

                selectinload(Purchase.items)
                .load_only(
                    *self.item_cols
                )
                .selectinload(PurchaseItems.pricing_infos)
                .load_only(
                    *self.pricing_cols
                ),

                selectinload(Purchase.items)
                .selectinload(PurchaseItems.storage_locations)
                .load_only(
                    *self.stl_cols
                ),

                selectinload(Purchase.items)
                .selectinload(PurchaseItems.reorder_point)
                .load_only(
                    *self.rop_cols
                ),
            )
        )

        res = (await self.session.execute(stmt)).scalars().one_or_none()
        ic(res)
        return res
    

    async def verify_invoice_exists(self,invoice_no:str,shop_id: str):
        stmt=(
            select(
                Purchase.id
            )
            .where(
                Purchase.invoice_no==invoice_no,
                Purchase.shop_id==shop_id
            )
            .limit(1)
        )

        res=(await self.session.execute(stmt)).scalar_one_or_none()
        ic(res)
        return res

    @start_db_transaction
    async def create_history(self, purchase_id: str, version: str, purchase_data: dict):
        from ..models.purchase_model import PurchaseHistory
        import uuid
        history = PurchaseHistory(
            id=str(uuid.uuid4()),
            purchase_id=purchase_id,
            version=version,
            purchase_data=purchase_data
        )
        self.session.add(history)
        await self.session.flush()
        return history

    async def get_history_by_purchase_id(self, purchase_id: str) -> List[dict]:
        from ..models.purchase_model import PurchaseHistory
        stmt = select(PurchaseHistory).where(PurchaseHistory.purchase_id == purchase_id).order_by(PurchaseHistory.created_at.asc())
        history_records = (await self.session.execute(stmt)).scalars().all()
        return [
            {
                "version": record.version,
                "created_at": record.created_at,
                "purchase_data": record.purchase_data
            }
            for record in history_records
        ]


    
    
