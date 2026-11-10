"""
nokia_text_motion.py - moving, scrolling and animated text

Copy this file to the Pico next to nokia_font.py. Needs the new
nokia_font.py (it has the clip option that keeps scrolling text inside its
window).

Every effect works from TIME, not from frames: you give it the number of
milliseconds since the effect started, so it moves at the same speed
whatever the FPS is. Use time.ticks_diff(time.ticks_ms(), start_time).

    from nokia_text_motion import Marquee, MessageRoller, VerticalScroller
    from nokia_text_motion import draw_wavy_text, draw_text_on_circle, draw_typewriter

    ticker = Marquee(font, "Breaking news  π ≈ 3.14", 0, 20, 128, WHITE, 40)

    def draw_scene(screen):
        elapsed = time.ticks_diff(time.ticks_ms(), start)
        ticker.draw(screen, elapsed)

    screen.render(draw_scene, background=BLACK)

WHAT IS HERE
    Marquee            one line that scrolls sideways again and again
    VerticalScroller   many lines that scroll up or down (credits, news)
    MessageRoller      a list of messages that roll in one after another
    draw_wavy_text     letters that ride a wave or hop up and down
    draw_text_on_circle  letters placed around a circle (spin it with time)
    draw_typewriter    letters that appear one by one with a blinking cursor
    fly_in_position    where text is while it slides in, with easing
    fade_colour        the colour of text that fades in or out
    easing functions   linear, ease_in, ease_out, ease_in_out, bounce_out

All maths uses whole numbers. Nothing here keeps a picture in memory.
"""
import array

from nokia_font import ALIGN_LEFT, ALIGN_CENTRE, ALIGN_RIGHT

SCROLL_LEFT = "left"
SCROLL_RIGHT = "right"
SCROLL_UP = "up"
SCROLL_DOWN = "down"

# ===============================
# SINE (whole numbers, no floats)
# ===============================
_SINE_TABLE = array.array("h", (
    0, 71, 143, 214, 286, 357, 428, 499, 570, 641, 711, 782, 852, 921, 991,
    1060, 1129, 1198, 1266, 1334, 1401, 1468, 1534, 1600, 1666, 1731, 1796,
    1860, 1923, 1986, 2048, 2110, 2171, 2231, 2290, 2349, 2408, 2465, 2522,
    2578, 2633, 2687, 2741, 2793, 2845, 2896, 2946, 2996, 3044, 3091, 3138,
    3183, 3228, 3271, 3314, 3355, 3396, 3435, 3474, 3511, 3547, 3582, 3617,
    3650, 3681, 3712, 3742, 3770, 3798, 3824, 3849, 3873, 3896, 3917, 3937,
    3956, 3974, 3991, 4006, 4021, 4034, 4046, 4056, 4065, 4074, 4080, 4086,
    4090, 4094, 4095, 4096))


def _sine(degrees):
    # sine of whole degrees, times 4096
    degrees %= 360
    if degrees <= 90:
        return _SINE_TABLE[degrees]
    if degrees <= 180:
        return _SINE_TABLE[180 - degrees]
    if degrees <= 270:
        return -_SINE_TABLE[degrees - 180]
    return -_SINE_TABLE[360 - degrees]


def _cosine(degrees):
    return _sine(degrees + 90)


# ===============================
# EASING
# An easing function takes progress from 0 to 1024 (1024 means finished)
# and returns how far along the movement is, also 0 to 1024. It decides
# how the movement speeds up or slows down.
# ===============================
_FULL = 1024


def linear(progress):
    """Constant speed."""
    return progress


def ease_in(progress):
    """Starts slowly, then speeds up."""
    return (progress * progress) >> 10


def ease_out(progress):
    """Starts fast, then slows down to a stop."""
    return _FULL - (((_FULL - progress) * (_FULL - progress)) >> 10)


