import eventlet
eventlet.monkey_patch()  # Ensure async compatibility for SocketIO

from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
# Allow CORS if needed. For local dev, "*"" is often fine:
socketio = SocketIO(app, cors_allowed_origins="*")
@app.route('/')
def index():
    return "WebSocket Streaming Server Running!"
@socketio.on('connect')
def handle_connect():
    print("Client connected.")

@socketio.on('tracking_data')
def handle_tracking_data(data):
    socketio.emit("tracking_update", data)

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected.")


def run(port=5000,debug=True,host="0.0.0.0"):
    # Run on port 5000, accessible at http://localhost:5000
    socketio.run(app, host=host, port=port, debug=debug)
    
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)