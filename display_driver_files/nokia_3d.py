"""
nokia_3d.py - simple 3D solids and wireframes for Shapes (nokia_shapes.py)

Copy this file to the Pico next to nokia_shapes.py.

    from nokia_shapes import Shapes
    from nokia_3d import Object3D, make_cube, make_sphere, MODE_SOLID

    shapes = Shapes(screen)
    cube = Object3D(make_cube(), RED, radius_pixels=36)
    cube.set_position(64, 80)                    # where its centre is on the screen

    def draw_scene(screen):
        cube.draw(shapes)                        # a solid, lit cube

    angle = 0
    while True:
        angle += 3
        cube.set_rotation(angle, angle * 2, 0)   # turn it between frames
        screen.render(draw_scene, background=BLACK)

SHAPES YOU CAN MAKE (every size is a whole number, 1000 is a good default)
    make_cube(size)               make_box(width, height, depth)
    make_pyramid(radius, height, sides=4)       make_cone(radius, height, sides=12)
    make_cylinder(radius, height, sides=12)     make_sphere(radius, rings=6, segments=10)
    make_torus(major_radius, minor_radius, rings=12, sides=8)
    make_octahedron(radius)       make_icosahedron(radius)
You do not choose a size in pixels here. Object3D scales the shape so that
its farthest point is radius_pixels from its centre on the screen.
You can also build your own Mesh from a list of points and faces.

HOW A FRAME IS DRAWN
  1. Every point is turned, then moved to its place on the screen
     (with perspective, so near parts look bigger).
  2. Faces that point away from you are skipped.
  3. Each remaining face gets a brightness from the light.
  4. The faces are drawn from the farthest to the nearest, so near faces
     cover far ones. This works well for solid shapes. A shape with a
     hollow, like a torus, is right when seen from most sides.
This is done once per frame in prepare(). If you draw in strips mode
(screen.render calls your scene several times) the work is NOT repeated:
draw() only fills the faces again.

AXES AND TURNING
x goes right, y goes up, z goes away from you. Angles are whole degrees:
    set_rotation(about_x, about_y, about_z)
    about_y: like a turntable seen from above, a positive angle turns it clockwise
    about_x: a positive angle tips the top of the shape towards you
    about_z: a positive angle turns it clockwise as you see it
The turns are done in this order: about z, then x, then y.

MEMORY
A Mesh keeps its points and faces (a sphere with 6 rings and 10 segments is
about 4 KB). Each Object3D keeps a few small work lists for one frame.
All maths is whole numbers.
"""
import array

from nokia_shapes import sine, cosine, integer_square_root

MODE_SOLID = "solid"
MODE_WIREFRAME = "wireframe"
MODE_WIREFRAME_HIDDEN_LINES = "wireframe, hidden lines removed"

_ONE = 4096          # 1.0 in the turning numbers


def _reversed_tuple(values):
    count = len(values)
    return tuple(values[count - 1 - number] for number in range(count))


