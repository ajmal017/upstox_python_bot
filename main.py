from upstox_api import api
from datetime import datetime, timedelta, date
import utils
import os.path
import os
import time

BN_SYMBOL = 'NIFTY_BANK'
N50_SYMBOL = 'NIFTY_50'


def main():
    client = utils.login_upstox('config.ini')
    if client is None:
        return
    else:
        print('Logged in successfully')

    client.enabled_exchanges.append('nse_index')

    fo = client.get_master_contract('NSE_FO')
    print("Loaded %d records of NSE_FO" % len(fo))

    client.get_master_contract('NSE_INDEX')

    cwd = os.getcwd()
    if os.path.exists(os.path.join(cwd, 'fno.txt')):
        with open('fno.txt', 'w') as fno:
            for i, val in fo.items():
                fno.write('Name = %s | Symbol = %s\n' % (val.name, val.symbol))

    banknifty = client.get_instrument_by_symbol('NSE_INDEX', BN_SYMBOL)

    today = date.today()
    from_date = today - timedelta(days=20)

    ohlc_7 = client.get_ohlc(banknifty, '1DAY', from_date, today)[-7:]

    nr7 = ohlc_7[-1]['high'] - ohlc_7[-1]['low']
    is_nr7_day = True

    for ohlc in ohlc_7[:-1]:
        nr = ohlc['high'] - ohlc['low']
        if nr < nr7:
            is_nr7_day = False

    trade_day = False
    if is_nr7_day:
        now = datetime.now()
        trade_hours = datetime.now()
        trade_hours.hour = 9
        trade_hours.minute = 17
        while now < trade_hours:
            time.sleep(1)
            print('%s > Waiting for trading hours...' % now.strftime('%H:%M'))
            now = datetime.now()
        current_ohlc = client.get_live_feed(banknifty, api.LiveFeedType.Full)
        if not (current_ohlc['open'] > ohlc_7[-1]['high'] or
                current_ohlc['open'] > ohlc_7[-1]['low']):
            trade_day = True

    if not is_nr7_day or not trade_day:
        print('NR7 conditions not met, exiting....')
        for i in range(5):
            time.sleep(1)
            print('%d ...' % (5 - i))
    else:
        pass
        # Do trading here


if __name__ == '__main__':
    main()
