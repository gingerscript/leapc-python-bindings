from flask import Flask
from flask_socketio import SocketIO
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = ''
socketio = SocketIO(app, cors_allowed_origins="*")  # Allow connections from any origin

@app.route("/")
def index():
    return "WebSocket Server Running"

# Function to send tracking data periodically
def send_tracking_data():
    while True:
        tracking_data = {
            "gesture": "fistClose",
            "position": {"x": 120, "y": 250},
            "confidence": 0.95,
            "timestamp": int(time.time())
        }
        socketio.emit("trackingData", tracking_data)  # Send data to connected clients
        time.sleep(0.1)  # Send data every 100ms (adjust as needed)

@socketio.on("connect")
def handle_connect():
    print("Client connected")

if __name__ == "__main__":
    socketio.start_background_task(send_tracking_data)  # Start streaming data
    socketio.run(app, host="0.0.0.0", port=5001)
