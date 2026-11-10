"""
Fast helpers for nokia_shapes.py
Copy this file to the Pico next to nokia_shapes.py.

These use MicroPython's "viper" mode, which runs close to machine speed.
They fill whole shapes row by row without going back to Python for every
row. If this file is missing or does not work, nokia_shapes.py falls back
to slower Python code that draws exactly the same pixels (it checks this
itself every time Shapes is created).

All lists of numbers are array('i') (32-bit signed). The screen buffer is a
bytearray of 16-bit pixels; 'colour' is already in the byte order the
buffer uses. Rows given to these functions have already been cut down to
the clip rectangle and the band being drawn, so nothing is checked here
except the left and right ends of each row.

An empty row in a list of row ends has left = 1 and right = 0.
"""
import micropython


@micropython.viper
def fill_polygon_rows(destination: ptr16, coordinates: ptr32, crossings: ptr32,
                      parameters: ptr32):
    # Fills a polygon (even-odd rule) from first_row to last_row.
    # parameters: 0 number of corners, 1 first row, 2 last row, 3 top row of
    # the band, 4 buffer width in pixels, 5 clip left, 6 clip right, 7 colour
    corner_count = int(parameters[0])
    first_row = int(parameters[1])
    last_row = int(parameters[2])
    band_top = int(parameters[3])
    buffer_width = int(parameters[4])
    clip_left = int(parameters[5])
    clip_right = int(parameters[6])
    colour = int(parameters[7])

    y = first_row
    while y <= last_row:
        count = 0
        previous_x = int(coordinates[2 * (corner_count - 1)])
        previous_y = int(coordinates[2 * (corner_count - 1) + 1])
        number = 0
        while number < corner_count:
            next_x = int(coordinates[2 * number])
            next_y = int(coordinates[2 * number + 1])
            if previous_y != next_y:
                edge_top = previous_y
                edge_bottom = next_y
                if previous_y > next_y:
                    edge_top = next_y
                    edge_bottom = previous_y
                if y >= edge_top:
                    if y < edge_bottom:
                        delta_y = next_y - previous_y
                        x = previous_x + (2 * (y - previous_y) * (next_x - previous_x) + delta_y) // (2 * delta_y)
                        position = count
                        while position > 0:
                            if int(crossings[position - 1]) <= x:
                                break
                            crossings[position] = crossings[position - 1]
                            position -= 1
                        crossings[position] = x
                        count += 1
            previous_x = next_x
            previous_y = next_y
            number += 1

        row_base = (y - band_top) * buffer_width
        pair = 0
        while pair + 1 < count:
            start = int(crossings[pair])
            end = int(crossings[pair + 1])
            if start < clip_left:
                start = clip_left
            if end > clip_right:
                end = clip_right
            while start <= end:
                destination[row_base + start] = colour
                start += 1
            pair += 2
        y += 1


@micropython.viper
def fill_spans(destination: ptr16, lefts: ptr32, rights: ptr32, parameters: ptr32):
    # Fills one span per row. Row number first_row + i uses lefts[i], rights[i].
    # parameters: 0 first row, 1 number of rows, 2 top row of the band,
    # 3 buffer width, 4 clip left, 5 clip right, 6 colour
    first_row = int(parameters[0])
    row_count = int(parameters[1])
    band_top = int(parameters[2])
    buffer_width = int(parameters[3])
    clip_left = int(parameters[4])
    clip_right = int(parameters[5])
    colour = int(parameters[6])

    i = 0
    while i < row_count:
        start = int(lefts[i])
        end = int(rights[i])
        if start < clip_left:
            start = clip_left
        if end > clip_right:
            end = clip_right
        row_base = (first_row + i - band_top) * buffer_width
        while start <= end:
            destination[row_base + start] = colour
            start += 1
        i += 1


