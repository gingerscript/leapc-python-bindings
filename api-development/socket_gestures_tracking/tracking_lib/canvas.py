import cv2
import numpy as np
from collections import deque
import time  # to generate timestamps
import leap

_TRACKING_MODES = {
    leap.TrackingMode.Desktop: "Desktop",
    leap.TrackingMode.HMD: "HMD",
    leap.TrackingMode.ScreenTop: "ScreenTop",
}

class Canvas:
    def __init__(self):
        self.name = "Python Gemini Visualiser"
        
        # Note: screen_size = [height, width]
        self.screen_size = [500, 700]
        
        # Now store 3D points: (x, y, z)
        self.drawn_points = deque(maxlen=200)
        
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
        """
        Stop drawing. If we have more than 10 points, convert them
        into a 2D grid and display the gesture in a separate window.
        """
        self.is_drawing = False
        
        # If enough points have been drawn, process the gesture
        if len(self.drawn_points) > 10:
            grid = self.create_grid_from_points(
                points=self.drawn_points,
                grid_size=(100, 100)  # e.g., 100×100 grid
            )
            # Display the grid as a black-and-white image in a new window
            cv2.imshow("Gesture Grid", grid * 255)
            cv2.waitKey(20)

            # --------------------------
            #  Call our new save method
            # --------------------------
            self.save_gesture_grid(grid, save_as_image=False, save_as_npy=False)

        # Clear the points regardless
        self.clear_gesture_screen()

    def clear_gesture_screen(self):
        """Erase all stored points (the gesture)."""
        self.drawn_points.clear()

    def get_joint_position(self, leap_vector, enable_z=True):
        """
        Convert Leap Motion 3D coordinates to Canvas coordinates.
        Returns an (x, y, z) tuple (by default) or (x, y) if enable_z=False.
        """
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
        """
        Update self.output_image with hand skeleton/dot drawings for the current frame.
        """
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
            return  # No hands, no drawing

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
        """
        Draw either 'Dots' or 'Skeleton' representation of each bone.
        """
        bone_start = self.get_joint_position(bone.prev_joint, enable_z=True)
        bone_end   = self.get_joint_position(bone.next_joint, enable_z=True)

        if self.hands_format == "Dots":
            if bone_start:
                cv2.circle(self.output_image, bone_start[:2], 2, self.hands_colour, -1)
            if bone_end:
                cv2.circle(self.output_image, bone_end[:2], 2, self.hands_colour, -1)
        else:
            # Skeleton mode
            if bone_start:
                cv2.circle(self.output_image, bone_start[:2], 3, self.hands_colour, -1)
            if bone_end:
                cv2.circle(self.output_image, bone_end[:2], 3, self.hands_colour, -1)
            if bone_start and bone_end:
                cv2.line(self.output_image, bone_start[:2], bone_end[:2], self.hands_colour, 2)

        # Example: if the fingertip of the index finger => "air-drawing"
        if (digit_idx == 1) and (bone_idx == 3):
            # Let's say we only draw with the right hand: hand.type.value == 1
            if self.is_drawing and hand.type.value == 1 and bone_end:
                self.counter += 1
                if self.counter % 2 == 0:  # rate-limiting
                    self.drawn_points.append(bone_end)
                    self.counter = 0

    def create_grid_from_points(
        self,
        points,
        grid_size=(100, 100),
        preserve_aspect=True,
        fill_entire_grid=False
    ):
        """
        Convert a set of (x, y, z) or (x, y) points to a 2D binary grid.
        1) Crop to bounding box by subtracting min_x, min_y.
        2) Scale to fit the grid_size.
        - If preserve_aspect=True, keep the same aspect ratio.
        - If fill_entire_grid=True, it will stretch to fill both dimensions (distorts aspect).
        """
        h, w = grid_size
        grid = np.zeros((h, w), dtype=np.uint8)
        
        arr = np.array(points)  # shape: (N, 3) or (N, 2)
        if len(arr) == 0:
            return grid  # nothing to draw
        
        # 1) Crop: shift the shape so min_x -> 0, min_y -> 0
        x_min, y_min = arr[:, 0].min(), arr[:, 1].min()
        x_max, y_max = arr[:, 0].max(), arr[:, 1].max()
        
        width  = x_max - x_min
        height = y_max - y_min
        
        if width == 0:
            width = 1
        if height == 0:
            height = 1

        # 2) Compute scale factors
        scale_x = (w - 1) / width
        scale_y = (h - 1) / height
        
        if preserve_aspect:
            final_scale = min(scale_x, scale_y)
            scale_x = final_scale
            scale_y = final_scale
        else:
            if fill_entire_grid:
                # Distort: use each dimension's scale independently
                pass
            else:
                final_scale = min(scale_x, scale_y)
                scale_x = final_scale
                scale_y = final_scale

        # 3) Apply the shift & scale
        transformed_points = []
        for (px, py, *rest) in arr:
            new_x = (px - x_min) * scale_x
            new_y = (py - y_min) * scale_y
            if len(rest) > 0:
                transformed_points.append((new_x, new_y, rest[0]))
            else:
                transformed_points.append((new_x, new_y))

        # 4) Rasterize: map to integer grid
        for p in transformed_points:
            x_p = int(round(p[0]))
            y_p = int(round(p[1]))
            if 0 <= y_p < h and 0 <= x_p < w:
                grid[y_p, x_p] = 1

        return grid

    # ---------------------------------------------------
    #  NEW FUNCTION: SAVE GESTURE GRID (AS IMAGE or NPY)
    # ---------------------------------------------------
    def save_gesture_grid(self, grid, save_as_image=True, save_as_npy=True):
        """
        Save the grid to disk so we can do further analysis or training later.
        Two ways:
          1) As an image (PNG/JPG) - black & white
          2) As a NumPy .npy file
        """
        # Construct a unique filename
        timestamp = int(time.time()) 
        
        if save_as_image:
            # Option A: Save as image
            filename_img = f"saved_gesture_{timestamp}.png"
            # Convert 0/1 grid to 0/255
            cv2.imwrite(filename_img, grid * 255)
            print(f"Saved gesture image as: {filename_img}")

        if save_as_npy:
            # Option B: Save as .npy array
            filename_npy = f"saved_gesture_{timestamp}.npy"
            np.save(filename_npy, grid)
            print(f"Saved gesture data as: {filename_npy}")

   