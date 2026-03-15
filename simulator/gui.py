from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode


class TelemetryGUI:
    def __init__(self):
        common = dict(
            align=TextNode.ALeft,
            fg=(1, 1, 1, 1),
            shadow=(0, 0, 0, 0.8),
            scale=0.05,
            mayChange=True,
        )
        self._pos_text = OnscreenText(
            pos=(-1.3, 0.9), **common
        )
        self._heading_text = OnscreenText(
            pos=(-1.3, 0.83), **common
        )
        self._speed_text = OnscreenText(
            pos=(-1.3, 0.76), **common
        )
        self._cam_text = OnscreenText(
            pos=(-1.3, 0.69), **common
        )

    def update(self, pos, heading, speed, pov_active):
        self._pos_text.setText(
            f"Pos  X:{pos.x:6.2f}  Y:{pos.y:6.2f}  Z:{pos.z:6.2f}"
        )
        self._heading_text.setText(f"Heading: {heading:6.1f} deg")
        self._speed_text.setText(f"Speed:  {speed:6.1f} km/h")
        cam_mode = "POV" if pov_active else "Follow"
        self._cam_text.setText(f"Camera: {cam_mode}  [V to toggle]")
