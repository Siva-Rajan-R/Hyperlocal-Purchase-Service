from enum import Enum


class InventoryProductCategoryEnum(str,Enum):
    ELECTRONICS="ELECTRONICS"
    FASHION="FASHION"
    GROCERY="GROCERY"
    TOYS="TOYS"
    BOOKS="BOOKS"
    BEAUTY="BEAUTY"
    SPORTS="SPORTS"


class InventoryFetchMode(str,Enum):
    ORDER="ORDER"
    INVENTORY="INVENTORY"