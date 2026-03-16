from panda3d.core import load_prc_file_data
load_prc_file_data("", "audio-library-name null\nevdev-no-udev 1\nwant-directtools 0\n")

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    Vec3, Point3, AmbientLight, DirectionalLight, LColor,
    WindowProperties, CardMaker, BitMask32, Texture, Shader
)
from panda3d.bullet import BulletWorld, BulletRigidBodyNode, BulletSphereShape
from panda3d.core import (GeomNode, Geom, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter)
import math
import random

from terrain import Terrain
from rover import Rover
from camera import CameraController
from gui import TelemetryGUI


# ── Rock mesh builder ─────────────────────────────────────────────────────────
def _build_rock_node(name, rx, ry, rz, seed):
    """Rough perturbed-sphere mesh for stone obstacles."""
    rng   = random.Random(seed)
    LATS  = 5
    LONS  = 8

    # Sphere vertices with random radial perturbation
    raw_verts = []
    for lat in range(LATS + 1):
        phi = math.pi * lat / LATS          # 0 (top) … π (bottom)
        for lon in range(LONS):
            theta = 2 * math.pi * lon / LONS
            p = 1.0 + rng.uniform(-0.22, 0.22)
            x = rx * p * math.sin(phi) * math.cos(theta)
            y = ry * p * math.sin(phi) * math.sin(theta)
            z = rz * p * math.cos(phi)
            raw_verts.append((x, y, z))

    fmt   = GeomVertexFormat.get_v3n3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")

    base_col = (0.44, 0.40, 0.35)
    for (x, y, z) in raw_verts:
        vw.addData3(x, y, z)
        ln = math.sqrt(x * x + y * y + z * z) or 1e-6
        nw.addData3(x / ln, y / ln, z / ln)
        cw.addData4(
            base_col[0] + rng.uniform(-0.07, 0.07),
            base_col[1] + rng.uniform(-0.07, 0.07),
            base_col[2] + rng.uniform(-0.07, 0.07),
            1.0
        )

    tris = GeomTriangles(Geom.UHStatic)
    for lat in range(LATS):
        for lon in range(LONS):
            a  = lat * LONS + lon
            b  = lat * LONS + (lon + 1) % LONS
            c  = (lat + 1) * LONS + lon
            d  = (lat + 1) * LONS + (lon + 1) % LONS
            tris.addVertices(a, c, b)
            tris.addVertices(b, c, d)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(geom)
    return gn


