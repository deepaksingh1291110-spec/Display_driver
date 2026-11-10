"""
nokia_graphics.py - a drawing surface that stays inside a RAM budget.

Copy this file to the Pico next to nokia_display.py and nokia_fast.py.
It does not change nokia_display.py. It is built on top of it.

THE IDEA
You give Screen a memory budget (default 100 KB). Screen looks at the
size of the display and picks the best way of drawing that fits:

  1. "full buffer with change tracking"  (fastest, needs the most memory)
       Keeps the whole picture and a copy of what the display shows now.
       Sends only the rows that changed.
  2. "full buffer"
       Keeps the whole picture. Sends all of it every frame.
  3. "strips"                            (needs the least memory)
       Keeps only a band of rows. The picture is drawn band by band and
       each band is sent as soon as it is ready. A full picture never
       exists in memory. The scene is drawn once for every band.

HOW TO DRAW SO IT WORKS IN ALL THREE WAYS
Put all your drawing in one function and give it to render():

    def draw_scene(screen):
        screen.draw_text("Hello", 10, 10, WHITE)
        screen.fill_circle(60, 80, 20, RED)

    screen.render(draw_scene, background=BLACK)

render() calls your function once (full buffer ways) or once per band
(strips way). Because of that, draw_scene must draw the WHOLE picture
every time, and must not change anything outside itself while drawing.

Create Screen AFTER display.start(), after choosing the rotation and
after display.use_hardware_spi(). Hardware SPI is required.
"""
import gc
import os
import framebuf

# These helpers already exist in nokia_display.py and are reused here.
from nokia_display import (_python_pack_data, _python_mark_changed_rows,
                           _python_copy_region, _fast_tools_work)

# ===============================
# MEMORY PLANNING
# ===============================
DEFAULT_BUDGET_BYTES = 100 * 1024

MODE_FULL_BUFFER_WITH_CHANGE_TRACKING = "full buffer with change tracking"
MODE_FULL_BUFFER = "full buffer"
MODE_STRIPS = "strips"

# Pixels are packed into 9-bit words and sent in pieces of this many data
# bytes. Must be a multiple of 8. 2048 data bytes become 2304 packed bytes.
SEND_CHUNK_DATA_BYTES = 2048
SEND_PACKED_BYTES = SEND_CHUNK_DATA_BYTES // 8 * 9

# Allowance for Python objects, the nokia_fast code and small lists.
# The real use is measured after allocating (see memory_used_bytes), so if
# this turns out too generous it can be lowered.
SAFETY_BYTES = 6144

MINIMUM_STRIP_ROWS = 4


