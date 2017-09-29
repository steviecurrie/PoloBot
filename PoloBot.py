import threading
import time
from datetime import datetime, timedelta
from os import makedirs
from os.path import isfile, expanduser

import pandas as pd
from poloniex import Poloniex

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


def loadchart(currency, startdate, enddate, freq=300, forcereload=False):
    """
    Function to load chart from csv file - if csv doesn't exist, call retreive to get it from Poloniex
    :param currency: string containing short name of currency, ie ETH, XMR, STEEM
    :param startdate: datetime for start of chart data
    :param enddate: datetime for end of chart data
    :param freq: int for chart frequency in seconds, ie 300 for 5 minutes, 3600 for 1 hour
    :param forcereload: force download of chart data from polo, use if you need to use older data
    :return: chartdata: pandas dataframe with chartdata for this currency
    """
    path = chartpath + currency + ".csv"
    if isfile(path) and not forcereload:
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


class LivePoloData:
    def __init__(self):
        self.tickerupdated = datetime(1970, 1, 1, 0, 0, 0)
        self.balancesupdated = datetime(1970, 1, 1, 0, 0, 0)
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
    def __init__(self, currencies, history=30, forcereload=False):
        """
        Load charts for currencies and create thread to keep them updated
        :param currencies: list of currencies to work with, ie ["BCH", "ETH", "XMR]
        :param history: number of days history to download
        :param forcereload: force download of chart data from polo, use if you need to use older data
        """
        self.chartdata = {}
        self.currencies = currencies
        for currency in currencies:
            self.chartdata[currency] = loadchart(currency, datetime.now() - timedelta(days=history),
                                                 datetime.now(), forcereload=forcereload)

        self.chartthread = threading.Thread(target=self.chartsupdate)
        self.chartthread.setDaemon(True)
        self.chartthread.start()

    def chartsupdate(self):
        while True:
            for currency in self.currencies:
                self.chartdata[currency] = updatechart(currency, self.chartdata[currency])
            time.sleep(chartsupdatedelay)


class BackTest:
    def __init__(self, data, tradepct=10, btcbalance=0.01, coinbalance=0.0,
                 buyfee=0.25, sellfee=0.15, candlewidth=5, **kwargs):
        self.data = data.asfreq(str(candlewidth) + 'Min', method='pad')
        self.startbtcbalance = btcbalance
        self.startcoinbalance = coinbalance
        self.btcbalance = btcbalance
        self.coinbalance = coinbalance
        self.tradepct = tradepct
        self.tradesizebtc = self.btcbalance * (self.tradepct / 100)
        self.buyfeemult = 1 - (buyfee / 100)
        self.sellfeemult = 1 - (sellfee / 100)
        self.step = 0
        self.testlength = self.data.shape[0]
        self.addindicators(**kwargs)

    def addindicators(self, **kwargs):
        '''
        override this with code to add your own indicators
        for example
        self.ma = ma
        self.data["ma"] = self.data["close"].rolling(self.ma).mean()
        '''
        pass

    def _dostep(self):
        self.tradesizebtc = self.btcbalance * (self.tradepct / 100)
        self.dostep()
        self.step += 1

    def dostep(self):
        '''
        override this with code to add your own strategy code
        for example
        if self.step > self.ma:
            price = self.data.ix[self.step, "close"]
            ma = self.data.ix[self.step, "ma"]

            if price > ma:
                self.buy(price)
            elif price < ma:
                self.sell(price)
        '''
        pass

    def buy(self, price):
        if self.btcbalance > self.tradesizebtc:
            self.btcbalance -= self.tradesizebtc
            self.coinbalance += ((self.tradesizebtc / price) * self.buyfeemult)
            # print("Step:{0} Bought at {1:.8f}".format(self.step, price))

    def sell(self, price):
        if self.coinbalance > 0:
            self.btcbalance += ((self.coinbalance * price) * self.sellfeemult)
            self.coinbalance = 0.0
            # print("Step:{0} Sold at {1:.8f}".format(self.step, price))

    def runtest(self):
        for i in range(self.testlength):
            self._dostep()

        finalvalue = self.btcbalance + (self.coinbalance * self.data.ix[self.testlength - 1, "close"])
        initialvalue = self.startbtcbalance + (self.startcoinbalance * self.data.ix[0, "close"])
        profit = ((finalvalue - initialvalue) / initialvalue) * 100
        return initialvalue, finalvalue, profit


