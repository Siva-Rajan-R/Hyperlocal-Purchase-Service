from pydantic import BaseModel

class CachingBillingSchema(BaseModel):
    qty:int
    product_price:float
    product_name:str
    barcode:str
    total_price:float