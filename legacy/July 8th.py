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
class App:
    def _enter_minigame(self):
        # Areas
        shake_left, shake_top, shake_right, shake_bottom, _, _ = self._get_areas("shake")
        fish_left, fish_top, fish_right, fish_bottom, fish_width, _ = self._get_areas("fish")
        friend_left, friend_top, friend_right, friend_bottom, _, _ = self._get_areas("friend")
        # Fishing Colors
        left_bar_hex = self.vars["left_color"]
        right_bar_hex = self.vars["right_color"]
        arrow_hex = self.vars["arrow_color"]
        fish_hex = self.vars["fish_color"]
        try: # Handle Nonetype and int properly
            left_tol = int(self.vars["left_tolerance"] or 8)
            right_tol = int(self.vars["right_tolerance"] or 8)
            arrow_tol = int(self.vars["arrow_tolerance"] or 8)
            fish_tol = int(self.vars["fish_tolerance"] or 4)
        except:
            left_tol = 8
            right_tol = 8
            arrow_tol = 8
            fish_tol = 4
        # Utility Colors
        friend_color = self.vars["friends_color"]
        friend_tol = int(self.vars["friends_tolerance"])
        note_box_hex = self.vars["tracking_color"]
        note_box_tol = self._get_var_number("tracking_tolerance", 8)
        # Minigame Settings
        bar_ratio = float(self.vars["bar_ratio_from_side"] or 0.5)
        restart_delay = float(self.vars["restart_delay"])
        scan_delay = float(self.vars["minigame_scan_delay"] or 0.05)
        fishing_profile = self.vars["fishing_profile"].lower()
        lock_cursor = (self.vars["lock_cursor"])
        minigame_controller_mode = self.vars["controller_mode"].lower()
        note_track_ratio = float(self.vars["pinion_note_ratio"])
        lullaby_metronome_ratio = float(self.vars["lullaby_metronome_ratio"])
        lullaby_fishing_ratio = float(self.vars["lullaby_fishing_ratio"])
        fishing_mode = self.vars["fishing_mode"].lower()
        # Other Settings
        catch_success = True
        shake_x = int((shake_left + shake_right) / 2)
        shake_y = int((shake_top + shake_bottom) / 2)
        fish_area_center = int((fish_right - fish_left) / 2) + fish_left
        scale = self._get_scale_factor()
        deadzone_action = 0
        canvas_offset = 0
        self._reset_pid_state()
        mouse_down = False
        self._set_fish_overlay_mode("fishing")
        # Helper Functions
        def hold_mouse(mouse_state=False):
            "Hold mouse. False for left click, True for right click."
            nonlocal mouse_down
            if not mouse_down:
                self.hold_mouse(mouse_state)
                mouse_down = True
        def release_mouse(mouse_state=False):
            "Release mouse. False for left click, True for right click."
            nonlocal mouse_down
            if mouse_down:
                self.release_mouse(mouse_state)
                mouse_down = False
        # Minigame Loop (Start capture thread first)
        _minigame_stop = self._start_capture(scan_delay)
        while self.macro_running:
            # Step 1: Grab Full Screen and Crop Images
            if not self._cap_event.wait(timeout=0.5):
                continue

            with self._cap_lock:
                frame = self._cap_frame
                self._cap_consumed_id = self._cap_frame_id
                self._cap_event.clear()
            if frame is None:
                _minigame_stop.set()
                self._set_fish_overlay_mode("idle")
                return catch_success
            
            if self.macro_running == False:
                break

            if fishing_profile == "dual":
                # Fish images
                fish_img = frame[fish_top:fish_bottom, fish_left:fish_area_center]
                fish_img2 = frame[fish_top:fish_bottom, fish_area_center:fish_right]
                # Note images
                note_img = frame[shake_top:fish_bottom, fish_left:fish_area_center]
                note_img2 = frame[shake_top:fish_bottom, fish_area_center:fish_right]
                # Make sure to recalculate fish width
                fish_width = fish_area_center - fish_left
                fish_width2 = fish_right - fish_area_center
            elif fishing_profile == "metronome":
                lullaby_metronome_pos = int((fish_bottom - fish_top) * lullaby_metronome_ratio)
                lullaby_fishing_top = int((fish_bottom - fish_top) * lullaby_fishing_ratio)
                # 1 fish 1 metronome 1 note image
                fish_img = frame[lullaby_fishing_top:fish_bottom, fish_left:fish_right]
                metronome_img = frame[fish_top:lullaby_fishing_top, fish_left:fish_right]
                note_img = frame[shake_top:fish_bottom, fish_left:fish_right]
            else:
                # 1 fish and 1 note image
                fish_img = frame[fish_top:fish_bottom, fish_left:fish_right]
                note_img = frame[shake_top:fish_bottom, fish_left:fish_right]
            # Keep 1 friend image
            friend_img = frame[friend_top:friend_bottom, friend_left:friend_right]
            # Make sure to clear overlay before searching
            self.fish_overlay.clear()
            if lock_cursor == "on":
                mouse_controller.position = (shake_x, shake_y)
            # Step 2. Do pixel search
            # Left Side / Main Image
            if fishing_mode == "line":
                fish_pos_left, fish_pos_right, left_x, right_x = self._do_line_search(fish_img, fish_left, fish_right)
            else:
                fish_pos_left, fish_pos_right, left_x, right_x = self._do_pixel_search(fish_img, fish_hex, left_bar_hex, right_bar_hex, fish_tol, left_tol, right_tol)
            try:
                fish_x = int((fish_pos_left[0] + fish_pos_right[0]) / 2)
            except:
                fish_x = None
            # Middle Side / Metronome
            if fishing_profile == "metronome":
                left_metronome, _, _ = self._find_color_cluster(metronome_img, left_bar_hex, left_tol)
                right_metronome, _, _ = self._find_color_cluster(metronome_img, right_bar_hex, right_tol)
                target_metronome, _, _ = self._find_color_cluster(metronome_img, fish_hex, fish_tol)
                try:
                    target_metronome = target_metronome[0]
                    metronome_center_x = int((left_metronome[0] + right_metronome[0]) / 2)
                    metronome_center_y = int((left_metronome[1] + right_metronome[1]) / 2)
                except:
                    target_metronome = None
                    metronome_center_x = None
                    metronome_center_y = None
            # Right Side (Only Triggers If fishing_profile Is dual)
            # Dual Fishing: LEFT (primary) is strong, RIGHT (secondary) is basic controls (no overlay)
            if fishing_profile == "dual":
                if fishing_mode == "line":
                    fish_pos_left2, fish_pos_right2, left_x2, right_x2 = self._do_line_search(fish_img2, fish_area_center)
                else:
                    fish_pos_left2, fish_pos_right2, left_x2, right_x2 = self._do_pixel_search(fish_img2, fish_hex, left_bar_hex, right_bar_hex, fish_tol, left_tol, right_tol)
                try:
                    fish_x2 = int((fish_pos_left2[0] + fish_pos_right2[0]) / 2)
                except:
                    fish_x2 = None
                arrow_indicator_x2 = self._find_color_center(fish_img2, arrow_hex, arrow_tol)
            arrow_indicator_x = self._find_color_center(fish_img, arrow_hex, arrow_tol)
            if fishing_profile == "notes":
                note_coords = self._find_color_center(note_img, note_box_hex, note_box_tol)
            else:
                note_coords = None
            # Extract arrow x coordinate safely
            try:
                arrow_indicator_x = arrow_indicator_x[0]
                arrow_indicator_x2 = arrow_indicator_x2[0]
            except (TypeError, IndexError):
                arrow_indicator_x = None
                arrow_indicator_x2 = None
            # Step 3: Pre-restart calculations
            if fishing_profile == "dual":
                any_bar_detected_this_frame2 = left_x2 is not None and right_x2 is not None # Check 1 for normal mode
                bar_valid2 = True
                if any_bar_detected_this_frame2:
                    detection_source2 = 0
                else:
                    bar_center2, left_x2, right_x2 = self._update_arrow_box_estimation(arrow_indicator_x2, any_bar_detected_this_frame2, fish_width)
                    any_bar_detected_this_frame2 = True # Check 2
                    detection_source2 = 1
                if left_x2 is not None and right_x2 is not None:
                    # Both bars detected - validate and save positions
                    # Ensure left is never greater than right (swap if needed)
                    if left_x2 > right_x2:
                        left_x2, right_x2 = right_x2, left_x2

                    # Calculate current frame values (don't update memory yet - edge detection does that)
                    bar_center2 = (left_x2 + right_x2) / 2.0
                elif left_x2 is not None:
                    if left_x2 < right_x2:
                        bar_center2 = (left_x2 + right_x2) / 2.0
                    else:
                        bar_valid2 = False
                elif right_x2 is not None:
                    if right_x2 > left_x2:
                        bar_center2 = (left_x2 + right_x2) / 2.0
                    else:
                        bar_valid2 = False
                try: bar_size2 = right_x2 - left_x2
                except: bar_size2 = 0
            any_bar_detected_this_frame = left_x is not None and right_x is not None # Check 1 for normal mode
            bar_valid = True
            if any_bar_detected_this_frame:
                detection_source = 0
            else:
                bar_center, left_x, right_x = self._update_arrow_box_estimation(arrow_indicator_x, any_bar_detected_this_frame, fish_width)
                any_bar_detected_this_frame = True # Check 2
                detection_source = 1
            if left_x is not None and right_x is not None:
                # Both bars detected - validate and save positions
                # Ensure left is never greater than right (swap if needed)
                if left_x > right_x:
                    left_x, right_x = right_x, left_x

                # Calculate current frame values (don't update memory yet - edge detection does that)
                bar_center = (left_x + right_x) / 2.0
            elif left_x is not None:
                if left_x < right_x:
                    bar_center = (left_x + right_x) / 2.0
                else:
                    bar_valid = False
            elif right_x is not None:
                if right_x > left_x:
                    bar_center = (left_x + right_x) / 2.0
                else:
                    bar_valid = False
            try: bar_size = right_x - left_x
            except: bar_size = 0
            # Deadzone calculations
            if deadzone_action == 3:
                deadzone_action = 0
            else:
                deadzone_action = deadzone_action + 1
            # Thresh: 3 pixels (scaled with scale factor and screen width)
            thresh = 3 * scale * int(SCREEN_WIDTH / 1920)
            # Step 4: Restart and Cache (using Friend Area)
            friend_x = self._find_color_center(friend_img, friend_color, friend_tol)
            if friend_x is not None:
                release_mouse()
                time.sleep(restart_delay)
                self._set_fish_overlay_mode("idle")
                return catch_success
            # Validate positions and update cache
            if bar_valid == False:
                left_x = self.last_left_x if self.last_left_x is not None else 0
                right_x = self.last_right_x if self.last_right_x is not None else 0
                bar_center = (left_x + right_x) / 2.0
            if bar_valid == True:
                self.last_cached_box_length = bar_size
                self.estimated_box_length = bar_size
                self.last_left_x = left_x
                self.last_right_x = right_x
                self.last_bar_size = bar_size
                self.last_bar_center_x = (left_x + right_x) / 2.0 if left_x is not None and right_x is not None else 0
            fish_valid = True
            if fish_x is None:
                fish_valid = False
            if fish_valid == False:
                fish_x = self.last_fish_x if self.last_fish_x is not None else 0
            if fish_valid == True:
                self.last_fish_x = fish_x if fish_x is not None else 0
            # Step 5: Lullaby-style minigame
            # METRONOME RHYTHM MODE (Lullaby-style minigame)
            # The metronome_img (upper slice of the fish area) contains:
            #   - A moving "metronome" indicator (fish_color cluster) → target_metronome (x)
            #   - 1-3 clickable "beat areas" defined by left_bar_hex / right_bar_hex clusters
            #     whose center is computed as metronome_center_x/y
            # Rule: ONLY click (short tap) when target_metronome is touching a beat area.
            #       Clicking at the wrong time = instant fish loss.
            # Therefore we completely bypass the normal bar-control hold/release logic.
            if fishing_profile == "metronome":
                did_click = False
                if target_metronome is not None and metronome_center_x is not None:
                    distance = abs(target_metronome - metronome_center_x)
                    # Tolerance for "touches" — scaled to resolution. 25-35 px typical at 1440p.
                    touch_tol = max(8, int(28 * scale))
                    if distance <= touch_tol:
                        # Clean short tap — never hold across frames
                        release_mouse()
                        time.sleep(0.006)
                        hold_mouse()
                        time.sleep(0.032)   # short press so Roblox registers a click
                        release_mouse()
                        did_click = True
                        self.set_status(f"Metronome hit ✓  dist={distance:.0f}")
                    else:
                        # Not aligned → must stay released
                        release_mouse()
                else:
                    # No valid detection → stay safe (released)
                    release_mouse()
                time.sleep(scan_delay)
                continue   # skip all normal controller / overlay / dual logic

            # Step 6: Check controller mode condition and calculate boundaries
            if any_bar_detected_this_frame and bar_center is not None: # Bar Found
                if note_coords is not None:
                    # Direct Mapping (Already In Fish Space)
                    note_screen_x = note_coords[0]
                    note_screen_y = note_coords[1]
                    note_screen_y_ratio = note_screen_y / (fish_bottom - fish_top)
                    overlay_fish_color = "#ff9c00"
                else:
                    overlay_fish_color = "#ff0000"
                    note_screen_x = None
                if note_coords is not None and fishing_profile == "notes":
                    if note_screen_y_ratio >= note_track_ratio:
                        fish_x = note_screen_x
                elif not fishing_profile == "notes":
                    pass
                
                # Boundary Calculations
                if fishing_mode == "dual":
                    boundary_bar_size = int(bar_size * bar_ratio)
                    max_left = boundary_bar_size
                    max_right = (fish_area_center - fish_left) - boundary_bar_size
                    boundary_bar_size2 = int(bar_size2 * bar_ratio)
                    max_left2 = boundary_bar_size2
                    max_right2 = (fish_right - fish_area_center) - boundary_bar_size2
                else:
                    boundary_bar_size = int(bar_size * bar_ratio)
                    max_left = boundary_bar_size
                    max_right = (fish_right - fish_left) - boundary_bar_size
                # Important: Bar left and right check is moved below the calculation
                try:
                    if not left_x <= fish_x <= right_x:
                        catch_success = False
                except:
                    pass

            # Step 7: Controller mode selection
            controller_mode = 0
            if bar_center is not None and fish_x is not None:
                if max_left is not None and fish_x <= max_left:
                    controller_mode = 4
                elif max_right is not None and fish_x >= max_right:
                    controller_mode = 3
                else:
                    if minigame_controller_mode == "steady":
                        controller_mode = 0
                    elif minigame_controller_mode == "normal":
                        controller_mode = 1
                    elif minigame_controller_mode == "predictive":
                        controller_mode = 5
                    if fishing_profile == "notes" and fish_x is not None:
                        if not (left_x <= fish_x <= right_x):
                            controller_mode = 2
            controller_mode2 = 0
            try:
                if bar_center2 is not None and fish_x2 is not None:
                    if minigame_controller_mode == "steady":
                        controller_mode2 = 0
                    elif minigame_controller_mode == "normal":
                        controller_mode2 = 1
                    elif minigame_controller_mode == "predictive":
                        controller_mode2 = 5
                    if fishing_profile == "notes" and fish_x2 is not None:
                        if not (left_x2 <= fish_x2 <= right_x2):
                            controller_mode2 = 2
            except:
                controller_mode2 = 0
            # Step 8: Draw overlay if enabled
            if fishing_profile == "dual":
                canvas_offset2 = 0 - abs(fish_area_center - fish_left)
                if self._is_fish_overlay_enabled() and bar_center is not None:
                    self.fish_overlay.draw(
                        bar_center=bar_center2, box_size=bar_size2,
                        color="green", canvas_offset=canvas_offset2,
                        show_bar_center=True
                    )
                    if max_left is not None:
                        self.fish_overlay.draw(
                            bar_center=max_left2, box_size=15,
                            color="lightblue", canvas_offset=canvas_offset2
                        )
                    if max_right is not None:
                        self.fish_overlay.draw(
                            bar_center=max_right2, box_size=15,
                            color="lightblue", canvas_offset=canvas_offset2
                        )
                    try:
                        fish_pos_size2 = int((fish_pos_right2[0] - fish_pos_left2[0]) * 2)
                    except:
                        fish_pos_size2 = 10
                    if fish_x is not None:
                        self.fish_overlay.draw(
                            bar_center=fish_x2, box_size=fish_pos_size2,
                            color=overlay_fish_color, canvas_offset=canvas_offset2
                        )
            if self._is_fish_overlay_enabled() and bar_center is not None:
                self.fish_overlay.draw(
                    bar_center=bar_center, box_size=bar_size,
                    color="green", canvas_offset=canvas_offset,
                    show_bar_center=True
                )
                if max_left is not None:
                    self.fish_overlay.draw(
                        bar_center=max_left, box_size=15,
                        color="lightblue", canvas_offset=canvas_offset
                    )
                if max_right is not None:
                    self.fish_overlay.draw(
                        bar_center=max_right, box_size=15,
                        color="lightblue", canvas_offset=canvas_offset
                    )
                try:
                    fish_pos_size = int((fish_pos_right[0] - fish_pos_left[0]) * 2)
                except:
                    fish_pos_size = 10
                if fish_x is not None:
                    self.fish_overlay.draw(
                        bar_center=fish_x, box_size=fish_pos_size,
                        color=overlay_fish_color, canvas_offset=canvas_offset
                    )
            # Step 9: Controller logic
            controller_found = 1
            controller_found2 = 1
            if fishing_profile == "dual" and bar_center2 is not None and fish_x2 is not None:
                controller_found2 = 1
                error2 = fish_x2 - bar_center2
                if controller_mode2 == 0 or controller_mode2 == 1:
                    control2 = self._steady_control(error2, bar_center2, True)
                    controller_found2 = 0
                elif controller_mode2 == 5:
                    should_hold = self._predictive_control(fish_x2, bar_center2, True)
                    if should_hold:
                        hold_mouse(True)
                    else:
                        release_mouse(True)
                    controller_found = 1
                elif controller_mode2 == 2:
                    control2 = error2
                    controller_found2 = 0
                elif controller_mode2 == 3:
                    hold_mouse(True)
                    controller_found2 = 1
                elif controller_mode2 == 4:
                    release_mouse(True)
                    controller_found2 = 1
            if bar_center is not None and fish_x is not None:
                error = fish_x - bar_center
                # Execute controller action
                if controller_mode == 0:  # PID (Steady)
                    control = self._steady_control(error, bar_center)
                    # print("error: ", int(error), "control: ", int(control), "mouse_down: ", mouse_down)
                    controller_found = 0
                elif controller_mode == 1:  # PID (Normal)
                    control = self._normal_control(error)
                    controller_found = 0
                elif controller_mode == 2:  # Simple Tracking
                    control = error
                    controller_found = 0
                elif controller_mode == 3:  # Force hold
                    hold_mouse()
                    controller_found = 1
                elif controller_mode == 4:  # Force release
                    release_mouse()
                    controller_found = 1
                elif controller_mode == 5:  # Predictive control
                    should_hold = self._predictive_control(fish_x, bar_center)
                    if should_hold:
                        hold_mouse()
                    else:
                        release_mouse()
                    controller_found = 1
            if controller_found == 0:
                if -thresh <= control <= thresh:
                    release_mouse() if deadzone_action == 0 else hold_mouse()
                elif control > thresh:
                    hold_mouse()
                elif control < -thresh:
                    release_mouse()
            if fishing_profile == "dual" and controller_found2 == 0:
                if -thresh <= control2 <= thresh:
                    release_mouse(True) if deadzone_action == 0 else hold_mouse(True)
                elif control2 > thresh:
                    hold_mouse(True)
                elif control2 < -thresh:
                    release_mouse(True)
            time.sleep(scan_delay)
        # If macro is not running, stop here
        release_mouse()
        time.sleep(restart_delay)
        self._set_fish_overlay_mode("idle")
        return True