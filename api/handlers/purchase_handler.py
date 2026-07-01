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
from schemas.v1.purchase_schemas.request_schema import CreatePurchaseSchema,UpdatePurchaseSchema,DeletePurchaseSchema,GetPurchaseByIdSchema,GetPurchaseByShopIdSchema,GetAllPurchaseSchemas
from messaging.saga_producer import SagaProducer,CreateSagaStateSchema,SagaStatusEnum,SagaStateExecutionTypDict
from hyperlocal_platform.core.enums.saga_state_enum import SagaStepsValueEnum
from hyperlocal_platform.core.utils.uuid_generator import generate_uuid
from hyperlocal_platform.core.utils.routingkey_builder import generate_routingkey,RoutingkeyState,RoutingkeyActions,RoutingkeyVersions

class HandlePurchaseRequest:
    def __init__(self,session:AsyncSession):
        self.session=session
        self.purchase_service_obj=PurchaseService(session=session)
        self.purchase_types=PurchaseTypeEnums._value2member_map_.values()

    async def create(self,data:CreatePurchaseSchema):
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

            if product_id not in product_serial_numbers:
                product_serial_numbers[product_id] = set()

            inc_serialnos = []
            if item.serialno_infos:
                for sn_info in item.serialno_infos:
                    if sn_info.name:
                        inc_serialnos.append(sn_info.name)

            for sn in inc_serialnos:
                if sn in product_serial_numbers[product_id]:
                    raise HTTPException(
                        status_code=400,
                        detail=ErrorResponseTypDict(
                            msg="Error : Creating Purchase",
                            status_code=400,
                            description=f"Duplicate serial number '{sn}' for the same product could not be added",
                            success=False
                        )
                    )
                product_serial_numbers[product_id].add(sn)
        
        res=await self.purchase_service_obj.create(data=data)
        ic(res)

        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                msg="Purchase Creation Request Accepted",
                status_code=202,
                success=True
            )
        )
    

    async def update(self,data:UpdatePurchaseSchema,user_id:str):
        res=await self.purchase_service_obj.update(data=data)

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
        res=await self.purchase_service_obj.get_purchases(data=data)
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
        res=await self.purchase_service_obj.get_purchase_by_shop_id(data=data)
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
        res=await self.purchase_service_obj.get_purchase_by_id(data=data)
        ic(res)
        return SuccessResponseTypDict(
            detail=BaseResponseTypDict(
                status_code=200,
                success=True,
                msg="Purchase fetched successfully"
            ),
            data=res
        )
        
