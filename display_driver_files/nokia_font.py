"""
nokia_font.py - fonts for Screen (nokia_graphics.py)

Copy this file, nokia_font_fast.py and your .nkf font files to the Pico.
Make .nkf files from any TrueType font with make_font.py on your PC.

    from nokia_font import Font

    normal = Font("fonts/sans_14.nkf")
    normal.draw(screen, "Hello  π ≈ 3.14  x² + √2", 4, 4, WHITE)

WHY IT USES LITTLE RAM
The font stays in the file in flash. Only the characters you really draw
are read into a small cache (cache_bytes, default 3 KB per font). The list
of characters is searched inside the file unless you ask for it to be kept
in memory (keep_index_in_memory=True: about 4 KB more per font, faster the
first time a character is drawn).

The text is drawn with 4 levels of grey (smooth edges) on top of whatever
is already in the picture, so it also works over backgrounds that are not
a single colour.

Text is drawn at 'x, y' = top-left corner of the text box, unless
y_is_baseline=True. Letters are placed one after another by their widths.
There is no kerning (pair spacing).
"""
import array

ALIGN_LEFT = "left"
ALIGN_CENTRE = "centre"
ALIGN_RIGHT = "right"

_MAGIC = b"NKF1"
_HEADER_BYTES = 16
_ENTRY_BYTES = 10

# Used when a character is not in the font
_REPLACEMENT_CODES = (0xFFFD, 63)

# Extra rows checked above and below a line before skipping it, because a
# few letters (like Å) reach a little outside the line height.
_SKIP_MARGIN = 4


# ===============================
# GLYPH BLENDING
# One character picture is blended into the screen buffer.
# This Python version is the slow reference. nokia_font_fast.py has a
# version that runs much faster and gives exactly the same result.
#
# parameters (a list of whole numbers) holds:
#   0 bytes in one row of the character picture
#   1 first row to draw          2 one past the last row to draw
#   3 first column to draw       4 one past the last column to draw
#   5 byte position in the buffer of the first pixel to draw
#   6 bytes in one row of the buffer
#   7 text colour red (0-31)     8 green (0-63)    9 blue (0-31)
#   10 text colour high byte    11 text colour low byte
# ===============================
def _python_blend_glyph(destination, glyph, parameters):
    glyph_row_bytes = parameters[0]
    first_row = parameters[1]
    last_row = parameters[2]
    first_column = parameters[3]
    last_column = parameters[4]
    destination_start = parameters[5]
    destination_row_bytes = parameters[6]
    colour_red = parameters[7]
    colour_green = parameters[8]
    colour_blue = parameters[9]
    colour_high_byte = parameters[10]
    colour_low_byte = parameters[11]

    for row in range(first_row, last_row):
        index = destination_start + (row - first_row) * destination_row_bytes
        glyph_row_start = row * glyph_row_bytes
        for column in range(first_column, last_column):
            level = (glyph[glyph_row_start + (column >> 2)] >> (6 - ((column & 3) << 1))) & 3
            if level == 3:
                destination[index] = colour_high_byte
                destination[index + 1] = colour_low_byte
            elif level != 0:
                if level == 1:
                    strength = 85
                else:
                    strength = 170
                current = (destination[index] << 8) | destination[index + 1]
                red = (((current >> 11) & 31) * (256 - strength) + colour_red * strength) >> 8
                green = (((current >> 5) & 63) * (256 - strength) + colour_green * strength) >> 8
                blue = ((current & 31) * (256 - strength) + colour_blue * strength) >> 8
                mixed = (red << 11) | (green << 5) | blue
                destination[index] = mixed >> 8
                destination[index + 1] = mixed & 255
            index += 2


def _fast_blend_works(nokia_font_fast):
    """Check the fast version gives the same pixels as the Python version."""
    try:
        # A 6 x 3 picture with every level in it
        glyph = bytearray([0b00011011, 0b11100100,
                           0b11100100, 0b01101100,
                           0b10101010, 0b01010101])
        start = bytearray([(index * 53 + 7) & 0xFF for index in range(6 * 3 * 2)])
        expected = bytearray(start)
        got = bytearray(start)

        parameters = array.array("i", [2, 0, 3, 0, 6, 0, 12,
                                       31, 20, 5, 0xF8, 0xA5])
        _python_blend_glyph(expected, glyph, parameters)
        nokia_font_fast.blend_glyph(got, glyph, parameters)
        if expected != got or expected == start:
            return False

        # A partly visible picture (columns 1 to 4, rows 1 to 2)
        expected = bytearray(start)
        got = bytearray(start)
        parameters = array.array("i", [2, 1, 3, 1, 5, 14, 12,
                                       3, 60, 17, 0x1F, 0x3C])
        _python_blend_glyph(expected, glyph, parameters)
        nokia_font_fast.blend_glyph(got, glyph, parameters)
        return expected == got
    except Exception:
        return False


