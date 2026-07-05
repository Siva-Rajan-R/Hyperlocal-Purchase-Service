from pydantic import BaseModel
from typing import Optional

class CreateCustomFieldDbSchema(BaseModel):
    id: str
    shop_id: str
    field_name: str
    label_name: str
    type: str
    required: bool = False
    visible_online: bool = False

class CreateCustomFieldValueDbSchema(BaseModel):
    id: str
    shop_id: str
    purchase_id: str
    field_id: str
    value: str
