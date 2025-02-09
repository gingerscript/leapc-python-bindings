import eventlet
eventlet.monkey_patch()  # Ensure async compatibility

import json
import time
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

BUFFER_FILE = "position.json"

@app.route('/')
def index():
    return "WebSocket Streaming Server Running!"

def watch_buffer_and_emit():
    """
    Background task that polls position.json for changes
    and emits the entire {left_hand, right_hand, complex_gesture} structure.
    """
    last_data = None
    while True:
        try:
            with open(BUFFER_FILE, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Default fallback structure if file is missing or corrupt
            if last_data is None:
                data = {
                    "left_hand": {
                        "position": {"x": 0, "y": 0, "z": 0},
                        "gesture": "N/A",
                        "timestamp": 0
                    },
                    "right_hand": {
                        "position": {"x": 0, "y": 0, "z": 0},
                        "gesture": "N/A",
                        "timestamp": 0
                    },
                    "complex_gesture": {
                        "gesture": "N/A",
                        "gesture_timestamp": 0
                    }
                }
            else:
                data = last_data

        # If the new data differs from what we last emitted, broadcast it
        if data != last_data:
            last_data = data
            socketio.emit("hand_update", data)

        time.sleep(0.01)  # Poll ~ every 10ms

@socketio.on("connect")
def handle_connect():
    print("Client connected!")
    # Start the background polling task
    socketio.start_background_task(watch_buffer_and_emit)

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected!")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
