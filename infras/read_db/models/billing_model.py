from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class BillingProductReadModel(BaseModel):
    inventory_id: str
    variant_id: Optional[str] = None
    batch_id: Optional[str] = None
    serialno_id: Optional[str] = None
    barcode: Optional[str] = None
    inv_serial_numbers: Optional[List[str]] = []
    buy_price: float
    sell_price: float
    gst: str
    quantity: float

class BillingReadModel(BaseModel):
    id: str
    shop_id: str
    customer_id: Optional[str] = None
    status: str
    origin: str
    payments: dict
    items: List[BillingProductReadModel]
    total_amount: float
    created_at: datetime
    updated_at: datetime
    datas: Optional[Dict[str, Any]] = None

class BillingStatsReadModel(BaseModel):
    shop_id: str
    total_orders: int = 0
    total_order_value: float = 0.0
    walk_in_customers_count: int = 0
    registered_customers_count: int = 0
    outstanding_amount: float = 0.0
