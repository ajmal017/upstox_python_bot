from threading import Thread
from time import sleep

FREQ = 5.0


class TradeBot(Thread):
    messages = None
    running = False

    def __init__(self):
        super().__init__()

    def setup(self, message_queue):
        self.messages = message_queue

    def run(self):
        self.running = True
        while self.running:
            while not self.messages.empty():
                m = self.messages.get()
                if m[0] == 'q':
                    self.process_quote(m[1])
                elif m[0] == 'o':
                    self.process_order(m[1])
                else:
                    self.process_trade(m[1])
                self.messages.task_done()
            sleep(1 / FREQ)

    def process_quote(self, message):
        pass

    def process_order(self, message):
        pass

    def process_trade(self, message):
        pass

    def stop(self):
        self.running = False



class LinearBot:

    def __init__(self):
        pass

    def process_quote(self, quote):
        pass

    def process_order(self, order):
        pass

    def process_trade(self, trade):
        pass

    def get_symbols(self):
        return None
