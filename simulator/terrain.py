from panda3d.core import (
    NodePath, GeomNode, Geom, GeomTriangles, GeomVertexData,
    GeomVertexFormat, GeomVertexWriter, Vec3, LColor, PNMImage
)
from panda3d.bullet import BulletRigidBodyNode, BulletHeightfieldShape, ZUp
import random
import math


TERRAIN_SIZE = 100   # world units
TILE_COUNT = 80      # vertices per side (tiles = TILE_COUNT-1)


def _build_heightmap():
    """Generate a mostly-flat heightmap with gentle bumps."""
    n = TILE_COUNT
    hmap = []
    for row in range(n):
        r = []
        for col in range(n):
            # two overlapping sine waves for gentle rolling terrain
            x = col / (n - 1)
            y = row / (n - 1)
            h = (math.sin(x * 6.0) * math.cos(y * 5.0) * 0.4 +
                 math.sin(x * 13.0 + 1.0) * math.sin(y * 11.0) * 0.15)
            r.append(h)
        hmap.append(r)
    return hmap


def _build_geom(hmap):
    n = TILE_COUNT
    cell = TERRAIN_SIZE / (n - 1)
    offset = TERRAIN_SIZE / 2.0

    fmt = GeomVertexFormat.get_v3n3c4()
    vdata = GeomVertexData("terrain", fmt, Geom.UHStatic)
    vdata.setNumRows(n * n)

    vwriter = GeomVertexWriter(vdata, "vertex")
    nwriter = GeomVertexWriter(vdata, "normal")
    cwriter = GeomVertexWriter(vdata, "color")

    for row in range(n):
        for col in range(n):
            h = hmap[row][col]
            x = col * cell - offset
            y = row * cell - offset
            vwriter.addData3(x, y, h)

            # approximate normal via finite diff
            hr = hmap[row][min(col + 1, n - 1)]
            hl = hmap[row][max(col - 1, 0)]
            hu = hmap[min(row + 1, n - 1)][col]
            hd = hmap[max(row - 1, 0)][col]
            nx = (hl - hr) / (2 * cell)
            ny = (hd - hu) / (2 * cell)
            nz = 1.0
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            nwriter.addData3(nx / length, ny / length, nz / length)

            # checkerboard: alternate every 8 tiles so movement is obvious
            checker = (row // 8 + col // 8) % 2
            if checker:
                cwriter.addData4(0.55, 0.42, 0.22, 1.0)  # tan/brown
            else:
                cwriter.addData4(0.28, 0.52, 0.18, 1.0)  # green

    tris = GeomTriangles(Geom.UHStatic)
    for row in range(n - 1):
        for col in range(n - 1):
            i = row * n + col
            tris.addVertices(i, i + 1, i + n)
            tris.addVertices(i + 1, i + n + 1, i + n)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("terrain_geom")
    node.addGeom(geom)
    return node


class Terrain:
    def __init__(self, render, bullet_world):
        self._hmap = _build_heightmap()
        self._setup_visual(render)
        self._setup_physics(bullet_world)

    def _setup_visual(self, render):
        node = _build_geom(self._hmap)
        self.np = render.attachNewNode(node)
        self.np.setTwoSided(True)

    def _setup_physics(self, bullet_world):
        n = TILE_COUNT
        flat = [self._hmap[row][col] for row in range(n) for col in range(n)]
        min_h = min(flat)
        max_h = max(flat)
        half_range = (max_h - min_h) / 2.0

        # BulletHeightfieldShape requires a PNMImage; gray [0,1] maps to [-half_range, +half_range]
        img = PNMImage(n, n, 1)
        for row in range(n):
            for col in range(n):
                h = self._hmap[row][col]
                gray = (h - min_h) / (max_h - min_h) if max_h != min_h else 0.5
                img.setGray(col, row, gray)

        shape = BulletHeightfieldShape(img, half_range, ZUp)
        shape.setUseDiamondSubdivision(True)

        node = BulletRigidBodyNode("terrain_body")
        node.addShape(shape)
        self.body_np = self.np.attachNewNode(node)
        # Bullet centres the heightfield at its midpoint height
        mid_h = (min_h + max_h) / 2.0
        self.body_np.setPos(0, 0, mid_h)
        bullet_world.attachRigidBody(node)
