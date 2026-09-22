# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "manifold3d>=3.0",
#     "matplotlib>=3.8",
#     "networkx>=3.0",
#     "numpy>=1.26",
#     "pillow>=10.0",
#     "rtree>=1.0",
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
    cradle_end_wall, cradle_front_wall, cradle_rear_wall, cradle_floor,
    cradle_front_height, cradle_rear_height, cradle_slot_clearance, cradle_depth,
    cradle_foot_width, cradle_foot_height
        The alternative design: a bar with a slot the Kindle drops into, leaning back by
        ``lean_angle_deg``, and two feet reaching back. The front wall stops below the
        display, the rear wall rises higher to support the back; the slot is the Kindle's
        thickness plus the clearance; the feet give the footprint its depth.
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

    cradle_end_wall: float = 8.0
    cradle_front_wall: float = 6.0
    cradle_rear_wall: float = 5.0
    cradle_floor: float = 3.0
    cradle_front_height: float = 13.0
    cradle_rear_height: float = 22.0
    cradle_slot_clearance: float = 0.6
    cradle_depth: float = 60.0
    cradle_foot_width: float = 14.0
    cradle_foot_height: float = 6.0

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
        if self.wall_keyholes and self.keyhole_head_pocket_depth >= self.pocket_depth - 1:
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
        lip = self.cradle_front_height - self.cradle_floor
        if lip >= self.bezel_side:
            limit = self.cradle_floor + self.bezel_side
            raise ValueError(
                f"the slotted stand's front lip ({lip:.1f} mm above the slot floor) would "
                f"cover the display; keep cradle_front_height under {limit:.1f}"
            )
        if lip < 5 or self.cradle_rear_height <= self.cradle_front_height:
            raise ValueError(
                "cradle_front_height must hold at least 5 mm and stay below cradle_rear_height"
            )
        if (
            self.cradle_foot_height >= self.cradle_front_height
            or self.cradle_depth
            <= self.cradle_front_wall + self.cradle_rear_wall + self.device_thickness
        ):
            raise ValueError("cradle_foot_height or cradle_depth leaves no stand under the slot")


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


def _tilted_axes(spec: FrameSpec) -> tuple[np.ndarray, np.ndarray]:
    """Unit vectors along a leaning Kindle: up its face, and out of its back."""
    tilt = math.radians(spec.lean_angle_deg)
    up = np.array([0.0, math.cos(tilt), math.sin(tilt)])
    back = np.array([0.0, -math.sin(tilt), math.cos(tilt)])
    return up, back


def cradle_layout(spec: FrameSpec) -> dict[str, float]:
    """Positions inside the cradle: slot origin, slot width, bar size.

    The slot's bottom-front corner is ``(slot_x, cradle_floor, slot_z)``; the slot runs
    ``slot_width`` along the Kindle's back normal and ``slot_length`` along X.
    """
    slot_width = spec.device_thickness + spec.cradle_slot_clearance
    slot_length = spec.device_length + 2 * spec.clearance
    tilt = math.radians(spec.lean_angle_deg)

    # The rear wall's inner face at a height y: z = slot_z + slot_width*cos + (y-floor)*tan.
    def rear_wall_z(y: float) -> float:
        return (
            spec.cradle_front_wall
            + slot_width * math.cos(tilt)
            + (y - spec.cradle_floor) * math.tan(tilt)
        )

    return {
        "slot_x": spec.cradle_end_wall,
        "slot_z": spec.cradle_front_wall,
        "slot_width": slot_width,
        "slot_length": slot_length,
        "length": slot_length + 2 * spec.cradle_end_wall,
        "rear_box_z": rear_wall_z(spec.cradle_front_height),
        "bar_depth": rear_wall_z(spec.cradle_rear_height) + spec.cradle_rear_wall,
    }


