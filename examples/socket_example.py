import eventlet
eventlet.monkey_patch()  # Required for async compatibility

import time
import leap
from leap import datatypes as ldt
from flask import Flask
from flask_socketio import SocketIO, emit
import threading  # Needed to run Leap Motion in a separate thread



app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

global_pinching_info = []  # Stores latest pinch data

def location_end_of_finger(hand: ldt.Hand, digit_idx: int) -> ldt.Vector:
    digit = hand.digits[digit_idx]
    return digit.distal.next_joint

def sub_vectors(v1: ldt.Vector, v2: ldt.Vector):
    return map(float.__sub__, v1, v2)

def fingers_pinching(thumb: ldt.Vector, index: ldt.Vector):
    diff = list(map(abs, sub_vectors(thumb, index)))
    pinching = (diff[0] < 20 and diff[1] < 20 and diff[2] < 20)
    return pinching, diff

class PinchingListener(leap.Listener):
    """ Leap Motion Listener that updates pinch detection every 50 frames. """

    def on_tracking_event(self, event):
        global global_pinching_info
        if event.tracking_frame_id % 50 == 0:
            frame_info = []

            for hand in event.hands:
                hand_type = "Left" if hand.type == leap.HandType.Left else "Right"
                thumb_tip = location_end_of_finger(hand, 0)
                index_tip = location_end_of_finger(hand, 1)

                pinching, diff_array = fingers_pinching(thumb_tip, index_tip)
                print(f"{hand_type} hand is {'pinching' if pinching else 'not pinching'} - diff={diff_array}")

                frame_info.append({
                    "hand_type": hand_type,
                    "pinching": pinching,
                    "diff": diff_array
                })

            global_pinching_info = frame_info

@app.route("/")
def index():
    return "Pinch Detection with Flask-SocketIO is running"

@socketio.on("connect")
def handle_connect():
    print("SocketIO client connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("SocketIO client disconnected")

def broadcast_pinch_data():
    """ Periodically emits pinch data to all WebSocket clients. """
    print("Starting WebSocket broadcasting...")
    while True:
        socketio.sleep(0.5)
        socketio.emit("pinchData", 0)
        print("Broadcasted pinch data")

def run_leap_motion():
    """ Opens Leap Motion connection in a separate thread so it doesn't block Flask. """
    print("Starting Leap Motion listener...")
    listener = PinchingListener()
    connection = leap.Connection()
    connection.add_listener(listener)

    with connection.open():  # Keeps Leap Motion running in its own loop
        while True:
            time.sleep(1)

if __name__ == "__main__":
    # Start Leap Motion in a separate thread so Flask isn't blocked
    leap_thread = threading.Thread(target=run_leap_motion, daemon=True)
    leap_thread.start()

    # Start WebSocket broadcasting task
    socketio.start_background_task(broadcast_pinch_data)

    # Run Flask-SocketIO server (ensuring eventlet is being used)
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=False)
