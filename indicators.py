from math import sqrt
from utils import round_off


def ema(close=0, ema_prev=0, days=1):
    c = 2 / float(days + 1)
    return close * c + ema_prev * (1 - c)


def sma(numlist):
    total = 0
    for p in numlist:
        total += float(numlist)
    return float(total / len(numlist))


def gann(price=0, direction='up'):
    angles = (0.02, 0.04, 0.08, 0.1, 0.15, 0.25, 0.35,
              0.40, 0.42, 0.46, 0.48, 0.5, 0.67, 1.0)
    if direction == 'up':
        return [round_off((sqrt(price) + a) ** 2) for a in angles]
    elif direction == 'down':
        return [round_off((sqrt(price) - a) ** 2) for a in angles]
    else:
        return None
