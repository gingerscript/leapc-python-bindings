"""Prints the palm position of each hand, every frame. When a device is 
connected we set the tracking mode to desktop and then generate logs for 
every tracking frame received. The events of creating a connection to the 
server and a device being plugged in also generate logs. 
"""

import leap
import time
import json
import os

# FOR WINDOWS TODO: Add if windows
import ctypes

class ActionController():
    MOUSEEVENTF_LEFTDOWN = 0x0002  # Left button down
    MOUSEEVENTF_LEFTUP = 0x0004    # Left button up
    
    def __init__(self):
        self.hand_state = {"left": "idle", "right": "idle"}
        self.hand_press_time = {"left": 0.0, "right": 0.0}

        # Pinch thresholds
        self.pinch_threshold = 0.6
        
        # Grab thresholds
        self.grab_threshold = 0.9

        # Common “short vs hold” threshold (seconds)
        self.hold_threshold = 0.3

        # For “grab to scroll”
        self.scroll_sensitivity = 1.0
        self.last_scroll_y = 0.0
        
        # For determining play area
        self.max_min_x = [260, -180]
        self.max_min_y = [50, 0]
        self.max_min_z = [290,-140]
        self.scaling_sensitivity = 0
        
        # Capture device dimensions
        self.cap_width = self.max_min_x[0] - self.max_min_x[1]  # Example video capture width
        self.cap_height = self.max_min_y[0] - self.max_min_y[1]  # Example video capture height

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
        
    def save_config(self, filename="play_area_config.json"):
        """
        Save the current max/min configurations to a JSON file.
        """
        config = {
            "max_min_x": self.max_min_x,
            "max_min_y": self.max_min_y,
            "max_min_z": self.max_min_z
        }
        with open(filename, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Configuration saved to {filename}")

    def load_config(self, filename="play_area_config.json"):
        """
        Load the max/min configurations from a JSON file, if it exists.
        """
        if not os.path.exists(filename):
            print(f"No config file found at {filename}. Using defaults.")
            return

        with open(filename, "r") as f:
            config = json.load(f)
        
        # Update your ActionController attributes
        self.max_min_x = config.get("max_min_x", self.max_min_x)
        self.max_min_y = config.get("max_min_y", self.max_min_y)
        self.max_min_z = config.get("max_min_z", self.max_min_z)

        print(f"Configuration loaded from {filename}")

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
                # Move cursor
                pointer_x, pointer_y = hand.palm.position.x, hand.palm.position.z
                self.move_cursor(pointer_x, pointer_y, 1, 1)

                # Pinch + Grab combined logic
                self.update_right_hand_state(
                    grab_strength=hand.grab_strength,
                    pinch_strength=hand.pinch_strength,
                    palm_y=hand.palm.position.y
                )

            elif hand_type == "left":
                # Ignore left hand
                pass
            
    def update_right_hand_state(self, grab_strength, pinch_strength, palm_y):
        """
        A single FSM for the right hand that:
        - Pinch => short pinch click, pinch hold => click-and-hold
        - Grab => short grab does nothing, grab hold => scroll with displacement
        Priority: If pinch_strength > grab_strength and pinch >= pinch_threshold => pinch
                Else if grab_strength >= grab_threshold => grab
                Else idle
        """
        current_time = time.time()
        current_state = self.hand_state["right"]

        # 1) Decide which gesture (pinch or grab) is active, if any
        pinch_active = (pinch_strength >= self.pinch_threshold)  
        grab_active  = (grab_strength >= self.grab_threshold)

        # Priority: pinch if pinch_strength > grab_strength
        if pinch_active and (pinch_strength > grab_strength):
            gesture = "pinch"
        elif grab_active:
            gesture = "grab"
        else:
            gesture = None

        # 2) State machine transitions
        if current_state == "idle":
            if gesture == "pinch":
                self.hand_state["right"] = "pinch-pressing"
                self.hand_press_time["right"] = current_time
                # Immediately press mouse => click down
                self.press_down()
            
            elif gesture == "grab":
                self.hand_state["right"] = "grab-pressing"
                self.hand_press_time["right"] = current_time
                # We'll start “grab” => store palm_y to begin scroll
                self.last_scroll_y = palm_y
                print("Grab start. Ready to scroll after hold_threshold if still grabbing.")

            # else remain idle

        elif current_state == "pinch-pressing":
            if gesture == "pinch":
                # Still pinching => check if we cross hold threshold
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["right"] = "pinch-holding"
                    print("Pinch-hold started (right hand).")
                    # Optionally press again or do nothing
            else:
                # We lost pinch => short pinch => a click
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed < self.hold_threshold:
                    print("Short pinch => click.")
                    self.trigger_click_event()
                    # Or if you prefer press_down + press_up, you already pressed_down above
                    self.press_up()
                # Return to idle
                self.hand_state["right"] = "idle"

        elif current_state == "pinch-holding":
            if gesture == "pinch":
                # Still pinch-holding => do nothing, keep mouse pressed
                pass
            else:
                # Pinch ended => release mouse
                print("Pinch-hold ended.")
                self.press_up()
                self.hand_state["right"] = "idle"

        elif current_state == "grab-pressing":
            if gesture == "grab":
                # Still grabbing => see if we cross hold threshold => start scrolling
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["right"] = "grab-holding"
                    self.last_scroll_y = palm_y
                    print("Grab-hold => begin scrolling mode.")
            else:
                # Lost grab => short grab => do nothing
                print("Short grab => do nothing (no click).")
                self.hand_state["right"] = "idle"

        elif current_state == "grab-holding":
            if gesture == "grab":
                # Keep scrolling based on displacement
                self.scroll_with_displacement(palm_y)
            else:
                # Grab ended => stop scrolling
                print("Grab scroll ended.")
                self.hand_state["right"] = "idle"

        # else: do nothing for any other unexpected states

            
    def scroll_with_displacement(self, current_y):
        """
        Compare current_y with the last_scroll_y, send mouse wheel event 
        for the difference. Positive => scroll up, negative => scroll down
        (or reverse if needed).
        """
        delta = current_y - self.last_scroll_y
        # print(delta)
        
        scroll_amount = int(-1 * delta * self.scroll_sensitivity * 120)

        if scroll_amount != 0:
            MOUSEEVENTF_WHEEL = 0x0800
            # +scroll_amount => typically scroll up, negative => scroll down
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, scroll_amount, 0)

        self.last_scroll_y = current_y
    
    def update_left_grab_state(self, grab_strength):
        """
        Detect a short grab => click, or a long grab => hold, on the LEFT hand.
        """
        current_time = time.time()

        # Check if "grabbing"
        if grab_strength >= self.grab_threshold:
            if self.hand_state["left"] == "idle":
                self.hand_state["left"] = "pressing"
                self.hand_press_time["left"] = current_time
                # Optionally press down the mouse here if you want immediate down:
                self.press_down()

            elif self.hand_state["left"] == "pressing":
                elapsed_time = current_time - self.hand_press_time["left"]
                if elapsed_time >= self.hold_threshold:
                    self.hand_state["left"] = "holding"
                    print("Left hand is now GRAB-holding.")
                    # Keep mouse pressed if desired:
                    self.press_down()

            elif self.hand_state["left"] == "holding":
                # Stay in hold until release
                pass

        else:
            # Grab release
            if self.hand_state["left"] == "pressing":
                elapsed_time = current_time - self.hand_press_time["left"]
                if elapsed_time < self.hold_threshold:
                    print("Left hand performed a short GRAB => treat as click.")
                    self.trigger_click_event()
                    self.press_up()
                self.hand_state["left"] = "idle"

            elif self.hand_state["left"] == "holding":
                print("Left hand ended the GRAB-hold.")
                self.press_up()
                self.hand_state["left"] = "idle"
            # If idle, do nothing


    
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
            print(
                f"Hand x position range: {self.max_min_x[0]}, {self.max_min_x[1]} \n Hand y position range: {self.max_min_y[0]}, {self.max_min_y[1]} \n Hand z position range: {self.max_min_z[0]}, {self.max_min_z[1]}"
            )
        
        if self.cap_width <= 0 or self.cap_height <= 0:
            raise ValueError("Capture dimensions must be greater than zero.")

        # Once we finish updating:
        self.save_config()

        
        
        
    def move_cursor(self, x: float, y: float, scaling_x: float, scaling_y: float):
        """
        Maps the device x,y position to the full screen resolution,
        using min and max from setup_handler.
        """
        # 1. Calculate the ranges
        range_x = self.max_min_x[0] - self.max_min_x[1]  # e.g. 200 - (-200) = 400
        range_y = self.max_min_y[0] - self.max_min_y[1]  # e.g. 100 - (-100) = 200
        
        if range_x == 0:
            range_x = 1
        if range_y == 0:
            range_y = 1

        # 2. Normalize [min..max] to [0..1]
        normalized_x = (x - self.max_min_x[1]) / range_x
        normalized_y = (y - self.max_min_y[1]) / range_y
        
        # 3. Multiply by screen size
        screen_x = normalized_x * self.screen_width  * scaling_x
        screen_y = normalized_y * self.screen_height * scaling_y

        # Optionally invert Y if needed
        # screen_y = (1 - normalized_y) * self.screen_height * scaling_y

        # 4. Clamp
        screen_x = max(0, min(screen_x, self.screen_width - 1))
        screen_y = max(0, min(screen_y, self.screen_height - 1))

        # 5. Move the cursor
        ctypes.windll.user32.SetCursorPos(int(screen_x), int(screen_y))

    
    def trigger_click_event(self):
        ctypes.windll.user32.mouse_event(ActionController.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)  # Simulate left button press
        ctypes.windll.user32.mouse_event(ActionController.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)    # Simulate left button release
        
    def press_down(self):
        """
        Simulates a mouse button press (left button down).
        """
        ctypes.windll.user32.mouse_event(ActionController.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

    def press_up(self):
        """
        Simulates a mouse button release (left button up).
        """
        ctypes.windll.user32.mouse_event(ActionController.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

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

def main():
    action_controller = ActionController()
    # Load the previously saved config (if any)
    action_controller.load_config()
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
