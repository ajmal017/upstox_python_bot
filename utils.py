from datetime import datetime, date, timedelta
import logging
import os


EXPIRIES = ('04-01-2018', '11-01-2018', '18-01-2018', '25-01-2018', '01-02-2018',
            '01-02-2018', '08-02-2018', '15-02-2018', '22-02-2018', '01-03-2018',
            '08-03-2018', '15-03-2018', '22-03-2018', '29-03-2018', '05-04-2018',
            '12-04-2018', '19-04-2018', '26-04-2018', '03-05-2018', '10-05-2018',
            '17-05-2018', '24-05-2018', '31-05-2018', '31-05-2018', '07-06-2018',
            '14-06-2018', '21-06-2018', '28-06-2018', '28-06-2018', '05-07-2018',
            '12-07-2018', '19-07-2018', '26-07-2018', '02-08-2018', '02-08-2018',
            '09-08-2018', '16-08-2018', '23-08-2018', '30-08-2018', '06-09-2018',
            '13-09-2018', '20-09-2018', '27-09-2018', '04-10-2018', '11-10-2018',
            '18-10-2018', '25-10-2018', '01-11-2018', '08-11-2018', '15-11-2018',
            '22-11-2018', '29-11-2018', '06-12-2018', '13-12-2018', '20-12-2018',
            '27-12-2018', '03-01-2019')

WEEKENDS = ('06-01-2018,' '07-01-2018,' '13-01-2018,' '14-01-2018,' '20-01-2018,'
            '21-01-2018,' '27-01-2018,' '28-01-2018,' '03-02-2018,' '04-02-2018,'
            '03-02-2018,' '04-02-2018,' '10-02-2018,' '11-02-2018,' '17-02-2018,'
            '18-02-2018,' '24-02-2018,' '25-02-2018,' '03-03-2018,' '04-03-2018,'
            '03-03-2018,' '04-03-2018,' '10-03-2018,' '11-03-2018,' '17-03-2018,'
            '18-03-2018,' '24-03-2018,' '25-03-2018,' '31-03-2018,' '01-04-2018,'
            '31-03-2018,' '01-04-2018,' '07-04-2018,' '08-04-2018,' '14-04-2018,'
            '15-04-2018,' '21-04-2018,' '22-04-2018,' '28-04-2018,' '29-04-2018,'
            '05-05-2018,' '06-05-2018,' '05-05-2018,' '06-05-2018,' '12-05-2018,'
            '13-05-2018,' '19-05-2018,' '20-05-2018,' '26-05-2018,' '27-05-2018,'
            '02-06-2018,' '03-06-2018,' '02-06-2018,' '03-06-2018,' '09-06-2018,'
            '10-06-2018,' '16-06-2018,' '17-06-2018,' '23-06-2018,' '24-06-2018,'
            '30-06-2018,' '01-07-2018,' '30-06-2018,' '01-07-2018,' '07-07-2018,'
            '08-07-2018,' '14-07-2018,' '15-07-2018,' '21-07-2018,' '22-07-2018,'
            '28-07-2018,' '29-07-2018,' '04-08-2018,' '05-08-2018,' '04-08-2018,'
            '05-08-2018,' '11-08-2018,' '12-08-2018,' '18-08-2018,' '19-08-2018,'
            '25-08-2018,' '26-08-2018,' '01-09-2018,' '02-09-2018,' '01-09-2018,'
            '02-09-2018,' '08-09-2018,' '09-09-2018,' '15-09-2018,' '16-09-2018,'
            '22-09-2018,' '23-09-2018,' '29-09-2018,' '30-09-2018,' '06-10-2018,'
            '07-10-2018,' '13-10-2018,' '14-10-2018,' '20-10-2018,' '21-10-2018,'
            '27-10-2018,' '28-10-2018,' '03-11-2018,' '04-11-2018,' '03-11-2018,'
            '04-11-2018,' '10-11-2018,' '11-11-2018,' '17-11-2018,' '18-11-2018,'
            '24-11-2018,' '25-11-2018,' '01-12-2018,' '02-12-2018,' '01-12-2018,'
            '02-12-2018,' '08-12-2018,' '09-12-2018,' '15-12-2018,' '16-12-2018,'
            '22-12-2018,' '23-12-2018,' '29-12-2018,' '30-12-2018,' '05-01-2019,'
            '06-01-2019,')

HOLIDAYS = ('26-01-2018', '13-02-2018', '19-02-2018', '02-03-2018', '29-03-2018',
            '30-03-2018', '02-04-2018', '30-04-2018', '01-05-2018', '15-08-2018',
            '17-08-2018', '22-08-2018', '13-09-2018', '20-09-2018', '02-10-2018',
            '18-10-2018', '07-11-2018', '08-11-2018', '21-11-2018', '23-11-2018',
            '25-12-2018')

