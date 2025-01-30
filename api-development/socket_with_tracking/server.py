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
    and emits the full hand object via Socket.IO.
    """
    last_data = None  # Track the last sent JSON data

    while True:
        try:
            with open(BUFFER_FILE, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {
                "hand_position": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0
                },
                "chirality": 0
            }

        # Ensure `hand_position` exists and is a dictionary
        if not isinstance(data.get("hand_position", {}), dict):
            data["hand_position"] = {"x": 0.0, "y": 0.0, "z": 0.0}

        # Only emit if data has changed
        if data != last_data:
            last_data = data
            socketio.emit("hand_update", data)  # Emit full object

        time.sleep(0.05)  # Poll every 50ms



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
