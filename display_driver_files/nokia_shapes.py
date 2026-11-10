"""
nokia_shapes.py - 2D shapes, clipping and sprites for Screen (nokia_graphics.py)

Copy this file to the Pico next to nokia_graphics.py.
Also copy nokia_shapes_fast.py to make it much faster. It is optional: if it
is missing or does not work, slower Python code is used and draws exactly
the same pixels.

    from nokia_shapes import Shapes, Sprite

    shapes = Shapes(screen)          # once, after creating Screen

    def draw_scene(screen):
        shapes.fill_triangle(10, 10, 60, 20, 30, 70, RED)
        shapes.draw_arc(64, 80, 40, 0, 270, GREEN, thickness=5)
        shapes.fill_rounded_rectangle(10, 100, 100, 40, 8, BLUE)

    screen.render(draw_scene, background=BLACK)

ANGLES
All angles are whole degrees. 0 points right, 90 points down, 180 points
left and 270 points up. Angles grow clockwise on the screen.
For stars and regular polygons, rotation 0 puts the first point straight up.

CLIPPING
shapes.set_clip(x, y, width, height) makes every Shapes call draw only
inside that rectangle. shapes.clear_clip() goes back to the whole screen.
The clip does not affect Screen's own drawing calls or Font.

MEMORY
Nothing here keeps a picture. Shapes are drawn row by row straight into the
Screen buffer, and in strips mode only the rows of the current band are
worked on. Shapes keeps a few small work lists (see memory_bytes()).
A Sprite keeps its pixels in RAM: width x height x 2 bytes.
"""
import array
import framebuf
import gc

# sine of 0..90 degrees, multiplied by 4096
_SINE_TABLE = array.array("h", (
    0, 71, 143, 214, 286, 357, 428, 499, 570, 641, 711, 782, 852, 921, 991,
    1060, 1129, 1198, 1266, 1334, 1401, 1468, 1534, 1600, 1666, 1731, 1796,
    1860, 1923, 1986, 2048, 2110, 2171, 2231, 2290, 2349, 2408, 2465, 2522,
    2578, 2633, 2687, 2741, 2793, 2845, 2896, 2946, 2996, 3044, 3091, 3138,
    3183, 3228, 3271, 3314, 3355, 3396, 3435, 3474, 3511, 3547, 3582, 3617,
    3650, 3681, 3712, 3742, 3770, 3798, 3824, 3849, 3873, 3896, 3917, 3937,
    3956, 3974, 3991, 4006, 4021, 4034, 4046, 4056, 4065, 4074, 4080, 4086,
    4090, 4094, 4095, 4096))

# How many corners the work list for polygon edges holds before a bigger
# one has to be made for a single call.
_CROSSING_LIST_SIZE = 64


def sine(degrees):
    """Sine of a whole number of degrees, multiplied by 4096 (no floats)."""
    degrees %= 360
    if degrees <= 90:
        return _SINE_TABLE[degrees]
    if degrees <= 180:
        return _SINE_TABLE[180 - degrees]
    if degrees <= 270:
        return -_SINE_TABLE[degrees - 180]
    return -_SINE_TABLE[360 - degrees]


def cosine(degrees):
    """Cosine of a whole number of degrees, multiplied by 4096."""
    return sine(degrees + 90)


