from manager import Manager
from niftyoptions import GannNiftyOptions

N50_SYMBOL = 'NIFTY_50'
LOT_SIZE = 75


def main():
    m = Manager('config.ini')
    m.login_upstox()
    o = GannNiftyOptions()
    o.setup(m.client)
    m.add_strategy(o)
    m.main_loop()

if __name__ == '__main__':
    main()
