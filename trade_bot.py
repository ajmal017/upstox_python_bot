from upstox_api import api
import threading


class Bot(threading.Thread):
    def __init__(self, client=None):
        self.client = client

    def run(self):
        pass

    def stop(self):
        pass

    def setup(self):
        pass

