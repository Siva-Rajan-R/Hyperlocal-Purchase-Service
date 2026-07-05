from ..main import RabbitMQMessagingConfig
from aio_pika import RobustConnection
from icecream import ic
from infras.primary_db.main import AsyncInventoryLocalSession
from infras.primary_db.repos.purchase_repo import PurchaseRepo
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
from infras.read_db.models.purchase_model import PurchaseReadModel, PurchaseItemReadModel, SupplierInfo, ReadVariantInfos, ReadBatchInfos, ReadStocksInfos, ReadReorderPointInfos, ReadStorageLocationInfos
from infras.primary_db.models.purchase_model import Purchase, PurchaseItems, PurchaseItemsPricing, PurchaseItemsStoragelocation, PurchaseItemsReorderPoint
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
import datetime
from integrations.utility_service import get_ui_id, get_shop_category, get_shop_unit
from typing import Optional, List, Dict, Any
import datetime
from infras.primary_db.services.customfield_service import CustomFieldsService
from schemas.v1.request_schemas.customfield_schema import CreateCustomFieldSchema,CreateCustomFieldValueSchema,BulkCreateCustomFieldValuesSchema,UpdateCustomFieldSchema,UpdateCustomFieldValueSchema




async def verify_and_update(purchase_data: dict, headers: dict, payload: dict, rabbitmq_connection: Any):
    body = []
    for item in purchase_data.get('items', []):
        stl_infos = item.get('storage_location_infos') or {}
        rop_infos = item.get('reorder_point_infos') or {}
        pricing_infos = item.get('pricing_infos') or {}
        stock_infos = item.get('stock_infos') or {}

        body.append({
            'shop_id': purchase_data['shop_id'],
            'product_id': item['product_id'],
            'variant_id': item.get('variant_id'),
            'batch_infos': item.get('batch_infos'),
            'serialno_infos': item.get('serialno_infos'),
            'storage_location': stl_infos.get('name'),
            'reorder_point': rop_infos.get('reorder_point'),
            'gst': item.get('gst'),
            'buy_price': pricing_infos.get('buy_price', 0),
            'sell_price': pricing_infos.get('sell_price', 0),
            'stocks': stock_infos.get('stocks', 0),
            'type': 'INCREMENT',
            "entity_name": 'PURCHASE',
            'create_stock_mov_adj': True
        })

    routing_key = "products.service.routing.key"
    exchange_name = "products.service.exchange"
    entity_name = "update_bulk_prodinv"
    service_name = "PRODUCTS"

    updated_headers = {
        **headers,
        "routing_key": routing_key,
        "exchange_name": exchange_name,
        "body": body,
        "entity_name": entity_name,
        "service_name": service_name 
    }

    await rabbitmq_connection.publish_event(
        routing_key=routing_key,
        exchange_name=exchange_name,
        payload=payload,
        headers=updated_headers
    )

    return {
        'success': True,
        'execution': {
            'step': "PRODUCT_VERIFY_UPDATE",
            'service': "PRODUCTS"
        }
    }


async def get_product_bulk(purchase_data: dict, headers: dict, payload: dict, rabbitmq_connection: Any):
    product_ids = [item.get('product_id') for item in purchase_data.get('items', []) if item.get('product_id')]

    routing_key = "products.service.routing.key"
    exchange_name = "products.service.exchange"
    entity_name = "get_bulk_product_by_id"
    service_name = "PRODUCTS"
    body = {
        "shop_id": purchase_data.get('shop_id'),
        "id": product_ids
    }

    updated_headers = {
        **headers,
        "routing_key": routing_key,
        "exchange_name": exchange_name,
        "entity_name": entity_name,
        "service_name": service_name,
        "body": body
    }

    await rabbitmq_connection.publish_event(
        routing_key=routing_key,
        payload=payload,
        headers=updated_headers,
        exchange_name=exchange_name
    )

    return {
        "success": True,
        "execution": {
            "step": "FETCHING_PRODUCTS",
            "service": "PRODUCTS"
        }
    }


