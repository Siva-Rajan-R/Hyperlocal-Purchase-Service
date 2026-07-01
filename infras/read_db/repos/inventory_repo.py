from ..main import INVENTORY_COLLECTION
from ..models.inventory_model import InventoryReadModel
from icecream import ic
from schemas.v1.request_schemas.inventory_schema import GetAllInventorySchema, GetInventoryByShopIdSchema, GetInventoryByIdSchema
from pymongo import UpdateOne
from typing import List, Dict

class InventoryReadDbRepo:

    @staticmethod
    async def create_inventory(inventory: InventoryReadModel):
        try:
            document = inventory.model_dump(mode="json")
            result = await INVENTORY_COLLECTION.insert_one(document)
            ic(f"Read DB inventory created: {result.inserted_id}")
            return True
        except Exception as e:
            ic(f"Error saving inventory to Read DB: {e}")
            return False

    @staticmethod
    async def replace_inventory(inventory: InventoryReadModel):
        try:
            document = inventory.model_dump(mode="json")
            result = await INVENTORY_COLLECTION.replace_one(
                {"id": inventory.id, "shop_id": inventory.shop_id},
                document,
                upsert=True
            )
            ic(f"Read DB inventory replaced/updated: {result.modified_count}")
            return True
        except Exception as e:
            ic(f"Error replacing inventory in Read DB: {e}")
            return False

    @staticmethod
    async def get_all_inventories(data: GetAllInventorySchema | GetInventoryByShopIdSchema):
        query = {}
        if hasattr(data, 'shop_id') and data.shop_id:
            query["shop_id"] = data.shop_id
            
        if data.is_active is not None:
            query["is_active"] = data.is_active

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
                {"id": {"$regex": data.query, "$options": "i"}},
                {"name": {"$regex": data.query, "$options": "i"}},
                {"description": {"$regex": data.query, "$options": "i"}},
                {"category": {"$regex": data.query, "$options": "i"}},
                {"barcode": {"$regex": data.query, "$options": "i"}},
                {"sku": {"$regex": data.query, "$options": "i"}}
            ]
            
        cursor = data.offset-1 if data.offset and data.offset > 0 else 0
        inventories_cursor = INVENTORY_COLLECTION.find(query).limit(data.limit).skip(cursor * data.limit).sort("created_at", -1)
        docs = await inventories_cursor.to_list(length=data.limit)
        
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
                
        return docs

    @staticmethod
    async def get_inventory_by_id(data: GetInventoryByIdSchema):
        query = {"id": data.id, "shop_id": data.shop_id}
        doc = await INVENTORY_COLLECTION.find_one(query)
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    @staticmethod
    async def delete_inventory(inventory_id: str, shop_id: str):
        result = await INVENTORY_COLLECTION.delete_one({"id": inventory_id, "shop_id": shop_id})
        return result.deleted_count > 0

    @staticmethod
    async def bulk_update_stocks(shop_id: str, quantity_updates: Dict[str, float]):
        """
        Updates the stocks for the given inventory IDs.
        quantity_updates is a dict mapping inventory_id -> increment/decrement amount
        """
        if not quantity_updates:
            return True
            
        operations = []
        for inv_id, qty_diff in quantity_updates.items():
            operations.append(
                UpdateOne(
                    {"id": inv_id, "shop_id": shop_id},
                    {"$inc": {"stocks": qty_diff}}
                )
            )
            
        if operations:
            try:
                result = await INVENTORY_COLLECTION.bulk_write(operations, ordered=False)
                ic(f"Bulk update read db stocks: modified {result.modified_count}")
                return True
            except Exception as e:
                ic(f"Error bulk updating read db stocks: {e}")
                return False
        return True