# ===============================
# MESH: the points and faces of a shape
# ===============================
class Mesh:
    def __init__(self, vertices, faces, reference_point=None):
        """vertices: list of (x, y, z) whole numbers.
        faces: list of tuples of point numbers going once around each face
        (three or more points, all in one flat plane).
        reference_point: leave it as None for solid shapes. The faces are
        turned so that they face away from the middle of the shape. For a
        shape with a hole (a torus) give a function that returns the nearest
        point of the 'core' of the shape: reference_point(x, y, z) -> (x, y, z)."""
        count = len(vertices)
        points = array.array("i", [0] * (3 * count))
        sum_x = 0
        sum_y = 0
        sum_z = 0
        farthest = 0
        for number in range(count):
            x, y, z = vertices[number]
            points[3 * number] = x
            points[3 * number + 1] = y
            points[3 * number + 2] = z
            sum_x += x
            sum_y += y
            sum_z += z
            distance_squared = x * x + y * y + z * z
            if distance_squared > farthest:
                farthest = distance_squared
        centre_x = sum_x // count
        centre_y = sum_y // count
        centre_z = sum_z // count

        self.vertices = points
        self.vertex_count = count
        self.radius = max(1, integer_square_root(farthest))

        self.faces = []
        self.face_normals = array.array("i", [0] * (3 * len(faces)))
        self.max_face_corners = 3

        for face_number in range(len(faces)):
            face = tuple(faces[face_number])
            corners = len(face)
            if corners > self.max_face_corners:
                self.max_face_corners = corners

            # the direction the face looks in (the sum around the edges
            # gives the same answer for any flat polygon) and its middle
            normal_x = 0
            normal_y = 0
            normal_z = 0
            middle_x = 0
            middle_y = 0
            middle_z = 0
            for corner in range(corners):
                a = face[corner] * 3
                b = face[(corner + 1) % corners] * 3
                ax = points[a]
                ay = points[a + 1]
                az = points[a + 2]
                bx = points[b]
                by = points[b + 1]
                bz = points[b + 2]
                normal_x += (ay - by) * (az + bz)
                normal_y += (az - bz) * (ax + bx)
                normal_z += (ax - bx) * (ay + by)
                middle_x += ax
                middle_y += ay
                middle_z += az
            middle_x //= corners
            middle_y //= corners
            middle_z //= corners

            # which way is outward?
            if reference_point is None:
                from_x, from_y, from_z = centre_x, centre_y, centre_z
            else:
                from_x, from_y, from_z = reference_point(middle_x, middle_y, middle_z)
            outward = (normal_x * (middle_x - from_x) + normal_y * (middle_y - from_y)
                       + normal_z * (middle_z - from_z))
            if outward < 0:
                face = _reversed_tuple(face)
                normal_x = -normal_x
                normal_y = -normal_y
                normal_z = -normal_z

            length = integer_square_root(normal_x * normal_x + normal_y * normal_y
                                         + normal_z * normal_z)
            if length == 0:
                length = 1
            self.face_normals[3 * face_number] = normal_x * _ONE // length
            self.face_normals[3 * face_number + 1] = normal_y * _ONE // length
            self.face_normals[3 * face_number + 2] = normal_z * _ONE // length
            self.faces.append(face)

        # every edge once, and which edges each face has
        edge_numbers = {}
        edge_list = []
        self.face_edges = []
        for face in self.faces:
            corners = len(face)
            numbers = []
            for corner in range(corners):
                a = face[corner]
                b = face[(corner + 1) % corners]
                key = (a, b) if a < b else (b, a)
                if key not in edge_numbers:
                    edge_numbers[key] = len(edge_list)
                    edge_list.append(key)
                numbers.append(edge_numbers[key])
            self.face_edges.append(tuple(numbers))
        self.edges = array.array("H", [0] * (2 * len(edge_list)))
        for number in range(len(edge_list)):
            self.edges[2 * number] = edge_list[number][0]
            self.edges[2 * number + 1] = edge_list[number][1]
        self.edge_count = len(edge_list)

    @property
    def face_count(self):
        return len(self.faces)

    def memory_bytes(self):
        """A rough size of this mesh in memory."""
        total = 4 * len(self.vertices) + 4 * len(self.face_normals) + 2 * len(self.edges)
        for face in self.faces:
            total += 8 + 4 * len(face)
        for numbers in self.face_edges:
            total += 8 + 4 * len(numbers)
        return total


# ===============================
# READY-MADE SHAPES
# ===============================
def make_box(width=1000, height=1000, depth=1000):
    """A box. width is along x, height along y, depth along z."""
    half_x = width // 2
    half_y = height // 2
    half_z = depth // 2
    vertices = []
    for number in range(8):
        vertices.append((half_x if number & 1 else -half_x,
                         half_y if number & 2 else -half_y,
                         half_z if number & 4 else -half_z))
    faces = [(1, 3, 7, 5), (0, 2, 6, 4), (2, 3, 7, 6), (0, 1, 5, 4), (4, 5, 7, 6), (0, 1, 3, 2)]
    return Mesh(vertices, faces)


