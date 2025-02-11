import time
import json
import cv2
import socketio
import leap
import argparse
import sys

from tracking_lib.canvas import Canvas, _TRACKING_MODES
from tracking_lib.controller import ActionController

BUFFER_FILE = "position.json"


class MyListener(leap.Listener):
    """
    This listener routes all Leap events to the ActionController
    and also emits data via Socket.IO.
    """
    def __init__(self, action_controller, server_url="http://localhost:5000"):
        super().__init__()
        self.action_controller = action_controller
        self.state = 0  # 0 => Sleep, 1 => Active, 2 => Setup

        # Socket.IO client
        self.sio = socketio.Client()
        try:
            self.sio.connect(server_url)
            print(f"[SocketIO] Connected to {server_url}")
        except Exception as e:
            print(f"[SocketIO] Connection failed: {e}")

    def set_state(self, new_state):
        self.state = new_state

    def on_connection_event(self, event):
        print("Leap connection established.")
        self.state = 1  # Immediately set to 'Active' if device found

    def on_device_event(self, event):
        try:
            with event.device.open():
                info = event.device.get_info()
                self.state = 1
        except leap.LeapCannotOpenDeviceError:
            info = event.device.get_info()
        print(f"Found device {info.serial}")

    def on_tracking_mode_event(self, event):
        self.action_controller.canvas.set_tracking_mode(event.current_tracking_mode)
        print(f"Tracking mode changed to {_TRACKING_MODES[event.current_tracking_mode]}")

    def on_tracking_event(self, event):
        """
        1) Pass event to controller for gesture/mouse logic
        2) Render hands in the canvas
        3) Build JSON data from the controller
        4) Emit via Socket.IO
        """
        # Step 1: Route event
        self.action_controller.tracking_event_router(event, self.state)

        # Step 2: Render only affects the canvas' output_image
        self.action_controller.canvas.render_hands(event)

        # Step 3: Build JSON data using our ActionController's get_state()
        data_to_send = self._build_data_json(event)

        # Step 4: Optionally save & emit
        self._dump_data_local(data_to_send)
        self._emit_data(data_to_send)

    def _emit_data(self, data):
        """Emit data to Socket.IO if connected."""
        if self.sio.connected:
            try:
                self.sio.emit("hand_data", data)
            except Exception as e:
                print(f"[SocketIO] Emit failed: {e}")

    def _dump_data_local(self, data):
        """Optionally save the data to a JSON file so other processes can read it."""
        try:
            with open(BUFFER_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Error writing {BUFFER_FILE}: {e}")

    def _build_data_json(self, event):
        """
        Uses ActionController.get_state() which returns the JSON string:
          {
            "left_hand": {
              "position": {"x":..., "y":..., "z":...},
              "gesture": "...",
              "timestamp": ...
            },
            "right_hand": {...},
            "complex_gesture": {
              "gesture": "...",
              "gesture_timestamp": ...
            }
          }
        We'll load it into a dict before returning, so we can emit or save as needed.
        """
        json_str = self.action_controller.get_state()  # returns a JSON string
        return json.loads(json_str)  # Convert to Python dict for Socket.IO / file


def main():
    parser = argparse.ArgumentParser(
        description="Leap Motion Tracking with optional Canvas display."
    )
    parser.add_argument("--canvas", action="store_true",
                        help="Show the OpenCV canvas window.")
    parser.add_argument("--control", action="store_true",
                        help="Enable click and drag OS controls.")
    args = parser.parse_args()

    # 1) Setup Canvas & Controller
    canvas = Canvas()
    action_controller = ActionController(canvas, enable_control=args.control)
    action_controller.load_config()  # Load existing play_area_config.json if present

    # 2) Create listener w/ Socket.IO client
    my_listener = MyListener(action_controller, server_url="http://localhost:5000")

    # 3) Setup Leap connection
    connection = leap.Connection()
    connection.add_listener(my_listener)

    running = True
    with connection.open():
        connection.set_tracking_mode(leap.TrackingMode.Desktop)

        # If user requested a Canvas, we show the OpenCV window & read keys from the window
        if args.canvas:
            while running:
                cv2.imshow(canvas.name, canvas.output_image)
                key = cv2.waitKey(1) & 0xFF

                if key == ord('x'):
                    print("Exiting...")
                    running = False

                elif key == ord('a'):
                    print("Switching to Active Mode...")
                    my_listener.set_state(1)

                elif key == ord('s'):
                    print("Switching to Sleep Mode...")
                    my_listener.set_state(0)

                elif key == ord('c'):
                    print("Switching to Setup Mode...")
                    my_listener.set_state(2)
                
                elif key == ord('f'):
                    print("Toggling hand format between Skeleton/Dots...")
                    canvas.toggle_hands_format()

        else:
            # If we're NOT showing the Canvas, we rely on console input for commands.
            print("No --canvas provided. Use console commands:")
            print("  x => Exit")
            print("  a => Active Mode")
            print("  s => Sleep Mode")
            print("  c => Setup Mode")
            print("  f => Toggle Hand Format")

            while running:
                user_input = input("Enter command: ").strip().lower()

                if user_input == 'x':
                    print("Exiting...")
                    running = False

                elif user_input == 'a':
                    print("Switching to Active Mode...")
                    my_listener.set_state(1)

                elif user_input == 's':
                    print("Switching to Sleep Mode...")
                    my_listener.set_state(0)

                elif user_input == 'c':
                    print("Switching to Setup Mode...")
                    my_listener.set_state(2)

                elif user_input == 'f':
                    print("Toggling hand format between Skeleton/Dots...")
                    canvas.toggle_hands_format()

                else:
                    print("Unknown command. Valid: x, a, s, c, f")

    # After exiting loop:
    if args.canvas:
        cv2.destroyAllWindows()

    # Disconnect Socket.IO
    if my_listener.sio.connected:
        my_listener.sio.disconnect()


if __name__ == "__main__":
    main()
