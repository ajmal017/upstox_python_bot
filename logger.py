import logging
from datetime import date
import os



def create_logger(name, level=logging.DEBUG):
    log_dir = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    name = name + date.today().strftime('_%m-%d-%Y') + '.log'
    fmt = logging.Formatter('[%(asctime)s - %(levelname)s] - %(message)s')
    fh = logging.FileHandler(os.path.join(log_dir, name))
    fh.setFormatter(fmt)
    fh.setLevel(level)
    logger.addHandler(fh)
    return logger


l = create_logger('main')
l.debug('test')
l.info('test info')