def stand_cradle(spec: FrameSpec) -> trimesh.Trimesh:
    """The alternative stand: a bar with a leaning slot for the Kindle and two feet.

    Printed as it stands, bottom on the bed. The slot's walls lean by
    ``lean_angle_deg``, well within what prints without supports.
    """
    lay = cradle_layout(spec)
    length, bar_depth = lay["length"], lay["bar_depth"]
    front = slab(0, 0, 0, length, spec.cradle_front_height, bar_depth)
    rear = slab(0, 0, lay["rear_box_z"], length, spec.cradle_rear_height, bar_depth)
    feet = [
        slab(0, 0, 0, spec.cradle_foot_width, spec.cradle_foot_height, spec.cradle_depth),
        slab(
            length - spec.cradle_foot_width,
            0,
            0,
            length,
            spec.cradle_foot_height,
            spec.cradle_depth,
        ),
    ]
    body = union(front, rear, *feet)
    up, back = _tilted_axes(spec)
    origin = np.array([0.0, spec.cradle_floor, lay["slot_z"]])
    reach = spec.cradle_rear_height + 5
    corners = [
        origin,
        origin + lay["slot_width"] * back,
        origin + lay["slot_width"] * back + reach * up,
        origin + reach * up,
    ]
    profile = Polygon([(c[1], c[2]) for c in corners])
    slot = extrude_polygon(profile, lay["slot_length"])
    slot.apply_transform(
        np.array([[0, 0, 1, lay["slot_x"]], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=float)
    )
    return difference(body, slot)


PARTS = {
    "frame-front": frame_front,
    "frame-back-stand": lambda spec: frame_back(spec, stand=True),
    "frame-back-wall": lambda spec: frame_back(spec, stand=False),
    "fit-test": fit_test,
    "stand-cradle": stand_cradle,
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


# --- Rendering ------------------------------------------------------------------------
#
# A small software renderer (perspective camera, z-buffer, Lambert shading, one textured
# quad for the display) so the finished frame can be pictured without OpenGL.


@dataclass
class Surface:
    """A mesh with a flat color, or a texture sampled through per-vertex UVs."""

    mesh: trimesh.Trimesh
    color: tuple[float, float, float]
    texture: np.ndarray | None = None
    uv: np.ndarray | None = None


def _normalize(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _lean_matrix(spec: FrameSpec) -> np.ndarray:
    """Lean the assembled frame back about its bottom-back edge, which lands on Y = 0."""
    tilt = math.radians(spec.lean_angle_deg)
    c, s = math.cos(tilt), math.sin(tilt)
    zp = spec.front_depth + spec.back_thickness
    return np.array(
        [[1, 0, 0, 0], [0, c, -s, zp * s], [0, s, c, -zp * c], [0, 0, 0, 1]], dtype=float
    )


def _quad(points: list[tuple[float, float, float]]) -> trimesh.Trimesh:
    """Two triangles over four corners given in order around the quad."""
    return trimesh.Trimesh(np.array(points, dtype=float), [[0, 1, 2], [0, 2, 3]], process=False)


def _cable(port: np.ndarray, floor_y: float) -> trimesh.Trimesh:
    """A micro-USB cable leaving the port (a world point) and drooping onto the shelf."""
    control = np.array(
        [
            port,
            port + [-45, 0, 0],
            [port[0] - 75, floor_y + 6, port[2] + 5],
            [port[0] - 150, floor_y + 1.8, port[2] + 30],
        ]
    )
    t = np.linspace(0, 1, 28)[:, None]
    path = (
        (1 - t) ** 3 * control[0]
        + 3 * (1 - t) ** 2 * t * control[1]
        + 3 * (1 - t) * t**2 * control[2]
        + t**3 * control[3]
    )
    pieces = []
    for a, b in zip(path[:-1], path[1:], strict=True):
        pieces.append(_cylinder(radius=1.8, segment=[a, b], sections=12))
        ball = trimesh.creation.icosphere(subdivisions=1, radius=1.8)
        ball.apply_translation(b)
        pieces.append(ball)
    return trimesh.util.concatenate(pieces)


def _shelf(
    bounds: tuple[float, float, float, float], footprint: tuple[float, float, float, float]
) -> Surface:
    """A shelf with a soft shadow painted under the footprint (x0, x1, z0, z1)."""
    from PIL import Image, ImageDraw, ImageFilter

    x0, x1, z0, z1 = bounds
    fx0, fx1, fz0, fz1 = footprint
    size = 512
    shadow = Image.new("L", (size, size), 255)
    draw = ImageDraw.Draw(shadow)
    sx = lambda x: (x - x0) / (x1 - x0) * size  # noqa: E731
    sz = lambda z: (z - z0) / (z1 - z0) * size  # noqa: E731
    draw.rectangle([sx(fx0 - 4), sz(fz0 - 8), sx(fx1 + 4), sz(fz1 + 6)], fill=150)
    draw.rectangle([sx(fx0 - 2), sz(fz0 - 3), sx(fx1 + 2), sz(fz0 + 9)], fill=90)
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    tone = np.asarray(shadow, dtype=float) / 255
    base = np.array([0.80, 0.75, 0.68])
    texture = tone[..., None] * base[None, None, :]
    quad = _quad([(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)])
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    return Surface(quad, (1, 1, 1), texture, uv)


def _kindle(spec: FrameSpec, screen: Path, placement: np.ndarray) -> list[Surface]:
    """The Kindle (body, display, cable) placed in the world by a 4x4 transform.

    In its own coordinates the Kindle lies in landscape with the port edge at X = 0,
    its front face at Z = 0 and its back toward +Z.
    """
    from PIL import Image

    body = prism(
        rounded_rect(0, 0, spec.device_length, spec.device_width, spec.device_corner_radius),
        0.02,
        spec.device_thickness,
    )
    x0, y0 = spec.bezel_bottom, spec.bezel_side
    x1, y1 = x0 + spec.screen_long, y0 + spec.screen_short
    z = -0.05
    display = _quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)])
    display_uv = np.array([[0, 1], [1, 1], [1, 0], [0, 0]], dtype=float)
    gray = np.asarray(Image.open(screen).convert("L"), dtype=float) / 255
    ink = 0.14 + 0.70 * gray
    texture = np.stack([ink, ink * 0.99, ink * 0.95], axis=-1)
    body.apply_transform(placement)
    display.apply_transform(placement)
    port_local = np.array([0.0, spec.device_width / 2, spec.device_thickness / 2, 1.0])
    port = (placement @ port_local)[:3]
    cable = _cable(port, 0.0)
    return [
        Surface(body, (0.13, 0.13, 0.14)),
        Surface(display, (1, 1, 1), texture, display_uv),
        Surface(cable, (0.10, 0.10, 0.11)),
    ]


