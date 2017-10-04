# PoloBot
A trading bot for the Poloniex Exchange (Very much WIP)

## Installation

You need to install this first

`pip3 install https://github.com/s4w3d0ff/python-poloniex/archive/v0.4.6.zip`

(This was the only variant of the Poloniex API wrapper that works for me.)

You'll also need pandas and matplotlib

## Progress so far...

Rethought the whole lot.  Moved the Polo stuff to it's own file and created basic TKinter GUI.
So far, there is a list of favourite markets on the left, a full list of markets in the menubar and a button to
add/remove markets from the list.  It displays a candlestick chart of recent price data at a user selected interval.

It's a start.

polodata.py contains the PoloData class with the following methods.

start_ticker(update_freq) - starts ticker thread with update_freq in seconds

stop_ticker() - stops ticker thread

start_charts(update_freq, chart_path) - starts chart update thread with update_freq in seconds, saves charts to chart_path

stop_charts() - stops chart update thread

add_chart(market) - adds market to list of charts to keep updated, ie "BTC_ETH" or "USDT_BTC"

remove_chart(market) - remove market from chart update list


.charts holds a dictionary of charts, each chart is a pandas dataframe

.ticker holds the latest price data, stored in a pandas dataframe


### class BackTest
A simple backtest.  Override addindicators and dostep methods.