class Font:
    def __init__(self, filename, keep_index_in_memory=False, cache_bytes=3072,
                 use_fast_helpers=True):
        """filename              a .nkf file made by make_font.py
        keep_index_in_memory  True = faster, uses about 10 bytes per character
        cache_bytes           how much memory the drawn-character cache may use
        use_fast_helpers      use nokia_font_fast.py if it is present"""
        self._file = open(filename, "rb")
        header = self._file.read(_HEADER_BYTES)
        if len(header) < _HEADER_BYTES or header[0:4] != _MAGIC:
            self._file.close()
            raise ValueError(filename + " is not a .nkf font file")
        if header[7] != 2:
            self._file.close()
            raise ValueError(filename + " does not use 2 bits per pixel")

        self.filename = filename
        self.line_height = header[4]
        self.ascent = header[5]
        self.descent = header[6]
        self._glyph_count = header[8] | (header[9] << 8)
        self._data_start = (header[12] | (header[13] << 8)
                            | (header[14] << 16) | (header[15] << 24))

        if keep_index_in_memory:
            self._index = self._file.read(self._glyph_count * _ENTRY_BYTES)
        else:
            self._index = None

        self._cache = {}
        self._cache_limit = cache_bytes
        self._cache_used = 0

        self._parameters = array.array("i", [0] * 12)

        self._blend_glyph = _python_blend_glyph
        self.fast_helpers_in_use = False
        if use_fast_helpers:
            try:
                import nokia_font_fast
                if _fast_blend_works(nokia_font_fast):
                    self._blend_glyph = nokia_font_fast.blend_glyph
                    self.fast_helpers_in_use = True
            except Exception:
                pass
            if not self.fast_helpers_in_use:
                print("nokia_font: nokia_font_fast.py not found or not working. Using slower Python code.")

    def close(self):
        self._file.close()

    def memory_bytes(self):
        """About how much memory this font can use at most."""
        index_bytes = 0
        if self._index is not None:
            index_bytes = len(self._index)
        return index_bytes + self._cache_limit

    # ===============================
    # FINDING CHARACTERS IN THE FILE
    # ===============================
    def _code_at(self, entry_number):
        if self._index is not None:
            base = entry_number * _ENTRY_BYTES
            return self._index[base] | (self._index[base + 1] << 8)
        self._file.seek(_HEADER_BYTES + entry_number * _ENTRY_BYTES)
        two_bytes = self._file.read(2)
        return two_bytes[0] | (two_bytes[1] << 8)

    def _entry_bytes(self, entry_number):
        if self._index is not None:
            base = entry_number * _ENTRY_BYTES
            return self._index[base:base + _ENTRY_BYTES]
        self._file.seek(_HEADER_BYTES + entry_number * _ENTRY_BYTES)
        return self._file.read(_ENTRY_BYTES)

    def _search(self, code):
        """Binary search. Returns the entry number, or -1 if not found."""
        low = 0
        high = self._glyph_count - 1
        while low <= high:
            middle = (low + high) >> 1
            middle_code = self._code_at(middle)
            if middle_code == code:
                return middle
            if middle_code < code:
                low = middle + 1
            else:
                high = middle - 1
        return -1

    def has_character(self, character):
        return self._search(ord(character)) >= 0

    def _glyph(self, code):
        """Returns (width, height, sideways_shift, upward_shift, advance, picture)
        or None when there is no such character and no replacement."""
        glyph = self._cache.get(code)
        if glyph is not None:
            return glyph

        entry_number = self._search(code)
        if entry_number < 0:
            for replacement in _REPLACEMENT_CODES:
                if replacement != code:
                    entry_number = self._search(replacement)
                    if entry_number >= 0:
                        break
            if entry_number < 0:
                return None

        entry = self._entry_bytes(entry_number)
        offset = entry[2] | (entry[3] << 8) | (entry[4] << 16)
        width = entry[5]
        height = entry[6]
        sideways_shift = entry[7] - 256 if entry[7] > 127 else entry[7]
        upward_shift = entry[8] - 256 if entry[8] > 127 else entry[8]
        advance = entry[9]

        picture_size = ((width + 3) >> 2) * height
        if picture_size > 0:
            self._file.seek(self._data_start + offset)
            picture = self._file.read(picture_size)
        else:
            picture = b""

        cost = picture_size + 64
        if self._cache_used + cost > self._cache_limit:
            self._cache = {}
            self._cache_used = 0

        glyph = (width, height, sideways_shift, upward_shift, advance, picture)
        self._cache[code] = glyph
        self._cache_used += cost
        return glyph

    # ===============================
    # MEASURING
    # ===============================
    def measure_line(self, text):
        """Width in pixels of one line of text (no new lines inside)."""
        total = 0
        for character in text:
            glyph = self._glyph(ord(character))
            if glyph is not None:
                total += glyph[4]
        return total

    def measure(self, text):
        """(width, height) in pixels of text that may have several lines."""
        lines = text.split("\n")
        widest = 0
        for line in lines:
            line_width = self.measure_line(line)
            if line_width > widest:
                widest = line_width
        return (widest, len(lines) * self.line_height)

    def wrap(self, text, max_width):
        """Break text into a list of lines no wider than max_width.
        Breaks at spaces. A single word that is too wide is cut."""
        result = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split(" "):
                if current == "":
                    candidate = word
                else:
                    candidate = current + " " + word
                if self.measure_line(candidate) <= max_width:
                    current = candidate
                    continue
                if current != "":
                    result.append(current)
                    current = ""
                while len(word) > 1 and self.measure_line(word) > max_width:
                    cut = len(word) - 1
                    while cut > 1 and self.measure_line(word[0:cut]) > max_width:
                        cut -= 1
                    result.append(word[0:cut])
                    word = word[cut:]
                current = word
            result.append(current)
        return result

    # ===============================
    # DRAWING
    # ===============================
    def character_width(self, character):
        """How far the pen moves after this character, in pixels."""
        glyph = self._glyph(ord(character))
        if glyph is None:
            return 0
        return glyph[4]

    # clip (optional, in every draw call below) is a box (left, top, right,
    # bottom), all four pixels included, in screen coordinates. Text is cut
    # off at its edges. It is how text scrolls inside a window.
    def draw(self, screen, text, x, y, colour, background=None,
             underline=False, strikethrough=False, y_is_baseline=False, clip=None):
        """Draw text (new lines allowed) with its top-left corner at x, y.
        background: colour of a box drawn behind each line first, or None
        to draw on top of what is already there.
        Returns (width, height) of the text."""
        lines = text.split("\n")
        widest = 0
        for line_number in range(len(lines)):
            line_top = y + line_number * self.line_height
            if y_is_baseline:
                line_top -= self.ascent
            line_width = self._draw_line(screen, lines[line_number], x, line_top, colour,
                                         background, underline, strikethrough, clip)
            if line_width > widest:
                widest = line_width
        return (widest, len(lines) * self.line_height)

    def draw_aligned(self, screen, text, x, y, width, colour, alignment=ALIGN_LEFT,
                     background=None, underline=False, strikethrough=False, clip=None):
        """Draw text inside a box that starts at x and is 'width' pixels wide.
        alignment is ALIGN_LEFT, ALIGN_CENTRE or ALIGN_RIGHT, applied to each
        line separately. Returns the height used."""
        lines = text.split("\n")
        for line_number in range(len(lines)):
            line = lines[line_number]
            line_width = self.measure_line(line)
            if alignment == ALIGN_RIGHT:
                line_x = x + width - line_width
            elif alignment == ALIGN_CENTRE:
                line_x = x + (width - line_width) // 2
            else:
                line_x = x
            self._draw_line(screen, line, line_x, y + line_number * self.line_height,
                            colour, background, underline, strikethrough, clip)
        return len(lines) * self.line_height

    def draw_wrapped(self, screen, text, x, y, width, colour, alignment=ALIGN_LEFT,
                     background=None, extra_line_spacing=0, clip=None):
        """Wrap text to 'width' pixels and draw it. Returns the height used."""
        lines = self.wrap(text, width)
        step = self.line_height + extra_line_spacing
        for line_number in range(len(lines)):
            self.draw_aligned(screen, lines[line_number], x, y + line_number * step,
                              width, colour, alignment, background, clip=clip)
        return len(lines) * step

    def _fill_clipped(self, screen, x, y, width, height, colour,
                      clip_left, clip_top, clip_right, clip_bottom):
        left = max(x, clip_left)
        top = max(y, clip_top)
        right = min(x + width - 1, clip_right)
        bottom = min(y + height - 1, clip_bottom)
        if left <= right and top <= bottom:
            screen.fill_rectangle(left, top, right - left + 1, bottom - top + 1, colour)

    def _draw_line(self, screen, line, x, line_top, colour, background,
                   underline, strikethrough, clip):
        line_width = self.measure_line(line)
        line_height = self.line_height

        # The box that drawing is allowed in: the screen, or the clip box.
        clip_left = 0
        clip_top = 0
        clip_right = screen.width - 1
        clip_bottom = screen.height - 1
        if clip is not None:
            clip_left = max(clip_left, clip[0])
            clip_top = max(clip_top, clip[1])
            clip_right = min(clip_right, clip[2])
            clip_bottom = min(clip_bottom, clip[3])

        # Skip lines that are completely outside the box or, in strips
        # mode, outside the band being drawn right now.
        band_top = screen._origin_y
        buffer_rows = screen.strip_height
        visible_top = max(band_top, clip_top)
        visible_bottom = min(band_top + buffer_rows - 1, clip_bottom)
        if (line_top + line_height + _SKIP_MARGIN <= visible_top
                or line_top - _SKIP_MARGIN > visible_bottom
                or x > clip_right or x + line_width <= clip_left):
            return line_width

        if background is not None and line_width > 0:
            self._fill_clipped(screen, x, line_top, line_width, line_height, background,
                               clip_left, clip_top, clip_right, clip_bottom)
        elif screen._tracking:
            screen._mark_dirty(max(line_top - _SKIP_MARGIN, clip_top),
                               min(line_top + line_height + _SKIP_MARGIN, clip_bottom))

        buffer = screen._buffer
        screen_width = screen.width
        baseline_y = line_top + self.ascent
        parameters = self._parameters
        blend = self._blend_glyph

        # The rows of the buffer that may be drawn on (the last one excluded)
        rows_start = max(clip_top - band_top, 0)
        rows_end = min(clip_bottom + 1 - band_top, buffer_rows)

        parameters[6] = screen_width * 2
        parameters[7] = (colour >> 11) & 31
        parameters[8] = (colour >> 5) & 63
        parameters[9] = colour & 31
        parameters[10] = colour >> 8
        parameters[11] = colour & 255

        pen_x = x
        for character in line:
            glyph = self._glyph(ord(character))
            if glyph is None:
                continue
            width, height, sideways_shift, upward_shift, advance, picture = glyph
            if width > 0:
                glyph_x = pen_x + sideways_shift
                glyph_y = baseline_y + upward_shift - band_top

                first_column = 0
                if glyph_x < clip_left:
                    first_column = clip_left - glyph_x
                last_column = width
                if glyph_x + width > clip_right + 1:
                    last_column = clip_right + 1 - glyph_x
                first_row = 0
                if glyph_y < rows_start:
                    first_row = rows_start - glyph_y
                last_row = height
                if glyph_y + height > rows_end:
                    last_row = rows_end - glyph_y

                if first_column < last_column and first_row < last_row:
                    parameters[0] = (width + 3) >> 2
                    parameters[1] = first_row
                    parameters[2] = last_row
                    parameters[3] = first_column
                    parameters[4] = last_column
                    parameters[5] = ((glyph_y + first_row) * screen_width
                                     + glyph_x + first_column) * 2
                    blend(buffer, picture, parameters)
            pen_x += advance

        if underline:
            thickness = 2 if line_height >= 24 else 1
            self._fill_clipped(screen, x, baseline_y + 2, line_width, thickness, colour,
                               clip_left, clip_top, clip_right, clip_bottom)
        if strikethrough:
            thickness = 2 if line_height >= 24 else 1
            self._fill_clipped(screen, x, baseline_y - self.ascent // 3, line_width,
                               thickness, colour, clip_left, clip_top, clip_right, clip_bottom)
        return line_width
