# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "manifold3d>=3.0",
#     "matplotlib>=3.8",
#     "networkx>=3.0",
#     "numpy>=1.26",
#     "scipy>=1.11",
#     "shapely>=2.0",
#     "trimesh>=4.4",
#     "typer>=0.12",
# ]
# ///
"""Parametric 3D-printable landscape picture frame for a Kindle Paperwhite 3.

The frame has two printed parts, both printed flat with no supports:

* ``frame-front``: the face with the window over the screen and a pocket behind it that
  the Kindle drops into from the back. The pocket's short walls have an opening on the
  port side (micro-USB cable and power button) and a finger notch on the other side.
* ``frame-back-stand`` or ``frame-back-wall``: the back plate that closes the pocket,
  screwed to the front with four M3 screws. The stand variant carries two fins that lean
  the frame back like a picture frame on a shelf; the wall variant has two keyholes.

A small ``fit-test`` part (one corner of the pocket) lets you check the clearance with a
ten-minute print before committing to the whole frame.

Every dimension is a field of :class:`FrameSpec`; the geometry is derived from it. Run
``uv run hardware/frame/frame.py --help`` for the commands. Units are millimeters.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
import typer
from shapely.geometry import LineString, Polygon, box
from trimesh.creation import cylinder as _cylinder
from trimesh.creation import extrude_polygon

logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, help=__doc__)

ENGINE = "manifold"
EPS = 0.01
"""Overlap so that unions and differences never share a coplanar face."""


@dataclass(frozen=True)
class FrameSpec:
    """All dimensions of the frame, in millimeters.

    The device block describes the Kindle Paperwhite 3 as it lies in landscape: its
    portrait *length* runs along X and its portrait *width* along Y. The portrait bottom
    edge (micro-USB port, power button) is on ``port_side``.

    Attributes
    ----------
    device_length, device_width, device_thickness
        Outer size of the Kindle (169 x 117 x 9.1 mm for the Paperwhite 3).
    device_corner_radius
        Radius of the Kindle's corners in the front view.
    screen_long, screen_short
        Active display area: 1448 x 1072 px at 300 ppi is 122.6 x 90.8 mm.
    bezel_top
        Distance from the Kindle's portrait top edge to the display. **Measure it on your
        device**; the default is an estimate. The bottom bezel is derived from it and the
        side bezels are derived from the width.
    port_side
        ``"left"`` or ``"right"``: where the port edge sits once the frame is on the shelf.
        With ``render.py`` rotating the landscape canvas 90 degrees counterclockwise, the
        image's top lands on the Kindle's portrait left edge, so the port edge is on the
        left when the picture is upright.
    clearance, depth_clearance
        Gap between the Kindle and the pocket on each side and behind it.
    rim
        Width of the frame's solid rim around the pocket. The rim on the side opposite to
        the port grows so that the window is centered in the frame (see
        ``center_window``).
    face_thickness, back_thickness
        Thickness of the face plate and of the back plate.
    window_margin
        The window is larger than the display by this much on every side.
    outer_corner_radius, window_corner_radius
        Corner radii of the frame outline and of the window.
    port_opening_width, notch_width
        Widths of the opening in the port-side wall and of the finger notch opposite.
    screw_inset, screw_tap_diameter, screw_clearance_diameter, screw_head_diameter,
    screw_head_depth, screw_hole_depth
        Four M3 screws at the corners: self-tapping blind holes in the front, clearance
        holes with a counterbore in the back plate.
    lean_angle_deg, leg_depth, leg_height, leg_thickness, leg_inset
        The stand's two fins: how far the frame leans back from vertical, how far the
        fins reach behind the plate, how far they climb up it, their thickness and their
        distance from the frame's ends.
    keyhole_spacing, keyhole_diameter, keyhole_slot_width, keyhole_slot_length,
    keyhole_head_pocket_width, keyhole_head_pocket_depth
        The wall variant's two keyholes in the top rim and the pockets in the front part
        that give the screw heads room.
    center_window
        Widen the rim opposite the port so the window sits in the middle of the frame.
    wall_keyholes
        Cut the keyholes in the wall plate and their head pockets in the front. Turn off
        for a rim narrower than 13.2 mm.
    fit_test_size
        Side of the square corner sample cut out of the front for the fit test.
    """

    device_length: float = 169.0
    device_width: float = 117.0
    device_thickness: float = 9.1
    device_corner_radius: float = 8.0
    screen_long: float = 1448 / 300 * 25.4
    screen_short: float = 1072 / 300 * 25.4
    bezel_top: float = 15.0
    port_side: str = "left"

    clearance: float = 0.4
    depth_clearance: float = 0.4
    rim: float = 14.0
    face_thickness: float = 3.0
    back_thickness: float = 3.0
    window_margin: float = 2.0
    outer_corner_radius: float = 6.0
    window_corner_radius: float = 2.0
    port_opening_width: float = 60.0
    notch_width: float = 25.0

    screw_inset: float = 7.0
    screw_tap_diameter: float = 2.5
    screw_clearance_diameter: float = 3.4
    screw_head_diameter: float = 6.5
    screw_head_depth: float = 1.5
    screw_hole_depth: float = 7.0

    lean_angle_deg: float = 15.0
    leg_depth: float = 40.0
    leg_height: float = 50.0
    leg_thickness: float = 4.0
    leg_inset: float = 35.0

    keyhole_spacing: float = 100.0
    keyhole_diameter: float = 6.5
    keyhole_slot_width: float = 4.2
    keyhole_slot_length: float = 3.75
    keyhole_head_pocket_width: float = 10.0
    keyhole_head_pocket_depth: float = 3.0

    center_window: bool = True
    wall_keyholes: bool = True
    fit_test_size: float = 40.0

    # Derived geometry. The pocket is the cavity the Kindle sits in; the window is the
    # opening in the face; both are placed in the frame's outline, whose origin is the
    # bottom-left corner of the front view with the port side on the left. A right-hand
    # port side mirrors the finished meshes.

    @property
    def bezel_bottom(self) -> float:
        """Portrait bottom bezel (the wide one with the logo), derived from the top."""
        return self.device_length - self.screen_long - self.bezel_top

    @property
    def bezel_side(self) -> float:
        """Portrait side bezel, derived from the width."""
        return (self.device_width - self.screen_short) / 2

    @property
    def pocket_size(self) -> tuple[float, float]:
        """Cavity size: the Kindle plus clearance on every side."""
        return (
            self.device_length + 2 * self.clearance,
            self.device_width + 2 * self.clearance,
        )

    @property
    def pocket_depth(self) -> float:
        """How far the cavity goes behind the face plate."""
        return self.device_thickness + self.depth_clearance

    @property
    def front_depth(self) -> float:
        """Total thickness of the front part."""
        return self.face_thickness + self.pocket_depth

    @property
    def window_size(self) -> tuple[float, float]:
        """Window in the face: the display plus the margin on every side."""
        return (
            self.screen_long + 2 * self.window_margin,
            self.screen_short + 2 * self.window_margin,
        )

    @property
    def outer_size(self) -> tuple[float, float]:
        """Outline of the frame."""
        pocket_w, pocket_h = self.pocket_size
        if self.center_window:
            # Distance from the pocket's left edge to the display's center.
            to_center = self.clearance + self.bezel_bottom + self.screen_long / 2
            width = 2 * (self.rim + to_center)
        else:
            width = pocket_w + 2 * self.rim
        return (width, pocket_h + 2 * self.rim)

    @property
    def pocket_origin(self) -> tuple[float, float]:
        """Bottom-left corner of the cavity in the frame's outline."""
        return (self.rim, self.rim)

    @property
    def window_origin(self) -> tuple[float, float]:
        """Bottom-left corner of the window in the frame's outline."""
        px, py = self.pocket_origin
        return (
            px + self.clearance + self.bezel_bottom - self.window_margin,
            py + self.clearance + self.bezel_side - self.window_margin,
        )

    @property
    def screw_positions(self) -> list[tuple[float, float]]:
        """Centers of the four corner screws."""
        w, h = self.outer_size
        i = self.screw_inset
        return [(i, i), (w - i, i), (i, h - i), (w - i, h - i)]

    @property
    def keyhole_positions(self) -> list[tuple[float, float]]:
        """Centers of the round part of the two keyholes, in the top rim."""
        w, h = self.outer_size
        strip_bottom = h - self.rim
        y = strip_bottom + 1.5 + self.keyhole_diameter / 2
        return [(w / 2 - self.keyhole_spacing / 2, y), (w / 2 + self.keyhole_spacing / 2, y)]

    def validate(self) -> None:
        """Reject combinations that cannot be printed or assembled.

        Raises
        ------
        ValueError
            With a message naming the field to change.
        """
        if self.port_side not in ("left", "right"):
            raise ValueError("port_side must be 'left' or 'right'")
        if self.bezel_bottom <= 0 or self.bezel_side <= 0:
            raise ValueError("bezel_top or the screen size leaves no bezel; check the device")
        if self.window_margin >= min(self.bezel_top, self.bezel_side):
            raise ValueError("window_margin must be smaller than the narrowest bezel")
        if self.screw_inset - self.screw_head_diameter / 2 < 1.5:
            raise ValueError("screw_inset leaves under 1.5 mm of wall around the screw head")
        if self.screw_inset + self.screw_head_diameter / 2 > self.rim:
            raise ValueError(
                "screw counterbores overlap the pocket; raise rim or lower screw_inset"
            )
        needed = 1.5 + self.keyhole_diameter + self.keyhole_slot_length + 1.5
        if self.wall_keyholes and self.rim < needed:
            raise ValueError(
                f"keyholes need a rim of at least {needed:.1f} mm; set wall_keyholes=false"
            )
        if self.keyhole_head_pocket_depth >= self.pocket_depth - 1:
            raise ValueError("keyhole_head_pocket_depth must leave 1 mm of wall")
        tilt = math.radians(self.lean_angle_deg)
        rise = self.leg_height - self.leg_depth * math.tan(tilt)
        if rise <= 0:
            raise ValueError("leg_height is too small for leg_depth and lean_angle_deg")
        overhang = math.degrees(math.atan(rise / self.leg_depth))
        if overhang > 50:
            raise ValueError(
                f"the fin's sloped edge overhangs {overhang:.0f} degrees from vertical; "
                "lower leg_height or raise leg_depth"
            )
        if self.leg_inset + self.leg_thickness / 2 > self.outer_size[0] / 2:
            raise ValueError("leg_inset places the fins past the middle of the frame")


