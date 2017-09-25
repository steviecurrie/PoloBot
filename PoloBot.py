from poloniex import Poloniex
from apikeys import getkeys

api_key, api_secret = getkeys()

polo = Poloniex(api_key, api_secret, timeout=30)

ticker = polo.returnTicker()['BTC_ETH']
print(ticker)

balances = polo.returnBalances()
print(balances)
