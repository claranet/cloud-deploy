from web_ui import create_app, create_ws 

app = create_app()
ws = create_ws(app)

if __name__ == '__main__':
    ws.run(app, host='0.0.0.0', port=5001)
