from single_manager import Manager
from niftyoptions import GannNiftyOptions
from datetime import date, timedelta
from utils import get_expiry_dates
from upstox_api import api as upstox

N50_SYMBOL = 'NIFTY_50'
LOT_SIZE = 75


def main():
    m = Manager('config.ini')
    m.login_upstox()
    o = GannNiftyOptions()
    o.setup(m.client)
    m.add_strategy(o)


if __name__ == '__main__':
    main()
