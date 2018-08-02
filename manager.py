import os
import configparser
from logging import DEBUG
from queue import Queue
from time import sleep
from datetime import date, datetime
from upstox_api import api
from urllib3.exceptions import MaxRetryError
import utils

MAX_LOGIN_TRIES = 10
TIMEOUT = 10


class Manager:
    def __init__(self, config_name, debug=False):
        if debug:
            self.logger = utils.create_logger(self.__class__.__name__, True, DEBUG)
        else:
            self.logger = utils.create_logger(self.__class__.__name__, True)

        if '.ini' not in config_name.lower()[-4:]:
            config_name = config_name + '.ini'

        self.config_name = config_name
        confPath = os.path.join(os.getcwd(), config_name)
        if not os.path.exists(confPath):
            self.create_config_file()
            self.logger.debug('Created new config file')

        self.config = configparser.ConfigParser()
        self.config.read(config_name)
        self.opening, self.cutoff = utils.get_trade_hours(date.today())
        self.last_update = None

        self.client = None
        self.bots = []
        self.quotes = Queue()
        self.orders = Queue()
        self.trades = Queue()

        self.subbed_stocks = []
        self.running = False

    def create_config_file(self):
        conf = configparser.ConfigParser()
        conf['userinfo'] = {'key': '0',
                            'secret': '0',
                            'token': '0',
                            'last_login': '0'}
        with open(self.config_name, 'w') as cf:
            conf.write(cf)
            self.logger.info("Updated config File")

    def login_upstox(self):
        creds = self.config['userinfo']
        if creds['key'] == '0':
            creds['key'] = input('Please enter the API key - ')
            self.logger.debug('Received new API key')
        if creds['secret'] == '0':
            creds['secret'] = input('Please enter the API secret - ')
            self.logger.debug('Received new API secret')

        tries = 0
        s = api.Session(creds['key'])
        s.set_redirect_uri('http://127.0.0.1')
        s.set_api_secret(creds['secret'])
        while tries < MAX_LOGIN_TRIES:
            try:
                self.client = api.Upstox(creds['key'], creds['token'])
                self.logger.info('Logged in successfully.')
                break
            except MaxRetryError:
                self.logger.exception('Unable to login- check internet connection')
            except Exception as e:
                if 'Invalid Bearer token' in e.args[0]:
                    url = s.get_login_url()
                    print('New token required. Auth url - ')
                    print(url)
                    code = input("Please enter the code from the login page - ")
                    s.set_code(code)
                    creds['token'] = s.retrieve_access_token()
                    self.logger.info('Received new upstox auth token')
            tries += 1

        if self.client is None:
            return

        self.logger.info('Loading master contracts')
        try:
            nse_fo = self.client.get_master_contract('nse_fo')
            if nse_fo:
                self.logger.info('NSE F&O loaded %d contracts' % len(nse_fo))
        except Exception as e:
            self.logger.exception('Couldn\'nt load NSE_FO master contract')
        try:
            self.client.enabled_exchanges.append('nse_index')
            nse_index = self.client.get_master_contract('nse_index')
            if nse_index:
                self.logger.info('NSE Index loaded %d contracts' % len(nse_fo))
        except Exception as e:
            self.logger.exception('Couldn\'nt load NSE_INDEX master contract')

        self.client.set_on_quote_update(self.quote_handler)
        self.client.set_on_order_update(self.order_handler)
        self.client.set_on_trade_update(self.trade_handler)
        self.client.set_on_disconnect(self._disconnect_handler)
        self.client.set_on_error(self._disconnect_handler)

        creds['last_login'] = datetime.now().strftime('%d-%m-%Y %H:%M')
        with open(self.config_name, 'w') as cf:
            self.config.write(cf)
            self.logger.info('Updated config file')

    def main_loop(self, freq=0.2):
        if datetime.now() < self.opening:
            print('Waiting for trade hours to start')
            try:
                while datetime.now() < self.opening:
                    sleep(TIMEOUT)
            except KeyboardInterrupt:
                print('Interrupted by user. Exiting')
                self._unsubscribe_all()
                return
        elif datetime.now() > self.cutoff:
            self.logger.info('Trade day over. Will not run main loop')
            return

        self.running = True
        self.logger.info('Starting websocket')
        print('Starting websocket')
        self.client.start_websocket(True)
        self.last_update = datetime.now()
        try:
            print('Entering main loop')
            while self.running:
                if self.last_update is not None:
                    diff = datetime.now() - self.last_update
                    if diff.seconds > TIMEOUT:
                        self.logger.debug('No update received in over %d seconds' % TIMEOUT)
                        self._reconnect()
                if datetime.now() > self.cutoff:
                    self.logger.info('Trade hours over. Exiting main loop')
                    self._stop()
                    self.running = False

                while not self.quotes.empty():
                    m = self.quotes.get()
                    sym = m['symbol'].lower()
                    for bot in self.bots:
                        if sym in bot[0]:
                            order = bot[1].process_quote(m)
                            if order is not None:
                                self.client.place_order(order['transaction'],
                                                        order['instrument'],
                                                        order['quantity'],
                                                        order['order_type'],
                                                        order['product'],
                                                        order['buy_price'],
                                                        None,
                                                        0,
                                                        api.DurationType.DAY,
                                                        order['stoploss'],
                                                        order['target'],
                                                        None)
                    self.quotes.task_done()

                while not self.orders.empty():
                    m = self.orders.get()
                    sym = m.symbol.lower()
                    for bot in self.bots:
                        if sym in bot[0]:
                            bot[1].process_order(m)
                    self.orders.task_done()

                while not self.trades.empty():
                    m = self.trades.get()
                    sym = m.symbol.lower()
                    for bot in self.bots:
                        if sym in bot[0]:
                            bot[1].process_trade(m)
                    self.trades.task_done()
                sleep(freq)

        except KeyboardInterrupt:
            self.logger.info('Forced exit by user')
        except Exception as e:
            self.logger.exception('Unknown error in manager.main_loop')
        finally:
            self._unsubscribe_all()

    def add_strategy(self, bot):
        self.bots.append((bot.get_symbols(), bot))
        syms = bot.get_symbols()
        if syms is not None:
            bot.setup(self.client)
            syms = bot.get_symbols()

        for s in bot.get_symbols():
            self.subbed_stocks.append(s)

    def quote_handler(self, message):
        self.last_update = datetime.now()
        inst = message['instrument']
        if inst.symbol.lower() not in self.subbed_stocks:
            try:
                self.client.unsubscribe(inst, api.LiveFeedType.LTP)
            except Exception as e:
                pass
        else:
            self.quotes.put(message)

    def order_handler(self, message):
        inst = message['instrument']
        if inst.symbol.lower() not in self.subbed_stocks:
            try:
                self.client.unsubscribe(inst, api.LiveFeedType.LTP)
            except Exception as e:
                pass
        else:
            self.orders.put(message)

    def trade_handler(self, message):
        inst = message['instrument']
        if inst.symbol.lower() not in self.subbed_stocks:
            try:
                self.client.unsubscribe(inst, api.LiveFeedType.LTP)
            except Exception as e:
                pass
        else:
            self.orders.put(message)

    def _unsubscribe_all(self):
        self.running = False
        for stock in self.subbed_stocks:
            try:
                self.client.unsubscribe(stock, api.LiveFeedType.LTP)
            except Exception as e:
                pass
        self.subbed_stocks.clear()
        if self.client.websocket is not None:
            self.client.websocket.keep_running = False

    def _disconnect_handler(self, message):
        self.logger.info('Websocket Disconnected')

    def _reconnect(self):
        print("reconnecting")
        self.logger.info('Reconnecting websocket')
        for inst in self.subbed_stocks:
            try:
                self.client.subscribe(inst, api.LiveFeedType.LTP)
            except Exception as e:
                pass
        self.client.start_websocket(True)

