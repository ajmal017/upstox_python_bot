from manager import Upstox_Manager
from options import Gann


def main():
    m = Upstox_Manager('config.ini')
    m.login_upstox()
    g = Gann(m.client, True)
    m.bots.append(g)
    m.run()


if __name__ == '__main__':
    main()
