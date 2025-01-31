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
    Background task that polls the JSON buffer for changes
    and emits the full hand object via Socket.IO.
    """
    last_x, last_y, last_z = None, None, None
    last_chirality = None
    last_gesture = None
    last_time = None

    while True:
        try:
            with open(BUFFER_FILE, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file is missing/corrupt, use last known values or default to 0.0
            data = {
                "hand_position": {
                    "x": last_x if last_x is not None else 0.0,
                    "y": last_y if last_y is not None else 0.0,
                    "z": last_z if last_z is not None else 0.0
                },
                "chirality": last_chirality if last_chirality is not None else 0,
                "gesture": last_gesture if last_gesture is not None else "N/A",
                "timestamp": "N/A"
            }

        # Ensure `hand_position` is a dictionary
        hand_position = data.get("hand_position", {})
        if not isinstance(hand_position, dict):
            hand_position = {"x": last_x, "y": last_y, "z": last_z}

        x_value = hand_position.get("x", last_x if last_x is not None else 0.0)
        y_value = hand_position.get("y", last_y if last_y is not None else 0.0)
        z_value = hand_position.get("z", last_z if last_z is not None else 0.0)
        chirality_value = data.get("chirality", last_chirality if last_chirality is not None else 0)
        gesture_value = data.get("gesture", last_gesture if last_gesture is not None else "N/A")
        curr_time = data.get("timestamp", last_time)

        # Only emit if data has changed
        if (x_value != last_x or y_value != last_y or z_value != last_z or
            chirality_value != last_chirality or gesture_value != last_gesture):

            # Update last known values
            last_x, last_y, last_z = x_value, y_value, z_value
            last_chirality = chirality_value
            last_gesture = gesture_value
            last_time = curr_time

            # Emit full hand object
            socketio.emit("hand_update", {
                "hand_position": {
                    "x": x_value,
                    "y": y_value,
                    "z": z_value
                },
                "chirality": chirality_value,
                "gesture": gesture_value,
                "timestamp": curr_time
            })

        time.sleep(0.01)  # Poll every 50ms

@socketio.on("connect")
def handle_connect():
    print("Client connected!")
    socketio.start_background_task(watch_buffer_and_emit)

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected!")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
