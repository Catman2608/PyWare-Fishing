import time
import Quartz
def _move_mouse(x, y):
    # Expects logical points (already converted by the caller).
    # CGWarpMouseCursorPosition works in logical coordinate space.
    point = Quartz.CGPointMake(x, y)
    Quartz.CGWarpMouseCursorPosition(point)
    Quartz.CGAssociateMouseAndMouseCursorPosition(True)
class Api:
    def __init__(self):
        super().__init__()
    def _run_auto_angler_loop(self):
        cycle_interval_s = 125.0

        while self.macro_running:
            s = self._get_settings_snapshot()
            fish_geom = str(getattr(s, "auto_angler_quest_fish_geom", "") or "").strip()
            job_point = self.vars["auto_angler_job_point"]
            search_point = self.vars["auto_angler_search_point"]
            inventory_point = self.vars["auto_angler_inventory_point"]
            click_delay_s = max(0.0, float(getattr(s, "auto_angler_sequence_delay_s", 0.20)))
            if (not fish_geom) or (job_point is None) or (search_point is None) or (inventory_point is None):
                print("Auto Angler: incomplete setup")
                return

            self._force_release_input()
            if self.macro_running == False:
                return
            print("Auto Angler: pressing E")
            self._send_key("e")
            if time.sleep(click_delay_s):
                return
            print("Auto Angler: clicking job")
            _move_mouse(job_point[0], job_point[1])
            self._click_at(job_point[0], job_point[1], clicks=1, interval=0.0)
            if time.sleep(click_delay_s):
                return
            print("Auto Angler: OCR fish")
            fish_name = self._scan_auto_angler_fish_name(fish_geom)
            if self.macro_running == False:
                return
            if not fish_name:
                print("Auto Angler: OCR failed")
                return
            print(f"Auto Angler: {fish_name}")
            self._send_key("g")
            if time.sleep(click_delay_s):
                return
            print("Auto Angler: opening search")
            _move_mouse(search_point[0], search_point[1])
            self._click_at(search_point[0], search_point[1], clicks=3, interval=min(0.25, max(0.03, click_delay_s * 0.35 if click_delay_s > 0 else 0.06)))
            if time.sleep(click_delay_s):
                return
            self._type_text_fast(fish_name)
            if time.sleep(click_delay_s):
                return
            print("Auto Angler: selecting fish")
            _move_mouse(inventory_point[0], inventory_point[1])
            self._click_at(inventory_point[0], inventory_point[1], clicks=1, interval=0.0)
            if time.sleep(click_delay_s):
                return
            self._send_key("g")
            if time.sleep(click_delay_s):
                return
            self._send_key("e")
            if time.sleep(click_delay_s):
                return
            print("Auto Angler: closing job")
            _move_mouse(job_point[0], job_point[1])
            self._click_at(job_point[0], job_point[1], clicks=1, interval=0.0)

            print(f"Auto Angler: waiting {cycle_interval_s:.0f}s")
            if time.sleep(cycle_interval_s):
                return
if __name__ == "__main__":
    app = Api()
    app.mainloop()