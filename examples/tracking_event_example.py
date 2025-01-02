"""Prints the palm position of each hand, every frame. When a device is 
connected we set the tracking mode to desktop and then generate logs for 
every tracking frame received. The events of creating a connection to the 
server and a device being plugged in also generate logs. 
"""

import leap
import time

# FOR WINDOWS TODO: Add if windows
import ctypes

class ActionController():
    MOUSEEVENTF_LEFTDOWN = 0x0002  # Left button down
    MOUSEEVENTF_LEFTUP = 0x0004    # Left button up
    
    def __init__(self):
        self.max_min_x = [0, 0]
        self.max_min_y = [0, 0]
        self.max_min_z = [0, 0]
        self.scaling_sensitivity = 0
        
        # Capture device dimensions
        self.cap_width = 1920  # Example video capture width
        self.cap_height = 1080  # Example video capture height

        # Screen resolution
        self.screen_width = 1920  # Default screen width
        self.screen_height = 1080  # Default screen height

        # Play area margins (adjusted dynamically)
        self.x_margin = 0
        self.y_margin = 0
        self.x_min = 0
        self.x_max = self.cap_width
        self.y_min = 0
        self.y_max = self.cap_height

    # This serves as an event router, taking routing event data to the proper handler
    def tracking_event_router(self, event, state):
        
        match state:
            case 0:
                pass # placeholder for sleep state
            case 1:
                self.active_handler(event) # pass event to active_handler
            case 2:
                self.setup_handler(event) # pass event to setup_handler
            case _:
                raise ValueError("Unexpected state {state} in handle_tracking_event")
            
    def active_handler(self, event):
         for hand in event.hands:

            hand_type = "left" if str(hand.type) == "HandType.Left" else "right"
            
            if hand_type == "right":
                pointer_x, pointer_y = hand.palm.position.x, hand.palm.position.z
                self.move_cursor(pointer_x, pointer_y, 1, 1) #update cursor on each update
            
            elif hand_type == "left":
                # Check grab strength for left hand
                grab_strength = hand.grab_strength
                if grab_strength > 0.9:  # Assuming 0.9 indicates a fist (adjust threshold as needed)
                    self.trigger_click_event()  # Custom function to handle the click event
                
            # print(
            #     f"Hand id {hand.id} is a {hand_type} hand with position ({hand.palm.position.x}, {hand.palm.position.y}, {hand.palm.position.z})."
            # )
    
    def setup_handler(self, event):
        # This function once called will place the user in play_area_setup mode (maybe a blocking state)
        # store maximum and 
        for hand in event.hands:

            hand_type = "left" if str(hand.type) == "HandType.Left" else "right"
            
            print('hand detected')
            
            hand_pos = hand.palm.position
            self.max_min_x = [max(self.max_min_x[0], hand_pos.x), min(self.max_min_x[1], hand_pos.x)]
            self.max_min_y = [max(self.max_min_y[0], hand_pos.y), min(self.max_min_y[1], hand_pos.y)]
            self.max_min_z = [max(self.max_min_z[0], hand_pos.z), min(self.max_min_z[1], hand_pos.z)]
        
    def move_cursor(self, x: int, y: int, scaling_x: float, scaling_y: float):
        
        #TODO Need to implement setup_handler to properly map screen, along with an enter and a exit method between states
        #TODO ensure to bound x,y values to the dimensions of the current screen to avoid undefined behavior
        
        # x_ratio, y_ratio = (self.screen_width/(self.cap_width)), (self.screen_height/(self.cap_height)) # x * x_ratio = screen_x_pos
        
        
        # # Create Play Area box in center of video of dimension: cap_dimensions / scaling_sensitivity
        # x_margin, y_margin = (self.cap_width/scaling_x) / 2, (self.cap_height/scaling_y) / 2  # Calculate total margin area, divide by 2
        # x_min, y_min = x_margin, y_margin
        # x_max, y_max = self.cap_width - x_margin, self.cap_height - y_margin 
        
        # # Shift Play Area box towards the right by the margin
        # x = x-x_margin
        # y = y-y_margin
        
        # # Clamp values to exist within the desktop borders
        # # x = clamp(x, x_min, x_max)
        # # y = clamp(y, y_min, y_max)
        
        # x = (x * x_ratio) * scaling_x # Map x video pos to screen pos, multiply by scaling sensitivity 
        # y = (y * y_ratio) * scaling_y  # Map y video to to screen pos. multiply by scaling sensitivity
        
        # Move Cursor
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    
    def trigger_click_event(self):
        ctypes.windll.user32.mouse_event(ActionController.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)  # Simulate left button press
        ctypes.windll.user32.mouse_event(ActionController.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)    # Simulate left button release
        

class MyListener(leap.Listener):
    def __init__(self, action_controller):
        super().__init__()
        self.action_controller = action_controller
        self.state = 0  # FSM states 0: Sleep, 1: Active, 2: Setup
        
    def set_state(self, state):
        self.state = state
    
    def on_connection_event(self, event):
        print("Connected")
        self.state = 1 # new device found, set to active stat

    def on_device_event(self, event):
        try:
            with event.device.open():
                info = event.device.get_info()
                self.state = 1
        except leap.LeapCannotOpenDeviceError:
            info = event.device.get_info()
            
        print(f"Found device {info.serial}")

    def on_tracking_event(self, event):
        # print(f"Frame {event.tracking_frame_id} with {len(event.hands)} hands.")
        
        
        self.action_controller.tracking_event_router(event, self.state)
        
        
            # print(
            #     f"Hand x position range: {max_min_x[0]}, {max_min_x[1]} \n Hand y position range: {max_min_y[0]}, {max_min_y[1]} \n Hand z position range: {max_min_z[0]}, {max_min_z[1]}"
            # )
        # State machine:
        # What state? Pass state to action handler to determine how to handle provided event from the event listener.

def main():
    action_controller = ActionController()
    my_listener = MyListener(action_controller)
    

    connection = leap.Connection()
    connection.add_listener(my_listener)

    running = True

    with connection.open():
        connection.set_tracking_mode(leap.TrackingMode.Desktop)
        print("Select the following Modes: \n a: Active \n s: Sleep \n c: Setup \n x: quit")
        while running:
            user_input = input("Enter your choice: ").strip().lower()
            
            if user_input == "a":
                print("Switching to Active Mode...")
                my_listener.set_state(1)
                
            elif user_input == "s":
                print("Switching to Sleep Mode...")
                my_listener.set_state(0)
                
            elif user_input == "c":
                print("Switching to Setup Mode...")
                my_listener.set_state(2)
                
            elif user_input == "x":
                print("Exiting...")
                running = False
            else:
                print("Invalid input. Please select a valid option.")
            time.sleep(1)


if __name__ == "__main__":
    main()
