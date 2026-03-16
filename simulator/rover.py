import math
from panda3d.core import Vec3, LColor, Point3, BitMask32
from panda3d.bullet import BulletRigidBodyNode, BulletBoxShape
from panda3d.core import (GeomNode, Geom, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter)


# ── Rover dimensions ────────────────────────────────────────────────────────
HALF_W = 0.4
HALF_L = 0.6
HALF_H = 0.11           # body height ≈ half wheel diameter

WHEEL_RADIUS = 0.225    # 1.5× original
WHEEL_WIDTH  = 0.14

# ── Kinematic driving parameters ────────────────────────────────────────────
ACCELERATION = 6.0      # m/s²  — how quickly rover gains speed
MAX_SPEED    = 5.0      # m/s   (≈ 18 km/h)
FRICTION     = 5.0      # m/s²  — deceleration when throttle released
TURN_RATE    = 75.0     # °/s   — yaw rate (applied directly to heading)

# ── Wheel attachment offsets (local chassis space) ───────────────────────────
_WHEEL_Z =  -HALF_H + WHEEL_RADIUS + 0.03   # centre at box-bottom level + clearance
_WHEEL_X =   HALF_W + WHEEL_WIDTH / 2 + 0.02
_WHEEL_Y =   HALF_L - 0.18
WHEEL_OFFSETS = [
    Vec3(-_WHEEL_X, -_WHEEL_Y, _WHEEL_Z),   # front-left
    Vec3( _WHEEL_X, -_WHEEL_Y, _WHEEL_Z),   # front-right
    Vec3(-_WHEEL_X,  _WHEEL_Y, _WHEEL_Z),   # rear-left
    Vec3( _WHEEL_X,  _WHEEL_Y, _WHEEL_Z),   # rear-right
]


# ── Geometry helpers ─────────────────────────────────────────────────────────
def _build_body_node():
    hw, hl, hh = HALF_W, HALF_L, HALF_H
    verts = [
        (-hw,-hl,-hh),(hw,-hl,-hh),(hw,hl,-hh),(-hw,hl,-hh),
        (-hw,-hl, hh),(hw,-hl, hh),(hw,hl, hh),(-hw,hl, hh),
    ]
    faces = [
        ((0,1,2,3), LColor(0.80,0.20,0.10,1)),
        ((4,7,6,5), LColor(0.80,0.20,0.10,1)),
        ((0,4,5,1), LColor(0.90,0.30,0.05,1)),  # front (brighter)
        ((1,5,6,2), LColor(0.60,0.15,0.05,1)),
        ((2,6,7,3), LColor(0.55,0.13,0.04,1)),
        ((3,7,4,0), LColor(0.60,0.15,0.05,1)),
    ]
    fmt   = GeomVertexFormat.get_v3c4()
    vdata = GeomVertexData("rover_body", fmt, Geom.UHStatic)
    vdata.setNumRows(24)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)
    base = 0
    for face_verts, col in faces:
        for vi in face_verts:
            vw.addData3(*verts[vi])
            cw.addData4(col)
        tris.addVertices(base, base+1, base+2)
        tris.addVertices(base, base+2, base+3)
        base += 4
    geom = Geom(vdata); geom.addPrimitive(tris)
    gn = GeomNode("rover_body"); gn.addGeom(geom)
    return gn


