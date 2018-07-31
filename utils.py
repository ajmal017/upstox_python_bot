import calendar
from datetime import datetime, date

MAX_LOGIN_TRIES = 10

BUY = 'B'
SELL = 'S'

TIMEOUT = 10


def round_off(num, div=0.1):
    x = div * round(num / div)
    return float(x)


def get_trade_hours(date):
    o = datetime.strptime(date.strftime('%d-%m-%y') + '-09:15', '%d-%m-%y-%H:%M')
    c = datetime.strptime(date.strftime('%d-%m-%y') + '-15:15', '%d-%m-%y-%H:%M')
    return o, c


def ts_to_datetime(ts=None):
    if ts is None:
        return ts
    return datetime.fromtimestamp(ts / 1000)


def thursdays():
    c = calendar.Calendar()
    days = []
    thursday = 3
    for i in range(1, 13):
        for d in c.itermonthdates(2018, i):
            if d.weekday() == thursday:
                days.append(d)
    with open('thursdays.txt', 'w') as f:
        for day in days:
            f.write(day.strftime('%d-%m-%Y\n'))


EXPIRIES = ['04-01-2018', '11-01-2018', '18-01-2018', '25-01-2018', '01-02-2018',
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
            '27-12-2018', '03-01-2019']


def get_expiry_dates(month=1):
    dates = []
    for e in EXPIRIES:
        d = int(e[0:2])
        m = int(e[3:5])
        Y = int(e[6:])
        if m == month:
            dates.append(date(day=d, month=m, year=Y))
    return dates


print(date.today().month)
