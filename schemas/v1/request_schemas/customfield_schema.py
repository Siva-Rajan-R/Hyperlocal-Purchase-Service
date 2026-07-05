from pydantic import BaseModel
from typing import Optional, List

# --- Custom Fields (Definitions) ---
class CreateCustomFieldSchema(BaseModel):
    field_name: str
    label_name: str
    type: str
    required: bool = False
    visible_online: bool = False

class UpdateCustomFieldSchema(BaseModel):
    label_name: Optional[str] = None
    type: Optional[str] = None
    required: Optional[bool] = None
    visible_online: Optional[bool] = None

# --- Custom Fields Values (Assignments) ---
class CreateCustomFieldValueSchema(BaseModel):
    purchase_id: str
    field_id: str
    value: str

class UpdateCustomFieldValueSchema(BaseModel):
    value: str

class BulkCreateCustomFieldValuesSchema(BaseModel):
    purchase_id: str
    values: List[dict] # Expected format: [{"field_id": "...", "value": "..."}]
