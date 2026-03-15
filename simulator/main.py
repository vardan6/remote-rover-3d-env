from direct.showbase.ShowBase import ShowBase
from panda3d.core import Vec3, AmbientLight, DirectionalLight, LColor, WindowProperties
from panda3d.bullet import BulletWorld

from terrain import Terrain
from rover import Rover
from camera import CameraController
from gui import TelemetryGUI


class RoverSimulator(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)

        self._setup_window()
        self._setup_lighting()
        self._setup_physics()
        self._setup_scene()
        self._setup_controls()

        self.taskMgr.add(self._update, "update")

    # ------------------------------------------------------------------
    def _setup_window(self):
        props = WindowProperties()
        props.setTitle("Remote Rover Simulator")
        props.setSize(1280, 720)
        self.win.requestProperties(props)

    def _setup_lighting(self):
        ambient = AmbientLight("ambient")
        ambient.setColor(LColor(0.35, 0.35, 0.35, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor(LColor(1.0, 0.95, 0.85, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(45, -60, 0)
        self.render.setLight(sun_np)

    def _setup_physics(self):
        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -9.81))

    def _setup_scene(self):
        self.terrain = Terrain(self.render, self.bullet_world)
        self.rover = Rover(self.render, self.bullet_world, start_pos=(0, 0, 3))
        self.cam_ctrl = CameraController(self, self.rover)
        self.gui = TelemetryGUI()

    def _setup_controls(self):
        self.key_map = {
            "forward": False,
            "backward": False,
            "left": False,
            "right": False,
        }
        self.accept("arrow_up",        self._set_key, ["forward",  True])
        self.accept("arrow_up-up",     self._set_key, ["forward",  False])
        self.accept("arrow_down",      self._set_key, ["backward", True])
        self.accept("arrow_down-up",   self._set_key, ["backward", False])
        self.accept("arrow_left",      self._set_key, ["left",     True])
        self.accept("arrow_left-up",   self._set_key, ["left",     False])
        self.accept("arrow_right",     self._set_key, ["right",    True])
        self.accept("arrow_right-up",  self._set_key, ["right",    False])
        self.accept("v",               self.cam_ctrl.toggle)
        self.accept("escape",          self.userExit)

    def _set_key(self, key, value):
        self.key_map[key] = value

    # ------------------------------------------------------------------
    def _update(self, task):
        dt = globalClock.getDt()

        # Map key state → rover throttle / steering (-1..1)
        throttle = 0.0
        if self.key_map["forward"]:
            throttle = 1.0
        elif self.key_map["backward"]:
            throttle = -1.0

        steering = 0.0
        if self.key_map["left"]:
            steering = 1.0
        elif self.key_map["right"]:
            steering = -1.0

        self.rover.throttle = throttle
        self.rover.steering = steering

        self.bullet_world.doPhysics(dt, 5, 1.0 / 180.0)
        self.rover.update(dt)
        self.cam_ctrl.update()
        self.gui.update(
            self.rover.pos,
            self.rover.heading,
            self.rover.speed,
            self.cam_ctrl.pov_active,
        )
        return task.cont


if __name__ == "__main__":
    app = RoverSimulator()
    app.run()
