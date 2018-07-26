from bot import TradeBot
from datetime import date, timedelta
from upstox_api import api
from indicators import ema, sma

INDEX = 'NIFTY_50'


class EMAOption(TradeBot):
    def __init__(self, client=None):
        if not isinstance(client, api.Upstox):
            print('Provide an Upstox class object for EMAOptions.client')
            self.client = None
        else:
            self.client = client

        self.running = False
        self.messages = None
        self.activity = []

    def setup(self, message_queue):
        nifty = self.client.get_instrument_by_symbol('nse_index', INDEX)
        ohlc_from = date.today() - timedelta(days=10)
        ohlc_to = date.today() - timedelta(days=1)
        ohlc_10 = self.client.get_ohlc(nifty, api.OHLCInterval.Day_1, ohlc_from, ohlc_to)
        self.calculate_crossover(ohlc_10)
        self.messages = message_queue


        return 0

    def run(self):
        super().run()

    def process_quote(self, message):
        pass

    def process_order(self, message):
        pass

    def process_trade(self, message):
        pass

    def stop(self):
        pass

    def calculate_ema(self, ohlc_arr, n=3):
        if len(ohlc_arr) < n + 1:
            return None
        c = 2 / float(len(ohlc_arr) + 1)
        n = int(abs(n) * -1)
        arr = ohlc_arr[n:]
        ema_prev = 0.0
        ema_today = 0.0
        for ohlc in arr[1:]:
            close = float(ohlc['close'])
            if ema_prev == 0.0:
                ema_prev = close
            else:
                ema_prev = ema_today
            ema_today = (close * c) + (ema_prev * (1 - c))
            print('close - %f | ema - %f' % (close, ema_today))
        return ema_today

    def calculate_sma(self, ohlc_arr):
        total = 0
        for ohlc in ohlc_arr:
            total += float(ohlc['close'])
        return total / float(len(ohlc_arr))

    def calculate_crossover(self, ohlc_arr=None):
        if ohlc_arr is None or len(ohlc_arr) < 5:
            return 0

        ema_3 = self.calculate_ema(ohlc_arr, 3)
        print('EMA 3 = %f' % ema_3)
        ema_5 = self.calculate_ema(ohlc_arr, 5)
        print('EMA 5 = %f' % ema_5)

        crossover = ((ema_5 * (1 - 5) * (1 + 3)) - (ema_3 * (1 - 3) * (1 + 5))) / \
                    (2 * (3 - 5))

        print('CROSSOVER = %f' % crossover)
        return crossover


