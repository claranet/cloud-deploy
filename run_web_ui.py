import argparse

import gunicorn.app.base
from gunicorn.six import iteritems

from web_ui import app as web_ui_app
from web_ui import websocket

app = web_ui_app.app
ws = websocket.create_ws(app)

class StandaloneApplication(gunicorn.app.base.BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super(StandaloneApplication, self).__init__()

    def load_config(self):
        config = dict([(key, value) for key, value in iteritems(self.options)
                       if key in self.cfg.settings and value is not None])
        for key, value in iteritems(config):
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

def run_standalone():
    app.config['DEBUG'] = True
    options = {
        'bind': '0.0.0.0:5001',
        'workers': 1,
        'worker_class': 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker',
        'debug': True,
        'timeout': 600,
    }
    StandaloneApplication(app, options).run()

def run_eclipse():
    ws.run(app, host='0.0.0.0', port=5001, log_output=True)

def parse_args():
    parser = argparse.ArgumentParser(
        description='Run the Ghost web ui from the command line.'
    )
    parser.add_argument('--eclipse', action='store_true')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    if args.eclipse:
        run_eclipse()
    else:
        run_standalone()