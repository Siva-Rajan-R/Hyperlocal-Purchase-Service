from fastapi import HTTPException
from .field_type_convertor import convert_field_type
from integrations.field_service import get_fields
from icecream import ic
from hyperlocal_platform.core.models.req_res_models import SuccessResponseTypDict,ErrorResponseTypDict,BaseResponseTypDict




async def validate_fields(service_name:str,shop_id:str,incoming_fields:dict):
    fields=await get_fields(service_name=service_name,shop_id=shop_id)
    check_list={}
    ic(fields)
    for key,value in fields.items():
        is_exists=incoming_fields.get(key,None)
        if value['required']==True and is_exists is None:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Creating Shop",
                    description="Invalid Fields",
                    success=False,
                    status_code=400
                )
            )
        
        ic(convert_field_type(field_type=value['type']),type(is_exists))

        if is_exists is None:
            continue

        if convert_field_type(field_type=value['type'])!=type(is_exists):
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Creating Shop",
                    description="Invalid data type",
                    success=False,
                    status_code=400
                )
            )
        
        if value['type']=="DROP DOWN":
            if is_exists not in value['dd_values']:
                raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    msg="Error : Creating Shop",
                    description=f"The value should be {value['dd_values']}",
                    success=False,
                    status_code=400
                )
            )
        
        check_list[key]=key

    if len(check_list)!=len(incoming_fields):
        raise HTTPException(
            status_code=400,
            detail=ErrorResponseTypDict(
                msg="Error : Creating Shop",
                description="Please enter a valid fields",
                success=False,
                status_code=400
            )
        )
    
    return True