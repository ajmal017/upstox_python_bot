import logging
from collections import namedtuple
from time import sleep
from datetime import date, timedelta
from upstox_api import api
from utils import BUY, SELL, get_expiry_dates
from indicators import gann
from bot import TradeBot
from logger import create_logger


N50_SYMBOL = 'NIFTY_50'
LOT_SIZE = 75

MAX_CYCLES = 2

Levels = namedtuple('Levels', ['buy', 'stoploss', 'target'])


class Gann(TradeBot):
    def __init__(self, client, debug=False):
        super().__init__()
        if not isinstance(client, api.Upstox):
            print('Provide an Upstox class object for gann.client')
            self.client = None
        else:
            self.client = client

        self.daemon = True
        self.running = False
        self.messages = None
        self.cycles = 0
        if debug:
            self.logger = create_logger('gann_opt_')
        else:
            self.logger = create_logger('gann_opt_')

        self.holdings = 0
        self.tally = 0.0
        self.parent_oid = None
        self.target_oid = None
        self.sl_oid = None
        self.activity = []

        self.gann_buy = 4
        self.gann_sl = 5
        self.gann_target = -1

        self.pe_inst = None
        self.pe_levels = Levels(0, 0, 0)
        self.pe_prev_ltp = None

        self.ce_inst = None
        self.ce_levels = Levels(0, 0, 0)
        self.ce_prev_ltp = None
        self.logger.info('===============================')
        self.logger.info('Created Gann Tradebot')

    def setup(self, message_queue=None):
        if 'setup complete' in self.activity and self.messages is not None:
            self.logger.debug('Initialise function called twice')
            return
        self.logger.debug('Creating options symbols')
        self.messages = message_queue
        tod = date.today()
        exp = get_expiry_dates(tod.month)[-1]
        if exp - tod < timedelta(days=6):
            exp = get_expiry_dates(tod.month + 1)[-1]
        nifty = self.client.get_instrument_by_symbol('nse_index', N50_SYMBOL)
        data = self.client.get_live_feed(nifty, api.LiveFeedType.Full)
        nearest_100 = int(float(data['close']) / 100) * 100
        self.logger.debug('Base price for options = %d' % nearest_100)

        pe_sym = self._get_put_symbol(nearest_100, exp)
        self.pe_inst = self.client.get_instrument_by_symbol('nse_fo', pe_sym)
        while self.client.subscribe(self.pe_inst, api.LiveFeedType.LTP)['success'] is not True:
            sleep(1)
        else:
            self.logger.debug('Subscribed to %s' % self.pe_inst.symbol)

        ce_sym = self._get_call_symbol(nearest_100, exp)
        self.ce_inst = self.client.get_instrument_by_symbol('nse_fo', ce_sym)
        while self.client.subscribe(self.ce_inst, api.LiveFeedType.LTP)['success'] is not True:
            sleep(1)
        else:
            self.logger.debug('Subscribed to %s' % self.ce_inst.symbol)

        self.activity.append('setup complete')
        self.logger.debug(self.activity[-1])
        return (ce_sym, pe_sym)

    def _get_put_symbol(self, nearest_100, exp):
        puts = []
        for i in range(-500, 0, 100):
            sym = 'nifty' + exp.strftime('%y%b').lower() + str(nearest_100 + i) + 'pe'
            feed = self.client.get_live_feed(self.client.get_instrument_by_symbol('nse_fo', sym),
                                             api.LiveFeedType.Full)
            if feed['close'] > 50.0 and feed['close'] < 100:
                puts.append(feed)
        puts_sorted = sorted(puts, key=lambda k: float(k['close']))
        pe_sym = puts_sorted[0]['symbol'].lower()
        return pe_sym

    def _get_call_symbol(self, nearest_100, exp):
        calls = []
        for i in range(0, 500, 100):
            sym = 'nifty' + exp.strftime('%y%b').lower() + str(nearest_100 + i) + 'ce'
            feed = self.client.get_live_feed(self.client.get_instrument_by_symbol('nse_fo', sym),
                                             api.LiveFeedType.Full)
            if feed['close'] > 50.0 and feed['close'] < 100:
                calls.append(feed)
        calls_sorted = sorted(calls, key=lambda k: float(k['close']))
        ce_sym = calls_sorted[0]['symbol'].lower()
        return ce_sym

    def _calculate_initial_values(self, quote):
        if 'initialised all' in self.activity:
            self.logger.debug('Initialise function called twice')
            return
        sym = quote['symbol'].lower()
        ltp = float(quote['ltp'])
        levels = gann(ltp)
        if sym == self.pe_inst.symbol.lower() and \
           'initialised pe' not in self.activity:
            self.pe_levels = Levels(levels[self.gann_buy],
                                    levels[self.gann_target],
                                    levels[self.gann_sl])
            self.pe_prev_ltp = ltp
            self.activity.append('initialised %s' % sym[-2:])
        elif sym == self.ce_inst.symbol.lower() and \
                'initialised ce' not in self.activity:
            self.ce_levels = Levels(levels[self.gann_buy],
                                    levels[self.gann_target],
                                    levels[self.gann_sl])
            self.ce_prev_ltp = ltp
            self.activity.append('initialised %s' % sym[-2:])
        elif 'initialised ce' in self.activity and 'initialised pe' in self.activity:
            self.activity.append('initialised all')
            self.logger.debug(self.activity[-1])
            return
        self.logger.debug(self.activity[-1])

        print('-----')
        print('Initial values for %s - ' % sym)
        print('Buy Trigger        - %f' % levels[self.gann_buy])
        print('Sell Trigger       - %f' % levels[self.gann_target])
        print('Initial SL Trigger - %f' % levels[self.gann_sl])
        print('-----')
        self.logger.debug('Initialised values for %s' % sym)

    def run(self):
        if not self.running:
            self.running = True
        self.logger.info('Starting run loop.')
        while self.running:
            while not self.messages.empty():
                m = self.messages.get()
                if m[0] == 'q':
                    self.process_quote(m[1])
                elif m[0] == 'o':
                    self.process_order(m[1])
                else:
                    self.process_trade(m[1])
                self.messages.task_done()
            sleep(0.5)

    def process_quote(self, message):
        sym = message['symbol'].lower()
        if 'initialised all' not in self.activity:
            self._calculate_initial_values(message)
            return
        if self.cycles == MAX_CYCLES:
            print('\nGann bot completed allowed trade cycles. Shutting down...')
            self.logger.info('Trade cycles complete. Shutting down')
            self.stop()
        if sym == self.pe_inst.symbol.lower():
            self._pe_gann(message)
            return True
        elif sym == self.ce_inst.symbol.lower():
            self._ce_gann(message)
            return True
        return False

    def process_order(self, message):
        status = str(message['status']).lower()
        act = self.activity[-1]
        sym = message['symbol'].lower()
        tt = message['transaction_type']
        oid = str(message['order_id'])

        if 'failed' in act:
            return

        if 'ordered' in act:
            if tt == BUY and status in ('rejected', 'cancelled'):
                if sym == self.pe_inst.symbol.lower():
                    self.activity.append('pe_position_failed')
                elif sym == self.pe_inst.symbol.lower():
                    self.activity.append('ce_position_failed')
            elif tt == SELL:
                if message['parent_order_id'] != self.parent_oid:
                    return
                elif status == 'open':
                    self.target_oid = str(oid)
                elif status == 'trigger pending':
                    self.sl_oid = (oid)

    def process_trade(self, message):
        sym = message['symbol'].lower()
        qty = int(message['quantity'])
        oid = str(message['order_id'])
        tt = str(message['transaction_type'])
        status = str(message['status'])
        poid = None
        if message['parent_order_id'] != 'NA':
            poid = str(message['parent_order_id'])

        if tt == BUY:
            if status in ('complete', 'completed'):
                self.holdings += qty
                self.logger.info('Current holdings for %s = %d' % (sym, self.holdings))
                if poid is None:
                    self.parent_oid = oid
                else:
                    self.parent_oid = poid

                if sym == self.pe_inst.symbol.lower():
                    self.activity.append('pe_position_open')
                elif sym == self.ce_inst.symbol.lower():
                    self.activity.append('ce_position_open')
        else:
            if poid is not None and poid == self.parent_oid \
               and status in ('complete', 'completed'):
                self.holdings -= qty
                self.sell_oids.append(oid)
                if self.holdings <= 0:
                    # self.log_trade(parent_oid)
                    self.holdings = 0
                    self.sell_oids.clear()
                    self.parent_oid = None
                    self.sl_oid = None
                    self.target_oid = None
                    self.cycles += 1
                    if sym == self.pe_inst.symbol.lower():
                        self.activity.append('pe_position_closed')
                    elif sym == self.ce_inst.symbol.lower():
                        self.activity.append('ce_position_closed')
        self._log_trade(message)

    def stop(self):
        print("Stopping Gann Robot")
        self.activity.append('stopped bot')
        with open('gann_log.txt', 'w') as gl:
            for act in self.activity:
                gl.write(act + '\n')
        self.running = False

    def _pe_gann(self, message):
        ltp = message['ltp']
        act = self.activity[-1]

        if ltp > self.pe_levels.buy + ltp * 0.01:
            return

        if ltp > self.pe_levels.buy and \
           act in ('initialised all', 'ce_position_closed') and \
           "ce_sell_target" not in self.activity:
            lots = self._get_tradeable_lots(ltp, 0.9)
            self.client.place_order(api.TransactionType.Buy,
                                    self.pe_inst,
                                    LOT_SIZE * lots,
                                    api.OrderType.Limit,
                                    api.ProductType.OneCancelsOther,
                                    self.pe_levels.buy,
                                    None,
                                    0,
                                    api.DurationType.DAY,
                                    abs(self.pe_levels.buy - self.pe_levels.stoploss),
                                    abs(self.pe_levels.target - self.pe_levels.buy),
                                    20)
            print('Placed buy order for %s at %f' %
                  (message['symbol'], ltp))
            print('\nTarget = %f\nStoploss = %f' % (self.pe_levels.target,
                                                    self.pe_levels.stoploss))
            self.activity.append('pe_ordered')
            return
        elif act == 'pe_ordered':
            return
        elif act == 'pe_position_open':
            if ltp < self.pe_levels.stoploss and self.parent_oid is not None:
                print('Stoploss reached for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('pe_sell_sl')
            elif ltp > self.pe_levels.target:
                print('Profit target reached for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('pe_sell_target')
        elif ltp < self.pe_prev_ltp:
            levels = gann(ltp)
            self.pe_levels = Levels(levels[self.gann_buy],
                                    levels[self.gann_target],
                                    levels[self.gann_sl])
            print('\nRecalculated prices for %s - ' % self.pe_inst.symbol)
            print('Buy Trigger        - %f' % self.pe_levels.buy)
            print('Sell Trigger       - %f' % self.pe_levels.target)
            print('SL Trigger - %f' % self.pe_levels.stoploss)
            self.pe_prev_ltp = message['ltp']

    def _ce_gann(self, message):
        ltp = message['ltp']
        act = self.activity[-1]

        if ltp > self.ce_levels.buy + ltp * 0.01:
            return

        if ltp > self.ce_levels.buy and act in ('initialised', 'pe_position_closed') and \
           "pe_sell_target" not in self.activity:
            lots = self._get_tradeable_lots(ltp, 0.9)
            self.client.place_order(api.TransactionType.Buy,
                                    self.ce_inst,
                                    lots * LOT_SIZE,
                                    api.OrderType.Limit,
                                    api.ProductType.OneCancelsOther,
                                    self.ce_levels.buy,
                                    None,
                                    0,
                                    api.DurationType.DAY,
                                    abs(self.ce_levels.buy - self.ce_levels.stoploss),
                                    abs(self.ce_levels.target - self.ce_levels.buy),
                                    20)
            print('Placed buy order for %s at %f' %
                  (message['symbol'], ltp))
            print('\nTarget = %f\nStoploss = %f' % (self.ce_target, self.ce_sl))
            self.activity.append('ce_ordered')
            return
        elif act == 'ce_ordered':
            return
        elif act == 'ce_position_open':
            if ltp < self.ce_sl and self.parent_oid is not None:
                print('Stoploss reached for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('ce_sell_sl')
            elif ltp > self.ce_target:
                print('Profit target reached for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('ce_sell_target')
        elif ltp < self.ce_prev_ltp:
            levels = gann(ltp)
            self.ce_levels = Levels(levels[self.gann_buy],
                                    levels[self.gann_target],
                                    levels[self.gann_sl])
            print('\nRecalculated prices for %s - ' % self.ce_inst.symbol)
            print('Buy Trigger        - %f' % self.ce_levels.buy)
            print('Sell Trigger       - %f' % self.ce_levels.target)
            print('SL Trigger - %f' % self.ce_levels.stoploss)
            self.ce_prev_ltp = message['ltp']

    def _get_tradeable_lots(self, ltp, ratio=0.9):
        balance = self.client.get_balance()['equity']['available_margin']
        num_lots = int((balance * ratio) / (75.0 * ltp))
        return num_lots

    def _log_trade(self, trade_info=None):
        if trade_info is None:
            self.logger.error('Invalid trade info given to _log_trade()')
        lots = int(int(trade_info['quantity']) / 75)
        sym = trade_info['symbol'].lower()
        oid = str(trade_info['order_id'])
        poid = str(trade_info['parent_order_id'])
        # atp = float(trade_info['average_price'])

        if trade_info['transaction_type'] == BUY:
            self.logger.info('Purchased %d lots of %s' % (lots, sym))
        else:
            self.logger.info('Sold %d lots of %s' % (lots, sym))

        if poid:
            self.logger.info('Parent OID - %s' % poid)
        self.logger.info('Order ID - %s' % oid)
        self.logger.info('Current holdings - %d' % self.holdings)

    def _movement_range(self, instrument=None, num_days=5):
        if self.client is None or instrument is None:
            return 0
        tod = date.today()
        start = tod - timedelta(days=10)
        ohlc = self.client.get_ohlc(instrument, api.OHLCInterval.Day_1,
                                    start, tod - timedelta(days=1))[-5:]
        print('\nRetrieved %d OHLCs' % len(ohlc))
        avg_range = 0
        for o in ohlc:
            print(o)
            avg_range += 100 * (o['high'] - o['low']) / o['close']
        return avg_range / len(ohlc)

