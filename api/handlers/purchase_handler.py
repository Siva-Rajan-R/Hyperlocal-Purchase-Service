from infras.primary_db.services.purchase_service import PurchaseService
from typing import Optional,List
from sqlalchemy.ext.asyncio import AsyncSession
from hyperlocal_platform.core.enums.timezone_enum import TimeZoneEnum
from hyperlocal_platform.core.models.req_res_models import SuccessResponseTypDict,ErrorResponseTypDict,BaseResponseTypDict
from core.data_formats.enums.purchase_enums import PurchaseTypeEnums,PurchaseViewsEnums
from icecream import ic
from fastapi.exceptions import HTTPException
from core.utils.validate_fields import convert_field_type,validate_fields
from infras.caching.models.purchase_model import PurchaseProductCacheModel,PurchaseProductCachingSchema,PurchaseSupplierCacheModel,PurchaseSupplierCachingSchema
from schemas.v1.purchase_schemas.request_schema import CreatePurchaseSchema,UpdatePurchaseSchema,DeletePurchaseSchema,GetPurchaseByIdSchema,GetPurchaseByShopIdSchema,GetAllPurchaseSchemas,GetPurchaseByProductIdSchema,GetPurchaseBySupplierIdSchema
from messaging.saga_producer import SagaProducer,CreateSagaStateSchema,SagaStatusEnum,SagaStateExecutionTypDict
from hyperlocal_platform.core.enums.saga_state_enum import SagaStepsValueEnum
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from hyperlocal_platform.core.utils.routingkey_builder import generate_routingkey,RoutingkeyState,RoutingkeyActions,RoutingkeyVersions
from infras.read_db.repos.purchase_repo import PurchaseReadDbRepo
from infras.primary_db.services.customfield_service import CustomFieldsService,GetFieldById,GetFieldByName,GetvaluesByCustomerId,GetFieldByShopIdSchema
from core.utils.validate_custom_fields import validate_and_filter_custom_fields
from schemas.v1.request_schemas.customfield_schema import BulkCreateCustomFieldValuesSchema


