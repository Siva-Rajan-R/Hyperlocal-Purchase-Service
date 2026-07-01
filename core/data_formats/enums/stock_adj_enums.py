from enum import Enum

class StockAdjustmentTypesEnum(str,Enum):
    DECREMENT="DECREMENT"
    INCREMENT="INCREMENT"


class StockAdjustmentMovementType(str,Enum):
    SALES="SALES"
    DIRECT="DIRECT"
    STOCK_ADJUSTMENT="STOCK_ADJUSTMENT"
    RETURN="RETURN"
    EXCHANGE="EXCHANGE"