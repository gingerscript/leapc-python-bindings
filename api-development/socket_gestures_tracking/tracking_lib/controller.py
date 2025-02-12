import json
import time
import os
import ctypes
from collections import deque
import numpy as np


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

        return (total_vx / valid_pairs,
                total_vy / valid_pairs,
                total_vz / valid_pairs)


class ActionController:
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP   = 0x0004
    SWIPE_THRESHOLD = 800

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

        # Track last time we updated a complex gesture (e.g., swipe)
        self.complex_gesture_timestamp = 0.0
        
        self.hand_buffer = HandTrackerBuffer(maxlen=10)
        self.right_hand_velocity = (0.0, 0.0, 0.0)
        self.left_hand_velocity  = (0.0, 0.0, 0.0)
        
        # Pinch/Grab thresholds
        self.pinch_threshold = 0.8
        self.grab_threshold  = 0.9
        self.hold_threshold  = 0.1

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

    # -------------------------------------------------------------------------
    #  get_state() -> JSON with positional, gesture, and timestamp info
    # -------------------------------------------------------------------------
    def get_state(self):
        """
        Return the structured JSON:
        {
          "left_hand": {
            "position": {"x":..., "y":..., "z":...},
            "gesture": "...",
            "timestamp": ...
          },
          "right_hand": {
            "position": {"x":..., "y":..., "z":...},
            "gesture": "...",
            "timestamp": ...
          },
          "complex_gesture": {
            "gesture": "...",
            "gesture_timestamp": ...
          }
        }
        """
        left_coords = None
        right_coords = None
        left_timestamp = None
        right_timestamp = None

        # If we have any frames in the buffer, use the most recent frame
        if self.hand_buffer.data_buffer:
            latest = self.hand_buffer.data_buffer[-1]
            left_coords = latest["left"]   # (x, y, z) or None
            right_coords = latest["right"] # (x, y, z) or None
            frame_timestamp = latest["timestamp"]

            # If there's valid left coords, set left_timestamp
            if left_coords is not None:
                left_timestamp = frame_timestamp
            # If there's valid right coords, set right_timestamp
            if right_coords is not None:
                right_timestamp = frame_timestamp

        state_dict = {
            "left_hand": {
                "position": {
                    "x": left_coords[0],
                    "y": left_coords[1],
                    "z": left_coords[2]
                } if left_coords else None,
                "gesture": self.hand_state["left"],
                "timestamp": left_timestamp
            },
            "right_hand": {
                "position": {
                    "x": right_coords[0],
                    "y": right_coords[1],
                    "z": right_coords[2]
                } if right_coords else None,
                "gesture": self.hand_state["right"],
                "timestamp": right_timestamp
            },
            "complex_gesture": {
                "gesture": self.complex_state,
                "gesture_timestamp": self.complex_gesture_timestamp
            }
        }
        return json.dumps(state_dict, indent=2)

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
        self.left_hand_velocity  = self.hand_buffer.calculate_velocity('left')

        present_hands = set()  # track which hands are actually present

        for hand in event.hands:
            hand_type = "left" if hand.type.value == 0 else "right"
            present_hands.add(hand_type)
            
            # For determining hand orientation
            device_forward = np.array([0, 0, 1])  # Leap Motion is typically +Z
            palm_normal = np.array([hand.palm.normal.x, hand.palm.normal.y, hand.palm.normal.z])
            dot_product = np.dot(palm_normal, device_forward) # if negative palm is facing device, positive is facing away
            

            if hand_type == "right":
                px, py = hand.palm.position.x, hand.palm.position.y
                self.move_cursor(px, py, 1, 1)  # Only moves mouse if enable_control = True
                self.update_right_hand_state(hand.grab_strength, hand.pinch_strength, hand.palm.position.y, dot_product)

            elif hand_type == "left":
                self.update_left_hand_state(hand.grab_strength, hand.pinch_strength, hand.palm.position.y, dot_product)

        recognized_gesture = self.canvas.get_and_forget_drawn_gesture()
        if recognized_gesture:
            print(f"[ActionController] Detected new drawn gesture: {recognized_gesture}")
            self.complex_state = recognized_gesture
            self.complex_gesture_timestamp = time.time()

        # ---- AFTER processing all hands ----
        # If the right hand is missing but we are stuck on a swipe, reset to idle
        if "right" not in present_hands and self.complex_state != "idle":
            # print("[Controller] Right hand lost => resetting complex gesture to idle.")
            self.complex_state = "idle"
            self.complex_gesture_timestamp = time.time()   
             
    def _check_for_pinch_swipe(self):
        """
        Checks the right hand velocity (vx, vy, vz) during pinch-holding
        and sets self.complex_state accordingly if a swipe is detected.
        """
        vx, vy, vz = self.right_hand_velocity

        # Check vertical velocity first (up/down)
        if vy > self.SWIPE_THRESHOLD:
            self.complex_state = "swipe-up"
            self.complex_gesture_timestamp = time.time()
        elif vy < -self.SWIPE_THRESHOLD:
            self.complex_state = "swipe-down"
            self.complex_gesture_timestamp = time.time()

        # Check horizontal velocity (left/right)
        elif vx > self.SWIPE_THRESHOLD:
            self.complex_state = "swipe-right"
            self.complex_gesture_timestamp = time.time()
        elif vx < -self.SWIPE_THRESHOLD:
            self.complex_state = "swipe-left"
            self.complex_gesture_timestamp = time.time()

        else:
            # If we already have a swipe state and it goes below threshold,
            # you might reset to idle or do nothing
            if self.complex_state in ["swipe-up", "swipe-down", "swipe-left", "swipe-right"]:
                self.complex_state = "idle"
                self.complex_gesture_timestamp = time.time()


    def update_right_hand_state(self, grab_strength, pinch_strength, palm_y, dot_product):
        """
        An extended state machine for the right hand, distinguishing:
        - open-palm-away
        - open-palm-towards
        - pinch-pressing / pinch-holding (with swipe detection)
        - grab-away-pressing / grab-away-holding
        - grab-towards-pressing / grab-towards-holding
        """
        current_time = time.time()
        current_state = self.hand_state["right"]

        # Check if pinch/grab are active
        pinch_active = (pinch_strength >= self.pinch_threshold)
        grab_active  = (grab_strength >= self.grab_threshold)

        # Determine basic palm orientation from dot_product:
        #   dot < 0 => palm_away, dot >= 0 => palm_towards
        palm_orientation = "palm_away" if (dot_product < 0) else "palm_towards"

        # Decide gesture type (pinch or grab + orientation)
        gesture = None
        if pinch_active and (pinch_strength > grab_strength):
            gesture = "pinch"
        elif grab_active:
            if palm_orientation == "palm_away":
                gesture = "grab_palm_away"
            else:
                gesture = "grab_palm_towards"

        # -------------------------------------------------------------
        #   OPEN-PALM States => default fallback if no pinch/grab
        # -------------------------------------------------------------
        # We'll treat any "idle" or unknown state as one of the open-palm states.
        if current_state in ("idle", "open-palm-away", "open-palm-towards"):
            if gesture == "pinch":
                self.hand_state["right"] = "pinch-pressing"
                self.hand_press_time["right"] = current_time

            elif gesture == "grab_palm_away":
                self.hand_state["right"] = "grab-away-pressing"
                self.hand_press_time["right"] = current_time
                self.last_scroll_y = palm_y

            elif gesture == "grab_palm_towards":
                self.hand_state["right"] = "grab-towards-pressing"
                self.hand_press_time["right"] = current_time
                self.last_scroll_y = palm_y

            else:
                # No pinch/grab => remain in open-palm-away or open-palm-towards
                if palm_orientation == "palm_away":
                    self.hand_state["right"] = "open-palm-away"
                else:
                    self.hand_state["right"] = "open-palm-towards"

        # -------------------------------------------------------------
        #        PINCH-PRESSING
        # -------------------------------------------------------------
        elif current_state == "pinch-pressing":
            if gesture == "pinch":
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["right"] = "pinch-holding"
                    # e.g., press mouse down or do something else
                    self.press_down()
            else:
                # short pinch => quick click
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed < self.hold_threshold:
                    self.trigger_click_event()
                # revert to open-palm states
                if palm_orientation == "palm_away":
                    self.hand_state["right"] = "open-palm-away"
                else:
                    self.hand_state["right"] = "open-palm-towards"

        # -------------------------------------------------------------
        #        PINCH-HOLDING (Swipes happen here)
        # -------------------------------------------------------------
        elif current_state == "pinch-holding":
            if gesture == "pinch":
                # Check for swipe logic
                self._check_for_pinch_swipe()

            else:
                # End pinch
                self.press_up()
                if palm_orientation == "palm_away":
                    self.hand_state["right"] = "open-palm-away"
                else:
                    self.hand_state["right"] = "open-palm-towards"

        # -------------------------------------------------------------
        #        GRAB-AWAY: pressing -> holding
        # -------------------------------------------------------------
        elif current_state == "grab-away-pressing":
            if gesture == "grab_palm_away":
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["right"] = "grab-away-holding"
                    # e.g., start scrolling mode
            else:
                # Lost gesture => revert to open palm
                if palm_orientation == "palm_away":
                    self.hand_state["right"] = "open-palm-away"
                else:
                    self.hand_state["right"] = "open-palm-towards"

        elif current_state == "grab-away-holding":
            if gesture == "grab_palm_away":
                self.scroll_with_displacement(palm_y)
            else:
                # End or orientation changed => open palm
                if palm_orientation == "palm_away":
                    self.hand_state["right"] = "open-palm-away"
                else:
                    self.hand_state["right"] = "open-palm-towards"

        # -------------------------------------------------------------
        #        GRAB-TOWARDS: pressing -> holding
        # -------------------------------------------------------------
        elif current_state == "grab-towards-pressing":
            if gesture == "grab_palm_towards":
                elapsed = current_time - self.hand_press_time["right"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["right"] = "grab-towards-holding"
                    # e.g., do something special
            else:
                if palm_orientation == "palm_away":
                    self.hand_state["right"] = "open-palm-away"
                else:
                    self.hand_state["right"] = "open-palm-towards"

        elif current_state == "grab-towards-holding":
            if gesture == "grab_palm_towards":
                self.scroll_with_displacement(palm_y)
            else:
                if palm_orientation == "palm_away":
                    self.hand_state["right"] = "open-palm-away"
                else:
                    self.hand_state["right"] = "open-palm-towards"

        # -------------------------------------------------------------
        #   Unhandled fallback
        # -------------------------------------------------------------
        else:
            # Some leftover pinch or unknown states => revert to open palm
            if palm_orientation == "palm_away":
                self.hand_state["right"] = "open-palm-away"
            else:
                self.hand_state["right"] = "open-palm-towards"




    def update_left_hand_state(self, grab_strength, pinch_strength, palm_y, dot_product):
        """
        Extended state machine for the left hand, including orientation-based
        open palm states (open-palm-away / open-palm-towards).

        States handled:
        - "open-palm-away" / "open-palm-towards" (default if not pinch/grab)
        - "pinch-pressing" / "pinch-holding"
        - "grab-away-pressing" / "grab-away-holding"
        - "grab-towards-pressing" / "grab-towards-holding"
        """
        current_time  = time.time()
        current_state = self.hand_state["left"]

        pinch_active = (pinch_strength >= self.pinch_threshold)
        grab_active  = (grab_strength >= self.grab_threshold)

        # Determine palm orientation: dot < 0 => palm_away, dot >= 0 => palm_towards
        palm_orientation = "palm_away" if (dot_product < 0) else "palm_towards"

        # Decide basic gesture
        gesture = None
        if pinch_active and (pinch_strength > grab_strength):
            gesture = "pinch"
        elif grab_active:
            if palm_orientation == "palm_away":
                gesture = "grab_palm_away"
            else:
                gesture = "grab_palm_towards"

        # -------------------------------------------------------------
        #   OPEN-PALM states => default if no pinch/grab
        #   (Replacing the old "idle" logic)
        # -------------------------------------------------------------
        if current_state in ("idle", "open-palm-away", "open-palm-towards"):
            if gesture == "pinch":
                self.hand_state["left"] = "pinch-pressing"
                self.hand_press_time["left"] = current_time
                # e.g., begin drawing
                self.canvas.begin_drawing()

            elif gesture == "grab_palm_away":
                self.hand_state["left"] = "grab-away-pressing"
                self.hand_press_time["left"] = current_time
                # e.g., possibly track last_scroll_y or do something else

            elif gesture == "grab_palm_towards":
                self.hand_state["left"] = "grab-towards-pressing"
                self.hand_press_time["left"] = current_time
                # e.g., possibly track last_scroll_y or do something else

            else:
                # No pinch/grab => remain in open-palm-away or open-palm-towards
                if palm_orientation == "palm_away":
                    self.hand_state["left"] = "open-palm-away"
                else:
                    self.hand_state["left"] = "open-palm-towards"

        # -------------------------------------------------------------
        #        PINCH-PRESSING
        # -------------------------------------------------------------
        elif current_state == "pinch-pressing":
            if gesture == "pinch":
                elapsed = current_time - self.hand_press_time["left"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["left"] = "pinch-holding"
                    # e.g., keep drawing
            else:
                # short pinch => short click
                elapsed = current_time - self.hand_press_time["left"]
                if elapsed < self.hold_threshold:
                    self.trigger_click_event()
                # end pinch => stop drawing
                self.canvas.stop_drawing()

                # revert to open palm
                if palm_orientation == "palm_away":
                    self.hand_state["left"] = "open-palm-away"
                else:
                    self.hand_state["left"] = "open-palm-towards"

        # -------------------------------------------------------------
        #        PINCH-HOLDING
        # -------------------------------------------------------------
        elif current_state == "pinch-holding":
            if gesture == "pinch":
                # e.g., keep drawing
                pass
            else:
                # end pinch
                self.canvas.stop_drawing()
                if palm_orientation == "palm_away":
                    self.hand_state["left"] = "open-palm-away"
                else:
                    self.hand_state["left"] = "open-palm-towards"

        # -------------------------------------------------------------
        #        GRAB-AWAY: pressing -> holding
        # -------------------------------------------------------------
        elif current_state == "grab-away-pressing":
            if gesture == "grab_palm_away":
                elapsed = current_time - self.hand_press_time["left"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["left"] = "grab-away-holding"
                    # e.g., clear gesture screen or prepare to scroll
                    self.canvas.clear_gesture_screen()
            else:
                # short grab => do nothing
                # revert to open palm
                if palm_orientation == "palm_away":
                    self.hand_state["left"] = "open-palm-away"
                else:
                    self.hand_state["left"] = "open-palm-towards"

        elif current_state == "grab-away-holding":
            if gesture == "grab_palm_away":
                # e.g., scroll or maintain grab
                self.scroll_with_displacement(palm_y)
            else:
                # end grab => revert to open palm
                if palm_orientation == "palm_away":
                    self.hand_state["left"] = "open-palm-away"
                else:
                    self.hand_state["left"] = "open-palm-towards"

        # -------------------------------------------------------------
        #        GRAB-TOWARDS: pressing -> holding
        # -------------------------------------------------------------
        elif current_state == "grab-towards-pressing":
            if gesture == "grab_palm_towards":
                elapsed = current_time - self.hand_press_time["left"]
                if elapsed >= self.hold_threshold:
                    self.hand_state["left"] = "grab-towards-holding"
                    # e.g., do something special (or also clear gesture screen)
                    self.canvas.clear_gesture_screen()
            else:
                if palm_orientation == "palm_away":
                    self.hand_state["left"] = "open-palm-away"
                else:
                    self.hand_state["left"] = "open-palm-towards"

        elif current_state == "grab-towards-holding":
            if gesture == "grab_palm_towards":
                # e.g., keep scrolling or do something else
                self.scroll_with_displacement(palm_y)
            else:
                # end grab => revert to open palm
                if palm_orientation == "palm_away":
                    self.hand_state["left"] = "open-palm-away"
                else:
                    self.hand_state["left"] = "open-palm-towards"

        # -------------------------------------------------------------
        #  Fallback to open palm
        # -------------------------------------------------------------
        else:
            if palm_orientation == "palm_away":
                self.hand_state["left"] = "open-palm-away"
            else:
                self.hand_state["left"] = "open-palm-towards"


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
