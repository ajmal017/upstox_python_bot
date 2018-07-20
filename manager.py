import os
import threading
import configparser
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

        self.client = None
        self.bots = []
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

        print('Loading master contracts')
        try:
            nse_fo = self.client.get_master_contract('nse_fo')
            if nse_fo:
                print('NSE F&O loaded.')
        except Exception as e:
            print('unable to load NSE_FO master contracts')
            print(e)
        try:
            self.client.enabled_exchanges.append('nse_index')
            nse_index = self.client.get_master_contract('nse_index')
            if nse_index:
                print('NSE Index loaded.')
        except Exception as e:
            print('unable to load NSE_INDEX master contracts')

        self.client.set_on_quote_update(self.quote_handler)
        self.client.set_on_order_update(self.order_handler)
        self.client.set_on_trade_update(self.trade_handler)

        creds['last_login'] = datetime.now().strftime('%d-%m-%Y %H:%M')
        with open(self.config_name, 'w') as cf:
            self.config.write(cf)

    def run(self):
        print(self.opening)
        print(self.cutoff)
        while 1:
            try:
                now = datetime.now()
                if now < self.opening:
                    print('\nWaiting for trade hours to start')
                    sleep(10)
                elif not self.running and now > self.opening and now < self.cutoff:
                    print('\nStarting bots...')
                    self.client.start_websocket(True)
                    self.running = True
                    self.start_bots()
                elif now > self.cutoff and self.running is True:
                    print('\nCutoff time reached. Close all positions')
                    self.stop()
                elif now > self.cutoff:
                    tom = datetime.now() + timedelta(days=1)
                    self.opening, self.cutoff = utils.get_trade_hours(tom.date())
                    print('\n')
                    print(self.opening)
                    print(self.cutoff)
            except KeyboardInterrupt:
                self.stop()
                return
            except Exception as e:
                print('\n-------------------')
                print(e)

    def quote_handler(self, message):
        sym = message['instrument'].symbol.lower()
        if not any(inst for inst in self.subbed_stocks if inst.symbol.lower() == sym):
            self.subbed_stocks.append(message['instrument'])
        print('\n%s | %s - LTP - %f' % (message['timestamp'], sym, message['ltp']))
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
            print('No workers for Symbol %s.' % sym)

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

    def start_bots(self):
        if len(self.bots) < 1:
            print('No Bots to run!')
            return
        for bot in self.bots:
            q = Queue()
            syms = bot.setup(q)
            if type(syms) is tuple:
                self.queues[syms] = q
            elif type(syms) is list:
                self.queues[tuple(syms)] = q
            else:
                self.queues[(syms, )] = q
            bot.start()



def main():
    m = Upstox_Manager('config.ini')
    m.login_upstox()
    g = Gann(m.client)
    m.bots.append(g)
    m.run()


if __name__ == '__main__':
    main()
