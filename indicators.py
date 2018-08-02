from math import sqrt
from utils import round_off


def ema(ohlc_arr, n=3, seed='sma'):
    '''
    ohlc_arr is any list of dicts with length > 3
    dict must have following keys - 'open', 'high', 'low', 'close', 'timestamp'
    '''
    if len(ohlc_arr) < n + 1:
        return None

    sorted_arr = sorted(ohlc_arr, key=lambda k: k['timestamp'])
    c = 2 / float(n + 1)
    arr = sorted_arr[-n:]
    if seed == 'sma':
        ema_prev = sma(sorted_arr[:-n])
    else:
        ema_prev = float(sorted_arr[-n - 1]['close'])

    ema = 0.0
    for ohlc in arr:
        close = float(ohlc['close'])
        ema = (close * c) + (ema_prev * (1 - c))
    return ema


def sma(ohlc_arr):
    total = 0
    if not ohlc_arr:
        return total
    for ohlc in ohlc_arr:
        total += float(ohlc['close'])
    return float(total / len(ohlc_arr))


def gann(price=0, direction='up'):
    angles = (0.02, 0.04, 0.08, 0.1, 0.15, 0.25, 0.35,
              0.40, 0.42, 0.46, 0.48, 0.5, 0.67, 1.0)
    if direction == 'up':
        return [round_off((sqrt(price) + a) ** 2) for a in angles]
    elif direction == 'down':
        return [round_off((sqrt(price) - a) ** 2) for a in angles]
    else:
        return None
