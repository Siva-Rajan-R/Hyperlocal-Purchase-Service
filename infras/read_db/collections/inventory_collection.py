from pydantic import BaseModel

from .. import main


def inventory_collection():
    print(main.READ_DATABASE)
    return main.READ_DATABASE['InventoryCollections']