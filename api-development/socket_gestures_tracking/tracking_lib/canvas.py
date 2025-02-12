import cv2
import numpy as np
from collections import deque
import time
import leap
import os
from scipy.spatial.distance import directed_hausdorff  # <-- IMPORTANT

REFERENCE_PATHS = {
    "box": "drawn_gestures/box.npy",
    "circle": "drawn_gestures/circle.npy",
    "vertical_line": "drawn_gestures/vertical_line.npy",
    "horizontal_line": "drawn_gestures/horizontal_line.npy",
    "bar_chart": "drawn_gestures/bar_chart.npy",
    "horizontal_bar_chart": "drawn_gestures/horizontal_bar_chart.npy",
    # "spiral": "drawn_gestures/spiral.npy"  # Spiral needs to be rethought, conflicts with other gestures
}

_TRACKING_MODES = {
    leap.TrackingMode.Desktop: "Desktop",
    leap.TrackingMode.HMD: "HMD",
    leap.TrackingMode.ScreenTop: "ScreenTop",
}

class Canvas:
    MATCH_THRESHOLD = 30.0
    
    def __init__(self):
        self.name = "Python Gemini Visualiser"
        
        # Note: screen_size = [height, width]
        self.screen_size = [500, 700]
        
        self.drawn_points = deque(maxlen=200)  # Now store 3D points: (x, y, z)
        self.is_drawing = False
        self.hands_colour = (255, 255, 255)
        self.font_colour = (0, 255, 44)
        self.hands_format = "Skeleton"
        self.output_image = np.zeros((self.screen_size[0], self.screen_size[1], 3), np.uint8)
        self.tracking_mode = None
        self.counter = 0  # Simple drawing rate-limiter

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
        """
        Stop drawing. If we have more than 10 points, convert them
        into a 2D grid and compare to reference gestures.
        """
        self.is_drawing = False
        
        # If enough points have been drawn, process the gesture
        if len(self.drawn_points) > 10:
            grid = self.create_grid_from_points(
                points=self.drawn_points,
                grid_size=(100, 100)
            )
            
            # Optionally save points as image and numpy array
            self.save_gesture_grid(grid, save_as_image=False, save_as_npy=False) #SET TO TRUE TO SAVE

            cv2.imshow("Gesture Grid", grid * 255)
            cv2.waitKey(20)

            # Compare with references (using Hausdorff)
            ranking = self.rank_reference_gestures(grid)
            
            if ranking[0][1] < self.MATCH_THRESHOLD:
                print("Similarity Ranking (lower Hausdorff => better match):")
                for gesture_name, score in ranking:
                    print(f"  {gesture_name} => {score:.2f}")

                best_match, best_score = ranking[0]
                print(f"Best match: {best_match} (Hausdorff={best_score:.2f})")
            else:
                print("No valid reference files found.")
        
        
        
        self.clear_gesture_screen()

    def clear_gesture_screen(self):
        self.drawn_points.clear()

    def get_joint_position(self, leap_vector, enable_z=True):
        """Convert Leap Motion 3D coordinates to Canvas coordinates."""
        if leap_vector is None:
            return None
        
        x_canvas = int(leap_vector.x + (self.screen_size[1] / 2))
        y_canvas = int(-leap_vector.y + (self.screen_size[0]))
        z_canvas = int(leap_vector.z)

        if enable_z:
            return (x_canvas, y_canvas, z_canvas)
        else:
            return (x_canvas, y_canvas)

    def render_hands(self, event):
        self.output_image[:] = 0  # Clear the canvas

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
            return

        for hand in event.hands:
            # Draw the arm (Skeleton mode)
            if self.hands_format == "Skeleton":
                wrist = self.get_joint_position(hand.arm.next_joint)
                elbow = self.get_joint_position(hand.arm.prev_joint)
                if wrist:
                    cv2.circle(self.output_image, wrist[:2], 3, self.hands_colour, -1)
                if elbow:
                    cv2.circle(self.output_image, elbow[:2], 3, self.hands_colour, -1)
                if wrist and elbow:
                    cv2.line(self.output_image, wrist[:2], elbow[:2], self.hands_colour, 2)

            # Draw each digit
            for digit_idx in range(5):
                digit = hand.digits[digit_idx]
                for bone_idx in range(4):
                    bone = digit.bones[bone_idx]
                    self._draw_bone(bone, hand, digit_idx, bone_idx)

        # Finally, draw all collected points in self.drawn_points
        for p in self.drawn_points:
            cv2.circle(self.output_image, (p[0], p[1]), 3, self.hands_colour, -1)

    def _draw_bone(self, bone, hand, digit_idx, bone_idx):
        bone_start = self.get_joint_position(bone.prev_joint, enable_z=True)
        bone_end   = self.get_joint_position(bone.next_joint, enable_z=True)

        if self.hands_format == "Dots":
            if bone_start:
                cv2.circle(self.output_image, bone_start[:2], 2, self.hands_colour, -1)
            if bone_end:
                cv2.circle(self.output_image, bone_end[:2], 2, self.hands_colour, -1)
        else:
            if bone_start:
                cv2.circle(self.output_image, bone_start[:2], 3, self.hands_colour, -1)
            if bone_end:
                cv2.circle(self.output_image, bone_end[:2], 3, self.hands_colour, -1)
            if bone_start and bone_end:
                cv2.line(self.output_image, bone_start[:2], bone_end[:2], self.hands_colour, 2)

        # Example: if the fingertip of the index finger => "air-drawing"
        if (digit_idx == 1) and (bone_idx == 3):
            if self.is_drawing and hand.type.value == 1 and bone_end:
                self.counter += 1
                if self.counter % 2 == 0:
                    self.drawn_points.append(bone_end)
                    self.counter = 0

    def create_grid_from_points(self, points, grid_size=(100, 100)):
        """Same as your existing bounding-box + scaling code."""
        h, w = grid_size
        grid = np.zeros((h, w), dtype=np.uint8)
        
        arr = np.array(points)  # shape: (N, 3) or (N, 2)
        if len(arr) == 0:
            return grid
        
        # Crop
        x_min, y_min = arr[:, 0].min(), arr[:, 1].min()
        x_max, y_max = arr[:, 0].max(), arr[:, 1].max()
        
        width  = x_max - x_min
        height = y_max - y_min
        if width == 0: width = 1
        if height == 0: height = 1

        # Scale
        scale_x = (w - 1) / width
        scale_y = (h - 1) / height
        final_scale = min(scale_x, scale_y)
        scale_x = final_scale
        scale_y = final_scale

        # Transform
        transformed_points = []
        for (px, py, *rest) in arr:
            new_x = (px - x_min) * scale_x
            new_y = (py - y_min) * scale_y
            transformed_points.append((new_x, new_y))

        # Rasterize
        for p in transformed_points:
            x_p = int(round(p[0]))
            y_p = int(round(p[1]))
            if 0 <= y_p < h and 0 <= x_p < w:
                grid[y_p, x_p] = 1

        return grid

    def hausdorff_distance(self, grid1, grid2):
        """
        Convert each binary grid to a set of points, then compute Hausdorff distance.
        """
        pts1 = np.argwhere(grid1 == 1)
        pts2 = np.argwhere(grid2 == 1)

        if len(pts1) == 0 and len(pts2) == 0:
            return 0.0
        if len(pts1) == 0 or len(pts2) == 0:
            return float('inf')

        fwd = directed_hausdorff(pts1, pts2)[0]
        bwd = directed_hausdorff(pts2, pts1)[0]
        return max(fwd, bwd)

    def rank_reference_gestures(self, new_grid):
        """
        Compare `new_grid` with each reference gesture using Hausdorff distance,
        return a sorted list of (gesture_name, distance).
        """
        scores = {}
        for gesture_name, path in REFERENCE_PATHS.items():
            if not os.path.exists(path):
                print(f"Warning: Reference file not found: {path}")
                continue
            ref_grid = np.load(path)
            distance = self.hausdorff_distance(new_grid, ref_grid)
            scores[gesture_name] = distance
        
        # Sort by ascending distance (lower => more similar)
        ranking = sorted(scores.items(), key=lambda x: x[1])
        
        
        return ranking

    def save_gesture_grid(self, grid, save_as_image=True, save_as_npy=True):
        """
        Same as before, if you still need saving logic.
        """
        timestamp = int(time.time()) 
        if save_as_image:
            filename_img = f"drawn_gestures/saved_gesture_{timestamp}.png"
            cv2.imwrite(filename_img, grid * 255)
            print(f"Saved gesture image as: {filename_img}")

        if save_as_npy:
            filename_npy = f"drawn_gestures/saved_gesture_{timestamp}.npy"
            np.save(filename_npy, grid)
            print(f"Saved gesture data as: {filename_npy}")