def _rotation_x(angle_deg: float) -> np.ndarray:
    tilt = math.radians(angle_deg)
    c, s = math.cos(tilt), math.sin(tilt)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], dtype=float)


def _translation(x: float, y: float, z: float) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


FRAME_COLOR = (0.88, 0.88, 0.86)


def scene(
    spec: FrameSpec, meshes: dict[str, trimesh.Trimesh], screen: Path, design: str, back: str
) -> list[Surface]:
    """The chosen design with the Kindle in it, leaning on a shelf.

    Parameters
    ----------
    spec
        The dimensions.
    meshes
        The built parts, by name.
    screen
        A landscape dashboard screenshot shown on the display.
    design
        ``"frame"`` (the picture frame) or ``"cradle"`` (the slotted stand).
    back
        For the frame, ``"stand"`` or ``"wall"``: which back plate to show.
    """
    if design == "frame":
        lean = _lean_matrix(spec)
        front = meshes["frame-front"].copy()
        plate = meshes[f"frame-back-{back}"].copy()
        plate.apply_translation((0, 0, spec.front_depth))
        front.apply_transform(lean)
        plate.apply_transform(lean)
        px, py = spec.pocket_origin
        placement = lean @ _translation(
            px + spec.clearance, py + spec.clearance, spec.face_thickness
        )
        surfaces = [Surface(front, FRAME_COLOR), Surface(plate, FRAME_COLOR)]
        width = spec.outer_size[0]
        footprint = (0.0, width, -6.0, spec.leg_depth if back == "stand" else 4.0)
    elif design == "cradle":
        lay = cradle_layout(spec)
        cradle = meshes["stand-cradle"].copy()
        _, back_normal = _tilted_axes(spec)
        seat = (
            np.array([lay["slot_x"] + spec.clearance, spec.cradle_floor, lay["slot_z"]])
            + back_normal * spec.cradle_slot_clearance / 2
        )
        placement = _translation(*seat) @ _rotation_x(spec.lean_angle_deg)
        surfaces = [Surface(cradle, FRAME_COLOR)]
        width = lay["length"]
        footprint = (0.0, width, 0.0, spec.cradle_depth)
    else:
        raise ValueError("design must be 'frame' or 'cradle'")
    surfaces += _kindle(spec, screen, placement)
    surfaces.append(_shelf((-220, width + 220, -320, 260), footprint))
    return surfaces