# ── Simulator ─────────────────────────────────────────────────────────────────
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
    SUN_POS    = Point3(-70, -90, 130)
    _SUN_OFFSET = Vec3(-35, -45, 80)

    def _setup_lighting(self):
        ambient = AmbientLight("ambient")
        ambient.setColor(LColor(0.45, 0.47, 0.52, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor(LColor(1.05, 0.98, 0.85, 1))
        sun.setShadowCaster(True, 4096, 4096)
        sun.getLens().setFilmSize(160, 160)
        sun.getLens().setNearFar(1, 250)

        self._sun_np = self.render.attachNewNode(sun)
        self._sun_np.setPos(self._SUN_OFFSET)
        self._sun_np.lookAt(Point3(0, 0, 0))
        self.render.setLight(self._sun_np)

        self._add_sun_disc(self.SUN_POS)
        self.render.setShaderAuto()

    def _add_sun_disc(self, pos):
        main_mask = self.cam.node().getCameraMask()
        cm = CardMaker("sun_disc")
        cm.setFrame(-1, 1, -1, 1)

        disc = self.render.attachNewNode(cm.generate())
        disc.setPos(pos); disc.setBillboardPointEye(); disc.setScale(6)
        disc.setColor(1.0, 0.97, 0.75, 1)
        disc.setLightOff(); disc.setShaderOff(); disc.setDepthWrite(False)
        disc.hide(BitMask32.allOn()); disc.show(main_mask)

        glow = self.render.attachNewNode(cm.generate())
        glow.setPos(pos); glow.setBillboardPointEye(); glow.setScale(14)
        glow.setColor(1.0, 0.90, 0.50, 0.18)
        glow.setLightOff(); glow.setShaderOff(); glow.setDepthWrite(False)
        glow.setTransparency(True)
        glow.hide(BitMask32.allOn()); glow.show(main_mask)

    def _setup_physics(self):
        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -9.81))

    def _setup_scene(self):
        main_mask = self.cam.node().getCameraMask()

        self.terrain = Terrain(self.render, self.bullet_world)
        self.terrain.np.hide(BitMask32.allOn())
        self.terrain.np.show(main_mask)

        # Spawn high enough to let the suspension settle onto the terrain
        self.rover = Rover(self.render, self.bullet_world, start_pos=(0, 0, 4))

        # Stone obstacles
        self._stone_nps = []
        self._create_stones(main_mask)

        # PCF soft-shadow shader
        pcf = Shader.load(Shader.SL_GLSL, "shadow_pcf.vert", "shadow_pcf.frag")
        self.terrain.np.setShader(pcf)
        self.rover.chassis_np.setShader(pcf)
        for wn in self.rover.wheel_nps:
            wn.setShader(pcf)
        for sn in self._stone_nps:
            sn.setShader(pcf)

        self._flip_timer = 0.0

        self.cam_ctrl = CameraController(self, self.rover)
        self.gui      = TelemetryGUI()

    # ── Stone obstacle creation ───────────────────────────────────────────────
    def _create_stones(self, main_mask):
        rng        = random.Random(42)
        num_stones = 14
        placed     = 0
        attempts   = 0

        while placed < num_stones and attempts < 200:
            attempts += 1
            # Random position on terrain, keep a clear zone around rover start
            px = rng.uniform(-44, 44)
            py = rng.uniform(-44, 44)
            if math.sqrt(px * px + py * py) < 8.0:
                continue   # too close to spawn

            radius = rng.uniform(0.28, 0.60)
            # Semi-axes: slightly squashed rocks
            rx = radius * rng.uniform(0.8, 1.3)
            ry = radius * rng.uniform(0.8, 1.3)
            rz = radius * rng.uniform(0.55, 0.85)

            terrain_z = self.terrain.height_at(px, py)
            stone_z   = terrain_z + rz * 0.6   # half-buried

            # Physics: static sphere (mass=0)
            shape = BulletSphereShape(radius)
            node  = BulletRigidBodyNode(f"stone_{placed}")
            node.addShape(shape)
            node.setMass(0)   # static / immovable
            stone_np = self.render.attachNewNode(node)
            stone_np.setPos(px, py, stone_z)
            stone_np.setHpr(
                rng.uniform(0, 360),
                rng.uniform(-15, 15),
                rng.uniform(-15, 15)
            )
            self.bullet_world.attachRigidBody(node)

            # Visual mesh
            rock_gn = _build_rock_node(f"rock_{placed}", rx, ry, rz, seed=placed)
            rock_np = stone_np.attachNewNode(rock_gn)
            rock_np.setTwoSided(True)
            rock_np.hide(BitMask32.allOn())
            rock_np.show(main_mask)
            self._stone_nps.append(rock_np)

            placed += 1

    def _reset_rover(self):
        """Teleport rover back to spawn with zeroed velocity (called after flip)."""
        cn = self.rover.chassis_np.node()
        self.rover.chassis_np.setPos(0, 0, 4)
        self.rover.chassis_np.setHpr(0, 0, 0)
        cn.setLinearVelocity(Vec3(0, 0, 0))
        cn.setAngularVelocity(Vec3(0, 0, 0))
        self.rover.throttle = 0.0
        self.rover.steering = 0.0

    # ------------------------------------------------------------------
    def _setup_controls(self):
        self.key_map = {
            "forward":  False,
            "backward": False,
            "left":     False,
            "right":    False,
        }
        self.accept("arrow_up",       self._set_key, ["forward",  True])
        self.accept("arrow_up-up",    self._set_key, ["forward",  False])
        self.accept("arrow_down",     self._set_key, ["backward", True])
        self.accept("arrow_down-up",  self._set_key, ["backward", False])
        self.accept("arrow_left",     self._set_key, ["left",     True])
        self.accept("arrow_left-up",  self._set_key, ["left",     False])
        self.accept("arrow_right",    self._set_key, ["right",    True])
        self.accept("arrow_right-up", self._set_key, ["right",    False])
        self.accept("v",              self.cam_ctrl.toggle)
        self.accept("escape",         self.userExit)

    def _set_key(self, key, value):
        self.key_map[key] = value

    def _fix_shadow_border(self, task):
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

        # Apply forces BEFORE stepping physics so they take effect this frame
        self.rover.update(dt)
        self.bullet_world.doPhysics(dt, 10, 1.0 / 180.0)

        # Flip detection: rover up-vector Z < 0 means upside-down (past 90°)
        up = self.rover.chassis_np.getQuat(self.render).xform(Vec3(0, 0, 1))
        if up.z < 0.0:
            self._flip_timer += dt
            if self._flip_timer >= 2.0:
                self._reset_rover()
                self._flip_timer = 0.0
        else:
            self._flip_timer = 0.0

        # Keep shadow camera centred over rover
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
