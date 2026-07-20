from models.service_models.base_service_model import BaseServiceModel
from ..repos.purchase_repo import PurchaseRepo

from core.data_formats.enums.stock_adj_enums import StockAdjustmentMovementType,StockAdjustmentTypesEnum
from typing import Optional,List
from ..models.purchase_model import Purchase,PurchaseItems,PurchaseItemsPricing,PurchaseItemsStoragelocation,PurchaseItemsReorderPoint
from sqlalchemy.ext.asyncio import AsyncSession
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from schemas.v1.purchase_schemas.db_schemas import CreatePurchaseDbSchema,CreatePurchaseItemsDbSchema,CreatePurchasePricingDbSchema,CreateStorageLocationDbSchema,UpdatePurchaseDbSchema,UpdatePurchaseItemsDbSchema,UpdatePurchasePricingDbSchema,UpdateStorageLocationDbSchema,DeletePurchaseDbSchema,UpdateReorderPointDbSchema
from schemas.v1.purchase_schemas.request_schema import CreatePurchaseItemsSchema,CreatePurchasePricingSchema,CreatePurchaseSchema,CreateStorageLocationSchema,UpdatePurchaseItemsSchema,UpdatePurchasePricingSchema,UpdatePurchaseSchema,UpdateStorageLocationSchema,DeletePurchaseSchema,PurchaseItemInfos,GetPurchaseByIdSchema,GetAllPurchaseSchemas,GetPurchaseByShopIdSchema
from core.errors.messaging_errors import BussinessError,FatalError,RetryableError
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums,PurchaseViewsEnums
from icecream import ic
from typing import Union,List,Dict
from datetime import date
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
from infras.read_db.models.purchase_model import PurchaseReadModel, SupplierInfo, PurchaseItemReadModel, ReadVariantInfos, ReadBatchInfos, ReadStocksInfos, ReadReorderPointInfos, ReadStorageLocationInfos
import httpx
from messaging.saga_producer import SagaProducer,CreateSagaStateSchema,SagaStatusEnum
from hyperlocal_platform.core.enums.saga_state_enum import SagaStepsValueEnum
from hyperlocal_platform.core.typed_dicts.saga_status_typ_dict import SagaStateExecutionTypDict
from infras.primary_db.services.customfield_service import CustomFieldsService
from schemas.v1.request_schemas.customfield_schema import CreateCustomFieldSchema,CreateCustomFieldValueSchema,BulkCreateCustomFieldValuesSchema,UpdateCustomFieldSchema,UpdateCustomFieldValueSchema,GetFieldByShopIdSchema,GetFieldById,GetFieldByName,GetValueByIdName,GetvaluesByCustomerId

from integrations.utility_service import get_ui_id

ACTIVITY_LOG_URL = "http://127.0.0.1:8001/activity-logs"

async def _send_activity_log(shop_id: str, action: str, entity_id: str, description: str, changes: list = None):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(ACTIVITY_LOG_URL, json={
                "shop_id": shop_id,
                "user_name": "siva",
                "service": "Purchase",
                "action": action,
                "entity_type": "Purchase",
                "entity_id": entity_id,
                "description": description,
                "changes": changes or []
            })
    except Exception as e:
        ic(f"Failed to log activity: {e}")


