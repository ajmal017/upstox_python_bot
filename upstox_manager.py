import os
import threading
import configparser
from queue import Queue
from time import sleep
from datetime import date, datetime
from upstox_api import api

from options import Gann

MAX_LOGIN_TRIES = 10

TRADE_OPEN = datetime.strptime(date.today().strftime('%d-%m-%y') + '-09:15',
                               '%d-%m-%y-%H:%M')
TRADE_CUTOFF = datetime.strptime(date.today().strftime('%d-%m-%y') + '-15:15',
                                 '%d-%m-%y-%H:%M')


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

        self.client = None
        self.workers = []
        self.queues = {}
        self.threads = []

        self.subbed_stocks = []
        self.running = False
        self.lock = threading.Lock()

    def create_config_file(self):
        conf = configparser.ConfigParser()
        conf['userinfo'] = {'key': '0',
                            'secret': '0',
                            'token': '0',
                            'last_login': '0'}
        with open(self.config_name, 'w') as cf:
            conf.write(cf)

    def login_upstox(self):
        creds = self.config['userinfo']
        if creds['key'] == '0':
            creds['key'] = input('Please enter the API key - ')
        if creds['secret'] == '0':
            creds['secret'] = input('Please enter the API secret - ')

        tries = 0
        s = api.Session(creds['key'])
        s.set_redirect_uri('http://127.0.0.1')
        s.set_api_secret(creds['secret'])
        while tries < MAX_LOGIN_TRIES:
            try:
                self.client = api.Upstox(creds['key'], creds['token'])
                print('Logged in successfully.')
                break
            except Exception as e:
                print(e.args)
                if 'Invalid Bearer token' in e.args[0]:
                    url = s.get_login_url()
                    print('New token required. Auth url - ')
                    print(url)
                    code = input("Please enter the code from the login page - ")
                    s.set_code(code)
                    creds['token'] = s.retrieve_access_token()
            tries += 1

        if self.client is None:
            return

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

        self.client.set_on_quote_update(self.quote_handler)
        self.client.set_on_order_update(self.order_handler)
        self.client.set_on_trade_update(self.trade_handler)

        creds['last_login'] = datetime.now().strftime('%d-%m-%Y %H:%M')
        with open(self.config_name, 'w') as cf:
            self.config.write(cf)

    def add_worker(self, worker=None):
        if worker is None:
            print("Failed to add worker - Invalid arguments")
            return

        q = Queue()
        syms = worker.setup(q)
        if type(syms) is tuple:
            self.queues[syms] = q
        elif type(syms) is list:
            self.queues[tuple(syms)] = q
        else:
            self.queues[(syms, )] = q

        self.threads.append(worker)

    def run(self):
        while 1:
            try:
                if datetime.now() < TRADE_OPEN:
                    print('\nWaiting for trade hours to start')
                    sleep(10)
                elif datetime.now() > TRADE_CUTOFF:
                    print('\nCutoff time reached. Close all positions')
                    self.stop()
                elif not self.running:
                    print('\nStarting bots...')
                    self.client.start_websocket(True)
                    self.running = True
                    for t in self.threads:
                        t.start()
                else:
                    sleep(1)
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                print('\n-------------------')
                print(e)
                pass

    def quote_handler(self, message):
        sym = message['instrument'].symbol.lower()
        if not any(inst for inst in self.subbed_stocks if inst.symbol.lower() == sym):
            self.subbed_stocks.append(message['instrument'])

        try:
            for k, w in self.queues.items():
                if sym in k:
                    self.queues[k].put(('q', message))
        except Exception as e:
            print('No workers for Symbol %s.' % sym)

    def order_handler(self, message):
        sym = message['instrument'].symbol.lower()
        try:
            for k, w in self.queues.items():
                if sym in k:
                    self.queues[k].put(('o', message))
        except Exception as e:
            print('No workers for Symbol %s. Unsubscribing instrument.' % sym)
            try:
                self.client.unsubscribe(message['instrument'], api.LiveFeedType.LTP)
            except Exception as e:
                pass
            pass

    def trade_handler(self, message):
        sym = message['instrument'].symbol.lower()
        try:
            for k, w in self.queues.items():
                if sym in k:
                    self.queues[k].put(('t', message))
        except Exception as e:
            print('No workers for Symbol %s. Unsubscribing instrument.' % sym)
            try:
                self.client.unsubscribe(message['instrument'], api.LiveFeedType.LTP)
            except Exception as e:
                pass

    def stop(self):
        for w in self.workers:
            w.stop()

        for t in self.threads:
            t.join()

        for stock in self.subbed_stocks:
            try:
                self.client.unsubscribe(stock, api.LiveFeedType.LTP)
            except Exception as e:
                pass
        self.subbed_stocks.clear()

        self.client.websocket.keep_running = False


def main():
    m = Upstox_Manager('config.ini')
    m.login_upstox()
    g = Gann(m.client)
    m.add_worker(g)
    m.run()


def create_samples():

    m = Upstox_Manager('config.ini')
    m.login_upstox()
    c = m.client
    print('\n-----------------------------')
    print('Balance - ')
    print(c.get_balance())
    print('\n-----------------------------')
    print('Profile - ')
    print(c.get_profile())
    print('\n-----------------------------')
    print('Holdings - ')
    print(c.get_holdings())
    print('\n-----------------------------')
    print('Positions - ')
    print(c.get_positions())
    print('\n-----------------------------')
    print('Orders - ')
    orders = c.get_order_history()
    for order in orders:
        print('\n-----------------------------')
        print(order)

    trades = c.get_trade_book()
    for t in trades:
        print('\n-----------------------------')
        print(order)


if __name__ == '__main__':
    main()
