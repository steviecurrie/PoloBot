from poloniex import Poloniex
import time
import threading
import pandas as pd
from os.path import isdir, isfile, expanduser
from os import makedirs
from datetime import datetime, timedelta
from gui import *

# Edit apikeys.py to set your Poloniex API key and secret
from apikeys import getkeys

# global variables
chartpath = expanduser("~/charts/")
tickerupdatedelay = 1
balancesupdatedelay = 5
chartsupdatedelay = 60

makedirs(chartpath, exist_ok=True)


def retrievechartdata(currency, startdate, enddate, freq=300):
    """
    Function to retreive chart data from poloniex
    :param currency: string containing short name of currency, ie ETH, XMR, STEEM
    :param startdate: datetime for start of chart data
    :param enddate: datetime for end of chart data
    :param freq: int for chart frequency in seconds, ie 300 for 5 minutes, 3600 for 1 hour
    :return: chartdata: pandas dataframe with chartdata for this currency
    """
    startdate = startdate.timestamp()
    enddate = enddate.timestamp()

    rawchartdata = polo.returnChartData("BTC_" + currency, freq, startdate, enddate)
    chartdata = pd.DataFrame(rawchartdata, dtype=float)
    chartdata["realdate"] = [datetime.fromtimestamp(d) for d in chartdata["date"]]
    chartdata.set_index(["realdate"], inplace=True)
    chartdata.drop("date", axis=1, inplace=True)
    chartdata = chartdata.drop_duplicates()
    freqstr = str(int(freq / 60)) + "Min"
    chartdata = chartdata.asfreq(freqstr, method='pad')
    return chartdata


def loadchart(currency, startdate, enddate, freq=300):
    """
    Function to load chart from csv file - if csv doesn't exist, call retreive to get it from Poloniex
    :param currency: string containing short name of currency, ie ETH, XMR, STEEM
    :param startdate: datetime for start of chart data
    :param enddate: datetime for end of chart data
    :param freq: int for chart frequency in seconds, ie 300 for 5 minutes, 3600 for 1 hour
    :return: chartdata: pandas dataframe with chartdata for this currency
    """
    path = chartpath + currency + ".csv"
    if isfile(path):
        print("Loading:", currency, end='', flush=True)
        chartdata = pd.read_csv(path, parse_dates=True, index_col="realdate")
        print(" OK.")
    else:
        print("Downloading:", currency)
        chartdata = retrievechartdata(currency, startdate, enddate, freq)
        chartdata.to_csv(path)
    return chartdata


def updatechart(currency, chartdata, freq=300):
    """
    Function to update provide chart with latest data from Poloniex
    :param currency: string containing short name of currency, ie ETH, XMR, STEEM
    :param chartdata: pandas dataframe with chartdata for this currency
    :param freq: int for chart frequency in seconds, ie 300 for 5 minutes, 3600 for 1 hour
    :return: chartdata: pandas dataframe with updated chartdata for this currency
    """
    path = chartpath + currency + ".csv"
    nextentry = chartdata.ix[-1].name.to_pydatetime() + timedelta(minutes=int(freq / 60))
    update = retrievechartdata(currency, nextentry, datetime.now(), freq)

    # noinspection PyUnresolvedReferences
    if update.shape[0] > 1:
        chartdata = pd.concat([chartdata, update])
        chartdata = chartdata.drop_duplicates()
        freqstr = str(int(freq / 60)) + "Min"
        chartdata = chartdata.asfreq(freqstr, method='pad')
        chartdata.to_csv(path)
    return chartdata


class livePoloData:
    def __init__(self):
        self.tickerupdated = datetime(1970,1,1,0,0,0)
        self.balancesupdated = datetime(1970,1,1,0,0,0)
        self.ticker = {}
        self.balances = {}

        self.tickerthread = threading.Thread(target=self.getticker)
        self.tickerthread.setDaemon(True)
        self.tickerthread.start()

        self.balancesthread = threading.Thread(target=self.getbalances)
        self.balancesthread.setDaemon(True)
        self.balancesthread.start()

    def getticker(self):
        while True:
            self.ticker = polo.returnTicker()
            self.tickerupdated = datetime.now()
            time.sleep(tickerupdatedelay)

    def getbalances(self):
        while True:
            self.balances = polo.returnCompleteBalances()
            self.balancesupdated = datetime.now()
            time.sleep(balancesupdatedelay)

class Portfolio:
    def __init__(self, currencies):
        """
        Load charts for currencies and create thread to keep them updated
        :param currencies: list of currencies to work with, ie ["BCH", "ETH", "XMR]
        """
        self.chartdata = {}
        self.currencies = currencies
        for currency in currencies:
            self.chartdata[currency] = loadchart(currency, datetime.now() - timedelta(days=30), datetime.now())

        self.chartthread = threading.Thread(target=self.chartsupdate)
        self.chartthread.setDaemon(True)
        self.chartthread.start()

    def chartsupdate(self):
        while True:
            for currency in self.currencies:
                self.chartdata[currency] = updatechart(currency, self.chartdata[currency])
            time.sleep(chartsupdatedelay)

# get API key and secret and create polo object
api_key, api_secret = getkeys()
polo = Poloniex(api_key, api_secret)
livedata = livePoloData()
portfolio = Portfolio(["BCH","ETH", "XMR", "ZEC"])

# simple tests print update times for livedata and last entry for each currency every minute
# wait for ticker and balances first updates
while livedata.ticker == {} or livedata.balances == {}:
    print(".", end="")
    time.sleep(.25)

for i in range(20):
    print(livedata.tickerupdated.strftime("%H:%M:%S"), livedata.balancesupdated.strftime("%H:%M:%S"))
    print("-------------")
    for currency in portfolio.currencies:
        print(currency, " last chart entry\n", portfolio.chartdata[currency].tail(3)[["open", "high", "low", "close"]])
        print(currency, "last price", livedata.ticker["BTC_" + currency]["last"], "\n")
    time.sleep(60)