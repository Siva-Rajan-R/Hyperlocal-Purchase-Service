from typing import List, Dict
from fastapi import HTTPException
from icecream import ic
from hyperlocal_platform.core.models.req_res_models import ErrorResponseTypDict

def validate_and_filter_custom_fields(payload_custom_fields: Dict, defined_custom_fields: List[Dict]) -> Dict:
    """
    Validates the provided custom fields against the defined custom fields.
    - If no defined custom fields, ignore the payload and return {}.
    - Checks for missing required fields and raises HTTPException.
    - Filters out any fields in payload that are not defined.
    """
    if not defined_custom_fields:
        return {}

    defined_fields_map = {field['field_name']: field for field in defined_custom_fields}
    payload_custom_fields = payload_custom_fields or {}
    ic(defined_fields_map,payload_custom_fields)

    # Check for required fields
    for field_name, field_def in defined_fields_map.items():
        if field_def.get('required') and field_name not in payload_custom_fields:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponseTypDict(
                    status_code=400,
                    msg="Missing Required Custom Field",
                    description=f"The custom field '{field_name}' is required.",
                    success=False
                )
            )

    # Filter out unknown fields and build valid custom fields
    valid_custom_fields = {}
    
    for key, value in payload_custom_fields.items():
        if key in defined_fields_map:
            valid_custom_fields[defined_fields_map[key]['id']] = value
    ic(valid_custom_fields)
    return valid_custom_fields
