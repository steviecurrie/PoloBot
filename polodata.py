import threading
import time
from os.path import isfile
from datetime import datetime, timedelta
import pandas as pd
from poloniex import Poloniex


class PoloData:
    def __init__(self, *args, **kwargs):
        self._polo = Poloniex(*args, **kwargs)

        self.ticker_update_freq = 1
        self.ticker_updated = datetime(1970, 1, 1)
        self._ticker = {}
        self.ticker = None
        self.ticker_active = False
        self._ticker_thread = None

        self.charts_update_freq = 60
        self.charts_updated = datetime(1970, 1, 1)
        self.charts = {}
        self.charts_active = False
        self._charts_thread = None
        self.chart_path = None
        self._new_chart = False

        self.markets = self._get_markets()

    def start_ticker(self, update_freq):
        self.ticker_update_freq = update_freq
        self._ticker_thread = threading.Thread(target=self._get_ticker)
        self._ticker_thread.setDaemon(True)
        self.ticker_active = True
        self._ticker_thread.start()

    def _get_ticker(self):
        while self.ticker_active:
            self._ticker = self._polo.returnTicker()
            self._populate_ticker()
            self.ticker_updated = datetime.now()
            time.sleep(self.ticker_update_freq)
        print("Ticker thread stopped.")

    def stop_ticker(self):
        self.ticker_active = False

    def _get_markets(self):
        ticker = self._polo.returnTicker()

        markets = {}

        for k in ticker.keys():
            pc, sc = k.split("_")
            if pc not in markets:
                markets[pc] = pd.DataFrame(columns=['last', 'highestBid', 'baseVolume', 'lowestAsk',
                                                    'quoteVolume', 'low24hr', 'high24hr', 'percentChange',
                                                    'isFrozen', 'id', 'favourite'],
                                           dtype=float)
            if sc not in markets[pc]:
                markets[pc].ix[sc, "favourite"] = 0

        return markets

    def _populate_ticker(self):
        self.ticker = pd.DataFrame.from_dict(self._ticker, orient='index', dtype=float).fillna(0)

    def start_charts(self, update_freq, chart_path):
        self.charts_update_freq = update_freq
        self.chart_path = chart_path
        self._charts_thread = threading.Thread(target=self._get_charts)
        self._charts_thread.setDaemon(True)
        self.charts_active = True
        self._charts_thread.start()

    def _get_charts(self):
        while self.charts_active:
            update_time = datetime.now() + timedelta(seconds=self.charts_update_freq)
            for chart in self.charts:
                market, currency = chart.split("_")
                if self.charts[chart] is None:
                    self.charts[chart] = self._load_chart(market, currency,
                                                          datetime.now() - timedelta(days=90), datetime.now())
                    self._new_chart = False
                else:
                    self.charts[chart] = self._update_chart(market, currency, self.charts[chart])
            self.charts_updated = datetime.now()
            while datetime.now() < update_time and not self._new_chart:
                time.sleep(1)

        print("Charts thread stopped.")

    def stop_charts(self):
        self.charts_active = False

    def add_chart(self, market):
        if market not in self.charts:
            self.charts[market] = None
            self._new_chart = True

    def remove_chart(self, market):
        if market is not None:
            del self.charts[market]

    def _retrieve_chart_data(self, market, currency, start_date, end_date, freq=300):
        start_date = start_date.timestamp()
        end_date = end_date.timestamp()

        raw_chart_data = self._polo.returnChartData(market + "_" + currency, freq, start_date, end_date)
        chart_data = pd.DataFrame(raw_chart_data, dtype=float)
        chart_data["Date"] = [datetime.fromtimestamp(d) for d in chart_data["date"]]
        chart_data.set_index(["Date"], inplace=True)
        chart_data.drop("date", axis=1, inplace=True)
        chart_data = chart_data.drop_duplicates()
        freq_str = str(int(freq / 60)) + "Min"
        chart_data = chart_data.asfreq(freq_str, method='pad')
        return chart_data

    def _load_chart(self, market, currency, start_date, end_date, freq=300, force_reload=False):
        path = self.chart_path + market + "_" + currency + ".csv"
        if isfile(path) and not force_reload:
            # print("Loading:", market + "_" + currency, end='', flush=True)
            chart_data = pd.read_csv(path, parse_dates=True, index_col="Date")
            # print(" OK.")
        else:
            # print("Downloading:", market + "_" + currency)
            chart_data = self._retrieve_chart_data(market, currency, start_date, end_date, freq)
            chart_data.to_csv(path)
        return chart_data

    def _update_chart(self, market, currency, chart_data, freq=300):
        path = self.chart_path + market + "_" + currency + ".csv"
        next_entry = chart_data.ix[-1].name.to_pydatetime() + timedelta(minutes=int(freq / 60))
        update = self._retrieve_chart_data(market, currency, next_entry, datetime.now(), freq)
        # print("Updating:", market + "_" + currency)
        if update.shape[0] > 1:
            chart_data = pd.concat([chart_data, update])
            chart_data = chart_data.drop_duplicates()
            freq_str = str(int(freq / 60)) + "Min"
            chart_data = chart_data.asfreq(freq_str, method='pad')
            chart_data.to_csv(path)
        return chart_data


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
        """
        override this with code to add your own indicators
        for example
        self.ma = ma
        self.data["ma"] = self.data["close"].rolling(self.ma).mean()
        """
        pass

    def _dostep(self):
        self.tradesizebtc = self.btcbalance * (self.tradepct / 100)
        self.dostep()
        self.step += 1

    def dostep(self):
        """
        Override this with code to add your own strategy code
        for example
        if self.step > self.ma:
            price = self.data.ix[self.step, "close"]
            ma = self.data.ix[self.step, "ma"]

            if price > ma:
                self.buy(price)
            elif price < ma:
                self.sell(price)
        """
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


class PriceCrossSMABackTest(BackTest):
    def addindicators(self, **kwargs):
        self.ma = kwargs["ma"]
        self.data["ma"] = self.data["close"].rolling(self.ma).mean()

    def dostep(self):
        if self.step > self.ma:
            prevprice = self.data.ix[self.step - 1, "close"]
            price = self.data.ix[self.step, "close"]
            prevma = self.data.ix[self.step - 1, "ma"]
            ma = self.data.ix[self.step, "ma"]

            if price > ma and prevprice < prevma:
                self.buy(price)
            elif price < ma and prevprice > prevma:
                self.sell(price)

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

# coin="XMR"
# polo = Poloniex()
# portfolio = Portfolio([coin])
# test = PriceCrossSMABackTest(portfolio.chartdata[coin], candlewidth=180, ma=50)
# initialvalue, finalvalue, profit = test.runtest()
# print("Start Value: {0:.8f}BTC, Final Value: {1:.8f}BTC, Profit {2:.2f}%".\
#       format(initialvalue, finalvalue, profit))
