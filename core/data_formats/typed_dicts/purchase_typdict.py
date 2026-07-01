from typing import TypedDict,Optional,Union
from ..enums.purchase_enums import PurchaseCalcultionDividedValue
from pydantic import BaseModel

class PurchaseCalcultionsGstSchmea(BaseModel):
    include:Optional[bool]=None
    exclude:Optional[bool]=None
    registered:bool

class PurchaseCalculationsTypDict(TypedDict):
    divided_by:Union[PurchaseCalcultionDividedValue,None]
    gst:PurchaseCalcultionsGstSchmea

class PurchaseAdditionalCharges(BaseModel):
    delivery_charge:float
    other_charge:float
