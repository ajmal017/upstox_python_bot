from upstox_api import api
import utils
import threading
from time import sleep
from math import sqrt
from datetime import date

N50_SYMBOL = 'NIFTY_50'
LOT_SIZE = 75
NUM_LOTS = 10


class Gann:
    def __init__(self, client):
        if not isinstance(client, api.Upstox):
            print('Provide an Upstox class object for gann.client')
            self.client = None
        else:
            self.client = client

        self.lock = threading.Lock()
        self.running = False
        self.messages = None

        self.gann_angles = (0.02, 0.04, 0.08, 0.1, 0.15, 0.25, 0.35,
                            0.40, 0.42, 0.46, 0.48, 0.5, 0.67, 1.0)

        self.buy_gann = 4
        self.buy_gann_sl = 5
        self.sell_gann = -1

        self.pe_inst = None
        self.pe_buy = None
        self.pe_target = None
        self.pe_sl = None
        self.pe_prev_ltp = None
        self.pe_buy_oid = 0
        self.pe_sell_oid = 0

        self.ce_inst = None
        self.ce_buy = None
        self.ce_sl = None
        self.ce_target = None
        self.ce_prev_ltp = None
        self.ce_buy_oid = 0
        self.ce_sell_oid = 0

        self.activity = []

    def setup(self, message_queue=None):
        if 'initialised' in self.activity and self.messages is not None:
            return

        self.messages = message_queue
        try:
            nse_fo = self.client.get_master_contract('nse_fo')
            if nse_fo:
                print('Loaded NSE F&O master contracts.')
        except Exception as e:
            print('unable to load NSE_FO master contracts')
            print(e)
        try:
            self.client.enabled_exchanges.append('nse_index')
            nse_index = self.client.get_master_contract('nse_index')
            if nse_index:
                print('Loaded NSE Index master contracts.')
        except Exception as e:
            print('unable to load NSE_INDEX master contracts')

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

        self.pe_buy_oid = None
        self.pe_target_oid = None
        self.pe_sl_oid = None

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

        self.ce_buy_oid = None
        self.ce_target_oid = None
        self.ce_sl_oid = None

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
        return [utils.round_off((sqrt(tp) - self.gann_angles[self.buy_gann_sl]) ** 2),
                utils.round_off((sqrt(tp) + self.gann_angles[self.buy_gann]) ** 2),
                utils.round_off((sqrt(tp) + self.gann_angles[self.sell_gann]) ** 2)]

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
            if sym == self.pe_inst.symbol.lower():
                if tt == api.TransactionType.Buy:
                    if status in ('complete', 'completed'):
                        self.pe_buy_oid = oid
                        self.activity.append('pe_position_open')
                    elif status in ('rejected', 'cancelled'):
                        self.activity.append('pe_position_failed')

                elif tt == api.TransactionType.Sell:
                    if status in ('complete', 'completed'):
                        if oid == self.pe_target_oid:
                            self.activity.append('pe_sold_target')
                        elif oid == self.pe_sl_sold:
                            self.activity.append('pe_sold_sl')
                    elif status == 'open':
                        self.pe_target_oid = None
                    elif status == 'trigger pending':
                        self.pe_sl_oid = oid

            elif sym == self.ce_inst.symbol.lower():
                if tt == api.TransactionType.Buy:
                    if status in ('complete', 'completed'):
                        self.pe_buy_oid = oid
                        self.activity.append('ce_position_open')
                    elif status in ('rejected', 'cancelled'):
                        self.activity.append('ce_failed')

                elif tt == api.TransactionType.Sell:
                    if status in ('complete', 'completed'):
                        if oid == self.ce_target_oid:
                            self.activity.append('ce_sold_target')
                        elif oid == self.pe_sl_sold:
                            self.activity.append('ce_sold_sl')
                    elif status == 'open':
                        self.ce_target_oid = None
                    elif status == 'trigger pending':
                        self.ce_sl_oid = oid

    def process_trade(self, message):
        pass

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
        print('PE GANN - %f' % ltp)

        if ltp > self.pe_buy + ltp * 0.01:
            return

        if ltp > self.pe_buy and act in ('initialised', 'ce_sold_sl'):
                self.client.place_order(api.TransactionType.Buy,
                                        self.pe_inst,
                                        LOT_SIZE,
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
                self.activity.append('pe_ordered')

        elif act == 'pe_ordered':
            return

        elif act == 'pe_position_open':
            if ltp < self.pe_sl and self.pe_buy_oid is not None:
                print('Placed stoploss order for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('pe_sold_sl')

            elif ltp > self.pe_target:
                print('Placed target sell order for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('pe_sold_target')

        elif ltp < self.pe_prev_ltp:
            pe_gann = self.get_gann_prices(ltp)
            self.pe_sl = pe_gann[0]
            self.pe_buy = pe_gann[1]
            self.pe_target = pe_gann[2]
            print('\n')
            print('Recalculated prices for %s - ' % self.pe_inst.symbol)
            print('Buy Trigger        - %f' % self.pe_buy)
            print('Sell Trigger       - %f' % self.pe_target)
            print('SL Trigger - %f' % self.pe_sl)
            print('\n')
            self.pe_prev_ltp = message['ltp']


    def ce_gann(self, message):
        ltp = message['ltp']
        act = self.activity[-1]
        print('CE GANN - %f' % ltp)

        if ltp > self.ce_buy + ltp * 0.01:
            return

        if ltp > self.ce_buy and act in ('initialised', 'pe_sold_sl'):
                self.client.place_order(api.TransactionType.Buy,
                                        self.ce_inst,
                                        NUM_LOTS * LOT_SIZE,
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
                self.activity.append('ce_ordered')

        elif act == 'ce_ordered':
            return

        elif act == 'ce_position_open':
            if ltp < self.ce_sl and self.ce_buy_oid is not None:
                print('Placed stoploss order for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('ce_sold_sl')
                self.ce_buy_oid = None
                self.ce_sl_oid = None
                self.ce_target_oid = None

            elif ltp > self.ce_target:
                print('Placed target sell order for %s at %f' %
                      (message['symbol'], ltp))
                self.activity.append('ce_sold_target')

        elif ltp < self.ce_prev_ltp:
            ce_gann = self.get_gann_prices(ltp)
            self.ce_sl = ce_gann[0]
            self.ce_buy = ce_gann[1]
            self.ce_target = ce_gann[2]
            print('\n')
            print('Recalculated prices for %s - ' % self.ce_inst.symbol)
            print('Buy Trigger        - %f' % self.ce_buy)
            print('Sell Trigger       - %f' % self.ce_target)
            print('SL Trigger - %f' % self.ce_sl)
            print('\n')
            self.prev_ce_ltp = message['ltp']
