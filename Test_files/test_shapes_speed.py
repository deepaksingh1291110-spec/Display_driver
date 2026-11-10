"""
Speed test for nokia_shapes.py

On the Pico you need:
    nokia_display.py  nokia_fast.py  nokia_graphics.py
    nokia_shapes.py   nokia_shapes_fast.py

It times every shape on its own, with the Python code and with the fast
helpers, and prints how long ONE call takes in microseconds (1 millisecond
= 1000 microseconds). It also times sending a whole picture to the display.
Nothing is shown on the screen during the shape timings.
"""
import gc
import time

import nokia_display
from nokia_display import Display
from nokia_graphics import Screen
from nokia_shapes import Shapes, Sprite

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4

ROTATION = nokia_display.PORTRAIT_FLEX_CABLE_AT_TOP
SPI_MEGABITS_PER_SECOND = 32
CALLS_PER_MEASUREMENT = 20

RED = nokia_display.RED
GREEN = nokia_display.GREEN
BLUE = nokia_display.BLUE
YELLOW = nokia_display.YELLOW
CYAN = nokia_display.CYAN
WHITE = nokia_display.WHITE
MAGENTA = nokia_display.MAGENTA

SMILEY = Sprite.from_text_rows((
    "....yyyyyyyy....", "..yyyyyyyyyyyy..", ".yyyyyyyyyyyyyy.",
    "yyyykyyyyykyyyyy", "yyyykyyyyykyyyyy", "yyyyyyyyyyyyyyyy",
    "yykyyyyyyyyyykyy", "yyykyyyyyyyykyyy", ".yyykkkkkkkkyyy.",
    "..yyyyyyyyyyyy..", "....yyyyyyyy...."),
    {"y": YELLOW, "k": 0x0000}, MAGENTA)

HEXAGON_POINTS = [(20, 10), (40, 10), (50, 30), (40, 50), (20, 50), (10, 30)]
CONCAVE_POINTS = [(10, 10), (60, 20), (40, 40), (70, 60), (20, 55), (5, 35)]
LINE_POINTS = [(10, 70), (40, 100), (70, 70), (100, 100), (120, 70)]

# (name, a function that draws one shape on a Shapes object)
TESTS = (
    ("fill_triangle 40x40",       lambda s: s.fill_triangle(10, 10, 50, 20, 25, 50, RED)),
    ("fill_polygon 6 corners",    lambda s: s.fill_polygon(CONCAVE_POINTS, GREEN)),
    ("fill_regular_polygon r20",  lambda s: s.fill_regular_polygon(64, 80, 20, 6, CYAN)),
    ("fill_star r30",             lambda s: s.fill_star(64, 80, 30, 12, 5, YELLOW)),
    ("fill_circle r12",           lambda s: s.fill_circle(64, 80, 12, MAGENTA)),
    ("fill_circle r40",           lambda s: s.fill_circle(64, 80, 40, MAGENTA)),
    ("fill_ellipse 30x15",        lambda s: s.fill_ellipse(64, 80, 30, 15, BLUE)),
    ("draw_ellipse 30x15",        lambda s: s.draw_ellipse(64, 80, 30, 15, WHITE)),
    ("fill_rounded_rectangle",    lambda s: s.fill_rounded_rectangle(10, 20, 100, 50, 10, BLUE)),
    ("draw_rounded_rectangle",    lambda s: s.draw_rounded_rectangle(10, 20, 100, 50, 10, WHITE)),
    ("fill_ring r30/r20",         lambda s: s.fill_ring(64, 80, 30, 20, MAGENTA)),
    ("draw_arc thin r30",         lambda s: s.draw_arc(64, 80, 30, 0, 270, WHITE)),
    ("draw_arc thick r30 x 7",    lambda s: s.draw_arc(64, 80, 30, 0, 270, WHITE, thickness=7)),
    ("fill_pie r30",              lambda s: s.fill_pie(64, 80, 30, 30, 300, CYAN)),
    ("draw_line thin 100 long",   lambda s: s.draw_line(5, 5, 105, 60, WHITE)),
    ("draw_line thick 7",         lambda s: s.draw_line(5, 5, 105, 60, WHITE, thickness=7)),
    ("draw_line thick 7 round",   lambda s: s.draw_line(5, 5, 105, 60, WHITE, 7, True)),
    ("draw_polyline 5 pts x 5",   lambda s: s.draw_polyline(LINE_POINTS, GREEN, thickness=5)),
    ("draw_sprite 16x11",         lambda s: s.draw_sprite(SMILEY, 50, 50)),
)


def time_calls(function, shapes):
    gc.collect()
    function(shapes)                      # one call first, not timed
    start = time.ticks_us()
    for call_number in range(CALLS_PER_MEASUREMENT):
        function(shapes)
    return time.ticks_diff(time.ticks_us(), start) // CALLS_PER_MEASUREMENT


def main():
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN, ROTATION)
    display.start()
    display.use_hardware_spi(SPI_MEGABITS_PER_SECOND * 1000000)
    screen = Screen(display, budget_bytes=100 * 1024, reserve_bytes=8 * 1024)
    # A new display shows random noise until the first picture is sent.
    screen.fill_screen(nokia_display.BLACK)
    screen.show()
    print(screen.memory_report())
    print()

    python_shapes = Shapes(screen, use_fast_helpers=False)
    fast_shapes = Shapes(screen)
    print("Fast helpers in use:", fast_shapes.fast_helpers_in_use)
    print("Memory held by Shapes work lists:", fast_shapes.memory_bytes(), "bytes")
    print()

    print("Timing... the screen stays black until the end.")
    print("%-26s %10s %10s %8s" % ("one call of", "Python us", "fast us", "faster"))
    for name, function in TESTS:
        python_microseconds = time_calls(function, python_shapes)
        if fast_shapes.fast_helpers_in_use:
            fast_microseconds = time_calls(function, fast_shapes)
            ratio = python_microseconds / max(1, fast_microseconds)
            print("%-26s %10d %10d %7.1fx" % (name, python_microseconds, fast_microseconds, ratio))
        else:
            print("%-26s %10d %10s %8s" % (name, python_microseconds, "-", "-"))

    print()
    print("Screen's own calls, for comparison:")
    start = time.ticks_us()
    for call_number in range(CALLS_PER_MEASUREMENT):
        screen.fill_rectangle(10, 10, 100, 50, RED)
    print("%-26s %10d" % ("screen.fill_rectangle", time.ticks_diff(time.ticks_us(), start) // CALLS_PER_MEASUREMENT))
    start = time.ticks_us()
    for call_number in range(CALLS_PER_MEASUREMENT):
        screen.fill_circle(64, 80, 40, RED)
    print("%-26s %10d" % ("screen.fill_circle r40", time.ticks_diff(time.ticks_us(), start) // CALLS_PER_MEASUREMENT))

    print()
    screen.show(full=True)
    start = time.ticks_us()
    for call_number in range(5):
        screen.show(full=True)
    send_microseconds = time.ticks_diff(time.ticks_us(), start) // 5
    print("Sending the whole picture to the display:", send_microseconds, "us")
    print("   = the most FPS a full-screen change can reach: %.1f" % (1000000 / send_microseconds))
    print("(The picture now on the screen is just all the test shapes drawn on top of each other.)")


main()
