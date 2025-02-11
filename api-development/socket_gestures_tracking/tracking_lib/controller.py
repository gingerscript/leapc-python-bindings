import json
import time
import os
import ctypes
from collections import deque


class HandTrackerBuffer:
    def __init__(self, maxlen=10):
        # We’ll keep up to 10 frames of data
        self.data_buffer = deque(maxlen=maxlen)
    
    def append(self, event):
        """
        event: an object that has event.hands,
            each hand has .type and .palm.position.x, etc.
        """
        left_coords = None
        right_coords = None
        
        for hand in event.hands:
            hand_type = "left" if hand.type.value == 0 else "right"
            x = hand.palm.position.x
            y = hand.palm.position.y
            z = hand.palm.position.z
            
            if hand_type == "left":
                left_coords = (x, y, z)
            else:
                right_coords = (x, y, z)

        entry = {
            "timestamp": time.time(),
            "left":  left_coords,
            "right": right_coords
        }

        # Store in the deque
        self.data_buffer.append(entry)

    def calculate_velocity(self, hand_type='left'):
        """
        Average velocity by summing velocities between consecutive frames
        and dividing by the number of intervals.
        """
        if len(self.data_buffer) < 2:
            return (0.0, 0.0, 0.0)

        total_vx = 0.0
        total_vy = 0.0
        total_vz = 0.0
        valid_pairs = 0

        for i in range(len(self.data_buffer) - 1):
            current = self.data_buffer[i]
            nxt     = self.data_buffer[i + 1]

            # Skip if missing data
            if current[hand_type] is None or nxt[hand_type] is None:
                continue

            (cx, cy, cz) = current[hand_type]
            (nx, ny, nz) = nxt[hand_type]

            dt = nxt["timestamp"] - current["timestamp"]
            if dt <= 0:
                continue

            vx = (nx - cx) / dt
            vy = (ny - cy) / dt
            vz = (nz - cz) / dt

            total_vx += vx
            total_vy += vy
            total_vz += vz
            valid_pairs += 1

        if valid_pairs == 0:
            return (0.0, 0.0, 0.0)

        return (total_vx/valid_pairs, total_vy/valid_pairs, total_vz/valid_pairs)


