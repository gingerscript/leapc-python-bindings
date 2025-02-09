import cv2
import numpy as np
from collections import deque
import leap

# Tracking mode labels, used for display text
_TRACKING_MODES = {
    leap.TrackingMode.Desktop: "Desktop",
    leap.TrackingMode.HMD: "HMD",
    leap.TrackingMode.ScreenTop: "ScreenTop",
}

class Canvas:
    def __init__(self):
        self.name = "Python Gemini Visualiser"
        self.screen_size = [500, 700]
        self.drawn_points = deque(maxlen=100)
        self.is_drawing = False

        self.hands_colour = (255, 255, 255)
        self.font_colour = (0, 255, 44)
        self.hands_format = "Skeleton"

        self.output_image = np.zeros((self.screen_size[0], self.screen_size[1], 3), np.uint8)
        self.tracking_mode = None

        # Simple drawing rate-limiter
        self.counter = 0

    def set_tracking_mode(self, tracking_mode):
        """Store the current tracking mode so we can display it on screen."""
        self.tracking_mode = tracking_mode

    def toggle_hands_format(self):
        """Switch between 'Skeleton' and 'Dots' drawing modes."""
        self.hands_format = "Dots" if self.hands_format == "Skeleton" else "Skeleton"
        print(f"Set hands format to {self.hands_format}")

    def begin_drawing(self):
        self.is_drawing = True

    def stop_drawing(self):
        self.is_drawing = False

    def clear_gesture_screen(self):
        self.drawn_points.clear()

    def get_joint_position(self, leap_vector):
        """Convert Leap Motion 3D coordinates to Canvas 2D coordinates."""
        if leap_vector is None:
            return None
        x = int(leap_vector.x + (self.screen_size[1] / 2))
        y = int(leap_vector.z + (self.screen_size[0] / 2))
        return (x, y)

    def render_hands(self, event):
        """
        Update self.output_image with hand skeleton/dot drawings for the current frame.
        """
        self.output_image[:] = 0  # clear

        mode_text = f"Tracking Mode: {_TRACKING_MODES.get(self.tracking_mode, 'Unknown')}"
        cv2.putText(
            self.output_image,
            mode_text,
            (10, self.screen_size[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            self.font_colour,
            1,
        )

        if not event.hands:
            return  # No hands, no drawing

        for hand in event.hands:
            # For "Skeleton" mode, show the arm as well
            if self.hands_format == "Skeleton":
                wrist = self.get_joint_position(hand.arm.next_joint)
                elbow = self.get_joint_position(hand.arm.prev_joint)
                if wrist:
                    cv2.circle(self.output_image, wrist, 3, self.hands_colour, -1)
                if elbow:
                    cv2.circle(self.output_image, elbow, 3, self.hands_colour, -1)
                if wrist and elbow:
                    cv2.line(self.output_image, wrist, elbow, self.hands_colour, 2)

            # Now draw each digit
            for digit_idx in range(5):
                digit = hand.digits[digit_idx]
                for bone_idx in range(4):
                    bone = digit.bones[bone_idx]
                    self._draw_bone(bone, hand)

    def _draw_bone(self, bone, hand):
        """
        Draw either 'Dots' or 'Skeleton' representation of each bone.
        """
        bone_start = self.get_joint_position(bone.prev_joint)
        bone_end = self.get_joint_position(bone.next_joint)

        if self.hands_format == "Dots":
            if bone_start:
                cv2.circle(self.output_image, bone_start, 2, self.hands_colour, -1)
            if bone_end:
                cv2.circle(self.output_image, bone_end, 2, self.hands_colour, -1)
        else:
            # Skeleton
            if bone_start:
                cv2.circle(self.output_image, bone_start, 3, self.hands_colour, -1)
            if bone_end:
                cv2.circle(self.output_image, bone_end, 3, self.hands_colour, -1)
            if bone_start and bone_end:
                cv2.line(self.output_image, bone_start, bone_end, self.hands_colour, 2)

            # Example: If the fingertip of the index finger => let's do "air-drawing"
            # Index finger is digit_idx=1, last bone is bone_idx=3
            # We'll cheat here and just detect it in the final bone of the index finger.
            # You might add more robust logic in ActionController or so.
            if bone_start and bone_end:
                # If this is the index fingertip:
                if (hand.type.value == 0):  # left or right hand - user can expand
                    pass
                # etc.

        # If "drawing" is enabled, maybe store the fingertip position
        # (Hand-coded example from your original logic)
        if self.is_drawing:
            # Could store bone_end to self.drawn_points if you want to draw lines
            self.counter += 1
            if self.counter % 2 == 0 and bone_end:
                self.drawn_points.append(bone_end)
                self.counter = 0

        # Draw recorded points if any:
        for p in self.drawn_points:
            cv2.circle(self.output_image, p, 3, self.hands_colour, -1)