def _build_wheel_node(name):
    SEGS = 16
    hw, r = WHEEL_WIDTH / 2.0, WHEEL_RADIUS
    fmt   = GeomVertexFormat.get_v3n3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHDynamic)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)
    idx = 0
    for i in range(SEGS):
        a0 = 2*math.pi*i/SEGS
        a1 = 2*math.pi*(i+1)/SEGS
        col = LColor(0.18,0.18,0.18,1) if (i//2)%2==0 else LColor(0.28,0.28,0.28,1)
        for (x, a) in [(-hw,a0),(-hw,a1),(hw,a1),(hw,a0)]:
            vw.addData3(x, math.cos(a)*r, math.sin(a)*r)
            nw.addData3(0, math.cos(a), math.sin(a))
            cw.addData4(col)
        tris.addVertices(idx, idx+1, idx+2)
        tris.addVertices(idx, idx+2, idx+3)
        idx += 4
    hub = LColor(0.55,0.55,0.60,1)
    for side, nx in [(-hw,-1.0),(hw,1.0)]:
        ci = idx
        vw.addData3(side,0,0); nw.addData3(nx,0,0); cw.addData4(hub); idx+=1
        for i in range(SEGS):
            a = 2*math.pi*i/SEGS
            vw.addData3(side, math.cos(a)*r, math.sin(a)*r)
            nw.addData3(nx,0,0); cw.addData4(hub)
        for i in range(SEGS):
            i0, i1 = ci+1+i, ci+1+(i+1)%SEGS
            if nx>0: tris.addVertices(ci, i0, i1)
            else:    tris.addVertices(ci, i1, i0)
        idx += SEGS
    geom = Geom(vdata); geom.addPrimitive(tris)
    gn = GeomNode(name); gn.addGeom(geom)
    return gn


# ── Rover ────────────────────────────────────────────────────────────────────
class Rover:
    def __init__(self, render, bullet_world, start_pos=(0, 0, 2)):
        self._render      = render
        self._world       = bullet_world
        self.throttle     = 0.0
        self.steering     = 0.0
        self._vel         = Vec3(0, 0, 0)   # horizontal world-space velocity
        self._wheel_angle = 0.0

        self._setup_body(render, bullet_world, start_pos)

        body_np = self.chassis_np.attachNewNode(_build_body_node())
        body_np.setZ(_WHEEL_Z + HALF_H)
        body_np.setTwoSided(True)

        self._wheels = []
        for i, offset in enumerate(WHEEL_OFFSETS):
            wn = self.chassis_np.attachNewNode(_build_wheel_node(f"wheel_{i}"))
            wn.setPos(offset)
            wn.setTwoSided(True)
            self._wheels.append(wn)

    # ── physics setup ────────────────────────────────────────────────────────
    def _setup_body(self, render, world, start_pos):
        shape = BulletBoxShape(Vec3(HALF_W, HALF_L, HALF_H))
        node  = BulletRigidBodyNode("rover")
        node.setMass(1.0)             # non-zero keeps it out of static category
        node.addShape(shape)
        node.setDeactivationEnabled(False)
        node.setKinematic(True)       # we drive it manually; physics just detects collisions
        node.setIntoCollideMask(BitMask32(0x2))   # keep rover out of terrain-height raycasts

        self.chassis_np = render.attachNewNode(node)
        self.chassis_np.setPos(*start_pos)
        world.attachRigidBody(node)
        self._node = node

    # ── terrain sampling ─────────────────────────────────────────────────────
    def _terrain_z(self, x, y, near_z):
        """Return terrain surface height at world (x, y) via downward raycast."""
        result = self._world.rayTestClosest(
            Point3(x, y, near_z + 2.0),
            Point3(x, y, near_z - 6.0),
            BitMask32(0x1)   # terrain mask only — ignore rover body
        )
        return result.getHitPos().z if result.hasHit() else near_z

    # ── terrain conformance ──────────────────────────────────────────────────
    def _conform_to_terrain(self):
        """Set chassis Z, pitch and roll so every wheel bottom touches terrain."""
        pos = self.chassis_np.getPos()
        h   = self.chassis_np.getH()     # heading (degrees, CW from +Y in Panda3D)

        # Rotate wheel XY offsets by heading so we sample the right world position
        h_rad     = math.radians(h)
        cos_h, sin_h = math.cos(h_rad), math.sin(h_rad)

        heights = []
        for off in WHEEL_OFFSETS:
            wx = pos.x + off.x * cos_h + off.y * sin_h
            wy = pos.y - off.x * sin_h + off.y * cos_h
            heights.append(self._terrain_z(wx, wy, pos.z))

        fl, fr, rl, rr = heights

        # ── chassis target Z ────────────────────────────────────────────────
        # wheel_centre = ground_z + WHEEL_RADIUS
        # chassis_centre = wheel_centre - _WHEEL_Z
        avg_ground = (fl + fr + rl + rr) / 4
        target_z   = avg_ground + WHEEL_RADIUS - _WHEEL_Z

        # ── pitch (front-rear tilt) ─────────────────────────────────────────
        # Wheels at +_WHEEL_Y (rl/rr) are the motion-forward side.
        # Positive P in Panda3D tilts +Y (forward) up → nose-up going uphill. ✓
        rear_h  = (rl + rr) / 2
        front_h = (fl + fr) / 2
        pitch = math.degrees(math.atan2(rear_h - front_h, 2.0 * _WHEEL_Y))

        # ── roll (left-right tilt) ──────────────────────────────────────────
        # Positive R in Panda3D tilts +X (right) down, so negate.
        right_h = (fr + rr) / 2
        left_h  = (fl + rl) / 2
        roll = -math.degrees(math.atan2(right_h - left_h, 2.0 * _WHEEL_X))

        self.chassis_np.setPos(pos.x, pos.y, target_z)
        self.chassis_np.setHpr(h, pitch, roll)

    # ── per-frame update ─────────────────────────────────────────────────────
    def update(self, dt):
        # Horizontal forward from heading only — no pitch/roll bleed into velocity
        h_rad = math.radians(self.chassis_np.getH())
        forward = Vec3(-math.sin(h_rad), math.cos(h_rad), 0)

        # Throttle
        if self.throttle != 0.0:
            self._vel += forward * self.throttle * ACCELERATION * dt
            spd = self._vel.length()
            if spd > MAX_SPEED:
                self._vel *= MAX_SPEED / spd
        else:
            spd = self._vel.length()
            if spd > 1e-3:
                drag = min(FRICTION * dt, spd)
                self._vel -= (self._vel / spd) * drag
            else:
                self._vel = Vec3(0, 0, 0)

        # Steering — directly rotate heading (no drift, instant response)
        if self.steering != 0.0:
            self.chassis_np.setH(self.chassis_np.getH()
                                 + self.steering * TURN_RATE * dt)

        # Translate horizontally
        pos = self.chassis_np.getPos()
        self.chassis_np.setPos(pos.x + self._vel.x * dt,
                               pos.y + self._vel.y * dt,
                               pos.z)

        # Snap Z + pitch + roll to terrain
        self._conform_to_terrain()

        # Spin wheels
        vel_fwd = forward.dot(self._vel)
        self._wheel_angle -= vel_fwd * dt / WHEEL_RADIUS * (180.0 / math.pi)
        for wheel_np in self._wheels:
            wheel_np.setP(self._wheel_angle)

    # ── properties ───────────────────────────────────────────────────────────
    @property
    def pos(self):
        return self.chassis_np.getPos()

    @property
    def heading(self):
        return self.chassis_np.getH()

    @property
    def speed(self):
        return self._vel.length() * 3.6    # km/h
