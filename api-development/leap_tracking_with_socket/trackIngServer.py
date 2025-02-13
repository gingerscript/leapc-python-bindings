# tracking.py
import leap
import time
import eventlet
eventlet.monkey_patch()  # Ensure async compatibility
from flask import Flask
from flask_socketio import SocketIO

from multiprocessing import Process
import multiprocessing

hand_data_offset = 10
hand_data_length = 70  # bones (5*4) * xyz (3) + other (10)

############################################# 
# Decorate hand data index structure
############################################# 
structure={
    "timestampOffset1":0,
    "timestampOffset2":1,
    "timestampOffset3":2,
    "hand_type":3,
    "hand_count":4
} 

hand_data_length = 5
for hand_index in range(0,2):
    offset = hand_data_offset*hand_index-1
    if hand_index == 0:
        hand_type = "left"
    else:
        hand_type = "right"
        
    structure[f"{hand_type}_hand_palm.x"] = (hand_data_offset:=hand_data_offset+1)-1
    structure[f"{hand_type}_hand_palm.y"] = (hand_data_offset:=hand_data_offset+1)-1
    structure[f"{hand_type}_hand_palm.z"] = (hand_data_offset:=hand_data_offset+1)-1
    structure[f"{hand_type}_pinch_strength"] = (hand_data_offset:=hand_data_offset+1)-1
    structure[f"{hand_type}_grab_strength"] = (hand_data_offset:=hand_data_offset+1)-1
    structure[f"{hand_type}_gesture"] = (hand_data_offset:=hand_data_offset+1)-1

    hand_data_length +=10
    for finger_index in range(0, 5):
        for bone_index in range(0, 4):
            structure[f"{hand_type}_finger_{finger_index}_{bone_index}_x"] = (hand_data_offset:=hand_data_offset+1)-1
            structure[f"{hand_type}_finger_{finger_index}_{bone_index}_y"] = (hand_data_offset:=hand_data_offset+1)-1
            structure[f"{hand_type}_finger_{finger_index}_{bone_index}_z"] = (hand_data_offset:=hand_data_offset+1)-1
    hand_data_length+= 20*3

############################################# 
# UltraLeap listener 
############################################# 
class UltraLeapListener(leap.Listener):
    def __init__(self,return_dict):
        super().__init__()
        self.listeners = []
        self.return_dict = return_dict

    def add_listener(self, listener):
        print("Listener added")
        self.listeners.append(listener)
        
    def on_connection_event(self, event):
        print("Leap connection established.")

    def on_device_event(self, event):
        try:
            with event.device.open():
                info = event.device.get_info()
        except leap.LeapCannotOpenDeviceError:
            info = event.device.get_info()
        print(f"Found device {info.serial}")
    def on_tracking_event(self, event):
        hands_data = self.return_dict
        # timestamp = str(time.time_ns())
        # hands_data[structure["timestampOffset1"]] = int(timestamp[0:7])
        # hands_data[structure["timestampOffset2"]] = int(timestamp[7:14])
        # hands_data[structure["timestampOffset3"]] = int(timestamp[14:20])
        hands_data[structure["hand_count"]] = len(event.hands)
        if len(event.hands)>0:
            # for hand in event.hands:
            # timestamp = str(time.time_ns())
            # hands_data[structure["timestampOffset1"]] = int(timestamp[0:7])
            # hands_data[structure["timestampOffset2"]] = int(timestamp[7:14])
            # hands_data[structure["timestampOffset3"]] = int(timestamp[14:20])
            hands_data[structure["hand_type"]] = int(event.hands[0].type.value)
            # hands_data[structure["hand_count"]] = len(event.hands)
            for hand_index in range(0, len(event.hands)):
                hand = event.hands[hand_index]
                chirality = int(hand.type.value)
                if chirality==0:
                    hand_type = "left"
                else:
                    hand_type = "right"

                # Let's pick the palm x for demonstration
                hands_data[structure[f"{hand_type}_hand_palm.x"]] = hand.palm.position.x
                hands_data[structure[f"{hand_type}_hand_palm.y"]] = hand.palm.position.y
                hands_data[structure[f"{hand_type}_hand_palm.z"]] = hand.palm.position.z
                hands_data[structure[f"{hand_type}_pinch_strength"]] = hand.pinch_strength
                hands_data[structure[f"{hand_type}_grab_strength"]] = hand.grab_strength

                for index_digit in range(0, 5):
                    digit = hand.digits[index_digit]
                    for index_bone in range(0, 4):
                        bone = digit.bones[index_bone]
                        bone_pos = bone.next_joint
                        hands_data[structure[f"{hand_type}_finger_{index_digit}_{index_bone}_x"]] = bone_pos.x
                        hands_data[structure[f"{hand_type}_finger_{index_digit}_{index_bone}_y"]] = bone_pos.y
                        hands_data[structure[f"{hand_type}_finger_{index_digit}_{index_bone}_z"]] = bone_pos.z
        else:
            hands_data[0] = -1

        
