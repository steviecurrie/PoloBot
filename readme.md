# PoloBot
A trading bot for the Poloniex Exchange (Very much WIP)

## Installation

You need to install this first

`pip3 install https://github.com/s4w3d0ff/python-poloniex/archive/v0.4.6.zip`

(This was the only variant of the Poloniex API wrapper that works for me.)

You'll also need pandas

## Progress so far...

Removed the need for matplotlib - it was annoying me - created my own candlestick graph routines.
Added SMA, EMA, MACD and RSI to charts.

added input and saving of API key & secret - currently saved as plain text in the charts folder - needs work.
added buy & sell, functionality.

Next step, strategies and backtesting

