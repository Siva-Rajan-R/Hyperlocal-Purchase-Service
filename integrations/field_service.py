import httpx
from icecream import ic


BAASE_URL="http://127.0.0.1:8000"
async def get_fields(service_name:str,shop_id:str):
    async with httpx.AsyncClient() as request:
        base_fields_req=await request.get(f"{BAASE_URL}/fields/base/by/s-name/{service_name}")
        custom_fields_req=await request.get(f"{BAASE_URL}/fields/custom/by/s-name/{service_name}")
        combined_fields={}
        if base_fields_req.status_code==200 and custom_fields_req.status_code==200:
            
            base_fields_datas=base_fields_req.json()['data']
            custom_fields_datas=custom_fields_req.json()['data']

            if base_fields_datas is None:
                base_fields_datas={}
            if custom_fields_datas is None:
                custom_fields_datas={}


            combined_fields={**base_fields_datas.get('fields',{}),**custom_fields_datas.get('fields',{})}
        
        ic(base_fields_datas)
        ic(custom_fields_datas)
        ic(combined_fields)

        return combined_fields

