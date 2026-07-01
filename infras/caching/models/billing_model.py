from schemas.v1.caching_schemas.billing_schema import CachingBillingSchema
from ..main import redis_client,RedisRepo
from typing import Optional,Dict
from icecream import ic

class BillingCacheModel:
    def __init__(self,shop_id:str,cur_user_id:str):
        self.shop_id=shop_id
        self.cur_user_id=cur_user_id
        self.cache_key=f"BILLING-CREATE-{shop_id}-{cur_user_id}"       
        
    async def set_billing_cache(self,data:CachingBillingSchema,exp:Optional[int]=10000):
        ic(data)
        cached_data=await RedisRepo.get(key=self.cache_key)
        cached_data={} if not cached_data else cached_data
        if isinstance(data,CachingBillingSchema):
            cached_data[data.barcode]=data.model_dump(mode='json') 
        else:
            cached_data=data
        return await RedisRepo.set(key=self.cache_key,value=cached_data,expire=exp)
    
    async def get_billing_cache(self)->Dict[str,dict]:
        return await RedisRepo.get(key=self.cache_key)
    
    async def delete_billing_cache(self):
        return await RedisRepo.unlink(keys=[self.cache_key]) 
    

