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



async def verify_and_update(purchase_data: dict,headers: dict,payload: dict,rabbitmq_connection:RabbitMQMessagingConfig):
    body=[]

    for item in purchase_data.get('items', []):
        body.append(
            {
                'shop_id':purchase_data['shop_id'],
                'product_id':item['product_id'],
                'variant_id':item['variant_id'],
                'batch_infos':item['batch_infos'],
                'serialno_infos':item['serialno_infos'],
                'storage_location':item['storage_location_infos']['name'] if item['storage_location_infos'] else None,
                'reorder_point':item['reorder_point_infos']['reorder_point'] if item['reorder_point_infos'] else None,
                'gst':item['gst'],
                'buy_price':item['pricing_infos']['buy_price'],
                'sell_price':item['pricing_infos']['sell_price'],
                'stocks':item['stock_infos']['stocks'],
                'type':'INCREMENT',
                "entity_name":'PURCHASE',
                'create_stock_mov_adj':True
            }
        )

    routing_key="products.service.routing.key"
    exchange_name="products.service.exchange"
    entity_name="update_bulk_prodinv"
    service_name="PRODUCTS"
    payload={
        **payload
    }

    headers={
        **headers,
        "routing_key":routing_key,
        "exchange_name":exchange_name,
        "body":body,
        "entity_name":entity_name,
        "service_name":service_name 
    }

    ic(rabbitmq_connection)
    await rabbitmq_connection.publish_event(
        routing_key=routing_key,
        exchange_name=exchange_name,
        payload=payload,
        headers=headers
    )

    return {
        'success':True,
        'execution':{
            'step':"PRODUCT_VERIFY_UPDATE",
            'service':"PRODUCTS"
        }
    }


async def get_product_bulk(purchase_data: dict,headers: dict,payload: dict,rabbitmq_connection:RabbitMQMessagingConfig):
    product_ids=[]

    for item in purchase_data.get('items', []):
        product_ids.append(item.get('product_id'))

    routing_key="products.service.routing.key"
    exchange_name="products.service.exchange"
    entity_name="get_bulk_product_by_id"
    service_name="PRODUCTS"
    body={
        "shop_id":purchase_data.get('shop_id'),
        "id":product_ids
    }
                

    headers={
        **headers,
        "routing_key":routing_key,
        "exchange_name":exchange_name,
        "entity_name":entity_name,
        "service_name":service_name,
        "body":body
    }
    payload={
        **payload
    }

    await rabbitmq_connection.publish_event(
        routing_key=routing_key,
        payload=payload,
        headers=headers,
        exchange_name=exchange_name
    )

    return {
        "success":True,
        "execution":{
            "step":"FETCHING_PRODUCTS",
            "service":"PRODUCTS"
        }
    }