class PurchaseService:
    def __init__(self, session:AsyncSession):
        self.session=session
        self.purchase_repo_obj=PurchaseRepo(session=session)


    async def create(self,data:CreatePurchaseSchema, executing_user_id: Optional[str] = None):
        # Validate paid amount against total purchase cost (QTY * (BUY PRICE + GST)) + charges
        total_item_cost = 0.0
        for item in data.items:
            qty = item.stock_infos.stocks
            buy_price = item.pricing_infos.buy_price
            gst_str = item.gst or "0%"
            gst_val = float(gst_str.replace("%", "").strip()) / 100.0 if "%" in gst_str else 0.0
            item_cost = qty * (buy_price + (buy_price * gst_val))
            total_item_cost += item_cost
        
        total_purchase_cost = total_item_cost
        
        total_paid = sum(p.amount for p in data.payment_infos) if data.payment_infos else 0.0
        if total_paid > total_purchase_cost:
            ic("Paid amount exceeds total purchase cost, leading to negative outstanding balance.")
            return False

        invoice_exists=await self.purchase_repo_obj.verify_invoice_exists(invoice_no=data.invoice_no,shop_id=data.shop_id)
        if invoice_exists:
            ic("invoice number already exists")
            return False
        

        saga_id:str=generate_uuid()
        steps={
            "SUPPLIER_VERIFY":SagaStepsValueEnum.PENDING,
            "PRODUCT_VERIFY_UPDATE":SagaStepsValueEnum.PENDING,
            "FETCHING_PRODUCTS":SagaStepsValueEnum.PENDING
        }

        saga_data={"purchase":data.model_dump(mode="json"), "executing_user_id": executing_user_id}
        await SagaProducer.emit(
            saga_payload=CreateSagaStateSchema(
                id=saga_id,
                status=SagaStatusEnum.IN_PROGRESS,
                type="PURCHASE_CREATED",
                steps=steps,
                execution=SagaStateExecutionTypDict(
                    step="SUPPLIER_VERIFY",
                    service="SUPPLIERS"
                ),
                data=saga_data
            ),
            routing_key="suppliers.service.routing.key",
            exchange_name="suppliers.service.exchange",
            headers={
                "reply_key":"purchase.producer.routing.key",
                "reply_exchange":"purchase.producer.exchange",
                "reply_entity_name":"create_purchase",
                "reply_service_name":"PURCHASE",
                "service_name":"SUPPLIERS",
                "entity_name":"get_supplier_by_id",
                "body":{
                    "shop_id":data.shop_id,
                    "id":data.supplier_id
                }

            }
        )

        return True


        



    async def update(self,data:UpdatePurchaseSchema):
        purchase_repo_obj=PurchaseRepo(session=self.session)
        items_toadd=[]
        items_toupdate=[]
        pricing_toadd=[]
        pricing_toupdate=[]
        stl_toadd=[]
        stl_toupdate=[]
        rop_toadd=[]
        rop_toupdate=[]
        inventory_toupdate=[]

        item_infos = {
            'total_pur_items': 0,
            'total_pur_stocks': 0,
            'total_pur_cost': 0,
            'total_gst_amount': 0
        }

        pur_get_res=await purchase_repo_obj.get_purchase_by_id(data=GetPurchaseByIdSchema(id=data.id,shop_id=data.shop_id))
        ic(pur_get_res)
        if not pur_get_res:
            ic("The give purchase was not found")
            return False
        
        # Enforce that existing items cannot be deleted
        existing_item_ids = {item.id for item in pur_get_res.items}
        incoming_item_ids = {item.id for item in data.items if item.id}
        ic(existing_item_ids,incoming_item_ids)
        if not existing_item_ids.issubset(incoming_item_ids):
            ic("Existing items cannot be removed.")
            return False

        # Prevent duplicate item IDs in update payload
        incoming_item_ids_list = [item.id for item in data.items if item.id]
        if len(incoming_item_ids_list) != len(set(incoming_item_ids_list)):
            from fastapi import HTTPException
            from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Updating Purchase",
                    status_code=400,
                    description="Duplicate purchase item IDs are not allowed",
                    success=False
                )
            )

        # Prevent duplicate product/variant/batch combinations in update payload
        product_variant_combos = []
        for item in data.items:
            batch_name = item.batch_infos.name if item.batch_infos else None
            batch_id = item.batch_infos.id if item.batch_infos else None
            combo = (item.product_id, item.variant_id, batch_name, batch_id)
            if combo in product_variant_combos:
                from fastapi import HTTPException
                from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Updating Purchase",
                        status_code=400,
                        description="Duplicate products in purchase items are not allowed",
                        success=False
                    )
                )
            product_variant_combos.append(combo)

        # Fetch product metadata from Mongo to check has_batch / has_serialno
        product_ids = [itm.product_id for itm in data.items]
        from infras.read_db.main import MONGO_CLIENT
        prod_inv_collection = MONGO_CLIENT["InventoryServiceReadDb"]["ProdInvCollections"]
        cursor = prod_inv_collection.find({"id": {"$in": product_ids}, "shop_id": data.shop_id})
        product_docs = {doc["id"]: doc async for doc in cursor}
        
        # Verify that all product IDs in payload actually exist in the database
        for item in data.items:
            if item.product_id not in product_docs:
                from fastapi import HTTPException
                from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Updating Purchase",
                        status_code=400,
                        description=f"Product with ID {item.product_id} not found.",
                        success=False
                    )
                )
        
        mapped_items={item.id: item for item in pur_get_res.items}
        ic(mapped_items)
        
        # Validate paid amount before performing any database updates
        temp_total_pur_cost = 0.0
        temp_total_gst_amount = 0.0
        
        for item in data.items:
            prod_doc = product_docs.get(item.product_id) or {}
            type_infos = prod_doc.get("type_infos") or {}
            
            t_gst = item.gst
            t_stocks = item.stock_infos.stocks
            
            pur_item_id = item.id
            is_new = not pur_item_id or pur_item_id not in mapped_items
            
            if is_new:
                if not item.stock_infos or not item.pricing_infos or item.stock_infos.stocks is None:
                    from fastapi import HTTPException
                    from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                    raise HTTPException(
                        status_code=400,
                        detail=ErrorResponseTypDict(
                            msg="Error : Updating Purchase",
                            status_code=400,
                            description="Pricing infos and stock infos are mandatory for new items",
                            success=False
                        )
                    )
                prev_pricing = None
                prev_gst_infos = pur_get_res.gst_infos
                stock_toupdate = t_stocks
            else:
                db_item = mapped_items[pur_item_id]
                prev_pricing = db_item.pricing_infos[0] if db_item.pricing_infos else None
                prev_gst_infos = pur_get_res.gst_infos
                stock_toupdate = t_stocks
            
            db_item_local = mapped_items.get(pur_item_id) if not is_new else None
            item_gst = t_gst or (db_item_local.gst if db_item_local else (prod_doc.get("gst") or "0%"))
            buy_price_val = item.pricing_infos.buy_price if item.pricing_infos else (prev_pricing.buy_price if prev_pricing else 0.0)
            
            tot_pur_cost = buy_price_val * stock_toupdate
            temp_total_pur_cost += tot_pur_cost
            
            gst_type = ""
            if prev_gst_infos:
                if isinstance(prev_gst_infos, dict):
                    gst_type = prev_gst_infos.get('type') or ""
                else:
                    gst_type = getattr(prev_gst_infos, 'type', '') or ""

            if item_gst and item_gst.endswith('%') and gst_type == "EXCLUSIVE":
                try:
                    gst_rate = float(item_gst[:-1]) / 100.0
                    temp_total_gst_amount += gst_rate * tot_pur_cost
                except ValueError:
                    pass

        existing_read_doc = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
        payment_infos = data.payment_infos if data.payment_infos is not None else (existing_read_doc.get("payment_infos") if existing_read_doc else [])
        payment_infos_dicts = [p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in payment_infos]
        total_amount_paid = sum(float(payment.get('amount', 0)) for payment in payment_infos_dicts)
        
        final_total_cost = float(temp_total_pur_cost + temp_total_gst_amount)
        charges_infos = data.charges_infos.model_dump(mode="json") if data.charges_infos else (existing_read_doc.get("charges_infos") if existing_read_doc else {})
        transport_charge = float(charges_infos.get("transport_charge", 0.0)) if charges_infos else 0.0
        other_charge = float(charges_infos.get("other_charge", 0.0)) if charges_infos else 0.0
        total_purchase_cost = final_total_cost + transport_charge + other_charge
        
        if total_amount_paid > total_purchase_cost:
            from fastapi import HTTPException
            from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Updating Purchase",
                    status_code=400,
                    description="Enter the proper amount and also it should not be goes to minus also",
                    success=False
                )
            )
        
        for item in data.items:
            prod_doc = product_docs.get(item.product_id) or {}
            type_infos = prod_doc.get("type_infos") or {}
            has_batch = type_infos.get("has_batch", False)
            has_serialno = type_infos.get("has_serialno", False)
            
            if not has_batch:
                item.batch_infos = None
            if not has_serialno:
                item.serialno_numbers = []

            pur_item_id = item.id
            is_new_item = not pur_item_id or pur_item_id not in mapped_items
            db_item_local = mapped_items.get(pur_item_id) if not is_new_item else None
            item_gst = item.gst or (db_item_local.gst if db_item_local else (prod_doc.get("gst") or "0%"))
            
            if is_new_item:
                pur_item_id = generate_uuid()
                prev_batch_id = item.batch_infos.id if item.batch_infos else None
                prev_variant_id = item.variant_id
                prev_serialno_numbers = set()
                prev_stocks = 0.0
                target_stock_infos = {}
                if has_batch:
                    b_id = item.batch_infos.id if item.batch_infos else None
                    b_name = item.batch_infos.name if item.batch_infos else None
                    for b in prod_doc.get("batch_infos", []):
                        if (b_id and b.get("id") == b_id) or (b_name and b.get("name") == b_name):
                            target_stock_infos = b.get("stock_infos") or {}
                            break
                else:
                    target_stock_infos = prod_doc.get("stock_infos") or {}
                
                prev_stocks_before = float(target_stock_infos.get("physical_stocks") or 0.0)
                prev_stocks_after = prev_stocks_before + item.stock_infos.stocks
                prev_stl = None
                prev_rop = None
                prev_pricing = None
                prev_gst_infos = pur_get_res.gst_infos
                
                stock_toupdate = item.stock_infos.stocks
                stock_diff = stock_toupdate
            else:
                db_item = mapped_items[pur_item_id]
                prev_batch_id=db_item.batch_id
                
                if prev_batch_id:
                    incoming_batch_id = item.batch_infos.id if item.batch_infos else None
                    incoming_batch_name = item.batch_infos.name if item.batch_infos else None
                    
                    existing_read_doc = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
                    db_batch_name = ""
                    if existing_read_doc and "items" in existing_read_doc:
                        for existing_itm in existing_read_doc["items"]:
                            if existing_itm.get("id") == pur_item_id:
                                if existing_itm.get("batch_infos"):
                                    db_batch_name = existing_itm["batch_infos"].get("name") or ""
                                break
                                
                    if incoming_batch_id and incoming_batch_id != prev_batch_id:
                        ic("Existing batch ID cannot be modified.")
                        return False
                    if incoming_batch_name and incoming_batch_name != db_batch_name:
                        ic("Existing batch name cannot be modified.")
                        return False

                prev_variant_id=db_item.variant_id
                prev_serialno_numbers=set(db_item.serial_numbers or [])
                prev_stocks=db_item.stocks
                prev_stocks_before=db_item.stocks_after #the stock after should be a stock before
                prev_stocks_after=db_item.stocks_after
                prev_stl=db_item.storage_locations[0] if db_item.storage_locations else None
                prev_rop=db_item.reorder_point[0] if db_item.reorder_point else None
                prev_gst_infos=pur_get_res.gst_infos
                prev_pricing = db_item.pricing_infos[0] if db_item.pricing_infos else None
                
                stock_toupdate=item.stock_infos.stocks
                stock_diff=stock_toupdate-prev_stocks
                if stock_diff < 0:
                    from fastapi import HTTPException
                    from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                    raise HTTPException(
                        status_code=400,
                        detail=ErrorResponseTypDict(
                            msg="Error : Updating Purchase",
                            status_code=400,
                            description="purchase cant be decresable use stock adjustment only increase",
                            success=False
                        )
                    )

            # Validate serial numbers quantity matching total stock
            new_serial_set = set(item.serialno_numbers or [])
            if has_serialno and len(new_serial_set) != stock_toupdate:
                ic("Invalid Serial Numbers count", len(new_serial_set), stock_toupdate)
                return False

            if is_new_item:
                items_toadd.append(
                    PurchaseItems(
                        id=pur_item_id,
                        purchase_id=data.id,
                        product_id=item.product_id,
                        variant_id=item.variant_id,
                        batch_id=prev_batch_id,
                        gst=item_gst,
                        stocks=item.stock_infos.stocks,
                        stocks_before=prev_stocks_before,
                        stocks_after=prev_stocks_after,
                        serial_numbers=list(new_serial_set)
                    )
                )
            else:
                items_toupdate.append(
                    UpdatePurchaseItemsDbSchema(
                        id=pur_item_id,
                        product_id=item.product_id,
                        gst=item_gst,
                        stocks=item.stock_infos.stocks,
                        stocks_before=prev_stocks_before,
                        stocks_after=prev_stocks_after+stock_diff,
                        serial_numbers=list(new_serial_set)
                    )
                )

            buy_price_val = item.pricing_infos.buy_price if item.pricing_infos else (prev_pricing.buy_price if prev_pricing else 0.0)
            sell_price_val = item.pricing_infos.sell_price if item.pricing_infos else (prev_pricing.sell_price if prev_pricing else 0.0)

            if is_new_item:
                pricing_toadd.append(
                    PurchaseItemsPricing(
                        purchase_id=data.id,
                        purchase_item_id=pur_item_id,
                        buy_price=buy_price_val,
                        sell_price=sell_price_val
                    )
                )
            else:
                if item.pricing_infos:
                    pricing_toupdate.append(
                        UpdatePurchasePricingDbSchema(
                            purchase_id=data.id,
                            purchase_item_id=pur_item_id,
                            buy_price=buy_price_val,
                            sell_price=sell_price_val
                        )
                    )

            if item.storage_location_infos:
                if is_new_item:
                    stl_toadd.append(
                        PurchaseItemsStoragelocation(
                            purchase_item_id=pur_item_id,
                            purchase_id=data.id,
                            name=item.storage_location_infos.name
                        )
                    )
                else:
                    if prev_stl:
                        stl_toupdate.append(
                            UpdateStorageLocationDbSchema(
                                purchase_item_id=pur_item_id,
                                purchase_id=data.id,
                                name=item.storage_location_infos.name
                            )
                        )
                    else:
                        stl_toadd.append(
                            PurchaseItemsStoragelocation(
                                purchase_item_id=pur_item_id,
                                purchase_id=data.id,
                                name=item.storage_location_infos.name
                            )
                        )

            if item.reorder_point_infos:
                if is_new_item:
                    rop_toadd.append(
                        PurchaseItemsReorderPoint(
                            purchase_id=data.id,
                            purchase_item_id=pur_item_id,
                            reorder_point=item.reorder_point_infos.reorder_point
                        )
                    )
                else:
                    if prev_rop:
                        rop_toupdate.append(
                            UpdateReorderPointDbSchema(
                                purchase_id=data.id,
                                purchase_item_id=pur_item_id,
                                reorder_point=item.reorder_point_infos.reorder_point
                            )
                        )
                    else:
                        rop_toadd.append(
                            PurchaseItemsReorderPoint(
                                purchase_id=data.id,
                                purchase_item_id=pur_item_id,
                                reorder_point=item.reorder_point_infos.reorder_point
                            )
                        )

            # Construct Delta stock adjustments for Inventory updates
            # INCREMENT inventory adjustments for newly added stock or serials
            added_sns = new_serial_set - prev_serialno_numbers
            removed_sns = prev_serialno_numbers - new_serial_set

            if is_new_item:
                inventory_toupdate.append({
                    'shop_id': data.shop_id,
                    'product_id': item.product_id,
                    'variant_id': item.variant_id,
                    'batch_infos': item.batch_infos.model_dump(mode="json") if item.batch_infos else None,
                    'serialno_infos': [{'name': sn} for sn in new_serial_set],
                    'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                    'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                    'gst': item_gst,
                    'buy_price': buy_price_val,
                    'sell_price': sell_price_val,
                    'stocks': stock_toupdate,
                    'type': 'INCREMENT',
                    "entity_name": 'PURCHASE',
                    'create_stock_mov_adj': True
                })
            else:
                # Existing item stock INCREMENT
                if stock_diff > 0:
                    inventory_toupdate.append({
                        'shop_id': data.shop_id,
                        'product_id': item.product_id,
                        'variant_id': prev_variant_id,
                        'batch_infos': {'id': prev_batch_id} if prev_batch_id else None,
                        'serialno_infos': [{'name': sn} for sn in added_sns],
                        'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                        'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                        'gst': item_gst,
                        'buy_price': buy_price_val,
                        'sell_price': sell_price_val,
                        'stocks': stock_diff,
                        'type': 'INCREMENT',
                        "entity_name": 'PURCHASE',
                        'create_stock_mov_adj': True
                    })
                # Existing item stock DECREMENT
                elif stock_diff < 0:
                    inventory_toupdate.append({
                        'shop_id': data.shop_id,
                        'product_id': item.product_id,
                        'variant_id': prev_variant_id,
                        'batch_infos': {'id': prev_batch_id} if prev_batch_id else None,
                        'serialno_infos': [{'name': sn} for sn in removed_sns],
                        'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                        'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                        'gst': item_gst,
                        'buy_price': buy_price_val,
                        'sell_price': sell_price_val,
                        'stocks': abs(stock_diff),
                        'type': 'DECREMENT',
                        "entity_name": 'PURCHASE',
                        'create_stock_mov_adj': True
                    })
                # If stock quantity is unchanged, but serial numbers were swapped/replaced:
                else:
                    if added_sns:
                        inventory_toupdate.append({
                            'shop_id': data.shop_id,
                            'product_id': item.product_id,
                            'variant_id': prev_variant_id,
                            'batch_infos': {'id': prev_batch_id} if prev_batch_id else None,
                            'serialno_infos': [{'name': sn} for sn in added_sns],
                            'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                            'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                            'gst': item_gst,
                            'buy_price': buy_price_val,
                            'sell_price': sell_price_val,
                            'stocks': 0.0,
                            'type': 'INCREMENT',
                            "entity_name": 'PURCHASE',
                            'create_stock_mov_adj': True
                        })
                    if removed_sns:
                        inventory_toupdate.append({
                            'shop_id': data.shop_id,
                            'product_id': item.product_id,
                            'variant_id': prev_variant_id,
                            'batch_infos': {'id': prev_batch_id} if prev_batch_id else None,
                            'serialno_infos': [{'name': sn} for sn in removed_sns],
                            'storage_location': item.storage_location_infos.name if item.storage_location_infos else None,
                            'reorder_point': item.reorder_point_infos.reorder_point if item.reorder_point_infos else None,
                            'gst': item_gst,
                            'buy_price': buy_price_val,
                            'sell_price': sell_price_val,
                            'stocks': 0.0,
                            'type': 'DECREMENT',
                            "entity_name": 'PURCHASE',
                            'create_stock_mov_adj': True
                        })

            tot_pur_cost=buy_price_val * stock_toupdate
            item_infos['total_pur_stocks']+=stock_toupdate
            item_infos['total_pur_cost']+=tot_pur_cost
            gst_type = ""
            if prev_gst_infos:
                if isinstance(prev_gst_infos, dict):
                    gst_type = prev_gst_infos.get('type') or ""
                else:
                    gst_type = getattr(prev_gst_infos, 'type', '') or ""

            if item_gst and item_gst.endswith('%') and gst_type == "EXCLUSIVE":
                try:
                    gst_rate = float(item_gst[:-1]) / 100.0
                    item_infos['total_gst_amount'] += gst_rate * (tot_pur_cost)
                except ValueError:
                    pass
            item_infos['total_pur_items']+=1

        old_version = getattr(pur_get_res, "version", "v1") or "v1"
        def increment_version(version_str: str) -> str:
            if not version_str or not version_str.startswith('v'):
                return 'v2'
            try:
                num = int(version_str[1:])
                return f"v{num + 1}"
            except ValueError:
                return 'v2'
        new_version = increment_version(old_version)

        purchase_toadd=UpdatePurchaseDbSchema(
            id=data.id,
            shop_id=data.shop_id,
            date=data.purchase_date,
            item_infos=item_infos,
            version=new_version,
            **data.model_dump(mode="json",exclude=['purchase_date','item_infos','id','shop_id'])
        )

        pur_add_res=await purchase_repo_obj.update_bulk_purchase(data=[purchase_toadd])
        self.session.expire_all()
        ic(pur_add_res)
        if pur_add_res:
            if data.custom_fields:
                cust_obj=await CustomFieldsService(session=self.session).upsert_values(
                data=CreateCustomFieldValueSchema(
                        shop_id=data.shop_id,
                        purchase_id=data.id,
                        value_infos=[
                            {'field_id':id,"value":value}
                            for id,value in data.custom_fields.items()
                        ]
                    )
                )
                ic(cust_obj)
                
            if items_toadd:
                await purchase_repo_obj.create_bulk_items(data=items_toadd)
            await purchase_repo_obj.update_bulk_item(data=items_toupdate)
            if pricing_toadd:
                await purchase_repo_obj.create_bulk_pricing(data=pricing_toadd)
            if pricing_toupdate:
                await purchase_repo_obj.update_bulk_pricing(data=pricing_toupdate)
            if stl_toadd:
                await purchase_repo_obj.create_bulk_stl(data=stl_toadd)
            if stl_toupdate:
                await purchase_repo_obj.update_bulk_stl(data=stl_toupdate)
            if rop_toadd:
                await purchase_repo_obj.create_bulk_rop(data=rop_toadd)
            if rop_toupdate:
                await purchase_repo_obj.update_bulk_rop(data=rop_toupdate)

        # Update Read DB (MongoDB) and Analytics Event
        try:
            existing_read_doc = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
            fresh_pur = await purchase_repo_obj.get_purchase_by_id(GetPurchaseByIdSchema(id=data.id, shop_id=data.shop_id))
            
            existing_items_map = {}
            if existing_read_doc and "items" in existing_read_doc:
                for itm in existing_read_doc["items"]:
                    existing_items_map[itm["id"]] = itm
                    
            read_items = []
            total_pur_cost = 0.0
            total_pur_stocks = 0.0
            total_gst_amount = 0.0
            
            for db_item in fresh_pur.items:
                item_id = db_item.id
                existing_item = existing_items_map.get(item_id) or {}
                
                prod_doc = product_docs.get(db_item.product_id) or {}
                
                product_name = prod_doc.get("name") or existing_item.get("name") or "Product"
                product_ui_id = prod_doc.get("ui_id") or existing_item.get("ui_id") or "PROD"
                category_infos = prod_doc.get("category_infos") or existing_item.get("category_infos")
                unit_infos = prod_doc.get("unit_infos") or existing_item.get("unit_infos")
                
                buy_price = db_item.pricing_infos[0].buy_price if db_item.pricing_infos else 0.0
                sell_price = db_item.pricing_infos[0].sell_price if db_item.pricing_infos else 0.0
                stocks = db_item.stocks
                
                total_amount = buy_price * stocks
                total_pur_cost += total_amount
                total_pur_stocks += stocks
                
                gst = db_item.gst or "0%"
                gst_rate = 0.0
                if gst and gst.endswith('%'):
                    try:
                        gst_rate = float(gst[:-1]) / 100.0
                    except ValueError:
                        pass
                
                gst_infos_val = data.gst_infos if hasattr(data, "gst_infos") and data.gst_infos else (existing_read_doc.get("gst_infos") if existing_read_doc else {})
                if gst_infos_val and gst_infos_val.get("type") == "EXCLUSIVE":
                    total_gst_amount += gst_rate * total_amount
                    
                variant_infos_model = None
                if db_item.variant_id:
                    variants_dict = prod_doc.get("variants") or {}
                    match_var = variants_dict.get(db_item.variant_id)
                    if match_var:
                        variant_infos_model = ReadVariantInfos(
                            id=db_item.variant_id,
                            name=match_var.get("name") or ""
                        )
                    else:
                        if existing_item.get("variant_infos"):
                            variant_infos_model = ReadVariantInfos(**existing_item["variant_infos"])
                    
                batch_infos_model = None
                if db_item.batch_id:
                    batches_list = prod_doc.get("batch_infos") or []
                    match_batch = None
                    for b in batches_list:
                        if b.get("id") == db_item.batch_id:
                            match_batch = b
                            break
                    if match_batch:
                        exp_infos = match_batch.get("expiration_infos") or {}
                        batch_infos_model = ReadBatchInfos(
                            id=db_item.batch_id,
                            name=match_batch.get("name") or "",
                            mfg_date=match_batch.get("manufacturing_date") or match_batch.get("mfg_date"),
                            exp_date=match_batch.get("expiry_date") or match_batch.get("exp_date")
                        )
                    else:
                        if existing_item.get("batch_infos"):
                            batch_infos_model = ReadBatchInfos(**existing_item["batch_infos"])
                    
                stock_infos_model = ReadStocksInfos(
                    stocks=stocks,
                    stocks_before=db_item.stocks_before,
                    stocks_after=db_item.stocks_after
                )
                
                reorder_point_model = None
                if db_item.reorder_point:
                    reorder_point_model = ReadReorderPointInfos(
                        id=str(db_item.reorder_point[0].id),
                        reorder_point=db_item.reorder_point[0].reorder_point
                    )
                    
                storage_location_model = None
                if db_item.storage_locations:
                    storage_location_model = ReadStorageLocationInfos(
                        id=str(db_item.storage_locations[0].id),
                        name=db_item.storage_locations[0].name
                    )
                    
                read_items.append(
                    PurchaseItemReadModel(
                        id=item_id,
                        product_id=db_item.product_id,
                        ui_id=product_ui_id,
                        name=product_name,
                        category_infos=category_infos,
                        unit_infos=unit_infos,
                        variant_infos=variant_infos_model,
                        batch_infos=batch_infos_model,
                        stocks_infos=stock_infos_model,
                        reorder_point_infos=reorder_point_model,
                        storage_location_infos=storage_location_model,
                        serial_numbers=db_item.serial_numbers or [],
                        sell_price=sell_price,
                        buy_price=buy_price,
                        total_amount=total_amount,
                        gst=gst
                    )
                )
                
            payment_infos = data.payment_infos if data.payment_infos is not None else (existing_read_doc.get("payment_infos") if existing_read_doc else [])
            payment_infos_dicts = [p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in payment_infos]
            total_amount_paid = sum(float(payment.get('amount', 0)) for payment in payment_infos_dicts)
            
            final_total_cost = float(total_pur_cost + total_gst_amount)
            charges_infos = data.charges_infos.model_dump(mode="json") if data.charges_infos else (existing_read_doc.get("charges_infos") if existing_read_doc else {})
            transport_charge = float(charges_infos.get("transport_charge", 0.0)) if charges_infos else 0.0
            other_charge = float(charges_infos.get("other_charge", 0.0)) if charges_infos else 0.0
            total_purchase_cost = final_total_cost + transport_charge + other_charge
            
            if total_amount_paid > total_purchase_cost:
                from fastapi import HTTPException
                from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponseTypDict(
                        msg="Error : Updating Purchase",
                        status_code=400,
                        description="Enter the proper amount and also it should not be goes to minus also",
                        success=False
                    )
                )
                
            outstanding_amount = abs(final_total_cost - total_amount_paid)
            
            if outstanding_amount == 0:
                outstanding_status = "COMPLETED"
            elif total_amount_paid == 0:
                outstanding_status = "NOT-PAID"
            else:
                outstanding_status = "PARTIALY-PAID"
                
            supplier_id = fresh_pur.supplier_id
            supplier_name = "Supplier"
            if existing_read_doc and existing_read_doc.get("supplier"):
                supplier_name = existing_read_doc["supplier"].get("supplier_name", "Supplier")
                
            supplier_info = SupplierInfo(supplier_id=supplier_id, supplier_name=supplier_name)
            
            cf_dict = {}
            cf_data = data.custom_fields or (existing_read_doc.get("custom_fields") if existing_read_doc else {})
            if isinstance(cf_data, dict):
                if "values" in cf_data:
                    for v in cf_data.get("values"):
                        if "field_name" in v and "value" in v:
                            cf_dict[v["field_name"]] = v["value"]
                else:
                    cf_dict = cf_data
                    
            purchase_read_model = PurchaseReadModel(
                purchase_id=fresh_pur.id,
                ui_id=fresh_pur.ui_id,
                invoice_no=fresh_pur.invoice_no or "",
                shop_id=fresh_pur.shop_id,
                purchase_date=fresh_pur.date,
                supplier=supplier_info,
                total_cost=final_total_cost,
                total_items=len(read_items),
                total_quantity=total_pur_stocks,
                payment_infos=payment_infos_dicts,
                charges_infos=data.charges_infos.model_dump(mode="json") if data.charges_infos else (existing_read_doc.get("charges_infos") if existing_read_doc else {}),
                gst_infos=gst_infos_val,
                payment_status=outstanding_status,
                outstanding_amount=outstanding_amount,
                calculations=data.calculation_infos.model_dump(mode="json") if data.calculation_infos else (existing_read_doc.get("calculations") if existing_read_doc else {}),
                custom_fields=cf_dict,
                items=read_items,
                item_infos=item_infos,
                version=new_version
            )
            
            # Save history copy to PG
            await purchase_repo_obj.create_history(
                purchase_id=fresh_pur.id,
                version=new_version,
                purchase_data=purchase_read_model.model_dump(mode="json", exclude={"history"})
            )
            
            await PurchaseReadDbRepo.update_purchase_with_history(purchase_read_model.model_dump(mode="json"), new_version)
            
            # Send delta analytics event
            try:
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                
                # Publish supplier outstanding update
                old_outstanding = float(existing_read_doc.get("outstanding_amount", 0.0)) if existing_read_doc else 0.0
                new_outstanding = outstanding_amount
                
                if new_outstanding != old_outstanding:
                    diff_amount = abs(new_outstanding - old_outstanding)
                    update_type = "INCREMENT" if new_outstanding > old_outstanding else "DECREMENT"
                    
                    try:
                        supplier_payload = {
                            "id": supplier_id,
                            "shop_id": fresh_pur.shop_id,
                            "outstanding_infos": {
                                "amount": float(diff_amount)
                            },
                            "type": update_type
                        }
                        if update_type == "DECREMENT":
                            last_payment = payment_infos_dicts[-1] if payment_infos_dicts else {}
                            pay_method = last_payment.get("mode") or last_payment.get("method") or "N/A"
                            if hasattr(pay_method, "value"):
                                pay_method = pay_method.value
                            supplier_payload.update({
                                "entity_name": "purchase",
                                "entity_id": fresh_pur.id,
                                "payment_method": str(pay_method),
                                "notes": last_payment.get("notes") or f"cleared outstanding for the purchase"
                            })
                        await rabbitmq_msg_obj.publish_event(
                            routing_key="suppliers.service.routing.key",
                            exchange_name="suppliers.service.exchange",
                            payload=supplier_payload,
                            headers={
                                "entity_name": "update_supllier_outstanding",
                                "service_name": "SUPPLIERS",
                                "saga_id": "none",
                                "reply_key": "none",
                                "reply_exchange": "none",
                                "reply_entity_name": "none",
                                "body": supplier_payload
                            }
                        )
                    except Exception as e:
                        ic(f"Failed to publish supplier outstanding update: {e}")

                delta_outstanding = new_outstanding - old_outstanding
                
                old_items_map = {}
                if existing_read_doc and "items" in existing_read_doc:
                    for itm in existing_read_doc["items"]:
                        key = (itm["product_id"], itm.get("variant_infos", {}).get("id") if itm.get("variant_infos") else None, itm.get("batch_infos", {}).get("id") if itm.get("batch_infos") else None)
                        old_items_map[key] = itm
                        
                analytics_datas = []
                for i, item in enumerate(read_items):
                    key = (item.product_id, item.variant_infos.id if item.variant_infos else None, item.batch_infos.id if item.batch_infos else None)
                    old_item = old_items_map.get(key) or {}
                    
                    old_stocks = float(old_item.get("stocks_infos", {}).get("stocks", 0.0)) if old_item.get("stocks_infos") else 0.0
                    old_amount = float(old_item.get("total_amount", 0.0))
                    
                    delta_stocks = float(item.stocks_infos.stocks) - old_stocks
                    delta_amount = float(item.total_amount) - old_amount
                    
                    item_outstanding_delta = delta_outstanding if i == 0 else 0.0
                    
                    analytics_datas.append({
                        "purchase_id": fresh_pur.id,
                        "supplier_id": supplier_id,
                        "product_id": item.product_id,
                        "variant_id": item.variant_infos.id if item.variant_infos else None,
                        "batch_id": item.batch_infos.id if item.batch_infos else None,
                        "stocks": delta_stocks,
                        "purchase_amounts": delta_amount,
                        "outstanding_amounts": item_outstanding_delta
                    })
                    
                analytics_payload = {
                    "shop_id": fresh_pur.shop_id,
                    "total_purchase": 0,
                    "datas": analytics_datas
                }
                
                await rabbitmq_msg_obj.publish_event(
                    routing_key="analytics.service.routing.key",
                    exchange_name="analytics.service.exchange",
                    payload=analytics_payload,
                    headers={
                        "entity_name": "purchase_event",
                        "service_name": "ANALYTICS",
                        "saga_id": "none",
                        "reply_key": "none",
                        "reply_exchange": "none",
                        "reply_entity_name": "none",
                        "body": analytics_payload
                    }
                )
            except Exception as e:
                ic(f"Failed to publish analytics delta event: {e}")
                
        except Exception as e:
            ic(f"Failed to update MongoDB Read DB: {e}")

        # Saga Product update emission
        if inventory_toupdate:
            routing_key = "products.service.routing.key"
            exchange_name = "products.service.exchange"
            entity_name = "update_bulk_prodinv"
            service_name = "PRODUCTS"


            saga_id:str=generate_uuid()
            steps={
                "PRODUCT_VERIFY_UPDATE":SagaStepsValueEnum.PENDING
            }

            saga_data={"purchase":data.model_dump(mode="json")}
            await SagaProducer.emit(
                saga_payload=CreateSagaStateSchema(
                    id=saga_id,
                    status=SagaStatusEnum.IN_PROGRESS,
                    type="PURCHASE_UPDATED",
                    steps=steps,
                    execution=SagaStateExecutionTypDict(
                        step="PRODUCT_VERIFY_UPDATE",
                        service=service_name
                    ),
                    data=saga_data
                ),
                routing_key=routing_key,
                exchange_name=exchange_name,
                headers={
                    "reply_key":"None",
                    "reply_exchange":"None",
                    "reply_entity_name":"None",
                    "reply_service_name":"None",
                    "service_name":service_name,
                    "entity_name":entity_name,
                    "body":inventory_toupdate

                }
            )


        try:
            from messaging.main import RabbitMQMessagingConfig
            rabbitmq_msg_obj = RabbitMQMessagingConfig()
            await rabbitmq_msg_obj.publish_event(
                routing_key="activity_logs.routing.key",
                exchange_name="activity_logs.exchange",
                payload={
                    "shop_id": data.shop_id,
                    "user_name": "Hyperlocal-User",
                    "service": "Purchase",
                    "action": "UPDATED",
                    "entity_type": "Purchase",
                    "entity_id": data.id,
                    "description": f"Updated purchase {data.id}",
                    "changes": [{"field": "id", "before": str(data.id), "after": "UPDATED"}]
                },
                headers={}
            )
        except Exception as e:
            ic(f"Failed to publish activity log: {e}")

        return True
    




    async def delete(self,data:DeletePurchaseSchema):
        final_data=DeletePurchaseDbSchema(**data.model_dump(mode="json"))
        res = await self.purchase_repo_obj.delete_purchase(data=final_data)
        
        if res:
            try:
                from messaging.main import RabbitMQMessagingConfig
                rabbitmq_msg_obj = RabbitMQMessagingConfig()
                await rabbitmq_msg_obj.publish_event(
                    routing_key="activity_logs.routing.key",
                    exchange_name="activity_logs.exchange",
                    payload={
                        "shop_id": data.shop_id,
                        "user_name": "Hyperlocal-User",
                        "service": "Purchase",
                        "action": "DELETE",
                        "entity_type": "Purchase",
                        "entity_id": data.id,
                        "description": f"Deleted purchase {data.id}",
                        "changes": [{"field": "id", "before": str(data.id), "after": "DELETED"}]
                    },
                    headers={}
                )
            except Exception as e:
                ic(f"Failed to publish activity log: {e}")

        return res


    async def get_purchases(self,data:GetAllPurchaseSchemas):
        return await self.purchase_repo_obj.get_purchases(data=data)

    async def get_purchase_by_id(self,data:GetPurchaseByIdSchema):
        return await self.purchase_repo_obj.get_purchase_by_id(data=data)
    
    async def get_purchase_by_shop_id(self,data:GetPurchaseByShopIdSchema):
        return await self.purchase_repo_obj.get_purchase_by_shop_id(data=data)
    
    async def get_history(self, purchase_id: str):
        return await self.purchase_repo_obj.get_history_by_purchase_id(purchase_id=purchase_id)
    
                    
            


        
        

            

            




        

    
    