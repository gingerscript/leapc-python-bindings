import eventlet
eventlet.monkey_patch()  # Ensure async compatibility

from flask import Flask, render_template
from flask_socketio import SocketIO
import time


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    return "WebSocket Streaming Server Running!"

def stream_numbers():
    """Background task that emits a looping count from 0 to 9"""
    while True:
        for i in range(10):
            socketio.emit("number_update", {"number": i})
            time.sleep(1)  # Simulate delay

@socketio.on("connect")
def handle_connect():
    print("Client connected!")
    socketio.start_background_task(stream_numbers)

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected!")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