MAX_LOGIN_TRIES = 10

BUY = 'B'
SELL = 'S'

TIMEOUT = 10

logger = logging.getLogger()


def is_trade_day(day):
    try:
        d = day.strftime('%d-%m-%Y')
        return d not in HOLIDAYS and day.weekday() not in (5, 6)
    except AttributeError:
        logger.exception('is_trade_day requires datetime or date object')
        return False


def next_trade_day(startdate):
    d = 0
    try:
        d = startdate + timedelta(days=1)
        while not is_trade_day(d):
            d += timedelta(days=1)
    except TypeError:
        logger.exception('get_next_trade_day requires datetime or date object')
    finally:
        if isinstance(d, date):
            return d
        else:
            return d.date()


def prev_trade_day(startdate):
    d = 0
    try:
        d = startdate - timedelta(days=1)
        while not is_trade_day(d):
            d -= timedelta(days=1)
    except TypeError:
        logger.exception('get_prev_trade_day requires datetime or date object')
    finally:
        if isinstance(d, date):
            return d
        else:
            return d.date()


def get_trade_hours(day):
    o = datetime.strptime(day.strftime('%d-%m-%y') + '-09:15', '%d-%m-%y-%H:%M')
    c = datetime.strptime(day.strftime('%d-%m-%y') + '-15:30', '%d-%m-%y-%H:%M')
    return o, c


def ts_to_datetime(ts=None):
    if ts is None:
        return ts
    return datetime.fromtimestamp(ts / 1000)


def thursdays():
    from calendar import Calendar
    c = Calendar()
    days = []
    thursday = 3
    for i in range(1, 13):
        for d in c.itermonthdates(2018, i):
            if d.weekday() == thursday:
                days.append(d)
    with open('thursdays.txt', 'w') as f:
        for day in days:
            f.write(day.strftime('%d-%m-%Y\n'))


def get_expiry_dates(month=1):
    dates = []
    for e in EXPIRIES:
        d = int(e[0:2])
        m = int(e[3:5])
        Y = int(e[6:])
        if m == month:
            dates.append(date(day=d, month=m, year=Y))
    return dates


def round_off(num, div=0.1):
    x = div * round(num / div)
    return float(x)


def create_logger(name, console=False, level=logging.INFO):
    log_dir = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    name = name + date.today().strftime(' %m-%d-%Y') + '.log'
    fmt = logging.Formatter('[{asctime} - {levelname}] {name} - {message}',
                            datefmt='%H:%M:%S',
                            style='{')
    if console:
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        ch.setLevel(level)
        logger.addHandler(ch)
    fh = logging.FileHandler(os.path.join(log_dir, name))
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    return logger


def get_master_contract_of_index(exchange, client):
    from collections import OrderedDict
    exchange = exchange.lower()
    u = client
    logging.debug('Downloading master contracts for exchange: %s' % (exchange))
    body = u.api_call_helper('masterContract', 'GET', {'exchange': exchange}, None)
    count = 0
    master_contract_by_token = OrderedDict()
    from upstox_api import api as upstox
    for line in body:
        count += 1
        if count == 1:
            continue
        item = line.split(',')

        # convert token
        if item[1] is not u'':
            item[1] = int(item[1])

        # convert parent token
        if item[2] is not u'':
            item[2] = int(item[2])
        else:
            item[2] = None

        # convert symbol to upper
        item[3] = item[3].lower()

        # convert closing price to float
        if item[5] is not u'':
            item[5] = float(item[5])
        else:
            item[5] = None

        # convert expiry to none if it's non-existent
        if item[6] is u'':
            item[6] = None

        # convert strike price to float
        if item[7] is not u'' and item[7] is not u'0':
            item[7] = float(item[7])
        else:
            item[7] = None

        # convert tick size to int
        if item[8] is not u'':
            item[8] = float(item[8])
        else:
            item[8] = None

        # convert lot size to int
        if item[9] is not u'':
            item[9] = int(item[9])
        else:
            item[9] = None

        # convert instrument_type to none if it's non-existent
        if item[10] is u'':
            item[10] = None

        # convert isin to none if it's non-existent
        if item[11] is u'':
            item[11] = None

        instrument = upstox.Instrument(item[0], item[1], item[2], item[3], item[4],
                                       item[5], item[6], item[7], item[8], item[9],
                                       item[10], item[11])

        token = item[1]
        symbol = item[3]
        master_contract_by_token[symbol] = instrument

    return master_contract_by_token
