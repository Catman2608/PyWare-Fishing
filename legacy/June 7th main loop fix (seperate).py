import time
from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController
from pynput.mouse import Button
# Initialize Controllers
keyboard_controller = KeyboardController()
mouse_controller = MouseController()
macro_running = False
macro_thread = None
def start():
    def _enter_minigame(self):
        # Get All 3 Areas
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self._get_areas("shake")
        shake_x = int((shake_left + shake_right) / 2)
        shake_y = int((shake_top + shake_bottom) / 2)
        fish_left, fish_top, fish_right, fish_bottom, fish_width, _ = self._get_areas("fish")
        fish_area_center = int((fish_right - fish_left) / 2) + fish_left
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._get_areas("friend")
        self._reset_pid_state()
        mouse_down = False
        minigame_controller_mode = self.vars["controller_mode"].lower()
        controller_mode = 0
        catch_success = True
        self._pred_filtered_vel = 0.0
        scale = self._get_scale_factor()
        self._set_fish_overlay_mode("fishing")
        # Load Values From Gui
        arrow_hex = self.vars["arrow_color"]
        bar_ratio = float(self.vars["bar_ratio_from_side"] or 0.5)
        restart_delay = float(self.vars["restart_delay"])
        track_notes = self.vars["track_notes"]
        note_box_hex = self.vars["tracking_color"]
        note_track_ratio = float(self.vars["pinion_note_ratio"] or 0.1)
        scan_delay = float(self.vars["minigame_scan_delay"] or 0.05)
        lock_cursor = (self.vars["lock_cursor"])
        dual_fishing = (self.vars["dual_fishing"]).lower()
        fishing_mode = (self.vars["fishing_mode"])
        friend_color = self.vars["friends_color"]
        friend_tol = int(self.vars["friends_tolerance"])
        if fishing_mode == "Line":
            line_lost_timeout = restart_delay
            self._line_state = {
                'initial_target_gap': None,
                'last_target_left_x': None,
                'last_target_right_x': None,
                'last_left_bar_x': None,
                'last_right_bar_x': None,
                'is_initial_run': True
            }
        else:
            line_lost_timeout = 0.0
        try:
            note_box_tol = int(self.vars["tracking_tolerance"])
            arrow_tol = int(self.vars["arrow_tolerance"])
        except:
            note_box_tol = 8
            arrow_tol = 8
        self.last_bar_size = None
        self.scan_height_ratio = None
        self._last_should_hold = False
        self._last_input_time = 0
        deadzone_action = 0
        last_line_seen_time = time.perf_counter()
        # Hold And Release Mouse
        def hold_mouse(mouse_state=False):
            nonlocal mouse_down
            if not mouse_down:
                self.hold_mouse(mouse_state)
                mouse_down = True
        def release_mouse(mouse_state=False):
            nonlocal mouse_down
            if mouse_down:
                self.release_mouse(mouse_state)
                mouse_down = False
        # Start Screen Capture Thread (via _start_capture so it's tracked and
        # any previously running capture thread is stopped before this one begins)
        _minigame_stop = self._start_capture(scan_delay)
        while self.macro_running:
            # Step 1: Grab Full Screen Then Crop (better on macOS)
            if not self._cap_event.wait(timeout=0.5):
                continue
            with self._cap_lock:
                frame = self._cap_frame
                self._cap_consumed_id = self._cap_frame_id  # back-pressure release
                self._cap_event.clear()
            if frame is None:
                _minigame_stop.set()
                self._set_fish_overlay_mode("idle")
                return catch_success
            if dual_fishing == "on":
                fish_img = frame[fish_top:fish_bottom, fish_left:fish_area_center]
                fish_img2 = frame[fish_top:fish_bottom, fish_area_center:fish_right]
            else:
                fish_img = frame[fish_top:fish_bottom, fish_left:fish_right]
            note_img = frame[shake_top:fish_bottom, fish_left:fish_right]
            friend_img = frame[friend_top:friend_bottom, friend_left:friend_right]
            # cv2.imwrite("screenshot.png", frame)
            # Move lock cursor to step 5/7
            if lock_cursor == "on": # Lock cursor if enabled
                mouse_controller.position = (shake_x, shake_y)
            # Step 2: Detection
            # Right Side (Only Triggers If dual_fishing Is True)
            if dual_fishing == "on":
                if fishing_mode == "Line":
                    fish_x2, left_x2, right_x2 = self._do_line_search(fish_img2)
                else:
                    fish_x2, left_x2, right_x2 = self._do_pixel_search(fish_img2)
                arrow_indicator_x2 = self._find_first_pixel(fish_img2, arrow_hex, arrow_tol)
            # Left Side / Main Image
            if fishing_mode == "Line":
                fish_x, left_x, right_x = self._do_line_search(fish_img)
            else:
                fish_x, left_x, right_x = self._do_pixel_search(fish_img)
            arrow_indicator_x = self._find_first_pixel(fish_img, arrow_hex, arrow_tol)
            if track_notes == "on":
                note_coords = self._find_color_center(note_img, note_box_hex, note_box_tol)
            else:
                note_coords = None
            try:
                arrow_indicator_x = arrow_indicator_x[0]
            except:
                arrow_indicator_x = None
            # Convert Fish X From Tuple To Int
            if fish_x is None:
                pass
            elif isinstance(fish_x, (list, tuple)):
                fish_x = fish_x[0] + fish_left
            else:
                fish_x = fish_x + fish_left
            if fishing_mode == "Line":
                line_has_full_detection = fish_x is not None and left_x is not None and right_x is not None
                if line_has_full_detection:
                    last_line_seen_time = time.perf_counter()
                elif time.perf_counter() - last_line_seen_time <= line_lost_timeout:
                    if fish_x is None and self.last_fish_x is not None:
                        fish_x = self.last_fish_x
                    if (left_x is None or right_x is None) and self._last_bar_left_x is not None and self._last_bar_right_x is not None:
                        left_x = self._last_bar_left_x
                        right_x = self._last_bar_right_x
            # Step 3: Calculations
            self.fish_overlay.clear()
            any_bar_detected_this_frame = left_x is not None and right_x is not None # Check 1
            if any_bar_detected_this_frame:
                detection_source = 0
            else:
                bar_center, left_x, right_x = self._update_arrow_box_estimation(arrow_indicator_x, fish_width)
                any_bar_detected_this_frame = True # Check 2
                detection_source = 1
            if any_bar_detected_this_frame and not (left_x == None or right_x == None): # Bar Or Arrows Found
                bar_size = abs(right_x - left_x)
                bar_center = (left_x + bar_size / 2.0) + fish_left # Add Fish Left Here (float to preserve sub-pixel precision for velocity)
                left_deadzone = bar_size * bar_ratio
                right_deadzone = bar_size * bar_ratio
                max_left = fish_left + left_deadzone
                max_right = fish_right - right_deadzone
            else:
                bar_size = 0
                bar_center = None
                max_left = fish_left
                max_right = fish_right
            if deadzone_action == 3:
                deadzone_action = 0
            else:
                deadzone_action = deadzone_action + 1
            thresh = (1 - round((bar_size / fish_width), 2)) * 8 * scale
            # Step 4: Restart and Cache (using Friend Area)
            friend_x = self._find_color_center(friend_img, friend_color, friend_tol)
            if friend_x is not None:
                release_mouse()
                time.sleep(restart_delay)
                self._set_fish_overlay_mode("idle")
                return catch_success
            # Use cached coordinates if current detection is None or bar bounds are invalid
            bar_valid = True
            try:
                if abs(self._last_bar_left_x - left_x) > 100 or abs(self._last_bar_right_x - right_x) > 100:
                    bar_valid = False
            except:
                pass
            if left_x is None or right_x is None:
                bar_valid = False
            elif right_x <= left_x:
                bar_valid = False
            if bar_valid == False:
                left_x = self._last_bar_left_x if self._last_bar_left_x is not None else 0
                right_x = self._last_bar_right_x if self._last_bar_right_x is not None else 0
                bar_center = (left_x + right_x) / 2.0
            if bar_valid == True:
                self.last_cached_box_length = bar_size
                self.estimated_box_length = bar_size
                self._last_bar_left_x = left_x
                self._last_bar_right_x = right_x
                self._last_bar_box_size = bar_size
                self._last_bar_center = (left_x + right_x) / 2.0 if left_x is not None and right_x is not None else 0
            # Fish Direction-Jump Rejection
            fish_valid = True
            if (self.last_fish_x is not None and fish_x is not None):
                if abs(self.last_fish_x - fish_x) > 100:
                    fish_valid = False
            if fish_x is None:
                fish_x = self.last_fish_x if self.last_fish_x is not None else 0
            if fish_valid == False:
                fish_x = self.last_fish_x if self.last_fish_x is not None else 0
            if fish_valid == True:
                self.last_fish_x = fish_x if fish_x is not None else 0
            # Position Bar Based On State
            if not mouse_down:
                right_x = left_x + bar_size if not left_x == None else None
            else:
                left_x = right_x - bar_size if not right_x == None else None
            # Step 5: Check controller mode condition and convert everything to screen coordinates
            if any_bar_detected_this_frame and bar_center is not None: # Bar Found
                if note_coords is not None:
                    # Direct Mapping (Already In Fish Space)
                    note_screen_x = note_coords[0] + fish_left
                    note_screen_y = note_coords[1]
                    note_screen_y_ratio = note_screen_y / (fish_bottom - fish_top)
                else:
                    note_screen_x = None
                if note_coords is not None and track_notes == "on":
                    if note_screen_y_ratio >= note_track_ratio:
                        fish_x = note_screen_x
                elif track_notes == "off":
                    pass
                # Compute Bar Left And Bar Right (Screen Coords)
                bar_left_screen  = left_x  + fish_left if not left_x == None else None
                bar_right_screen = right_x + fish_left if not right_x == None else None
                # Important: Bar left and right check is moved below the calculation
                try:
                    if not bar_left_screen <= fish_x <= bar_right_screen:
                        catch_success = False
                except:
                    pass
                # Check Max Left And Max Right
                if fish_x == None:
                    fish_x = 0
                if max_left and fish_x <= max_left: # Max Left And Right Check (Inside Bar)
                    controller_mode = 4
                elif max_right and fish_x >= max_right:
                    controller_mode = 3
                else:
                    if bar_left_screen <= fish_x <= bar_right_screen:
                        if minigame_controller_mode == "steady":
                            controller_mode = 0
                        elif minigame_controller_mode == "normal":
                            controller_mode = 1
                        elif minigame_controller_mode == "predictive":
                            controller_mode = 5
                    else:
                        if track_notes == "on" or minigame_controller_mode == "predictive":
                            controller_mode = 2
            if self._is_fish_overlay_enabled():
                self.fish_overlay.draw(
                    bar_center=bar_center, box_size=bar_size,
                    color="green", canvas_offset=fish_left,
                    show_bar_center=True
                )
                self.fish_overlay.draw(
                    bar_center=max_left, box_size=15,
                    color="lightblue", canvas_offset=fish_left
                )
                self.fish_overlay.draw(
                    bar_center=max_right, box_size=15,
                    color="lightblue", canvas_offset=fish_left
                )
                self.fish_overlay.draw(
                    bar_center=fish_x, box_size=10,
                    color="red", canvas_offset=fish_left
                )
            # Step 7: Controller (Image coordinates)
            error = (fish_x - bar_center) if bar_center is not None and fish_x is not None else 0.0
            if controller_mode == 0 and bar_center is not None: # PID (Steady)
                control = self._steady_control(error, bar_center)
                # Map PID Output To Mouse Clicks Using Hysteresis To Avoid Jitter/Oscillation
                # Stabilize Deadzone Checker
                if -thresh <= error <= thresh:
                    if not deadzone_action == 0:
                        hold_mouse()
                    else:
                        release_mouse()
                elif control > thresh:
                    hold_mouse()
                elif control < -thresh:
                    release_mouse()
            elif controller_mode == 1 and bar_center is not None: # PID (Normal)
                control = self._normal_control(error)
                # Map PID Output To Mouse Clicks Using Hysteresis To Avoid Jitter/Oscillation
                # Stabilize Deadzone Checker
                if control > thresh:
                    hold_mouse()
                elif control < -thresh:
                    release_mouse()
                else:
                    if not deadzone_action == 0:
                        hold_mouse()
                    else:
                        release_mouse()
            elif controller_mode == 2 and bar_center is not None: # Simple Tracking
                control = fish_x - bar_center
                # Stabilize Deadzone Checker
                if control > thresh:
                    hold_mouse()
                elif control < -thresh:
                    release_mouse()
                else:
                    if not deadzone_action == 0:
                        hold_mouse()
                    else:
                        release_mouse()
            elif controller_mode == 3:
                hold_mouse()
            elif controller_mode == 4:
                release_mouse()
            elif controller_mode == 5 and bar_center is not None:
                should_hold = self._predictive_control(fish_x, bar_center, 
                                                    fish_left, fish_right, 
                                                    bar_left_screen, bar_right_screen)
                if should_hold:
                    hold_mouse()
                else:
                    release_mouse()
            time.sleep(scan_delay)