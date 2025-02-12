# tracking.py
import leap
import json
import time
import cv2
import os

# We'll just pick a single int for demonstration.
# This is the same file the server reads from.
BUFFER_FILE = "position.json"

class MyListener(leap.Listener):
    def __init__(self):
        super().__init__()
    
    def on_connection_event(self, event):
        print("Leap connection established.")

    def on_device_event(self, event):
        try:
            with event.device.open():
                info = event.device.get_info()
        except leap.LeapCannotOpenDeviceError:
            info = event.device.get_info()
        print(f"Found device {info.serial}")
    
    def dump_data(self, data):
        try:
            with open(BUFFER_FILE, "w") as f:
                json.dump(data, f)
        except IOError as e:
            print(f"Error writing to {BUFFER_FILE}: {e}")

    def on_tracking_event(self, event):
        # If there's at least one hand, pick the first
        if event.hands:
            for hand in event.hands:
            # hand = event.hands[0]
                # Let's pick the palm x for demonstration
                gesture = "N/A"
                palm_x = hand.palm.position.x
                palm_y = hand.palm.position.y
                palm_z = hand.palm.position.z
                # Or do your own logic to get the "number" you want
                # e.g. maybe round it
                x_pos = int(round(palm_x))
                y_pos = int(round(palm_y))
                z_pos = int(round(palm_z))
                # Write that to the file
                
                data = {
                        "hand_position" : {
                            "x" : x_pos,
                            "y" : y_pos,
                            "z" : z_pos
                            },
                        "chirality" : int(hand.type.value),
                        "gesture" : gesture,
                        "timestamp": time.time_ns()
                        }
                
                self.dump_data(data)

                # Optionally print
                # print("Palm X =", palm_x, " => storing", x_pos)

def main():
    my_listener = MyListener()
    connection = leap.Connection()
    connection.add_listener(my_listener)

    running = True

    with connection.open():
        connection.set_tracking_mode(leap.TrackingMode.Desktop)

        # Example: show a simple black window or do nothing
        while running:
            # (Optional) If you have a debug window:
            # blank_img = 255 * (1 - 0)*None  # Not doing real CV now
            cv2.waitKey(1)

            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord("q"):
                running = False

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
