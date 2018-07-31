from manager import Upstox_Manager
from options import Gann


def main():
    conf = input("Enter config file name: ")
    conf += '.ini'
    m = Upstox_Manager(conf)
    m.login_upstox()
    g = Gann(m.client, True)
    m.bots.append(g)
    m.run()


if __name__ == '__main__':
    main()
