# Configuration settings for the portfolio optimizer

# Top-level configuration setting - can be "YahooFinance" or "AlphaVantage"
DATA_GETTER = "AlphaVantage"

def get_fetcher():
    """
    Returns the data fetcher implementation based on configuration.
    
    Returns:
        Type: Fetcher class to use for getting financial data
    """
    if DATA_GETTER == "AlphaVantage":
        from data_getter import AlphaVantageDataGetter
        return AlphaVantageDataGetter
    else:
        from data_getter import YahooFinanceDataGetter
        return YahooFinanceDataGetter

# The fetcher instance that should be used throughout the application
Fetcher = get_fetcher()
