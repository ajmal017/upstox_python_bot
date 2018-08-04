from time import sleep
from datetime import date, timedelta
from upstox_api import api as upstox
from utils import BUY, SELL, get_expiry_dates, create_logger
from gannbot import GannBot
from logging import DEBUG


N50_SYMBOL = 'NIFTY_50'
LOT_SIZE = 75

MAX_CYCLES = 2


class GannOptions:
    def __init__(self, instrument=None, debug=False, showinfo=False):
        if debug:
            self.logger = create_logger(self.__class__.__name__,
                                        console=showinfo,
                                        level=DEBUG)
        else:
            self.logger = create_logger(self.__class__.__name__,
                                        console=showinfo)
        self.running = False
        self.cycles = 0
        self.state = []

        if instrument is None or not isinstance(instrument, upstox.Instrument):
            self.logger.error('Invalid Instrument given in constructor.')
            return
        self.inst = instrument
        self.pe_bot = GannBot()
        self.pe_symbol = None
        self.ce_bot = GannBot()
        self.ce_symbol = None

    def setup(self, client=None):
        if 'setup complete' in self.state:
            return
        self.logger.debug('Creating options symbols')
        tod = date.today()
        exp = get_expiry_dates(tod.month)[-1]
        if exp - tod < timedelta(days=6):
            exp = get_expiry_dates(tod.month + 1)[-1]
        data = client.get_live_feed(self.inst, upstox.LiveFeedType.Full)
        nearest_100 = int(float(data['close']) / 100) * 100
        self.logger.debug('Base price for options = %d' % nearest_100)

        self._create_ce_symbol(client, nearest_100, exp)
        ce_inst = client.get_instrument_by_symbol('nse_fo', self.ce_symbol)
        while client.subscribe(ce_inst, upstox.LiveFeedType.LTP)['success'] is not True:
            sleep(1)
        else:
            self.logger.debug('Subscribed to %s' % self.ce_symbol)
            self.logger.debug('close = %f' % ce_inst.closing_price)
            pass

        self._create_pe_symbol(client, nearest_100, exp)
        pe_inst = client.get_instrument_by_symbol('nse_fo', self.pe_symbol)
        while client.subscribe(pe_inst, upstox.LiveFeedType.LTP)['success'] is not True:
            sleep(1)
        else:
            self.logger.debug('Subscribed to %s' % self.pe_symbol)
            self.logger.debug('close = %f' % pe_inst.closing_price)
            pass

        self.state.append('setup complete')
        self.logger.debug(self.state[-1])

    def process_quote(self, quote):
        sym = quote['symbol'].lower()
        pe_order = None
        ce_order = None
        if sym == self.pe_symbol:
            pe_order = self.pe_bot.process_quote(quote)
        elif sym == self.ce_symbol:
            ce_order = self.ce_bot.process_quote(quote)

        if self.state[-1] in ('setup complete') and self.cycles < MAX_CYCLES:
            if pe_order is not None and 'pe position closed' not in self.state:
                self.state.append('pe ordered')
                return pe_order
            elif ce_order is not None and 'ce position closed' not in self.state:
                self.state.append('ce ordered')
                return ce_order
        elif self.cycles == MAX_CYCLES:
            self.state.append('finished trading')

    def process_order(self, order):
        sym = order['symbol'].lower()
        if sym == self.pe_symbol:
            self.pe_bot.process_order(order)
        elif sym == self.ce_symbol:
            self.ce_bot.process_order(order)

    def process_trade(self, trade):
        self._log_trade(trade)
        sym = trade['symbol'].lower()
        if sym == self.pe_symbol:
            self.pe_bot.process_trade(trade)
            newstate = 'pe ' + self.pe_bot.state[-1]
        elif sym == self.ce_symbol:
            self.ce_bot.process_trade(trade)
            newstate = 'ce ' + self.pe_bot.state[-1]
        if newstate != self.state[-1]:
            self.state.append(newstate)

        if 'position closed' in self.state[-1]:
            self.cycles += 1

    def get_symbols(self):
        if 'setup complete' not in self.state:
            return None
        return (self.pe_symbol, self.ce_symbol)

    def _create_pe_symbol(self, client, nearest_100, expiry):
        exp = expiry
        puts = []
        for i in range(-400, 0, 100):
            sym = 'nifty' + exp.strftime('%y%b').lower() + str(nearest_100 + i) + 'pe'
            feed = client.get_live_feed(client.get_instrument_by_symbol('nse_fo', sym),
                                        upstox.LiveFeedType.Full)
            puts.append(feed)
        puts_sorted = sorted(puts, key=lambda k: float(k['close']))
        self.pe_symbol = puts_sorted[0]['symbol'].lower()

    def _create_ce_symbol(self, client, nearest_100, expiry):
        exp = expiry
        calls = []
        for i in range(0, 400, 100):
            sym = 'nifty' + exp.strftime('%y%b').lower() + str(nearest_100 + i) + 'ce'
            feed = client.get_live_feed(client.get_instrument_by_symbol('nse_fo', sym),
                                        upstox.LiveFeedType.Full)
            calls.append(feed)
        calls_sorted = sorted(calls, key=lambda k: float(k['close']))
        self.ce_symbol = calls_sorted[0]['symbol'].lower()

    def _log_trade(self, trade_info=None):
        if trade_info is None:
            self.logger.error('Invalid trade info given to _log_trade()')
        lots = int(int(trade_info['quantity']) / 75)
        sym = trade_info['symbol'].lower()
        oid = str(trade_info['order_id'])
        poid = str(trade_info['parent_order_id'])

        if trade_info['transaction_type'] == BUY:
            self.logger.info('Purchased %d lots of %s' % (lots, sym))
        else:
            self.logger.info('Sold %d lots of %s' % (lots, sym))

        if poid != 'NA':
            self.logger.info('Parent OID - %s' % poid)
        self.logger.info('Order ID - %s' % oid)
