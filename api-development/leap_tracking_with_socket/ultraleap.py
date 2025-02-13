import leap
import time
import cv2
import json

import argparse
from tracking_lib.canvas import Canvas, _TRACKING_MODES
from tracking_lib.controller import ActionController

class GestureActionController():
    def __init__(self):
        self.state = 0

        parser = argparse.ArgumentParser(
            description="Leap Motion Tracking with optional Canvas display."
        )
        parser.add_argument("--canvas", action="store_true",
                            help="Show the OpenCV canvas window.")
        parser.add_argument("--control", action="store_true",
                            help="Enable click and drag OS controls.")
        self.args = parser.parse_args()
        # 1) Setup Canvas & Controller
        self.canvas = Canvas()
        self.action_controller = ActionController(self.canvas, enable_control=self.args.control)
        self.action_controller.load_config()  # Load existing play_area_config.json if present

    def set_state(self, new_state):
        self.state = new_state

    def get_state(self):
        return self.state
    
    def get_data(self):
        return json.loads(self.action_controller.get_state())
    
    def parsing_data(self, data):
        self.action_controller.tracking_event_router(data, self.get_state())
        self.update_canvas(data)
        return self.get_data()

    def update_canvas(self,data):
        """
        Render only affects the canvas' output_image
        """ 
        self.action_controller.canvas.render_hands(data)
    def show_canvas(self):
        cv2.imshow(self.canvas.name, self.canvas.output_image)

    def toggle_hands_format(self):
        print("Toggling hand format between Skeleton/Dots...")
        self.canvas.toggle_hands_format()
    def hasCanvas(self):
        """ 
        Check if the user has specified the --canvas flag.
        :return: True if --canvas was specified, False otherwise.
        """
        return self.args.canvas
    def dispose(self):
        if self.hasCanvas():
            cv2.destroyAllWindows()


############################################# 
# UltraLeap listener 
############################################# 
class UltraLeapListener(leap.Listener):
    def __init__(self):
        super().__init__()
        self.init_counter = 0

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

    def before_tracking_dispatch(self,source,data):
        pass
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
        self.before_tracking_dispatch(event,data)
        # Step 4: Emit to server (no local file writes)
        if self.init_counter < 4: # emit every 4 frames to prevent IO bottleneck
            self.init_counter += 1
        else:
            self.init_counter = 0
            
            self.dispatch(data)
        return data
    def before_run(self):
        pass
    def running(self):
        pass
    def dispose(self):
        pass

class UltraLeapActionListener(UltraLeapListener):
    def __init__(self):
        super().__init__()
        self.gesture_action_controller = GestureActionController()


    def set_state(self,value):
        return self.gesture_action_controller.set_state(value)
    
    def on_device_event(self, event):
        super().on_device_event(event)
        self.set_state(1)

    def before_tracking_dispatch(self,source,data):
        action_data = self.gesture_action_controller.parsing_data(source)
        data["complex_gesture"] = action_data["complex_gesture"]


    def before_run(self):
        print(" No --canvas provided. Use console commands:")
        print("  x => Exit")
        print("  a => Active Mode")
        print("  s => Sleep Mode")
        print("  c => Setup Mode")
        print("  f => Toggle Hand Format")

    def running(self):
        gesture_action = self.gesture_action_controller
        if gesture_action.hasCanvas():
            gesture_action.show_canvas()

        user_input = input("Enter command: ").strip().lower()
        if user_input == 'x':
            print("Exiting...")
            return False

        elif user_input == 'a':
            print("Switching to Active Mode...")
            self.set_state(1)

        elif user_input == 's':
            print("Switching to Sleep Mode...")
            self.set_state(0)

        elif user_input == 'c':
            print("Switching to Setup Mode...")
            self.set_state(2)

        elif user_input == 'f':
            print("Toggling hand format between Skeleton/Dots...")
            gesture_action.toggle_hands_format()
        else:
            print("Unknown command. Valid: x, a, s, c, f")
        return True
    def dispose(self):
        self.gesture_action_controller.dispose()
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
            self.listener.before_run()
            while running:
                self.listener.running()
                

    