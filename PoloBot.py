import tkinter as tk
import time
from os import makedirs
from os.path import expanduser
from os.path import isfile
import pandas as pd

from polodata import PoloData

# global variables
apptitle = "PoloBot v0.2"
chartpath = expanduser("~/charts/")
makedirs(chartpath, exist_ok=True)
SM_MONO = ("mono", 6)


class MainWindow(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title(apptitle)
        self.minsize(width=400, height=100)
        self.resizable(False, True)

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
                    submenu.add_command(label=coin, command=lambda m=mkt + "_" + coin: self._open_market(m))
                market_menu.add_cascade(label=mkt, menu=submenu)
            else:
                arr = sorted(pdat.markets[mkt].index)
                size = 16
                idx = 1
                while len(arr) > size:
                    sub = arr[:size]
                    submenu = tk.Menu(market_menu)
                    for coin in sub:
                        submenu.add_command(label=coin, command=lambda m=mkt + "_" + coin: self._open_market(m))
                    market_menu.add_cascade(label=mkt + str(idx), menu=submenu)
                    arr = arr[size:]
                    idx += 1
                for coin in arr:
                    submenu.add_command(label=coin, command=lambda m=mkt + "_" + coin: self._open_market(m))
                market_menu.add_cascade(label=mkt + str(idx), menu=submenu)

        menubar.add_cascade(label="Markets", menu=market_menu)
        self.config(menu=menubar)

        self.balances_frame = tk.Frame(self)
        self.balances_frame.pack(expand=1, fill='both')
        self._after_id = self.after(2500, self._display_balances)


        self.protocol("WM_DELETE_WINDOW", self._stop_everything)

    def _open_market(self, market):
        pdat.add_chart(market)
        market_window = tk.Toplevel()
        market_window.title(market + " - " + apptitle)
        market_window.maxsize(width=1600, height=1024)
        market_window.minsize(width=640, height=400)
        market = ChartFrame(market_window, market, 400, 400)
        market.pack(fill=tk.BOTH, expand=tk.YES)

    def _stop_everything(self):
        pdat.stop_ticker()
        pdat.stop_charts()
        self.destroy()
        quit(0)

    def _display_balances(self):
        if pdat.balances is not None:
            self.balances_frame.destroy()
            self.balances_frame = tk.Frame(self)
            self.balances_frame.pack(expand=1, fill='both')
            row = 0
            tk.Label(self.balances_frame, text="Currency").grid(row=row, column=0, padx=10)
            tk.Label(self.balances_frame, text="Available").grid(row=row, column=1, padx=10)
            tk.Label(self.balances_frame, text="On Orders").grid(row=row, column=2, padx=10)
            tk.Label(self.balances_frame, text="BTC Value").grid(row=row, column=3, padx=10)
            for c in sorted(pdat.balances):
                row += 1
                if float(pdat.balances[c]['btcValue']) > 0.0:
                    available = '{:.8f}'.format(float(pdat.balances[c]['available']))[:10]
                    onorders = '{:.8f}'.format(float(pdat.balances[c]['onOrders']))[:10]
                    btcvalue = '{:.8f}'.format(float(pdat.balances[c]['btcValue']))[:10]
                    tk.Label(self.balances_frame, text=c).grid(row=row, column=0, padx=10, sticky="nsew")
                    tk.Label(self.balances_frame, text=available).grid(row=row, column=1, padx=10)
                    tk.Label(self.balances_frame, text=onorders).grid(row=row, column=2, padx=10)
                    tk.Label(self.balances_frame, text=btcvalue).grid(row=row, column=3, padx=10)
        self._after_id = self.after(2500, self._display_balances)

class ChartFrame(tk.Frame):
    def __init__(self, parent, market, width, height):
        tk.Frame.__init__(self, parent)

        self.market = market
        while market not in pdat.charts:
            time.sleep(0.5)
        self.chart_data = pdat.charts[market]
        self.width = width
        self.height = height
        self.x_scale = 1
        self.y_scale = 1

        self.candle_width = 10
        self.label_width = 42
        self.offset = -1
        self.candle_freq = '30Min'
        self.visible_data_length = None
        self.indicator = 'macd'
        self.macd = {'ema_fast': 12, 'ema_slow': 26, 'ema_signal': 9}
        self.rsi = {'periods': 14}
        self.sma = [0, 0, 0]
        self.sma_cols = ['blue', 'orange', 'grey']
        self.ema = [0, 0, 0]
        self.ema_cols = ['cyan', 'yellow', 'brown']

        self._buy_window = None
        self._sell_window = None
        self._cfg_win = None

        self.market_info = tk.StringVar()
        self.market_info.set(self.market)
        title_frame = tk.Frame(self)
        title_frame.pack(side='top', fill='x')
        label = tk.Label(title_frame, textvariable=self.market_info)
        label.pack(side='top', expand=0)

        chart_frame = tk.Frame(self)
        chart_frame.pack(side='top', fill='both', expand=1)
        self.canvas = tk.Canvas(chart_frame, width=self.width, height=self.height, highlightthickness=0, bg='white')
        self.canvas.pack(side='top', fill='both', expand=1)
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Button-3>", self._config_chart)

        button_frame = tk.Frame(self)
        button_frame.pack(anchor='e')
        button = tk.Button(button_frame, text='<<', command=lambda d=-6: self.change_offset(d), relief='flat')
        button.pack(side='left')
        button = tk.Button(button_frame, text='<', command=lambda d=-1: self.change_offset(d), relief='flat')
        button.pack(side='left')
        button = tk.Button(button_frame, text='>', command=lambda d=1: self.change_offset(d), relief='flat')
        button.pack(side='left')
        button = tk.Button(button_frame, text='>>', command=lambda d=6: self.change_offset(d), relief='flat')
        button.pack(side='left')
        button = tk.Button(button_frame, text='+', command=lambda w=1.1: self.change_width(w), relief='flat')
        button.pack(side='left')
        button = tk.Button(button_frame, text='-', command=lambda w=0.9: self.change_width(w), relief='flat')
        button.pack(side='left')

        self.menubutton = tk.Menubutton(button_frame, text=self.candle_freq, relief='flat')
        self.menubutton.pack(side='left')
        self.menubutton.menu = tk.Menu(self.menubutton)
        self.menubutton['menu'] = self.menubutton.menu
        self.menubutton.menu.add_command(label='5m', command=lambda f='5Min': self.change_candles(f))
        self.menubutton.menu.add_command(label='15m', command=lambda f='15Min': self.change_candles(f))
        self.menubutton.menu.add_command(label='30m', command=lambda f='30Min': self.change_candles(f))
        self.menubutton.menu.add_command(label='1h', command=lambda f='1H': self.change_candles(f))
        self.menubutton.menu.add_command(label='3h', command=lambda f='3H': self.change_candles(f))
        self.menubutton.menu.add_command(label='6h', command=lambda f='6H': self.change_candles(f))
        self.menubutton.menu.add_command(label='1d', command=lambda f='24H': self.change_candles(f))

        button_frame = tk.Frame(self)
        button_frame.pack(anchor='nw', fill='x')
        button = tk.Button(button_frame, text='Buy', command=self._buy)
        button.pack(side='left')
        self.buy_price_label = tk.Label(button_frame, text='0.00001234')
        self.buy_price_label.pack(side='left')
        button = tk.Button(button_frame, text='Sell', command=self._sell)
        button.pack(side='left')
        self.sell_price_label = tk.Label(button_frame, text='0.00001234')
        self.sell_price_label.pack(side='left')
        button = tk.Button(button_frame, text='Auto')
        button.pack(side='right')

        self.after(1000, self._update_data)

    def _update_data(self):
        if pdat.charts[self.market] is not None:
            self.chart_data = pdat.charts[self.market]
            label_string = self.market + "\n"
            label_string += "24hr Low:" + "{:.8f}".format(pdat.ticker.ix[self.market, "low24hr"])[:10] + "  "
            label_string += "24hr High:" + "{:.8f}".format(pdat.ticker.ix[self.market, "high24hr"])[:10] + "\n"
            label_string += "Volume:" + "{:.2f}".format(pdat.ticker.ix[self.market, "baseVolume"]) + "  "
            label_string += "Change:" + "{:.2f}".format(pdat.ticker.ix[self.market, "percentChange"] * 100) + "%"
            self.market_info.set(label_string)

            self.buy_price_label["text"] = "{:.8f}".format(pdat.ticker.ix[self.market, "lowestAsk"])[:10]
            self.sell_price_label["text"] = "{:.8f}".format(pdat.ticker.ix[self.market, "highestBid"])[:10]
            self.draw_chart()
        else:
            label_string = "Waiting for market data for " + self.market
            self.market_info.set(label_string)
        self.after(1000, self._update_data)

    def draw_chart(self):
        if self.chart_data is not None:
            self.canvas.delete("chart")

            x1 = self.width * 0.01
            y1 = self.height * 0.01
            x2 = self.width * 0.99
            y2 = self.height * 0.75

            y3 = self.height * 0.79
            y4 = self.height * 0.99
            y5 = (y3 + y4) / 2

            first_full_day = (self.chart_data.index.to_period('H')[0] + 1).to_timestamp()
            data = self.chart_data[first_full_day:]

            data = data.resample(self.candle_freq).agg(
                {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum',
                 'weightedAverage': 'last'})
            self.data_length = data.shape[0]
            for a in range(2):
                data['sma' + str(a)] = data['weightedAverage'].rolling(self.sma[a]).mean()
                data['ema' + str(a)] = data['weightedAverage'].ewm(self.ema[a]).mean()

            line30 = self._get_y(30, 0, 100, y4 - y3, y4)
            line50 = self._get_y(50, 0, 100, y4 - y3, y4)
            line70 = self._get_y(70, 0, 100, y4 - y3, y4)

            m, s, h = pdat.calculate_macd(data['close'],
                                          self.macd['ema_fast'], self.macd['ema_slow'], self.macd['ema_signal'])
            data['MACDLine'] = m
            data['SignalLine'] = s
            data['Histogram'] = h

            data['rsi'] = pdat.calculate_rsi(data['close'], self.rsi['periods'])
            if self.indicator == 'rsi':
                self.canvas.create_line(x1 + self.label_width, line30, x2, line30, fill='red', tags='chart')
                self.canvas.create_line(x1 + self.label_width, line50, x2, line50, fill='black', tags='chart')
                self.canvas.create_line(x1 + self.label_width, line70, x2, line70, fill='green', tags='chart')
                self.canvas.create_text(x1 + self.label_width - 3, line50, text="RSI", anchor='e', tags='chart')
            elif self.indicator == 'macd':
                self.canvas.create_text(x1 + self.label_width - 3, line50, text="MACD", anchor='e', tags='chart')

            width = x2 - x1
            height = y2 - y1

            candle_count = int((width - self.label_width) // self.candle_width)
            visible_data = data[self.offset - candle_count:self.offset]

            y_max = visible_data["high"].max()
            y_min = visible_data["low"].min()
            v_max = visible_data["volume"].max()

            macd_max = visible_data["MACDLine"].max() if visible_data["MACDLine"].max() > visible_data[
                "SignalLine"].max() else visible_data["SignalLine"].max()
            macd_min = visible_data["MACDLine"].min() if visible_data["MACDLine"].min() < visible_data[
                "SignalLine"].min() else visible_data["SignalLine"].min()
            if macd_max < -macd_min:
                macd_max = -macd_min

            y = y_max
            y_step = ((y_max - y_min) / 10)
            for _ in range(11):
                self.canvas.create_text(x1 + self.label_width, self._get_y(y, y_min, y_max, height, y2),
                                        text="{0:<10.8f}".format(y)[:10], anchor='e', font=('Times', 6), tags='chart')
                self.canvas.create_line(x1 + self.label_width, self._get_y(y, y_min, y_max, height, y2),
                                        x2, self._get_y(y, y_min, y_max, height, y2), fill='#c0c0d0', tags='chart')
                y -= y_step

            d = visible_data.ix[0].name.strftime("%d%b %H:%M")
            self.canvas.create_text(x1 + self.label_width, y2 + 2,
                                    text=d, anchor='nw', font=('Times', 6), tags='chart')
            d = visible_data.ix[-1].name.strftime("%d%b %H:%M")
            self.canvas.create_text(x2, y2 + 2,
                                    text=d, anchor='ne', font=('Times', 6), tags='chart')

            x = x1 + self.label_width + (self.candle_width / 2)
            old_x = x
            old_macd = None
            old_sig = None
            old_sma = [None, None, None]
            old_ema = [None, None, None]
            old_rsi = None

            for i in visible_data.index:
                high = self._get_y(visible_data.ix[i, "high"], y_min, y_max, height, y2)
                low = self._get_y(visible_data.ix[i, "low"], y_min, y_max, height, y2)
                open = self._get_y(visible_data.ix[i, "open"], y_min, y_max, height, y2)
                close = self._get_y(visible_data.ix[i, "close"], y_min, y_max, height, y2)
                volume = self._get_y(visible_data.ix[i, "volume"] / 2, 0, v_max, height, y2)

                self.canvas.create_rectangle(x - (self.candle_width // 2) + 1, y2,
                                             x + (self.candle_width // 2) - 1, volume,
                                             outline='#e0e0e0', fill='#e0e0e0', tags='chart')

                self.canvas.create_line(x, high, x, low, tags='chart')
                c = '#b04050' if open < close else '#50c040'
                self.canvas.create_rectangle(x - (self.candle_width // 2) + 1, open,
                                             x + (self.candle_width // 2) - 1, close,
                                             fill=c, outline=c, tags='chart')
                if self.indicator == 'macd':
                    hist = visible_data.ix[i, "Histogram"]
                    c = '#b04050' if hist < 0 else '#50c040'
                    hist = self._get_y(hist, -macd_max, macd_max, y4 - y3, y4)
                    macd = self._get_y(visible_data.ix[i, "MACDLine"], -macd_max, macd_max, y4 - y3, y4)
                    sig = self._get_y(visible_data.ix[i, "SignalLine"], -macd_max, macd_max, y4 - y3, y4)

                    self.canvas.create_rectangle(x - (self.candle_width // 2) + 1, y5,
                                                 x + (self.candle_width // 2) - 1, hist,
                                                 outline=c, fill=c, tags='chart')

                    if old_macd is None:
                        old_macd = macd
                        old_sig = sig
                    self.canvas.create_line(old_x, old_macd, x, macd, fill='#000000', tags='chart')
                    self.canvas.create_line(old_x, old_sig, x, sig, fill='#ff0000', tags='chart')
                    old_macd = macd
                    old_sig = sig

                elif self.indicator == 'rsi':
                    rsi = self._get_y(visible_data.ix[i, "rsi"], 0, 100, y4 - y3, y4)
                    if old_rsi is None:
                        old_rsi = rsi
                    self.canvas.create_line(old_x, old_rsi, x, rsi, fill='#7f7f7f', tags='chart')
                    old_rsi = rsi

                for a in range(3):
                    if self.sma[a] > 0:
                        sma = self._get_y(visible_data.ix[i, 'sma' + str(a)], y_min, y_max, height, y2)
                        if not pd.isnull(sma):
                            if old_sma[a] is None:
                                old_sma[a] = sma
                            self.canvas.create_line(old_x, old_sma[a], x, sma, fill=self.sma_cols[a], tags='chart')
                            old_sma[a] = sma

                    if self.ema[a] > 0:
                        ema = self._get_y(visible_data.ix[i, 'ema' + str(a)], y_min, y_max, height, y2)
                        if not pd.isnull(ema):
                            if old_ema[a] is None:
                                old_ema[a] = ema
                            self.canvas.create_line(old_x, old_ema[a], x, ema, fill=self.ema_cols[a], tags='chart')
                            old_ema[a] = ema

                old_x = x
                x += self.candle_width

            self.canvas.create_rectangle(x1 + self.label_width, y1, x2, y2, fill='', tags='chart')
            self.canvas.create_rectangle(x1 + self.label_width, y3, x2, y4, fill='', tags='chart')

    def _get_y(self, y_in, y_min, y_max, height, bottom):
        y_out = ((y_in - y_min) / (y_max - y_min)) * height
        y_out = bottom - y_out
        if y_out > bottom:
            y_out = bottom
        if y_out < bottom - height:
            y_out = bottom - height
        return y_out

    def change_offset(self, d):
        self.offset += d

        if self.offset > -1:
            self.offset = -1
        if self.offset < -self.data_length + 12:
            self.offset = -self.data_length + 12

        self.draw_chart()

    def change_width(self, w):
        self.candle_width *= w
        if self.candle_width < 2:
            self.candle_width = 2
        if self.candle_width > 100:
            self.candle_width = 100
        self.draw_chart()

    def change_candles(self, s):
        self.candle_freq = s
        self.menubutton["text"] = s
        self.draw_chart()

    def on_resize(self, event):
        self.x_scale = float(event.width) / self.width
        self.y_scale = float(event.height) / self.height
        self.width = event.width
        self.height = event.height
        self.canvas.config(width=self.width, height=self.height-100)
        self.canvas.scale("all", 0, 0, self.x_scale, self.y_scale)
        self.candle_width *= self.x_scale
        self.label_width *= self.x_scale

    def _config_chart(self, event):
        if self._cfg_win is None:
            self._cfg_win = tk.Toplevel(self)
            self._cfg_win.title("Config Chart")
            tk.Label(self._cfg_win, text="SMA 1").grid(row=0, column=0)
            self.sma1 = tk.Entry(self._cfg_win, width=4)
            self.sma1.insert(0, self.sma[0])
            self.sma1.grid(row=0, column=1)
            tk.Label(self._cfg_win, text="SMA 2").grid(row=1, column=0)
            self.sma2 = tk.Entry(self._cfg_win, width=4)
            self.sma2.insert(0, self.sma[1])
            self.sma2.grid(row=1, column=1)
            tk.Label(self._cfg_win, text="SMA 3").grid(row=2, column=0)
            self.sma3 = tk.Entry(self._cfg_win, width=4)
            self.sma3.insert(0, self.sma[2])
            self.sma3.grid(row=2, column=1)
            tk.Label(self._cfg_win, text="EMA 1").grid(row=0, column=2)
            self.ema1 = tk.Entry(self._cfg_win, width=4)
            self.ema1.insert(0, self.ema[0])
            self.ema1.grid(row=0, column=3)
            tk.Label(self._cfg_win, text="EMA 2").grid(row=1, column=2)
            self.ema2 = tk.Entry(self._cfg_win, width=4)
            self.ema2.insert(0, self.ema[1])
            self.ema2.grid(row=1, column=3)
            tk.Label(self._cfg_win, text="EMA 3").grid(row=2, column=2)
            self.ema3 = tk.Entry(self._cfg_win, width=4)
            self.ema3.insert(0, self.ema[2])
            self.ema3.grid(row=2, column=3)

            self.indicator_mode = tk.StringVar()
            self.indicator_mode.set(self.indicator)
            tk.Radiobutton(self._cfg_win, text="MACD", variable=self.indicator_mode, value='macd').grid(row=3, column=0)
            tk.Radiobutton(self._cfg_win, text="RSI", variable=self.indicator_mode, value='rsi').grid(row=3, column=2)

            tk.Label(self._cfg_win, text="MACD Fast EMA").grid(row=4, column=0)
            self.macd_f_ema = tk.Entry(self._cfg_win, width=4)
            self.macd_f_ema.insert(0, self.macd['ema_fast'])
            self.macd_f_ema.grid(row=4, column=1)
            tk.Label(self._cfg_win, text="MACD Slow EMA").grid(row=5, column=0)
            self.macd_s_ema = tk.Entry(self._cfg_win, width=4)
            self.macd_s_ema.insert(0, self.macd['ema_slow'])
            self.macd_s_ema.grid(row=5, column=1)
            tk.Label(self._cfg_win, text="MACD Signal EMA").grid(row=6, column=0)
            self.macd_sig_ema = tk.Entry(self._cfg_win, width=4)
            self.macd_sig_ema.insert(0, self.macd['ema_signal'])
            self.macd_sig_ema.grid(row=6, column=1)
            tk.Label(self._cfg_win, text="RSI Periods").grid(row=4, column=2)
            self.rsi_periods = tk.Entry(self._cfg_win, width=4)
            self.rsi_periods.insert(0, self.rsi['periods'])
            self.rsi_periods.grid(row=4, column=3)

            tk.Button(self._cfg_win, text="OK", command=self.config_ok).grid(row=7, column=3, sticky='e')

            self._cfg_win.protocol("WM_DELETE_WINDOW", self._cfg_win_close)

    def config_ok(self):
        try:
            self.sma = [int(self.sma1.get()), int(self.sma2.get()), int(self.sma3.get())]
            self.ema = [int(self.ema1.get()), int(self.ema2.get()), int(self.ema3.get())]
            self.indicator = self.indicator_mode.get()
            self.macd['ema_fast'] = int(self.macd_f_ema.get())
            self.macd['ema_slow'] = int(self.macd_s_ema.get())
            self.macd['ema_signal'] = int(self.macd_sig_ema.get())
            self.rsi['periods'] = int(self.rsi_periods.get())

            self._cfg_win.destroy()
            self._cfg_win = None
            self.draw_chart()
        except:
            print("Error!")

    def _cfg_win_close(self):
        self._cfg_win.destroy()
        self._cfg_win = None

    def _buy(self):
        if self._buy_window is None:
            self._buy_window = BuyWindow(self.market)
            self._buy_window.protocol("WM_DELETE_WINDOW", self._buy_window_close)

    def _buy_window_close(self):
        self._buy_window.destroy()
        self._buy_window = None

    def _sell(self):
        if self._sell_window is None:
            self._sell_window = SellWindow(self.market)
            self._sell_window.protocol("WM_DELETE_WINDOW", self._sell_window_close)

    def _sell_window_close(self):
        self._sell_window.destroy()
        self._sell_window = None

class APIKeyInput(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        self.parent = parent
        self.api_key = ""
        self.api_secret = ""
        tk.Label(self, text="Poloniex API Access", font=(24)).grid(row=0, column=0, columnspan=4)
        tk.Label(self, text="API Key").grid(row=1, column=0)
        self._api_key_entry = tk.Entry(self, width=40)
        self._api_key_entry.grid(row=1, column=1, columnspan=3)
        tk.Label(self, text="API Secret").grid(row=2, column=0)
        self._api_secret_entry = tk.Entry(self, width=40)
        self._api_secret_entry.grid(row=2, column=1, columnspan=3)
        tk.Button(self, text='View Only', command=self._view_only).grid(row=3, column=2)
        tk.Button(self, text='Full Access', command=self._test_entry).grid(row=3, column=3)
        self._warning_label = tk.Label(self, text='', fg='red')
        self._warning_label.grid(row=4, column=0, columnspan=4)

    def _view_only(self):
        self.api_key = ''
        self.api_secret = ''
        self.parent.destroy()

    def _test_entry(self):
        self.api_key = self._api_key_entry.get()
        self.api_secret = self._api_secret_entry.get()
        warning = ''
        if len(self.api_key) != 35:
            warning += 'API Key error: format is 4 groups of 8 seperated by dashes!'
        if len(self.api_secret) != 128:
            if warning != '':
                warning += '\n'
            warning += 'API Secret error: should be 128 alphanumeric digits!'
        if warning == '':
            self.parent.destroy()

        else:
            self._warning_label["text"] = warning

class BuyWindow(tk.Toplevel):
    def __init__(self, market):
        tk.Toplevel.__init__(self)
        self.resizable(False, True)
        self.market = market
        self.title("Buy " + market.split("_")[1])

        self.frame = tk.Frame(self)
        self.frame.pack(fill='both', expand=0)

        tk.Label(self.frame, text="Available:").grid(row=0, column=0, pady=10)
        self.available = tk.Label(self.frame, width=12, text=pdat.balances[self.market.split('_')[0]]["available"])
        self.available.grid(row=0, column=1, sticky='e')
        tk.Label(self.frame, text=self.market.split("_")[0]).grid(row=0, column=2, sticky="w")

        tk.Label(self.frame, text="Price:").grid(row=1, column=0, padx=10)
        prc_val = (self.register(self._validate_price), '%P')
        self.price = tk.Entry(self.frame, width=12, justify='right', validate='focusout', validatecommand=prc_val)
        self.price.grid(row=1, column=1)
        tk.Label(self.frame, text=self.market.split("_")[0]).grid(row=1, column=2, sticky="w")

        tk.Label(self.frame, text="Amount:").grid(row=2, column=0, padx=10)
        amt_val = (self.register(self._validate_amount), '%P')
        self.amount = tk.Entry(self.frame, width=12, justify='right', validate='focusout', validatecommand=amt_val)
        self.amount.grid(row=2, column=1)
        tk.Label(self.frame, text=self.market.split("_")[1]).grid(row=2, column=2, sticky="w")

        tk.Label(self.frame, text="Total:").grid(row=3, column=0, padx=10)
        tot_val = (self.register(self._validate_total), '%P')
        self.total = tk.Entry(self.frame, width=12, text='', justify='right', validate='focusout', validatecommand=tot_val)
        self.total.grid(row=3, column=1)
        tk.Label(self.frame, text=self.market.split("_")[0]).grid(row=3, column=2, sticky="w")

        self.result_label = tk.Label(self.frame, text="")
        self.result_label.grid(row=4, column=0, columnspan=2)

        tk.Button(self.frame, text="Buy", command=self._buy).grid(row=4, column=2, padx=10, pady=10)

        self.price.delete(1, 'end')
        self.price.insert(0, '{:.8f}'.format(pdat.ticker.ix[self.market, 'lowestAsk'])[:9])
        self.amount.delete(1, 'end')
        self.amount.insert(0, '0.0')
        self.total.delete(1, 'end')
        self.total.insert(0, '0.0')

    def _validate_amount(self, value_if_allowed):
        try:
            v = float(value_if_allowed)
            self.total.delete(1, 'end')
            self.total.insert(0, '{:.8f}'.format(float(self.price.get()) * v)[:9])
            return True
        except ValueError:
            return False

    def _validate_price(self, value_if_allowed):
        try:
            v = float(value_if_allowed)
            self.total.delete(1, 'end')
            self.total.insert(0, '{:.8f}'.format(float(self.amount.get()) * v)[:9])
            return True
        except ValueError:
            return False

    def _validate_total(self, value_if_allowed):
        try:
            v = float(value_if_allowed)
            self.amount.delete(1, 'end')
            self.amount.insert(0, '{:.8f}'.format(v / float(self.price.get()))[:9])
            return True
        except ValueError:
            return False

    def _buy(self):
        price = self.price.get()
        amount = self.amount.get()
        print("Buy", self.market, price, amount)
        result = pdat.buy(self.market, price, amount)
        self.result_label['text'] = result

class SellWindow(tk.Toplevel):
    def __init__(self, market):
        tk.Toplevel.__init__(self)
        self.resizable(False, True)
        self.market = market
        self.title = "Sell " + market.split("_")[1]
    def __init__(self, market):
        tk.Toplevel.__init__(self)
        self.resizable(False, True)
        self.market = market
        self.title("Sell " + market.split("_")[1])

        self.frame = tk.Frame(self)
        self.frame.pack(fill='both', expand=0)

        tk.Label(self.frame, text="Available:").grid(row=0, column=0, pady=10)
        self.available = tk.Label(self.frame, width=12, text=pdat.balances[self.market.split('_')[1]]["available"])
        self.available.grid(row=0, column=1, sticky='e')
        tk.Label(self.frame, text=self.market.split("_")[1]).grid(row=0, column=2, sticky="w")

        tk.Label(self.frame, text="Price:").grid(row=1, column=0, padx=10)
        prc_val = (self.register(self._validate_price), '%P')
        self.price = tk.Entry(self.frame, width=12, justify='right', validate='focusout', validatecommand=prc_val)
        self.price.grid(row=1, column=1)
        tk.Label(self.frame, text=self.market.split("_")[0]).grid(row=1, column=2, sticky="w")

        tk.Label(self.frame, text="Amount:").grid(row=2, column=0, padx=10)
        amt_val = (self.register(self._validate_amount), '%P')
        self.amount = tk.Entry(self.frame, width=12, justify='right', validate='focusout', validatecommand=amt_val)
        self.amount.grid(row=2, column=1)
        tk.Label(self.frame, text=self.market.split("_")[1]).grid(row=2, column=2, sticky="w")

        tk.Label(self.frame, text="Total:").grid(row=3, column=0, padx=10)
        tot_val = (self.register(self._validate_total), '%P')
        self.total = tk.Entry(self.frame, width=12, text='', justify='right', validate='focusout', validatecommand=tot_val)
        self.total.grid(row=3, column=1)
        tk.Label(self.frame, text=self.market.split("_")[0]).grid(row=3, column=2, sticky="w")

        self.result_label = tk.Label(self.frame, text="")
        self.result_label.grid(row=4, column=0, columnspan=2)

        tk.Button(self.frame, text="Sell", command=self._sell).grid(row=4, column=2, padx=10, pady=10)

        self.price.delete(1, 'end')
        self.price.insert(0, '{:.8f}'.format(pdat.ticker.ix[self.market, 'highestBid'])[:9])
        self.amount.delete(1, 'end')
        self.amount.insert(0, '0.0')
        self.total.delete(1, 'end')
        self.total.insert(0, '0.0')

    def _validate_amount(self, value_if_allowed):
        try:
            v = float(value_if_allowed)
            self.total.delete(1, 'end')
            self.total.insert(0, '{:.8f}'.format(float(self.price.get()) * v)[:9])
            return True
        except ValueError:
            return False

    def _validate_price(self, value_if_allowed):
        try:
            v = float(value_if_allowed)
            self.total.delete(1, 'end')
            self.total.insert(0, '{:.8f}'.format(float(self.amount.get()) * v)[:9])
            return True
        except ValueError:
            return False

    def _validate_total(self, value_if_allowed):
        try:
            v = float(value_if_allowed)
            self.amount.delete(1, 'end')
            self.amount.insert(0, '{:.8f}'.format(v / float(self.price.get()))[:9])
            return True
        except ValueError:
            return False

    def _sell(self):
        price = self.price.get()
        amount = self.amount.get()
        print("Sell", self.market, price, amount)
        result = pdat.sell(self.market, price, amount)
        self.result_label['text'] = result



# quick and dirty api key input and save WARNING!! Saves as plain text
filename = chartpath + '.key'
if isfile(filename):
    with open(filename,'r') as f:
        api_key = f.readline().strip()
        api_secret = f.readline().strip()
else:
    root = tk.Tk()
    root.title("API Access " + apptitle)
    api_frame = APIKeyInput(root)
    api_frame.pack(fill=tk.BOTH, expand=tk.YES)
    root.mainloop()

    api_key = api_frame.api_key
    api_secret = api_frame.api_secret
    del root
    del api_frame

    with open(filename,'w') as f:
        data = api_key + "\n" + api_secret
        f.write(data)

pdat = PoloData(api_key, api_secret)
pdat.start_ticker(1)
pdat.start_charts(60, chartpath)
if api_secret != "":
    pdat.start_balances(2)


app = MainWindow()
app.mainloop()
