from web_ui import app as web_ui_app
from web_ui import websocket 

app = web_ui_app.app
ws = websocket.create_ws(app)

if __name__ == '__main__':
    ws.run(app, host='0.0.0.0', port=5001)