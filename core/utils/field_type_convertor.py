from datetime import date

def convert_field_type(field_type:str):
    mapper={
        "DROP DOWN":str,
        "TEXT":str,
        "NUMBER":int,
        "DECIMAL":float,
        "DATE":date,
        "BOOLEAN":bool
    }

    return mapper.get(field_type,None)