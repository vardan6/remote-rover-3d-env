from panda3d.core import (
    NodePath, Camera, PerspectiveLens, Vec3, Point3,
    FrameBufferProperties, WindowProperties, GraphicsPipe,
    GraphicsOutput
)


FOLLOW_DIST = 8.0
FOLLOW_HEIGHT = 4.0
POV_FORWARD_OFFSET = 0.65   # metres in front of rover centre
POV_HEIGHT_OFFSET = 0.25    # metres above rover centre
POV_FOV = 90.0
POV_W, POV_H = 640, 480     # offscreen buffer resolution


class CameraController:
    def __init__(self, base, rover):
        self._base = base
        self._rover = rover
        self._pov_active = False
        self._pov_buffer = None
        self._pov_cam_np = None

        # Disable Panda3D's default mouse-controlled camera
        base.disableMouse()
        self._setup_follow_cam()
        self._setup_pov_cam()

    # ------------------------------------------------------------------
    def _setup_follow_cam(self):
        base = self._base
        base.camera.reparentTo(base.render)
        base.camLens.setFov(60)
        base.camLens.setNear(0.1)
        base.camLens.setFar(500)

    def _setup_pov_cam(self):
        base = self._base
        # Create offscreen buffer for POV capture (Phase 2 will use this)
        fb_props = FrameBufferProperties()
        fb_props.setRgbColor(True)
        fb_props.setDepthBits(24)

        win_props = WindowProperties.size(POV_W, POV_H)

        self._pov_buffer = base.graphicsEngine.makeOutput(
            base.pipe,
            "pov_buffer",
            -2,
            fb_props,
            win_props,
            GraphicsPipe.BFRefuseWindow | GraphicsPipe.BFResizeable,
            base.win.getGsg(),
            base.win,
        )

        if self._pov_buffer is None:
            print("[camera] Warning: could not create POV offscreen buffer")
            return

        pov_cam_node = Camera("pov_cam")
        lens = PerspectiveLens()
        lens.setFov(POV_FOV)
        lens.setNear(0.1)
        lens.setFar(300)
        pov_cam_node.setLens(lens)

        self._pov_cam_np = base.render.attachNewNode(pov_cam_node)
        dr = self._pov_buffer.makeDisplayRegion()
        dr.setCamera(self._pov_cam_np)

        # Buffer is active only when POV mode is on
        self._pov_buffer.setActive(False)

    # ------------------------------------------------------------------
    def toggle(self):
        self._pov_active = not self._pov_active
        if self._pov_buffer:
            self._pov_buffer.setActive(self._pov_active)

    @property
    def pov_active(self):
        return self._pov_active

    # ------------------------------------------------------------------
    def update(self):
        rover = self._rover
        pos = rover.pos

        if self._pov_active:
            # Position POV camera at rover front
            rover_np = rover.chassis_np
            # Forward direction in world space: Panda3D Y-forward
            fwd = base = self._base.render
            forward = rover_np.getQuat(self._base.render).getForward()
            up = Vec3(0, 0, 1)
            cam_pos = (pos +
                       forward * POV_FORWARD_OFFSET +
                       up * POV_HEIGHT_OFFSET)
            if self._pov_cam_np:
                self._pov_cam_np.setPos(cam_pos)
                self._pov_cam_np.setHpr(rover_np.getHpr(self._base.render))
            # Hide main camera output so only POV is visible
            # (we keep the main display region active but park the camera)
            self._base.camera.setPos(cam_pos)
            self._base.camera.setHpr(rover_np.getHpr(self._base.render))
        else:
            # Smooth follow camera: position behind and above rover
            rover_np = rover.chassis_np
            forward = rover_np.getQuat(self._base.render).getForward()
            cam_pos = pos - forward * FOLLOW_DIST + Vec3(0, 0, FOLLOW_HEIGHT)
            self._base.camera.setPos(cam_pos)
            self._base.camera.lookAt(Point3(pos.x, pos.y, pos.z + 0.5))

    @property
    def pov_buffer(self):
        """Expose the offscreen buffer for Phase 2 frame capture."""
        return self._pov_buffer