def integer_square_root(value):
    """Largest whole number whose square is not more than value."""
    if value <= 0:
        return 0
    root = value
    guess = (root + 1) >> 1
    while guess < root:
        root = guess
        guess = (root + value // root) >> 1
    return root


def _divide_rounded(numerator, denominator):
    """numerator / denominator rounded to the nearest whole number.
    The denominator may be negative."""
    return (2 * numerator + denominator) // (2 * denominator)


def _ellipse_half_width(radius_x, radius_y, row_offset):
    """Half the width of an ellipse row that is row_offset rows from the
    centre row. The shape is the ellipse with half a pixel added all round,
    so a circle of radius r is 2r+1 pixels wide at its centre."""
    full_x = 2 * radius_x + 1
    full_y = 2 * radius_y + 1
    return integer_square_root(
        (full_x * full_x * (full_y * full_y - 4 * row_offset * row_offset))
        // (4 * full_y * full_y))


def _ellipse_fits_fast_helper(radius_x, radius_y):
    # The fast helper uses 32-bit numbers. This keeps the sums inside them.
    return (2 * radius_x + 1) * (2 * radius_y + 1) < 32768


class _TestScreen:
    """A tiny stand-in for Screen, used only to check the fast helpers."""
    def __init__(self, width, height, band_rows, band_top):
        self.width = width
        self.height = height
        self.strip_height = band_rows
        self._origin_y = band_top
        self._tracking = False
        self._buffer = bytearray(width * band_rows * 2)
        self._frame = framebuf.FrameBuffer(self._buffer, width, band_rows, framebuf.RGB565)

    def _mark_dirty(self, top, bottom):
        pass


def _draw_test_pictures(shapes):
    # Uses every fast helper, with shapes partly outside the picture and
    # with and without a clip rectangle.
    shapes.fill_triangle(-6, -4, 30, 8, 10, 40, 0xF800)
    shapes.fill_polygon([(20, 2), (42, 8), (34, 18), (46, 30), (24, 26), (16, 14)], 0x07E0)
    shapes.draw_polygon([(2, 20), (14, 44), (30, 36)], 0xFFE0, thickness=3)
    shapes.fill_ellipse(14, 24, 12, 7, 0x001F)
    shapes.draw_ellipse(30, 20, 14, 9, 0xFFFF)
    shapes.fill_circle(36, 40, 7, 0x07FF)
    shapes.draw_circle(5, 40, 9, 0xF81F)
    shapes.fill_rounded_rectangle(4, 6, 30, 20, 6, 0xFD20)
    shapes.draw_rounded_rectangle(8, 14, 28, 26, 7, 0x0410)
    shapes.fill_ring(24, 24, 15, 8, 0x8410)
    shapes.draw_arc(20, 24, 16, 20, 300, 0xFFFF, thickness=5)
    shapes.draw_arc(20, 24, 12, 100, 130, 0xF800)
    shapes.fill_pie(30, 22, 14, 200, 500, 0x07E0)
    shapes.draw_line(0, 0, 47, 47, 0xFFFF, thickness=4, round_caps=True)
    shapes.fill_star(22, 24, 18, 7, 5, 0xFFE0, rotation_degrees=20)
    shapes.set_clip(10, 8, 24, 30)
    shapes.fill_circle(12, 20, 14, 0x07FF)
    shapes.draw_ellipse(24, 24, 18, 12, 0xF800)
    shapes.fill_rounded_rectangle(2, 2, 40, 40, 9, 0x001F)
    shapes.fill_ring(22, 22, 17, 10, 0xFFE0)
    shapes.clear_clip()


def _fast_shapes_work(fast_module):
    """Draw the same pictures with and without the fast helpers (once for
    the whole picture and once for a band of it) and compare the pixels."""
    try:
        for band_rows, band_top in ((48, 0), (16, 16)):
            slow_screen = _TestScreen(48, 48, band_rows, band_top)
            fast_screen = _TestScreen(48, 48, band_rows, band_top)
            _draw_test_pictures(Shapes(slow_screen, use_fast_helpers=False))
            _draw_test_pictures(Shapes(fast_screen, _fast_module=fast_module))
            if slow_screen._buffer != fast_screen._buffer:
                return False
            # the test must really have drawn something
            if slow_screen._buffer == bytearray(len(slow_screen._buffer)):
                return False
        return True
    except Exception:
        return False


class Shapes:
    def __init__(self, screen, use_fast_helpers=True, _fast_module=None):
        """screen            a Screen (nokia_graphics.py)
        use_fast_helpers  use nokia_shapes_fast.py if it is present and works"""
        self._screen = screen
        self._frame = screen._frame
        self._swapped = 0

        # Work lists, made once. 'i' = 32-bit numbers.
        self._parameters = array.array("i", [0] * 12)
        # big enough for the tall side, so a rotation to landscape or back
        # never needs bigger lists
        longest_side = max(screen.width, screen.height)
        self._lefts = array.array("i", [0] * (longest_side + 2))
        self._rights = array.array("i", [0] * (longest_side + 2))
        self._crossings = array.array("i", [0] * _CROSSING_LIST_SIZE)

        self._fast = None
        self.fast_helpers_in_use = False
        if _fast_module is not None:
            self._fast = _fast_module
        elif use_fast_helpers:
            try:
                import nokia_shapes_fast
                if _fast_shapes_work(nokia_shapes_fast):
                    self._fast = nokia_shapes_fast
                    self.fast_helpers_in_use = True
            except Exception:
                pass
            if not self.fast_helpers_in_use:
                print("nokia_shapes: nokia_shapes_fast.py not found or not working. Using slower Python code.")
            # The self-check above leaves temporary pictures in memory.
            # Free them now so they do not count against the RAM budget.
            gc.collect()

        self.clear_clip()
        if hasattr(screen, "add_rotation_listener"):
            screen.add_rotation_listener(self._screen_changed)

    def _screen_changed(self, screen):
        # The Screen was turned and has new buffers. The clip rectangle was
        # for the old size, so it is cleared.
        self._frame = screen._frame
        self.clear_clip()

    def memory_bytes(self):
        """Memory held by the work lists (the sine table is shared)."""
        return 4 * (len(self._parameters) + len(self._lefts)
                    + len(self._rights) + len(self._crossings))

    # ===============================
    # CLIPPING
    # ===============================
    def set_clip(self, x, y, width, height):
        """From now on draw only inside this rectangle."""
        left = max(x, 0)
        top = max(y, 0)
        right = min(x + width - 1, self._screen.width - 1)
        bottom = min(y + height - 1, self._screen.height - 1)
        self._clip_left = left
        self._clip_top = top
        self._clip_right = right
        self._clip_bottom = bottom
        self._clip_is_whole_screen = (left == 0 and top == 0
                                      and right == self._screen.width - 1
                                      and bottom == self._screen.height - 1)

    def clear_clip(self):
        """Draw on the whole screen again."""
        self.set_clip(0, 0, self._screen.width, self._screen.height)

    # ===============================
    # SMALL HELPERS (inside the class)
    # ===============================
    def _set_colour(self, colour):
        self._swapped = ((colour & 0xFF) << 8) | (colour >> 8)

    def _mark_rows(self, top, bottom):
        if self._screen._tracking:
            self._screen._mark_dirty(top, bottom)

    def _row_range(self, top, bottom):
        """The rows from top to bottom that are inside the clip and, in
        strips mode, inside the band being drawn. Returns (first, last).
        first is more than last when nothing is visible."""
        screen = self._screen
        band_top = screen._origin_y
        first = max(top, self._clip_top, band_top)
        last = min(bottom, self._clip_bottom, band_top + screen.strip_height - 1)
        return (first, last)

    def _fill_row(self, y, x_start, x_end):
        """Fill pixels x_start to x_end (both included) of row y."""
        screen = self._screen
        band_top = screen._origin_y
        if (y < self._clip_top or y > self._clip_bottom
                or y < band_top or y >= band_top + screen.strip_height):
            return
        if x_start < self._clip_left:
            x_start = self._clip_left
        if x_end > self._clip_right:
            x_end = self._clip_right
        if x_start > x_end:
            return
        self._frame.fill_rect(x_start, y - band_top, x_end - x_start + 1, 1, self._swapped)

    def _plot(self, x, y):
        screen = self._screen
        band_top = screen._origin_y
        if (x < self._clip_left or x > self._clip_right
                or y < self._clip_top or y > self._clip_bottom
                or y < band_top or y >= band_top + screen.strip_height):
            return
        self._frame.pixel(x, y - band_top, self._swapped)

    def _span_parameters(self, first_row, row_count):
        # The numbers that fill_spans, outline_spans and fill_ring_spans read.
        screen = self._screen
        parameters = self._parameters
        parameters[0] = first_row
        parameters[1] = row_count
        parameters[2] = screen._origin_y
        parameters[3] = screen.width
        parameters[4] = self._clip_left
        parameters[5] = self._clip_right
        parameters[6] = self._swapped
        return parameters

    def _fill_by_rows(self, top, bottom, extent_of_row):
        """extent_of_row(y) returns (left, right) of the shape in row y."""
        first, last = self._row_range(top, bottom)
        for y in range(first, last + 1):
            left, right = extent_of_row(y)
            self._fill_row(y, left, right)

    def _outline_by_rows(self, top, bottom, extent_of_row):
        """Draw the one pixel thick edge of a shape that is described by the
        left and right end of every row. A pixel is on the edge when the pixel
        above it, below it, or beside it is outside the shape."""
        first, last = self._row_range(top, bottom)
        if first > last:
            return
        previous = None
        if first - 1 >= top:
            previous = extent_of_row(first - 1)
        current = extent_of_row(first)
        for y in range(first, last + 1):
            following = None
            if y + 1 <= bottom:
                following = extent_of_row(y + 1)
            left, right = current
            if previous is None or following is None:
                self._fill_row(y, left, right)
            else:
                inner_left = max(previous[0], following[0])
                end = min(right, inner_left - 1)
                if end < left:
                    end = left
                self._fill_row(y, left, end)
                inner_right = min(previous[1], following[1])
                start = max(left, inner_right + 1)
                if start > right:
                    start = right
                self._fill_row(y, start, right)
            previous = current
            current = following

    # ===============================
    # LINES
    # ===============================
    def draw_line(self, x_start, y_start, x_end, y_end, colour, thickness=1, round_caps=False):
        """A straight line. thickness is in pixels. With round_caps the ends
        are rounded. An odd thickness (3, 5, 7) gives the neatest result."""
        self._set_colour(colour)
        reach = thickness // 2 + 1
        self._mark_rows(min(y_start, y_end) - reach, max(y_start, y_end) + reach)
        self._line(x_start, y_start, x_end, y_end, thickness, round_caps)

    def _line(self, x_start, y_start, x_end, y_end, thickness, round_caps):
        if thickness <= 1:
            self._thin_line(x_start, y_start, x_end, y_end)
            return

        delta_x = x_end - x_start
        delta_y = y_end - y_start
        length = integer_square_root(delta_x * delta_x + delta_y * delta_y)
        if length == 0:
            self._ellipse(x_start, y_start, thickness // 2, thickness // 2, False)
            return

        side_one = thickness // 2            # pixels to one side of the line
        side_two = (thickness - 1) // 2      # pixels to the other side
        one_x = _divide_rounded(-delta_y * side_one, length)
        one_y = _divide_rounded(delta_x * side_one, length)
        two_x = _divide_rounded(-delta_y * side_two, length)
        two_y = _divide_rounded(delta_x * side_two, length)

        corners = array.array("i", (
            x_start + one_x, y_start + one_y,
            x_end + one_x, y_end + one_y,
            x_end - two_x, y_end - two_y,
            x_start - two_x, y_start - two_y))
        self._fill_polygon_coordinates(corners, 4)

        if round_caps:
            self._ellipse(x_start, y_start, thickness // 2, thickness // 2, False)
            self._ellipse(x_end, y_end, thickness // 2, thickness // 2, False)

    def _thin_line(self, x_start, y_start, x_end, y_end):
        screen = self._screen
        if self._clip_is_whole_screen:
            band_top = screen._origin_y
            self._frame.line(x_start, y_start - band_top, x_end, y_end - band_top,
                             self._swapped)
            return
        # With a clip rectangle: step along the line and plot only what is inside.
        delta_x = abs(x_end - x_start)
        delta_y = abs(y_end - y_start)
        step_x = 1 if x_start < x_end else -1
        step_y = 1 if y_start < y_end else -1
        error = delta_x - delta_y
        x = x_start
        y = y_start
        while True:
            self._plot(x, y)
            if x == x_end and y == y_end:
                break
            doubled = 2 * error
            if doubled > -delta_y:
                error -= delta_y
                x += step_x
            if doubled < delta_x:
                error += delta_x
                y += step_y

    def draw_polyline(self, points, colour, thickness=1, closed=False):
        """Lines through a list of (x, y) points. closed=True joins the last
        point back to the first. Joints are rounded when thickness is 3 or more."""
        count = len(points)
        if count == 0:
            return
        self._set_colour(colour)
        top = points[0][1]
        bottom = top
        for point in points:
            if point[1] < top:
                top = point[1]
            if point[1] > bottom:
                bottom = point[1]
        reach = thickness // 2 + 1
        self._mark_rows(top - reach, bottom + reach)

        segments = count if closed else count - 1
        for number in range(segments):
            x_start, y_start = points[number]
            x_end, y_end = points[(number + 1) % count]
            self._line(x_start, y_start, x_end, y_end, thickness, False)
        if thickness >= 3:
            for x, y in points:
                self._ellipse(x, y, thickness // 2, thickness // 2, False)

    # ===============================
    # POLYGONS AND TRIANGLES
    # ===============================
    def fill_polygon(self, points, colour):
        """Fill a polygon given as a list of (x, y) points. The polygon may
        be concave. If its edges cross, the crossing part is left empty."""
        count = len(points)
        if count == 0:
            return
        coordinates = array.array("i", [0] * (2 * count))
        for number in range(count):
            coordinates[2 * number] = points[number][0]
            coordinates[2 * number + 1] = points[number][1]
        self._set_colour(colour)
        self._fill_polygon_flat(coordinates, count)

    def fill_polygon_flat(self, coordinates, corner_count, colour):
        """Like fill_polygon, but the corners are already in an array('i')
        as x0, y0, x1, y1, ... (no tuples are made, so it is faster).
        Only the first corner_count corners are used."""
        self._set_colour(colour)
        self._fill_polygon_flat(coordinates, corner_count)

    def draw_polygon(self, points, colour, thickness=1):
        """Outline of a polygon (the last point joins back to the first)."""
        self.draw_polyline(points, colour, thickness, True)

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, colour):
        coordinates = array.array("i", (x0, y0, x1, y1, x2, y2))
        self._set_colour(colour)
        self._fill_polygon_flat(coordinates, 3)

    def draw_triangle(self, x0, y0, x1, y1, x2, y2, colour, thickness=1):
        self.draw_polyline(((x0, y0), (x1, y1), (x2, y2)), colour, thickness, True)

    def _fill_polygon_flat(self, coordinates, vertex_count):
        top = coordinates[1]
        bottom = top
        for number in range(1, vertex_count):
            y = coordinates[2 * number + 1]
            if y < top:
                top = y
            if y > bottom:
                bottom = y
        self._mark_rows(top, bottom)
        self._fill_polygon_coordinates(coordinates, vertex_count)

    def _fill_polygon_coordinates(self, coordinates, vertex_count):
        # coordinates is x0, y0, x1, y1, ... as array('i') (even-odd rule).
        # An edge covers the rows from its upper end up to, but not
        # including, its lower end. That way a corner shared by two edges is
        # counted once. The lowest row is added separately at the end.
        top = coordinates[1]
        bottom = top
        for number in range(1, vertex_count):
            y = coordinates[2 * number + 1]
            if y < top:
                top = y
            if y > bottom:
                bottom = y

        first, last = self._row_range(top, bottom)
        if first > last:
            return

        if vertex_count <= _CROSSING_LIST_SIZE:
            crossings = self._crossings
        else:
            crossings = array.array("i", [0] * vertex_count)

        if self._fast is not None:
            screen = self._screen
            parameters = self._parameters
            parameters[0] = vertex_count
            parameters[1] = first
            parameters[2] = last
            parameters[3] = screen._origin_y
            parameters[4] = screen.width
            parameters[5] = self._clip_left
            parameters[6] = self._clip_right
            parameters[7] = self._swapped
            self._fast.fill_polygon_rows(screen._buffer, coordinates, crossings, parameters)
        else:
            last_vertex = vertex_count - 1
            for y in range(first, last + 1):
                count = 0
                previous_x = coordinates[2 * last_vertex]
                previous_y = coordinates[2 * last_vertex + 1]
                for number in range(vertex_count):
                    next_x = coordinates[2 * number]
                    next_y = coordinates[2 * number + 1]
                    if previous_y != next_y:
                        if previous_y < next_y:
                            edge_top = previous_y
                            edge_bottom = next_y
                        else:
                            edge_top = next_y
                            edge_bottom = previous_y
                        if edge_top <= y < edge_bottom:
                            x = previous_x + _divide_rounded(
                                (y - previous_y) * (next_x - previous_x), next_y - previous_y)
                            position = count
                            while position > 0 and crossings[position - 1] > x:
                                crossings[position] = crossings[position - 1]
                                position -= 1
                            crossings[position] = x
                            count += 1
                    previous_x = next_x
                    previous_y = next_y
                for pair in range(0, count - 1, 2):
                    self._fill_row(y, crossings[pair], crossings[pair + 1])

        # The lowest row: flat edges and single corner points.
        if last == bottom:
            for number in range(vertex_count):
                y = coordinates[2 * number + 1]
                if y != bottom:
                    continue
                x = coordinates[2 * number]
                following = (number + 1) % vertex_count
                if coordinates[2 * following + 1] == bottom:
                    other_x = coordinates[2 * following]
                    self._fill_row(bottom, min(x, other_x), max(x, other_x))
                else:
                    self._fill_row(bottom, x, x)

    def _regular_points(self, centre_x, centre_y, radius, sides, rotation_degrees):
        coordinates = array.array("i", [0] * (2 * sides))
        for number in range(sides):
            angle = rotation_degrees - 90 + (360 * number) // sides
            coordinates[2 * number] = centre_x + ((radius * cosine(angle) + 2048) >> 12)
            coordinates[2 * number + 1] = centre_y + ((radius * sine(angle) + 2048) >> 12)
        return coordinates

    def fill_regular_polygon(self, centre_x, centre_y, radius, sides, colour, rotation_degrees=0):
        """Triangle, square, pentagon, hexagon ... with 'sides' sides."""
        coordinates = self._regular_points(centre_x, centre_y, radius, sides, rotation_degrees)
        self._set_colour(colour)
        self._fill_polygon_flat(coordinates, sides)

    def draw_regular_polygon(self, centre_x, centre_y, radius, sides, colour,
                             rotation_degrees=0, thickness=1):
        coordinates = self._regular_points(centre_x, centre_y, radius, sides, rotation_degrees)
        points = [(coordinates[2 * number], coordinates[2 * number + 1])
                  for number in range(sides)]
        self.draw_polyline(points, colour, thickness, True)

    def _star_points(self, centre_x, centre_y, outer_radius, inner_radius, point_count,
                     rotation_degrees):
        total = 2 * point_count
        coordinates = array.array("i", [0] * (2 * total))
        for number in range(total):
            radius = outer_radius if number % 2 == 0 else inner_radius
            angle = rotation_degrees - 90 + (360 * number) // total
            coordinates[2 * number] = centre_x + ((radius * cosine(angle) + 2048) >> 12)
            coordinates[2 * number + 1] = centre_y + ((radius * sine(angle) + 2048) >> 12)
        return coordinates, total

    def fill_star(self, centre_x, centre_y, outer_radius, inner_radius, point_count,
                  colour, rotation_degrees=0):
        coordinates, total = self._star_points(centre_x, centre_y, outer_radius,
                                               inner_radius, point_count, rotation_degrees)
        self._set_colour(colour)
        self._fill_polygon_flat(coordinates, total)

    def draw_star(self, centre_x, centre_y, outer_radius, inner_radius, point_count,
                  colour, rotation_degrees=0, thickness=1):
        coordinates, total = self._star_points(centre_x, centre_y, outer_radius,
                                               inner_radius, point_count, rotation_degrees)
        points = [(coordinates[2 * number], coordinates[2 * number + 1])
                  for number in range(total)]
        self.draw_polyline(points, colour, thickness, True)

    # ===============================
    # ELLIPSES, CIRCLES, RINGS
    # ===============================
    def _ellipse(self, centre_x, centre_y, radius_x, radius_y, outline):
        """Fill or outline an ellipse. The colour is already set."""
        top = centre_y - radius_y
        bottom = centre_y + radius_y
        first, last = self._row_range(top, bottom)
        if first > last:
            return

        if self._fast is not None and _ellipse_fits_fast_helper(radius_x, radius_y):
            parameters = self._parameters
            if outline:
                # the lists also hold the row above and the row below
                parameters[0] = first - 1
                parameters[1] = last - first + 3
            else:
                parameters[0] = first
                parameters[1] = last - first + 1
            parameters[2] = centre_x
            parameters[3] = centre_y
            parameters[4] = radius_x
            parameters[5] = radius_y
            self._fast.ellipse_extents(self._lefts, self._rights, parameters)
            parameters = self._span_parameters(first, last - first + 1)
            if outline:
                self._fast.outline_spans(self._screen._buffer, self._lefts, self._rights, parameters)
            else:
                self._fast.fill_spans(self._screen._buffer, self._lefts, self._rights, parameters)
            return

        def extent(y):
            half = _ellipse_half_width(radius_x, radius_y, abs(y - centre_y))
            return (centre_x - half, centre_x + half)
        if outline:
            self._outline_by_rows(top, bottom, extent)
        else:
            self._fill_by_rows(top, bottom, extent)

    def fill_ellipse(self, centre_x, centre_y, radius_x, radius_y, colour):
        self._set_colour(colour)
        self._mark_rows(centre_y - radius_y, centre_y + radius_y)
        self._ellipse(centre_x, centre_y, radius_x, radius_y, False)

    def draw_ellipse(self, centre_x, centre_y, radius_x, radius_y, colour):
        self._set_colour(colour)
        self._mark_rows(centre_y - radius_y, centre_y + radius_y)
        self._ellipse(centre_x, centre_y, radius_x, radius_y, True)

    def fill_circle(self, centre_x, centre_y, radius, colour):
        self.fill_ellipse(centre_x, centre_y, radius, radius, colour)

    def draw_circle(self, centre_x, centre_y, radius, colour):
        self.draw_ellipse(centre_x, centre_y, radius, radius, colour)

    def fill_ring(self, centre_x, centre_y, outer_radius, inner_radius, colour):
        """A flat ring (donut): the part between two circles."""
        self._set_colour(colour)
        self._mark_rows(centre_y - outer_radius, centre_y + outer_radius)
        first, last = self._row_range(centre_y - outer_radius, centre_y + outer_radius)
        if first > last:
            return

        if self._fast is not None and _ellipse_fits_fast_helper(outer_radius, outer_radius):
            row_count = last - first + 1
            parameters = self._parameters
            parameters[0] = first
            parameters[1] = row_count
            parameters[2] = centre_x
            parameters[3] = centre_y
            parameters[4] = outer_radius
            parameters[5] = outer_radius
            self._fast.ellipse_extents(self._lefts, self._rights, parameters)
            # the inner circle goes after the outer one in the same lists
            inner_lefts = array.array("i", [0] * row_count)
            inner_rights = array.array("i", [0] * row_count)
            parameters[4] = inner_radius
            parameters[5] = inner_radius
            self._fast.ellipse_extents(inner_lefts, inner_rights, parameters)
            parameters = self._span_parameters(first, row_count)
            self._fast.fill_ring_spans(self._screen._buffer, self._lefts, self._rights,
                                       inner_lefts, inner_rights, parameters)
            return

        for y in range(first, last + 1):
            offset = abs(y - centre_y)
            outer_half = _ellipse_half_width(outer_radius, outer_radius, offset)
            if offset <= inner_radius:
                inner_half = _ellipse_half_width(inner_radius, inner_radius, offset)
                self._fill_row(y, centre_x - outer_half, centre_x - inner_half - 1)
                self._fill_row(y, centre_x + inner_half + 1, centre_x + outer_half)
            else:
                self._fill_row(y, centre_x - outer_half, centre_x + outer_half)

    # ===============================
    # ARCS AND PIES
    # ===============================
    def _arc_setup(self, radius, start_degrees, end_degrees):
        sweep = end_degrees - start_degrees
        if sweep < 0:
            sweep %= 360
        if sweep > 360:
            sweep = 360
        step = 360 // max(16, 2 * radius)
        if step < 1:
            step = 1
        segments = (sweep + step - 1) // step
        if segments < 1:
            segments = 1
        return sweep, segments

    def _arc_polygon(self, centre_x, centre_y, outer_radius, inner_radius,
                     start_degrees, sweep, segments, pie):
        """Corner points of an arc band (a piece of a ring), or of a pie
        slice when pie is True. Returns (coordinates, corner_count)."""
        if pie:
            total = segments + 2
        else:
            total = 2 * (segments + 1)
        coordinates = array.array("i", [0] * (2 * total))

        if self._fast is not None:
            parameters = self._parameters
            parameters[0] = centre_x
            parameters[1] = centre_y
            parameters[2] = outer_radius
            parameters[3] = inner_radius
            parameters[4] = start_degrees
            parameters[5] = sweep
            parameters[6] = segments
            parameters[7] = 1 if pie else 0
            self._fast.arc_polygon_points(coordinates, _SINE_TABLE, parameters)
            return coordinates, total

        if pie:
            coordinates[0] = centre_x
            coordinates[1] = centre_y
        for number in range(segments + 1):
            angle = start_degrees + (sweep * number) // segments
            cos_value = cosine(angle)
            sin_value = sine(angle)
            outer_x = centre_x + ((outer_radius * cos_value + 2048) >> 12)
            outer_y = centre_y + ((outer_radius * sin_value + 2048) >> 12)
            if pie:
                coordinates[2 * (number + 1)] = outer_x
                coordinates[2 * (number + 1) + 1] = outer_y
            else:
                coordinates[2 * number] = outer_x
                coordinates[2 * number + 1] = outer_y
                inner_index = 2 * segments + 1 - number
                coordinates[2 * inner_index] = centre_x + ((inner_radius * cos_value + 2048) >> 12)
                coordinates[2 * inner_index + 1] = centre_y + ((inner_radius * sin_value + 2048) >> 12)
        return coordinates, total

    def _arc_point(self, centre_x, centre_y, radius, angle):
        return (centre_x + ((radius * cosine(angle) + 2048) >> 12),
                centre_y + ((radius * sine(angle) + 2048) >> 12))

    def draw_arc(self, centre_x, centre_y, radius, start_degrees, end_degrees, colour,
                 thickness=1):
        """Part of a circle, from start_degrees to end_degrees going clockwise.
        With thickness more than 1 the arc grows inward from 'radius'."""
        sweep, segments = self._arc_setup(radius, start_degrees, end_degrees)
        if sweep == 0:
            return
        self._set_colour(colour)
        self._mark_rows(centre_y - radius, centre_y + radius)

        if thickness <= 1:
            previous_x, previous_y = self._arc_point(centre_x, centre_y, radius, start_degrees)
            for number in range(1, segments + 1):
                angle = start_degrees + (sweep * number) // segments
                x, y = self._arc_point(centre_x, centre_y, radius, angle)
                self._thin_line(previous_x, previous_y, x, y)
                previous_x = x
                previous_y = y
            return

        inner_radius = radius - thickness + 1
        if inner_radius < 0:
            inner_radius = 0
        coordinates, total = self._arc_polygon(centre_x, centre_y, radius, inner_radius,
                                               start_degrees, sweep, segments, False)
        self._fill_polygon_coordinates(coordinates, total)

    def fill_pie(self, centre_x, centre_y, radius, start_degrees, end_degrees, colour):
        """A slice of a disc, like a piece of pie, going clockwise from
        start_degrees to end_degrees."""
        sweep, segments = self._arc_setup(radius, start_degrees, end_degrees)
        if sweep == 0:
            return
        self._set_colour(colour)
        self._mark_rows(centre_y - radius, centre_y + radius)
        coordinates, total = self._arc_polygon(centre_x, centre_y, radius, 0,
                                               start_degrees, sweep, segments, True)
        self._fill_polygon_coordinates(coordinates, total)

    # ===============================
    # ROUNDED RECTANGLES
    # ===============================
    def _rounded(self, x, y, width, height, radius, outline):
        """Fill or outline a rounded rectangle. The colour is already set."""
        top = y
        bottom = y + height - 1
        first, last = self._row_range(top, bottom)
        if first > last:
            return

        if self._fast is not None:
            parameters = self._parameters
            if outline:
                parameters[0] = first - 1
                parameters[1] = last - first + 3
            else:
                parameters[0] = first
                parameters[1] = last - first + 1
            parameters[2] = x
            parameters[3] = y
            parameters[4] = width
            parameters[5] = height
            parameters[6] = radius
            self._fast.rounded_extents(self._lefts, self._rights, parameters)
            parameters = self._span_parameters(first, last - first + 1)
            if outline:
                self._fast.outline_spans(self._screen._buffer, self._lefts, self._rights, parameters)
            else:
                self._fast.fill_spans(self._screen._buffer, self._lefts, self._rights, parameters)
            return

        def extent(row_y):
            row = row_y - y
            distance = row
            if height - 1 - row < distance:
                distance = height - 1 - row
            if distance < radius:
                half = _ellipse_half_width(radius, radius, radius - distance)
                inset = radius - half
                return (x + inset, x + width - 1 - inset)
            return (x, x + width - 1)
        if outline:
            self._outline_by_rows(top, bottom, extent)
        else:
            self._fill_by_rows(top, bottom, extent)

    def fill_rounded_rectangle(self, x, y, width, height, radius, colour):
        if width < 1 or height < 1:
            return
        radius = max(0, min(radius, (min(width, height) - 1) // 2))
        self._set_colour(colour)
        self._mark_rows(y, y + height - 1)
        self._rounded(x, y, width, height, radius, False)

    def draw_rounded_rectangle(self, x, y, width, height, radius, colour):
        if width < 1 or height < 1:
            return
        radius = max(0, min(radius, (min(width, height) - 1) // 2))
        self._set_colour(colour)
        self._mark_rows(y, y + height - 1)
        self._rounded(x, y, width, height, radius, True)

    # ===============================
    # SPRITES
    # ===============================
    def draw_sprite(self, sprite, x, y):
        """Draw a Sprite with its top-left corner at x, y. Pixels that have
        the sprite's transparent colour are left alone."""
        screen = self._screen
        band_top = screen._origin_y
        self._mark_rows(y, y + sprite.height - 1)

        if sprite.transparent_colour is None:
            key = -1
        else:
            key = ((sprite.transparent_colour & 0xFF) << 8) | (sprite.transparent_colour >> 8)

        inside_clip = (x >= self._clip_left and y >= self._clip_top
                       and x + sprite.width - 1 <= self._clip_right
                       and y + sprite.height - 1 <= self._clip_bottom)
        if self._clip_is_whole_screen or inside_clip:
            self._frame.blit(sprite._framebuffer, x, y - band_top, key)
            return

        # Partly outside the clip rectangle: draw the visible part row by row.
        first_column = max(0, self._clip_left - x)
        last_column = min(sprite.width - 1, self._clip_right - x)
        if first_column > last_column:
            return
        first_row, last_row = self._row_range(y, y + sprite.height - 1)
        visible_width = last_column - first_column + 1
        row_bytes = sprite.width * 2
        pixels = memoryview(sprite._pixels)
        for screen_row in range(first_row, last_row + 1):
            sprite_row = screen_row - y
            start = sprite_row * row_bytes + first_column * 2
            piece = framebuf.FrameBuffer(pixels[start:start + visible_width * 2],
                                         visible_width, 1, framebuf.RGB565)
            self._frame.blit(piece, x + first_column, screen_row - band_top, key)


class Sprite:
    """A small picture with see-through parts.
    The pixels are 16-bit colours, high byte first, the same format as the
    raw image files that show_image_file / draw_image_file use.
    transparent_colour: the colour that means 'see through', or None.
    Magenta (0xF81F) is a common choice."""

    def __init__(self, width, height, pixel_bytes, transparent_colour=None):
        if len(pixel_bytes) != width * height * 2:
            raise ValueError("sprite needs " + str(width * height * 2) + " bytes of pixels")
        self.width = width
        self.height = height
        self.transparent_colour = transparent_colour
        self._pixels = bytearray(pixel_bytes)
        self._framebuffer = framebuf.FrameBuffer(self._pixels, width, height, framebuf.RGB565)

    def memory_bytes(self):
        return len(self._pixels)

    @classmethod
    def from_file(cls, filename, width, height, transparent_colour=None, frame=0):
        """Load a sprite from a raw 16-bit file. A file may hold several
        frames one after another; frame picks which one (0 is the first)."""
        frame_bytes = width * height * 2
        with open(filename, "rb") as sprite_file:
            sprite_file.seek(frame * frame_bytes)
            pixels = bytearray(frame_bytes)
            if sprite_file.readinto(pixels) != frame_bytes:
                raise ValueError(filename + " is too short for this frame")
        return cls(width, height, pixels, transparent_colour)

    @classmethod
    def from_text_rows(cls, rows, colour_for_character, transparent_colour=0xF81F):
        """Build a tiny sprite from rows of text. Every character stands for a
        colour in the colour_for_character dictionary. A character that is
        not in the dictionary is see-through.
            Sprite.from_text_rows(("..r..", ".rrr.", "rrrrr"), {"r": 0xF800})"""
        height = len(rows)
        width = len(rows[0])
        pixels = bytearray(width * height * 2)
        for row_number in range(height):
            for column in range(width):
                colour = colour_for_character.get(rows[row_number][column], transparent_colour)
                position = (row_number * width + column) * 2
                pixels[position] = colour >> 8
                pixels[position + 1] = colour & 0xFF
        return cls(width, height, pixels, transparent_colour)

    def flipped(self, horizontally=True, vertically=False):
        """A new sprite that is a mirror image. It uses its own memory."""
        row_bytes = self.width * 2
        pixels = bytearray(len(self._pixels))
        for row in range(self.height):
            source_row = (self.height - 1 - row) if vertically else row
            for column in range(self.width):
                source_column = (self.width - 1 - column) if horizontally else column
                source = source_row * row_bytes + source_column * 2
                target = row * row_bytes + column * 2
                pixels[target] = self._pixels[source]
                pixels[target + 1] = self._pixels[source + 1]
        return Sprite(self.width, self.height, pixels, self.transparent_colour)
