"""
Text motion test for nokia_text_motion.py

On the Pico you need:
    nokia_display.py  nokia_fast.py  nokia_graphics.py
    nokia_font.py (the new one)  nokia_font_fast.py  nokia_text_motion.py
    the fonts folder with the .nkf files

Four pages, PAGE_SECONDS each, with the FPS of each printed:
    1. marquees (sideways scrolling) and a message roller
    2. vertical scroller (like film credits)
    3. wavy letters, bouncing letters and text around a spinning circle
    4. typewriter, fly-in with bounce, and fade in / fade out
"""
import gc
import time

import nokia_display
from nokia_display import Display, make_colour
from nokia_graphics import Screen
from nokia_font import Font, ALIGN_CENTRE, ALIGN_LEFT
from nokia_text_motion import (Marquee, VerticalScroller, MessageRoller, SCROLL_LEFT,
                               SCROLL_RIGHT, SCROLL_UP, SCROLL_DOWN, draw_wavy_text,
                               draw_text_on_circle, draw_typewriter, fly_in_position,
                               fade_colour, bounce_out, ease_out)

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4

ROTATION = nokia_display.PORTRAIT_FLEX_CABLE_AT_TOP
SPI_MEGABITS_PER_SECOND = 32
PAGE_SECONDS = 10

FONT_FOLDER = "fonts"
SCREEN_BUDGET_BYTES = 100 * 1024
FONT_RESERVE_BYTES = 24 * 1024

BLACK = nokia_display.BLACK
WHITE = nokia_display.WHITE
YELLOW = nokia_display.YELLOW
CYAN = nokia_display.CYAN
GREEN = nokia_display.GREEN
ORANGE = make_colour(255, 140, 0)
PANEL = make_colour(30, 30, 60)
DARK = make_colour(10, 10, 30)

CREDITS = ("Display driver credits. "
           "Written step by step on a Pico 2 for an old Nokia screen. "
           "Text can roll up, roll down, slide sideways and wave. "
           "Maths symbols work too: π ≈ 3.14159, √2, x² + y², ∑ ∫ ∂. "
           "Money signs: $ € ¥ £ ₹. The end of the credits.")


def load_fonts():
    fonts = {}
    for name in ("sans_11", "sans_14", "bold_14", "sans_20", "mono_12"):
        fonts[name] = Font(FONT_FOLDER + "/" + name + ".nkf")
    return fonts


def build_effects(fonts, width):
    effects = {}
    effects["marquees"] = (
        Marquee(fonts["sans_14"], "Rolling text  π ≈ 3.14159  √2 × ½  ₹ $ € ¥", 0, 24, width,
                WHITE, pixels_per_second=40, background=PANEL),
        Marquee(fonts["bold_14"], "<<< moving right <<<", 0, 46, width, YELLOW,
                pixels_per_second=60, direction=SCROLL_RIGHT, background=PANEL),
        Marquee(fonts["mono_12"], "FAST 1234567890 +-*/=", 0, 68, width, GREEN,
                pixels_per_second=110, background=PANEL),
    )
    effects["roller"] = MessageRoller(
        fonts["sans_14"], ("Battery 82 %", "Thu 22 Oct", "x² + √2 = ?", "∑ π ∞ ∫"),
        0, 100, width, CYAN, hold_milliseconds=1300, slide_milliseconds=350,
        background=PANEL, height=24)
    effects["roller_down"] = MessageRoller(
        fonts["sans_11"], ("rolls down", "from the top", "and settles"),
        0, 130, width, ORANGE, hold_milliseconds=1000, slide_milliseconds=300,
        direction=SCROLL_DOWN, background=PANEL, height=22)
    effects["credits"] = VerticalScroller(
        fonts["sans_11"], CREDITS, 6, 24, width - 12, 130, WHITE,
        pixels_per_second=14, alignment=ALIGN_CENTRE, background=DARK)
    return effects


# ===============================
# PAGES - each draws the WHOLE picture
# ===============================
def title(screen, fonts, text):
    fonts["bold_14"].draw_aligned(screen, text, 0, 2, screen.width, YELLOW, ALIGN_CENTRE,
                                  underline=True)


