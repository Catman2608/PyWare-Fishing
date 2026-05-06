    def _perform_perfect_cast_release_prediction(self):
        """
        Time-based prediction with 11 velocity bands.
        Releases when time_to_impact <= reaction_delay (varies by velocity band).
        
        This uses velocity tracking to predict when the white marker will reach green,
        and releases with adaptive timing based on velocity bands (11 speed ranges).
        """
        print("    ⚡ Prediction (Time-Based) Release: Starting detection...")
        
        # Get settings
        green_tolerance = self.settings.get("perfect_cast_green_color_tolerance", 10)
        white_tolerance = self.settings.get("perfect_cast_white_color_tolerance", 10)
        fail_timeout = self.settings.get("perfect_cast_fail_scan_timeout", 3.0)
        
        # Get timing adjustments for each velocity band
        timing_very_slow = self.settings.get("perfect_cast_very_slow_timing", 0)
        timing_slow = self.settings.get("perfect_cast_slow_timing", 0)
        timing_walking = self.settings.get("perfect_cast_walking_timing", 0)
        timing_jogging = self.settings.get("perfect_cast_jogging_timing", 0)
        timing_running = self.settings.get("perfect_cast_running_timing", 0)
        timing_cycling = self.settings.get("perfect_cast_cycling_timing", 0)
        timing_motorcycle = self.settings.get("perfect_cast_motorcycle_timing", 0)
        timing_driving = self.settings.get("perfect_cast_driving_timing", 0)
        timing_flying = self.settings.get("perfect_cast_flying_timing", 0)
        timing_rocket = self.settings.get("perfect_cast_rocket_timing", 0)
        timing_lightning = self.settings.get("perfect_cast_lightning_timing", 0)
        
        # Setup capture region - use same as regular shake detection
        shake_area = self.shake_box
        if shake_area is None:
            print("    ❌ Failed to get shake detection area")
            windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return
        
        y1, x1, y2, x2 = shake_area['y1'], shake_area['x1'], shake_area['y2'], shake_area['x2']
        region = (x1, y1, x2, y2)
        
        # Initialize camera
        use_dxcam = DXCAM_AVAILABLE and self.settings.get("capture_mode", "MSS") == "DXCam"
        camera = None
        if use_dxcam:
            try:
                import dxcam
                camera = dxcam.create(output_color="BGR")
                if camera is None:
                    use_dxcam = False
            except Exception as e:
                print(f"⚠️ DXCAM initialization failed: {e}")
                use_dxcam = False
        
        # Tracking state
        white_positions = []
        timestamps = []
        last_time_to_impact = None
        is_tracking = False
        last_midpoint_x = None
        last_green_y = None
        frames_since_lost = 0
        tracking_box_size = 100
        
        # Calculate scaling factor based on resolution
        reference_height = 1440
        actual_height = y2 - y1
        scaling_factor = actual_height / reference_height
        
        # Minimum distance threshold (scaled)
        minimum_distance = 30 * scaling_factor
        
        frame_count = 0
        scan_time_start = time.time()
        
        print(f"    📊 Output format: F#frame | time_ms | MODE | Distance_pixels")
        
        while True:
            frame_start_time = time.time()
            current_time = time.time()
            elapsed_time = current_time - scan_time_start
            
            # Check for timeout
            if elapsed_time >= fail_timeout:
                print(f"    ⏰ TIMEOUT REACHED ({fail_timeout}s) - Releasing left click")
                windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                break
            
            # Check if bot has been stopped
            if not self.global_hotkey_states["Start/Stop"] or self.is_quitting:
                print("    🛑 Bot stopped during perfect cast release")
                windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                break
            
            frame_count += 1
            
            # Capture frame
            frame = None
            if use_dxcam and camera:
                frame = camera.grab(region=region)
            else:
                try:
                    with mss.mss() as sct:
                        mss_monitor = {"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1}
                        screenshot = sct.grab(mss_monitor)
                        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
                except Exception as e:
                    continue
            
            if frame is None:
                continue
            
            # STEP 1: GREEN DETECTION
            green_midpoint_result = None
            
            if is_tracking and last_midpoint_x is not None and last_green_y is not None:
                green_midpoint_result = find_green_tracking_box(
                    frame, last_midpoint_x, last_green_y, GREEN_BGR, green_tolerance, tracking_box_size
                )
                if green_midpoint_result is not None:
                    frames_since_lost = 0
                else:
                    frames_since_lost += 1
                    if frames_since_lost >= 3:
                        is_tracking = False
                        frames_since_lost = 0
            
            if not is_tracking or green_midpoint_result is None:
                green_midpoint_result = find_green_full_scan(frame, GREEN_BGR, green_tolerance)
                if green_midpoint_result is not None:
                    is_tracking = True
                    frames_since_lost = 0
            
            # STEP 2: WHITE DETECTION
            white_result = None
            green_left_x = None
            green_right_x = None
            green_width = None
            local_distance = 0
            
            if green_midpoint_result is not None:
                local_midpoint_x, local_green_y, green_left_x, green_right_x = green_midpoint_result
                
                # Calculate green width
                green_width = green_right_x - green_left_x
                
                last_midpoint_x = local_midpoint_x
                last_green_y = local_green_y
                
                white_result = find_white_below_green(frame, local_green_y, green_left_x, green_right_x, white_tolerance)
                if white_result is not None:
                    local_white_x, local_white_y = white_result
                    white_x = x1 + local_white_x
                    white_y = y1 + local_white_y
                    
                    local_distance = abs(local_white_y - local_green_y)
                    
                    # Print status
                    if frame_count % 10 == 0:
                        mode_text = "TRACK" if is_tracking else "FULL"
                        scan_duration = (current_time - scan_time_start) * 1000
                        print(f"    Completed: F#{frame_count} | {scan_duration:.1f}ms | {mode_text} | Dist:{local_distance}")
                    
                    # Store position for velocity tracking
                    white_positions.append((white_x, white_y))
                    timestamps.append(current_time)
                    
                    if len(white_positions) > 5:
                        white_positions.pop(0)
                        timestamps.pop(0)
                    
                    # Initialize prediction_info for visualization
                    prediction_info = None
                    
                    # VELOCITY-BASED PREDICTION
                    if len(white_positions) >= 3:
                        velocity_y = calculate_speed_and_predict(white_positions, timestamps)
                        
                        min_speed_threshold = 5 * scaling_factor
                        if velocity_y is not None:
                            velocity_magnitude = abs(velocity_y)
                            if velocity_magnitude > min_speed_threshold:
                                white_above_green = local_white_y < local_green_y
                                moving_toward_green = (white_above_green and velocity_y > 0) or (not white_above_green and velocity_y < 0)
                                
                                if moving_toward_green:
                                    time_to_impact = local_distance / velocity_magnitude
                                
                                # Define velocity bands (scaled to resolution)
                                v700 = 700 * scaling_factor
                                v800 = 800 * scaling_factor
                                v900 = 900 * scaling_factor
                                v1000 = 1000 * scaling_factor
                                v1100 = 1100 * scaling_factor
                                v1200 = 1200 * scaling_factor
                                v1300 = 1300 * scaling_factor
                                v1400 = 1400 * scaling_factor
                                v1500 = 1500 * scaling_factor
                                v1600 = 1600 * scaling_factor
                                
                                # Determine reaction delay based on velocity band
                                if velocity_magnitude < v700:
                                    reaction_delay = 0.060
                                    user_adjustment = timing_very_slow * 0.001
                                elif velocity_magnitude < v800:
                                    reaction_delay = 0.058
                                    user_adjustment = timing_slow * 0.001
                                elif velocity_magnitude < v900:
                                    reaction_delay = 0.057
                                    user_adjustment = timing_walking * 0.001
                                elif velocity_magnitude < v1000:
                                    reaction_delay = 0.056
                                    user_adjustment = timing_jogging * 0.001
                                elif velocity_magnitude < v1100:
                                    reaction_delay = 0.055
                                    user_adjustment = timing_running * 0.001
                                elif velocity_magnitude < v1200:
                                    reaction_delay = 0.050
                                    user_adjustment = timing_cycling * 0.001
                                elif velocity_magnitude < v1300:
                                    reaction_delay = 0.048
                                    user_adjustment = timing_motorcycle * 0.001
                                elif velocity_magnitude < v1400:
                                    reaction_delay = 0.047
                                    user_adjustment = timing_driving * 0.001
                                elif velocity_magnitude < v1500:
                                    reaction_delay = 0.046
                                    user_adjustment = timing_flying * 0.001
                                elif velocity_magnitude < v1600:
                                    reaction_delay = 0.050
                                    user_adjustment = timing_rocket * 0.001
                                else:
                                    reaction_delay = 0.049
                                    user_adjustment = timing_lightning * 0.001
                                
                                adjusted_reaction_delay = reaction_delay + user_adjustment
                                
                                # Build prediction info for visualization
                                prediction_info = {
                                    'distance': local_distance,
                                    'velocity': velocity_magnitude,
                                    'time_to_impact': time_to_impact * 1000,  # Convert to ms
                                    'release_timing': adjusted_reaction_delay * 1000  # Convert to ms
                                }
                    
                    # VISUALIZATION - Show green and white positions (without prediction info during loop)
                    if self.global_gui_settings.get("Show Perfect Cast Overlay", True):
                        self._show_cast_visualization(
                            shake_area, local_midpoint_x, local_green_y,
                            local_white_y,  # Updated every scan when white detected
                            y2 - y1,  # Frame height
                            green_width,  # Width of detected green
                            None  # Don't show prediction info during loop (only at release)
                        )
                    
                    # Continue with velocity-based prediction logic
                    if prediction_info is not None:
                                
                                # RELEASE CONDITION
                                if time_to_impact <= adjusted_reaction_delay:
                                    print(f"    🎯 PREDICTIVE RELEASE!")
                                    print(f"       Distance: {local_distance}px")
                                    print(f"       Velocity: {velocity_magnitude:.1f}px/s")
                                    print(f"       Time to impact: {time_to_impact*1000:.1f}ms")
                                    print(f"       Release timing: {adjusted_reaction_delay*1000:.1f}ms")
                                    
                                    # Show final prediction info overlay at release
                                    if self.global_gui_settings.get("Show Perfect Cast Overlay", True):
                                        self._show_cast_visualization(
                                            shake_area, local_midpoint_x, local_green_y,
                                            local_white_y,
                                            y2 - y1,
                                            green_width,
                                            prediction_info  # Show prediction info at release
                                        )
                                    
                                    windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                                    print("    Completed: PERFECT CAST COMPLETE")
                                    break
                                
                                last_time_to_impact = time_to_impact
                    
                    # SLOW SPEED FALLBACK
                    if len(white_positions) >= 3:
                        slow_speed_threshold = minimum_distance * 0.8
                        if local_distance <= slow_speed_threshold:
                            recent_distances = []
                            for i in range(-3, 0):
                                pos, _ = white_positions[i]
                                dist = abs(pos[1] - (y1 + local_green_y))
                                recent_distances.append(dist)
                            
                            if recent_distances[-1] < recent_distances[0]:
                                print(f"    🎯 SLOW SPEED RELEASE! Distance: {local_distance}px")
                                windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                                print("    Completed: PERFECT CAST COMPLETE (slow speed)")
                                break
                    
                    # EMERGENCY RELEASE
                    emergency_distance = minimum_distance * 0.5
                    if local_distance <= emergency_distance:
                        print(f"    🚨 EMERGENCY RELEASE! Distance: {local_distance}px")
                        windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        print("    Completed: PERFECT CAST COMPLETE (emergency)")
                        break