# server.py
import eventlet
eventlet.monkey_patch()  # Ensure async compatibility

import json
import time
import threading

from flask import Flask, render_template
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


BUFFER_FILE = "position.json"

@app.route('/')
def index():
    return "WebSocket Streaming Server Running!"

def watch_buffer_and_emit():
    """
    Background task that polls the JSON buffer for changes
    and emits the updated position via Socket.IO.
    """
    last_value = None
    while True:
        try:
            with open(BUFFER_FILE, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"hand_position": 0}
        except json.JSONDecodeError:
            data = {"hand_position": 0}

        current_value = data.get("hand_position", 0)

        # If the value in the file has changed, emit an update
        if current_value != last_value:
            last_value = current_value
            
            socketio.emit("number_update", {"number": current_value})

        time.sleep(.02)  # Check 1 times per second

@socketio.on("connect")
def handle_connect():
    print("Client connected!")
    socketio.start_background_task(watch_buffer_and_emit)

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected!")

if __name__ == "__main__":
    # Run the SocketIO server (on localhost:5000)
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
