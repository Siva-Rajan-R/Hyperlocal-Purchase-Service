from pydantic import BaseModel
from typing import Optional, List


class CustomFieldInfos(BaseModel):
    field_name: str
    label_name: str
    type: str
    required: bool = False
    visible_online: bool = False

    
# --- Custom Fields (Definitions) ---
class CreateCustomFieldSchema(BaseModel):
    shop_id: str
    field_infos:List[CustomFieldInfos]
    

class UpdateCustomFieldSchema(BaseModel):
    field_id:str
    shop_id: str
    label_name: Optional[str] = None
    type: Optional[str] = None
    required: Optional[bool] = None
    visible_online: Optional[bool] = None


class DeleteCustomFieldSchema(BaseModel):
    id:str
    shop_id:str



class GetFieldByShopIdSchema(BaseModel):
    shop_id:str

class GetFieldById(BaseModel):
    id:str
    shop_id:str

class GetFieldByName(BaseModel):
    name:str
    shop_id:str

class CustomFieldValueInfos(BaseModel):
    field_id:str
    value:str

# --- Custom Fields Values (Assignments) ---
class CreateCustomFieldValueSchema(BaseModel):
    shop_id: str
    purchase_id: str
    value_infos:List[CustomFieldValueInfos]

class UpdateCustomFieldValueSchema(BaseModel):
    value: str

class GetValueByIdName(BaseModel):
    id:Optional[str]=None
    name:Optional[str]=None
    shop_id:str

class GetvaluesByCustomerId(BaseModel):
    id:str
    shop_id:str

class BulkCreateCustomFieldValuesSchema(BaseModel):
    shop_id: str
    purchase_id: str
    values: List[dict] # Expected format: [{"field_id": "...", "value": "..."}]
