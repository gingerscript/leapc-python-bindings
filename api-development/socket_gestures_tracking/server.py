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

@socketio.on('hand_data')
def handle_hand_data(data):
    """
    Whenever the client (tracking_socket.py) sends 'hand_data',
    we can log or process 'data' here. Then rebroadcast it to
    any other connected clients under the event name 'hand_update'.
    """
    print("Received hand_data from client, broadcasting to others...")
    socketio.emit("hand_update", data)

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected.")

if __name__ == "__main__":
    # Run on port 5000, accessible at http://localhost:5000
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
