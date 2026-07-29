import asyncio
import uuid
import datetime
from icecream import ic
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.services.purchase_service import PurchaseService
from infras.primary_db.models.purchase_model import Purchase, PurchaseItems, PurchaseItemsPricing
from infras.read_db.main import MONGO_CLIENT
from schemas.v1.purchase_schemas.request_schema import (
    UpdatePurchaseSchema, UpdatePurchaseItemsSchema,
    GetPurchaseByIdSchema,
    PurchasePricingInfos, PurchaseStocksInfosType,
    PurchasePaymentInfos
)
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods
from fastapi import HTTPException

async def test_real_scenarios():
    shop_id = "shop-real-" + str(uuid.uuid4())[:8]
    supplier_a = "sup-a-" + str(uuid.uuid4())[:8]
    supplier_b = "sup-b-" + str(uuid.uuid4())[:8]
    
    prod_a_id = "prod-a-" + str(uuid.uuid4())[:8]
    prod_b_id = "prod-b-" + str(uuid.uuid4())[:8]
    
    invoice_no = "INV-REAL-" + str(uuid.uuid4())[:6]
    purchase_id = str(uuid.uuid4())
    item_a_id = str(uuid.uuid4())

    # 1. Setup Mongo ProdInvCollections documents for real stock checks
    prod_inv_coll = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
    await prod_inv_coll.insert_many([
        {
            "id": prod_a_id,
            "shop_id": shop_id,
            "name": "Product A Real",
            "stock_infos": {"physical_stocks": 100.0},
            "gst": "0%"
        },
        {
            "id": prod_b_id,
            "shop_id": shop_id,
            "name": "Product B Real",
            "stock_infos": {"physical_stocks": 50.0},
            "gst": "0%"
        }
    ])

    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)
        
        print("\n=======================================================")
        print("STEP 1: INSERTING INITIAL PURCHASE (Product-A: 10 units, Paid 900/1000, Outstanding 100, Supplier-A)")
        print("=======================================================")
        
        # Insert Purchase directly into Postgres
        pur_model = Purchase(
            id=purchase_id,
            ui_id="PUR-" + purchase_id[:6].upper(),
            shop_id=shop_id,
            supplier_id=supplier_a,
            invoice_no=invoice_no,
            type="DIRECT",
            status="COMPLETED",
            purchase_view=True,
            date=datetime.datetime.now(),
            gst_infos={"type": "EXCLUSIVE"},
            charges_infos={"transport_charge": 0.0, "other_charge": 0.0},
            calculation_infos={"sub_total": 1000.0, "grand_total": 1000.0},
            payment_infos=[{"amount": 900.0, "method": "CASH"}],
            item_infos={
                "total_pur_items": 1,
                "total_pur_stocks": 10.0,
                "total_pur_cost": 1000.0,
                "total_gst_amount": 0.0
            },
            version="v1"
        )
        pur_item_model = PurchaseItems(
            id=item_a_id,
            purchase_id=purchase_id,
            product_id=prod_a_id,
            gst="0%",
            stocks=10.0,
            stocks_before=0.0,
            stocks_after=10.0
        )
        pur_pricing_model = PurchaseItemsPricing(
            purchase_id=purchase_id,
            purchase_item_id=item_a_id,
            buy_price=100.0,
            sell_price=150.0
        )
        
        session.add(pur_model)
        session.add(pur_item_model)
        session.add(pur_pricing_model)
        await session.commit()
        
        ic("Initial Purchase Created Successfully in DB =>", purchase_id)

        print("\n=======================================================")
        print("STEP 2: TESTING SCENARIO 1 (Changing Supplier-A to Supplier-B)")
        print("=======================================================")
        
        update_supplier_payload = UpdatePurchaseSchema(
            id=purchase_id,
            shop_id=shop_id,
            supplier_id=supplier_b, # Swapping to Supplier B
            invoice_no=invoice_no,
            purchase_date="2026-07-27",
            payment_infos=[
                PurchasePaymentInfos(amount=900.0, method=PurchasePaymentMethods.CASH)
            ],
            items=[
                UpdatePurchaseItemsSchema(
                    id=item_a_id,
                    product_id=prod_a_id,
                    pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=10.0, stocks_before=0.0, stocks_after=10.0)
                )
            ]
        )
        
        upd_supp_res = await service.update(update_supplier_payload)
        ic("Update Supplier Result =>", upd_supp_res)
        assert upd_supp_res is True
        
        pur_updated_supp = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id))
        ic("Updated Supplier ID in PG DB =>", pur_updated_supp.supplier_id)
        assert pur_updated_supp.supplier_id == supplier_b

        print("\n=======================================================")
        print("STEP 3: TESTING SCENARIO 2 (Replacing Product-A with Product-B & Stock Reversion)")
        print("=======================================================")
        
        update_prod_payload = UpdatePurchaseSchema(
            id=purchase_id,
            shop_id=shop_id,
            supplier_id=supplier_b,
            invoice_no=invoice_no,
            purchase_date="2026-07-27",
            payment_infos=[
                PurchasePaymentInfos(amount=900.0, method=PurchasePaymentMethods.CASH)
            ],
            items=[
                # Product-A removed, Product-B added
                UpdatePurchaseItemsSchema(
                    id="", # New item
                    product_id=prod_b_id,
                    pricing_infos=PurchasePricingInfos(buy_price=200.0, sell_price=300.0),
                    gst="0%",
                    stock_infos=PurchaseStocksInfosType(stocks=5.0, stocks_before=0.0, stocks_after=5.0)
                )
            ]
        )
        
        upd_prod_res = await service.update(update_prod_payload)
        ic("Update Product Replace Result =>", upd_prod_res)
        assert upd_prod_res is True

        pur_updated_prod = await service.purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=purchase_id, shop_id=shop_id))
        updated_items = [i.product_id for i in pur_updated_prod.items]
        ic("Updated Product IDs in PG DB =>", updated_items)
        assert prod_b_id in updated_items
        assert prod_a_id not in updated_items

        print("\n=======================================================")
        print("STEP 4: VERIFYING MONGO READ DB DATA PERSISTENCE & HISTORY UPDATES")
        print("=======================================================")
        
        pur_mongo_coll = MONGO_CLIENT["PurchaseServiceReadDb"]["PurchaseCollections"]
        pur_mongo_doc = await pur_mongo_coll.find_one({"purchase_id": purchase_id, "shop_id": shop_id})
        assert pur_mongo_doc is not None, "Purchase document not found in Mongo Read DB"
        
        ic("Mongo Document Version =>", pur_mongo_doc.get("version"))
        ic("Mongo Supplier ID =>", pur_mongo_doc.get("supplier", {}).get("supplier_id"))
        ic("Mongo Items Count =>", len(pur_mongo_doc.get("items", [])))
        ic("Mongo History Count =>", len(pur_mongo_doc.get("history", [])))
        
        assert pur_mongo_doc.get("supplier", {}).get("supplier_id") == supplier_b
        assert pur_mongo_doc.get("version") == "v3"
        assert len(pur_mongo_doc.get("history", [])) >= 2
        assert pur_mongo_doc.get("items", [])[0]["product_id"] == prod_b_id
        assert pur_mongo_doc.get("payment_status") == "PARTIALY-PAID"
        assert pur_mongo_doc.get("outstanding_amount") == 100.0

        print("\n=======================================================")
        print("STEP 5: TESTING INSUFFICIENT STOCK VALIDATION (Product-B stock reduced to 2)")
        print("=======================================================")
        
        # Set Product-B stock in Mongo to 2 (less than 5 purchased units)
        await prod_inv_coll.update_one({"id": prod_b_id, "shop_id": shop_id}, {"$set": {"stock_infos.physical_stocks": 2.0}})
        
        # Attempt to update purchase to remove Product-B when physical stock is only 2
        try:
            await service.update(UpdatePurchaseSchema(
                id=purchase_id,
                shop_id=shop_id,
                supplier_id=supplier_b,
                invoice_no=invoice_no,
                purchase_date="2026-07-27",
                items=[
                    UpdatePurchaseItemsSchema(
                        id="",
                        product_id=prod_a_id,
                        pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0),
                        gst="0%",
                        stock_infos=PurchaseStocksInfosType(stocks=10.0, stocks_before=0.0, stocks_after=10.0)
                    )
                ]
            ))
            print("ERROR: Insufficient stock check did NOT block update as expected!")
            assert False, "Should have raised HTTPException 400"
        except HTTPException as exc:
            ic("Successfully caught expected stock sufficiency error =>", exc.detail)
            assert exc.status_code == 400

        print("\n=======================================================")
        print("STEP 6: TESTING OVERPAYMENT VALIDATION (Paid 600 on 590 total cost)")
        print("=======================================================")
        
        # Reset Product-B physical stock to 50
        await prod_inv_coll.update_one({"id": prod_b_id, "shop_id": shop_id}, {"$set": {"stock_infos.physical_stocks": 50.0}})
        
        try:
            await service.update(UpdatePurchaseSchema(
                id=purchase_id,
                shop_id=shop_id,
                supplier_id=supplier_b,
                invoice_no=invoice_no,
                purchase_date="2026-07-27",
                payment_infos=[
                    PurchasePaymentInfos(amount=500.0, method=PurchasePaymentMethods.UPI),
                    PurchasePaymentInfos(amount=100.0, method=PurchasePaymentMethods.CASH)
                ],
                items=[
                    UpdatePurchaseItemsSchema(
                        id="",
                        product_id=prod_b_id,
                        pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0),
                        gst="18%",
                        stock_infos=PurchaseStocksInfosType(stocks=5.0, stocks_before=0.0, stocks_after=5.0)
                    )
                ]
            ))
            print("ERROR: Overpayment check did NOT block update as expected!")
            assert False, "Should have raised HTTPException 400 for overpayment"
        except HTTPException as exc:
            ic("Successfully caught expected overpayment error =>", exc.detail)
            assert exc.status_code == 400

        print("\n=======================================================")
        print("STEP 7: TESTING USER SPECIFIC OVERPAYMENT PAYLOAD (Paid 700 on 590 total cost without passing pricing_infos)")
        print("=======================================================")
        
        # Update existing DB item buy_price to 100
        item_b_pg_id = pur_updated_prod.items[0].id
        
        try:
            await service.update(UpdatePurchaseSchema(
                id=purchase_id,
                shop_id=shop_id,
                supplier_id=supplier_b,
                invoice_no=invoice_no,
                purchase_date="2026-07-27",
                payment_infos=[
                    PurchasePaymentInfos(amount=500.0, method=PurchasePaymentMethods.UPI),
                    PurchasePaymentInfos(amount=200.0, method=PurchasePaymentMethods.CASH) # Total paid 700
                ],
                items=[
                    UpdatePurchaseItemsSchema(
                        id=item_b_pg_id,
                        product_id=prod_b_id,
                        pricing_infos=PurchasePricingInfos(buy_price=100.0, sell_price=150.0),
                        gst="18%", # 5 * 100 = 500 + 90 GST = 590 total cost
                        stock_infos=PurchaseStocksInfosType(stocks=5.0, stocks_before=0.0, stocks_after=5.0)
                    )
                ]
            ))
            print("ERROR: Overpayment check did NOT block user payload (700 paid vs 590 cost) as expected!")
            assert False, "Should have raised HTTPException 400 for 700 paid on 590 total cost"
        except HTTPException as exc:
            ic("Successfully caught expected user payload overpayment error =>", exc.detail)
            assert exc.status_code == 400

        print("\n=======================================================")
        print("ALL REAL DATA SCENARIOS & OVERPAYMENT CHECKS PASSED CLEANLY!")
        print("=======================================================")

        # Clean up test documents from Mongo
        await prod_inv_coll.delete_many({"shop_id": shop_id})
        await pur_mongo_coll.delete_many({"purchase_id": purchase_id})

if __name__ == "__main__":
    asyncio.run(test_real_scenarios())