class MessagingQueuePurchasegproducer:

    def __init__(self,headers:dict,payload:dict,saga_datas:dict):
        self.headers=headers
        self.payload=payload
        self.saga_datas=saga_datas


    async def create_purchase(self):
        ic(self.headers,self.payload,self.saga_datas)
        rabbitmq_msg_obj=RabbitMQMessagingConfig()
        datas=self.saga_datas["data"]
        purchase_data=datas.get('purchase', {})
        execution=self.saga_datas.get('execution', {})
        current_step=execution.get('step')

        ic(execution,current_step,purchase_data)


        # STEP-1 VERIFY SUPPLIER
        if current_step=="SUPPLIER_VERIFY":
            supplier_data=datas.get("suppliers",None)
            if not supplier_data:
                ic("The given supplier doesn't exists")
                return {
                    "success":False,
                    "error_infos":{"msg":"The given supplier doesn't exists"},
                    "execution":None
                }
            
            # STEP-2 EMITTING EVENT TO VERIFY PRODUCT
            return await verify_and_update(
                purchase_data=purchase_data,
                headers=self.headers,
                payload=self.payload,
                rabbitmq_connection=rabbitmq_msg_obj
            )
        
        # STEP-3 VERIFICATION OF THE PRODUCT
        if current_step=="PRODUCT_VERIFY_UPDATE":
            ic("current step is product verify")
            ic("finished")
            return await get_product_bulk(
                purchase_data=purchase_data,
                headers=self.headers,
                payload=self.payload,
                rabbitmq_connection=rabbitmq_msg_obj
            )
        

        if current_step=="FETCHING_PRODUCTS":

            purchase_id = generate_uuid()
            ui_id_res = await get_ui_id(shop_id=purchase_data.get('shop_id'))
            ui_id=f"{ui_id_res.get("prefix")}-{ui_id_res.get("current_number")}"

            product_res=datas.get("products")

            shop_id=purchase_data.get("shop_id")

            supplier_id=purchase_data.get("supplier_id")
            pur_type=purchase_data.get("type")
            calculation_infos=purchase_data.get("calculation_infos")
            charges_infos=purchase_data.get("charges_infos")
            payment_infos=purchase_data.get("payment_infos")
            purchase_date=purchase_data.get("purchase_date")
            invoice_no=purchase_data.get("invoice_no")
            gst_infos=purchase_data.get("gst_infos")
            item_infos={
                'total_pur_items':0,
                'total_pur_stocks':0,
                'total_pur_cost':0,
                'total_gst_amount':0
            }

            pur_items=purchase_data.get("items")
            
            # 1. Primary DB Insert
            async with AsyncInventoryLocalSession() as session:
                repo = PurchaseRepo(session)

                validated_data={}
                for prod in pur_items:
                    ic(prod)
                    product_id=prod['product_id']
                    if product_id not in validated_data:
                        validated_data[product_id]=[]
                    
                    validated_data[product_id].append(prod)
                ic(validated_data)

                

                read_items = []

                for prod in product_res:
                    ic(prod)
                    product_id=prod['id']
                    product_name=prod['name']
                    ui_id=prod['ui_id']
                    has_variant=prod['type_infos']['has_variant']
                    has_batch=prod['type_infos']['has_batch']
                    has_serialno=prod['type_infos']['has_serialno']
                    variant_id=None
                    batch_id=None
                    variant_name=''
                    batch_infos={}
                    serialno_infos=[]
                    stock_infos={}
                    stl_infos={}
                    rop_infos={}
                    gst=prod['gst']

                    category_id = prod.get('category_id')
                    unit_id = prod.get('unit_id')
                    category_name = ""
                    unit_name = ""
                    if category_id:
                        cat_res = await get_shop_category(shop_id=shop_id, category_id=category_id)
                        category_name = cat_res.get("name", "") if isinstance(cat_res, dict) else ""
                    if unit_id:
                        unit_res = await get_shop_unit(shop_id=shop_id, unit_id=unit_id)
                        unit_name = unit_res.get("name", "") if isinstance(unit_res, dict) else ""

                    stock_before=0
                    stock_after=0
                    stocks=0

                    pur_items_toadd=[]
                    pur_pricing_toadd=[]
                    pur_stl_toadd=[]
                    pur_rop_toadd=[]


                    datas=validated_data.get(product_id)
                    for itm in datas:
                        ic(itm)
                        batch_infos=itm['batch_infos']
                        batch_id=itm['batch_id'] if batch_infos else None
                        variant_id=itm['variant_id']
                        if has_variant:
                            if variant_id in prod['variants']:
                                stock_infos=prod['variants'][variant_id].get("stock_infos",{})
                        
                                variant_name=prod['variants']['name']
                                if has_batch and not has_serialno:
                                    batch_infos=prod['variants'][variant_id]['batch_infos'].get("batch_id",{})
                                    stock_infos=batch_infos['stock_infos']
                                
                                if has_serialno and not has_batch:
                                    serialno_infos=prod['variants'][variant_id].get('serialno_infos',{})

                                if has_serialno and has_batch:
                                    batch_infos=prod['variants'][variant_id]['batch_infos'].get("batch_id",{})
                                    stock_infos=batch_infos['stock_infos']
                                    serialno_infos=batch_infos['serialno_infos']
                                
                                stl_infos=prod['variants'][variant_id].get("storage_location_infos",{})
                                rop_infos=prod['variants'][variant_id].get("reorder_point_infos",{})
                                pricing_infos=prod['variants'][variant_id]['pricing_infos']


                                stocks=itm['stock_infos']['stocks']
                                stock_before=stock_infos['physical_stocks']-stocks
                                stock_after=stock_infos['physical_stocks']



                        else:

                            stock_infos=stock_infos=prod.get("stock_infos",{})
                            ic(stock_infos)

                            if has_batch and not serialno_infos:
                                batch_infos=prod['batch_infos'][batch_id]
                                stock_infos=batch_infos['stock_infos']
                            
                            if has_serialno and not has_batch:
                                serialno_infos=prod['serialno_infos']
                            
                            if has_serialno and has_batch:
                                batch_infos=prod['batch_infos'][batch_id]
                                stock_infos=batch_infos['stock_infos']
                                serialno_infos=batch_infos['serialno_infos']

                            stocks=itm['stock_infos']['stocks']
                            ic(stocks)
                            stock_before=stock_infos['physical_stocks']-stocks
                            stock_after=stock_infos['physical_stocks']

                            stl_infos=prod.get("storage_location_infos",{})
                            rop_infos=prod.get("reorder_point_infos",{})
                            pricing_infos=prod['pricing_infos']

                            ic(stl_infos,rop_infos,pricing_infos)


                            item_infos['total_pur_items']+=1
                            item_infos['total_pur_cost']+=pricing_infos['buy_price']
                            item_infos['total_gst_amount']+=(int(gst[:-1])/100)*pricing_infos['buy_price'] if gst_infos['type']=="EXCLUSIVE" else 0
                            item_infos['total_pur_stocks']+=stocks


                        pur_item_id=generate_uuid()  
                        pur_items_toadd.append(PurchaseItems(
                            id=pur_item_id,
                            purchase_id=purchase_id,
                            product_id=product_id,
                            variant_id=variant_id,
                            batch_id=batch_id,
                            serial_numbers=serialno_infos,
                            gst=gst,
                            stocks=stocks,
                            stocks_before=stock_before,
                            stocks_after=stock_after
                        ))

                        pricing_id = generate_uuid()
                        pur_pricing_toadd.append(PurchaseItemsPricing(
                            pricing_id=pricing_id,
                            purchase_id=purchase_id,
                            purchase_item_id=pur_item_id,
                            buy_price=pricing_infos['buy_price'],
                            sell_price=pricing_infos['sell_price']
                        ))
                        
                        if stl_infos:
                            pur_stl_toadd.append(PurchaseItemsStoragelocation(
                                storage_location_id=generate_uuid(),
                                purchase_id=purchase_id,
                                purchase_item_id=pur_item_id,
                                name=stl_infos['storage_location']
                            ))
                            
                        if rop_infos:
                            pur_rop_toadd.append(PurchaseItemsReorderPoint(
                                reorder_point_id=generate_uuid(),
                                purchase_id=purchase_id,
                                purchase_item_id=pur_item_id,
                                reorder_point=rop_infos['reorder_point']
                            ))

                        variant_infos_model = ReadVariantInfos(id=variant_id, name=variant_name) if variant_id else None
                        batch_infos_model = ReadBatchInfos(id=batch_id, name=batch_infos.get('name', '') if isinstance(batch_infos, dict) else str(batch_infos)) if batch_id else None
                        
                        stock_infos_model = ReadStocksInfos(
                            stocks=stocks,
                            stocks_before=stock_before,
                            stocks_after=stock_after
                        )
                        
                        reorder_point_model = ReadReorderPointInfos(
                            id=rop_infos.get('id'), reorder_point=rop_infos.get('reorder_point', 0)
                        ) if rop_infos else None
                        
                        storage_location_model = ReadStorageLocationInfos(
                            id=stl_infos.get('id'), name=stl_infos.get('storage_location', '')
                        ) if stl_infos else None

                        read_items.append(
                            PurchaseItemReadModel(
                                id=pur_item_id,
                                product_id=product_id,
                                ui_id=ui_id,
                                name=product_name,
                                category_name=category_name,
                                unit_name=unit_name,
                                variant_infos=variant_infos_model,
                                batch_infos=batch_infos_model,
                                stocks_infos=stock_infos_model,
                                reorder_point_infos=reorder_point_model,
                                storage_location_infos=storage_location_model,
                                serial_numbers=[sn.get('id', sn) if isinstance(sn, dict) else sn for sn in serialno_infos] if serialno_infos else [],
                                sell_price=pricing_infos.get('sell_price', 0),
                                buy_price=pricing_infos.get('buy_price', 0),
                                total_amount=pricing_infos.get('buy_price', 0) * stocks,
                                gst=gst
                            )
                        )


                ic(purchase_date)
                if isinstance(purchase_date, str):
                    purchase_date = datetime.datetime.strptime(
                        purchase_date,
                        "%Y-%m-%d"
                    ).date()
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

                await repo.create_bulk_items(data=pur_items_toadd)
                await repo.create_bulk_pricing(data=pur_pricing_toadd)
                await repo.create_bulk_rop(data=pur_rop_toadd)
                await repo.create_bulk_stl(data=pur_stl_toadd)


                
                total_amount_paid=0
                ic(total_amount_paid)
                total_pur_cost=item_infos['total_pur_cost']+item_infos['total_gst_amount']
                ic(total_amount_paid,total_pur_cost,payment_infos)
                for payment in payment_infos:
                    ic(payment)
                    total_amount_paid+=payment['amount']

                ic(total_amount_paid,total_pur_cost)
                outstanding_amount=abs(total_pur_cost-total_amount_paid)

                outstanding_status="COMPLETED"
                if outstanding_amount==total_pur_cost:
                    outstanding_status="NOT-PAID"
                else:
                    outstanding_status="PARTIALY-PAID"

                supplier_info = SupplierInfo(supplier_id=supplier_id, supplier_name=self.saga_datas["data"].get("suppliers", {}).get("name", ""))
                
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
                    paid_amount=total_amount_paid,
                    payment_status=outstanding_status,
                    calculations=calculation_infos or {},
                    items=read_items
                )
                
                await PurchaseReadDbRepo.add_updatereaddb(purchase_read_model)

                ic(outstanding_status)
                if outstanding_status!="COMPLETED":
                    rabbitmq_msg_obj = RabbitMQMessagingConfig()
                    await rabbitmq_msg_obj.publish_event(
                        routing_key="suppliers.service.routing.key",
                        exchange_name="suppliers.service.exchange",
                        payload={
                            "shop_id": purchase_data.get('shop_id'),
                            "id":purchase_data.get("supplier_id"),
                            "outstanding_infos":{"amount":outstanding_amount},
                            "type":"INCREMENT",
                        },
                        headers={
                            **self.headers.copy(),
                            "body":{
                                "shop_id": purchase_data.get('shop_id'),
                                "id":purchase_data.get("supplier_id"),
                                "outstanding_infos":{"amount":outstanding_amount},
                                "type":"INCREMENT"
                            },
                            "entity_name":"update_supllier_outstanding",
                            "service_name":"SUPPLIERS"
                        }
                    )

            return {
                "success": True,
                "execution": {
                    "step":"SUCCESS",
                    "service":"PURCHASE"
                }
            }



        if current_step=="SUCCESS":
            ic("Successfully Completed the purchase")
            return {
                "success": True,
                "execution": None
            }