class MessagingQueuePurchasegproducer:

    def __init__(self, headers: dict, payload: dict, saga_datas: dict):
        self.headers = headers
        self.payload = payload
        self.saga_datas = saga_datas

    async def create_purchase(self) -> dict:
        ic(self.headers, self.payload, self.saga_datas)
        rabbitmq_msg_obj = RabbitMQMessagingConfig()
        datas = self.saga_datas.get("data", {})
        purchase_data = datas.get('purchase', {})
        execution = self.saga_datas.get('execution', {})
        current_step = execution.get('step')

        # STEP-1: SUPPLIER VERIFICATION
        if current_step == "SUPPLIER_VERIFY":
            supplier_data = datas.get("suppliers")
            if not supplier_data:
                ic("The given supplier doesn't exist.")
                return {
                    "success": False,
                    "error_infos": {"msg": "The given supplier doesn't exist"},
                    "execution": None
                }
            
            return await verify_and_update(
                purchase_data=purchase_data,
                headers=self.headers,
                payload=self.payload,
                rabbitmq_connection=rabbitmq_msg_obj
            )
        
        # STEP-2: PRODUCT STRATEGY VERIFICATION
        if current_step == "PRODUCT_VERIFY_UPDATE":
            return await get_product_bulk(
                purchase_data=purchase_data,
                headers=self.headers,
                payload=self.payload,
                rabbitmq_connection=rabbitmq_msg_obj
            )
        
        # STEP-3: PARSE AND PERSIST TRANSACTION RECORD
        if current_step == "FETCHING_PRODUCTS":
            purchase_id = generate_uuid()
            
            ui_id_res = await get_ui_id(shop_id=purchase_data.get('shop_id'))
            if isinstance(ui_id_res, dict) and "prefix" in ui_id_res:
                ui_id = f"{ui_id_res.get('prefix')}-{ui_id_res.get('current_number')}"
            else:
                ui_id = f"PUR-{int(datetime.datetime.utcnow().timestamp())}"

            product_res = datas.get("products") or []
            shop_id = purchase_data.get("shop_id")
            supplier_id = purchase_data.get("supplier_id")
            pur_type = purchase_data.get("type")
            calculation_infos = purchase_data.get("calculation_infos") or {}
            charges_infos = purchase_data.get("charges_infos") or {}
            payment_infos = purchase_data.get("payment_infos") or []
            purchase_date_raw = purchase_data.get("purchase_date")
            invoice_no = purchase_data.get("invoice_no")
            gst_infos = purchase_data.get("gst_infos") or {}

            item_infos = {
                'total_pur_items': 0,
                'total_pur_stocks': 0,
                'total_pur_cost': 0,
                'total_gst_amount': 0
            }

            pur_items = purchase_data.get("items") or []
            
            validated_payload_map: Dict[str, List[dict]] = {}
            for prod in pur_items:
                p_id = prod['product_id']
                if p_id not in validated_payload_map:
                    validated_payload_map[p_id] = []
                validated_payload_map[p_id].append(prod)

            read_items = []
            pur_items_toadd = []
            pur_pricing_toadd = []
            pur_stl_toadd = []
            pur_rop_toadd = []

            async with AsyncInventoryLocalSession() as session:
                repo = PurchaseRepo(session)

                ic(product_res)
                for prod_db in product_res:
                    ic(prod_db)
                    product_id = prod_db['id']
                    product_name = prod_db['name']
                    db_ui_id = prod_db['ui_id']
                    
                    type_infos = prod_db.get('type_infos', {})
                    has_variant = type_infos.get('has_variant', False)
                    has_batch = type_infos.get('has_batch', False)
                    has_serialno = type_infos.get('has_serialno', False)
                    gst = prod_db.get('gst', '0%')

                    category_infos=prod_db.get('category_infos') or {}
                    unit_infos=prod_db.get('unit_infos') or {}

                    incoming_item_matches = validated_payload_map.get(product_id) or []
                    
                    for itm in incoming_item_matches:
                        variant_id = itm.get('variant_id')
                        batch_infos_payload = itm.get('batch_infos') or {}
                        # Match batch by ID or clean name fallback string
                        batch_target_name = batch_infos_payload.get('name')
                        batch_id = batch_infos_payload.get('id')

                        variant_name = ''
                        batch_infos = {}
                        serialno_infos = []
                        stock_infos = {}
                        stl_infos = {}
                        rop_infos = {}
                        pricing_infos = {}

                        # --- Dynamic Scope Resolution Resolution Tree ---
                        if has_variant:
                            variants_dict = prod_db.get('variants', {})
                            variant_data = variants_dict.get(variant_id) if variants_dict else None
                            
                            if variant_data:
                                variant_name = variant_data.get('name', '')
                                
                                if has_batch:
                                    batches_list = variant_data.get('batch_infos', [])
                                    for b in batches_list:
                                        if (batch_id and b.get('id') == batch_id) or (batch_target_name and b.get('name') == batch_target_name):
                                            batch_infos = b
                                            break
                                    
                                    stock_infos = batch_infos.get('stock_infos') or {}
                                    serialno_infos = batch_infos.get('serialno_infos') or [] if has_serialno else []
                                    stl_infos = batch_infos.get("storage_location_infos") or {}
                                    rop_infos = batch_infos.get("reorder_point_infos") or {}
                                    pricing_infos = batch_infos.get('pricing_infos') or {}
                                else:
                                    stock_infos = variant_data.get('stock_infos') or {}
                                    serialno_infos = variant_data.get('serialno_infos') or [] if has_serialno else []
                                    stl_infos = variant_data.get("storage_location_infos") or {}
                                    rop_infos = variant_data.get("reorder_point_infos") or {}
                                    pricing_infos = variant_data.get('pricing_infos') or {}
                        else:
                            if has_batch:
                                batches_list = prod_db.get('batch_infos', [])
                                for b in batches_list:
                                    if (batch_id and b.get('id') == batch_id) or (batch_target_name and b.get('name') == batch_target_name):
                                        batch_infos = b
                                        break
                                
                                stock_infos = batch_infos.get('stock_infos') or {}
                                serialno_infos = batch_infos.get('serialno_infos') or [] if has_serialno else []
                                stl_infos = batch_infos.get("storage_location_infos") or {}
                                rop_infos = batch_infos.get("reorder_point_infos") or {}
                                pricing_infos = batch_infos.get('pricing_infos') or {}
                            else:
                                stock_infos = prod_db.get('stock_infos') or {}
                                serialno_infos = prod_db.get('serialno_infos') or [] if has_serialno else []
                                stl_infos = prod_db.get("storage_location_infos") or {}
                                rop_infos = prod_db.get("reorder_point_infos") or {}
                                pricing_infos = prod_db.get('pricing_infos') or {}

                        # Compute Safe Inventory Delta Strategy metrics
                        stocks = float(itm.get('stock_infos', {}).get('stocks', 0))
                        current_db_physical = float(stock_infos.get('physical_stocks', 0))
                        
                        stock_before = current_db_physical - stocks
                        ic(stock_before, current_db_physical, stocks)
                        stock_after = current_db_physical

                        # Update transaction metadata
                        item_infos['total_pur_items'] += 1
                        buy_price_val = float(pricing_infos.get('buy_price', 0))
                        item_infos['total_pur_cost'] += buy_price_val
                        
                        if gst and gst.endswith('%') and gst_infos.get('type') == "EXCLUSIVE":
                            try:
                                gst_rate = float(gst[:-1]) / 100.0
                                item_infos['total_gst_amount'] += gst_rate * buy_price_val
                            except ValueError:
                                pass
                        
                        item_infos['total_pur_stocks'] += stocks

                        pur_item_id = generate_uuid()  
                        pur_items_toadd.append(PurchaseItems(
                            id=pur_item_id,
                            purchase_id=purchase_id,
                            product_id=product_id,
                            variant_id=variant_id,
                            batch_id=batch_infos.get('id', batch_id),
                            serial_numbers=[sn['name'] for sn in serialno_infos],
                            gst=gst,
                            stocks=stocks,
                            stocks_before=stock_before,
                            stocks_after=stock_after
                        ))

                        pur_pricing_toadd.append(PurchaseItemsPricing(
                            pricing_id=generate_uuid(),
                            purchase_id=purchase_id,
                            purchase_item_id=pur_item_id,
                            buy_price=buy_price_val,
                            sell_price=float(pricing_infos.get('sell_price', 0))
                        ))
                        
                        if itm.get('storage_location_infos', {}).get('name') or stl_infos.get('storage_location'):
                            pur_stl_toadd.append(PurchaseItemsStoragelocation(
                                storage_location_id=generate_uuid(),
                                purchase_id=purchase_id,
                                purchase_item_id=pur_item_id,
                                name=itm.get('storage_location_infos', {}).get('name') or stl_infos.get('storage_location')
                            ))
                            
                        if itm.get('reorder_point_infos', {}).get('reorder_point') or rop_infos.get('reorder_point'):
                            pur_rop_toadd.append(PurchaseItemsReorderPoint(
                                reorder_point_id=generate_uuid(),
                                purchase_id=purchase_id,
                                purchase_item_id=pur_item_id,
                                reorder_point=float(itm.get('reorder_point_infos', {}).get('reorder_point') or rop_infos.get('reorder_point', 0))
                            ))

                        variant_infos_model = ReadVariantInfos(id=variant_id, name=variant_name) if variant_id else None
                        batch_infos_model = ReadBatchInfos(id=batch_infos.get('id', batch_id), name=batch_infos.get('name', ''),mfg_date=batch_infos.get('manufacturing_date'),exp_date=batch_infos.get('expiry_date')) if (batch_id or batch_infos_payload.get('name')) else None
                        stock_infos_model = ReadStocksInfos(stocks=stocks, stocks_before=stock_before, stocks_after=stock_after)
                        
                        reorder_point_model = ReadReorderPointInfos(
                            id=rop_infos.get('id'), reorder_point=float(rop_infos.get('reorder_point', 0))
                        ) if rop_infos else None
                        
                        storage_location_model = ReadStorageLocationInfos(
                            id=stl_infos.get('id'), name=stl_infos.get('storage_location', '')
                        ) if stl_infos else None

                        read_items.append(
                            PurchaseItemReadModel(
                                id=pur_item_id,
                                product_id=product_id,
                                ui_id=db_ui_id,
                                name=product_name,
                                category_infos=category_infos,
                                unit_infos=unit_infos,
                                variant_infos=variant_infos_model,
                                batch_infos=batch_infos_model,
                                stocks_infos=stock_infos_model,
                                reorder_point_infos=reorder_point_model,
                                storage_location_infos=storage_location_model,
                                serial_numbers=[sn.get('name', sn) if isinstance(sn, dict) else sn for sn in (itm.get('serialno_infos') or serialno_infos)],
                                sell_price=float(pricing_infos.get('sell_price', 0)),
                                buy_price=buy_price_val,
                                total_amount=buy_price_val * stocks,
                                gst=gst
                            )
                        )

                purchase_date = purchase_date_raw
                if isinstance(purchase_date, str):
                    purchase_date = datetime.datetime.strptime(purchase_date, "%Y-%m-%d").date()

                purchase_model = Purchase(
                    id=purchase_id,
                    ui_id=ui_id,
                    shop_id=shop_id,
                    supplier_id=supplier_id,
                    invoice_no=invoice_no,
                    type=pur_type,
                    purchase_view=True,
                    calculation_infos=calculation_infos,
                    charges_infos=charges_infos,
                    item_infos=item_infos, 
                    payment_infos=payment_infos,
                    date=purchase_date
                )

                await repo.create_bulk_purchase([purchase_model])
                if pur_items_toadd:
                    await repo.create_bulk_items(data=pur_items_toadd)
                if pur_pricing_toadd:
                    await repo.create_bulk_pricing(data=pur_pricing_toadd)
                if pur_rop_toadd:
                    await repo.create_bulk_rop(data=pur_rop_toadd)
                if pur_stl_toadd:
                    await repo.create_bulk_stl(data=pur_stl_toadd)

                if purchase_data.get("custom_fields") and purchase_data.get("custom_fields").get("values"):
                    await CustomFieldsService(session=session).bulk_upsert_values(
                        shop_id=shop_id,
                        data=BulkCreateCustomFieldValuesSchema(
                            purchase_id=purchase_id,
                            values=purchase_data.get("custom_fields").get("values")

                        )
                    )

                total_amount_paid = sum(float(payment.get('amount', 0)) for payment in payment_infos)
                total_pur_cost = float(item_infos['total_pur_cost'] + item_infos['total_gst_amount'])
                outstanding_amount = abs(total_pur_cost - total_amount_paid)

                if outstanding_amount == 0:
                    outstanding_status = "COMPLETED"
                elif total_amount_paid == 0:
                    outstanding_status = "NOT-PAID"
                else:
                    outstanding_status = "PARTIALY-PAID"

                supplier_name_val = datas.get("suppliers", {}).get("name", "")
                supplier_info = SupplierInfo(supplier_id=supplier_id, supplier_name=supplier_name_val)
                
                cf_dict = {}
                cf_data = purchase_data.get("custom_fields", {})
                if cf_data and cf_data.get("values"):
                    for v in cf_data.get("values"):
                        if "field_name" in v and "value" in v:
                            cf_dict[v["field_name"]] = v["value"]

                purchase_read_model = PurchaseReadModel(
                    purchase_id=purchase_id,
                    ui_id=ui_id,
                    invoice_no=invoice_no,
                    shop_id=shop_id,
                    purchase_date=purchase_date,
                    supplier=supplier_info,
                    total_cost=total_pur_cost,
                    total_items=item_infos['total_pur_items'],
                    total_quantity=item_infos['total_pur_stocks'],
                    payment_infos=payment_infos,
                    charges_infos=charges_infos,
                    gst_infos=gst_infos,
                    payment_status=outstanding_status,
                    outstanding_amount=outstanding_amount,
                    calculations=calculation_infos,
                    custom_fields=cf_dict,
                    items=read_items,
                )
                
                await PurchaseReadDbRepo.add_updatereaddb(purchase_read_model)

                if outstanding_status != "COMPLETED":
                    supplier_payload = {
                        "shop_id": purchase_data.get('shop_id'),
                        "id": purchase_data.get("supplier_id"),
                        "outstanding_infos": {"amount": outstanding_amount},
                        "type": "INCREMENT"
                    }
                    await rabbitmq_msg_obj.publish_event(
                        routing_key="suppliers.service.routing.key",
                        exchange_name="suppliers.service.exchange",
                        payload=supplier_payload,
                        headers={
                            **self.headers.copy(),
                            "body": supplier_payload,
                            "entity_name": "update_supllier_outstanding",
                            "service_name": "SUPPLIERS"
                        }
                    )

            return {
                "success": True,
                "execution": {
                    "step": "SUCCESS",
                    "service": "PURCHASE"
                }
            }

        if current_step == "SUCCESS":
            ic("Successfully completed the purchase cycle context workflow.")
            return {
                "success": True,
                "execution": None
            }

        return {
            "success": False,
            "error_infos": {"msg": f"Unhandled step context executed: {current_step}"},
            "execution": None
        }