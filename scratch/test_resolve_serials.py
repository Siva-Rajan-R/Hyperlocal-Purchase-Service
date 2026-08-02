import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infras.primary_db.services.purchase_service import resolve_serials_from_inventory
from icecream import ic

def test_resolve_serials():
    # Input serials from purchase request
    itm_serials = [{"name": "HELLO"}]
    
    # Real serialno_infos returned from InventoryService (ProdInvCollections)
    db_serialno_infos = [
        {
            "id": "0e44bca7-dad3-500f-82a1-f27eaa8a4ed1",
            "name": "HELLO",
            "status": "AVAILABLE",
            "visible_online": False
        }
    ]
    
    res = resolve_serials_from_inventory(itm_serials, db_serialno_infos)
    ic("Resolved Serials =>", res)
    
    assert len(res) == 1
    assert res[0]["id"] == "0e44bca7-dad3-500f-82a1-f27eaa8a4ed1"
    assert res[0]["name"] == "HELLO"
    
    print("RESOLVE SERIALS WITH INVENTORY PROD_DB ID VERIFIED CLEANLY!")

if __name__ == "__main__":
    test_resolve_serials()
