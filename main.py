from manager import Manager
from niftyoptions import GannNiftyOptions
import logging

N50_SYMBOL = 'NIFTY_50'
LOT_SIZE = 75

l = logging.getLogger()
l.setLevel(logging.ERROR)
fh = logging.FileHandler('Errors.log')
fh.setLevel(logging.ERROR)
l.addHandler(fh)


def main():
    m = Manager('config.ini')
    m.login_upstox()
    o = GannNiftyOptions()
    o.setup(m.client)
    m.add_strategy(o)
    m.main_loop()


def test():
    m = Manager('config.ini')
    m.login_upstox()
    import emats
    e = emats.EMATS(debug=True)
    e.setup(m.client)


if __name__ == '__main__':
    test()
