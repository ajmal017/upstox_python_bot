from datetime import datetime, date
import os
import logging

MAX_LOGIN_TRIES = 10
TRADE_OPEN = datetime.strptime(date.today().strftime('%d-%m-%y') + '-09:16',
                               '%d-%m-%y-%H:%M')
TRADE_CUTOFF = datetime.strptime(date.today().strftime('%d-%m-%y') + '-15:15',
                                 '%d-%m-%y-%H:%M')


def round_off(num, div=0.1):
    x = div * round(num / div)
    return float(x)
