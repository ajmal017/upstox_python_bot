from datetime import datetime, date

MAX_LOGIN_TRIES = 10
TRADE_OPEN = datetime.strptime(date.today().strftime('%d-%m-%y') + '-09:16',
                               '%d-%m-%y-%H:%M')
TRADE_CUTOFF = datetime.strptime(date.today().strftime('%d-%m-%y') + '-15:15',
                                 '%d-%m-%y-%H:%M')

BUY = 'B'
SELL = 'S'

NIFTY_OPTION_TEMPLATE = 'nifty' + date.today().strftime('%y%b').lower() + '%d'


def round_off(num, div=0.1):
    x = div * round(num / div)
    return float(x)


def get_trade_hours(date):
    o = datetime.strptime(date.strftime('%d-%m-%y') + '-09:16', '%d-%m-%y-%H:%M')
    c = datetime.strptime(date.strftime('%d-%m-%y') + '-15:15', '%d-%m-%y-%H:%M')
    return o, c
