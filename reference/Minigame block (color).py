import time
import dxcam
from win32api import windll
import ctypes
import cv2
import numpy as np
import sys
import Quartz
import mss
# Ctypes/Quartz For Special Click Types
if sys.platform == "win32":
    windll = ctypes.windll.user32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
elif sys.platform == "darwin":
    def _move_mouse(x, y):
        point = Quartz.CGPointMake(float(x), float(y))
        Quartz.CGWarpMouseCursorPosition(point)
        Quartz.CGAssociateMouseAndMouseCursorPosition(True)

    def _mouse_event(event_type, x, y):
        event = Quartz.CGEventCreateMouseEvent(
            None,
            event_type,
            Quartz.CGPointMake(float(x), float(y)),
            Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
class App():
    def _execute_fish_stage_color(self):  # AI_TARGET: FISH_COLOR_DETECTION
        
        try:
            # Load fish settings for current rod
            current_rod = self.settings.get("fish_rod_type", "Default")
            
            # Get colors and tolerances for current rod
            target_line_color = self._get_fish_color_for_rod("fish_target_line_color", current_rod)
            left_bar_color = self._get_fish_color_for_rod("fish_left_bar_color", current_rod)
            right_bar_color = self._get_fish_color_for_rod("fish_right_bar_color", current_rod)
            arrow_color = self._get_fish_color_for_rod("fish_arrow_color", current_rod)
            
            target_line_tolerance = self._get_fish_tolerance_for_rod("fish_target_line_tolerance", current_rod)
            left_bar_tolerance = self._get_fish_tolerance_for_rod("fish_left_bar_tolerance", current_rod)
            right_bar_tolerance = self._get_fish_tolerance_for_rod("fish_right_bar_tolerance", current_rod)
            arrow_tolerance = self._get_fish_tolerance_for_rod("fish_arrow_tolerance", current_rod)
            
            # Get fish-specific settings
            scan_fps = self._get_rod_specific_setting("fish_scan_fps", 150)
            fish_lost_timeout = self._get_rod_specific_setting("fish_lost_timeout", 1)
            bar_ratio_from_side = self._get_rod_specific_setting("fish_bar_ratio_from_side", 0.5)
            control_mode = self._get_rod_specific_setting("fish_control_mode", "Normal")
            kp = self._get_rod_specific_setting("fish_kp", 0.9)
            kd = self._get_rod_specific_setting("fish_kd", 0.3)
            pd_clamp = self._get_rod_specific_setting("fish_pd_clamp", 1.0)
            
            # Get capture mode from settings  
            capture_mode, use_mss = self._get_capture_mode_settings()
            
            # Fish area coordinates
            if not self.fish_box:
                print("⚠️ No fish area set - cannot proceed")
                return "restart"
                
            x1, y1, x2, y2 = self.fish_box["x1"], self.fish_box["y1"], self.fish_box["x2"], self.fish_box["y2"]
            region = (x1, y1, x2, y2)
            width = x2 - x1
            height = y2 - y1
            
            print(f"🐟 Fish area: ({x1},{y1}) to ({x2},{y2}) - {width}x{height}")
            print(f"🎣 Rod: {current_rod} | Capture: {capture_mode} | FPS: {scan_fps}")
            print(f"🎨 Colors - Target: {target_line_color}, Left: {left_bar_color}, Right: {right_bar_color}, Arrow: {arrow_color}")

            # Move cursor to top middle of shake area (anti-Roblox detection)
            if self.shake_box:
                shake_center_x = (self.shake_box["x1"] + self.shake_box["x2"]) // 2
                shake_top_y = self.shake_box["y1"]
                print(f"🖱️ Moving cursor to shake area top-middle: ({shake_center_x}, {shake_top_y})")
                windll.user32.SetCursorPos(shake_center_x, shake_top_y)
                # Move 1 pixel down relatively (anti-Roblox detection)
                windll.user32.mouse_event(MOUSEEVENTF_MOVE, 0, 1, 0, 0)
                print(f"🖱️ Moved cursor 1px down relatively")

            # Arrow disabled check
            arrow_enabled = arrow_color is not None and arrow_color.lower() not in ["none", "#none", ""]
            if not arrow_enabled:
                print("⚙️ Arrow color disabled - using bar-only mode")

            # Pre-compute BGR colors once before loop (optimization)
            target_line_bgr = self._hex_to_bgr(target_line_color)
            left_bar_bgr = self._hex_to_bgr(left_bar_color)
            right_bar_bgr = self._hex_to_bgr(right_bar_color)
            arrow_bgr = self._hex_to_bgr(arrow_color) if arrow_enabled else None

            # Initialize capture method
            camera = None
            mss_instance = None

            if use_mss:
                print("📷 Using MSS capture for fish detection")
                mss_monitor = {"top": y1, "left": x1, "width": width, "height": height}
                mss_instance = mss.mss()  # Create once, reuse in loop
            else:
                print("🎥 Using DXCAM capture for fish detection")
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Release any previous camera instance before retry
                        if camera is not None:
                            try:
                                camera.release()
                            except:
                                pass
                            camera = None
                        
                        camera = dxcam.create(output_idx=0, output_color="BGR")
                        if camera:
                            break
                        print(f"❌ DXCam creation failed (attempt {attempt + 1}/{max_retries})")
                        time.sleep(0.1)
                    except Exception as e:
                        print(f"❌ DXCam error (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(0.1)

                if not camera:
                    print("⚠️ Failed to create DXCam - falling back to MSS")
                    use_mss = True
                    mss_monitor = {"top": y1, "left": x1, "width": width, "height": height}
                    mss_instance = mss.mss()  # Create once, reuse in loop
            
            # Calculate scan delay
            scan_delay = 1.0 / scan_fps if scan_fps > 0 else 0.001
            if scan_fps >= 1000:
                scan_delay = 0.001  # 0ms delay special case
            
            # Initialize tracking variables
            target_line_last_x = None
            bar_center_x = None
            target_line_lost_timer = 0.0
            last_scan_time = time.time()
            
            # Exit condition checking variables
            last_exit_check_time = time.time()
            exit_check_interval = 0.5  # Check every 500ms during valid detection
            
            # Stability detection variables
            stability_state = True  # Start in stability mode
            stability_initial_target_x = None
            stability_initial_bar_x = None
            stability_scan_count = 0
            stability_alternate_state = False  # Alternates between hold/release
            
            # PD control variables
            last_error = None
            last_target_x = None
            is_holding_click = False
            frame_counter = 0  # For periodic logging

            # Arrow fallback variables (based on v5.py logic)
            estimated_box_length = None
            has_calculated_length_once = False
            last_left_x = None
            last_right_x = None
            last_indicator_x = None
            last_holding_state = False

            # Track if bars were found to skip arrow scanning (optimization)
            bars_found_previously = False

            print("🔄 Starting fish detection loop...")

            # Main fish detection loop
            while self.global_hotkey_states["Start/Stop"] and not self.is_quitting:
                current_time = time.time()
                frame_counter += 1  # Increment frame counter
                
                # Capture frame with retry loop - keep trying until we get a frame
                frame = None
                capture_attempts = 0
                max_capture_attempts = 10

                while frame is None and capture_attempts < max_capture_attempts:
                    try:
                        if use_mss:
                            # Reuse mss_instance instead of creating new one each frame
                            screenshot = mss_instance.grab(mss_monitor)
                            frame = np.array(screenshot)
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        else:
                            # Use linear grab() method
                            frame = camera.grab(region=region)

                        if frame is None:
                            capture_attempts += 1
                            if capture_attempts == 1:
                                print(f"⚠️ Frame capture returned None, retrying... (attempt {capture_attempts}/{max_capture_attempts})")
                            time.sleep(0.001)  # 1ms delay between retries

                    except Exception as e:
                        capture_attempts += 1
                        print(f"❌ Capture error on attempt {capture_attempts}: {e}")
                        time.sleep(0.001)

                # If we exhausted all retries, skip this cycle
                if frame is None:
                    print(f"❌ Failed to capture frame after {max_capture_attempts} attempts, skipping cycle")
                    time.sleep(scan_delay)
                    continue

                # Detect colors in frame (using pre-computed BGR colors)
                # Skip bar detection entirely when in edge lock state (optimization)
                in_edge_lock = hasattr(self, '_locked_edge_threshold') and self._locked_edge_threshold is not None
                
                if in_edge_lock:
                    # Edge lock active - only scan for target line, skip all bar detection
                    detection_result = self._detect_fish_colors_in_frame(
                        frame, target_line_bgr, left_bar_bgr, right_bar_bgr,
                        arrow_bgr,
                        target_line_tolerance, 0, 0,  # Set bar tolerances to 0 to skip detection
                        0,  # Skip arrow
                        skip_arrow_scan=True
                    )
                    # Use locked bar positions from memory
                    target_line_x = detection_result.get("target_line_x")
                    target_left_x = detection_result.get("target_left_x")
                    target_right_x = detection_result.get("target_right_x")
                    target_middle_x = detection_result.get("target_middle_x")
                    bar_left_x = self._last_bar_left_x
                    bar_right_x = self._last_bar_right_x
                    arrow_center_x = None
                    if frame_counter % 10 == 0:
                        print("🔒 EDGE LOCK: Skipping bar detection, using locked positions")
                else:
                    # Normal detection - scan for everything
                    skip_arrow = bars_found_previously and arrow_enabled
                    if skip_arrow and frame_counter % 10 == 0:  # Log every 10th frame
                        print("⚡ Optimization: Skipping arrow scan (bars found)")
                    detection_result = self._detect_fish_colors_in_frame(
                        frame, target_line_bgr, left_bar_bgr, right_bar_bgr,
                        arrow_bgr,
                        target_line_tolerance, left_bar_tolerance, right_bar_tolerance,
                        arrow_tolerance if arrow_enabled else 0,
                        skip_arrow_scan=skip_arrow
                    )
                    
                    target_line_x = detection_result.get("target_line_x")
                    target_left_x = detection_result.get("target_left_x")
                    target_right_x = detection_result.get("target_right_x")
                    target_middle_x = detection_result.get("target_middle_x")
                    bar_left_x = detection_result.get("bar_left_x")
                    bar_right_x = detection_result.get("bar_right_x")
                    arrow_center_x = detection_result.get("arrow_center_x")
                
                # Debug logging - show detected color coordinates
                debug_colors = []
                if target_left_x is not None and target_right_x is not None and target_middle_x is not None:
                    debug_colors.append(f"Target=L{target_left_x:.0f}/M{target_middle_x:.0f}/R{target_right_x:.0f}")
                elif target_line_x is not None:
                    debug_colors.append(f"Target={target_line_x:.0f}")
                if bar_left_x is not None:
                    debug_colors.append(f"BarL={bar_left_x:.0f}")
                if bar_right_x is not None:
                    debug_colors.append(f"BarR={bar_right_x:.0f}")
                if arrow_center_x is not None:
                    debug_colors.append(f"Arrow={arrow_center_x:.0f}")

                if debug_colors:
                    print(f"🔍 DEBUG: Detected X coords: {', '.join(debug_colors)}")
                
                # Check exit condition (every 500ms when valid detection found)
                if (target_line_x is not None or target_left_x is not None) and (bar_left_x is not None or bar_right_x is not None or arrow_center_x is not None):
                    # Valid detection - check exit condition periodically
                    if current_time - last_exit_check_time >= exit_check_interval:
                        exit_result = self._check_fish_exit_condition()
                        if exit_result == "fish_stage":
                            print(f"🐟 Fish stage exit condition met - green color detected in bottom left")
                            break
                        last_exit_check_time = current_time
                
                # NOTE: Live feed overlay update moved to after bar calculations
                # so it can show arrow-estimated positions too
                
                # Update target line position and reset timer if found
                if target_line_x is not None:
                    target_line_last_x = target_line_x  # Use most right pixel as requested
                    target_line_lost_timer = 0.0  # Reset timer
                else:
                    # Target line lost - increment timer
                    target_line_lost_timer += (current_time - last_scan_time)
                    
                    # Check if target line lost too long
                    if target_line_lost_timer >= fish_lost_timeout:
                        print(f"⚠️ Target line lost for {fish_lost_timeout}s - exiting fish stage")
                        break
                
                # Initialize last known bar positions
                if not hasattr(self, '_last_bar_left_x'):
                    self._last_bar_left_x = None
                if not hasattr(self, '_last_bar_right_x'):
                    self._last_bar_right_x = None
                if not hasattr(self, '_last_bar_box_size'):
                    self._last_bar_box_size = None  # Track box size (right - left)
                if not hasattr(self, '_last_bar_center_x'):
                    self._last_bar_center_x = None  # Track last known center for arrow side detection
                
                # Calculate bar center and remember positions
                # Track if ANY bar color was detected in current frame
                any_bar_detected_this_frame = (bar_left_x is not None or bar_right_x is not None)
                bar_center_found = False
                if bar_left_x is not None and bar_right_x is not None:
                    # Both bars detected - validate and save positions
                    # Ensure left is never greater than right (swap if needed)
                    if bar_left_x > bar_right_x:
                        bar_left_x, bar_right_x = bar_right_x, bar_left_x
                        print(f"🔄 Color mode: Swapped bars (L was > R)")

                    # Calculate current frame values (don't update memory yet - edge detection does that)
                    bar_center_x = (bar_left_x + bar_right_x) / 2.0
                    bar_center_found = True
                    bar_box_size = bar_right_x - bar_left_x
                    print(f"📊 Color mode: Bars at L={bar_left_x:.0f}, R={bar_right_x:.0f}, Size={bar_box_size:.0f}px")
                elif bar_left_x is not None:
                    # Only left bar found - use last known right position
                    bar_right_x = self._last_bar_right_x  # Use last known right position
                    if bar_right_x is not None:
                        # Validate: left must be less than right
                        if bar_left_x < bar_right_x:
                            bar_center_x = (bar_left_x + bar_right_x) / 2.0
                            bar_center_found = True
                        else:
                            # Invalid: left >= right, use old positions
                            print(f"⚠️ Color mode: Rejected left bar {bar_left_x:.0f} (>= right {bar_right_x:.0f})")
                            bar_left_x = self._last_bar_left_x  # Keep old position
                            if bar_left_x is not None:
                                bar_center_x = (bar_left_x + bar_right_x) / 2.0
                                bar_center_found = True
                elif bar_right_x is not None:
                    # Only right bar found - use last known left position
                    bar_left_x = self._last_bar_left_x  # Use last known left position
                    if bar_left_x is not None:
                        # Validate: right must be greater than left
                        if bar_right_x > bar_left_x:
                            bar_center_x = (bar_left_x + bar_right_x) / 2.0
                            bar_center_found = True
                        else:
                            # Invalid: right <= left, use old positions
                            print(f"⚠️ Color mode: Rejected right bar {bar_right_x:.0f} (<= left {bar_left_x:.0f})")
                            bar_right_x = self._last_bar_right_x  # Keep old position
                            if bar_right_x is not None:
                                bar_center_x = (bar_left_x + bar_right_x) / 2.0
                                bar_center_found = True
                
                # Arrow fallback logic: ONLY triggers if NO bar colors were detected in this frame
                # If arrow is found, it updates ONE side (whichever is closer), OTHER side uses old position
                if not any_bar_detected_this_frame and arrow_enabled and arrow_center_x is not None:
                    last_center = self._last_bar_center_x
                    box_size = self._last_bar_box_size

                    # If we have previous bar data, determine which side the arrow is on
                    if last_center is not None and box_size is not None and box_size > 0:
                        # Get last known bar positions for validation
                        last_left = self._last_bar_left_x
                        last_right = self._last_bar_right_x

                        # Determine which side based on center comparison
                        arrow_on_left_side = arrow_center_x < last_center

                        # SMART VALIDATION: Check if arrow is actually near the bar we think it is
                        # Calculate distances to both last known bars
                        dist_to_left = abs(arrow_center_x - last_left) if last_left is not None else float('inf')
                        dist_to_right = abs(arrow_center_x - last_right) if last_right is not None else float('inf')

                        # Self-correction: If arrow is much closer to the opposite bar, we detected wrong side!
                        # Threshold: arrow should be within reasonable distance (box_size / 4) of expected bar
                        proximity_threshold = box_size / 4

                        if arrow_on_left_side:
                            # We think arrow is on LEFT, but verify it's actually near left bar
                            if dist_to_right < dist_to_left and dist_to_right < proximity_threshold:
                                # Arrow is actually closer to RIGHT bar - we were wrong!
                                print(f"🔧 Arrow mode: SELF-CORRECTION - Arrow at {arrow_center_x:.0f} closer to RIGHT bar ({dist_to_right:.0f}px) than LEFT ({dist_to_left:.0f}px)")
                                arrow_on_left_side = False  # Flip the decision

                        else:
                            # We think arrow is on RIGHT, but verify it's actually near right bar
                            if dist_to_left < dist_to_right and dist_to_left < proximity_threshold:
                                # Arrow is actually closer to LEFT bar - we were wrong!
                                print(f"🔧 Arrow mode: SELF-CORRECTION - Arrow at {arrow_center_x:.0f} closer to LEFT bar ({dist_to_left:.0f}px) than RIGHT ({dist_to_right:.0f}px)")
                                arrow_on_left_side = True  # Flip the decision

                        # Now apply the corrected decision
                        if arrow_on_left_side:
                            # Arrow is on the LEFT side - update left bar, keep right bar from memory
                            bar_left_x = arrow_center_x
                            bar_right_x = self._last_bar_right_x

                            if bar_right_x is None:
                                # If no right bar in memory, calculate from box size
                                bar_right_x = bar_left_x + box_size

                            # Validate: ensure left < right
                            if bar_left_x < bar_right_x:
                                self._last_bar_left_x = bar_left_x
                                self._last_bar_right_x = bar_right_x
                                bar_center_x = (bar_left_x + bar_right_x) / 2.0
                                self._last_bar_center_x = bar_center_x
                                bar_center_found = True
                                print(f"⬅️ Arrow mode: Arrow LEFT of center - L={bar_left_x:.0f} (arrow), R={bar_right_x:.0f} (kept)")
                            else:
                                print(f"⚠️ Arrow mode: Invalid - arrow left {bar_left_x:.0f} >= right {bar_right_x:.0f}")
                        else:
                            # Arrow is on the RIGHT side - update right bar, keep left bar from memory
                            bar_right_x = arrow_center_x
                            bar_left_x = self._last_bar_left_x

                            if bar_left_x is None:
                                # If no left bar in memory, calculate from box size
                                bar_left_x = bar_right_x - box_size

                            # Validate: ensure left < right
                            if bar_left_x < bar_right_x:
                                self._last_bar_left_x = bar_left_x
                                self._last_bar_right_x = bar_right_x
                                bar_center_x = (bar_left_x + bar_right_x) / 2.0
                                self._last_bar_center_x = bar_center_x
                                bar_center_found = True
                                print(f"➡️ Arrow mode: Arrow RIGHT of center - L={bar_left_x:.0f} (kept), R={bar_right_x:.0f} (arrow)")
                            else:
                                print(f"⚠️ Arrow mode: Invalid - left {bar_left_x:.0f} >= arrow right {bar_right_x:.0f}")

                    # Fallback: Try to establish initial box size from previous positions
                    elif self._last_bar_left_x is not None and self._last_bar_right_x is not None:
                        box_size = self._last_bar_right_x - self._last_bar_left_x
                        last_center = (self._last_bar_left_x + self._last_bar_right_x) / 2.0

                        if box_size > 0:
                            self._last_bar_box_size = box_size
                            self._last_bar_center_x = last_center

                            # Determine side based on arrow position relative to last center
                            if arrow_center_x < last_center:
                                bar_left_x = arrow_center_x
                                bar_right_x = bar_left_x + box_size
                                print(f"⬅️ Arrow mode: Initial LEFT - L={bar_left_x:.0f} (arrow), R={bar_right_x:.0f} (size={box_size:.0f})")
                            else:
                                bar_right_x = arrow_center_x
                                bar_left_x = bar_right_x - box_size
                                print(f"➡️ Arrow mode: Initial RIGHT - L={bar_left_x:.0f} (size={box_size:.0f}), R={bar_right_x:.0f} (arrow)")

                            self._last_bar_left_x = bar_left_x
                            self._last_bar_right_x = bar_right_x
                            bar_center_x = (bar_left_x + bar_right_x) / 2.0
                            self._last_bar_center_x = bar_center_x
                            bar_center_found = True
                        else:
                            # Invalid box size (<=0) - use default based on fish area width
                            default_box_size = width // 2
                            bar_left_x = arrow_center_x
                            bar_right_x = bar_left_x + default_box_size

                            self._last_bar_left_x = bar_left_x
                            self._last_bar_right_x = bar_right_x
                            self._last_bar_box_size = default_box_size

                            bar_center_x = (bar_left_x + bar_right_x) / 2.0
                            self._last_bar_center_x = bar_center_x
                            bar_center_found = True
                            print(f"⚠️ Arrow mode: Invalid box size (<=0), using fish area width/2={default_box_size}px - L={bar_left_x:.0f}, R={bar_right_x:.0f}")

                    else:
                        # No previous data - assume a default box size based on fish area width
                        # Default box size: half the width of the fish area (reasonable estimate)
                        default_box_size = width // 2

                        # Start with arrow as left bar, calculate right from default size
                        bar_left_x = arrow_center_x
                        bar_right_x = bar_left_x + default_box_size

                        # Save these initial estimates
                        self._last_bar_left_x = bar_left_x
                        self._last_bar_right_x = bar_right_x
                        self._last_bar_box_size = default_box_size

                        bar_center_x = (bar_left_x + bar_right_x) / 2.0
                        self._last_bar_center_x = bar_center_x
                        bar_center_found = True
                        print(f"⚠️ Arrow mode: No previous data, using fish area width/2 as default box size={default_box_size}px - L={bar_left_x:.0f}, R={bar_right_x:.0f}")

                # Update bars_found_previously flag for next frame optimization
                # If bars were detected from colors (not arrow fallback), we can skip arrow scanning next time
                bars_detected_from_colors = (detection_result.get("bar_left_x") is not None or
                                            detection_result.get("bar_right_x") is not None)
                bars_found_previously = bars_detected_from_colors

                # Show visual overlay of detected elements (for debugging)
                self._show_fish_visualization(
                    frame, target_line_x, bar_left_x, bar_right_x, bar_center_x, arrow_center_x,
                    width, height, x1, y1,
                    target_left_x=target_left_x, target_right_x=target_right_x, target_middle_x=target_middle_x
                )

                # PD Control (only if both target line and bar center are available)
                if target_line_last_x is not None and bar_center_found and bar_center_x is not None:
                    
                    # STEP 1: Edge detection - determine if at edges and whether to update bar positions
                    current_bar_width = abs(bar_right_x - bar_left_x) if bar_left_x is not None and bar_right_x is not None else 0
                    
                    # Initialize transition state (default: not in transition)
                    in_transition = False
                    
                    # Lock edge threshold when entering edge zone (don't update while at edge)
                    if not hasattr(self, '_locked_edge_threshold') or self._locked_edge_threshold is None:
                        # Not at edge or first time - calculate from current bar width
                        edge_threshold = current_bar_width * bar_ratio_from_side
                        self._locked_edge_threshold = edge_threshold
                    else:
                        # Already at edge - use locked threshold
                        edge_threshold = self._locked_edge_threshold
                    
                    target_at_left_edge = target_line_last_x < edge_threshold
                    target_at_right_edge = target_line_last_x > (width - edge_threshold)
                    target_at_edge = target_at_left_edge or target_at_right_edge
                    
                    # Update bar positions ONLY if in safe zone (not at edges)
                    if not target_at_edge:
                        # Clear locked threshold when in safe zone
                        self._locked_edge_threshold = None
                        if bar_left_x is not None:
                            self._last_bar_left_x = bar_left_x
                        if bar_right_x is not None:
                            self._last_bar_right_x = bar_right_x
                        if bar_center_x is not None:
                            self._last_bar_center_x = bar_center_x
                        # Update box size for arrow fallback
                        if bar_left_x is not None and bar_right_x is not None:
                            self._last_bar_box_size = bar_right_x - bar_left_x
                    
                    # STEP 2: Calculate error (ALWAYS, regardless of edge state)
                    # Use current detection for error calculation
                    error = target_line_last_x - bar_center_x
                    
                    # STEP 3: Stability state check (ALWAYS, regardless of edge state)
                    # Use MEMORY positions for stability check (only updated in safe zone)
                    if stability_state:
                        # Initialize reference positions on first detection
                        if stability_initial_target_x is None:
                            stability_initial_target_x = target_line_last_x
                            stability_initial_bar_x = self._last_bar_center_x if self._last_bar_center_x is not None else bar_center_x
                            print(f"📌 STABILITY: Initial positions - Target: {target_line_last_x:.0f}, Bar: {stability_initial_bar_x:.0f}")
                        
                        # Check if target line or bar has moved by 3 pixels (scaled to current resolution)
                        # Compare using MEMORY positions (which only update in safe zone)
                        stability_threshold = 3 * (width / 517)
                        target_moved = abs(target_line_last_x - stability_initial_target_x) >= stability_threshold
                        # Use memory bar position for comparison, fall back to current if memory not available
                        current_tracked_bar_x = self._last_bar_center_x if self._last_bar_center_x is not None else bar_center_x
                        bar_moved = abs(current_tracked_bar_x - stability_initial_bar_x) >= stability_threshold
                        
                        if target_moved or bar_moved:
                            # Exit stability mode
                            stability_state = False
                            print(f"🔄 STABILITY: Movement detected! Target moved: {target_moved}, Bar moved: {bar_moved}")
                            print(f"⚙️ STABILITY: Switching to normal PD control after {stability_scan_count} scans")
                        else:
                            # Stay in stability mode - alternate every 2 scans
                            stability_scan_count += 1
                            if stability_scan_count % 2 == 0:
                                stability_alternate_state = not stability_alternate_state
                            
                            # Stability alternation sets should_hold, but edge can override below
                            should_hold = stability_alternate_state
                            
                            # Update error for derivative calculation even in stability mode
                            last_error = error
                            last_target_x = target_line_last_x
                    
                    # STEP 4: Normal PD control (if not in stability)
                    if not stability_state:
                        # Select control algorithm based on mode
                        if control_mode in ["Normal", "Steady"]:
                            # P term - proportional to how far we need to move
                            p_term = kp * error
                            
                            # D term - ASYMMETRIC damping based on situation
                            d_term = 0.0
                            time_delta = current_time - last_scan_time
                            if last_target_x is not None and last_error is not None and time_delta > 0.001:
                                # Calculate bar velocity (how fast bar is moving)
                                last_bar_x = last_target_x - last_error
                                bar_velocity = (bar_center_x - last_bar_x) / time_delta
                                
                                # Determine if we're approaching or chasing
                                error_magnitude_decreasing = abs(error) < abs(last_error)
                                bar_moving_toward_target = (bar_velocity > 0 and error > 0) or (bar_velocity < 0 and error < 0)
                                
                                if error_magnitude_decreasing and bar_moving_toward_target:
                                    # APPROACHING TARGET - Strong damping to prevent overshoot (2x)
                                    damping_multiplier = 2.0
                                    d_term = -kd * damping_multiplier * bar_velocity
                                else:
                                    # CHASING TARGET - Minimal damping to allow fast movement (0.5x)
                                    damping_multiplier = 0.5
                                    d_term = -kd * damping_multiplier * bar_velocity
                            
                            # Combined control signal (PD controller output)
                            control_signal = p_term + d_term
                            control_signal = max(-pd_clamp, min(pd_clamp, control_signal))  # Clamp
                            
                            # DIRECTIONAL DECISION: Convert continuous signal to binary hold/release
                            if control_signal > 0:
                                should_hold = True
                            else:
                                should_hold = False
                        
                        elif control_mode == "NigGamble":
                            # NIGGAMBLE MODE: (Clone of Normal for now - will be modified)
                            p_term = kp * error
                            
                            # D term - ASYMMETRIC damping
                            d_term = 0.0
                            time_delta = current_time - last_scan_time
                            if last_target_x is not None and last_error is not None and time_delta > 0.001:
                                last_bar_x = last_target_x - last_error
                                bar_velocity = (bar_center_x - last_bar_x) / time_delta
                                
                                error_magnitude_decreasing = abs(error) < abs(last_error)
                                bar_moving_toward_target = (bar_velocity > 0 and error > 0) or (bar_velocity < 0 and error < 0)
                                
                                if error_magnitude_decreasing and bar_moving_toward_target:
                                    damping_multiplier = 2.0
                                    d_term = -kd * damping_multiplier * bar_velocity
                                else:
                                    damping_multiplier = 0.5
                                    d_term = -kd * damping_multiplier * bar_velocity
                            
                            control_signal = p_term + d_term
                            control_signal = max(-pd_clamp, min(pd_clamp, control_signal))  # Clamp
                            
                            if control_signal > 0:
                                should_hold = True
                            else:
                                should_hold = False
                        
                        # Update PD state for next iteration
                        last_error = error
                        last_target_x = target_line_last_x
                    
                    # STEP 5: Execute mouse control
                    # Apply edge overrides
                    if target_at_left_edge:
                        should_hold = False  # Force RELEASE at left edge
                        print(f"⬅️ EDGE: Left ({target_line_last_x:.0f} < {edge_threshold:.0f}) - FORCE RELEASE")
                    elif target_at_right_edge:
                        should_hold = True  # Force HOLD at right edge
                        print(f"➡️ EDGE: Right ({target_line_last_x:.0f} > {width - edge_threshold:.0f}) - FORCE HOLD")
                    elif in_transition:
                        print(f"⏳ TRANSITION: {'HOLD' if should_hold else 'RELEASE'}")
                    
                    # Execute the mouse action
                    mouse_action_taken = False
                    if should_hold and not is_holding_click:
                        windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        is_holding_click = True
                        mouse_action_taken = True
                        if stability_state:
                            print(f"  STABILITY #{stability_scan_count}: HOLD (Target: {target_line_last_x:.0f}, Bar: {bar_center_x:.0f}, Error: {error:.1f})")
                        elif not target_at_edge and not in_transition:
                            print(f" 🔒 HOLD [{control_mode}] - Error: {error:.1f}, Control: {control_signal:.1f}, P: {p_term:.1f}, D: {d_term:.1f}")
                    elif not should_hold and is_holding_click:
                        windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        is_holding_click = False
                        mouse_action_taken = True
                        if stability_state:
                            print(f"  STABILITY #{stability_scan_count}: RELEASE (Target: {target_line_last_x:.0f}, Bar: {bar_center_x:.0f}, Error: {error:.1f})")
                        elif not target_at_edge and not in_transition:
                            print(f" 🔓 RELEASE [{control_mode}] - Error: {error:.1f}, Control: {control_signal:.1f}, P: {p_term:.1f}, D: {d_term:.1f}")

                    if not mouse_action_taken and not stability_state and not target_at_edge and not in_transition:
                        current_state = "HOLDING" if is_holding_click else "RELEASED"
                        print(f"⚡ {current_state} [{control_mode}] - Error: {error:.1f}, Control: {control_signal:.1f}, P: {p_term:.1f}, D: {d_term:.1f}")
                    
                else:
                    # No tracking data - alternate hold/release to keep bar moving
                    if is_holding_click:
                        windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        is_holding_click = False
                        print("🔓 FALLBACK RELEASE - No tracking data")
                    else:
                        windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        is_holding_click = True
                        print("🔒 FALLBACK HOLD - No tracking data")
                
                last_scan_time = current_time
                time.sleep(scan_delay)
            
            # Cleanup
            if is_holding_click:
                windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                print("✅ Final RELEASE")
            
            # Close visualization window
            try:
                if hasattr(self, '_debug_overlay') and self._debug_overlay:
                    self._debug_overlay.destroy()
                    self._debug_overlay = None
            except:
                pass

            if camera and not use_mss:
                camera.release()
                print("📷 DXCam camera released")
            elif use_mss and mss_instance:
                mss_instance.close()
                print("📷 MSS instance closed")

            # Close cast visualization overlays at end of fish stage
            self._cleanup_cast_overlays()

            print("✅ === FISH STAGE ENDED ===")
            return "restart"  # Return to main loop
            
        except Exception as e:
            print(f"❌ Error in fish stage: {e}")
            import traceback
            traceback.print_exc()
            
            # Cleanup on error
            if 'is_holding_click' in locals() and is_holding_click:
                windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

            if 'camera' in locals() and camera and not use_mss:
                try:
                    camera.release()
                except:
                    pass
            elif 'mss_instance' in locals() and mss_instance:
                try:
                    mss_instance.close()
                except:
                    pass
            return "restart"