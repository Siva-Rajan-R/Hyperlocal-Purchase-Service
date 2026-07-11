from ..main import PURCHAESE_COLLECTION, PURCHASE_STATS_COLLECTION, SUPPLIER_STATS_COLLECTION
from ..models.purchase_model import PurchaseReadModel
from icecream import ic
from typing import List,Optional
from schemas.v1.purchase_schemas.request_schema import GetAllPurchaseSchemas,GetPurchaseByIdSchema,GetPurchaseByShopIdSchema,GetPurchaseByProductIdSchema,GetPurchaseBySupplierIdSchema





class PurchaseReadDbRepo:
    @staticmethod
    async def create_purchase(purchase: PurchaseReadModel):
        result = await PURCHAESE_COLLECTION.insert_one(purchase.model_dump(mode="json"))
        if result.acknowledged and purchase.shop_id:
            import asyncio
            asyncio.create_task(PurchaseStatsReadDbRepo.update_stats(purchase.shop_id))
            if purchase.supplier and getattr(purchase.supplier, "supplier_id", None):
                asyncio.create_task(SupplierStatsReadDbRepo.update_supplier_stats(purchase.shop_id, purchase.supplier.supplier_id))
        ic(result)
        return result
    
    @staticmethod
    async def add_updatereaddb(purchase: PurchaseReadModel):
        result = await PURCHAESE_COLLECTION.update_one(
            {"purchase_id": purchase.purchase_id, "shop_id": purchase.shop_id},
            {"$set": purchase.model_dump(mode="json")},
            upsert=True
        )
        if result.acknowledged and purchase.shop_id:
            import asyncio
            asyncio.create_task(PurchaseStatsReadDbRepo.update_stats(purchase.shop_id))
            if purchase.supplier and getattr(purchase.supplier, "supplier_id", None):
                asyncio.create_task(SupplierStatsReadDbRepo.update_supplier_stats(purchase.shop_id, purchase.supplier.supplier_id))
        ic(result)
        return result
    

    @staticmethod
    async def get_all(
        data:GetAllPurchaseSchemas
    ) -> List[dict]:
        query = {}

        cursor = PURCHAESE_COLLECTION.find(
            query,
            {"_id": 0}
        )

        return await cursor.to_list(length=None)

    @staticmethod
    async def get_by_shop_id(
        data:GetPurchaseByShopIdSchema
    ) -> List[dict]:
        query = {
            "shop_id": data.shop_id
        }

        cursor = PURCHAESE_COLLECTION.find(
            query,
            {"_id": 0}
        )

        return await cursor.to_list(length=None)

    @staticmethod
    async def get_by_id(
        data:GetPurchaseByIdSchema
    ) -> Optional[dict]:
        query = {
            "shop_id": data.shop_id,
            "purchase_id": data.id,
        }


        return await PURCHAESE_COLLECTION.find_one(
            query,
            {"_id": 0}
        )

    @staticmethod
    async def get_by_product_id(
        data: GetPurchaseByProductIdSchema
    ) -> List[dict]:
        query = {
            "shop_id": data.shop_id,
            "items.product_id": data.product_id
        }
        cursor = PURCHAESE_COLLECTION.find(
            query,
            {"_id": 0}
        ).skip((data.offset - 1) * data.limit).limit(data.limit)
        return await cursor.to_list(length=None)

    @staticmethod
    async def get_by_supplier_id(
        data: GetPurchaseBySupplierIdSchema
    ) -> List[dict]:
        query = {
            "shop_id": data.shop_id,
            "supplier.supplier_id": data.supplier_id
        }
        cursor = PURCHAESE_COLLECTION.find(
            query,
            {"_id": 0}
        ).skip((data.offset - 1) * data.limit).limit(data.limit)
        return await cursor.to_list(length=None)
    
    # @staticmethod
    # async def get_all_purchases(data:GetPurchaseByShopIdSchema):
    #     query = {"shop_id": data.shop_id}
    #     if data.query:
    #         query["$or"] = [
    #             {"po_number": {"$regex": data.query, "$options": "i"}},
    #             {"supplier.supplier_name": {"$regex": data.query, "$options": "i"}},
    #             {"purchase_id": {"$regex": data.query, "$options": "i"}}
    #         ]
            
    #     if getattr(data, 'type', None):
    #         query["type"] = data.type
            
    #     if getattr(data, 'supplier_id', None):
    #         query["supplier.supplier_id"] = data.supplier_id
            
    #     if getattr(data, 'from_date', None) or getattr(data, 'to_date', None):
    #         created_at_query = {}
    #         if getattr(data, 'from_date', None):
    #             created_at_query["$gte"] = data.from_date
    #         if getattr(data, 'to_date', None):
    #             to_date_str = data.to_date
    #             if len(to_date_str) <= 10:
    #                 to_date_str += "T23:59:59"
    #             created_at_query["$lte"] = to_date_str
    #         if created_at_query:
    #             query["created_at"] = created_at_query
        
    #     cursor = data.offset-1 if data.offset and data.offset > 0 else 0
    #     purchases_cursor = PURCHAESE_COLLECTION.find(query).limit(data.limit).skip(cursor * data.limit).sort("created_at", -1)
    #     ic(purchases_cursor)
    #     docs = await purchases_cursor.to_list(length=data.limit)
    #     for doc in docs:
    #         if "_id" in doc:
    #             doc["_id"] = str(doc["_id"])
    #     return docs
    
    @staticmethod
    async def update_purchase(purchase_id: str, update_data: PurchaseReadModel):
        data_toupdate=update_data.model_dump(mode="json",exclude_unset=True,exclude_none=True,exclude=["purchase_id","shop_id"])
        
        # Get shop_id before update if not explicitly present in update_data
        shop_id = update_data.shop_id
        if not shop_id:
            existing = await PURCHAESE_COLLECTION.find_one({"purchase_id": purchase_id})
            if existing:
                shop_id = existing.get("shop_id")

        result = await PURCHAESE_COLLECTION.update_one({"purchase_id": purchase_id}, {"$set": data_toupdate})
        
        if result.modified_count > 0 and shop_id:
            import asyncio
            asyncio.create_task(PurchaseStatsReadDbRepo.update_stats(shop_id))
            
            supplier_id = getattr(update_data.supplier, "supplier_id", None) if update_data.supplier else None
            if not supplier_id and existing and existing.get("supplier"):
                supplier_id = existing["supplier"].get("supplier_id")
                
            if supplier_id:
                asyncio.create_task(SupplierStatsReadDbRepo.update_supplier_stats(shop_id, supplier_id))
            
        ic(result)
        return result.modified_count > 0
    
    @staticmethod
    async def delete_purchase(purchase_id: str):
        existing = await PURCHAESE_COLLECTION.find_one({"purchase_id": purchase_id})
        shop_id = existing.get("shop_id") if existing else None
        
        result = await PURCHAESE_COLLECTION.delete_one({"purchase_id": purchase_id})
        
        if result.deleted_count > 0 and shop_id:
            import asyncio
            asyncio.create_task(PurchaseStatsReadDbRepo.update_stats(shop_id))
            
            supplier_id = existing.get("supplier", {}).get("supplier_id") if existing else None
            if supplier_id:
                asyncio.create_task(SupplierStatsReadDbRepo.update_supplier_stats(shop_id, supplier_id))
            
        ic(result)
        return result.deleted_count > 0

    # @staticmethod
    # async def get_purchase_by_id(data: GetPurchaseByIdSchema) -> PurchaseReadModel:
    #     purchase_data = await PURCHAESE_COLLECTION.find_one({"purchase_id": data.id,"shop_id": data.shop_id})
    #     if purchase_data:
    #         return PurchaseReadModel(**purchase_data)
    #     return None
    
    # @staticmethod
    # async def get_purchases_by_supplier_id(data: GetPurchaseBySupplierIdSchema):
    #     purchases_cursor = PURCHAESE_COLLECTION.find({"shop_id": data.shop_id,"supplier.supplier_id": data.supplier_id})
    #     docs = await purchases_cursor.to_list(length=100)
    #     for doc in docs:
    #         if "_id" in doc:
    #             doc["_id"] = str(doc["_id"])
    #     return docs
    
    # @staticmethod
    # async def get_purchases_by_inventory_id(data: GetPurchaseByInventoryIdSchema):
    #     purchases_cursor = PURCHAESE_COLLECTION.find({"shop_id": data.shop_id,"products.inventory_id": data.inventory_id})
    #     docs = await purchases_cursor.to_list(length=100)
    #     for doc in docs:
    #         if "_id" in doc:
    #             doc["_id"] = str(doc["_id"])
    #     return docs
        
    @staticmethod
    async def check_invoice_uniqueness(shop_id: str, supplier_id: str, invoice_no: str, exclude_purchase_id: str = None) -> bool:
        if not invoice_no:
            return True
        query = {
            "shop_id": shop_id,
            "supplier.supplier_id": supplier_id,
            "invoice_no": invoice_no
        }
        if exclude_purchase_id:
            query["purchase_id"] = {"$ne": exclude_purchase_id}
        existing = await PURCHAESE_COLLECTION.find_one(query)
        return existing is None
        
    @staticmethod
    async def get_supplier_stats(shop_id: str, supplier_id: str):
        stats = await SUPPLIER_STATS_COLLECTION.find_one({"shop_id": shop_id, "supplier_id": supplier_id})
        if not stats:
            stats = await SupplierStatsReadDbRepo.update_supplier_stats(shop_id, supplier_id)
        
        if stats:
            stats.pop("_id", None)
            return stats
            
        return {
            "purchase_count": 0,
            "total_purchase_value": 0.0,
            "outstanding_count": 0,
            "outstanding_value": 0.0,
            "total_items_bought": 0,
            "last_order_date": None
        }


