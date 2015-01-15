from eve import Eve
from apps import pre_GET_apps
from flask.ext.bootstrap import Bootstrap
from eve_docs import eve_docs


app = Eve()

app.on_pre_GET_apps += pre_GET_apps

Bootstrap(app)
app.register_blueprint(eve_docs, url_prefix='/docs')
if __name__ == '__main__':
    app.run(host='0.0.0.0')
