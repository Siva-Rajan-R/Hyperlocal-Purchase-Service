def validate_offer_input(offer:str):
    try:
        float(offer)
        return offer
    except:
        if offer[-1]=="%":
            try:
                float(offer[0:-1])
                return offer
            except:
                return False