class PurchaseStatsReadDbRepo:
    @staticmethod
    async def update_stats(shop_id: str):
        try:
            pipeline = [
                {"$match": {"shop_id": shop_id}},
                {
                    "$group": {
                        "_id": None,
                        "total_purchase_count": {"$sum": 1},
                        "total_purchase_value": {"$sum": "$total_cost"},
                        "pending_count": {
                            "$sum": {"$cond": [{"$gt": [{"$subtract": ["$total_cost", "$paid_amount"]}, 0]}, 1, 0]}
                        },
                        "pending_value": {
                            "$sum": {"$cond": [{"$gt": [{"$subtract": ["$total_cost", "$paid_amount"]}, 0]}, {"$subtract": ["$total_cost", "$paid_amount"]}, 0]}
                        },
                        "completed_count": {
                            "$sum": {"$cond": [{"$lte": [{"$subtract": ["$total_cost", "$paid_amount"]}, 0]}, 1, 0]}
                        },
                        "completed_value": {
                            "$sum": {"$cond": [{"$lte": [{"$subtract": ["$total_cost", "$paid_amount"]}, 0]}, "$total_cost", 0]}
                        }
                    }
                }
            ]
            
            cursor = PURCHAESE_COLLECTION.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            stats_data = {
                "shop_id": shop_id,
                "total_purchase_count": 0,
                "total_purchase_value": 0.0,
                "pending_count": 0,
                "pending_value": 0.0,
                "completed_count": 0,
                "completed_value": 0.0,
            }
            
            if result and len(result) > 0:
                agg = result[0]
                stats_data["total_purchase_count"] = agg.get("total_purchase_count", 0)
                stats_data["total_purchase_value"] = agg.get("total_purchase_value", 0.0)
                stats_data["pending_count"] = agg.get("pending_count", 0)
                stats_data["pending_value"] = agg.get("pending_value", 0.0)
                stats_data["completed_count"] = agg.get("completed_count", 0)
                stats_data["completed_value"] = agg.get("completed_value", 0.0)
                
            res = await PURCHASE_STATS_COLLECTION.replace_one(
                {"shop_id": shop_id},
                stats_data,
                upsert=True
            )
            return res
        except Exception as e:
            ic(f"Error updating purchase stats: {e}")
            return None

    @staticmethod
    async def get_stats(shop_id: str):
        stats = await PURCHASE_STATS_COLLECTION.find_one({"shop_id": shop_id})
        return stats


