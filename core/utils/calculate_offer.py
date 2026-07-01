def calculate_offer(amount:float,offer:str):
    if offer[-1]=="%":
        calculated_result=amount-((18/amount)*100)
    else:
        calculated_result=amount-offer if offer>amount else 0
    
    return calculated_result