def _project(
    points: np.ndarray, eye: np.ndarray, basis: np.ndarray, focal: float, size: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cam = (points - eye) @ basis.T
    z = cam[:, 2]
    safe = np.where(z > 1e-6, z, 1e-6)
    return size[0] / 2 + focal * cam[:, 0] / safe, size[1] / 2 - focal * cam[:, 1] / safe, z


def rasterize(
    surfaces: list[Surface],
    eye: tuple[float, float, float],
    target: tuple[float, float, float],
    size: tuple[int, int],
    focal: float,
) -> np.ndarray:
    """Render the surfaces with a pinhole camera into an RGB float image."""
    eye_v = np.array(eye, dtype=float)
    forward = _normalize(np.array(target, dtype=float) - eye_v)
    right = _normalize(np.cross(np.array([0.0, 1.0, 0.0]), forward))
    up = np.cross(forward, right)
    basis = np.stack([right, up, forward])
    width, height = size
    lights = [
        (_normalize(np.array([-0.45, 0.75, -0.55])), 0.55),
        (_normalize(np.array([0.7, 0.25, -0.4])), 0.22),
    ]
    ambient = 0.33

    ys, xs = np.mgrid[0:height, 0:width]
    image = np.empty((height, width, 3))
    image[..., :] = 0.965 - 0.05 * (ys / height)[..., None]
    zbuf = np.full((height, width), np.inf)

    for surface in surfaces:
        verts, faces = surface.mesh.vertices, surface.mesh.faces
        sx, sy, sz = _project(verts, eye_v, basis, focal, size)
        normals = surface.mesh.face_normals
        centers = verts[faces].mean(axis=1)
        facing = np.einsum("ij,ij->i", normals, eye_v - centers) < 0
        normals = np.where(facing[:, None], -normals, normals)
        shade = np.full(len(faces), ambient)
        for direction, strength in lights:
            shade += strength * np.clip(normals @ direction, 0, None)
        shade = np.clip(shade, 0, 1.15)
        color = np.array(surface.color)
        for i, (a, b, c) in enumerate(faces):
            if sz[a] < 1 or sz[b] < 1 or sz[c] < 1:
                continue
            xa, xb, xc = sx[a], sx[b], sx[c]
            ya, yb, yc = sy[a], sy[b], sy[c]
            x0, x1 = (
                max(int(np.floor(min(xa, xb, xc))), 0),
                min(int(np.ceil(max(xa, xb, xc))), width - 1),
            )
            y0, y1 = (
                max(int(np.floor(min(ya, yb, yc))), 0),
                min(int(np.ceil(max(ya, yb, yc))), height - 1),
            )
            if x0 > x1 or y0 > y1:
                continue
            det = (yb - yc) * (xa - xc) + (xc - xb) * (ya - yc)
            if abs(det) < 1e-9:
                continue
            gx = xs[y0 : y1 + 1, x0 : x1 + 1] + 0.5
            gy = ys[y0 : y1 + 1, x0 : x1 + 1] + 0.5
            wa = ((yb - yc) * (gx - xc) + (xc - xb) * (gy - yc)) / det
            wb = ((yc - ya) * (gx - xc) + (xa - xc) * (gy - yc)) / det
            wc = 1 - wa - wb
            inside = (wa >= 0) & (wb >= 0) & (wc >= 0)
            if not inside.any():
                continue
            inv_z = wa / sz[a] + wb / sz[b] + wc / sz[c]
            depth = 1 / np.where(inv_z > 0, inv_z, 1e-9)
            window = zbuf[y0 : y1 + 1, x0 : x1 + 1]
            mask = inside & (depth < window)
            if not mask.any():
                continue
            if surface.texture is not None and surface.uv is not None:
                uv = (
                    wa[..., None] * surface.uv[a] / sz[a]
                    + wb[..., None] * surface.uv[b] / sz[b]
                    + wc[..., None] * surface.uv[c] / sz[c]
                ) * depth[..., None]
                th, tw = surface.texture.shape[:2]
                ti = np.clip((uv[..., 1] * (th - 1)).round().astype(int), 0, th - 1)
                tj = np.clip((uv[..., 0] * (tw - 1)).round().astype(int), 0, tw - 1)
                base = surface.texture[ti, tj]
            else:
                base = np.broadcast_to(color, mask.shape + (3,))
            pixels = base * shade[i]
            target_px = image[y0 : y1 + 1, x0 : x1 + 1]
            target_px[mask] = pixels[mask]
            window[mask] = depth[mask]
    return np.clip(image, 0, 1)


def render(
    spec: FrameSpec,
    meshes: dict[str, trimesh.Trimesh],
    screen: Path,
    output: Path,
    design: str = "frame",
    back: str = "stand",
) -> None:
    """Save a picture of the finished piece: on a shelf from the front, and from behind."""
    from PIL import Image

    output.parent.mkdir(parents=True, exist_ok=True)
    surfaces = scene(spec, meshes, screen, design, back)
    solid = np.concatenate([s.mesh.bounds for s in surfaces[:-1]])
    lo, hi = solid.min(axis=0), solid.max(axis=0)
    center = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2 * 0.95, (lo[2] + hi[2]) / 2])
    scale = 2
    hero_size = (1600 * scale, 1000 * scale)
    small_size = (790 * scale, 560 * scale)
    views = [
        (center + [-210, 81, -428], center, hero_size, 1.75 * hero_size[0] / 2),
        (center + [0, -9, -568], center + [0, 0, -8], small_size, 2.9 * small_size[0] / 2),
        (center + [-330, 121, 292], center + [0, -24, 12], small_size, 1.7 * small_size[0] / 2),
    ]
    frames = []
    for eye, target, size, focal in views:
        pixels = rasterize(surfaces, tuple(eye), tuple(target), size, focal)
        frame = Image.fromarray((pixels * 255).round().astype(np.uint8))
        frames.append(frame.resize((size[0] // scale, size[1] // scale), Image.LANCZOS))
    gap = 20
    sheet = Image.new("RGB", (1600, 1000 + gap + 560), (246, 246, 244))
    sheet.paste(frames[0], (0, 0))
    sheet.paste(frames[1], (0, 1000 + gap))
    sheet.paste(frames[2], (1600 - 790, 1000 + gap))
    sheet.save(output)


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


@app.command("render")
def render_command(
    output: Path = typer.Option(
        Path("hardware/frame/img/frame-render.png"), "--output", "-o", help="PNG to write."
    ),
    screen: Path = typer.Option(
        Path("docs/img/minimal-landscape-view.png"),
        "--screen",
        help="Landscape dashboard screenshot to show on the display.",
    ),
    design: str = typer.Option(
        "frame", "--design", help="frame (picture frame) or cradle (slotted stand)."
    ),
    back: str = typer.Option(
        "stand", "--back", help="Back plate of the frame to show: stand or wall."
    ),
    set_: list[str] = typer.Option(
        [], "--set", "-s", help="Override a dimension, e.g. -s bezel_top=14.2."
    ),
) -> None:
    """Picture the finished piece with the Kindle in it, from the front and from behind."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if design not in ("frame", "cradle"):
        raise typer.BadParameter("--design must be 'frame' or 'cradle'")
    if back not in ("stand", "wall"):
        raise typer.BadParameter("--back must be 'stand' or 'wall'")
    spec = _spec_from_overrides(set_)
    meshes = {name: builder(spec) for name, builder in PARTS.items()}
    render(spec, meshes, screen, output, design, back)
    logger.info("render written to %s", output)


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