class SupplierStatsReadDbRepo:
    @staticmethod
    async def update_supplier_stats(shop_id: str, supplier_id: str):
        try:
            pipeline = [
                {"$match": {"shop_id": shop_id, "supplier.supplier_id": supplier_id}},
                {
                    "$group": {
                        "_id": None,
                        "purchase_count": {"$sum": 1},
                        "total_purchase_value": {"$sum": "$total_cost"},
                        "outstanding_count": {
                            "$sum": {"$cond": [{"$gt": [{"$subtract": ["$total_cost", "$paid_amount"]}, 0]}, 1, 0]}
                        },
                        "outstanding_value": {
                            "$sum": {"$cond": [{"$gt": [{"$subtract": ["$total_cost", "$paid_amount"]}, 0]}, {"$subtract": ["$total_cost", "$paid_amount"]}, 0]}
                        },
                        "total_items_bought": {"$sum": "$total_quantity"},
                        "last_order_date": {"$max": "$purchase_date"}
                    }
                }
            ]
            
            cursor = PURCHAESE_COLLECTION.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            stats_data = {
                "shop_id": shop_id,
                "supplier_id": supplier_id,
                "purchase_count": 0,
                "total_purchase_value": 0.0,
                "outstanding_count": 0,
                "outstanding_value": 0.0,
                "total_items_bought": 0,
                "last_order_date": None
            }
            
            if result and len(result) > 0:
                agg = result[0]
                stats_data["purchase_count"] = agg.get("purchase_count", 0)
                stats_data["total_purchase_value"] = agg.get("total_purchase_value", 0.0)
                stats_data["outstanding_count"] = agg.get("outstanding_count", 0)
                stats_data["outstanding_value"] = agg.get("outstanding_value", 0.0)
                stats_data["total_items_bought"] = agg.get("total_items_bought", 0)
                stats_data["last_order_date"] = agg.get("last_order_date", None)
                
            res = await SUPPLIER_STATS_COLLECTION.replace_one(
                {"shop_id": shop_id, "supplier_id": supplier_id},
                stats_data,
                upsert=True
            )
            return stats_data
        except Exception as e:
            ic(f"Error updating supplier stats: {e}")
            return None