############################################# 
# UltraLeap tracking 
############################################# 
class UltraLeap(Process):
    def __init__(self,return_dict):
        Process.__init__(self)
        self.daemon = True
        self.return_dict = return_dict

    def run(self): 
        leap_listener = UltraLeapListener(self.return_dict)
        connection = leap.Connection()
        connection.add_listener(leap_listener)
        with connection.open():  # Keeps Leap Motion running in its own loop
            connection.set_tracking_mode(leap.TrackingMode.Desktop)
       
        print("Connection closed")

############################################# 
# Socket server with tracking
############################################# 
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*",cors_credentials=False)

def transfer_data():
    source = list(return_dict)
    timestamp = time.time_ns()
    hand_count = int(source[structure["hand_count"]])
    data = {
            "timestamp":timestamp,
            "hands":{},
            "hand_count":hand_count,
        }
    if hand_count != 0:
        chirality = source[3]
        
        for hand_index in range(0,2):
            if hand_index == 0:
                hand_type = "left"
            else:
                hand_type = "right"
            data["hands"][hand_type] = {}
            data["hands"][hand_type]["palm"]={
                "position":{
                    "x":source[structure[f"{hand_type}_hand_palm.x"]],
                    "y":source[structure[f"{hand_type}_hand_palm.y"]],
                    "z":source[structure[f"{hand_type}_hand_palm.z"]],
                },
            }
            data["hands"][hand_type]["pinch_strength"] = source[structure[f"{hand_type}_pinch_strength"]]
            data["hands"][hand_type]["grab_strength"] = source[structure[f"{hand_type}_grab_strength"]]
            data["hands"][hand_type]["gesture"] = source[structure[f"{hand_type}_gesture"]]

            data["hands"][hand_type]["finger"] = []
            for finger_index in range(0, 5):
                data["hands"][hand_type]["finger"].append([]) 
                for bone_index in range(0, 4):
                    data["hands"][hand_type]["finger"][finger_index].append([
                        source[structure[f"{hand_type}_finger_{finger_index}_{bone_index}_x"]],
                        source[structure[f"{hand_type}_finger_{finger_index}_{bone_index}_y"]],
                        source[structure[f"{hand_type}_finger_{finger_index}_{bone_index}_z"]]
                    ]) 
    return data
    # return {}
def listener():
    tracking_response_time = 0
    while True:
        timestamp = time.time_ns()/1000000
        # dispatch per 30ms
        if(timestamp - tracking_response_time > 600):
            socketio.emit("tracking_update",transfer_data())
            tracking_response_time = timestamp
    
@app.route('/')
def index():
    return "WebSocket Streaming Server Running!"
@socketio.on("connect")
def handle_connect():
    print("Client connected!")
    socketio.start_background_task(listener)

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected!")


if __name__ == "__main__":
    return_dict = multiprocessing.Array("f",size_or_initializer=hand_data_length,lock=False)
    UltraLeap(return_dict).start()
    socketio.run(app, host="0.0.0.0", port=5000)
    
    
