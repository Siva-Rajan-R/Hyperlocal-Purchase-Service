import asyncio
import sys
import os

sys.path.insert(0, r"d:\projects\airport-marketplace\Services\HyperLocal_Services\purchase_service")

from infras.primary_db.main import AsyncInventoryLocalSession, init_inventory_pg_db
from infras.primary_db.services.purchase_service import PurchaseService
from schemas.v1.purchase_schemas.request_schema import UpdatePurchaseSchema, UpdatePurchaseItemsSchema, PurchaseStocksInfosType, PurchasePricingInfos
from sqlalchemy import select
from infras.primary_db.models.purchase_model import PurchaseItems
from icecream import ic

async def run_test():
    print("=======================================================")
    print("TESTING PURCHASE UPDATE IN POSTGRES PRIMARY DB")
    print("=======================================================")

    await init_inventory_pg_db()

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)

        # Execute purchase update to replace product in item c87396dc-ccc3-53a3-a184-48b67da07185 with 2c3a22b2-0ad6-5c73-96a2-2878c9696c9b
        update_payload = UpdatePurchaseSchema(
            id="776211cb-1506-5793-88cf-1bfcf74e223f",
            shop_id="050bb7e7-84af-58a4-84e9-dd95572be5d9",
            items=[
                UpdatePurchaseItemsSchema(
                    id="c87396dc-ccc3-53a3-a184-48b67da07185",
                    product_id="2c3a22b2-0ad6-5c73-96a2-2878c9696c9b",
                    variant_id=None,
                    batch_infos=None,
                    stock_infos=PurchaseStocksInfosType(stocks=2.0),
                    pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0)
                )
            ]
        )

        res = await service.update(data=update_payload)
        ic("Service update result =>", res)

    # Re-open session and check if PostgreSQL purchase_items table was updated
    async with AsyncInventoryLocalSession() as session:
        stmt = select(PurchaseItems).where(PurchaseItems.id == "c87396dc-ccc3-53a3-a184-48b67da07185")
        item_after = (await session.execute(stmt)).scalar_one_or_none()
        if item_after:
            ic("AFTER PG UPDATE =>", item_after.id, item_after.product_id, item_after.variant_id)
            assert item_after.product_id == "2c3a22b2-0ad6-5c73-96a2-2878c9696c9b", f"Expected product_id 2c3a22b2... but got {item_after.product_id}"
            assert item_after.variant_id is None, f"Expected variant_id None but got {item_after.variant_id}"

    print("=======================================================")
    print("POSTGRES PRIMARY DB UPDATED SUCCESSFULLY!")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_test())
