    def _detect_circle_in_frame(self, frame):
        """
        Detect circles in frame using strict Hough Circle Transform for perfect circles only.
        Specifically optimized for SHAKE button detection with strict filtering.
        Returns (center_x, center_y) of the best circle found, or None if no circles.

        Args:
            frame: BGR image from dxcam/mss
        """
        try:
            # Convert BGR to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Scale circle detection parameters based on resolution
            # Reference values are for 2560x1440 resolution
            # Use average of scale_x and scale_y for uniform circle scaling
            scale_factor = (self.scale_x + self.scale_y) / 2

            # Scale parameters proportionally to resolution
            scaled_min_dist = int(150 * scale_factor)
            scaled_min_radius = int(50 * scale_factor)
            scaled_max_radius = int(300 * scale_factor)
            scaled_good_min_radius = int(50 * scale_factor)
            scaled_good_max_radius = int(120 * scale_factor)

            # Hough Circle Transform with strict parameters for perfect circles only
            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=1,           # Inverse ratio of accumulator resolution
                minDist=scaled_min_dist,    # Increased distance between circles to avoid overlapping detections
                param1=100,     # Higher Canny threshold for edge detection
                param2=100,     # Much higher accumulator threshold - only perfect circles
                minRadius=scaled_min_radius,   # Larger minimum radius to ignore small false positives
                maxRadius=scaled_max_radius   # Maximum circle radius
            )

            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")

                # Additional filtering: Only accept circles with good radius range for SHAKE buttons
                good_circles = []
                for (x, y, r) in circles:
                    # SHAKE buttons are typically 50-120 pixels radius (scaled)
                    if scaled_good_min_radius <= r <= scaled_good_max_radius:
                        good_circles.append((x, y, r))

                if good_circles:
                    # Return the largest good circle (most likely to be SHAKE button)
                    largest_circle = max(good_circles, key=lambda c: c[2])
                    x, y, r = largest_circle
                    print(f"    ⚡ Circle detected at local ({x}, {y}) with radius {r} (scale: {scale_factor:.3f})")
                    return (int(x), int(y))

            # Only use strict HoughCircles detection - no backup methods to avoid false positives
            return None

        except Exception as e:
            print(f"    Error in circle detection: {e}")
            return None