class HandlePurchaseRequest:
    def __init__(self,session:AsyncSession):
        self.session=session
        self.purchase_service_obj=PurchaseService(session=session)
        self.purchase_types=PurchaseTypeEnums._value2member_map_.values()

    async def create(self,data:CreatePurchaseSchema, executing_user_id: Optional[str] = None):
        if data.type.value!=PurchaseTypeEnums.DIRECT.value:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Creating Purchase",
                    status_code=400,
                    description=f"Invalid types, type should be direct",
                    success=False
                )
            )

        validated_data = {}
        product_serial_numbers = {}

        for item in data.items:
            product_id = item.product_id
            
            if product_id not in validated_data:
                validated_data[product_id] = []
            else:
                validated_data_info = validated_data[product_id]
                inc_variant_id = item.variant_id
                inc_batch_id = item.batch_infos.id if item.batch_infos else None

                for inside_data in validated_data_info:
                    v_variant_id = inside_data.variant_id
                    v_batch_id = inside_data.batch_infos.id if inside_data.batch_infos else None

                    if v_variant_id == inc_variant_id and v_batch_id == inc_batch_id:
                        raise HTTPException(
                            status_code=400,
                            detail=ErrorResponseTypDict(
                                msg="Error : Creating Purchase",
                                status_code=400,
                                description=f"Duplicate product with same variant or batch id could not be added",
                                success=False
                            )
                        )
            
            validated_data[product_id].append(item)

            product_variant_key = f"{product_id}_{item.variant_id}"
            if product_variant_key not in product_serial_numbers:
                product_serial_numbers[product_variant_key] = set()

            inc_serialnos = []
            if item.serialno_numbers:
                for sn_info in item.serialno_numbers:
                    inc_serialnos.append(sn_info)

            for sn in inc_serialnos:
                if sn in product_serial_numbers[product_variant_key]:
                    raise HTTPException(
                        status_code=400,
                        detail=ErrorResponseTypDict(
                            msg="Error : Creating Purchase",
                            status_code=400,
                            description=f"Duplicate serial number '{sn}' for the same product variant could not be added",
                            success=False
                        )
                    )
                product_serial_numbers[product_variant_key].add(sn)
        
        # for checking the custome fields
        defined_fields = await CustomFieldsService(session=self.session).get_field_by_shop_id(data=GetFieldByShopIdSchema(shop_id=data.shop_id))
        valid_custom_fields = validate_and_filter_custom_fields(payload_custom_fields=data.custom_fields, defined_custom_fields=defined_fields)
        ic(valid_custom_fields)

        data_toadd=CreatePurchaseSchema(custom_fields=valid_custom_fields,**data.model_dump(exclude=['custom_fields']))
        
        res = await self.purchase_service_obj.create(data=data_toadd, executing_user_id=executing_user_id)
        ic(res)

        if res:
            return SuccessResponseTypDict(
                detail=BaseResponseTypDict(
                    msg="Purchase Creation Request Accepted",
                    status_code=202,
                    success=True
                )
            )
        
        raise HTTPException(
            status_code=400,
            detail=ErrorResponseTypDict(
                msg="Error : Creating Purchase",
                status_code=400,
                description=f"Invalid data types or Invoive no already exists",
                success=False
            )
        )
    

    async def update(self,data:UpdatePurchaseSchema,user_id:str):
        defined_fields = await CustomFieldsService(session=self.session).get_field_by_shop_id(data=GetFieldByShopIdSchema(shop_id=data.shop_id))
        valid_custom_fields = validate_and_filter_custom_fields(data.custom_fields, defined_fields)
        
        final_data = UpdatePurchaseSchema(custom_fields=valid_custom_fields,**data.model_dump(exclude=['custom_fields']))
        res = await self.purchase_service_obj.update(data=final_data)

        if res:
             return SuccessResponseTypDict(
                 detail=BaseResponseTypDict(
                     msg="Purchase updated successfully",
                     status_code=200,
                     success=True
                 )
             )
        
        raise HTTPException(
            status_code=400,
            detail=ErrorResponseTypDict(
                msg="Error : Updating Purchase",
                status_code=400,
                description=f"Invalid data types",
                success=False
            )
        )
    

    async def delete(self,data:DeletePurchaseSchema):
        res=await self.purchase_service_obj.delete(data=data)

        if res:
            return SuccessResponseTypDict(
                detail=BaseResponseTypDict(
                    msg="Purchase deleted successfully",
                    status_code=200,
                    success=True
                )
            )
        
        raise HTTPException(
            status_code=400,
            detail=ErrorResponseTypDict(
                msg="Error : Deleting Purchase",
                status_code=400,
                description=f"Invalid data types",
                success=False
            )
        )
    

    async def get_purchases(self,data:GetAllPurchaseSchemas):
        # res=await self.purchase_service_obj.get_purchases(data=data)
        res=await PurchaseReadDbRepo.get_all(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Purchase fetched successfully"
            ),
            data=res
        )
    
    async def get_purchases_by_shop_id(self,data:GetPurchaseByShopIdSchema):
        # res=await self.purchase_service_obj.get_purchase_by_shop_id(data=data)
        res=await PurchaseReadDbRepo.get_by_shop_id(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Purchase fetched successfully"
            ),
            data=res
        )
    async def get_purchase_by_id(self,data:GetPurchaseByIdSchema):
        # res=await self.purchase_service_obj.get_purchase_by_id(data=data)
        res=await PurchaseReadDbRepo.get_by_id(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Purchase fetched successfully"
            ),
            data=res
        )

    async def get_purchases_by_product_id(self,data:GetPurchaseByProductIdSchema):
        res=await PurchaseReadDbRepo.get_by_product_id(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Purchase fetched successfully"
            ),
            data=res
        )

    async def get_purchases_by_supplier_id(self,data:GetPurchaseBySupplierIdSchema):
        res=await PurchaseReadDbRepo.get_by_supplier_id(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Purchase fetched successfully"
            ),
            data=res
        )

    async def get_purchase_history(self, shop_id: str, id: str):
        # Try MongoDB first
        doc = await PurchaseReadDbRepo.get_by_id(GetPurchaseByIdSchema(id=id, shop_id=shop_id))
        if doc and doc.get("history"):
            return SuccessResponseTypDict(
                detail=BaseResponseTypDict(
                    status_code=200,
                    success=True,
                    msg="Purchase history fetched successfully"
                ),
                data=doc["history"]
            )
        
        # Fallback to PostgreSQL
        res = await self.purchase_service_obj.get_history(purchase_id=id)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Purchase history fetched successfully"
            ),
            data=res
        )
        
