from machine import Pin, SPI
import framebuf
import os
import time

# ===============================
# COLOURS (16-bit, red-green-blue 5-6-5)
# ===============================
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
YELLOW = 0xFFE0
CYAN = 0x07FF
MAGENTA = 0xF81F
WHITE = 0xFFFF
BLACK = 0x0000


def make_colour(red, green, blue):
    """Turn red, green, blue (each 0 to 255) into one 16-bit colour."""
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


# ===============================
# ROTATIONS
# The name says where the flex cable is when the picture is upright.
# ===============================
PORTRAIT_FLEX_CABLE_AT_TOP = 0
SIDEWAYS_FLEX_CABLE_ON_LEFT = 1
PORTRAIT_FLEX_CABLE_AT_BOTTOM = 2
SIDEWAYS_FLEX_CABLE_ON_RIGHT = 3

# Shorter names for the same four rotations
PORTRAIT = PORTRAIT_FLEX_CABLE_AT_TOP
LANDSCAPE_FLEX_CABLE_ON_LEFT = SIDEWAYS_FLEX_CABLE_ON_LEFT
PORTRAIT_UPSIDE_DOWN = PORTRAIT_FLEX_CABLE_AT_BOTTOM
LANDSCAPE_FLEX_CABLE_ON_RIGHT = SIDEWAYS_FLEX_CABLE_ON_RIGHT

# The memory access byte for each rotation (0, 1, 2, 3), and the one that
# gives the mirror image of it: the picture flipped left to right, so that
# x runs the other way. Both lists are the values tested on this display.
_memory_access_values = (0x00, 0x60, 0xC0, 0xA0)
_memory_access_values_mirrored = (0x40, 0xE0, 0x80, 0x20)