@micropython.viper
def outline_spans(destination: ptr16, lefts: ptr32, rights: ptr32, parameters: ptr32):
    # Draws the one pixel thick edge of a shape described by its row ends.
    # The lists hold row_count + 2 entries: entry 0 is the row above the
    # first row and the last entry is the row below the last row.
    # parameters are the same as for fill_spans.
    first_row = int(parameters[0])
    row_count = int(parameters[1])
    band_top = int(parameters[2])
    buffer_width = int(parameters[3])
    clip_left = int(parameters[4])
    clip_right = int(parameters[5])
    colour = int(parameters[6])

    i = 1
    while i <= row_count:
        left = int(lefts[i])
        right = int(rights[i])
        if left <= right:
            previous_left = int(lefts[i - 1])
            previous_right = int(rights[i - 1])
            following_left = int(lefts[i + 1])
            following_right = int(rights[i + 1])
            row_base = (first_row + i - 1 - band_top) * buffer_width

            # first piece (from the left end) and second piece (to the right end)
            piece_one_start = left
            piece_one_end = right
            piece_two_start = right + 1      # nothing, unless set below
            piece_two_end = right
            neighbour_missing = 0
            if previous_left > previous_right:
                neighbour_missing = 1
            if following_left > following_right:
                neighbour_missing = 1
            if neighbour_missing == 0:
                inner_left = previous_left
                if following_left > inner_left:
                    inner_left = following_left
                piece_one_end = inner_left - 1
                if right < piece_one_end:
                    piece_one_end = right
                if piece_one_end < left:
                    piece_one_end = left
                inner_right = previous_right
                if following_right < inner_right:
                    inner_right = following_right
                piece_two_start = inner_right + 1
                if left > piece_two_start:
                    piece_two_start = left
                if piece_two_start > right:
                    piece_two_start = right
                piece_two_end = right

            start = piece_one_start
            end = piece_one_end
            if start < clip_left:
                start = clip_left
            if end > clip_right:
                end = clip_right
            while start <= end:
                destination[row_base + start] = colour
                start += 1

            start = piece_two_start
            end = piece_two_end
            if start < clip_left:
                start = clip_left
            if end > clip_right:
                end = clip_right
            while start <= end:
                destination[row_base + start] = colour
                start += 1
        i += 1


@micropython.viper
def fill_ring_spans(destination: ptr16, outer_lefts: ptr32, outer_rights: ptr32,
                    inner_lefts: ptr32, inner_rights: ptr32, parameters: ptr32):
    # A ring: the outer shape with the inner shape cut out of it.
    # parameters are the same as for fill_spans.
    first_row = int(parameters[0])
    row_count = int(parameters[1])
    band_top = int(parameters[2])
    buffer_width = int(parameters[3])
    clip_left = int(parameters[4])
    clip_right = int(parameters[5])
    colour = int(parameters[6])

    i = 0
    while i < row_count:
        outer_left = int(outer_lefts[i])
        outer_right = int(outer_rights[i])
        if outer_left <= outer_right:
            inner_left = int(inner_lefts[i])
            inner_right = int(inner_rights[i])
            row_base = (first_row + i - band_top) * buffer_width

            piece_one_start = outer_left
            piece_one_end = outer_right
            piece_two_start = outer_right + 1
            piece_two_end = outer_right
            if inner_left <= inner_right:
                piece_one_end = inner_left - 1
                piece_two_start = inner_right + 1

            start = piece_one_start
            end = piece_one_end
            if start < clip_left:
                start = clip_left
            if end > clip_right:
                end = clip_right
            while start <= end:
                destination[row_base + start] = colour
                start += 1

            start = piece_two_start
            end = piece_two_end
            if start < clip_left:
                start = clip_left
            if end > clip_right:
                end = clip_right
            while start <= end:
                destination[row_base + start] = colour
                start += 1
        i += 1


