import os
from threading import Thread
import configparser
from queue import Queue
from time import sleep
from datetime import date, datetime, timedelta
from upstox_api import api

import utils
from options import Gann
from moving_avg import EMAOption


class Upstox_Manager(Thread):

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
        self.bots = []
        self.worker_queues = {}

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

    def login_upstox(self):
        creds = self.config['userinfo']
        if creds['key'] == '0':
            creds['key'] = input('Please enter the API key - ')
        if creds['secret'] == '0':
            creds['secret'] = input('Please enter the API secret - ')

        s = api.Session(creds['key'])
        s.set_redirect_uri('http://127.0.0.1')
        s.set_api_secret(creds['secret'])
        diff = None

        if creds['last_login'] == '0':
            diff = timedelta(hours=1)
        else:
            now = datetime.now()
            last = datetime.strptime(creds['last_login'], '%d-%m-%Y %H:%M')
            diff = now - last

        if creds['token'] == '0' or diff > timedelta(hours=11, minutes=59):
            url = s.get_login_url()
            print('Auth url - ')
            print(url)
            code = input("Please enter the code from the login page - ")
            s.set_code(code)
            creds['token'] = s.retrieve_access_token()
        else:
            print('Reusing token - ', creds['token'])
        try:
            self.client = api.Upstox(creds['key'], creds['token'])
            print('Logged in successfully.')
        except Exception as e:
            print('ERROR! Unable to start Upstox client.')
            print(e)
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
            self.worker_queues[syms] = q
        else:
            self.worker_queues[(syms, )] = q

        self.bots.append(worker)

    def run(self):
        try:
            while 1:
                if datetime.now() < utils.TRADE_OPEN:
                    print('\nWaiting for trade hours to start')
                    sleep(10)
                elif datetime.now() > utils.TRADE_CUTOFF:
                    print('\nCutoff time reached. Close all positions')
                    self.stop()
                    break
                elif not self.running:
                    self.client.start_websocket(True)
                    self.running = True
                    for t in self.bots:
                        t.start()
                else:
                    sleep(1)
        except Exception as e:
            self.stop()

    def quote_handler(self, message):
        sym = message['instrument'].symbol.lower()
        if not any(inst for inst in self.subbed_stocks if inst.symbol.lower() == sym):
            self.subbed_stocks.append(message['instrument'])

        try:
            for k, w in self.worker_queues.items():
                if sym in k:
                    self.worker_queues[k].put(('q', message))
        except Exception as e:
            print('No workers for Symbol %s. Unsubscribing instrument.' % sym)
            try:
                self.client.unsubscribe(message['instrument'], api.LiveFeedType.LTP)
            except Exception as e:
                pass
            pass

    def order_handler(self, message):
        sym = message['instrument'].symbol.lower()
        try:
            for k, w in self.worker_queues.items():
                if sym in k:
                    self.worker_queues[k].put(('o', message))
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
            for k, w in self.worker_queues.items():
                if sym in k:
                    self.worker_queues[k].put(('t', message))
        except Exception as e:
            print('No workers for Symbol %s. Unsubscribing instrument.' % sym)
            try:
                self.client.unsubscribe(message['instrument'], api.LiveFeedType.LTP)
            except Exception as e:
                pass

    def stop(self):
        for w in self.workers:
            w.stop()

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

    # g = Gann(m.client)
    # m.add_worker(g)

    e = EMAOption(m.client)
    m.add_worker(e)

    # m.run()


if __name__ == '__main__':
    main()
