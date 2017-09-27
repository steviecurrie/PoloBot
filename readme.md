# PoloBot
A trading bot for the Poloniex Exchange

## Installation

You need to install this first

`pip3 install https://github.com/s4w3d0ff/python-poloniex/archive/v0.4.6.zip`

(I couldn't find a way to to install a working poloniex wrapper from setup.py - this is a workaround for now)

then run
`python3 setup.py`

## Progress so far...

### retrievechartdata(currency, startdate, enddate, freq=300)
Retrieves chart data from Poloniex API.
Returns chart in a pandas dataframe.

### loadchart(currency, startdate, enddate, freq=300)
Loads chart data from ~/charts/ if it exists, otherwise calls retrievechartdata to retrieve it from Poloniex and saves it.
Returns chart in a pandas dataframe.

### updatechart(currency, chartdata, freq=300)
Given existing chart dataframe, retrieves updated chart from Poloniex and saves to ~/charts/
Returns updated chart in a pandas dataframe.

### class livePoloData:
Threads to provide ticker and balances

### class Portfolio:
Class to load chart data and thread to automatically update charts
provide it with a list of currencies to use.
ie, portfolio = Portfolio(["BCH","ETH", "XMR", "ZEC"])

portfolio.chartdata[currency] returns dataframe
portfolio.currencies holds list of currencies created by __init__
