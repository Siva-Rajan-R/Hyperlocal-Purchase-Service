from ..main import STOCK_MOVEMENT_COLLECTION, STOCK_MOVEMENT_STATS_COLLECTION
from ..models.stock_movement_model import StockMovementReadModel
from icecream import ic
from schemas.v1.request_schemas.stock_adj_schema import GetStockAdjByShopIdSchema, GetStockAdjByIdSchema, GetStockAdjByInventoryIdSchema, GetAllStockAdjSchema
from typing import List

class StockMovementReadDbRepo:

    @staticmethod
    async def create_stock_movement(data: StockMovementReadModel):
        try:
            document = data.model_dump(mode="json")
            result = await STOCK_MOVEMENT_COLLECTION.insert_one(document)
            ic(result.inserted_id)
            return True
        except Exception as e:
            ic(f"Error saving to Read DB: {e}")
            return False

    @staticmethod
    async def get_all_movements(data: GetStockAdjByShopIdSchema | GetAllStockAdjSchema):
        query = {}
        if hasattr(data, 'shop_id') and data.shop_id:
            query["shop_id"] = data.shop_id
            
        if getattr(data, 'movement_type', None):
            query["movement_type"] = data.movement_type

        if getattr(data, 'from_date', None) or getattr(data, 'to_date', None):
            created_at_query = {}
            if getattr(data, 'from_date', None):
                created_at_query["$gte"] = data.from_date
            if getattr(data, 'to_date', None):
                to_date_str = data.to_date
                if len(to_date_str) <= 10:
                    to_date_str += "T23:59:59"
                created_at_query["$lte"] = to_date_str
            if created_at_query:
                query["created_at"] = created_at_query

        if data.query:
            query["$or"] = [
                {"description": {"$regex": data.query, "$options": "i"}},
                {"stock_movement_id": {"$regex": data.query, "$options": "i"}},
                {"movement_type": {"$regex": data.query, "$options": "i"}}
            ]
            
        cursor = STOCK_MOVEMENT_COLLECTION.find(query).skip((data.offset - 1) * data.limit).limit(data.limit).sort("created_at", -1)
        documents = await cursor.to_list(length=data.limit)
        
        # Add id for UI consistency if needed
        for doc in documents:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
                
        return documents

    @staticmethod
    async def get_movement_by_id(data: GetStockAdjByIdSchema):
        document = await STOCK_MOVEMENT_COLLECTION.find_one({"shop_id": data.shop_id, "stock_movement_id": data.id})
        if document and "_id" in document:
            document["_id"] = str(document["_id"])
        return document

    @staticmethod
    async def get_movements_by_inventory_id(data: GetStockAdjByInventoryIdSchema):
        cursor = STOCK_MOVEMENT_COLLECTION.find({"shop_id": data.shop_id, "products.inventory_id": data.inventory_id}).sort("created_at", -1)
        documents = await cursor.to_list(length=100)
        for doc in documents:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return documents


class StockMovementStatsReadDbRepo:
    @staticmethod
    async def update_stats(shop_id: str, stock_in: float, stock_out: float, is_purchase: bool = False, is_sales: bool = False):
        
        inc_data = {
            "total_movements_count": 1,
            "total_stock_in": stock_in,
            "total_stock_out": stock_out
        }
        
        if is_purchase:
            inc_data["total_purchase_count"] = 1
        if is_sales:
            inc_data["total_sales_count"] = 1
            
        result = await STOCK_MOVEMENT_STATS_COLLECTION.update_one(
            {"shop_id": shop_id},
            {"$inc": inc_data},
            upsert=True
        )
        return result

    @staticmethod
    async def get_stats(shop_id: str):
        stats = await STOCK_MOVEMENT_STATS_COLLECTION.find_one({"shop_id": shop_id})
        if stats and "_id" in stats:
            stats["_id"] = str(stats["_id"])
        return stats