# --- Geometry helpers -----------------------------------------------------------------


def rounded_rect(x: float, y: float, w: float, h: float, r: float) -> Polygon:
    """Rectangle with rounded corners, bottom-left corner at (x, y)."""
    r = min(r, w / 2, h / 2)
    if r <= 0:
        return box(x, y, x + w, y + h)
    return box(x + r, y + r, x + w - r, y + h - r).buffer(r, quad_segs=12)


def prism(polygon: Polygon, z0: float, z1: float) -> trimesh.Trimesh:
    """Extrude a polygon between two heights."""
    mesh = extrude_polygon(polygon, z1 - z0)
    mesh.apply_translation((0, 0, z0))
    return mesh


def slab(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> trimesh.Trimesh:
    """Axis-aligned box between two corners."""
    return prism(box(x0, y0, x1, y1), z0, z1)


def cylinder(x: float, y: float, z0: float, z1: float, diameter: float) -> trimesh.Trimesh:
    """Vertical cylinder of the given diameter between two heights."""
    mesh = _cylinder(radius=diameter / 2, height=z1 - z0, sections=48)
    mesh.apply_translation((x, y, (z0 + z1) / 2))
    return mesh


def stadium(x: float, y0: float, y1: float, width: float) -> Polygon:
    """Vertical slot with round ends, centered on x."""
    return LineString([(x, y0), (x, y1)]).buffer(width / 2, quad_segs=12)


def difference(body: trimesh.Trimesh, *cutters: trimesh.Trimesh) -> trimesh.Trimesh:
    """Subtract every cutter from the body."""
    return trimesh.boolean.difference([body, *cutters], engine=ENGINE)


def union(*parts: trimesh.Trimesh) -> trimesh.Trimesh:
    """Fuse parts into one mesh."""
    return trimesh.boolean.union(list(parts), engine=ENGINE)


def mirror_x(mesh: trimesh.Trimesh, width: float) -> trimesh.Trimesh:
    """Mirror a mesh across the vertical center line of the frame."""
    transform = np.eye(4)
    transform[0, 0] = -1
    transform[0, 3] = width
    mesh = mesh.copy()
    mesh.apply_transform(transform)
    mesh.fix_normals()
    return mesh


# --- Parts ----------------------------------------------------------------------------


def frame_front(spec: FrameSpec) -> trimesh.Trimesh:
    """The face plate with the window and the pocket behind it.

    Printed face down: Z = 0 is the visible face, the pocket opens toward +Z.
    """
    w, h = spec.outer_size
    pw, ph = spec.pocket_size
    px, py = spec.pocket_origin
    ww, wh = spec.window_size
    wx, wy = spec.window_origin
    ft, fd = spec.face_thickness, spec.front_depth
    body = prism(rounded_rect(0, 0, w, h, spec.outer_corner_radius), 0, fd)
    pocket_radius = spec.device_corner_radius + spec.clearance
    cutters = [
        prism(rounded_rect(px, py, pw, ph, pocket_radius), ft, fd + 1),
        prism(rounded_rect(wx, wy, ww, wh, spec.window_corner_radius), -1, ft + 1),
    ]
    # Opening for the cable and the power button in the port-side wall (left), and a
    # finger notch in the opposite wall to lift the Kindle out.
    y_mid = py + ph / 2
    cutters.append(
        slab(
            -1,
            y_mid - spec.port_opening_width / 2,
            ft,
            px + 1,
            y_mid + spec.port_opening_width / 2,
            fd + 1,
        )
    )
    cutters.append(
        slab(
            px + pw - 1,
            y_mid - spec.notch_width / 2,
            ft,
            w + 1,
            y_mid + spec.notch_width / 2,
            fd + 1,
        )
    )
    for sx, sy in spec.screw_positions:
        cutters.append(
            cylinder(sx, sy, fd - spec.screw_hole_depth, fd + 1, spec.screw_tap_diameter)
        )
    # Room for the screw heads behind the wall variant's keyholes.
    strip_bottom = h - spec.rim
    for kx, _ in spec.keyhole_positions if spec.wall_keyholes else []:
        pocket = rounded_rect(
            kx - spec.keyhole_head_pocket_width / 2,
            strip_bottom + 1.0,
            spec.keyhole_head_pocket_width,
            spec.rim - 2.5,
            2.0,
        )
        cutters.append(prism(pocket, fd - spec.keyhole_head_pocket_depth, fd + 1))
    mesh = difference(body, *cutters)
    return mirror_x(mesh, w) if spec.port_side == "right" else mesh


def _leg(spec: FrameSpec, x: float) -> trimesh.Trimesh:
    """One fin of the stand, standing on the back plate at X = x.

    The fin is a triangle in the Y-Z plane: its base lies on the plate from the bottom
    edge up to ``leg_height``, and its foot reaches ``leg_depth`` behind the plate, rising
    so that the foot line and the frame's bottom edge share the table when the frame
    leans back by ``lean_angle_deg``.
    """
    bt = spec.back_thickness
    tilt = math.radians(spec.lean_angle_deg)
    profile = Polygon(
        [
            (0.0, bt - EPS),
            (spec.leg_height, bt - EPS),
            (spec.leg_depth * math.tan(tilt), bt + spec.leg_depth),
        ]
    )
    fin = extrude_polygon(profile, spec.leg_thickness)
    # extrude_polygon builds (u, v, w) with w the extrusion; map to (x=w, y=u, z=v).
    transform = np.array(
        [
            [0.0, 0.0, 1.0, x],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    fin.apply_transform(transform)
    return fin


def frame_back(spec: FrameSpec, *, stand: bool) -> trimesh.Trimesh:
    """The back plate, with the stand's fins or the wall keyholes.

    Printed inner face down: Z = 0 touches the Kindle, the fins rise toward +Z.
    """
    w, h = spec.outer_size
    bt = spec.back_thickness
    plate = prism(rounded_rect(0, 0, w, h, spec.outer_corner_radius), 0, bt)
    cutters = []
    for sx, sy in spec.screw_positions:
        cutters.append(cylinder(sx, sy, -1, bt + 1, spec.screw_clearance_diameter))
        cutters.append(
            cylinder(sx, sy, bt - spec.screw_head_depth, bt + 1, spec.screw_head_diameter)
        )
    if not stand and spec.wall_keyholes:
        for kx, ky in spec.keyhole_positions:
            cutters.append(cylinder(kx, ky, -1, bt + 1, spec.keyhole_diameter))
            slot = stadium(kx, ky, ky + spec.keyhole_slot_length, spec.keyhole_slot_width)
            cutters.append(prism(slot, -1, bt + 1))
    mesh = difference(plate, *cutters)
    if stand:
        legs = [
            _leg(spec, spec.leg_inset - spec.leg_thickness / 2),
            _leg(spec, w - spec.leg_inset - spec.leg_thickness / 2),
        ]
        mesh = union(mesh, *legs)
    return mirror_x(mesh, w) if spec.port_side == "right" else mesh


def fit_test(spec: FrameSpec) -> trimesh.Trimesh:
    """One corner of the front part, to check the pocket fit with a short print."""
    front = frame_front(replace(spec, port_side="left"))
    px, py = spec.pocket_origin
    s = spec.fit_test_size
    corner = slab(-1, -1, -1, px + s, py + s, spec.front_depth + 1)
    return trimesh.boolean.intersection([front, corner], engine=ENGINE)


PARTS = {
    "frame-front": frame_front,
    "frame-back-stand": lambda spec: frame_back(spec, stand=True),
    "frame-back-wall": lambda spec: frame_back(spec, stand=False),
    "fit-test": fit_test,
}


# --- Preview --------------------------------------------------------------------------


def _draw(ax: Any, mesh: trimesh.Trimesh, elev: float, azim: float, title: str) -> None:
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    # Small triangles let the painter's algorithm order the faces correctly.
    vertices, faces = trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces, max_edge=8.0)
    mesh = trimesh.Trimesh(vertices, faces, process=False)

    light = np.array([0.3, -0.5, 0.8])
    light = light / np.linalg.norm(light)
    shade = 0.45 + 0.55 * np.clip(mesh.face_normals @ light, 0, 1)
    colors = np.stack([shade * 0.85, shade * 0.87, shade * 0.9, np.ones_like(shade)], axis=1)
    polys = Poly3DCollection(mesh.vertices[mesh.faces], facecolors=colors, edgecolors="none")
    polys.set_zsort("average")
    ax.add_collection3d(polys)
    lo, hi = mesh.bounds
    center, span = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(center[0] - span, center[0] + span)
    ax.set_ylim(center[1] - span, center[1] + span)
    ax.set_zlim(center[2] - span, center[2] + span)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title, fontsize=10)


def preview(meshes: dict[str, trimesh.Trimesh], output: Path) -> None:
    """Save a PNG with the parts seen from the useful angles."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    views = [
        ("frame-front", -60, -90, "Front, as seen on the shelf"),
        ("frame-front", 60, -90, "Front from behind: the pocket"),
        ("frame-back-stand", 35, -60, "Back plate with the stand fins"),
        ("frame-back-wall", 35, -60, "Back plate for the wall"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), subplot_kw={"projection": "3d"})
    for ax, (name, elev, azim, title) in zip(axes.flat, views, strict=True):
        _draw(ax, meshes[name], elev, azim, title)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --- Drawing --------------------------------------------------------------------------


def _section(
    mesh: trimesh.Trimesh, origin: tuple[float, float, float], normal: tuple[float, float, float]
) -> list[Polygon]:
    """Cut a mesh with a plane and return the filled polygons of the cut, in 2D.

    The 2D frame keeps the mesh's axes: a cut normal to Z returns (x, y), a cut normal to
    Y returns (x, z).
    """
    path = mesh.section(plane_origin=origin, plane_normal=normal)
    if path is None:
        return []
    axes = [i for i in range(3) if not normal[i]]
    planar, to_3d = path.to_2D()
    polys = list(planar.polygons_full)
    # Map the planar polygons back into world axes through the transform.
    result = []
    for poly in polys:
        ext = _to_world(np.array(poly.exterior.coords), to_3d)[:, axes]
        holes = [_to_world(np.array(h.coords), to_3d)[:, axes] for h in poly.interiors]
        result.append(Polygon(ext, holes))
    return result


def _to_world(points2d: np.ndarray, to_3d: np.ndarray) -> np.ndarray:
    homogeneous = np.column_stack([points2d, np.zeros(len(points2d)), np.ones(len(points2d))])
    return (to_3d @ homogeneous.T).T[:, :3]


def _fill(ax: Any, polys: list[Polygon], **style: Any) -> None:
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MplPath

    for poly in polys:
        verts = list(poly.exterior.coords)
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * (len(verts) - 2) + [MplPath.CLOSEPOLY]
        for hole in poly.interiors:
            h = list(hole.coords)
            verts += h
            codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(h) - 2) + [MplPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MplPath(verts, codes), **style))


def _dim(
    ax: Any,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text: str,
    offset: float = 8.0,
    vertical: bool = False,
) -> None:
    """Draw a dimension line with arrows and a label."""
    (x0, y0), (x1, y1) = p0, p1
    if vertical:
        xa = x0 + offset
        ax.plot([x0, xa + 2], [y0, y0], color="0.4", lw=0.6)
        ax.plot([x1, xa + 2], [y1, y1], color="0.4", lw=0.6)
        ax.annotate(
            "", (xa, y0), (xa, y1), arrowprops={"arrowstyle": "<->", "lw": 0.8, "color": "0.2"}
        )
        ax.text(xa + 2, (y0 + y1) / 2, text, fontsize=8, va="center", ha="left", rotation=90)
    else:
        ya = y0 + offset
        ax.plot([x0, x0], [y0, ya + 2], color="0.4", lw=0.6)
        ax.plot([x1, x1], [y1, ya + 2], color="0.4", lw=0.6)
        ax.annotate(
            "", (x0, ya), (x1, ya), arrowprops={"arrowstyle": "<->", "lw": 0.8, "color": "0.2"}
        )
        ax.text((x0 + x1) / 2, ya + 2, text, fontsize=8, ha="center", va="bottom")


def drawing(spec: FrameSpec, meshes: dict[str, trimesh.Trimesh], output: Path) -> None:
    """Save a dimensioned drawing: front view, side section, and the frame on a shelf."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    w, h = spec.outer_size
    ft, fd, bt = spec.face_thickness, spec.front_depth, spec.back_thickness
    front, back = meshes["frame-front"], meshes["frame-back-stand"]
    face = {"facecolor": "0.82", "edgecolor": "0.1", "lw": 0.8}
    hidden = {"facecolor": "none", "edgecolor": "0.35", "lw": 0.7, "linestyle": (0, (4, 3))}
    kindle = {"facecolor": "none", "edgecolor": "0.1", "lw": 0.8, "hatch": "////"}

    fig = plt.figure(figsize=(15, 10))
    grid = fig.add_gridspec(2, 2, width_ratios=[2.4, 1.0], height_ratios=[2.2, 1.0])
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[1, :]), fig.add_subplot(grid[0, 1])]
    fig.suptitle(
        f"Paperwhite Weather landscape frame: {w:.1f} x {h:.1f} mm, "
        f"port side {spec.port_side}, bezel_top {spec.bezel_top:.1f} mm (verify)",
        fontsize=11,
    )

    # Front view: the face, with the pocket, the wall openings and the screws behind it.
    ax = axes[0]
    ax.set_title("Front view (face section; hidden pocket dashed)", fontsize=9)
    _fill(ax, _section(front, (0, 0, ft / 2), (0, 0, 1)), **face)
    _fill(ax, _section(front, (0, 0, fd - 1), (0, 0, 1)), **hidden)
    _dim(ax, (0, h), (w, h), f"{w:.1f}")
    _dim(ax, (w, 0), (w, h), f"{h:.1f}", vertical=True)
    wx, wy = spec.window_origin
    ww, wh = spec.window_size
    _dim(ax, (wx, wy), (wx + ww, wy), f"window {ww:.1f}", offset=-14)
    _dim(ax, (wx + ww, wy), (wx + ww, wy + wh), f"{wh:.1f}", offset=-12, vertical=True)
    ax.set_xlim(-10, w + 25)
    ax.set_ylim(-25, h + 20)

    # Side section through the middle: face, pocket, Kindle, back plate and a fin.
    ax = axes[1]
    ax.set_title("Section at mid-height (Y = H/2), as assembled", fontsize=9)
    back_assembled = back.copy()
    back_assembled.apply_translation((0, 0, fd))
    _fill(ax, _section(front, (0, h / 2, 0), (0, 1, 0)), **face)
    _fill(ax, _section(back_assembled, (0, h / 2, 0), (0, 1, 0)), **face)
    px, _ = spec.pocket_origin
    device = box(
        px + spec.clearance,
        ft,
        px + spec.clearance + spec.device_length,
        ft + spec.device_thickness,
    )
    _fill(ax, [device], **kindle)
    _dim(ax, (0, 0), (0, fd + bt), f"{fd + bt:.1f}", offset=-14, vertical=True)
    _dim(ax, (w, ft), (w, fd), f"pocket {spec.pocket_depth:.1f}", offset=8, vertical=True)
    _dim(ax, (0, fd + bt), (px, fd + bt), f"rim {px:.0f}", offset=6)
    ax.text(
        w / 2,
        ft + spec.device_thickness / 2,
        "Kindle",
        fontsize=8,
        va="center",
        ha="center",
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1},
    )
    ax.text(w / 2, ft / 2, "face plate, cut by the window", fontsize=7, va="center", ha="center")
    ax.text(
        w / 2,
        fd + bt / 2,
        "back plate",
        fontsize=7,
        va="center",
        ha="center",
        bbox={"facecolor": "0.82", "edgecolor": "none", "pad": 1},
    )
    ax.annotate(
        "cable and power button opening",
        (px / 2, fd),
        (px / 2, fd + 22),
        fontsize=8,
        ha="left",
        arrowprops={"arrowstyle": "->", "lw": 0.8},
    )
    ax.annotate(
        "finger notch",
        (w - 8, fd),
        (w - 60, fd + 22),
        fontsize=8,
        ha="left",
        arrowprops={"arrowstyle": "->", "lw": 0.8},
    )
    ax.set_xlim(-25, w + 25)
    ax.set_ylim(-12, fd + bt + 32)

    # The frame standing on a shelf, seen from the side (a section across a fin).
    ax = axes[2]
    ax.set_title(
        f"On the shelf: leans back {spec.lean_angle_deg:.0f}° (section across a fin)", fontsize=9
    )
    x_fin = spec.leg_inset if spec.port_side == "left" else w - spec.leg_inset
    parts = _section(front, (x_fin, 0, 0), (1, 0, 0)) + _section(
        back_assembled, (x_fin, 0, 0), (1, 0, 0)
    )
    # Section across X returns (y, z): y up the frame, z toward the back. Pivot on the
    # frame's bottom-back edge (y = 0, z = fd + bt) and lean back.
    tilt = math.radians(spec.lean_angle_deg)
    pivot_z = fd + bt
    cos_t, sin_t = math.cos(tilt), math.sin(tilt)

    def lean(coords: np.ndarray) -> np.ndarray:
        y, z = coords[:, 0], coords[:, 1] - pivot_z
        # Horizontal axis points backward (away from the viewer), vertical is up.
        return np.column_stack([z * cos_t + y * sin_t, y * cos_t - z * sin_t])

    leaned = [
        Polygon(lean(np.array(p.exterior.coords)), [lean(np.array(i.coords)) for i in p.interiors])
        for p in parts
    ]
    _fill(ax, leaned, **face)
    ax.axhline(0, color="0.2", lw=1.2)
    ax.text(spec.leg_depth + 25, -6, "shelf", fontsize=8, ha="right")
    ax.text(-h * sin_t - pivot_z - 5, h / 2, "← viewer", fontsize=8, ha="right")
    ax.set_xlim(-h * sin_t - pivot_z - 15, spec.leg_depth + 30)
    ax.set_ylim(-15, h + 15)

    for ax in axes:
        ax.set_aspect("equal")
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)


