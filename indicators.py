from math import sqrt
from utils import round_off


def ema(ohlc_arr, n=3):
    '''
    ohlc_arr is any list of dicts with length > 3
    dict must have following keys - 'open', 'high', 'low', 'close'
    '''
    if len(ohlc_arr) < n + 1:
        return None
    c = 2 / float(len(ohlc_arr) + 1)
    n = int(abs(n) * -1)
    arr = ohlc_arr[n:]
    ema_prev = 0.0
    ema = 0.0
    for ohlc in arr[1:]:
        close = float(ohlc['close'])
        if ema_prev == 0.0:
            ema_prev = close
        else:
            ema_prev = ema
        ema = (close * c) + (ema_prev * (1 - c))
    return ema


def sma(ohlc_arr):
    total = 0
    for ohlc in ohlc_arr:
        total += float(ohlc['close'])
    return total / float(len(ohlc_arr))


def gann(price=0, direction='up'):
    angles = (0.02, 0.04, 0.08, 0.1, 0.15, 0.25, 0.35,
              0.40, 0.42, 0.46, 0.48, 0.5, 0.67, 1.0)
    if direction == 'up':
        return [round_off((sqrt(price) + a) ** 2) for a in angles]
    elif direction == 'down':
        return [round_off((sqrt(price) - a) ** 2) for a in angles]
    else:
        return None
