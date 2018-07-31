import os
import configparser
import logging
from queue import Queue
from time import sleep
from datetime import date, datetime, timedelta
from upstox_api import api
import utils
from options import Gann

MAX_LOGIN_TRIES = 10


class Upstox_Manager:

    def __init__(self, config_name):
        if '.ini' not in config_name.lower():
            config_name = config_name + '.ini'

        self.config_name = config_name
        confPath = os.path.join(os.getcwd(), config_name)
        if not os.path.exists(confPath):
            self.create_config_file()

        self.config = configparser.ConfigParser()
        self.config.read(config_name)
        self.opening, self.cutoff = utils.get_trade_hours(date.today())
        self.last_update = None

        self.client = None
        self.bots = []
        self.queues = {}

        self.subbed_stocks = []
        self.running = False
        self._setup_logger()
        self.logger = logging.getLogger()
        self.logger.debug("Initialised Upstox_manager")
        tod = date.today().strftime('%d%m%Y')
        self.trades_log = 'trades_%s' % tod + '.txt' 
        with open(self.trades_log, 'w'):
            pass

    def create_config_file(self):
        conf = configparser.ConfigParser()
        conf['userinfo'] = {'key': '0',
                            'secret': '0',
                            'token': '0',
                            'last_login': '0'}
        with open(self.config_name, 'w') as cf:
            conf.write(cf)
            self.logger.info("Created new config File")

    def login_upstox(self):
        creds = self.config['userinfo']
        if creds['key'] == '0':
            creds['key'] = input('Please enter the API key - ')
            self.logger.debug('Received new API key')
        if creds['secret'] == '0':
            creds['secret'] = input('Please enter the API secret - ')
            self.logger.info('Received new API secret')

        tries = 0
        s = api.Session(creds['key'])
        s.set_redirect_uri('http://127.0.0.1')
        s.set_api_secret(creds['secret'])
        while tries < MAX_LOGIN_TRIES:
            try:
                self.client = api.Upstox(creds['key'], creds['token'])
                self.logger.info('Logged in successfully.')
                break
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

        print('Loading master contracts')
        try:
            nse_fo = self.client.get_master_contract('nse_fo')
            if nse_fo:
                print('NSE F&O loaded.')
                self.logger.debug('NSE F&O loaded %d contracts' % len(nse_fo))
        except Exception as e:
            self.logger.error('unable to load NSE_FO master contracts')
            self.logger.exception('Couldn\'nt load NSE_FO master contract')
        try:
            self.client.enabled_exchanges.append('nse_index')
            nse_index = self.client.get_master_contract('nse_index')
            if nse_index:
                print('NSE Index loaded.')
                self.logger.debug('NSE Index loaded %d contracts' % len(nse_fo))
        except Exception as e:
            self.logger.error('unable to load NSE_INDEX master contracts')
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

    def run(self):
        self.logger.info('Starting run loop')
        self.logger.debug('opening - ' + self.opening.isoformat())
        self.logger.debug('close - ' + self.cutoff.isoformat())

        self._setup_bots()
        if datetime.now() < self.opening:
            print('\nWaiting for trade hours to start')
        while 1:
            if self.last_update is not None:
                if self.last_update - datetime.now() > timedelta(20) and self.running:
                    self._reconnect()
            try:
                now = datetime.now()
                if now < self.opening:
                    sleep(10)
                elif not self.running and now > self.opening and now < self.cutoff:
                    print('Trade open! Starting websocket.')
                    self.running = True
                    self.client.start_websocket(True)
                elif now > self.cutoff and self.running is True:
                    print('\nCutoff time reached. Close all positions')
                    self._stop()
                elif now > self.cutoff:
                    tom = datetime.now() + timedelta(days=1)
                    self.opening, self.cutoff = utils.get_trade_hours(tom.date())
                    print('\n')
                    print(self.opening)
                    print(self.cutoff)
            except KeyboardInterrupt:
                self._stop()
                return
            except Exception as e:
                self.logger.exception('Fatal error in Gann.run()')

    def _setup_bots(self):
        print('\nSetting up Trade bots')
        if len(self.bots) < 1:
            self.logger.critical('No Bots to run!')
            return
        for bot in self.bots:
            q = Queue()
            syms = bot.setup(q)
            self.logger.info('Added %s bot. Required instruments:' %
                             bot.__class__.__name__)
            for s in syms:
                self.logger.info(s)
            if type(syms) is tuple:
                self.queues[syms] = q
            elif type(syms) is list:
                self.queues[tuple(syms)] = q
            else:
                self.queues[(syms, )] = q

    def quote_handler(self, message):
        self.last_update = datetime.now()
        sym = message['instrument'].symbol.lower()
        self.last_update = datetime.now()
        print(sym, message['ltp'])
        if not any(inst for inst in self.subbed_stocks if inst.symbol.lower() == sym):
            self.subbed_stocks.append(message['instrument'])
        try:
            for k, w in self.queues.items():
                if sym in k:
                    self.queues[k].put(('q', message))
        except Exception as e:
            self.logger.info("Symbol %s - no worker associated" % sym)

    def order_handler(self, message):
        sym = message['instrument'].symbol.lower()
        try:
            for k, w in self.queues.items():
                if sym in k:
                    self.queues[k].put(('o', message))
        except Exception as e:
            self.logger.info("Symbol %s - no worker associated" % sym)

    def trade_handler(self, message):
        sym = message['instrument'].symbol.lower()
        with open(self.trades_log, 'a'):
            print('===========================================\n')
            for k, v in message:
                if k == 'instrument':
                    pass
                else:
                    print('\t', k, ' : ', v)
        try:
            for k, w in self.queues.items():
                if sym in k:
                    self.queues[k].put(('t', message))
        except Exception as e:
            self.logger.debug("Trade update for %s with worker associated" % sym)
            try:
                self.client.unsubscribe(message['instrument'], api.LiveFeedType.LTP)
            except Exception as e:
                pass

    def _stop(self):
        self.running = False
        for bot in self.bots:
            bot.stop()
            if bot.isAlive():
                bot.join()
        for stock in self.subbed_stocks:
            try:
                self.client.unsubscribe(stock, api.LiveFeedType.LTP)
            except Exception as e:
                pass
        self.subbed_stocks.clear()
        if self.client.websocket is not None:
            self.client.websocket.keep_running = False

    def _disconnect_handler(self, message):
        print('Websocket Disconnected')
        self.logger.debug('Websocket Disconnected')

    def _reconnect(self):
        print('Reconnecting websocket')
        self.logger.debug('Reconnecting Websocket')
        for inst in self.subbed_stocks:
            try:
                self.client.subscribe(inst, api.LiveFeedType.LTP)
            except Exception as e:
                pass
        self.client.start_websocket(True)

    def _setup_logger(self):
        fn = date.today().strftime('%d-%m-%Y_root.log')
        with open(fn, 'w'):
            pass

        logger = logging.getLogger()

        fmt = logging.Formatter('[%(asctime)s ROOT] - %(levelname)s - %(message)s')

        fh = logging.FileHandler(fn)
        fh.setFormatter(fmt)
        fh.setLevel(logging.INFO)
        logger.addHandler(fh)

        with open('errors.log', 'w'):
            pass
        eh = logging.FileHandler('errors.log')
        eh.setLevel(logging.ERROR)
        logger.addHandler(eh)


def main():
    m = Upstox_Manager('config.ini')
    m.login_upstox()
    g = Gann(m.client)
    m.bots.append(g)
    m.run()


if __name__ == '__main__':
    main()
