import configparser
from upstox_api import api
from datetime import datetime, timedelta
import os


def round_off(num, div=0.1):
    x = div * round(num / div)
    return float(x)


def create_config_file(config_name='config.ini'):
    conf = configparser.ConfigParser()
    conf['userinfo'] = {'key': '0',
                        'secret': '0',
                        'token': '0',
                        'last_login': '0'}
    with open(config_name, 'w') as cf:
        conf.write(cf)


def login_upstox(config_name):
    confPath = os.path.join(os.getcwd(), config_name)
    if not os.path.exists(confPath):
        create_config_file(config_name)

    config = configparser.ConfigParser()
    config.read(config_name)
    creds = config['userinfo']

    client = None

    if creds['key'] == '0':
        creds['key'] = input('Please enter the API key - ')
    if creds['secret'] == '0':
        creds['secret'] = input('Please enter the API secret - ')

    s = api.Session(creds['key'])
    s.set_redirect_uri('http://127.0.0.1')
    s.set_api_secret(creds['secret'])
    diff = None

    if creds['last_login'] == '0':
        diff = timedelta(hours=1)
    else:
        now = datetime.now()
        last = datetime.strptime(creds['last_login'], '%d-%m-%Y %H:%M')
        diff = now - last

    if creds['token'] == '0' or diff > timedelta(hours=11, minutes=59):
        url = s.get_login_url()
        print('Auth url - ')
        print(url)
        code = input("Please enter the code from the login page - ")
        s.set_code(code)
        creds['token'] = s.retrieve_access_token()
    else:
        print('Reusing token - ', creds['token'])
    try:
        client = api.Upstox(creds['key'], creds['token'])
    except Exception as e:
        print('ERROR! Unable to start Upstox client.')
        print(e)

    creds['last_login'] = datetime.now().strftime('%d-%m-%Y %H:%M')

    with open(config_name, 'w') as cf:
        config.write(cf)

    return client