def make_cube(size=1000):
    return make_box(size, size, size)


def _ring(radius, y, sides, first_degrees):
    points = []
    for number in range(sides):
        degrees = first_degrees + (360 * number) // sides
        points.append(((radius * cosine(degrees)) >> 12, y, (radius * sine(degrees)) >> 12))
    return points


def make_cylinder(radius=500, height=1000, sides=12):
    half = height // 2
    vertices = _ring(radius, half, sides, 0) + _ring(radius, -half, sides, 0)
    faces = [tuple(range(sides)), tuple(range(sides, 2 * sides))]
    for number in range(sides):
        following = (number + 1) % sides
        faces.append((number, following, sides + following, sides + number))
    return Mesh(vertices, faces)


def make_cone(radius=500, height=1000, sides=12):
    half = height // 2
    vertices = _ring(radius, -half, sides, 0) + [(0, half, 0)]
    faces = [tuple(range(sides))]
    for number in range(sides):
        faces.append((number, (number + 1) % sides, sides))
    return Mesh(vertices, faces)


def make_pyramid(radius=700, height=1000, sides=4):
    """A pyramid with 'sides' sides. With 4 sides, radius is the distance
    from the middle of the base to a corner of the base."""
    half = height // 2
    vertices = _ring(radius, -half, sides, 180 // sides) + [(0, half, 0)]
    faces = [tuple(range(sides))]
    for number in range(sides):
        faces.append((number, (number + 1) % sides, sides))
    return Mesh(vertices, faces)


def make_sphere(radius=1000, rings=6, segments=10):
    """A ball made of flat faces. More rings and segments look rounder and
    draw slower."""
    vertices = [(0, radius, 0)]
    for ring in range(1, rings):
        angle = (180 * ring) // rings
        y = (radius * cosine(angle)) >> 12
        ring_radius = (radius * sine(angle)) >> 12
        vertices += _ring(ring_radius, y, segments, 0)
    vertices.append((0, -radius, 0))
    bottom = len(vertices) - 1

    faces = []
    for number in range(segments):
        following = (number + 1) % segments
        faces.append((0, 1 + following, 1 + number))                       # top cap
    for ring in range(1, rings - 1):
        first = 1 + (ring - 1) * segments
        second = 1 + ring * segments
        for number in range(segments):
            following = (number + 1) % segments
            faces.append((first + number, first + following,
                          second + following, second + number))
    last = 1 + (rings - 2) * segments
    for number in range(segments):
        following = (number + 1) % segments
        faces.append((last + number, last + following, bottom))             # bottom cap
    return Mesh(vertices, faces)


def make_torus(major_radius=700, minor_radius=300, rings=12, sides=8):
    """A donut lying flat. major_radius: from the middle of the hole to the
    middle of the tube. minor_radius: the radius of the tube."""
    vertices = []
    for ring in range(rings):
        around = (360 * ring) // rings
        for side in range(sides):
            tube = (360 * side) // sides
            distance = major_radius + ((minor_radius * cosine(tube)) >> 12)
            vertices.append(((distance * cosine(around)) >> 12,
                             (minor_radius * sine(tube)) >> 12,
                             (distance * sine(around)) >> 12))
    faces = []
    for ring in range(rings):
        next_ring = (ring + 1) % rings
        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append((ring * sides + side, next_ring * sides + side,
                          next_ring * sides + next_side, ring * sides + next_side))

    def middle_of_tube(x, y, z):
        distance = integer_square_root(x * x + z * z)
        if distance == 0:
            return (0, 0, 0)
        return (x * major_radius // distance, 0, z * major_radius // distance)
    return Mesh(vertices, faces, middle_of_tube)


def make_octahedron(radius=1000):
    vertices = [(radius, 0, 0), (-radius, 0, 0), (0, radius, 0), (0, -radius, 0),
                (0, 0, radius), (0, 0, -radius)]
    faces = []
    for x_side in (0, 1):
        for y_side in (2, 3):
            for z_side in (4, 5):
                faces.append((x_side, y_side, z_side))
    return Mesh(vertices, faces)


def make_icosahedron(radius=1000):
    """A ball made of 20 triangles."""
    long_side = radius * 8507 // 10000          # radius / sqrt(1 + phi squared) * phi
    short_side = radius * 5257 // 10000        # radius / sqrt(1 + phi squared)
    a = short_side
    b = long_side
    vertices = [(-a, b, 0), (a, b, 0), (-a, -b, 0), (a, -b, 0),
                (0, -a, b), (0, a, b), (0, -a, -b), (0, a, -b),
                (b, 0, -a), (b, 0, a), (-b, 0, -a), (-b, 0, a)]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
             (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
             (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
             (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    return Mesh(vertices, faces)


# ===============================
# TURNING
# ===============================
def _matrix_multiply(first, second):
    result = [0] * 9
    for row in range(3):
        for column in range(3):
            result[3 * row + column] = (first[3 * row] * second[column]
                                        + first[3 * row + 1] * second[3 + column]
                                        + first[3 * row + 2] * second[6 + column]) >> 12
    return result


def rotation_matrix(about_x, about_y, about_z):
    """Nine numbers (a 3 x 3 turning table, 4096 means 1.0)."""
    sin_x = sine(about_x)
    cos_x = cosine(about_x)
    sin_y = sine(about_y)
    cos_y = cosine(about_y)
    sin_z = sine(about_z)
    cos_z = cosine(about_z)
    turn_z = [cos_z, sin_z, 0, -sin_z, cos_z, 0, 0, 0, _ONE]
    turn_x = [_ONE, 0, 0, 0, cos_x, sin_x, 0, -sin_x, cos_x]
    turn_y = [cos_y, 0, sin_y, 0, _ONE, 0, -sin_y, 0, cos_y]
    return _matrix_multiply(turn_y, _matrix_multiply(turn_x, turn_z))


def shade_colour(colour, brightness):
    """Make a 16-bit colour darker. brightness 256 keeps it, 128 halves it."""
    red = (((colour >> 11) & 31) * brightness) >> 8
    green = (((colour >> 5) & 63) * brightness) >> 8
    blue = ((colour & 31) * brightness) >> 8
    return (red << 11) | (green << 5) | blue


# ===============================
# OBJECT3D: one shape on the screen
# ===============================
class Object3D:
    def __init__(self, mesh, colour, radius_pixels=30, camera_distance_in_radii=4,
                 ambient=60, face_colours=None):
        """mesh                      a Mesh from the make_ functions
        colour                    the colour of the shape (16 bit)
        radius_pixels             how far its farthest point is from its middle
                                  on the screen, in pixels
        camera_distance_in_radii  how far away the camera is, counted in
                                  shape radii (at least 2). Small = strong
                                  perspective. None = no perspective at all.
        ambient                   light that every face gets, 0 to 255
        face_colours              optional list with one colour for every face"""
        self.mesh = mesh
        self.colour = colour
        self.radius_pixels = radius_pixels
        self.camera_distance_in_radii = camera_distance_in_radii
        self.ambient = ambient
        self.face_colours = face_colours

        self.centre_x = 64
        self.centre_y = 80
        self.about_x = 0
        self.about_y = 0
        self.about_z = 0
        self.set_light(-1800, 2200, -3000)

        count = mesh.vertex_count
        self._rotated_x = array.array("i", [0] * count)
        self._rotated_y = array.array("i", [0] * count)
        self._rotated_z = array.array("i", [0] * count)
        self._screen_x = array.array("i", [0] * count)
        self._screen_y = array.array("i", [0] * count)
        self._depth = array.array("i", [0] * mesh.face_count)
        self._colours = array.array("H", [0] * mesh.face_count)
        self._scratch = array.array("i", [0] * (2 * mesh.max_face_corners))
        self._edge_done = bytearray(mesh.edge_count)
        self._visible = []
        self._prepared = False
        self.bounds = (0, 0, 0, 0)

    # --- settings that change between frames ---
    def set_rotation(self, about_x, about_y, about_z=0):
        """Whole degrees, see the top of this file."""
        self.about_x = about_x
        self.about_y = about_y
        self.about_z = about_z
        self._prepared = False

    def set_position(self, centre_x, centre_y):
        """Where the middle of the shape is on the screen."""
        self.centre_x = centre_x
        self.centre_y = centre_y
        self._prepared = False

    def set_colour(self, colour):
        self.colour = colour
        self._prepared = False

    def set_light(self, x, y, z):
        """The direction TOWARDS the light, in the shape's own axes (x right,
        y up, z away from you). The default comes from the top left, in front."""
        length = integer_square_root(x * x + y * y + z * z)
        if length == 0:
            length = 1
        self._light_x = x * _ONE // length
        self._light_y = y * _ONE // length
        self._light_z = z * _ONE // length
        self._prepared = False

    @property
    def visible_face_count(self):
        """How many faces were drawn in the last frame."""
        return len(self._visible)

    def bounding_box(self):
        """(left, top, right, bottom) of the shape on the screen, after
        prepare(). Useful to clear only that part before the next frame."""
        if not self._prepared:
            self.prepare()
        return self.bounds

    # --- the work of one frame ---
    def prepare(self):
        """Turn and project the points, drop the faces that look away, light
        and sort the rest. draw() calls this by itself when something has
        changed, and does not repeat it for the next strip."""
        mesh = self.mesh
        matrix = rotation_matrix(self.about_x, self.about_y, self.about_z)
        m0, m1, m2, m3, m4, m5, m6, m7, m8 = matrix

        perspective = self.camera_distance_in_radii is not None
        if perspective:
            distance = max(2, self.camera_distance_in_radii) * mesh.radius
            focal = self.radius_pixels * distance // mesh.radius
        else:
            distance = 0
            focal = 0
        radius = mesh.radius
        radius_pixels = self.radius_pixels
        centre_x = self.centre_x
        centre_y = self.centre_y

        points = mesh.vertices
        rotated_x = self._rotated_x
        rotated_y = self._rotated_y
        rotated_z = self._rotated_z
        screen_x = self._screen_x
        screen_y = self._screen_y
        left = 32767
        top = 32767
        right = -32768
        bottom = -32768

        for number in range(mesh.vertex_count):
            x = points[3 * number]
            y = points[3 * number + 1]
            z = points[3 * number + 2]
            turned_x = (m0 * x + m1 * y + m2 * z) >> 12
            turned_y = (m3 * x + m4 * y + m5 * z) >> 12
            turned_z = (m6 * x + m7 * y + m8 * z) >> 12
            rotated_x[number] = turned_x
            rotated_y[number] = turned_y
            rotated_z[number] = turned_z
            if perspective:
                depth = turned_z + distance
                if depth < 1:
                    depth = 1
                px = centre_x + (turned_x * focal) // depth
                py = centre_y - (turned_y * focal) // depth
            else:
                px = centre_x + (turned_x * radius_pixels) // radius
                py = centre_y - (turned_y * radius_pixels) // radius
            screen_x[number] = px
            screen_y[number] = py
            if px < left:
                left = px
            if px > right:
                right = px
            if py < top:
                top = py
            if py > bottom:
                bottom = py
        self.bounds = (left, top, right, bottom)

        normals = mesh.face_normals
        faces = mesh.faces
        depth_of_face = self._depth
        colour_of_face = self._colours
        light_x = self._light_x
        light_y = self._light_y
        light_z = self._light_z
        ambient = self.ambient
        face_colours = self.face_colours
        visible = []

        for face_number in range(len(faces)):
            normal_x = normals[3 * face_number]
            normal_y = normals[3 * face_number + 1]
            normal_z = normals[3 * face_number + 2]
            turned_normal_x = (m0 * normal_x + m1 * normal_y + m2 * normal_z) >> 12
            turned_normal_y = (m3 * normal_x + m4 * normal_y + m5 * normal_z) >> 12
            turned_normal_z = (m6 * normal_x + m7 * normal_y + m8 * normal_z) >> 12

            face = faces[face_number]
            first = face[0]
            if perspective:
                looks_at_you = (turned_normal_x * rotated_x[first]
                                + turned_normal_y * rotated_y[first]
                                + turned_normal_z * (rotated_z[first] + distance)) < 0
            else:
                looks_at_you = turned_normal_z < 0
            if not looks_at_you:
                continue

            light = (turned_normal_x * light_x + turned_normal_y * light_y
                     + turned_normal_z * light_z) >> 12
            if light < 0:
                light = 0
            brightness = ambient + (((256 - ambient) * light) >> 12)
            if brightness > 256:
                brightness = 256

            if face_colours is not None:
                base = face_colours[face_number]
            else:
                base = self.colour
            colour_of_face[face_number] = shade_colour(base, brightness)

            total_depth = 0
            for vertex in face:
                total_depth += rotated_z[vertex]
            depth_of_face[face_number] = total_depth // len(face)
            visible.append(face_number)

        # far faces first, so that near faces are drawn over them
        visible.sort(key=lambda face_number: depth_of_face[face_number], reverse=True)
        self._visible = visible
        self._prepared = True

    # --- drawing ---
    def draw(self, shapes, mode=MODE_SOLID, edge_colour=None):
        """Draw the shape with a Shapes object.
        MODE_SOLID: lit faces. Give edge_colour to also draw the edges.
        MODE_WIREFRAME: every edge, as if the shape were made of wire.
        MODE_WIREFRAME_HIDDEN_LINES: only the edges that you can see.
        For the wireframe modes edge_colour is the line colour (default: the
        shape colour)."""
        if not self._prepared:
            self.prepare()
        mesh = self.mesh
        screen_x = self._screen_x
        screen_y = self._screen_y

        if mode == MODE_SOLID:
            faces = mesh.faces
            scratch = self._scratch
            colours = self._colours
            for face_number in self._visible:
                face = faces[face_number]
                corner = 0
                for vertex in face:
                    scratch[2 * corner] = screen_x[vertex]
                    scratch[2 * corner + 1] = screen_y[vertex]
                    corner += 1
                shapes.fill_polygon_flat(scratch, corner, colours[face_number])
                if edge_colour is not None:
                    for number in range(corner):
                        following = (number + 1) % corner
                        shapes.draw_line(scratch[2 * number], scratch[2 * number + 1],
                                         scratch[2 * following], scratch[2 * following + 1],
                                         edge_colour)
            return

        line_colour = self.colour if edge_colour is None else edge_colour
        edges = mesh.edges
        if mode == MODE_WIREFRAME:
            for number in range(mesh.edge_count):
                a = edges[2 * number]
                b = edges[2 * number + 1]
                shapes.draw_line(screen_x[a], screen_y[a], screen_x[b], screen_y[b], line_colour)
            return

        # hidden lines removed: the edges of the faces that look at you, each once
        done = self._edge_done
        for number in range(len(done)):
            done[number] = 0
        for face_number in self._visible:
            for edge_number in mesh.face_edges[face_number]:
                if done[edge_number] == 0:
                    done[edge_number] = 1
                    a = edges[2 * edge_number]
                    b = edges[2 * edge_number + 1]
                    shapes.draw_line(screen_x[a], screen_y[a], screen_x[b], screen_y[b],
                                     line_colour)
