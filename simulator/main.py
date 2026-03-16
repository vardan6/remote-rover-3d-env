from panda3d.core import load_prc_file_data
load_prc_file_data("", "audio-library-name null\nevdev-no-udev 1\nwant-directtools 0\n")

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    Vec3, Point3, AmbientLight, DirectionalLight, LColor,
    WindowProperties, CardMaker, BitMask32, Texture, Shader
)
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
        self.taskMgr.add(self._fix_shadow_border, "fix_shadow_border")

    # ------------------------------------------------------------------
    def _setup_window(self):
        props = WindowProperties()
        props.setTitle("Remote Rover Simulator")
        props.setSize(1280, 720)
        self.win.requestProperties(props)

    # Visual sun position — fixed in the sky for the glowing disc
    SUN_POS = Point3(-70, -90, 130)
    # Offset from rover used to keep the shadow camera centred over the rover.
    # Same direction as SUN_POS but shorter (shadow camera doesn't need to be far).
    _SUN_OFFSET = Vec3(-35, -45, 80)

    def _setup_lighting(self):
        # High ambient = light, natural-looking shadows
        ambient = AmbientLight("ambient")
        ambient.setColor(LColor(0.45, 0.47, 0.52, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        # Directional sun light
        sun = DirectionalLight("sun")
        sun.setColor(LColor(1.05, 0.98, 0.85, 1))
        # 4096×4096 at 160×160 world units → ~25 px/m: covers full terrain
        # at the same pixel density as the crisp 2048@80 version.
        sun.setShadowCaster(True, 4096, 4096)
        sun.getLens().setFilmSize(160, 160)
        sun.getLens().setNearFar(1, 250)

        self._sun_np = self.render.attachNewNode(sun)
        self._sun_np.setPos(self._SUN_OFFSET)   # start above scene origin
        self._sun_np.lookAt(Point3(0, 0, 0))    # sets the light direction once
        self.render.setLight(self._sun_np)

        # Visible sun disc — billboard card fixed in the sky
        self._add_sun_disc(self.SUN_POS)

        # Auto-shader enables shadow map rendering on all geometry
        self.render.setShaderAuto()

    def _add_sun_disc(self, pos):
        """Bright glowing billboard that acts as the visible sun in the sky."""
        # Only show these cards to the main camera — hide from shadow cameras
        # so they don't project a giant card-shaped shadow onto the terrain.
        main_mask = self.cam.node().getCameraMask()

        cm = CardMaker("sun_disc")
        cm.setFrame(-1, 1, -1, 1)

        disc = self.render.attachNewNode(cm.generate())
        disc.setPos(pos)
        disc.setBillboardPointEye()
        disc.setScale(6)
        disc.setColor(1.0, 0.97, 0.75, 1)
        disc.setLightOff()
        disc.setShaderOff()
        disc.setDepthWrite(False)
        disc.hide(BitMask32.allOn())          # hidden from all cameras …
        disc.show(main_mask)                  # … except the main view camera

        glow = self.render.attachNewNode(cm.generate())
        glow.setPos(pos)
        glow.setBillboardPointEye()
        glow.setScale(14)
        glow.setColor(1.0, 0.90, 0.50, 0.18)
        glow.setLightOff()
        glow.setShaderOff()
        glow.setDepthWrite(False)
        glow.setTransparency(True)
        glow.hide(BitMask32.allOn())
        glow.show(main_mask)

    def _setup_physics(self):
        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -9.81))

    def _setup_scene(self):
        self.terrain = Terrain(self.render, self.bullet_world)
        # Hide terrain from shadow cameras (it should not cast shadows).
        main_mask = self.cam.node().getCameraMask()
        self.terrain.np.hide(BitMask32.allOn())
        self.terrain.np.show(main_mask)
        # Apply PCF soft-shadow shader to terrain — overrides the auto-shader
        # for this node only, giving smooth Poisson-disk sampled shadows instead
        # of the single bilinear sample that produces hard pixelated edges.
        pcf = Shader.load(Shader.SL_GLSL, "shadow_pcf.vert", "shadow_pcf.frag")
        self.terrain.np.setShader(pcf)

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

    def _fix_shadow_border(self, task):
        """Set the shadow map's out-of-bounds area to fully-lit (white border).
        The shadow buffer is created lazily on the first render, so we retry
        each frame until it's available, then fix it once and stop."""
        buf = self._sun_np.node().getShadowBuffer(self.win.getGsg())
        if buf is None:
            return task.cont
        tex = buf.getTexture()
        tex.setWrapU(Texture.WMBorderColor)
        tex.setWrapV(Texture.WMBorderColor)
        tex.setBorderColor(LColor(1, 1, 1, 1))
        return task.done

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

        # Keep shadow camera centred over the rover so the tight film window
        # always covers the rover regardless of where it has driven
        rp = self.rover.pos
        self._sun_np.setPos(Point3(rp.x + self._SUN_OFFSET.x,
                                   rp.y + self._SUN_OFFSET.y,
                                   rp.z + self._SUN_OFFSET.z))
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
