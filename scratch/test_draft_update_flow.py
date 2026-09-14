import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import uuid
import datetime
from schemas.v1.purchase_schemas.request_schema import (
    CreatePurchaseSchema, CreatePurchaseItemsSchema, UpdatePurchaseSchema,
    UpdatePurchaseItemsSchema, PurchaseGstInfos, GetPurchaseByIdSchema
)
from schemas.v1.purchase_schemas.custom_types import (
    PurchaseCalculationInfos, PurchaseChargeInfos, PurchasePricingInfos, PurchaseStocksInfosType
)
from infras.primary_db.services.purchase_service import PurchaseService
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.models.purchase_model import Purchase
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo

async def test_draft_update_and_promote():
    shop_id = "test_shop_draft"
    draft_id = str(uuid.uuid4())
    supplier_id = "SUP_TEST_DRAFT"
    
    inv1 = f"INV-DRAFT-{uuid.uuid4().hex[:6]}"
    inv2 = f"INV-DRAFT-{uuid.uuid4().hex[:6]}"

    print("\n--- 1. Create Draft Purchase ---")
    draft_payload = CreatePurchaseSchema(
        id=draft_id,
        shop_id=shop_id,
        supplier_id=supplier_id,
        status="DRAFT",
        type="DIRECT",
        calculation_infos=PurchaseCalculationInfos(distribute_by="NONE", gst_type="EXCLUSIVE"),
        gst_infos=PurchaseGstInfos(type="EXCLUSIVE"),
        charges_infos=PurchaseChargeInfos(transport_charge=10.0, other_charge=5.0),
        payment_infos=[],
        purchase_date=datetime.date.today(),
        invoice_no=inv1,
        items=[
            CreatePurchaseItemsSchema(
                product_id="prod_1",
                pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0),
                gst="18%",
                stock_infos=PurchaseStocksInfosType(stocks=5.0)
            )
        ]
    )

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)
        res_draft = await service.save_draft(draft_payload)
        print("Draft Save Result =>", res_draft)
        assert res_draft["success"] is True
        assert res_draft["status"] == "DRAFT"

        # Verify in Postgres DB
        db_draft = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=draft_id, shop_id=shop_id))
        assert db_draft is not None
        assert db_draft.status == "DRAFT"
        print("-> Verified: Draft saved with status DRAFT in DB")

        print("\n--- 2. Update Draft Purchase (Keep Status DRAFT) ---")
        update_draft_payload = UpdatePurchaseSchema(
            id=draft_id,
            shop_id=shop_id,
            supplier_id=supplier_id,
            status="DRAFT",
            invoice_no=inv2,
            charges_infos=PurchaseChargeInfos(transport_charge=20.0, other_charge=10.0),
            items=[
                UpdatePurchaseItemsSchema(
                    product_id="prod_1",
                    pricing_infos=PurchasePricingInfos(buy_price=120.0, sell_price=160.0),
                    gst="18%",
                    stock_infos=PurchaseStocksInfosType(stocks=10.0)
                ),
                UpdatePurchaseItemsSchema(
                    product_id="prod_2",
                    pricing_infos=PurchasePricingInfos(buy_price=50.0, sell_price=80.0),
                    gst="12%",
                    stock_infos=PurchaseStocksInfosType(stocks=2.0)
                )
            ]
        )

        res_update_draft = await service.update(update_draft_payload)
        print("Update Draft Result =>", res_update_draft)
        assert res_update_draft is True

        # Verify in Postgres DB
        db_draft_updated = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=draft_id, shop_id=shop_id))
        assert db_draft_updated is not None
        assert db_draft_updated.status == "DRAFT"
        assert db_draft_updated.invoice_no == inv2
        print("-> Verified: Draft updated successfully and retained DRAFT status!")

        print("\n--- 3. Clean up test draft ---")
        from infras.read_db.main import PURCHAESE_COLLECTION
        await PURCHAESE_COLLECTION.delete_one({"id": draft_id})
        print("-> Test draft cleaned up successfully.")

    print("\nALL DRAFT UPDATE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_draft_update_and_promote())
