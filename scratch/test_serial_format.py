import sys
import os
import asyncio
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infras.primary_db.services.purchase_service import normalize_serial_numbers, extract_sn_info
from icecream import ic

def test_normalization():
    # Test 1: Plain strings
    s1 = ["SN-001", "SN-002"]
    norm1 = normalize_serial_numbers(s1)
    ic("Norm 1 (plain strings) =>", norm1)
    assert len(norm1) == 2
    assert "id" in norm1[0] and "name" in norm1[0]
    assert norm1[0]["name"] == "SN-001"

    # Test 2: Dicts with name only
    s2 = [{"name": "SN-100"}, {"name": "SN-200"}]
    norm2 = normalize_serial_numbers(s2)
    ic("Norm 2 (dicts name only) =>", norm2)
    assert len(norm2) == 2
    assert "id" in norm2[0] and norm2[0]["name"] == "SN-100"

    # Test 3: Dicts with id and name
    custom_id = str(uuid.uuid4())
    s3 = [{"id": custom_id, "name": "SN-300"}]
    norm3 = normalize_serial_numbers(s3)
    ic("Norm 3 (dicts id & name) =>", norm3)
    assert norm3[0]["id"] == custom_id
    assert norm3[0]["name"] == "SN-300"

    # Test 4: Dicts with serialno_id and serialno_name
    s4 = [{"serialno_id": custom_id, "serialno_name": "SN-400"}]
    norm4 = normalize_serial_numbers(s4)
    ic("Norm 4 (serialno_id & serialno_name) =>", norm4)
    assert norm4[0]["id"] == custom_id
    assert norm4[0]["name"] == "SN-400"

    print("ALL SERIAL NORMALIZATION TESTS PASSED CLEANLY!")

if __name__ == "__main__":
    test_normalization()