def plan_memory(width, height, budget_bytes, reserve_bytes=0):
    """Return the ways of drawing that fit, best first, as a list of
    (mode, rows_in_buffer, planned_bytes).
    reserve_bytes is memory kept free for other things (fonts, 3D data)."""
    usable = budget_bytes - reserve_bytes
    row_bytes = width * 2
    frame_bytes = row_bytes * height
    fixed = SEND_PACKED_BYTES + SAFETY_BYTES
    plans = []

    with_tracking = 2 * frame_bytes + height + fixed
    if with_tracking <= usable:
        plans.append((MODE_FULL_BUFFER_WITH_CHANGE_TRACKING, height, with_tracking))

    full = frame_bytes + fixed
    if full <= usable:
        plans.append((MODE_FULL_BUFFER, height, full))

    rows_that_fit = (usable - fixed) // row_bytes
    if rows_that_fit >= MINIMUM_STRIP_ROWS:
        if rows_that_fit > height:
            rows_that_fit = height
        passes = -(-height // rows_that_fit)        # round up
        strip_rows = -(-height // passes)           # even out the bands
        plans.append((MODE_STRIPS, strip_rows, strip_rows * row_bytes + fixed))

    return plans


def _memory_in_use():
    if hasattr(gc, "mem_alloc"):
        return gc.mem_alloc()
    return 0


def _draw_nothing(screen):
    pass


def _swap_bytes(colour):
    # The display wants the high byte first. The memory picture stores each
    # pixel low byte first, so the two bytes are swapped on the way in.
    return ((colour & 0xFF) << 8) | (colour >> 8)


class Screen:
    def __init__(self, display, budget_bytes=DEFAULT_BUDGET_BYTES,
                 reserve_bytes=0, mode=None, use_fast_helpers=True):
        """display        a started Display that is using hardware SPI
        budget_bytes   the most RAM this screen may use
        reserve_bytes  part of the budget kept free for other features
        mode           None = choose automatically, or force one of the
                       three MODE_ names above"""
        if display._spi is None and display._link is None:
            raise RuntimeError("Call display.use_hardware_spi() (or use_spi_dma() or "
                               "use_pio_dma()) before creating Screen.")

        self._display = display
        self.budget_bytes = budget_bytes
        self.reserve_bytes = reserve_bytes
        self._requested_mode = mode
        self._rotation_listeners = []
        # With PIO + DMA the picture can go out in the background while the next
        # frame is drawn (only in 'full buffer with change tracking'). Set to
        # False to make show() wait until everything has been sent.
        self.background_sending = True

        gc.collect()
        baseline = _memory_in_use()
        self._load_helpers(use_fast_helpers)
        gc.collect()
        self._helper_bytes = _memory_in_use() - baseline

        self._build()

    def _build(self):
        """Choose the way of drawing for the display's current size and
        allocate the memory for it. Used when the Screen is created and
        again every time the rotation changes between portrait and landscape."""
        display = self._display
        self.width = display.width
        self.height = display.height
        usable = self.budget_bytes - self.reserve_bytes
        mode = self._requested_mode

        plans = plan_memory(self.width, self.height, self.budget_bytes, self.reserve_bytes)
        if mode is not None:
            plans = [plan for plan in plans if plan[0] == mode]
        if not plans:
            raise MemoryError(self._explain_no_plan(usable, mode))

        gc.collect()
        baseline = _memory_in_use()
        self.mode = None
        for plan_mode, rows, planned_bytes in plans:
            self._allocate(plan_mode, rows)
            gc.collect()
            used = _memory_in_use() - baseline + self._helper_bytes
            if used <= usable:
                self.memory_planned_bytes = planned_bytes
                self.memory_used_bytes = used
                break
            self._release()
            gc.collect()
        else:
            raise MemoryError("Measured memory use was over the budget of "
                              + str(usable) + " bytes for every way of drawing.")

        if self.mode == MODE_STRIPS:
            self.passes_per_frame = -(-self.height // self.strip_height)
        else:
            self.passes_per_frame = 1

    # ===============================
    # ROTATION
    # ===============================
    @property
    def rotation(self):
        """The rotation now in use (0 to 3, see nokia_display.py)."""
        return self._display.rotation

    @property
    def mirrored(self):
        return self._display.mirrored

    @property
    def is_landscape(self):
        return self.width > self.height

    def set_rotation(self, rotation, mirrored=False):
        """Turn the picture while the program runs. rotation is one of the
        constants in nokia_display.py (PORTRAIT, LANDSCAPE_FLEX_CABLE_ON_LEFT,
        PORTRAIT_UPSIDE_DOWN, LANDSCAPE_FLEX_CABLE_ON_RIGHT). mirrored=True
        also flips the picture left to right.

        The display goes black. The screen size may change (portrait is
        128 x 160, landscape is 160 x 128), so read screen.width and
        screen.height again and draw your next picture for the new size.
        The memory is released and allocated again, so the screen never
        needs more memory than before. Anything made for the old size
        (a Marquee, a clip rectangle) has to be made again."""
        self.wait_until_sent()
        self._display.set_rotation(rotation, mirrored)
        self._release()
        gc.collect()
        self._build()

        # Black, so the old picture does not show up turned the wrong way.
        if self.mode == MODE_STRIPS:
            self.render(_draw_nothing, background=0)
        else:
            self.fill_screen(0)
            self.show(full=True, wait=True)

        for listener in self._rotation_listeners:
            listener(self)

    def rotate_clockwise(self):
        """A quarter turn clockwise, as seen on the fixed display."""
        self.set_rotation((self.rotation + 1) % 4, self.mirrored)

    def rotate_anticlockwise(self):
        """A quarter turn anticlockwise, as seen on the fixed display."""
        self.set_rotation((self.rotation + 3) % 4, self.mirrored)

    def add_rotation_listener(self, function):
        """function(screen) is called after every set_rotation. Objects that
        keep something for the old size (Shapes does) use this to update."""
        self._rotation_listeners.append(function)

    # ===============================
    # SETUP
    # ===============================
    def _load_helpers(self, use_fast_helpers):
        self._pack_data = _python_pack_data
        self._mark_changed_rows = _python_mark_changed_rows
        self._copy_region = _python_copy_region
        self.fast_helpers_in_use = False
        if use_fast_helpers:
            try:
                import nokia_fast
                if _fast_tools_work(nokia_fast):
                    self._pack_data = nokia_fast.pack_data
                    self._mark_changed_rows = nokia_fast.mark_changed_rows
                    self._copy_region = nokia_fast.copy_region
                    self.fast_helpers_in_use = True
            except Exception:
                pass
            if not self.fast_helpers_in_use:
                print("nokia_graphics: nokia_fast.py not found or not working. Using slower Python code.")

    def _allocate(self, mode, rows):
        self.mode = mode
        self.strip_height = rows
        self._tracking = (mode == MODE_FULL_BUFFER_WITH_CHANGE_TRACKING)
        row_bytes = self.width * 2

        self._buffer = bytearray(rows * row_bytes)
        self._buffer_view = memoryview(self._buffer)
        self._frame = framebuf.FrameBuffer(self._buffer, self.width, rows, framebuf.RGB565)
        self._packed = bytearray(SEND_PACKED_BYTES)
        self._packed_spare = None      # the second piece buffer, made when SPI + DMA needs it

        if self._tracking:
            self._previous = bytearray(rows * row_bytes)
            self._row_flags = bytearray(self.height)
        else:
            self._previous = None
            self._row_flags = None

        # Changed rows closer together than this are sent as one block
        self.merge_gap_rows = 3
        self._dirty_top = None
        self._dirty_bottom = None
        self._force_full_update = True

        # In strips mode: the screen row that the top of the buffer shows.
        self._origin_y = 0

    def _release(self):
        self._buffer = None
        self._buffer_view = None
        self._frame = None
        self._packed = None
        self._packed_spare = None
        self._previous = None
        self._row_flags = None

    def _explain_no_plan(self, usable, mode):
        row_bytes = self.width * 2
        fixed = SEND_PACKED_BYTES + SAFETY_BYTES
        smallest = MINIMUM_STRIP_ROWS * row_bytes + fixed
        text = "Budget too small: " + str(usable) + " bytes usable."
        if mode is None:
            text += " The smallest way (strips) needs " + str(smallest) + " bytes."
        else:
            text += " The way '" + mode + "' does not fit. Try mode=None for automatic."
        return text

    def memory_report(self):
        """A few lines of text about the chosen way and the memory used."""
        lines = [
            "Pixels sent by : " + self._display.pixel_backend,
            "Way of drawing : " + self.mode,
            "Rows in buffer : " + str(self.strip_height) + " of " + str(self.height)
            + " (" + str(self.passes_per_frame) + " pass(es) per frame)",
            "Budget         : " + str(self.budget_bytes) + " bytes"
            + " (" + str(self.reserve_bytes) + " kept free for other features)",
            "Planned use    : " + str(self.memory_planned_bytes) + " bytes",
            "Measured use   : " + str(self.memory_used_bytes) + " bytes",
        ]
        if hasattr(gc, "mem_free"):
            lines.append("Free RAM now   : " + str(gc.mem_free()) + " bytes")
        return "\n".join(lines)

    # ===============================
    # ONE WHOLE FRAME
    # ===============================
    def render(self, draw_scene, background=None):
        """Draw one complete frame and send it to the display.
        draw_scene(screen) must draw the whole picture.
        background: colour to clear to before drawing. Leave it as None
        in the full buffer ways to keep the previous picture and only
        draw what changed (fastest). In strips mode the buffer is reused
        for every band, so always give a background there, or draw one."""
        if self.mode == MODE_STRIPS:
            try:
                for strip_top in range(0, self.height, self.strip_height):
                    self._origin_y = strip_top
                    if background is not None:
                        self._frame.fill(_swap_bytes(background))
                    draw_scene(self)
                    self._send_strip(strip_top)
            finally:
                self._origin_y = 0
        else:
            if background is not None:
                self.fill_screen(background)
            draw_scene(self)
            self.show()

    # ===============================
    # DRAWING (into memory only)
    # In strips mode, a drawing call only changes the band that is being
    # drawn right now. Everything outside it is ignored automatically.
    # ===============================
    def _mark_dirty(self, top, bottom):
        if top > bottom:
            top, bottom = bottom, top
        if top < 0:
            top = 0
        if bottom > self.height - 1:
            bottom = self.height - 1
        if top > bottom:
            return
        if self._dirty_top is None:
            self._dirty_top = top
            self._dirty_bottom = bottom
        else:
            if top < self._dirty_top:
                self._dirty_top = top
            if bottom > self._dirty_bottom:
                self._dirty_bottom = bottom

    def fill_screen(self, colour):
        self._frame.fill(_swap_bytes(colour))
        if self._tracking:
            self._mark_dirty(0, self.height - 1)

    def draw_pixel(self, x, y, colour):
        self._frame.pixel(x, y - self._origin_y, _swap_bytes(colour))
        if self._tracking:
            self._mark_dirty(y, y)

    def fill_rectangle(self, x, y, width, height, colour):
        self._frame.fill_rect(x, y - self._origin_y, width, height, _swap_bytes(colour))
        if self._tracking:
            self._mark_dirty(y, y + height - 1)

    def draw_rectangle(self, x, y, width, height, colour):
        self._frame.rect(x, y - self._origin_y, width, height, _swap_bytes(colour))
        if self._tracking:
            self._mark_dirty(y, y + height - 1)

    def draw_line(self, x_start, y_start, x_end, y_end, colour):
        origin = self._origin_y
        self._frame.line(x_start, y_start - origin, x_end, y_end - origin, _swap_bytes(colour))
        if self._tracking:
            self._mark_dirty(y_start, y_end)

    def draw_circle(self, centre_x, centre_y, radius, colour):
        self._frame.ellipse(centre_x, centre_y - self._origin_y, radius, radius,
                            _swap_bytes(colour))
        if self._tracking:
            self._mark_dirty(centre_y - radius, centre_y + radius)

    def fill_circle(self, centre_x, centre_y, radius, colour):
        self._frame.ellipse(centre_x, centre_y - self._origin_y, radius, radius,
                            _swap_bytes(colour), True)
        if self._tracking:
            self._mark_dirty(centre_y - radius, centre_y + radius)

    def measure_text(self, text, scale=1):
        """Return (width, height) in pixels that the text will take."""
        lines = text.split("\n")
        longest_line = 0
        for line in lines:
            if len(line) > longest_line:
                longest_line = len(line)
        return (longest_line * 8 * scale, len(lines) * 8 * scale)

    def draw_text(self, text, x, y, colour, background_colour=None, scale=1):
        """Draw 8 x 8 pixel text. scale 2 = 16 x 16 per letter, and so on.
        Use \\n for a new line."""
        character_size = 8 * scale
        lines = text.split("\n")
        swapped_colour = _swap_bytes(colour)
        buffer_y = y - self._origin_y

        if background_colour is not None:
            swapped_background = _swap_bytes(background_colour)
            for line_number in range(len(lines)):
                self._frame.fill_rect(x, buffer_y + line_number * character_size,
                                      len(lines[line_number]) * character_size,
                                      character_size, swapped_background)

        if scale == 1:
            for line_number in range(len(lines)):
                self._frame.text(lines[line_number], x, buffer_y + line_number * 8,
                                 swapped_colour)
        else:
            glyph_buffer = bytearray(8)
            glyph = framebuf.FrameBuffer(glyph_buffer, 8, 8, framebuf.MONO_HLSB)
            for line_number in range(len(lines)):
                line = lines[line_number]
                line_y = buffer_y + line_number * character_size
                if line_y >= self.strip_height or line_y + character_size <= 0:
                    continue
                for character_number in range(len(line)):
                    character_x = x + character_number * character_size
                    if character_x >= self.width or character_x + character_size <= 0:
                        continue
                    glyph.fill(0)
                    glyph.text(line[character_number], 0, 0, 1)
                    for row in range(8):
                        column = 0
                        while column < 8:
                            if glyph.pixel(column, row):
                                run_start = column
                                while column < 8 and glyph.pixel(column, row):
                                    column += 1
                                self._frame.fill_rect(character_x + run_start * scale,
                                                      line_y + row * scale,
                                                      (column - run_start) * scale,
                                                      scale, swapped_colour)
                            else:
                                column += 1

        if self._tracking:
            text_width, text_height = self.measure_text(text, scale)
            self._mark_dirty(y, y + text_height - 1)

    def draw_image_file(self, filename, x=0, y=0, width=None, height=None):
        """Draw a raw 16-bit image file (high byte first) with its top-left
        corner at x, y. Works in every way of drawing: in strips mode only
        the rows of the current band are read from the file."""
        if width is None:
            width = self.width
        if height is None:
            height = self.height

        expected_size = width * height * 2
        actual_size = os.stat(filename)[6]
        if actual_size != expected_size:
            raise ValueError("image file is " + str(actual_size) + " bytes, but "
                             + str(width) + " x " + str(height) + " needs "
                             + str(expected_size) + " bytes")
        if x < 0 or y < 0 or x + width > self.width or y + height > self.height:
            raise ValueError("image does not fit on the screen")

        band_top = self._origin_y
        band_bottom = band_top + self.strip_height      # one past the last row
        first_row = y if y > band_top else band_top
        last_row = y + height if y + height < band_bottom else band_bottom
        if first_row >= last_row:
            return

        image_row_bytes = width * 2
        with open(filename, "rb") as image_file:
            for row in range(first_row, last_row):
                image_file.seek((row - y) * image_row_bytes)
                start = ((row - band_top) * self.width + x) * 2
                image_file.readinto(self._buffer_view[start:start + image_row_bytes])

        if self._tracking:
            self._mark_dirty(y, y + height - 1)

    # ===============================
    # SENDING TO THE SCREEN
    # ===============================
    def show(self, full=False, wait=False):
        """Send the picture. In 'full buffer with change tracking' only the
        rows that changed are sent. show(full=True) sends everything.
        Not available in strips mode: use render() there.

        With PIO + DMA the picture goes out in the background: show() comes
        back as soon as it has started, and you can draw the next frame at
        once (the data being sent is a copy, so drawing cannot disturb it).
        The next show() waits for the one before. show(wait=True), or
        wait_until_sent(), waits until everything has left."""
        if self.mode == MODE_STRIPS:
            raise RuntimeError("Strips mode has no show(). Use render(draw_scene).")

        display = self._display
        link = display._link
        width = self.width
        height = self.height
        bytes_per_row = width * 2

        if self.mode == MODE_FULL_BUFFER or full or self._force_full_update:
            bands = [(0, height - 1)]
        else:
            if self._dirty_top is None:
                if wait:
                    self.wait_until_sent()
                return
            first_row = self._dirty_top
            last_row = self._dirty_bottom
            self._mark_changed_rows(self._buffer, self._previous, bytes_per_row // 4,
                                    first_row, last_row, self._row_flags)
            bands = self._find_bands(first_row, last_row)

        self._dirty_top = None
        self._dirty_bottom = None
        self._force_full_update = False

        background = (self._tracking and self.background_sending
                      and link is not None and link.takes_raw_pixels)

        try:
            for band_top, band_bottom in bands:
                offset = band_top * bytes_per_row
                byte_count = (band_bottom - band_top + 1) * bytes_per_row
                if background:
                    # Send from the copy in self._previous: the next frame can be
                    # drawn into self._buffer while these bytes are still going out.
                    link.wait()
                    self._copy_region(self._buffer, self._previous, offset // 4, byte_count // 4)
                    display.set_window(0, band_top, width - 1, band_bottom)
                    link.start_raw(self._previous, offset, byte_count)
                else:
                    display.set_window(0, band_top, width - 1, band_bottom)
                    self._send_region(offset, byte_count)
                    if self._tracking:
                        self._copy_region(self._buffer, self._previous, offset // 4,
                                          byte_count // 4)
            if wait:
                self.wait_until_sent()
        except Exception:
            # Something did not go out: send the whole picture next time.
            self._force_full_update = True
            raise

    def wait_until_sent(self):
        """Wait until a picture that is going out in the background has
        completely left. Does nothing if nothing is going out."""
        link = self._display._link
        if link is not None and link.in_flight:
            try:
                link.wait()
            except Exception:
                self._force_full_update = True
                raise

    def _find_bands(self, first_row, last_row):
        flags = self._row_flags
        bands = []
        band_top = -1
        last_changed = -1
        for row in range(first_row, last_row + 1):
            if flags[row]:
                if band_top < 0:
                    band_top = row
                last_changed = row
            elif band_top >= 0 and row - last_changed > self.merge_gap_rows:
                bands.append((band_top, last_changed))
                band_top = -1
        if band_top >= 0:
            bands.append((band_top, last_changed))
        return bands

    def _send_strip(self, strip_top):
        rows = self.height - strip_top
        if rows > self.strip_height:
            rows = self.strip_height
        self._display.set_window(0, strip_top, self.width - 1, strip_top + rows - 1)
        self._send_region(0, rows * self.width * 2)

    def _send_region(self, offset, byte_count):
        """Send byte_count bytes of the buffer (a whole number of rows) to the
        display, the way the display is set up to send pixels."""
        display = self._display
        link = display._link

        if link is not None and link.takes_raw_pixels:
            # PIO + DMA: the buffer goes out as it is, nothing to pack.
            link.send_raw(self._buffer, offset, byte_count)
            return

        packed = self._packed
        end = offset + byte_count
        position = offset

        if link is not None:
            # SPI + DMA: pack the next piece while the DMA sends the one before.
            if self._packed_spare is None:
                self._packed_spare = bytearray(SEND_PACKED_BYTES)
            pieces = (packed, self._packed_spare)
            which = 0
            sending = False
            display._select_pin.low()
            try:
                while position < end:
                    piece = end - position
                    if piece > SEND_CHUNK_DATA_BYTES:
                        piece = SEND_CHUNK_DATA_BYTES
                    target = pieces[which]
                    self._pack_data(self._buffer, position, target, piece)
                    if sending:
                        link.wait()
                    link.start(target, piece // 8 * 9)
                    sending = True
                    which = 1 - which
                    position += piece
                if sending:
                    link.wait()
            finally:
                display._select_pin.high()
            return

        display._select_pin.low()
        while position < end:
            piece = end - position
            if piece > SEND_CHUNK_DATA_BYTES:
                piece = SEND_CHUNK_DATA_BYTES
            self._pack_data(self._buffer, position, packed, piece)
            if piece == SEND_CHUNK_DATA_BYTES:
                display._spi.write(packed)
            else:
                display._spi.write(memoryview(packed)[0:piece // 8 * 9])
            position += piece
        display._select_pin.high()
