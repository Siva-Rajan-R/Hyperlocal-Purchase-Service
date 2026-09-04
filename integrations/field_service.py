import os
import httpx
from icecream import ic
from dotenv import load_dotenv
load_dotenv()

BAASE_URL = os.getenv("UTILITY_SERVICE_URL", "http://127.0.0.1:8000")

async def get_fields(service_name: str, shop_id: str):
    try:
        async with httpx.AsyncClient(timeout=10.0) as request:
            base_fields_req = await request.get(f"{BAASE_URL}/fields/base/by/s-name/{service_name}")
            custom_fields_req = await request.get(f"{BAASE_URL}/fields/custom/by/s-name/{service_name}")
            combined_fields = {}
            if base_fields_req.status_code == 200 and custom_fields_req.status_code == 200:
                base_fields_datas = base_fields_req.json().get('data') or {}
                custom_fields_datas = custom_fields_req.json().get('data') or {}
                combined_fields = {**base_fields_datas.get('fields', {}), **custom_fields_datas.get('fields', {})}
            return combined_fields
    except Exception as e:
        ic(f"Error fetching fields: {e}")
        return {}


