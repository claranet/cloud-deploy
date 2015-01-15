from eve import Eve
from apps import pre_GET_apps
app = Eve()

app.on_pre_GET_apps += pre_GET_apps

if __name__ == '__main__':
    app.run()
