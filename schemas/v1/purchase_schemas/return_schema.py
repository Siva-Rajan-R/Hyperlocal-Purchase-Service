from pydantic import BaseModel
from typing import Optional, List, Any, Dict

class ReturnSerialnoInfoSchema(BaseModel):
    id: str

class ReturnItemRequestSchema(BaseModel):
    purchase_item_id: str
    quantity: float
    unit: Optional[str] = None
    reason: Optional[str] = None
    serialno_infos: Optional[List[ReturnSerialnoInfoSchema]] = None

class CreatePurchaseReturnSchema(BaseModel):
    purchase_id: str
    shop_id: Optional[str] = None
    payment_infos: Dict[str, Any]
    items: List[ReturnItemRequestSchema]
