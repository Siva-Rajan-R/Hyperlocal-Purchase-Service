import asyncio
import uuid
from icecream import ic
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.services.purchase_service import PurchaseService
from schemas.v1.purchase_schemas.request_schema import (
    CreatePurchaseSchema, CreatePurchaseItemsSchema,
    UpdatePurchaseSchema, UpdatePurchaseItemsSchema,
    GetPurchaseByIdSchema,
    PurchasePricingInfos, PurchaseStocksInfosType,
    PurchaseCalculationInfos, PurchaseGstInfos,
    PurchaseChargeInfos, PurchasePaymentInfos
)
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums, PurchasePaymentMethods

async def run_purchase_flow_test():
    shop_id = "test-shop-" + str(uuid.uuid4())[:8]
    supplier_1 = "sup-a-" + str(uuid.uuid4())[:8]
    supplier_2 = "sup-b-" + str(uuid.uuid4())[:8]
    
    prod_a = "prod-a-" + str(uuid.uuid4())[:8]
    prod_b = "prod-b-" + str(uuid.uuid4())[:8]
    prod_c_new = "prod-c-" + str(uuid.uuid4())[:8]
    prod_d_added = "prod-d-" + str(uuid.uuid4())[:8]
    
    invoice_no = "INV-" + str(uuid.uuid4())[:6]

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)
        
        print("\n==========================================")
        print("1. CREATING INITIAL PURCHASE (DRAFT)")
        print("==========================================")
        
        create_payload = CreatePurchaseSchema(
            shop_id=shop_id,
            supplier_id=supplier_1,
            type=PurchaseTypeEnums.DIRECT,
            status="DRAFT",
            invoice_no=invoice_no,
            purchase_date="2026-07-26",
            calculation_infos=PurchaseCalculationInfos(
                total_pur_items=2,
                total_pur_cost=200.0,
                total_gst_amount=0.0
            ),
            gst_infos=PurchaseGstInfos(type="EXCLUSIVE"),
            charges_infos=PurchaseChargeInfos(transport_charge=0.0, other_charge=0.0),
            payment_infos=[
                PurchasePaymentInfos(amount=50.0, method=PurchasePaymentMethods.CASH)
            ],
            items=[
                CreatePurchaseItemsSchema(
                    product_id=prod_a,
                    pricing_infos=PurchasePricingInfos(buy_price=10.0, sell_price=15.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=10.0, stocks_before=0.0, stocks_after=10.0)
                ),
                CreatePurchaseItemsSchema(
                    product_id=prod_b,
                    pricing_infos=PurchasePricingInfos(buy_price=20.0, sell_price=30.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=5.0, stocks_before=0.0, stocks_after=5.0)
                )
            ]
        )
        
        res_create = await service.save_draft(create_payload)
        ic("Draft Create Result =>", res_create)
        assert res_create.get("success") is True
        purchase_id = res_create["id"]
        
        # Get existing items from DB to extract generated item IDs
        existing_pur = await service.purchase_repo_obj.get_purchase_by_id(
            from_schemas_import := __import__('schemas.v1.purchase_schemas.request_schema', fromlist=['GetPurchaseByIdSchema']).GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id)
        )
        item_a_db = next(i for i in existing_pur.items if i.product_id == prod_a)
        item_b_db = next(i for i in existing_pur.items if i.product_id == prod_b)
        
        # Seed product documents into Mongo ProdInvCollections so update() product check passes
        from infras.read_db.main import MONGO_CLIENT
        prod_inv_collection = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
        for pid in [prod_a, prod_b, prod_c_new, prod_d_added]:
            await prod_inv_collection.update_one(
                {"id": pid, "shop_id": shop_id},
                {"$set": {"id": pid, "shop_id": shop_id, "name": f"Product-{pid[-4:]}", "ui_id": f"PRD-{pid[-4:]}", "stock_infos": {"physical_stocks": 20.0}}},
                upsert=True
            )

        print("\n==========================================")
        print("2. UPDATING SUPPLIER & INVOICE & PRODUCT & ADDING NEW PRODUCT")
        print("==========================================")
        # We will:
        # - Change Supplier to supplier_2
        # - Keep/Update Invoice Number
        # - Replace prod_b (item_b_db) with prod_c_new
        # - Add brand new item prod_d_added
        
        update_payload = UpdatePurchaseSchema(
            id=purchase_id,
            shop_id=shop_id,
            supplier_id=supplier_2,
            invoice_no=invoice_no + "-UPDATED",
            purchase_date="2026-07-26",
            payment_infos=[
                PurchasePaymentInfos(amount=50.0, method=PurchasePaymentMethods.CASH)
            ],
            items=[
                # Keep item A but DECREASE stock from 10.0 to 6.0 (no sales occurred)
                UpdatePurchaseItemsSchema(
                    id=item_a_db.id,
                    product_id=prod_a,
                    pricing_infos=PurchasePricingInfos(buy_price=10.0, sell_price=15.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=6.0, stocks_before=0.0, stocks_after=6.0)
                ),
                # Replace Item B with Prod C
                UpdatePurchaseItemsSchema(
                    id=item_b_db.id,
                    product_id=prod_c_new,
                    pricing_infos=PurchasePricingInfos(buy_price=25.0, sell_price=35.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=8.0, stocks_before=0.0, stocks_after=8.0)
                ),
                # Add new Item D (no ID provided)
                UpdatePurchaseItemsSchema(
                    id="",
                    product_id=prod_d_added,
                    pricing_infos=PurchasePricingInfos(buy_price=30.0, sell_price=45.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=4.0, stocks_before=0.0, stocks_after=4.0)
                )
            ]
        )
        
        res_update = await service.update(update_payload)
        ic("Update Result =>", res_update)
        assert res_update is True

        print("\n==========================================")
        print("3. VERIFYING UPDATED PURCHASE STATE")
        print("==========================================")
        updated_pur = await service.purchase_repo_obj.get_purchase_by_id(
            GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id)
        )
        
        ic(updated_pur.supplier_id)
        ic(updated_pur.invoice_no)
        updated_prod_ids = [i.product_id for i in updated_pur.items]
        ic(updated_prod_ids)
        
        assert updated_pur.supplier_id == supplier_2
        assert updated_pur.invoice_no == invoice_no + "-UPDATED"
        assert prod_a in updated_prod_ids
        assert prod_c_new in updated_prod_ids
        assert prod_d_added in updated_prod_ids
        assert prod_b not in updated_prod_ids
        
        print("\n==========================================")
        print("SUCCESS: ALL FLOWS WORKING AS EXPECTED!")
        print("==========================================")

if __name__ == "__main__":
    asyncio.run(run_purchase_flow_test())