@micropython.viper
def ellipse_extents(lefts: ptr32, rights: ptr32, parameters: ptr32):
    # Left and right end of an ellipse in each row.
    # parameters: 0 first row, 1 number of rows, 2 centre x, 3 centre y,
    # 4 radius x, 5 radius y
    first_row = int(parameters[0])
    row_count = int(parameters[1])
    centre_x = int(parameters[2])
    centre_y = int(parameters[3])
    radius_x = int(parameters[4])
    radius_y = int(parameters[5])
    full_x = 2 * radius_x + 1
    full_y = 2 * radius_y + 1

    i = 0
    while i < row_count:
        offset = first_row + i - centre_y
        if offset < 0:
            offset = -offset
        if offset > radius_y:
            lefts[i] = 1
            rights[i] = 0
        else:
            value = (full_x * full_x * (full_y * full_y - 4 * offset * offset)) // (4 * full_y * full_y)
            root = 0
            if value > 0:
                root = value
                guess = (root + 1) >> 1
                while guess < root:
                    root = guess
                    guess = (root + value // root) >> 1
            lefts[i] = centre_x - root
            rights[i] = centre_x + root
        i += 1


@micropython.viper
def rounded_extents(lefts: ptr32, rights: ptr32, parameters: ptr32):
    # Left and right end of a rounded rectangle in each row.
    # parameters: 0 first row, 1 number of rows, 2 x, 3 y, 4 width,
    # 5 height, 6 corner radius
    first_row = int(parameters[0])
    row_count = int(parameters[1])
    x = int(parameters[2])
    y = int(parameters[3])
    width = int(parameters[4])
    height = int(parameters[5])
    radius = int(parameters[6])
    full = 2 * radius + 1

    i = 0
    while i < row_count:
        row = first_row + i - y
        inside = 1
        if row < 0:
            inside = 0
        if row >= height:
            inside = 0
        if inside == 0:
            lefts[i] = 1
            rights[i] = 0
        else:
            distance = row
            if height - 1 - row < distance:
                distance = height - 1 - row
            left = x
            right = x + width - 1
            if distance < radius:
                offset = radius - distance
                value = (full * full - 4 * offset * offset) // 4
                root = 0
                if value > 0:
                    root = value
                    guess = (root + 1) >> 1
                    while guess < root:
                        root = guess
                        guess = (root + value // root) >> 1
                inset = radius - root
                left = x + inset
                right = x + width - 1 - inset
            lefts[i] = left
            rights[i] = right
        i += 1


@micropython.viper
def arc_polygon_points(coordinates: ptr32, table: ptr16, parameters: ptr32):
    # Corner points of an arc band (a piece of a ring) or of a pie slice.
    # table is the sine table (sine of 0 to 90 degrees, times 4096).
    # parameters: 0 centre x, 1 centre y, 2 outer radius, 3 inner radius,
    # 4 start degrees, 5 sweep degrees, 6 number of segments, 7 pie (1) or ring (0)
    centre_x = int(parameters[0])
    centre_y = int(parameters[1])
    outer_radius = int(parameters[2])
    inner_radius = int(parameters[3])
    start = int(parameters[4])
    sweep = int(parameters[5])
    segments = int(parameters[6])
    pie = int(parameters[7])

    if pie == 1:
        coordinates[0] = centre_x
        coordinates[1] = centre_y

    i = 0
    while i <= segments:
        angle = start + (sweep * i) // segments

        a = angle % 360
        sine_value = 0
        if a <= 90:
            sine_value = int(table[a])
        elif a <= 180:
            sine_value = int(table[180 - a])
        elif a <= 270:
            sine_value = -int(table[a - 180])
        else:
            sine_value = -int(table[360 - a])

        b = (angle + 90) % 360
        cosine_value = 0
        if b <= 90:
            cosine_value = int(table[b])
        elif b <= 180:
            cosine_value = int(table[180 - b])
        elif b <= 270:
            cosine_value = -int(table[b - 180])
        else:
            cosine_value = -int(table[360 - b])

        outer_x = centre_x + ((outer_radius * cosine_value + 2048) >> 12)
        outer_y = centre_y + ((outer_radius * sine_value + 2048) >> 12)
        if pie == 1:
            coordinates[2 * (i + 1)] = outer_x
            coordinates[2 * (i + 1) + 1] = outer_y
        else:
            coordinates[2 * i] = outer_x
            coordinates[2 * i + 1] = outer_y
            inner_index = 2 * segments + 1 - i
            coordinates[2 * inner_index] = centre_x + ((inner_radius * cosine_value + 2048) >> 12)
            coordinates[2 * inner_index + 1] = centre_y + ((inner_radius * sine_value + 2048) >> 12)
        i += 1
