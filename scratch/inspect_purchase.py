import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from icecream import ic
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.services.purchase_service import PurchaseService
from infras.read_db.main import MONGO_CLIENT
from schemas.v1.purchase_schemas.request_schema import GetPurchaseByIdSchema

async def inspect():
    purchase_id = "d3f98dbe-c35a-53d5-bb03-39c24cb61a8d"
    shop_id = "d76277ab-232b-500f-9109-31538c2bc638"
    
    # 1. Fetch from Mongo Read DB
    pur_mongo_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]
    mongo_doc = await pur_mongo_coll.find_one({"purchase_id": purchase_id})
    ic("MONGO READ DB DOC =>", mongo_doc)
    
    # 2. Fetch from Postgres DB
    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)
        pg_doc = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id))
        if pg_doc:
            ic("PG PURCHASE RECORD =>", pg_doc.id, pg_doc.supplier_id, pg_doc.item_infos, pg_doc.payment_infos)
            for item in pg_doc.items:
                ic("PG ITEM =>", item.id, item.product_id, item.stocks, item.gst)
                if item.pricing_infos:
                    ic("PG PRICING =>", item.pricing_infos[0].buy_price, item.pricing_infos[0].sell_price)
        else:
            ic("PG RECORD NOT FOUND FOR SHOP_ID =>", shop_id)
            from sqlalchemy import select
            from infras.primary_db.models.purchase_model import Purchase
            stmt = select(Purchase).where(Purchase.id == purchase_id)
            res = (await session.execute(stmt)).scalars().one_or_none()
            if res:
                ic("FOUND IN PG WITHOUT SHOP_ID FILTER => shop_id in PG is:", res.shop_id)

if __name__ == "__main__":
    asyncio.run(inspect())
