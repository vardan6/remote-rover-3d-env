import math
from panda3d.core import Vec3, LColor
from panda3d.bullet import BulletRigidBodyNode, BulletBoxShape
from panda3d.core import GeomNode, Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter


# Rover dimensions (half-extents)
HALF_W = 0.4
HALF_L = 0.6
HALF_H = 0.11          # body height ≈ half wheel diameter (wheel diam = 0.45)

WHEEL_RADIUS = 0.225   # 1.5× original 0.15
WHEEL_WIDTH  = 0.14

# Physics tuning
MASS            = 60.0
DRIVE_FORCE     = 500.0
TURN_TORQUE     = 80.0
LINEAR_DAMPING  = 0.7
ANGULAR_DAMPING = 0.9

# Wheel positions relative to chassis centre
# _WHEEL_Z: wheel centre sits at box-bottom level, +0.03 m clearance so the
# visual tyre never clips through terrain during normal Bullet contact penetration
_WHEEL_Z = -HALF_H + WHEEL_RADIUS + 0.03
_WHEEL_X =  HALF_W + WHEEL_WIDTH / 2 + 0.02
_WHEEL_Y =  HALF_L - 0.18
WHEEL_OFFSETS = [
    Vec3(-_WHEEL_X, -_WHEEL_Y, _WHEEL_Z),   # front-left
    Vec3( _WHEEL_X, -_WHEEL_Y, _WHEEL_Z),   # front-right
    Vec3(-_WHEEL_X,  _WHEEL_Y, _WHEEL_Z),   # rear-left
    Vec3( _WHEEL_X,  _WHEEL_Y, _WHEEL_Z),   # rear-right
]


