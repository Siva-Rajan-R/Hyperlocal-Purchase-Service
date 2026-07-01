from enum import Enum

class PurchaseTypeEnums(str,Enum):
    PO_CREATE="PO_CREATE"
    PO_UPDATE="PO_UPDATE"
    DIRECT="DIRECT"
    PRODUCTION="PRODUCTION"

class PurchaseCalcultionDividedValue(str,Enum):
    BY_VALUE="BY_VALUE"
    BY_QUANTITY="BY_QUANTITY"
    BY_EQUAL="BY_EQUAL"
    NONE="NONE"


class PurchasePaymentMethods(str,Enum):
    UPI="UPI"
    CASH="CASH"
    CARD="CARD"
    BANK="BANK"


class PurchaseViewsEnums(str,Enum):
    PO_VIEW="PO_VIEW"
    PURCHASE_VIEW="PURCHASE_VIEW"
    STOCKADJUSTMENT_VIEW="STOCKADJUSTMENT_VIEW"
