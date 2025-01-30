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
    last_x_value = None
    last_y_value = None
    last_z_value = None

    while True:
        try:
            with open(BUFFER_FILE, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {
                "hand_position": {
                    "x": last_x_value,
                    "y": last_y_value,
                    "z": last_z_value
                },
                "chirality": 0
            }

        # Ensure hand_position is always a dictionary
        hand_position = data.get("hand_position", {})
        if not isinstance(hand_position, dict):
            hand_position = {"x": 0.0, "y": 0.0, "z": 0.0}

        # Extract values with last known values as default
        x_value = hand_position.get("x", last_x_value)
        y_value = hand_position.get("y", last_y_value)
        z_value = hand_position.get("z", last_z_value)

        # If any value has changed, emit an update
        if (x_value != last_x_value) or (y_value != last_y_value) or (z_value != last_z_value):
            last_x_value, last_y_value, last_z_value = x_value, y_value, z_value

            socketio.emit("number_update", {
                "x": x_value,
                "y": y_value,
                "z": z_value
            })

        time.sleep(0.05)  # Check every 50ms


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
