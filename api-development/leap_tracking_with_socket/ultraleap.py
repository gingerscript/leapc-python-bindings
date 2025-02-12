import leap
import time
import cv2
import json
from multiprocessing import Process
############################################# 
# UltraLeap listener 
############################################# 
class UltraLeapListener(leap.Listener):
    def __init__(self):
        super().__init__()
        
    def on_connection_event(self, event):
        print("Leap connection established.")

    def dispatch(self,data):
        pass

    def on_device_event(self, event):
        try:
            with event.device.open():
                info = event.device.get_info()
        except leap.LeapCannotOpenDeviceError:
            info = event.device.get_info()
        print(f"Found device {info.serial}")

    def on_tracking_event(self, event):
        data = {
                "timestamp":time.time_ns(),
                "hands":{},
                "hand_count":len(event.hands)
            }
        if len(event.hands) > 0:
            for hand_index in range(0,len(event.hands)):
                hand = event.hands[hand_index]
                chirality = int(hand.type.value)
                
                if chirality == 0:
                    data["hands"]["left"]={}
                    hand_data = data["hands"]["left"]
                else:
                    data["hands"]["right"]={}
                    hand_data = data["hands"]["right"]

                palm = hand.palm
                    
                hand_data["palm"] = {
                    "position":list(palm.position),
                    "velocity":list(palm.velocity),
                    "normal":list(palm.normal),
                    "stabilized_position":list(palm.stabilized_position),
                    "direction":list(palm.direction),
                    "orientation":{
                        "x":palm.orientation.x,
                        "y":palm.orientation.y,
                        "z":palm.orientation.z,
                        "w":palm.orientation.w,
                    },
                    "width":palm.width,
                }

                hand_data["pinch_strength"] = hand.pinch_strength
                hand_data["grab_strength"] = hand.grab_strength
                hand_data["id"] = hand.id
                hand_data["flags"] = hand.flags
                hand_data["confidence"] = hand.confidence
                hand_data["visible_time"] = hand.visible_time
                hand_data["pinch_distance"] = hand.pinch_distance
                hand_data["grab_angle"] = hand.grab_angle

                # finger data
                hand_data["fingers"]=[]
                for finger_index in range(0, len(hand.digits)):
                    digit = hand.digits[finger_index]
                    hand_data["fingers"].append([])
                    for bone_index in range(0, 4):
                        bone = digit.bones[bone_index]
                        hand_data["fingers"][finger_index].append([list(bone.next_joint)])
                # arm data
                hand_data["arm"]={
                    "prev_joint":list(hand.arm.prev_joint),
                    "next_joint":list(hand.arm.next_joint),
                    "width":hand.arm.width,
                    "rotation":{
                        "x":hand.arm.rotation.x,
                        "y":hand.arm.rotation.y,
                        "z":hand.arm.rotation.z,
                        "w":hand.arm.rotation.w,
                    },
                }

        self.dispatch(data)

############################################# 
# UltraLeap tracking 
############################################# 
class UltraLeap():
    def __init__(self,listener):
        # Process.__init__(self)
        # self.daemon = True
        self.listener = listener
        self.run()

    def run(self): 
        connection = leap.Connection()
        connection.add_listener(self.listener)
        running = True
        with connection.open():  # Keeps Leap Motion running in its own loop
            connection.set_tracking_mode(leap.TrackingMode.Desktop)
            
            
            while running:
                # (Optional) If you have a debug window:
                # blank_img = 255 * (1 - 0)*None  # Not doing real CV now
                cv2.waitKey(1)

                # Press 'q' to quit
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    running = False
       
        leap_listener.dispose()
        cv2.destroyAllWindows()
        print("Connection closed")

    