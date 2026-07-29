import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from icecream import ic
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.services.purchase_service import PurchaseService
from schemas.v1.purchase_schemas.request_schema import UpdatePurchaseSchema, UpdatePurchaseItemsSchema, PurchasePaymentInfos, PurchaseChargeInfos
from core.data_formats.enums.purchase_enums import PurchasePaymentMethods
from fastapi import HTTPException

async def test_charges():
    purchase_id = "d3f98dbe-c35a-53d5-bb03-39c24cb61a8d"
    shop_id = "d76277ab-232b-500f-9109-31538c2bc638"
    
    async with AsyncInventoryLocalSession() as session:
        service = PurchaseService(session=session)
        
        print("\n--- TEST: Explicitly passing charges_infos with 0 transport and 0 other charge ---")
        try:
            res = await service.update(UpdatePurchaseSchema(
                id=purchase_id,
                shop_id=shop_id,
                purchase_date="2026-07-17",
                charges_infos=PurchaseChargeInfos(transport_charge=0.0, other_charge=0.0), # Reset charges to 0
                payment_infos=[
                    PurchasePaymentInfos(amount=500.0, method=PurchasePaymentMethods.UPI),
                    PurchasePaymentInfos(amount=200.0, method=PurchasePaymentMethods.CASH) # Total 700
                ],
                items=[
                    UpdatePurchaseItemsSchema(
                        id="9d7c1168-0a7c-5837-8408-db27c455f0e4",
                        product_id="d40a5cf2-1150-543f-8381-8adb894e1b63",
                        gst="18%",
                        stock_infos={"stocks": 5.0}
                    )
                ]
            ))
            print("ERROR: Overpayment check failed to block!")
        except HTTPException as exc:
            ic("SUCCESSFULLY BLOCKED WITH EXPECTED HTTP 400 =>", exc.detail)

if __name__ == "__main__":
    asyncio.run(test_charges())
