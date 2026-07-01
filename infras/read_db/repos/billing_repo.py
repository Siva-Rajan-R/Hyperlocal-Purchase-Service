from motor.motor_asyncio import AsyncIOMotorClient
from infras.read_db.main import DB
from ..models.billing_model import BillingReadModel, BillingStatsReadModel
from icecream import ic
from typing import Optional, List, Dict

class BillingReadDbRepo:
    collection = DB['billings']

    @classmethod
    async def create_billing(cls, data: BillingReadModel):
        try:
            dumped_data = data.model_dump()
            res = await cls.collection.replace_one(
                {"id": dumped_data["id"]}, 
                dumped_data, 
                upsert=True
            )
            return bool(res.acknowledged)
        except Exception as e:
            ic(f"Error inserting billing to Read DB: {e}")
            return False

    @classmethod
    async def get_billings_by_shop(cls, shop_id: str, limit: int = 50, skip: int = 0) -> List[dict]:
        try:
            cursor = cls.collection.find({"shop_id": shop_id}).sort("created_at", -1).skip(skip).limit(limit)
            results = await cursor.to_list(length=limit)
            for res in results:
                res['_id'] = str(res['_id'])
            return results
        except Exception as e:
            ic(f"Error fetching billings: {e}")
            return []

class BillingStatsReadDbRepo:
    collection = DB['billing_stats']

    @classmethod
    async def get_stats(cls, shop_id: str) -> dict:
        try:
            stats = await cls.collection.find_one({"shop_id": shop_id})
            if not stats:
                return BillingStatsReadModel(shop_id=shop_id).model_dump()
            stats['_id'] = str(stats['_id'])
            return stats
        except Exception as e:
            ic(f"Error fetching billing stats: {e}")
            return BillingStatsReadModel(shop_id=shop_id).model_dump()

    @classmethod
    async def update_stats(cls, shop_id: str, 
                           total_orders_inc: int = 0, 
                           total_order_value_inc: float = 0.0,
                           walk_in_customers_inc: int = 0,
                           registered_customers_inc: int = 0,
                           outstanding_amount_inc: float = 0.0):
        try:
            inc_payload = {}
            if total_orders_inc != 0: inc_payload['total_orders'] = total_orders_inc
            if total_order_value_inc != 0.0: inc_payload['total_order_value'] = total_order_value_inc
            if walk_in_customers_inc != 0: inc_payload['walk_in_customers_count'] = walk_in_customers_inc
            if registered_customers_inc != 0: inc_payload['registered_customers_count'] = registered_customers_inc
            if outstanding_amount_inc != 0.0: inc_payload['outstanding_amount'] = outstanding_amount_inc

            if not inc_payload:
                return True

            res = await cls.collection.update_one(
                {"shop_id": shop_id},
                {"$inc": inc_payload},
                upsert=True
            )
            return bool(res.acknowledged)
        except Exception as e:
            ic(f"Error updating billing stats: {e}")
            return False
