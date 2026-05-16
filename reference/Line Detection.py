    def _detect_lines_in_frame(self, frame, original_width=None, filter_noise=False):
        """
        Detect vertical lines in frame using Canny + Sobel edge detection.
        Returns list of x-coordinates of detected vertical lines.
        """
        try:
            original_height, original_frame_width = frame.shape[:2]
            if original_width is None:
                original_width = original_frame_width
            
            height, width = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect edges
            edges = cv2.Canny(gray, 50, 150)
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobelx_abs = np.abs(sobelx)
            
            # Find full-height vertical lines
            vertical_lines = []
            line_strengths = []
            
            for col in range(width):
                column_edges = edges[:, col]
                edge_coverage = np.sum(column_edges > 0) / height
                
                column_gradient = sobelx_abs[:, col]
                strong_gradient_count = np.sum(column_gradient > 40)
                gradient_coverage = strong_gradient_count / height
                
                if edge_coverage >= 0.50 or gradient_coverage >= 0.50:
                    vertical_lines.append(col)
                    line_strengths.append((col, edge_coverage, gradient_coverage))
            
            if len(vertical_lines) == 0:
                return []
            
            # Merge adjacent pixels
            cluster_tolerance = max(2, int(width / 512))
            distinct_lines = []
            distinct_strengths = []
            current_cluster_start = 0
            current_cluster_end = 0
            
            for i in range(1, len(vertical_lines)):
                if vertical_lines[i] - vertical_lines[current_cluster_end] <= cluster_tolerance:
                    current_cluster_end = i
                else:
                    cluster = line_strengths[current_cluster_start:current_cluster_end+1]
                    best = max(cluster, key=lambda x: (x[1], x[2]))
                    distinct_lines.append(best[0])
                    distinct_strengths.append((best[1], best[2]))
                    current_cluster_start = i
                    current_cluster_end = i
            
            cluster = line_strengths[current_cluster_start:current_cluster_end+1]
            best = max(cluster, key=lambda x: (x[1], x[2]))
            distinct_lines.append(best[0])
            distinct_strengths.append((best[1], best[2]))
            
            # Filter weak lines in 4-line cases
            if len(distinct_lines) == 4:
                combined_strengths = [(i, canny + sobel) for i, (canny, sobel) in enumerate(distinct_strengths)]
                combined_strengths.sort(key=lambda x: x[1])
                weakest_idx = combined_strengths[0][0]
                weakest_strength = combined_strengths[0][1]
                median_strength = combined_strengths[2][1]
                
                if weakest_strength < 0.5 * median_strength:
                    distinct_lines.pop(weakest_idx)
            
            # Smart filtering for 5 lines
            if len(distinct_lines) == 5:
                combined_strengths = [(i, canny + sobel) for i, (canny, sobel) in enumerate(distinct_strengths)]
                combined_strengths.sort(key=lambda x: x[1])
                weakest_idx = combined_strengths[0][0]
                second_weakest_idx = combined_strengths[1][0]
                weakest_strength = combined_strengths[0][1]
                second_weakest_strength = combined_strengths[1][1]
                
                # If weakest is <60% of second-weakest, remove it
                if weakest_strength < 0.6 * second_weakest_strength:
                    distinct_lines.pop(weakest_idx)
                    distinct_strengths.pop(weakest_idx)
                # Check if two weakest lines are close together (same bar split)
                elif abs(distinct_lines[weakest_idx] - distinct_lines[second_weakest_idx]) < 30:
                    distinct_lines.pop(weakest_idx)
                    distinct_strengths.pop(weakest_idx)
                else:
                    # Check if all 5 lines are relatively weak (likely noise)
                    avg_strength = sum(s for _, s in combined_strengths) / 5
                    if avg_strength < 1.2:  # Average strength threshold
                        if filter_noise:
                            return []
                    
                    # All 5 lines are strong - check for suspicious patterns
                    # Pattern: 3 lines close together within 100px - remove middle one
                    for i in range(3):  # Check positions 0-1-2, 1-2-3, 2-3-4
                        if i + 2 < 5:
                            dist1 = distinct_lines[i+1] - distinct_lines[i]
                            dist2 = distinct_lines[i+2] - distinct_lines[i+1]
                            # If three consecutive lines are all within 100px spacing
                            if dist1 < 100 and dist2 < 100:
                                # Remove the middle one (i+1)
                                distinct_lines.pop(i+1)
                                distinct_strengths.pop(i+1)
                                return distinct_lines
                    
                    # Fallback: Check if second-weakest is <90% of median
                    median_strength = combined_strengths[2][1]
                    if second_weakest_strength < 0.9 * median_strength:
                        distinct_lines.pop(second_weakest_idx)
                        distinct_strengths.pop(second_weakest_idx)
                    else:
                        if filter_noise:
                            return []
            
            # Filter noise: >5 lines
            if len(distinct_lines) > 5:
                if filter_noise:
                    return []
            
            return distinct_lines

        except Exception as e:
            print(f"    Error in line detection: {e}")
            return []

    def _check_lines_in_area(self, camera=None, use_mss=False):
        """
        Check for vertical lines in the fish area (Line mode exit condition).
        Returns True if minimum number of lines are detected (configurable).
        Uses MSS for fish area capture to avoid DXCam instance conflicts.
        """
        try:
            # Get minimum line count from settings (configurable via GUI)
            min_line_count = self._get_rod_specific_setting("fish_line_min_count", 4)

            # Get fish area coordinates
            fish_area = self.fish_box
            if not fish_area:
                print("    No fish area set, cannot check lines")
                return False

            x1, y1, x2, y2 = fish_area["x1"], fish_area["y1"], fish_area["x2"], fish_area["y2"]

            # Use MSS for fish area capture
            with mss.mss() as sct:
                monitor = {"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1}
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            # Detect lines in frame (with noise filtering for exit condition)
            line_coordinates = self._detect_lines_in_frame(frame, filter_noise=True)

            # Check if minimum lines detected
            if len(line_coordinates) >= min_line_count:
                print(f"    📏 Line detection: Found {len(line_coordinates)} lines (min: {min_line_count})")
                return True

            return False

        except Exception as e:
            print(f"    Error checking lines: {e}")
            return False