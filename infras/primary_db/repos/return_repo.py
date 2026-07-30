from infras.primary_db.models.purchase_model import PurchaseReturns, PurchaseReturnItems
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from hyperlocal_platform.core.decorators.db_session_handler_dec import start_db_transaction

class ReturnRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    @start_db_transaction
    async def create_return_with_items(self, return_obj: PurchaseReturns, return_items: List[PurchaseReturnItems]) -> bool:
        self.session.add(return_obj)
        self.session.add_all(return_items)
        return True