class SMACrossoverBackTest(BackTest):
    def addindicators(self, **kwargs):
        self.fastma = kwargs["fastma"]
        self.slowma = kwargs["slowma"]
        self.data["fastma"] = self.data["close"].rolling(self.fastma).mean()
        self.data["slowma"] = self.data["close"].rolling(self.slowma).mean()

    def dostep(self):
        if self.step > self.slowma:
            prevfastma = self.data.ix[self.step - 1, "fastma"]
            prevslowma = self.data.ix[self.step - 1, "slowma"]

            price = self.data.ix[self.step, "close"]
            fastma = self.data.ix[self.step, "fastma"]
            slowma = self.data.ix[self.step, "slowma"]

            if fastma > slowma and prevfastma < prevslowma:
                self.buy(price)
            elif fastma < slowma and prevfastma > prevslowma:
                self.sell(price)


class EMACrossoverBackTest(BackTest):
    def addindicators(self, **kwargs):
        self.fastma = kwargs["fastma"]
        self.slowma = kwargs["slowma"]
        self.data["fastma"] = self.data["close"].ewm(self.fastma).mean()
        self.data["slowma"] = self.data["close"].ewm(self.slowma).mean()

    def dostep(self):
        if self.step > self.slowma:
            prevfastma = self.data.ix[self.step - 1, "fastma"]
            prevslowma = self.data.ix[self.step - 1, "slowma"]

            price = self.data.ix[self.step, "close"]
            fastma = self.data.ix[self.step, "fastma"]
            slowma = self.data.ix[self.step, "slowma"]

            if fastma > slowma and prevfastma < prevslowma:
                self.buy(price)
            elif fastma < slowma and prevfastma > prevslowma:
                self.sell(price)


# get API key and secret and create polo object
#api_key, api_secret = getkeys()
#polo = Poloniex(api_key, api_secret)
# livedata = LivePoloData() # Don't need live updates for now
# portfolio = Portfolio(["ETH", "XMR", "ZEC"], history=180, forcereload=False)

# # Test Simple Moving Average Crossover
# for fastma in range(5, 50, 5):
#     slowma = fastma * 4
#     print("\nMoving Average: Fast:{0} Slow:{1}".format(fastma, slowma))
#     for coin in portfolio.currencies:
#         test = SMACrossoverBackTest(portfolio.chartdata[coin], fastma=fastma, slowma=slowma)
#         initialvalue, finalvalue, profit = test.runtest()
#         print("{0}: Profit {1:.2f}%".format(coin, profit))
#
# # Test Exponential Moving Average Crossover
# for fastma in range(5, 50, 5):
#     slowma = fastma * 4
#     print("\nMoving Average: Fast:{0} Slow:{1}".format(fastma, slowma))
#     for coin in portfolio.currencies:
#         test = EMACrossoverBackTest(portfolio.chartdata[coin], fastma=fastma, slowma=slowma)
#         initialvalue, finalvalue, profit = test.runtest()
#         print("{0}: Profit {1:.2f}%".format(coin, profit))

polo = Poloniex()
portfolio = Portfolio(["XMR"])
test = SMACrossoverBackTest(portfolio.chartdata["XMR"], fastma=25, slowma=100)
initialvalue, finalvalue, profit = test.runtest()
print("Start Value: {0:.8f}BTC, Final Value: {1:.8f}BTC, Profit {2:.2f}%".\
      format(initialvalue, finalvalue, profit))