def ease_in_out(progress):
    """Slow start, fast middle, slow stop."""
    if progress < 512:
        return (2 * progress * progress) >> 10
    return _FULL - ((2 * (_FULL - progress) * (_FULL - progress)) >> 10)


def bounce_out(progress):
    """Arrives, then bounces a few times before it settles."""
    if progress < 372:
        return (7744 * progress * progress) >> 20
    if progress < 745:
        progress -= 558
        return ((7744 * progress * progress) >> 20) + 768
    if progress < 931:
        progress -= 838
        return ((7744 * progress * progress) >> 20) + 960
    progress -= 977
    return ((7744 * progress * progress) >> 20) + 1008


def progress_of(elapsed_milliseconds, duration_milliseconds, delay_milliseconds=0):
    """0 to 1024: how much of a movement that takes duration_milliseconds
    has happened, after waiting delay_milliseconds."""
    time_into_movement = elapsed_milliseconds - delay_milliseconds
    if time_into_movement <= 0:
        return 0
    if duration_milliseconds <= 0 or time_into_movement >= duration_milliseconds:
        return _FULL
    return time_into_movement * _FULL // duration_milliseconds


def fly_in_position(from_x, from_y, to_x, to_y, elapsed_milliseconds,
                    duration_milliseconds, easing=ease_out, delay_milliseconds=0):
    """Where text is while it slides from (from_x, from_y) to (to_x, to_y).
    Returns (x, y). Draw the text there."""
    amount = easing(progress_of(elapsed_milliseconds, duration_milliseconds,
                                delay_milliseconds))
    return (from_x + ((to_x - from_x) * amount) // _FULL,
            from_y + ((to_y - from_y) * amount) // _FULL)


def blend_colours(first_colour, second_colour, amount):
    """Mix two 16-bit colours. amount 0 gives the first colour, 256 the second."""
    inverse = 256 - amount
    red = (((first_colour >> 11) & 31) * inverse + ((second_colour >> 11) & 31) * amount) >> 8
    green = (((first_colour >> 5) & 63) * inverse + ((second_colour >> 5) & 63) * amount) >> 8
    blue = ((first_colour & 31) * inverse + (second_colour & 31) * amount) >> 8
    return (red << 11) | (green << 5) | blue


def fade_colour(text_colour, background_colour, elapsed_milliseconds,
                duration_milliseconds, fade_in=True, delay_milliseconds=0):
    """The colour to draw text in while it fades in (or out) against a
    background of one solid colour."""
    amount = progress_of(elapsed_milliseconds, duration_milliseconds,
                         delay_milliseconds) >> 2          # 0 to 256
    if fade_in:
        return blend_colours(background_colour, text_colour, amount)
    return blend_colours(text_colour, background_colour, amount)


# ===============================
# MARQUEE: one line scrolling sideways
# ===============================
class Marquee:
    def __init__(self, font, text, x, y, width, colour, pixels_per_second=40,
                 direction=SCROLL_LEFT, gap=24, background=None):
        """A one-line window at x, y that is 'width' pixels wide and as high
        as one line of the font. The text slides through it again and again.
        gap: empty space between the end of the text and its next copy.
        background: colour of the window, or None to keep what is there."""
        self.font = font
        self.text = text.replace("\n", " ")
        self.x = x
        self.y = y
        self.width = width
        self.colour = colour
        self.pixels_per_second = pixels_per_second
        self.direction = direction
        self.background = background
        self.height = font.line_height
        self.text_width = font.measure_line(self.text)
        self.period = max(1, self.text_width + gap)

    def draw(self, screen, elapsed_milliseconds):
        if self.background is not None:
            screen.fill_rectangle(self.x, self.y, self.width, self.height, self.background)
        offset = (elapsed_milliseconds * self.pixels_per_second // 1000) % self.period
        clip = (self.x, self.y, self.x + self.width - 1, self.y + self.height - 1)

        if self.direction == SCROLL_RIGHT:
            copy_x = self.x + offset - self.period
        else:
            copy_x = self.x - offset
        right_edge = self.x + self.width
        while copy_x < right_edge:
            if copy_x + self.text_width > self.x:
                self.font.draw(screen, self.text, copy_x, self.y, self.colour, clip=clip)
            copy_x += self.period


# ===============================
# VERTICAL SCROLLER: many lines moving up or down
# ===============================
class VerticalScroller:
    def __init__(self, font, text, x, y, width, height, colour, pixels_per_second=15,
                 direction=SCROLL_UP, alignment=ALIGN_LEFT, extra_line_spacing=0,
                 loop=True, background=None):
        """A window at x, y (width x height pixels). The text is cut into
        lines once, here, and then scrolls through the window. Only the lines
        that are visible are drawn. SCROLL_UP is like film credits.
        loop=False: the text goes through once and then the window stays empty."""
        self.font = font
        self.lines = font.wrap(text, width)
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.colour = colour
        self.pixels_per_second = pixels_per_second
        self.direction = direction
        self.alignment = alignment
        self.loop = loop
        self.background = background
        self.step = font.line_height + extra_line_spacing
        self.total_height = len(self.lines) * self.step
        # distance the text travels from just outside the window to just outside again
        self.travel = self.total_height + height

    def finished(self, elapsed_milliseconds):
        """True when a loop=False scroller has gone all the way through."""
        return (not self.loop
                and elapsed_milliseconds * self.pixels_per_second // 1000 >= self.travel)

    def draw(self, screen, elapsed_milliseconds):
        if self.background is not None:
            screen.fill_rectangle(self.x, self.y, self.width, self.height, self.background)

        distance = elapsed_milliseconds * self.pixels_per_second // 1000
        if self.loop:
            distance %= self.travel
        elif distance >= self.travel:
            return

        if self.direction == SCROLL_DOWN:
            top = self.y - self.total_height + distance
        else:
            top = self.y + self.height - distance

        first_line = max(0, (self.y - top) // self.step)
        last_line = min(len(self.lines) - 1, (self.y + self.height - 1 - top) // self.step)
        clip = (self.x, self.y, self.x + self.width - 1, self.y + self.height - 1)
        for number in range(first_line, last_line + 1):
            self.font.draw_aligned(screen, self.lines[number], self.x,
                                   top + number * self.step, self.width, self.colour,
                                   self.alignment, clip=clip)


# ===============================
# MESSAGE ROLLER: messages that roll in one after another
# ===============================
class MessageRoller:
    def __init__(self, font, messages, x, y, width, colour, hold_milliseconds=1500,
                 slide_milliseconds=300, direction=SCROLL_UP, alignment=ALIGN_CENTRE,
                 background=None, height=None, easing=ease_in_out):
        """A window at x, y that shows one message at a time. When the time
        is up the next message rolls in while the old one rolls out.
        direction SCROLL_UP: new messages come from below. SCROLL_DOWN: from above.
        height: window height, default one line of the font."""
        self.font = font
        self.messages = messages
        self.x = x
        self.y = y
        self.width = width
        self.colour = colour
        self.hold_milliseconds = hold_milliseconds
        self.slide_milliseconds = max(1, slide_milliseconds)
        self.direction = direction
        self.alignment = alignment
        self.background = background
        self.height = height if height is not None else font.line_height
        self.easing = easing
        self._text_offset = (self.height - font.line_height) // 2

    def current_index(self, elapsed_milliseconds):
        """Number of the message that is showing (or rolling in)."""
        cycle = self.hold_milliseconds + self.slide_milliseconds
        return (elapsed_milliseconds // cycle) % len(self.messages)

    def draw(self, screen, elapsed_milliseconds):
        if self.background is not None:
            screen.fill_rectangle(self.x, self.y, self.width, self.height, self.background)

        cycle = self.hold_milliseconds + self.slide_milliseconds
        step_number = elapsed_milliseconds // cycle
        phase = elapsed_milliseconds % cycle
        current = step_number % len(self.messages)
        previous = (current - 1) % len(self.messages)

        rolling = phase < self.slide_milliseconds
        if rolling:
            amount = self.easing(phase * _FULL // self.slide_milliseconds)
        else:
            amount = _FULL
        moved = (self.height * amount) >> 10          # how far the roll has gone

        if self.direction == SCROLL_DOWN:
            current_y = self.y - self.height + moved
            previous_y = self.y + moved
        else:
            current_y = self.y + self.height - moved
            previous_y = self.y - moved

        clip = (self.x, self.y, self.x + self.width - 1, self.y + self.height - 1)
        if rolling and step_number > 0:
            self.font.draw_aligned(screen, self.messages[previous], self.x,
                                   previous_y + self._text_offset, self.width,
                                   self.colour, self.alignment, clip=clip)
        self.font.draw_aligned(screen, self.messages[current], self.x,
                               current_y + self._text_offset, self.width,
                               self.colour, self.alignment, clip=clip)


# ===============================
# LETTER BY LETTER MOVEMENT
# ===============================
def draw_wavy_text(screen, font, text, x, y, colour, elapsed_milliseconds,
                   amplitude=4, wavelength=48, speed_pixels_per_second=60,
                   bounce=False, clip=None):
    """Draw text whose letters move up and down in a wave that travels along
    the text. amplitude: how many pixels up and down. wavelength: pixels from
    one wave top to the next. bounce=True: letters only hop upward, like
    bouncing balls, instead of going both up and down."""
    wavelength = max(1, wavelength)
    shift = elapsed_milliseconds * speed_pixels_per_second * 360 // (1000 * wavelength)
    pen_x = x
    for character in text:
        degrees = ((pen_x - x) * 360) // wavelength - shift
        sine_value = _sine(degrees)
        if bounce:
            offset = -((amplitude * abs(sine_value)) >> 12)
        else:
            offset = (amplitude * sine_value) >> 12
        if character != " ":
            font.draw(screen, character, pen_x, y + offset, colour, clip=clip)
        pen_x += font.character_width(character)


def draw_text_on_circle(screen, font, text, centre_x, centre_y, radius, colour,
                        start_degrees=0, clip=None):
    """Place the letters around a circle, reading clockwise, with the first
    letter at start_degrees (0 is right, 90 is down, 270 is the top). The
    letters stay upright. Change start_degrees with time to spin the text:
        start_degrees = elapsed_milliseconds * 60 // 1000   # 60 degrees per second"""
    radius = max(1, radius)
    angle_hundredths = start_degrees * 100
    half_height = font.line_height // 2
    for character in text:
        width = font.character_width(character)
        # one pixel along the circle is 5730 / radius hundredths of a degree
        middle = angle_hundredths + (width * 5730) // (2 * radius)
        if character != " ":
            degrees = middle // 100
            letter_x = centre_x + ((radius * _cosine(degrees) + 2048) >> 12) - width // 2
            letter_y = centre_y + ((radius * _sine(degrees) + 2048) >> 12) - half_height
            font.draw(screen, character, letter_x, letter_y, colour, clip=clip)
        angle_hundredths += (width * 5730) // radius


def draw_typewriter(screen, font, text, x, y, colour, elapsed_milliseconds,
                    characters_per_second=12, cursor=True, clip=None):
    """Show the text one character at a time, with a blinking cursor.
    Returns True when all the text is showing."""
    shown = elapsed_milliseconds * characters_per_second // 1000
    finished = shown >= len(text)
    if finished:
        shown = len(text)
    visible = text[0:shown]
    if shown > 0:
        font.draw(screen, visible, x, y, colour, clip=clip)
    if cursor and (elapsed_milliseconds // 400) % 2 == 0:
        lines = visible.split("\n")
        cursor_x = x + font.measure_line(lines[-1])
        cursor_y = y + (len(lines) - 1) * font.line_height
        font.draw(screen, "_", cursor_x, cursor_y, colour, clip=clip)
    return finished
