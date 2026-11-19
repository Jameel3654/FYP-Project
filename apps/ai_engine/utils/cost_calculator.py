"""
Token cost calculation utility.
"""

def calculate_cost(tokens: int, provider: str, is_input: bool = True) -> dict:
    """
    Calculates cost based on token count and provider.
    GPT-4 rates: input $0.03/1K tokens, output $0.06/1K tokens.
    Gemini rates: input $0.00025/1K, output $0.0005/1K.
    PKR conversion rate: 280.
    """
    usd_cost = 0.0
    pkr_rate = 280.0
    
    provider_lower = provider.lower()
    
    if provider_lower == 'gpt-4':
        if is_input:
            usd_cost = (tokens / 1000) * 0.03
        else:
            usd_cost = (tokens / 1000) * 0.06
    elif provider_lower == 'gemini':
        if is_input:
            usd_cost = (tokens / 1000) * 0.00025
        else:
            usd_cost = (tokens / 1000) * 0.0005
            
    pkr_cost = usd_cost * pkr_rate
    
    return {
        "usd": usd_cost,
        "pkr": pkr_cost
    }
