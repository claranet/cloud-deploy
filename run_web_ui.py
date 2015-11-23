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

if __name__ == '__main__':
    app.config['DEBUG'] = True
    options = {
        'bind': '0.0.0.0:5001',
        'workers': 1,
        'worker_class': 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker',
    }
    StandaloneApplication(app, options).run()
