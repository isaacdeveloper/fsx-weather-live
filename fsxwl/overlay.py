"""Small always-on-top window showing the wind relative to the aircraft's nose.

It is a Tkinter window running on its own thread (every Tk call stays on that thread).
FSX must be in windowed mode (Alt+Enter) for any window to show on top of it.
Drag it with the left mouse button; right-click hides it (show it again from the web UI).
"""
import math
import threading
import time

from .i18n import t
from .wind import components

W, H = 210, 250
CX, CY, R = W // 2, 100, 72
BG, FG, DIM = "#111820", "#e8eef4", "#6b7c8c"
HEAD, TAIL, CROSS = "#4cd07d", "#ff6b5b", "#ffc857"


class Overlay:
    def __init__(self, app):
        self.app = app
        self.visible = bool(app.cfg.get("overlay", True))
        self._thread = None

    def start(self):
        try:
            import tkinter  # noqa: F401  (32-bit Python from python.org ships it)
        except ImportError:
            self.app.log(t("ov_notk"))
            return
        self._thread = threading.Thread(target=self._run, name="overlay", daemon=True)
        self._thread.start()

    def set_visible(self, on):
        self.visible = bool(on)

    # ---------- Tk thread only ----------
    def _run(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except Exception as e:  # no display
            self.app.log(t("ov_fail", err=e))
            return
        self.root = root
        root.title("FSX Weather Live - wind")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-alpha", float(self.app.cfg.get("overlay_alpha", 0.85)))
        except Exception:
            pass
        x, y = self.app.cfg.get("overlay_x", 40), self.app.cfg.get("overlay_y", 40)
        root.geometry("%dx%d+%d+%d" % (W, H, x, y))
        self.c = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=1,
                           highlightbackground="#2c3a48")
        self.c.pack()
        self._drag = (0, 0)
        self.c.bind("<ButtonPress-1>", lambda e: setattr(self, "_drag", (e.x, e.y)))
        self.c.bind("<B1-Motion>", self._on_drag)
        self.c.bind("<Button-3>", lambda e: self.set_visible(False))
        self._shown = True
        self._tick()
        root.mainloop()

    def _on_drag(self, e):
        dx, dy = self._drag
        self.root.geometry("+%d+%d" % (e.x_root - dx, e.y_root - dy))

    def _tick(self):
        try:
            if self.visible != self._shown:
                self._shown = self.visible
                if self._shown:
                    self.root.deiconify()
                    self.root.attributes("-topmost", True)
                else:
                    self.root.withdraw()
            if self._shown:
                self.root.attributes("-topmost", True)  # FSX may steal the top spot on focus
                self._draw()
        except Exception as e:
            self.app.log(t("ov_fail", err=e))
        self.root.after(150, self._tick)

    def _draw(self):
        c = self.c
        c.delete("all")
        p = self.app.sim.pos
        c.create_text(8, 8, anchor="nw", fill=DIM, font=("Segoe UI", 8), text=t("ov_title"))
        c.create_oval(CX - R, CY - R, CX + R, CY + R, outline="#2c3a48", width=2)
        for a in range(0, 360, 30):
            r1 = R - (8 if a % 90 == 0 else 4)
            s, co = math.sin(math.radians(a)), math.cos(math.radians(a))
            c.create_line(CX + R * s, CY - R * co, CX + r1 * s, CY - r1 * co, fill=DIM)
        self._plane()
        if not p or time.time() - p.get("t", 0) > 5 or "wind_dir" not in p:
            c.create_text(CX, H - 40, fill=DIM, font=("Segoe UI", 10), text=t("ov_nosim"))
            return
        hdg, wdir, wkt = p["hdg"], p["wind_dir"], p["wind_kt"]
        if wkt < 1:
            c.create_text(CX, H - 40, fill=FG, font=("Segoe UI", 13, "bold"), text=t("ov_calm"))
            return
        rel, head, cross = components(hdg, wdir, wkt)
        col = HEAD if head >= 0 else TAIL
        # Arrow from the ring (where the wind comes from) towards the aircraft.
        s, co = math.sin(math.radians(rel)), math.cos(math.radians(rel))
        x0, y0 = CX + (R - 2) * s, CY - (R - 2) * co
        x1, y1 = CX + 24 * s, CY - 24 * co
        c.create_line(x0, y0, x1, y1, fill=col, width=5, arrow="last", arrowshape=(14, 16, 6))
        c.create_text(CX, CY + R + 14, fill=FG, font=("Segoe UI", 11, "bold"),
                      text="%03d° / %d kt" % (round(wdir) % 360 or 360, round(wkt)))
        hk = t("ov_head") if head >= 0 else t("ov_tail")
        c.create_text(14, H - 34, anchor="w", fill=col, font=("Segoe UI", 11, "bold"),
                      text="%s %d kt" % (hk, round(abs(head))))
        side = t("ov_right") if cross >= 0 else t("ov_left")
        c.create_text(14, H - 14, anchor="w", fill=CROSS if abs(cross) >= 1 else DIM,
                      font=("Segoe UI", 11, "bold"),
                      text="%s %d kt %s" % (t("ov_cross"), round(abs(cross)), side if abs(cross) >= 1 else ""))
        c.create_text(W - 8, 8, anchor="ne", fill=DIM, font=("Segoe UI", 8), text="HDG %03d°" % (round(hdg) % 360))

    def _plane(self):
        c, x, y = self.c, CX, CY
        c.create_line(x, y - 16, x, y + 14, fill=FG, width=3)           # fuselage
        c.create_line(x - 14, y - 2, x + 14, y - 2, fill=FG, width=3)   # wings
        c.create_line(x - 6, y + 12, x + 6, y + 12, fill=FG, width=2)   # tail
