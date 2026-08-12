            # Step 5: Determine which pixel to use for each note based on availability
            left_pixel = shake_left_pixel[1] if shake_left_pixel is not None else shake_top
            right_pixel = shake_right_pixel[1] if shake_right_pixel is not None else shake_top
            arrow_pixel = shake_arrow_pixel[1] if shake_arrow_pixel is not None else shake_top
            fish_pixel = shake_fish_pixel[1] if shake_fish_pixel is not None else shake_top
            # Step 6: Convert to ratios using total_height (fish_bottom - shake_top)
            total_height = fish_bottom - shake_top
            left_ratio = left_pixel / total_height if not left_pixel == None else 0
            right_ratio = right_pixel / total_height if not right_pixel == None else 0
            arrow_ratio = arrow_pixel / total_height if not arrow_pixel == None else 0
            fish_ratio = fish_pixel / total_height if not fish_pixel == None else 0
            # Step 7: Draw
            # You'll need to adjust the drawing logic based on which pixel was used
            # This is a placeholder - you may want to draw both or the active one
            overlay_center_x = fish_height / 2
            note_height = 0.1
            for ratio, color in (
                (left_ratio, left_color),
                (right_ratio, right_color),
                (arrow_ratio, arrow_color),
                (fish_ratio, fish_color),
            ):
                if ratio is None:
                    continue
                self.fish_overlay.draw(
                    bar_center=overlay_center_x,
                    box_size=fish_height * 0.8,
                    color=color,
                    canvas_offset=0,
                    show_bar_center=False,
                    bar_y1=max(0.0, ratio - note_height / 2),
                    bar_y2=min(1.0, ratio + note_height / 2)
                )
            # Step 8: Compare note ratios to user given target (based on tranquility mode)
            if tranquility_mode == "Steady" or tranquility_mode == "steady":
                if left_ratio is not None and left_ratio > target:
                    time.sleep(target_delay)
                    self._send_key(tranquility_key_1, 0.03, 1)
                else:
                    self._send_key(tranquility_key_1, 0.03, 2)
                if right_ratio is not None and right_ratio > target:
                    time.sleep(target_delay)
                    self._send_key(tranquility_key_2, 0.03, 1)
                else:
                    self._send_key(tranquility_key_2, 0.03, 2)
                if arrow_ratio is not None and arrow_ratio > target:
                    time.sleep(target_delay)
                    self._send_key(tranquility_key_3, 0.03, 1)
                else:
                    self._send_key(tranquility_key_3, 0.03, 2)
                if fish_ratio is not None and fish_ratio > target:
                    time.sleep(target_delay)
                    self._send_key(tranquility_key_4, 0.03, 1)
                else:
                    self._send_key(tranquility_key_4, 0.03, 2)
            elif tranquility_mode == "Rapid" or tranquility_mode == "rapid":
                if left_ratio is not None and left_ratio > target:
                    time.sleep(target_delay)
                    self._send_key(tranquility_key_1)
                if right_ratio is not None and right_ratio > target:
                    time.sleep(target_delay)
                    self._send_key(tranquility_key_2)
                if arrow_ratio is not None and arrow_ratio > target:
                    time.sleep(target_delay)
                    self._send_key(tranquility_key_3)
                if fish_ratio is not None and fish_ratio > target:
                    time.sleep(target_delay)
                    self._send_key(tranquility_key_4)
            time.sleep(scan_delay)