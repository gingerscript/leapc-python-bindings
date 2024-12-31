"""Prints the palm position of each hand, every frame. When a device is 
connected we set the tracking mode to desktop and then generate logs for 
every tracking frame received. The events of creating a connection to the 
server and a device being plugged in also generate logs. 
"""

import leap
import time

MOUSEEVENTF_LEFTDOWN = 0x0002  # Left button down
MOUSEEVENTF_LEFTUP = 0x0004    # Left button up

# FOR WINDOWS TODO: Add if windows
import ctypes

def move_cursor(x, y):
    ctypes.windll.user32.SetCursorPos(int(x), int(y))

def trigger_click_event():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)  # Simulate left button press
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)    # Simulate left button release


class MyListener(leap.Listener):
    def __init__(self):
        self.max_min_x = [0, 0]
        self.max_min_y = [0, 0]
        self.max_min_z = [0, 0]

    
    def on_connection_event(self, event):
        print("Connected")

    def on_device_event(self, event):
        try:
            with event.device.open():
                info = event.device.get_info()
        except leap.LeapCannotOpenDeviceError:
            info = event.device.get_info()

        print(f"Found device {info.serial}")

    def on_tracking_event(self, event):
        print(f"Frame {event.tracking_frame_id} with {len(event.hands)} hands.")
        for hand in event.hands:
            hand_type = "left" if str(hand.type) == "HandType.Left" else "right"
            
            if hand_type == "right":
                pointer_x, pointer_y = hand.palm.position.x, hand.palm.position.z
                move_cursor(pointer_x, pointer_y) #update cursor on each update
            
            elif hand_type == "left":
                # Check grab strength for left hand
                grab_strength = hand.grab_strength
                if grab_strength > 0.9:  # Assuming 0.9 indicates a fist (adjust threshold as needed)
                    trigger_click_event()  # Custom function to handle the click event
                
            # print(
            #     f"Hand id {hand.id} is a {hand_type} hand with position ({hand.palm.position.x}, {hand.palm.position.y}, {hand.palm.position.z})."
            # )
            hand_pos = hand.palm.position
            self.max_min_x = [max(self.max_min_x[0], hand_pos.x), min(self.max_min_x[1], hand_pos.x)]
            self.max_min_y = [max(self.max_min_y[0], hand_pos.y), min(self.max_min_y[1], hand_pos.y)]
            self.max_min_z = [max(self.max_min_z[0], hand_pos.z), min(self.max_min_z[1], hand_pos.z)]
            
            # print(
            #     f"Hand x position range: {max_min_x[0]}, {max_min_x[1]} \n Hand y position range: {max_min_y[0]}, {max_min_y[1]} \n Hand z position range: {max_min_z[0]}, {max_min_z[1]}"
            # )

def main():
    my_listener = MyListener()

    connection = leap.Connection()
    connection.add_listener(my_listener)

    running = True

    with connection.open():
        connection.set_tracking_mode(leap.TrackingMode.Desktop)
        while running:
            time.sleep(1)


if __name__ == "__main__":
    main()
