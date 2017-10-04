import time
import tkinter as tk
from os import makedirs
from os.path import expanduser
from os.path import isfile

import matplotlib

from polodata import PoloData

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
# from matplotlib.figure import Figure
from matplotlib import pyplot as plt

import matplotlib.dates as mdates
from matplotlib.finance import candlestick_ohlc

# global variables
apptitle = "PoloBot v0.1"
chartpath = expanduser("~/charts/")
makedirs(chartpath, exist_ok=True)
SM_MONO = ("mono", 6)


class MainWindow(tk.Tk):
    def __init__(self):
        self.displaying = None
        tk.Tk.__init__(self)
        self.title(apptitle)
        self.maxsize(width=1280, height=1024)
        self.minsize(width=800, height=600)
        self.resizable(True, True)

        if isfile(chartpath + ".cfg"):
            with open(chartpath + ".cfg", "r") as f:
                self.active_currencies = f.readline().strip().split(",")
        else:
            self.active_currencies = ["USDT_BTC"]
        self.market = None
        self.prev_market = None
        self._set_market(self.active_currencies[0])
        self._candle_freq = "5Min"
        self._candle_width = 0.002
        self._ticker_button_dict = {}

        self._chart_last_drawn = None
        self._chart_changed = True
        self._after_id = None

        self.root_frame = tk.Frame(self)
        self.root_frame.pack(side="top", fill="both", expand=True)

        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Options", command=self.bell())
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self._stop_everything)
        menubar.add_cascade(label="File", menu=filemenu)

        market_menu = tk.Menu(menubar)
        for mkt in sorted(pdat.markets):
            if pdat.markets[mkt].index.shape[0] < 17:
                submenu = tk.Menu(market_menu)
                for coin in sorted(pdat.markets[mkt].index):
                    submenu.add_command(label=coin, command=lambda m=mkt + "_" + coin: self._set_market(m))
                market_menu.add_cascade(label=mkt, menu=submenu)
            else:
                arr = sorted(pdat.markets[mkt].index)
                size = 16
                idx = 1
                while len(arr) > size:
                    sub = arr[:size]
                    submenu = tk.Menu(market_menu)
                    for coin in sub:
                        submenu.add_command(label=coin, command=lambda m=mkt + "_" + coin: self._set_market(m))
                    market_menu.add_cascade(label=mkt + str(idx), menu=submenu)
                    arr = arr[size:]
                    idx += 1
                for coin in arr:
                    submenu.add_command(label=coin, command=lambda m=mkt + "_" + coin: self._set_market(m))
                market_menu.add_cascade(label=mkt + str(idx), menu=submenu)

        chart_menu = tk.Menu(menubar)
        chart_menu.add_command(label="5 Min", command=lambda f="5Min", w=0.0025: self._set_candle_width(f,w))
        chart_menu.add_command(label="15 Min", command=lambda f="15Min", w=0.0075: self._set_candle_width(f,w))
        chart_menu.add_command(label="30 Min", command=lambda f="30Min", w=0.015: self._set_candle_width(f,w))
        chart_menu.add_command(label="1 Hour", command=lambda f="1H", w=0.03: self._set_candle_width(f,w))
        chart_menu.add_command(label="3 Hour", command=lambda f="3H", w=0.1: self._set_candle_width(f,w))
        chart_menu.add_command(label="6 Hour", command=lambda f="6H", w=0.2: self._set_candle_width(f,w))
        chart_menu.add_command(label="12 Hour", command=lambda f="12H", w=0.4: self._set_candle_width(f,w))
        menubar.add_cascade(label="Candles", menu=chart_menu)

        menubar.add_cascade(label="Markets", menu=market_menu)
        self.config(menu=menubar)

        self.button_frame = tk.Frame(self.root_frame)
        self.button_frame.pack(side='left', fill='y')
        self.button_sub_frame = tk.Frame(self.button_frame)
        self._add_market_buttons()

        self.chart_frame = tk.Frame(self.root_frame)
        self.chart_frame.pack(side='top', fill='both', expand=1)
        self.figure = plt.figure(figsize=(7, 5))
        self.ax1 = plt.subplot(1, 1, 1)
        self.mpl_canvas = FigureCanvasTkAgg(self.figure, self.chart_frame)
        self.mpl_canvas.show()
        self.mpl_canvas.get_tk_widget().pack(side='top', fill='both', expand=1)

        self._after_id = self.after(1500, func=self._chart_frame_update)

        self.button_frame2 = tk.Frame(self.root_frame)
        self.button_frame2.pack(side='bottom', fill='x')
        button1 = tk.Button(self.button_frame2, text="<->", command=self._add_market)
        button1.pack(side='left', fill='y')
        button1 = tk.Button(self.button_frame2, text="Buy")
        button1.pack(side='left', fill='y')
        button2 = tk.Button(self.button_frame2, text="Sell")
        button2.pack(side='left', fill='y')
        button3 = tk.Button(self.button_frame2, text="Auto")
        button3.pack(side='left', fill='y')

        toolbar = NavigationToolbar2TkAgg(self.mpl_canvas, self.button_frame2)
        toolbar.update()
        self.mpl_canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH)

        self.protocol("WM_DELETE_WINDOW", self._stop_everything)

    def _set_candle_width(self, freq, width):
        if width != self._candle_width:
            self._candle_freq = freq
            self._candle_width = width
            self._chart_changed = True

    def _add_market_buttons(self):
        self.button_sub_frame.destroy()
        self.button_sub_frame = tk.Frame(self.button_frame)
        self.button_sub_frame.pack(side='left', fill='both')
        self._ticker_button_list = {}
        for mkt in sorted(self.active_currencies):
            self._ticker_button_list[mkt] = tk.Button(self.button_sub_frame, text=mkt + "\n----.--------",
                                                      command=lambda m=mkt: self._set_market(m))
            self._ticker_button_list[mkt].pack(side='top', fill="x")
        self.button_sub_frame.after(1000, func=self._update_button_prices)

    def _update_button_prices(self):
        for btn in self._ticker_button_list:
            self._ticker_button_list[btn]["text"] = btn + "\n{:>13.8f}".format(pdat.ticker.ix[btn]["last"])
        self.button_sub_frame.after(1000, func=self._update_button_prices)

    def _add_market(self):
        if self.market not in self.active_currencies:
            self.active_currencies.append(self.market)
        else:
            self.active_currencies.remove(self.market)
            pdat.remove_chart(self.market)
        self._set_market(self.market)
        self._add_market_buttons()

    def _set_market(self, mkt):
        self.title(apptitle + " - " + mkt)
        self.prev_market = self.market
        if self.market != mkt and self.market not in self.active_currencies:
            pdat.remove_chart(self.market)
        self.market = mkt
        pdat.add_chart(mkt)
        self._chart_changed = True

    def _chart_frame_update(self):
        if pdat.ticker.ix[self.market] is not None and pdat.charts[self.market] is not None and self._chart_changed:
            tick = pdat.ticker.ix[self.market]
            title_string = "{0} ({1})\nAsk:{2:10.8f} Bid:{3:10.8f}\n24hr High:{4:10.8f} 24hr Low:{5:10.8f}". \
                format(self.market, self._candle_freq, tick["lowestAsk"], tick["highestBid"], tick["high24hr"],
                       tick["low24hr"])
            self.ax1.set_title(title_string)
            data = pdat.charts[self.market]
            first_full_day = (data.index.to_period('H')[0]+1).to_timestamp()
            data = data[first_full_day:]
            #data = data.asfreq(self._candle_freq, method='pad').tail(200)
            data = data.resample(self._candle_freq).agg({'open': 'first','high': 'max','low': 'min', 'close': 'last'})
            data = data.tail(200)
            data["Date"] = data.index
            data["MPLDate"] = data['Date'].apply(lambda date: mdates.date2num(date.to_pydatetime()))
            dataAr = [tuple(x) for x in data[['MPLDate', 'open', 'high', 'low', 'close']].to_records(index=False)]
            self.ax1.clear()
            csticks = candlestick_ohlc(self.ax1, dataAr, width=self._candle_width, colorup="#50c040", colordown="#b04050")

            self.ax1.set_title(title_string)
            self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m %H:%M'))
            self.ax1.xaxis.set_major_locator(mdates.AutoDateLocator())

            self.figure.autofmt_xdate()
            self._chart_last_drawn = pdat.charts[self.market].index.values[-1]
            self._chart_changed = False
            self.mpl_canvas.draw()
        self._after_id = self.after(1500, func=self._chart_frame_update)

    def _stop_everything(self):
        self.after_cancel(self._after_id)
        pdat.stop_ticker()
        pdat.stop_charts()
        self.destroy()
        quit(0)


pdat = PoloData()
pdat.start_ticker(1)
pdat.start_charts(60, chartpath)

app = MainWindow()
app.mainloop()
