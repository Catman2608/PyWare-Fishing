                            # Select control algorithm based on mode
                            if control_mode in ["Normal", "Steady"]:
                                # NORMAL/STEADY MODE: PD control with asymmetric damping
                                # P term - proportional to how far we need to move
                                p_term = kp * error
                            
                                # D term - ASYMMETRIC damping based on situation
                                d_term = 0.0
                                time_delta = current_time - last_scan_time
                                if last_target_x is not None and last_error is not None and time_delta > 0.001:
                                    # Calculate bar velocity (how fast bar is moving)
                                    last_bar_x = last_target_x - last_error
                                    bar_velocity = (bar_middle_x - last_bar_x) / time_delta
                                    
                                    # Determine if we're approaching or chasing
                                    error_magnitude_decreasing = abs(error) < abs(last_error)
                                    
                                    # Check if bar is moving toward target
                                    bar_moving_toward_target = (bar_velocity > 0 and error > 0) or (bar_velocity < 0 and error < 0)
                                    
                                    if error_magnitude_decreasing and bar_moving_toward_target:
                                        # APPROACHING TARGET - Strong damping to prevent overshoot (2x instead of 5x)
                                        damping_multiplier = 2.0
                                        d_term = -kd * damping_multiplier * bar_velocity
                                    else:
                                        # CHASING TARGET - Minimal damping to allow fast movement (0.5x instead of 0.2x)
                                        damping_multiplier = 0.5
                                        d_term = -kd * damping_multiplier * bar_velocity
                                
                                # Combined control signal (PD controller output)
                                control_signal = p_term + d_term
                                control_signal = max(-pd_clamp, min(pd_clamp, control_signal))  # Clamp

                                # DIRECTIONAL DECISION: Convert continuous signal to binary hold/release
                                # Positive = need to move bar right = HOLD
                                # Negative = need to move bar left = RELEASE
                                # D term naturally prevents overshoot by opposing velocity
                                if control_signal > 0:
                                    should_hold = True
                                else:
                                    should_hold = False
                            
                            elif control_mode == "NigGamble":
                                # NIGGAMBLE MODE: (Clone of Normal for now - will be modified)
                                # P term - proportional to how far we need to move
                                p_term = kp * error
                                
                                # D term - ASYMMETRIC damping based on situation
                                d_term = 0.0
                                time_delta = current_time - last_scan_time
                                if last_target_x is not None and last_error is not None and time_delta > 0.001:
                                    # Calculate bar velocity (how fast bar is moving)
                                    last_bar_x = last_target_x - last_error
                                    bar_velocity = (bar_middle_x - last_bar_x) / time_delta
                                    
                                    # Determine if we're approaching or chasing
                                    error_magnitude_decreasing = abs(error) < abs(last_error)
                                    
                                    # Check if bar is moving toward target
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
                                # NIGGAMBLE MODE
                                p_term = kp * error
                                
                                d_term = 0.0
                                time_delta = current_time - last_scan_time
                                if last_target_x is not None and last_error is not None and time_delta > 0.001:
                                    last_bar_x = last_target_x - last_error
                                    bar_velocity = (bar_middle_x - last_bar_x) / time_delta
                                    
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
                            last_target_x = target_middle_x
                            
                            # Update memory (normal zone - not at edge)
                            last_target_left_x = target_left_x
                            last_target_right_x = target_right_x
                            last_left_bar_x = left_bar_x
                            last_right_bar_x = right_bar_x