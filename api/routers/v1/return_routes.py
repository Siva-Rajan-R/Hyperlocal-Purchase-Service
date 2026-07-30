from ...handlers.return_handler import HandleReturnRequest
from schemas.v1.purchase_schemas.return_schema import CreatePurchaseReturnSchema
from fastapi import APIRouter, Depends
from typing import Annotated, Optional
from infras.primary_db.main import get_pg_async_session, AsyncSession

router = APIRouter(
    prefix='/purchases/returns',
    tags=['Purchase Returns']
)

from core.utils.user_info import get_current_user_id

PG_SESSION = Annotated[AsyncSession, Depends(get_pg_async_session)]
SHOP_ID = "37d5519b-51a1-5854-982b-4d6524171017"


@router.post('')
async def create_return(data: CreatePurchaseReturnSchema, session: PG_SESSION, user_id: Optional[str] = Depends(get_current_user_id)):
    shop_id = data.shop_id or SHOP_ID
    data.shop_id = shop_id
    return await HandleReturnRequest(session=session, shop_id=shop_id, cur_user_id=user_id or "").create(data=data)
