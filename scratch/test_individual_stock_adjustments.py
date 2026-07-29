import asyncio
import sys
import os

# Add Stock_Mov_Adj_Service directory to sys.path
sys.path.insert(0, r"d:\projects\airport-marketplace\Services\HyperLocal_Services\Stock_Mov_Adj_Service")

from infras.primary_db.main import AsyncInventoryLocalSession, init_inventory_pg_db
from infras.primary_db.repos.stock_mov_adj_repo import StockMovAdjRepo
from messaging.msgqueue_producers.stock_mov_adj_msgqueue_producer import MessagingQueueStockMovAdjProducer
from icecream import ic

async def run_test():
    print("=======================================================")
    print("TESTING INDIVIDUAL STOCK MOVEMENT ADJUSTMENTS")
    print("=======================================================")
    
    await init_inventory_pg_db()

    async with AsyncInventoryLocalSession() as session:
        from sqlalchemy import delete
        from infras.primary_db.models.stock_mov_adj_model import StockMovementAdjustment, StockMovAdjItems
        await session.execute(delete(StockMovAdjItems))
        await session.execute(delete(StockMovementAdjustment).where(StockMovementAdjustment.shop_id == "shop-test-indiv"))
        await session.commit()

    producer = MessagingQueueStockMovAdjProducer(
        headers={},
        payload={},
        saga_datas={
            "execution": {"step": "FETCHING_PRODUCTS"},
            "data": {
                "stock_mov_adj": {
                    "shop_id": "shop-test-indiv",
                    "type": "INCREMENT",
                    "description": "Individual items test",
                    "items": [
                        {"product_id": "prod-1", "qty": 5, "type": "INCREMENT"},
                        {"product_id": "prod-2", "qty": 10, "type": "INCREMENT"}
                    ]
                },
                "products": [
                    {
                        "id": "prod-1",
                        "name": "Product One",
                        "ui_id": "PRD-0001",
                        "type_infos": {"has_variant": False, "has_batch": False, "has_serialno": False},
                        "stock_infos": {"physical_stocks": 20.0}
                    },
                    {
                        "id": "prod-2",
                        "name": "Product Two",
                        "ui_id": "PRD-0002",
                        "type_infos": {"has_variant": False, "has_batch": False, "has_serialno": False},
                        "stock_infos": {"physical_stocks": 50.0}
                    }
                ]
            }
        }
    )

    res = await producer.create_adjustment()
    ic("Producer result =>", res)

    async with AsyncInventoryLocalSession() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from infras.primary_db.models.stock_mov_adj_model import StockMovementAdjustment
        stmt = select(StockMovementAdjustment).options(selectinload(StockMovementAdjustment.items)).where(StockMovementAdjustment.shop_id == "shop-test-indiv")
        adj_list = (await session.execute(stmt)).scalars().all()
        ic("Created adjustments count =>", len(adj_list))
        assert len(adj_list) == 2, f"Should create 2 individual adjustments, found {len(adj_list)}"
        for adj in adj_list:
            ic("Adjustment =>", adj.id, adj.ui_id, "Items count =>", len(adj.items))
            assert len(adj.items) == 1, "Each adjustment should have exactly 1 item"

    print("\n=======================================================")
    print("INDIVIDUAL ADJUSTMENTS TEST PASSED SUCCESSFULLY!")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_test())