# --- CLI ------------------------------------------------------------------------------


def _spec_from_overrides(overrides: list[str]) -> FrameSpec:
    """Build a spec from ``field=value`` strings."""
    spec = FrameSpec()
    values: dict[str, Any] = {}
    for item in overrides:
        key, _, raw = item.partition("=")
        if key not in FrameSpec.__dataclass_fields__:
            raise typer.BadParameter(f"unknown field {key!r}")
        current = getattr(spec, key)
        if isinstance(current, bool):
            values[key] = raw.lower() in ("1", "true", "yes")
        elif isinstance(current, float):
            values[key] = float(raw)
        else:
            values[key] = raw
    spec = replace(spec, **values)
    spec.validate()
    return spec


@app.command()
def build(
    output: Path = typer.Option(
        Path("hardware/frame/stl"), "--output", "-o", help="Directory for the STL files."
    ),
    preview_path: Path | None = typer.Option(
        None, "--preview", help="Also save a PNG preview here."
    ),
    drawing_path: Path | None = typer.Option(
        None, "--drawing", help="Also save a dimensioned PNG drawing here."
    ),
    set_: list[str] = typer.Option(
        [], "--set", "-s", help="Override a dimension, e.g. -s bezel_top=14.2."
    ),
) -> None:
    """Export every part as a binary STL."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    spec = _spec_from_overrides(set_)
    output.mkdir(parents=True, exist_ok=True)
    meshes: dict[str, trimesh.Trimesh] = {}
    for name, builder in PARTS.items():
        mesh = builder(spec)
        if not mesh.is_watertight:
            raise RuntimeError(f"{name} is not watertight; the geometry needs fixing")
        meshes[name] = mesh
        path = output / f"{name}.stl"
        mesh.export(path)
        size = mesh.extents
        logger.info(
            "%-18s %6.1f x %5.1f x %4.1f mm  %5.0f cm3  %s",
            name,
            size[0],
            size[1],
            size[2],
            mesh.volume / 1000,
            path,
        )
    if preview_path is not None:
        preview(meshes, preview_path)
        logger.info("preview written to %s", preview_path)
    if drawing_path is not None:
        drawing(spec, meshes, drawing_path)
        logger.info("drawing written to %s", drawing_path)


@app.command()
def dimensions(
    set_: list[str] = typer.Option(
        [], "--set", "-s", help="Override a dimension, e.g. -s bezel_top=14.2."
    ),
) -> None:
    """Print the derived dimensions without building anything."""
    spec = _spec_from_overrides(set_)
    w, h = spec.outer_size
    pw, ph = spec.pocket_size
    ww, wh = spec.window_size
    wx, wy = spec.window_origin
    lines = [
        f"frame outline        {w:.1f} x {h:.1f} mm",
        f"front part depth     {spec.front_depth:.1f} mm "
        f"(face {spec.face_thickness:.1f} + pocket {spec.pocket_depth:.1f})",
        f"back plate           {spec.back_thickness:.1f} mm, "
        f"stand fins add {spec.leg_depth:.1f} mm",
        f"pocket               {pw:.1f} x {ph:.1f} mm at {spec.pocket_origin}",
        f"window               {ww:.1f} x {wh:.1f} mm at ({wx:.1f}, {wy:.1f})",
        f"bezels top/bottom/side  {spec.bezel_top:.1f} / {spec.bezel_bottom:.1f} / "
        f"{spec.bezel_side:.1f} mm",
        f"port side            {spec.port_side}",
    ]
    typer.echo("\n".join(lines))


if __name__ == "__main__":
    app()