def page_marquees(screen, fonts, effects, elapsed):
    title(screen, fonts, "Marquees")
    for marquee in effects["marquees"]:
        marquee.draw(screen, elapsed)
    effects["roller"].draw(screen, elapsed)
    effects["roller_down"].draw(screen, elapsed)


def page_credits(screen, fonts, effects, elapsed):
    title(screen, fonts, "Vertical scroll")
    effects["credits"].draw(screen, elapsed)
    screen.draw_rectangle(5, 23, screen.width - 10, 132, PANEL)


def page_letters(screen, fonts, effects, elapsed):
    title(screen, fonts, "Letter motion")
    draw_wavy_text(screen, fonts["sans_20"], "Hello Wave", 4, 28, CYAN, elapsed,
                   amplitude=7, wavelength=70, speed_pixels_per_second=90)
    draw_wavy_text(screen, fonts["bold_14"], "Bouncing text", 4, 62, ORANGE, elapsed,
                   amplitude=8, wavelength=60, speed_pixels_per_second=80, bounce=True)
    draw_text_on_circle(screen, fonts["sans_11"], "ROUND AND ROUND  x² π √ ", 64, 118, 34,
                        GREEN, start_degrees=elapsed * 60 // 1000)


def page_entrance(screen, fonts, effects, elapsed):
    title(screen, fonts, "Entrances")
    cycle = elapsed % 6000

    draw_typewriter(screen, fonts["mono_12"], "Typing this out\nletter by letter...", 4, 24,
                    GREEN, cycle, characters_per_second=10)

    x, y = fly_in_position(-100, 64, 8, 64, cycle, 1200, easing=bounce_out)
    fonts["bold_14"].draw(screen, "Bounce in", x, y, YELLOW)
    x, y = fly_in_position(140, 86, 8, 86, cycle, 900, easing=ease_out, delay_milliseconds=500)
    fonts["bold_14"].draw(screen, "Slide in", x, y, CYAN)

    if cycle < 3000:
        colour = fade_colour(WHITE, BLACK, cycle, 1500, fade_in=True)
    else:
        colour = fade_colour(WHITE, BLACK, cycle - 3000, 1500, fade_in=False)
    fonts["sans_20"].draw(screen, "Fade", 8, 112, colour)
    fonts["sans_11"].draw(screen, "in and out", 8, 136, colour)


PAGES = (
    ("Marquees + roller", page_marquees),
    ("Vertical scroll", page_credits),
    ("Letter motion", page_letters),
    ("Entrances", page_entrance),
)


def main():
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN, ROTATION)
    display.start()
    display.use_hardware_spi(SPI_MEGABITS_PER_SECOND * 1000000)

    screen = Screen(display, budget_bytes=SCREEN_BUDGET_BYTES, reserve_bytes=FONT_RESERVE_BYTES)
    screen.fill_screen(BLACK)
    screen.show()
    print(screen.memory_report())

    gc.collect()
    before = gc.mem_alloc()
    fonts = load_fonts()
    effects = build_effects(fonts, screen.width)
    gc.collect()
    print()
    print("Fonts and effects:", gc.mem_alloc() - before, "bytes")

    for page_name, page_function in PAGES:
        def draw_page(target, page_function=page_function):
            page_function(target, fonts, effects, elapsed_now[0])
        elapsed_now = [0]

        frame_count = 0
        start_time = time.ticks_ms()
        end_time = time.ticks_add(start_time, PAGE_SECONDS * 1000)
        while time.ticks_diff(end_time, time.ticks_ms()) > 0:
            elapsed_now[0] = time.ticks_diff(time.ticks_ms(), start_time)
            screen.render(draw_page, background=BLACK)
            frame_count += 1
        total_milliseconds = time.ticks_diff(time.ticks_ms(), start_time)
        print("%-18s %6.1f FPS" % (page_name, frame_count * 1000 / total_milliseconds))

    gc.collect()
    print()
    print("Free RAM at the end:", gc.mem_free(), "bytes")


main()
