from manager import Manager
from niftyoptions import GannOptions
import configparser
import logging
import os
from collections import OrderedDict

N50_SYMBOL = 'NIFTY_50'
BN_SYMBOL = 'NIFTY_BANK'

BOT_CONF = os.getcwd() + "\\bot_conf.txt"

l = logging.getLogger()
l.setLevel(logging.ERROR)
fh = logging.FileHandler('Errors.log')
fh.setLevel(logging.ERROR)
l.addHandler(fh)


def main():
    m = Manager('config.ini')
    m.login_upstox()
    nifty = m.client.get_instrument_by_symbol('nse_index', N50_SYMBOL)
    o = GannOptions(nifty)
    o.setup(m.client)
    m.add_strategy(o)
    m.main_loop()


def test():
    botconf = configparser.ConfigParser()
    if os.path.isfile(BOT_CONF):
        botconf.read(BOT_CONF)

    m = Manager('config.ini')
    m.login_upstox()
    '''
    import emats
    e = emats.EMATS(nifty, debug=False, showinfo=True)
    e.setup(m.client)
    '''




if __name__ == '__main__':
    test()
