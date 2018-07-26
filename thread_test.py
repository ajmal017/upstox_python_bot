import threading
import time
from upstox_manager import Upstox_Manager


class Worker(threading.Thread):

    def __init__(self, name):
        super().__init__()
        self.ctr = 0
        self.name = name
        self.running = False
    
    def run(self):
        if not self.running:
            self.running = True
        while self.running:
            print(self.name, ' ', self.ctr)
            self.ctr += 1
            time.sleep(1)

    def stop(self):
        if self.running:
            print('stopping %s' % self.name)
            self.running = False


def main():
    num_threads = int(input("Enter number of workers: "))
    w = []
    for i in range(num_threads):
        w.append(Worker('Worker - %d' % i + 1))
        w[-1].start()

    while 1:
        try:
            time.sleep(2)
            print('Main thread')
        except KeyboardInterrupt:
            print('\nStopping all threads')
            for worker in w:
                worker.stop()
                worker.join()
            break


def test():
    u = Upstox_Manager('test_conf.ini')
    u.login_upstox()
    c = u.client
    balance = c.get_balance()['equity']['available_margin']
    print('Balance = ', balance)
    ratio = 0.9
    num_lots = int((balance * ratio) / (75.0 * 110))
    print('Tradable lots = ', num_lots)


test()
