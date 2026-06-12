import cv2
import time
import pytesseract
class Api:
    def __init__(self):
        super().__init__()
    def start_appraisal(self):
        self._stop_active_capture()
        self.macro_running = True
        dialogue_left, dialogue_top, dialogue_right, dialogue_bottom, dialogue_width, dialogue_height = self._get_areas("shake")
        hotbar_left, hotbar_top, hotbar_right, hotbar_bottom, _, _ = self._get_areas("fish")
        tesseract_path = self.vars["tesseract_path"]
        mutation_enchant = self.vars["mutation_enchant"]
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        tolerance = int(self.vars["shake_tolerance"])
        shake_pixel = self.vars["shake_color"]
        appraisal_mode = self.vars["appraisal_enchant_mode"].capitalize()
        appraisal_x_ratio = self.vars["appraisal_enchant_x"]
        appraisal_y_ratio = self.vars["appraisal_enchant_y"]
        appraisal_x = int(dialogue_width * appraisal_x_ratio) + dialogue_left
        appraisal_y = int(dialogue_height * appraisal_y_ratio) + dialogue_top
        # Check for utilities
        self._check_logging_trigger(-1)
        # Main loop
        time.sleep(0.1)
        self._send_key("e", 0.05)
        while self.macro_running:
            for i in range(2):
                time.sleep(1.2)
                img = self._grab_screen_full()
                shake = img[dialogue_top:dialogue_bottom, dialogue_left:dialogue_right]
                fish = img[hotbar_top:hotbar_bottom, hotbar_left:hotbar_right]
                if appraisal_mode == "Search":
                    dialogue = self._find_first_pixel(shake, shake_pixel, tolerance)
                    try:
                        if dialogue is None:
                            continue
                        dialogue_x, dialogue_y = dialogue
                        # Convert cropped coordinates back to screen coordinates
                        screen_x = dialogue_left + dialogue_x
                        screen_y = dialogue_top + dialogue_y
                        self._click_at(screen_x, screen_y)
                        time.sleep(1.2)
                    except Exception as e:
                        self.set_status(e)
                        self.stop_macro(f"Appraisal failed: {e}")
                else:
                    self._click_at(appraisal_x, appraisal_y)
            gray = cv2.cvtColor(fish, cv2.COLOR_BGR2GRAY)
            # Upscale image
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            # Sharpen contrast
            gray = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]
            text = pytesseract.image_to_string(gray)
            if mutation_enchant.lower() in text.lower():
                self.stop_macro("Appraisal finished")
if __name__ == "__main__":
    app = Api()
    app.mainloop()