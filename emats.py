from upstox_api import api as upstox
from datetime import datetime, timedelta
from itertools import groupby
from logging import DEBUG
from utils import create_logger, ts_to_datetime
from collections import namedtuple
from indicators import ema

N50_SYMBOL = 'NIFTY_50'
LOT_SIZE = 75

SLOW_EMA = 5
FAST_EMA = 3

Crossover = namedtuple('Crossover', ['direction', 'date', 'instrument'])


class EMATS:
    def __init__(self, debug=False):
        if debug:
            self.logger = create_logger(self.__class__.__name__,
                                        console=True, level=DEBUG)
        else:
            self.logger = create_logger(self.__class__.__name__, console=False)

        self.state = []
        self.logger.debug('')
        self.logger.debug('Initialised class')

    def setup(self, client=None):
        tod = datetime.today()
        fromdt = (tod - timedelta(days=120)).date()
        todt = (tod - timedelta(days=1)).date()
        nifty = client.get_instrument_by_symbol('nse_index', N50_SYMBOL)
        ohlc_arr = self._get_ohlc(client, nifty, fromdt, todt)

        import csv
        with open('nifty_ohlc_sample.csv', 'w') as cfile:
            fields = ['timestamp', 'open', 'high', 'low', 'close']
            writer = csv.DictWriter(cfile, fieldnames=fields)
            writer.writeheader()
            for ohlc in ohlc_arr:
                row = {'timestamp': ts_to_datetime(ohlc['timestamp']).strftime('%d-%m-%Y'),
                       'open': ohlc['open'],
                       'high': ohlc['high'],
                       'low': ohlc['low'],
                       'close': ohlc['close']}
                writer.writerow(row)

        for i, ohlc in enumerate(ohlc_arr):
            if i <= SLOW_EMA + 1:
                continue
            ema_3 = []
            ema_5 = []
            ema_3 = (ema(ohlc_arr[i - FAST_EMA - 2:i - 1], n=FAST_EMA, seed=None),
                     ema(ohlc_arr[i - FAST_EMA - 1:i], n=FAST_EMA, seed=None))
            ema_5 = (ema(ohlc_arr[i - SLOW_EMA - 2:i - 1:], n=SLOW_EMA, seed=None),
                     ema(ohlc_arr[i - SLOW_EMA - 1:i], n=SLOW_EMA, seed=None))
            cross = self._check_crossover(ema_3, ema_5)
            if cross is not None:
                d = ts_to_datetime(ohlc['timestamp']).date()
                self.logger.debug('Crossover on %s. Direction = %s' %
                                  (d.strftime('%d-%m-%Y'), cross))
                self.logger.debug('3 EMAs = %.2f | %.2f' % (ema_3[0], ema_3[1]))
                self.logger.debug('5 EMAs = %.2f | %.2f' % (ema_5[0], ema_5[1]))
                self.logger.debug('-------------------------------\n')


    def _get_ohlc(self, client, instrument, fromdt, todt):
        self.logger.debug('Retrieving daily ohlc data for period %s to %s' %
                          (fromdt.strftime('%d-%m-%Y'), todt.strftime('%d-%m-%Y')))
        data = client.get_ohlc(instrument, upstox.OHLCInterval.Day_1, fromdt, todt)
        self.logger.debug('Total records  = %d' % len(data))
        data = sorted(data[:], key=lambda k: k['timestamp'])
        ohlc = [list(g)[0] for k, g in groupby(data, key=lambda k: k['timestamp'])]
        self.logger.debug('Unique records = %d' % len(ohlc))
        return ohlc

    def _check_crossover(self, fast_ma, slow_ma):
        if fast_ma is None or slow_ma is None:
            return None
        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return None
        if fast_ma[0] < slow_ma[0] and fast_ma[1] > slow_ma[1]:
            return 'up'
        elif fast_ma[0] > slow_ma[0] and fast_ma[1] < slow_ma[1]:
            return 'down'
        else:
            return None

