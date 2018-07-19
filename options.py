from upstox_api import api
import utils
import threading
from time import sleep
from math import sqrt
from datetime import date
from threading import Thread

N50_SYMBOL = 'NIFTY_50'
LOT_SIZE = 75
NUM_LOTS = 10
BUY = 'B'
SELL = 'S'


class Gann(Thread):
    def __init__(self, client):
        super().__init__()
        if not isinstance(client, api.Upstox):
            print('Provide an Upstox class object for gann.client')
            self.client = None
        else:
            self.client = client

        self.lock = threading.Lock()
        self.running = False
        self.messages = None

        self.holdings = 0
        self.tally = 0.0
        self.parent_oid = None
        self.target_oid = None
        self.sl_oid = None
        self.sell_oids = []
        self.activity = []

        self.gann_angles = (0.02, 0.04, 0.08, 0.1, 0.15, 0.25, 0.35,
                            0.40, 0.42, 0.46, 0.48, 0.5, 0.67, 1.0)

        self.buy_gann = 4
        self.sl_gann = 5
        self.target_gann = -1

        self.pe_inst = None
        self.pe_buy = None
        self.pe_target = None
        self.pe_sl = None
        self.pe_prev_ltp = None

        self.ce_inst = None
        self.ce_buy = None
        self.ce_sl = None
        self.ce_target = None
        self.ce_prev_ltp = None


    def setup(self, message_queue=None):
        if 'initialised' in self.activity and self.messages is not None:
            return

        self.messages = message_queue
        self.daemon = True

        nifty = self.client.get_instrument_by_symbol('nse_index', N50_SYMBOL)
        data = self.client.get_live_feed(nifty, api.LiveFeedType.Full)

        nearest_100 = int(float(data['open']) / 100) * 100
        print('Nearest 100 for Nifty = %d' % nearest_100)

        tod = date.today()
        pe_symbol = 'nifty' + tod.strftime('%y%b').lower() + str(nearest_100) + 'pe'
        ce_symbol = 'nifty' + tod.strftime('%y%b').lower() + str(nearest_100) + 'ce'
        print('FnO symbols for trade = %s | %s' % (pe_symbol, ce_symbol))

        pe_inst = self.client.get_instrument_by_symbol('nse_fo', pe_symbol)
        ce_inst = self.client.get_instrument_by_symbol('nse_fo', ce_symbol)

        pe_feed = self.client.get_live_feed(pe_inst, api.LiveFeedType.Full)
        self.pe_inst = pe_inst
        pe_prices = self.get_gann_prices(pe_feed['open'])
        self.pe_sl = pe_prices[0]
        self.pe_buy = pe_prices[1]
        self.pe_target = pe_prices[2]
        self.pe_prev_ltp = pe_feed['open']

        print(self.client.subscribe(pe_inst, api.LiveFeedType.LTP))
        print('-----')
        print('Initial values for %s - ' % pe_inst.symbol)
        print('Buy Trigger        - %f' % self.pe_buy)
        print('Sell Trigger       - %f' % self.pe_target)
        print('Initial SL Trigger - %f' % self.pe_sl)
        print('-----')

        # -------------------------------------------------------------------------------

        ce_feed = self.client.get_live_feed(ce_inst, api.LiveFeedType.Full)
        self.ce_inst = ce_inst
        ce_prices = self.get_gann_prices(ce_feed['open'])
        self.ce_buy = ce_prices[1]
        self.ce_target = ce_prices[2]
        self.ce_sl = ce_prices[0]
        self.ce_prev_ltp = ce_feed['open']

        print(self.client.subscribe(ce_inst, api.LiveFeedType.LTP))
        print('-----')
        print('Initial values for %s - ' % ce_inst.symbol)
        print('Buy Trigger        - %f' % self.ce_buy)
        print('Sell Trigger       - %f' % self.ce_target)
        print('Initial SL Trigger - %f' % self.ce_sl)
        print('-----')

        self.activity.append('initialised')

        return (ce_inst.symbol.lower(), pe_inst.symbol.lower())

    def run(self):
        if not self.running:
            self.running = True

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

    def get_gann_prices(self, tp=None):
        if tp is None:
            return tp
        return [utils.round_off((sqrt(tp) - self.gann_angles[self.buy_gann]) ** 2),
                utils.round_off((sqrt(tp) + self.gann_angles[self.sl_gann]) ** 2),
                utils.round_off((sqrt(tp) + self.gann_angles[self.target_gann]) ** 2)]

    def process_quote(self, message):
        sym = message['symbol'].lower()
        if sym == self.pe_inst.symbol.lower():
            self.pe_gann(message)
            return True
        elif sym == self.ce_inst.symbol.lower():
            self.ce_gann(message)
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
        qty = int(message['traded_quantity'])
        qty = int(message['quantity'])
        oid = str(message['order_id'])
        tt = str(message['transaction_type'])
        atp = float(message['average_price'])
        status = str(message['status'])
        poid = None
        if message['parent_order_id'] != 'NA':
            poid = str(message['parent_order_id'])

        if tt == BUY:
            if status in ('complete', 'completed'):
                self.holdings += qty
                self.tally -= qty * atp
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
                self.tally += qty * atp
                self.sell_oids.append(oid)
                if self.holdings <= 0:
                    # self.log_trade(parent_oid)
                    self.holdings = 0
                    self.sell_oids.clear()
                    self.parent_oid = None
                    self.sl_oid = None
                    self.target_oid = None
                    if sym == self.pe_inst.symbol.lower():
                        self.activity.append('pe_position_closed')
                    elif sym == self.ce_inst.symbol.lower():
                        self.activity.append('ce_position_closed')

    def stop(self):
        print("Stopping Gann Robot")
        self.activity.append('stopped bot')
        with open('gann_log.txt', 'w') as gl:
            for act in self.activity:
                gl.write(act + '\n')
        self.running = False

    def pe_gann(self, message):
        ltp = message['ltp']
        act = self.activity[-1]

        if ltp > self.pe_buy + ltp * 0.01:
            return

        if ltp > self.pe_buy and act in ('initialised', 'ce_position_closed'):
                self.client.place_order(api.TransactionType.Buy,
                                        self.pe_inst,
                                        LOT_SIZE * NUM_LOTS,
                                        api.OrderType.Limit,
                                        api.ProductType.OneCancelsOther,
                                        self.pe_buy,
                                        None,
                                        0,
                                        api.DurationType.DAY,
                                        abs(self.pe_buy - self.pe_sl),
                                        abs(self.pe_target - self.pe_buy),
                                        20)
                print('Placed buy order for %s at %f' %
                      (message['symbol'], ltp))
                print('\nTarget = %f\nStoploss = %f' % (self.pe_target, self.pe_sl))
                self.activity.append('pe_ordered')
                return
        elif act == 'pe_ordered':
            return
        elif act == 'pe_position_open':
            if ltp < self.pe_sl and self.parent_oid is not None:
                print('Stoploss reached for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('pe_sell_sl')
            elif ltp > self.pe_target:
                print('Profit target reached for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('pe_sell_target')
        elif ltp < self.pe_prev_ltp:
            pe_gann = self.get_gann_prices(ltp)
            self.pe_sl = pe_gann[0]
            self.pe_buy = pe_gann[1]
            self.pe_target = pe_gann[2]
            print('\nRecalculated prices for %s - ' % self.pe_inst.symbol)
            print('Buy Trigger        - %f' % self.pe_buy)
            print('Sell Trigger       - %f' % self.pe_target)
            print('SL Trigger - %f' % self.pe_sl)
            self.pe_prev_ltp = message['ltp']


    def ce_gann(self, message):
        ltp = message['ltp']
        act = self.activity[-1]

        if ltp > self.ce_buy + ltp * 0.01:
            return

        if ltp > self.ce_buy and act in ('initialised', 'pe_position_closed'):
                self.client.place_order(api.TransactionType.Buy,
                                        self.ce_inst,
                                        LOT_SIZE,
                                        api.OrderType.Limit,
                                        api.ProductType.OneCancelsOther,
                                        self.ce_buy,
                                        None,
                                        0,
                                        api.DurationType.DAY,
                                        abs(self.ce_buy - self.ce_sl),
                                        abs(self.ce_target - self.ce_buy),
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
            ce_gann = self.get_gann_prices(ltp)
            self.ce_sl = ce_gann[0]
            self.ce_buy = ce_gann[1]
            self.ce_target = ce_gann[2]
            print('\nRecalculated prices for %s - ' % self.ce_inst.symbol)
            print('Buy Trigger        - %f' % self.ce_buy)
            print('Sell Trigger       - %f' % self.ce_target)
            print('SL Trigger - %f' % self.ce_sl)
            self.ce_prev_ltp = message['ltp']
