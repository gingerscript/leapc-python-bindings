import json
import os

CONFIG_FILE = "assets/play_area_config.json"

def save_config(action_controller):
    config = {
        "max_min_x": action_controller.max_min_x,
        "max_min_y": action_controller.max_min_y,
        "max_min_z": action_controller.max_min_z
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Configuration saved to {CONFIG_FILE}")

def load_config(action_controller):
    if not os.path.exists(CONFIG_FILE):
        print("No config file found. Using defaults.")
        return

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    action_controller.max_min_x = config.get("max_min_x", action_controller.max_min_x)
    action_controller.max_min_y = config.get("max_min_y", action_controller.max_min_y)
    action_controller.max_min_z = config.get("max_min_z", action_controller.max_min_z)
    print(f"Configuration loaded from {CONFIG_FILE}")
