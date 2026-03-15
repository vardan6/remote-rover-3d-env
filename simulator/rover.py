from panda3d.core import Vec3, NodePath, LColor
from panda3d.bullet import BulletRigidBodyNode, BulletBoxShape


# Rover dimensions (half-extents)
HALF_W = 0.4
HALF_L = 0.6
HALF_H = 0.2

# Physics tuning
MASS = 60.0
DRIVE_FORCE = 500.0     # N — forward/backward thrust
TURN_TORQUE = 80.0      # N·m — yaw torque
LINEAR_DAMPING = 0.7    # bleeds speed when key released
ANGULAR_DAMPING = 0.9   # snaps steering back quickly


def _make_body_visual(render):
    """Simple coloured box for the rover body."""
    from panda3d.core import GeomNode, Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter
    hw, hl, hh = HALF_W, HALF_L, HALF_H
    verts = [
        (-hw, -hl, -hh), ( hw, -hl, -hh), ( hw,  hl, -hh), (-hw,  hl, -hh),
        (-hw, -hl,  hh), ( hw, -hl,  hh), ( hw,  hl,  hh), (-hw,  hl,  hh),
    ]
    faces = [
        (0,1,2,3), (4,7,6,5), (0,4,5,1),
        (1,5,6,2), (2,6,7,3), (3,7,4,0),
    ]
    fmt = GeomVertexFormat.get_v3c4()
    vdata = GeomVertexData("rover_body", fmt, Geom.UHStatic)
    vdata.setNumRows(24)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")
    colours = [
        LColor(0.8, 0.2, 0.1, 1), LColor(0.8, 0.2, 0.1, 1),
        LColor(0.6, 0.15, 0.05, 1), LColor(0.6, 0.15, 0.05, 1),
        LColor(0.7, 0.18, 0.08, 1), LColor(0.7, 0.18, 0.08, 1),
    ]
    tris = GeomTriangles(Geom.UHStatic)
    base = 0
    for fi, face in enumerate(faces):
        for vi in face:
            vw.addData3(*verts[vi])
            cw.addData4(colours[fi])
        tris.addVertices(base, base+1, base+2)
        tris.addVertices(base, base+2, base+3)
        base += 4
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gn = GeomNode("rover_visual")
    gn.addGeom(geom)
    np = render.attachNewNode(gn)
    np.setTwoSided(True)
    return np


class Rover:
    def __init__(self, render, bullet_world, start_pos=(0, 0, 2)):
        self._render = render
        self.throttle = 0.0   # -1..1  (set by input)
        self.steering = 0.0   # -1..1  (set by input)

        self._setup_body(render, bullet_world, start_pos)
        self._visual = _make_body_visual(render)

    # ------------------------------------------------------------------
    def _setup_body(self, render, world, start_pos):
        shape = BulletBoxShape(Vec3(HALF_W, HALF_L, HALF_H))

        node = BulletRigidBodyNode("rover")
        node.setMass(MASS)
        node.addShape(shape)
        node.setDeactivationEnabled(False)
        node.setLinearDamping(LINEAR_DAMPING)
        node.setAngularDamping(ANGULAR_DAMPING)
        # Only allow yaw — rover cannot pitch or roll
        node.setAngularFactor(Vec3(0, 0, 1))

        self.chassis_np = render.attachNewNode(node)
        self.chassis_np.setPos(*start_pos)
        world.attachRigidBody(node)
        self._node = node

    # ------------------------------------------------------------------
    def update(self, dt):
        # Forward direction in world space (rover's +Y axis)
        forward = self.chassis_np.getQuat(self._render).getForward()

        if self.throttle != 0.0:
            force = forward * self.throttle * DRIVE_FORCE
            self._node.applyCentralForce(force)

        if self.steering != 0.0:
            # Positive steering = left turn = +Z torque
            self._node.applyTorque(Vec3(0, 0, self.steering * TURN_TORQUE))

        # Sync visual mesh to physics transform
        self._visual.setPos(self.chassis_np.getPos())
        self._visual.setHpr(self.chassis_np.getHpr())

    # ------------------------------------------------------------------
    @property
    def pos(self):
        return self.chassis_np.getPos()

    @property
    def heading(self):
        return self.chassis_np.getH()

    @property
    def speed(self):
        # km/h from linear velocity magnitude
        vel = self._node.getLinearVelocity()
        return vel.length() * 3.6
