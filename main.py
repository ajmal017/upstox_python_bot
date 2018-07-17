import os
from git import Repo

DIR_NAME = os.path.join(os.getcwd(), 'upstox_python_bot')
REMOTE_URL = 'https://github.com/shashquatch/upstox_python_bot.git'

repo = None
origin = None

if not os.path.isdir(DIR_NAME):
    print('Repo not created. Creating repo dir and cloning...')
    os.mkdir(DIR_NAME)
    repo = Repo.init(DIR_NAME)
    origin = repo.create_remote('origin', REMOTE_URL)
    origin.pull()
else:
    repo = Repo(DIR_NAME)
    origin = repo.remotes.origin

origin.fetch()

print('Loaded branch %s' % origin.refs[0])
