from upstox_api import api as upstox
from datetime import datetime, timedelta
from itertools import groupby
from logging import DEBUG
import utils
import indicators
import csv
import os
import configparser

EMA_PERIOD = timedelta(days=90)
CSV_FIELDS = ['symbol', 'date', 'close', 'fast_ema', 'slow_ema']
DATA_DIR = os.getcwd() + "\\EMATS_files\\"

CROSSOVER_FILE = DATA_DIR + "crossovers.txt"


class EMATS:
    def __init__(self, instrument=None, debug=False, showinfo=False):
        if debug:
            self.logger = utils.create_logger(self.__class__.__name__,
                                              console=showinfo,
                                              level=DEBUG)
        else:
            self.logger = utils.create_logger(self.__class__.__name__,
                                              console=showinfo)

        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

        if instrument is None or not isinstance(instrument, upstox.Instrument):
            self.logger.error('Invalid Instrument given in constructor.')
            return
        self.inst = instrument
        self.ema_file = None
        self.fast = 0
        self.slow = 0
        self.xover = 0
        self.last_record = {}
        self.trade_params = {}

        now = datetime.now()
        opening, closing = utils.get_trade_hours(now.date())
        if utils.is_trade_day(now.date()) and now > closing:
            self.today = now.date()
        else:
            self.today = utils.prev_trade_day(now.date())
        self.prev_day = utils.prev_trade_day(self.today)
        self.next_day = utils.next_trade_day(self.today)

        self.logger.debug('')
        self.logger.info('Created EMATS for %s' % self.inst.symbol.upper())
        self.logger.debug('Current working day  : %s' % self.today.strftime('%d-%m-%Y'))
        self.logger.debug('Next working day     : %s' % self.next_day.strftime('%d-%m-%Y'))
        self.logger.debug('Previous working day : %s' % self.prev_day.strftime('%d-%m-%Y'))

    def setup(self, client=None, fast=3, slow=5):
        self.fast = fast
        self.slow = slow
        if self._load_trade_params():
            self.logger.info('Loaded Crossover info from file')
        else:
            self._update_datafiles(client)
            self._load_trade_params()

    def _update_datafiles(self, client):
        self.logger.debug('Updating datafiles')
        self.ema_file = DATA_DIR + self.inst.symbol.lower() + '_EMA.csv'
        self.logger.debug('EMA file = %s' % self.ema_file)
        if not os.path.isfile(self.ema_file):
            if self._create_ema_file(client):
                self.logger.debug('Created new EMA file')
        last = self._load_ema()
        if last['date'] != self.today:
            self.logger.info('Updating EMA file')
            if last['date'] - self.today == timedelta(days=1):
                ohlc_arr = self._get_ohlc(client, self.inst, self.today, self.today)
            else:
                fromdt = last['date'] + timedelta(days=1)
                todt = self.today
                ohlc_arr = self._get_ohlc(client, self.inst, fromdt, todt)
            records = self._create_ema_records(ohlc_arr,
                                               fast_prev=last['fast_ema'],
                                               slow_prev=last['slow_ema'])
            with open(self.ema_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                for record in records:
                    self.logger.debug('%s %.2f | %.2f' % (record['date'],
                                                          record['fast_ema'],
                                                          record['slow_ema']))
                    writer.writerow(record)
            last = records[-1]
            last['date'] = datetime.strptime(last['date'], '%d-%m-%Y').date()
            self.logger.debug('Added %d records to EMA file' % len(records))
        else:
            self.logger.debug('EMA File up-to-date')
        self.xover = self._calculate_crossover(last)
        self.last_record = last
        if self._save_trade_params():
            self.logger.debug('Saved new EMA trade params')

    def _load_ema(self):
        self.logger.debug('Loading EMAs from file')
        last = {}
        with open(self.ema_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            data = []
            for row in reader:
                data.append(row)
            last['symbol'] = data[-1]['symbol']
            last['date'] = datetime.strptime(data[-1]['date'], '%d-%m-%Y').date()
            last['close'] = float(data[-1]['close'])
            last['slow_ema'] = float(data[-1]['slow_ema'])
            last['fast_ema'] = float(data[-1]['fast_ema'])
        return last

    def _create_ema_file(self, client):
        tod = datetime.today()
        opening, cutoff = utils.get_trade_hours(tod)
        if datetime.now() < cutoff:
            todt = (tod - timedelta(days=1)).date()
        else:
            todt = tod.date()
        fromdt = (todt - EMA_PERIOD)
        ohlc_arr = self._get_ohlc(client, self.inst, fromdt, todt)
        records = self._create_ema_records(ohlc_arr)

        with open(self.ema_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for record in records:
                self.logger.debug('%s %.2f | %.2f' % (record['date'],
                                                      record['fast_ema'],
                                                      record['slow_ema']))
                writer.writerow(record)
            self.logger.debug('Wrote %d records to file' % len(records))
        return True

    def _create_ema_records(self, ohlc_arr, fast_prev=0, slow_prev=0):
        sym = self.inst.symbol.upper()
        self.logger.debug('Generating EMA records')
        records = []
        if len(ohlc_arr) < 2:
            if not fast_prev or not slow_prev:
                return records
            ohlc = ohlc_arr[0]
            fast_ema = indicators.ema(close=ohlc['close'],
                                      ema_prev=fast_prev,
                                      days=self.fast)
            slow_ema = indicators.ema(close=ohlc['close'],
                                      ema_prev=slow_prev,
                                      days=self.slow)
            ohlc_date = utils.ts_to_datetime(ohlc['timestamp']).strftime('%d-%m-%Y')
            r = {'symbol': sym,
                 'date': ohlc_date,
                 'close': float(ohlc['close']),
                 'fast_ema': fast_ema,
                 'slow_ema': slow_ema}
            records.append(r)
        else:
            if not fast_prev:
                fast_prev = ohlc_arr[0]['close']
            if not slow_prev:
                slow_prev = ohlc_arr[0]['close']
            for ohlc in ohlc_arr[1:]:
                fast_ema = indicators.ema(close=ohlc['close'],
                                          ema_prev=fast_prev,
                                          days=self.fast)
                fast_prev = fast_ema

                slow_ema = indicators.ema(close=ohlc['close'],
                                          ema_prev=slow_prev,
                                          days=self.slow)
                slow_prev = slow_ema
                ohlc_date = utils.ts_to_datetime(ohlc['timestamp']).strftime('%d-%m-%Y')
                r = {'symbol': sym,
                     'date': ohlc_date,
                     'close': float(ohlc['close']),
                     'fast_ema': fast_ema,
                     'slow_ema': slow_ema}
                records.append(r)
        return records

    def _get_ohlc(self, client, instrument, fromdt, todt):
        self.logger.debug('Retrieving daily ohlc data for period %s to %s' %
                          (fromdt.strftime('%d-%m-%Y'), todt.strftime('%d-%m-%Y')))
        if fromdt == todt:
            ohlc = client.get_ohlc(instrument,
                                   upstox.OHLCInterval.Day_1,
                                   fromdt,
                                   todt)
        else:
            data = client.get_ohlc(instrument, upstox.OHLCInterval.Day_1, fromdt, todt)
            data = sorted(data[:], key=lambda k: k['timestamp'])
            ohlc = [list(g)[0] for k, g in groupby(data, key=lambda k: k['timestamp'])]
        self.logger.debug('Records received = %d' % len(ohlc))
        return ohlc

    def _calculate_crossover(self, ema_record):
        xover = (ema_record['slow_ema'] * (1 - self.slow) * (1 + self.fast) -
                 ema_record['fast_ema'] * (1 - self.fast) * (1 + self.slow)) / \
                (2 * (self.fast - self.slow))
        return utils.round_off(xover, 0.5)

    def _save_trade_params(self):
        data = configparser.ConfigParser()
        if os.path.exists(CROSSOVER_FILE):
            data.read(CROSSOVER_FILE)
        sym = self.inst.symbol.upper()
        data[sym] = {
            'date': self.last_record['date'].strftime('%d-%m-%Y'),
            'close': self.last_record['close'],
            'fast_ema': self.last_record['fast_ema'],
            'slow_ema': self.last_record['slow_ema'],
            'crossover': self.xover,
            'crossover_date': self.next_day.strftime('%d-%m-%Y')
        }
        if self.last_record['fast_ema'] <= self.last_record['slow_ema']:
            data[sym]['action'] = 'BUY'
        else:
            data[sym]['action'] = 'SELL'
        with open(CROSSOVER_FILE, 'w') as f:
            data.write(f)

    def _load_trade_params(self):
        data = configparser.ConfigParser()
        if os.path.exists(CROSSOVER_FILE):
            data.read(CROSSOVER_FILE)
        try:
            tp = data[self.inst.symbol.upper()]
        except KeyError:
            self.logger.debug('No trade params found')
            return False
        dt = datetime.strptime(tp['date'], '%d-%m-%Y').date()
        cdt = datetime.strptime(tp['crossover_date'], '%d-%m-%Y').date()

        self.trade_params['date'] = dt
        self.trade_params['close'] = float(tp['close'])
        self.trade_params['slow_ema'] = float(tp['slow_ema'])
        self.trade_params['fast_ema'] = float(tp['fast_ema'])
        self.trade_params['crossover'] = float(tp['crossover'])
        self.trade_params['crossover_date'] = cdt
        if self.trade_params['crossover_date'] == self.today:
            return True
        return False