class Display:
    def __init__(self, clock_pin_number, data_pin_number,
                 select_pin_number, reset_pin_number,
                 rotation=PORTRAIT_FLEX_CABLE_AT_TOP, mirrored=False):
        self._clock_pin = Pin(clock_pin_number, Pin.OUT)
        self._data_pin = Pin(data_pin_number, Pin.OUT)
        self._select_pin = Pin(select_pin_number, Pin.OUT)
        self._reset_pin = Pin(reset_pin_number, Pin.OUT)
        self._select_pin.high()
        self._clock_pin.high()

        # How long to wait on each step of every bit, in microseconds.
        # 3 is the value that is known to work.
        self.bit_delay_microseconds = 3

        self.width = 128
        self.height = 160
        self._column_offset = 2
        self._row_offset = 1
        self._rotation = rotation
        self._mirrored = mirrored

        # Needed to switch to the fast hardware method and back
        self._clock_pin_number = clock_pin_number
        self._data_pin_number = data_pin_number
        self._spi = None
        self._link = None            # DMA sender, see use_spi_dma / use_pio_dma

    # ===============================
    # SENDING
    # ===============================
    def _send_9bit(self, value, is_command):
        delay = self.bit_delay_microseconds
        data_pin = self._data_pin
        clock_pin = self._clock_pin

        self._select_pin.low()

        # First bit: 0 means command, 1 means data
        data_pin.value(0 if is_command else 1)
        time.sleep_us(delay)
        clock_pin.low(); time.sleep_us(delay); clock_pin.high()

        for bit_position in range(8):
            data_pin.value((value >> (7 - bit_position)) & 1)
            time.sleep_us(delay)
            clock_pin.low(); time.sleep_us(delay); clock_pin.high()

        self._select_pin.high()

    def send_command(self, command_value, data_values=()):
        if self._link is not None and self._link.in_flight:
            self._link.wait()            # a picture is still going out: let it finish first
        if self._spi is not None:
            words = [command_value]
            for data_value in data_values:
                words.append(0x100 | data_value)
            self._select_pin.low()
            self._spi.write(self._pack_words(words))
            self._select_pin.high()
            return

        self._send_9bit(command_value, True)
        for data_value in data_values:
            self._send_9bit(data_value, False)

    def _send_colour(self, colour_value):
        if self._spi is not None:
            high_word = 0x100 | (colour_value >> 8)
            low_word = 0x100 | (colour_value & 0xFF)
            self._select_pin.low()
            self._spi.write(self._pack_words([high_word, low_word]))
            self._select_pin.high()
            return

        self._send_9bit(colour_value >> 8, False)
        self._send_9bit(colour_value & 0xFF, False)

    # ===============================
    # STEP 5: FAST SENDING WITH THE PICO'S HARDWARE SPI
    # Call start() first (it uses the slow, safe method),
    # then call use_hardware_spi().
    # ===============================
    def use_hardware_spi(self, baudrate=16000000, spi_number=0):
        """Switch to fast sending. Pins 6 and 7 belong to SPI number 0.
        On this board the SPI runs from a 48 MHz clock, so 24 MHz is the
        fastest it can really go, whatever higher speed you ask for."""
        self._close_link()
        if self._spi is not None:
            self._spi.deinit()
        self._spi = SPI(spi_number, baudrate=baudrate, polarity=1, phase=1,
                        bits=8, firstbit=SPI.MSB,
                        sck=Pin(self._clock_pin_number),
                        mosi=Pin(self._data_pin_number))

    def use_bit_banging(self):
        """Go back to the slow, simple sending method."""
        self._close_link()
        if self._spi is not None:
            self._spi.deinit()
            self._spi = None
        self._reclaim_pins()

    def use_spi_dma(self, baudrate=24000000):
        """Hardware SPI, but the pixels are sent by DMA: the CPU is free
        while they go out (it packs the next piece meanwhile).
        The commands still go through the SPI as before.
        Needs nokia_dma_link.py. Same speed limit as use_hardware_spi."""
        self.use_hardware_spi(baudrate)
        import nokia_dma_link
        self._link = nokia_dma_link.SpiDmaLink(self)

    def use_pio_dma(self, bit_clock_hz=62500000, command_delay_microseconds=0):
        """Send the pixels with a PIO state machine fed by DMA. The raw
        picture bytes go straight out (no packing), the CPU is free, and the
        clock can be far faster than the SPI: tested correct from 25 up to
        75 MHz on the Nokia display. The commands are sent by bit-banging
        (slow, but they are few). command_delay_microseconds is the wait per
        bit for those commands: 0 is fastest and worked on this display; use 3
        (the old value) if you ever see garbage at the start of a picture.
        Use this with Screen; the drawing methods of Display itself fall back
        to bit-banging in this mode.
        Needs nokia_dma_link.py."""
        self.use_bit_banging()
        import nokia_dma_link
        self._link = nokia_dma_link.PioDmaLink(self, bit_clock_hz, command_delay_microseconds)

    @property
    def pixel_backend(self):
        """A few words on how the pixels are sent now."""
        if self._link is not None:
            return self._link.name
        if self._spi is not None:
            return "hardware SPI"
        return "bit-banging"

    def _close_link(self):
        if self._link is not None:
            self._link.close()
            self._link = None

    def _reclaim_pins(self):
        # The clock and data pins as normal outputs again (after PIO used them).
        self._clock_pin = Pin(self._clock_pin_number, Pin.OUT)
        self._data_pin = Pin(self._data_pin_number, Pin.OUT)
        self._clock_pin.high()

    @staticmethod
    def _pack_words(words):
        # Each word is 9 bits: 0x100 plus the value for data, or just the
        # value for a command. The words are joined and cut into bytes.
        # Spare bits at the end are filled with zeros.
        packed = bytearray()
        accumulator = 0
        bit_count = 0
        for word in words:
            accumulator = (accumulator << 9) | word
            bit_count += 9
            while bit_count >= 8:
                bit_count -= 8
                packed.append((accumulator >> bit_count) & 0xFF)
                accumulator &= (1 << bit_count) - 1
        if bit_count > 0:
            packed.append((accumulator << (8 - bit_count)) & 0xFF)
        return packed

    @staticmethod
    def _pack_data_bytes(data):
        # Faster packing for data only. The length must be a multiple of 8:
        # every 8 data bytes (8 words of 9 bits = 72 bits) become exactly 9 bytes.
        packed = bytearray((len(data) // 8) * 9)
        out = 0
        for position in range(0, len(data), 8):
            d0 = data[position]
            d1 = data[position + 1]
            d2 = data[position + 2]
            d3 = data[position + 3]
            d4 = data[position + 4]
            d5 = data[position + 5]
            d6 = data[position + 6]
            d7 = data[position + 7]
            packed[out] = 0x80 | (d0 >> 1)
            packed[out + 1] = ((d0 & 1) << 7) | 0x40 | (d1 >> 2)
            packed[out + 2] = ((d1 & 3) << 6) | 0x20 | (d2 >> 3)
            packed[out + 3] = ((d2 & 7) << 5) | 0x10 | (d3 >> 4)
            packed[out + 4] = ((d3 & 15) << 4) | 0x08 | (d4 >> 5)
            packed[out + 5] = ((d4 & 31) << 3) | 0x04 | (d5 >> 6)
            packed[out + 6] = ((d5 & 63) << 2) | 0x02 | (d6 >> 7)
            packed[out + 7] = ((d6 & 127) << 1) | 0x01
            packed[out + 8] = d7
            out += 9
        return packed

    def _fill_window_with_hardware(self, pixel_count, colour):
        high_word = 0x100 | (colour >> 8)
        low_word = 0x100 | (colour & 0xFF)

        self._select_pin.low()
        if pixel_count < 256:
            self._spi.write(self._pack_words([high_word, low_word] * pixel_count))
        else:
            # 4 pixels = 72 bits = exactly 9 bytes.
            # 64 of those = 256 pixels = 576 bytes, sent again and again.
            four_pixels = self._pack_words([high_word, low_word] * 4)
            chunk = bytearray()
            for group_number in range(64):
                chunk += four_pixels

            for chunk_number in range(pixel_count // 256):
                self._spi.write(chunk)
            leftover_pixels = pixel_count % 256
            if leftover_pixels > 0:
                self._spi.write(self._pack_words([high_word, low_word] * leftover_pixels))
        self._select_pin.high()

    # ===============================
    # START-UP
    # ===============================
    def start(self):
        self._reset_pin.low()
        time.sleep(0.1)
        self._reset_pin.high()
        time.sleep(0.1)

        self.send_command(0x01)          # software reset
        time.sleep(0.15)

        self.send_command(0x11)          # sleep out
        time.sleep(0.2)

        self.send_command(0xC9, (0x08,)) # kept from the working code
        self.send_command(0x3A, (0x05,)) # 16 bits per pixel

        self.set_rotation(self._rotation, self._mirrored)

        self.send_command(0x29)          # display on
        time.sleep(0.1)

    # ===============================
    # ROTATION
    # ===============================
    def set_rotation(self, rotation, mirrored=False):
        """Turn the picture. rotation is one of the four constants above
        (0 to 3). mirrored=True flips the picture left to right as well, so
        that x runs the other way (like text seen in a mirror).
        After this call width and height may have changed (a sideways
        rotation is 160 wide and 128 high). What is on the display is not
        redrawn: draw a new picture."""
        if rotation < 0 or rotation > 3:
            raise ValueError("rotation must be 0, 1, 2 or 3")
        self._rotation = rotation
        self._mirrored = bool(mirrored)

        if rotation == SIDEWAYS_FLEX_CABLE_ON_LEFT or rotation == SIDEWAYS_FLEX_CABLE_ON_RIGHT:
            self.width = 160
            self.height = 128
            self._column_offset = 1
            self._row_offset = 2
        else:
            self.width = 128
            self.height = 160
            self._column_offset = 2
            self._row_offset = 1

        if mirrored:
            self.send_command(0x36, (_memory_access_values_mirrored[rotation],))
        else:
            self.send_command(0x36, (_memory_access_values[rotation],))

    @property
    def rotation(self):
        """The rotation now in use (0 to 3)."""
        return self._rotation

    @property
    def mirrored(self):
        """True when the picture is flipped left to right."""
        return self._mirrored

    @property
    def is_landscape(self):
        return self.width > self.height

    # ===============================
    # WINDOW
    # ===============================
    def set_window(self, x_start, y_start, x_end, y_end):
        first_column = x_start + self._column_offset
        last_column = x_end + self._column_offset
        first_row = y_start + self._row_offset
        last_row = y_end + self._row_offset

        self.send_command(0x2A, (0x00, first_column, 0x00, last_column))
        self.send_command(0x2B, (0x00, first_row, 0x00, last_row))
        self.send_command(0x2C)

    # ===============================
    # STEP 1 DRAWING: SCREEN AND PIXELS
    # ===============================
    def fill_screen(self, colour):
        self.fill_rectangle(0, 0, self.width, self.height, colour)

    def draw_pixel(self, x, y, colour):
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        self.set_window(x, y, x, y)
        self._send_colour(colour)

    # ===============================
    # STEP 2 DRAWING: RECTANGLES, LINES, CIRCLES
    # ===============================
    def fill_rectangle(self, x, y, width, height, colour):
        """Solid rectangle. x and y are the top-left corner."""
        x_end = x + width - 1
        y_end = y + height - 1

        # Keep only the part that is on the screen
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x_end > self.width - 1:
            x_end = self.width - 1
        if y_end > self.height - 1:
            y_end = self.height - 1
        if x > x_end or y > y_end:
            return

        self.set_window(x, y, x_end, y_end)
        pixel_count = (x_end - x + 1) * (y_end - y + 1)

        if self._spi is not None:
            self._fill_window_with_hardware(pixel_count, colour)
            return

        high_byte = colour >> 8
        low_byte = colour & 0xFF
        for pixel_number in range(pixel_count):
            self._send_9bit(high_byte, False)
            self._send_9bit(low_byte, False)

    def draw_rectangle(self, x, y, width, height, colour):
        """Rectangle outline, one pixel thick."""
        if width < 1 or height < 1:
            return
        self.fill_rectangle(x, y, width, 1, colour)                    # top
        self.fill_rectangle(x, y + height - 1, width, 1, colour)       # bottom
        self.fill_rectangle(x, y, 1, height, colour)                   # left
        self.fill_rectangle(x + width - 1, y, 1, height, colour)       # right

    def draw_line(self, x_start, y_start, x_end, y_end, colour):
        """Straight line between any two points."""
        if y_start == y_end:
            left = min(x_start, x_end)
            right = max(x_start, x_end)
            self.fill_rectangle(left, y_start, right - left + 1, 1, colour)
            return
        if x_start == x_end:
            top = min(y_start, y_end)
            bottom = max(y_start, y_end)
            self.fill_rectangle(x_start, top, 1, bottom - top + 1, colour)
            return

        x_distance = abs(x_end - x_start)
        y_distance = abs(y_end - y_start)
        x_step = 1 if x_start < x_end else -1
        y_step = 1 if y_start < y_end else -1
        error = x_distance - y_distance
        x = x_start
        y = y_start

        while True:
            self.draw_pixel(x, y, colour)
            if x == x_end and y == y_end:
                break
            doubled_error = 2 * error
            if doubled_error > -y_distance:
                error -= y_distance
                x += x_step
            if doubled_error < x_distance:
                error += x_distance
                y += y_step

    def draw_circle(self, centre_x, centre_y, radius, colour):
        """Circle outline, one pixel thick."""
        if radius < 1:
            self.draw_pixel(centre_x, centre_y, colour)
            return
        x = radius
        y = 0
        decision = 1 - x
        while y <= x:
            self.draw_pixel(centre_x + x, centre_y + y, colour)
            self.draw_pixel(centre_x - x, centre_y + y, colour)
            self.draw_pixel(centre_x + x, centre_y - y, colour)
            self.draw_pixel(centre_x - x, centre_y - y, colour)
            self.draw_pixel(centre_x + y, centre_y + x, colour)
            self.draw_pixel(centre_x - y, centre_y + x, colour)
            self.draw_pixel(centre_x + y, centre_y - x, colour)
            self.draw_pixel(centre_x - y, centre_y - x, colour)
            y += 1
            if decision <= 0:
                decision += 2 * y + 1
            else:
                x -= 1
                decision += 2 * (y - x) + 1

    def fill_circle(self, centre_x, centre_y, radius, colour):
        """Solid circle."""
        if radius < 1:
            self.draw_pixel(centre_x, centre_y, colour)
            return
        for row_offset in range(-radius, radius + 1):
            half_width = int((radius * radius - row_offset * row_offset) ** 0.5)
            self.fill_rectangle(centre_x - half_width, centre_y + row_offset,
                                2 * half_width + 1, 1, colour)

    # ===============================
    # STEP 3 DRAWING: IMAGES FROM A FILE
    # ===============================
    def show_image_file(self, filename, x=0, y=0, width=None, height=None):
        """Show a raw 16-bit image file (high byte first) with its top-left
        corner at x, y. If width and height are not given, the image must
        fill the whole screen in the current rotation."""
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

        self.set_window(x, y, x + width - 1, y + height - 1)

        if self._spi is not None:
            self._select_pin.low()
            with open(filename, "rb") as image_file:
                while True:
                    chunk = image_file.read(512)
                    if not chunk:
                        break
                    if len(chunk) % 8 == 0:
                        self._spi.write(self._pack_data_bytes(chunk))
                    else:
                        self._spi.write(self._pack_words([0x100 | byte_value for byte_value in chunk]))
            self._select_pin.high()
            return

        with open(filename, "rb") as image_file:
            while True:
                chunk = image_file.read(512)
                if not chunk:
                    break
                for byte_value in chunk:
                    self._send_9bit(byte_value, False)

    # ===============================
    # STEP 4 DRAWING: TEXT
    # Uses the 8 x 8 pixel font that is built into MicroPython.
    # ===============================
    def measure_text(self, text, scale=1):
        """Return (width, height) in pixels that the text will take."""
        lines = text.split("\n")
        longest_line = 0
        for line in lines:
            if len(line) > longest_line:
                longest_line = len(line)
        return (longest_line * 8 * scale, len(lines) * 8 * scale)

    def draw_text(self, text, x, y, colour, background_colour=None, scale=1):
        """Draw text with its top-left corner at x, y.
        scale 1 = 8 x 8 pixels per letter, 2 = 16 x 16, and so on.
        Use \\n for a new line. If background_colour is None the
        picture underneath stays visible."""
        character_size = 8 * scale
        lines = text.split("\n")

        if background_colour is not None:
            for line_number in range(len(lines)):
                self.fill_rectangle(x, y + line_number * character_size,
                                    len(lines[line_number]) * character_size,
                                    character_size, background_colour)

        glyph_buffer = bytearray(8)
        glyph = framebuf.FrameBuffer(glyph_buffer, 8, 8, framebuf.MONO_HLSB)

        for line_number in range(len(lines)):
            line = lines[line_number]
            line_y = y + line_number * character_size
            if line_y >= self.height or line_y + character_size <= 0:
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
                            self.fill_rectangle(character_x + run_start * scale,
                                                line_y + row * scale,
                                                (column - run_start) * scale,
                                                scale, colour)
                        else:
                            column += 1

# ===============================
# STEP 6: BUFFERED DRAWING - ONLY THE CHANGED PARTS ARE SENT
#
# BufferedDisplay keeps a picture of the screen in memory. You draw into
# that picture (instant), then call show(). show() compares the picture
# with what the display already shows and sends only the rows that
# changed. If nothing changed, nothing is sent.
#
# Create it AFTER start(), after choosing the rotation, and after
# use_hardware_spi(). Uses about 130 KB of memory for a full screen.
#
# The helper functions in the separate file nokia_fast.py make it much
# faster. Copy nokia_fast.py to the Pico too. It is only loaded when you
# create a BufferedDisplay. If it is missing, the slower Python versions
# below are used instead (same result, slower).
# To switch the fast helpers off: BufferedDisplay(display, use_fast_helpers=False)
# ===============================
def _python_pack_data(source, source_offset, destination, byte_count):
    packed = Display._pack_data_bytes(memoryview(source)[source_offset:source_offset + byte_count])
    destination[0:len(packed)] = packed


def _python_mark_changed_rows(current, previous, words_per_row, first_row, last_row, flags):
    bytes_per_row = words_per_row * 4
    for row in range(first_row, last_row + 1):
        start = row * bytes_per_row
        if current[start:start + bytes_per_row] != previous[start:start + bytes_per_row]:
            flags[row] = 1
        else:
            flags[row] = 0


def _python_copy_region(source, destination, word_offset, word_count):
    start = word_offset * 4
    end = start + word_count * 4
    destination[start:end] = source[start:end]


def _fast_tools_work(nokia_fast):
    """Check nokia_fast.py gives the same answers as the Python versions."""
    try:
        source = bytearray([(index * 37 + 11) & 0xFF for index in range(80)])
        expected = bytearray(18)
        got = bytearray(18)
        _python_pack_data(source, 8, expected, 16)
        nokia_fast.pack_data(source, 8, got, 16)
        if expected != got:
            return False

        current = bytearray(24)
        previous = bytearray(24)
        current[10] = 5
        flags = bytearray(3)
        nokia_fast.mark_changed_rows(current, previous, 2, 0, 2, flags)
        if flags != bytearray([0, 1, 0]):
            return False

        destination = bytearray(24)
        nokia_fast.copy_region(current, destination, 2, 4)
        if destination[8:24] != current[8:24] or destination[0:8] != bytearray(8):
            return False
        return True
    except Exception:
        return False


class BufferedDisplay:
    def __init__(self, display, use_fast_helpers=True):
        import gc
        gc.collect()

        # Slower Python versions by default; nokia_fast.py replaces them if it works
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
                print("nokia_display: nokia_fast.py not found or not working. Using slower Python code.")

        self._display = display
        self.width = display.width
        self.height = display.height

        picture_size = self.width * self.height * 2
        self._buffer = bytearray(picture_size)      # the picture you draw into
        self._previous = bytearray(picture_size)    # what the display shows now
        self._packed = bytearray((picture_size // 8) * 9)   # bytes ready to send
        self._row_flags = bytearray(self.height)
        self._memoryview = memoryview(self._buffer)
        self._frame = framebuf.FrameBuffer(self._buffer, self.width, self.height,
                                           framebuf.RGB565)

        # Changed rows closer together than this are sent as one block
        self.merge_gap_rows = 3

        self._dirty_top = None
        self._dirty_bottom = None
        # The first show() sends the whole screen
        self._force_full_update = True

    @staticmethod
    def _swap(colour):
        # The display wants the high byte first. The memory picture stores
        # each pixel low byte first, so the two bytes are swapped on the way in.
        return ((colour & 0xFF) << 8) | (colour >> 8)

    def _mark_dirty(self, left, top, right, bottom):
        # Remember which rows might have changed, so show() only
        # has to compare those rows.
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

    # ===============================
    # DRAWING (into memory only)
    # ===============================
    def fill_screen(self, colour):
        self._frame.fill(self._swap(colour))
        self._mark_dirty(0, 0, self.width - 1, self.height - 1)

    def draw_pixel(self, x, y, colour):
        self._frame.pixel(x, y, self._swap(colour))
        self._mark_dirty(x, y, x, y)

    def fill_rectangle(self, x, y, width, height, colour):
        self._frame.fill_rect(x, y, width, height, self._swap(colour))
        self._mark_dirty(x, y, x + width - 1, y + height - 1)

    def draw_rectangle(self, x, y, width, height, colour):
        self._frame.rect(x, y, width, height, self._swap(colour))
        self._mark_dirty(x, y, x + width - 1, y + height - 1)

    def draw_line(self, x_start, y_start, x_end, y_end, colour):
        self._frame.line(x_start, y_start, x_end, y_end, self._swap(colour))
        self._mark_dirty(x_start, y_start, x_end, y_end)

    def draw_circle(self, centre_x, centre_y, radius, colour):
        self._frame.ellipse(centre_x, centre_y, radius, radius, self._swap(colour))
        self._mark_dirty(centre_x - radius, centre_y - radius,
                         centre_x + radius, centre_y + radius)

    def fill_circle(self, centre_x, centre_y, radius, colour):
        self._frame.ellipse(centre_x, centre_y, radius, radius, self._swap(colour), True)
        self._mark_dirty(centre_x - radius, centre_y - radius,
                         centre_x + radius, centre_y + radius)

    def measure_text(self, text, scale=1):
        return self._display.measure_text(text, scale)

    def draw_text(self, text, x, y, colour, background_colour=None, scale=1):
        """Same as Display.draw_text, but into memory."""
        character_size = 8 * scale
        lines = text.split("\n")
        swapped_colour = self._swap(colour)

        if background_colour is not None:
            for line_number in range(len(lines)):
                self._frame.fill_rect(x, y + line_number * character_size,
                                      len(lines[line_number]) * character_size,
                                      character_size, self._swap(background_colour))

        if scale == 1:
            for line_number in range(len(lines)):
                self._frame.text(lines[line_number], x, y + line_number * 8, swapped_colour)
        else:
            glyph_buffer = bytearray(8)
            glyph = framebuf.FrameBuffer(glyph_buffer, 8, 8, framebuf.MONO_HLSB)
            for line_number in range(len(lines)):
                line = lines[line_number]
                line_y = y + line_number * character_size
                for character_number in range(len(line)):
                    character_x = x + character_number * character_size
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

        text_width, text_height = self._display.measure_text(text, scale)
        self._mark_dirty(x, y, x + text_width - 1, y + text_height - 1)

    def load_image_file(self, filename, x=0, y=0, width=None, height=None):
        """Load a raw image file (made by convert_image_to_raw.py) into memory."""
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

        with open(filename, "rb") as image_file:
            for row in range(height):
                start = ((y + row) * self.width + x) * 2
                image_file.readinto(self._memoryview[start:start + width * 2])
        self._mark_dirty(x, y, x + width - 1, y + height - 1)

    # ===============================
    # SENDING TO THE SCREEN
    # ===============================
    def show(self, full=False):
        """Send only the rows that changed since the last show().
        show(full=True) sends the whole picture."""
        width = self.width
        height = self.height
        bytes_per_row = width * 2

        if full or self._force_full_update:
            bands = [(0, height - 1)]
        else:
            if self._dirty_top is None:
                return
            first_row = self._dirty_top
            last_row = self._dirty_bottom
            self._mark_changed_rows(self._buffer, self._previous, bytes_per_row // 4,
                                    first_row, last_row, self._row_flags)
            bands = self._find_bands(first_row, last_row)

        self._dirty_top = None
        self._dirty_bottom = None
        self._force_full_update = False

        for band_top, band_bottom in bands:
            self._display.set_window(0, band_top, width - 1, band_bottom)
            offset = band_top * bytes_per_row
            byte_count = (band_bottom - band_top + 1) * bytes_per_row
            self._send_region(offset, byte_count)
            self._copy_region(self._buffer, self._previous, offset // 4, byte_count // 4)

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

    def _send_region(self, offset, byte_count):
        display = self._display

        if display._spi is None:
            # Slow method: one byte at a time
            for position in range(offset, offset + byte_count):
                display._send_9bit(self._buffer[position], False)
            return

        self._pack_data(self._buffer, offset, self._packed, byte_count)
        packed_length = (byte_count // 8) * 9
        display._select_pin.low()
        display._spi.write(memoryview(self._packed)[0:packed_length])
        display._select_pin.high()