class ActionController:
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP   = 0x0004
    SWIPE_THRESHOLD = 1000

    def __init__(self, canvas, enable_control=False):
        """
        :param canvas: The Canvas instance used for drawing.
        :param enable_control: If False, disable ALL OS-level actions
                               (mouse movement, click, scroll).
        """
        self.canvas = canvas
        self.enable_control = enable_control

        self.hand_state = {"left": "idle", "right": "idle"}
        self.complex_state = "idle"
        self.hand_press_time = {"left": 0.0, "right": 0.0}
        
        self.hand_buffer = HandTrackerBuffer(maxlen=10)
        self.right_hand_velocity = (0.0, 0.0, 0.0)
        self.left_hand_velocity = (0.0, 0.0, 0.0)
        
        # Pinch/Grab thresholds
        self.pinch_threshold = 0.8
        self.grab_threshold  = 0.9
        self.hold_threshold  = 0.2

        # For “grab to scroll”
        self.scroll_sensitivity = 0.8
        self.last_scroll_y = 0.0

        # Play area
        self.max_min_x = [260, -180]
        self.max_min_y = [50, 0]
        self.max_min_z = [290, -140]

        # Capture device dimensions
        self.cap_width = self.max_min_x[0] - self.max_min_x[1]
        self.cap_height = self.max_min_y[0] - self.max_min_y[1]

        # Screen resolution
        self.screen_width  = 1920
        self.screen_height = 1080

    # --------------------
    # Configuration
    # --------------------
    def save_config(self, filename="play_area_config.json"):
        config = {
            "max_min_x": self.max_min_x,
            "max_min_y": self.max_min_y,
            "max_min_z": self.max_min_z
        }
        with open(filename, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Configuration saved to {filename}")

    def load_config(self, filename="play_area_config.json"):
        if not os.path.exists(filename):
            print(f"No config file found at {filename}. Using defaults.")
            return

        with open(filename, "r") as f:
            config = json.load(f)

        self.max_min_x = config.get("max_min_x", self.max_min_x)
        self.max_min_y = config.get("max_min_y", self.max_min_y)
        self.max_min_z = config.get("max_min_z", self.max_min_z)

        print(f"Configuration loaded from {filename}")

    def reset_setup(self):
        self.max_min_x = [260, -180] 
        self.max_min_y = [50, 0]
        self.max_min_z = [290, -140]

    # --------------------
    # Event Router
    # --------------------
    def tracking_event_router(self, event, state):
        """
        States:
          0 -> Sleep
          1 -> Active
          2 -> Setup
        """
        if state == 0:
            # Sleep state => do nothing
            pass
        elif state == 1:
            self.active_handler(event)
        elif state == 2:
            self.setup_handler(event)
        else:
            raise ValueError(f"Unexpected state: {state}")

    # --------------------
    # Active mode
    # --------------------
    def active_handler(self, event):
        """Process gestures and optionally move mouse, etc."""
        self.hand_buffer.append(event)
        
        self.right_hand_velocity = self.hand_buffer.calculate_velocity('right')
        self.left_hand_velocity = self.hand_buffer.calculate_velocity('left')
        
        for hand in event.hands:
            hand_type = "left" if hand.type.value == 0 else "right"

            if hand_type == "right":
                px, py, pz = hand.palm.position.x, hand.palm.position.y, hand.palm.position.z
                self.move_cursor(px, py, 1, 1)  # Only does something if enable_control = True
                self.update_right_hand_state(hand.grab_strength, hand.pinch_strength, py)

            elif hand_type == "left":
                self.update_left_hand_state(hand.grab_strength, hand.pinch_strength, hand.palm.position.y)

    def update_right_hand_state(self, grab_strength, pinch_strength, palm_y):
        """Simple state machine for the right hand (grab or pinch)."""
        current_time  = time.time()
        current_state = self.hand_state["right"]

        pinch_active = (pinch_strength >= self.pinch_threshold)
        grab_active  = (grab_strength >= self.grab_threshold)

        # Priority: pinch if pinch_strength > grab_strength
        gesture = None
        if pinch_active and (pinch_strength > grab_strength):
            gesture = "pinch"
        elif grab_active:
            gesture = "grab"

        if current_state == "idle":
            if gesture == "pinch":
                self.hand_state["right"] = "pinch-pressing"
                self.hand_press_time["right"] = current_time

            elif gesture == "grab":
                self.hand_state["right"] = "grab-pressing"
                self.hand_press_time["right"] = current_time
                self.last_scroll_y = palm_y
                print("[Right] Grab start. Will scroll if held.")

        elif current_state == "pinch-pressing":
            if gesture == "pinch":
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["right"] = "pinch-holding"
                    print("[Right] Pinch-hold started.")
                    self.press_down()
            else:
                # short pinch => quick click
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed < self.hold_threshold:
                    print("[Right] Short pinch => click.")
                    self.trigger_click_event()
                self.hand_state["right"] = "idle"

        elif current_state == "pinch-holding":
            if gesture == "pinch":
                if self.right_hand_velocity[1] > self.SWIPE_THRESHOLD: 
                    print("[Right] Pinch-hold => swipe-up.")
                    self.complex_state = "swipe-up"
                    # self.scroll_with_displacement(palm_y)
                elif self.right_hand_velocity[1] < -self.SWIPE_THRESHOLD: 
                    print("[Right] Pinch-hold => swipe-down.")
                    self.complex_state = "swipe-down"
                
                else:  
                    self.complex_state = "idle"
                
                # pass  # still pinching => continue hold
            else:
                print("[Right] Pinch-hold ended.")
                self.press_up()
                self.hand_state["right"] = "idle"

        elif current_state == "grab-pressing":
            if gesture == "grab":
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["right"] = "grab-holding"
                    print("[Right] Grab-hold => scrolling mode.")
            else:
                print("[Right] Short grab => do nothing.")
                self.hand_state["right"] = "idle"

        elif current_state == "grab-holding":
            if gesture == "grab":
                self.scroll_with_displacement(palm_y)
            else:
                print("[Right] Grab scroll ended.")
                self.hand_state["right"] = "idle"

    def update_left_hand_state(self, grab_strength, pinch_strength, palm_y):
        """Simple state machine for the left hand (pinch => draw, etc.)."""
        current_time  = time.time()
        current_state = self.hand_state["left"]

        pinch_active = (pinch_strength >= self.pinch_threshold)
        grab_active  = (grab_strength >= self.grab_threshold)

        gesture = None
        if pinch_active and (pinch_strength > grab_strength):
            gesture = "pinch"
        elif grab_active:
            gesture = "grab"

        if current_state == "idle":
            if gesture == "pinch":
                self.hand_state["left"] = "pinch-pressing"
                self.hand_press_time["left"] = current_time
                self.canvas.begin_drawing()

            elif gesture == "grab":
                self.hand_state["left"] = "grab-pressing"
                self.hand_press_time["left"] = current_time
                print("[Left] Grab start => maybe reset canvas?")

        elif current_state == "pinch-pressing":
            if gesture == "pinch":
                elapsed = current_time - self.hand_press_time["left"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["left"] = "pinch-holding"
                    print("[Left] Pinch-hold started => begin drawing.")
                    self.canvas.begin_drawing()
            else:
                # short pinch => short click
                elapsed = current_time - self.hand_press_time["left"]
                if elapsed < self.hold_threshold:
                    print("[Left] Short pinch => click.")
                    self.trigger_click_event()
                self.canvas.stop_drawing()
                self.hand_state["left"] = "idle"

        elif current_state == "pinch-holding":
            if gesture == "pinch":
                pass
            else:
                print("[Left] Pinch-hold ended.")
                self.canvas.stop_drawing()
                self.hand_state["left"] = "idle"

        elif current_state == "grab-pressing":
            if gesture == "grab":
                elapsed = current_time - self.hand_press_time["left"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["left"] = "grab-holding"
                    self.canvas.clear_gesture_screen()
                    print("[Left] Grab-hold => clear canvas.")
            else:
                print("[Left] Short grab => do nothing.")
                self.hand_state["left"] = "idle"

        elif current_state == "grab-holding":
            if gesture == "grab":
                self.scroll_with_displacement(palm_y)
            else:
                print("[Left] Grab ended => stop scrolling, clear canvas.")
                self.canvas.clear_gesture_screen()
                self.hand_state["left"] = "idle"

    # --------------------
    # Setup mode
    # --------------------
    def setup_handler(self, event):
        """
        For each hand, expand max/min boundaries. Then save config.
        """
        for hand in event.hands:
            hp = hand.palm.position
            self.max_min_x[0] = max(self.max_min_x[0], hp.x)
            self.max_min_x[1] = min(self.max_min_x[1], hp.x)

            self.max_min_y[0] = max(self.max_min_y[0], hp.y)
            self.max_min_y[1] = min(self.max_min_y[1], hp.y)

            self.max_min_z[0] = max(self.max_min_z[0], hp.z)
            self.max_min_z[1] = min(self.max_min_z[1], hp.z)

        print("Current ranges: X =>", self.max_min_x, 
              " Y =>", self.max_min_y, 
              " Z =>", self.max_min_z)

        self.save_config()

    # --------------------
    # Utility: Move cursor
    # --------------------
    def move_cursor(self, x, y, scale_x, scale_y):
        """
        Skip mouse movement if enable_control == False.
        """
        if not self.enable_control:
            return
        
        if self.cap_width <= 0: 
            self.cap_width = 1
        if self.cap_height <= 0:
            self.cap_height = 1

        range_x = self.max_min_x[0] - self.max_min_x[1] or 1
        range_y = self.max_min_y[0] - self.max_min_y[1] or 1

        # Simple offset to shift the y range
        y_axis_offset = 0.1

        # Normalize to [0..1]
        norm_x = (x - self.max_min_x[1]) / range_x
        norm_y = ((y - self.max_min_y[1]) / range_y) - y_axis_offset

        screen_x = norm_x * self.screen_width  * scale_x
        screen_y = (1 - norm_y) * self.screen_height * scale_y

        # Clamp
        screen_x = max(0, min(screen_x, self.screen_width-1))
        screen_y = max(0, min(screen_y, self.screen_height-1))

        # Move OS cursor
        ctypes.windll.user32.SetCursorPos(int(screen_x), int(screen_y))

    # --------------------
    # Utility: Scrolling
    # --------------------
    def scroll_with_displacement(self, current_y):
        """
        Only scroll if OS control is enabled.
        """
        if not self.enable_control:
            return

        delta = current_y - self.last_scroll_y
        scroll_amount = int(-1 * delta * self.scroll_sensitivity * 120)
        if scroll_amount:
            MOUSEEVENTF_WHEEL = 0x0800
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, scroll_amount, 0)
        self.last_scroll_y = current_y

    # --------------------
    # Utility: Mouse Click
    # --------------------
    def trigger_click_event(self):
        """
        If we are not controlling the OS, skip the actual click.
        """
        if not self.enable_control:
            return
        ctypes.windll.user32.mouse_event(self.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(self.MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)

    def press_down(self):
        if not self.enable_control:
            return
        ctypes.windll.user32.mouse_event(self.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

    def press_up(self):
        if not self.enable_control:
            return
        ctypes.windll.user32.mouse_event(self.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