# ---------------------------------------------------------------------------
def _build_body_node():
    """Box geometry for the rover chassis."""
    hw, hl, hh = HALF_W, HALF_L, HALF_H
    verts = [
        (-hw, -hl, -hh), ( hw, -hl, -hh), ( hw,  hl, -hh), (-hw,  hl, -hh),
        (-hw, -hl,  hh), ( hw, -hl,  hh), ( hw,  hl,  hh), (-hw,  hl,  hh),
    ]
    # face vertex indices + per-face colour
    faces = [
        ((0,1,2,3), LColor(0.80, 0.20, 0.10, 1)),  # bottom
        ((4,7,6,5), LColor(0.80, 0.20, 0.10, 1)),  # top
        ((0,4,5,1), LColor(0.90, 0.30, 0.05, 1)),  # front  ← brighter = front indicator
        ((1,5,6,2), LColor(0.60, 0.15, 0.05, 1)),  # right
        ((2,6,7,3), LColor(0.55, 0.13, 0.04, 1)),  # back
        ((3,7,4,0), LColor(0.60, 0.15, 0.05, 1)),  # left
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
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode("rover_body")
    gn.addGeom(geom)
    return gn


def _build_wheel_node(name):
    """Cylinder along the X axis (wheel axle).  Tread + hub caps."""
    SEGS = 16
    hw   = WHEEL_WIDTH / 2.0
    r    = WHEEL_RADIUS

    fmt   = GeomVertexFormat.get_v3n3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHDynamic)
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)
    idx = 0

    # --- side surface (tread) — alternating dark/light bands every 2 segs ---
    for i in range(SEGS):
        a0 = 2 * math.pi * i       / SEGS
        a1 = 2 * math.pi * (i + 1) / SEGS
        tread = LColor(0.18, 0.18, 0.18, 1) if (i // 2) % 2 == 0 else LColor(0.28, 0.28, 0.28, 1)
        for (x, a) in [(-hw, a0), (-hw, a1), (hw, a1), (hw, a0)]:
            y = math.cos(a) * r
            z = math.sin(a) * r
            vw.addData3(x, y, z)
            nw.addData3(0, math.cos(a), math.sin(a))
            cw.addData4(tread)
        tris.addVertices(idx, idx+1, idx+2)
        tris.addVertices(idx, idx+2, idx+3)
        idx += 4

    # --- hub caps (flat discs on each side) ---
    hub_col = LColor(0.55, 0.55, 0.60, 1)
    for side, nx_val in [(-hw, -1.0), (hw, 1.0)]:
        centre_idx = idx
        vw.addData3(side, 0, 0)
        nw.addData3(nx_val, 0, 0)
        cw.addData4(hub_col)
        idx += 1
        for i in range(SEGS):
            a = 2 * math.pi * i / SEGS
            vw.addData3(side, math.cos(a) * r, math.sin(a) * r)
            nw.addData3(nx_val, 0, 0)
            cw.addData4(hub_col)
        for i in range(SEGS):
            i0 = centre_idx + 1 + i
            i1 = centre_idx + 1 + (i + 1) % SEGS
            if nx_val > 0:
                tris.addVertices(centre_idx, i0, i1)
            else:
                tris.addVertices(centre_idx, i1, i0)
        idx += SEGS

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode(name)
    gn.addGeom(geom)
    return gn


# ---------------------------------------------------------------------------
class Rover:
    def __init__(self, render, bullet_world, start_pos=(0, 0, 2)):
        self._render       = render
        self.throttle      = 0.0
        self.steering      = 0.0
        self._wheel_angle  = 0.0   # cumulative spin angle (degrees)

        self._setup_body(render, bullet_world, start_pos)

        # Visual body: raise it so its bottom face sits at wheel-axle height.
        # body bottom = chassis_centre + _WHEEL_Z, so node centre = _WHEEL_Z + HALF_H
        body_np = self.chassis_np.attachNewNode(_build_body_node())
        body_np.setZ(_WHEEL_Z + HALF_H)
        body_np.setTwoSided(True)

        # Four wheels, also parented to chassis
        self._wheels = []
        for i, offset in enumerate(WHEEL_OFFSETS):
            wn = self.chassis_np.attachNewNode(_build_wheel_node(f"wheel_{i}"))
            wn.setPos(offset)
            wn.setTwoSided(True)
            self._wheels.append(wn)

    # ------------------------------------------------------------------
    def _setup_body(self, render, world, start_pos):
        shape = BulletBoxShape(Vec3(HALF_W, HALF_L, HALF_H))
        node  = BulletRigidBodyNode("rover")
        node.setMass(MASS)
        node.addShape(shape)
        node.setDeactivationEnabled(False)
        node.setLinearDamping(LINEAR_DAMPING)
        node.setAngularDamping(ANGULAR_DAMPING)
        node.setAngularFactor(Vec3(0, 0, 1))   # yaw only — no pitch/roll

        self.chassis_np = render.attachNewNode(node)
        self.chassis_np.setPos(*start_pos)
        world.attachRigidBody(node)
        self._node = node

    # ------------------------------------------------------------------
    def update(self, dt):
        # Local +Y axis in world space = rover's forward direction
        forward = self.chassis_np.getQuat(self._render).xform(Vec3(0, 1, 0))

        if self.throttle != 0.0:
            self._node.applyCentralForce(forward * self.throttle * DRIVE_FORCE)

        if self.steering != 0.0:
            self._node.applyTorque(Vec3(0, 0, self.steering * TURN_TORQUE))

        # Spin wheels: P = pitch = rotation around the X axle (left-right)
        # Panda3D: R rotates around Y (forward), P rotates around X (axle) — we want P
        vel_fwd = forward.dot(self._node.getLinearVelocity())
        self._wheel_angle -= vel_fwd * dt / WHEEL_RADIUS * (180.0 / math.pi)
        for wheel_np in self._wheels:
            wheel_np.setP(self._wheel_angle)   # P = rotation around local X = axle

    # ------------------------------------------------------------------
    @property
    def pos(self):
        return self.chassis_np.getPos()

    @property
    def heading(self):
        return self.chassis_np.getH()

    @property
    def speed(self):
        return self._node.getLinearVelocity().length() * 3.6   # km/h
