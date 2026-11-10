"""
Rotation test: shows the picture in all 8 orientations
(4 rotations, each normal and mirrored), HOLD_SECONDS each.

On the Pico you need:
    nokia_display.py (the new one)  nokia_fast.py  nokia_graphics.py (the new one)
    nokia_shapes.py (the new one)   nokia_shapes_fast.py

WHAT TO LOOK AT in each orientation (photograph every one):
  - a one pixel border: TOP side red, RIGHT side green, BOTTOM side blue,
    LEFT side yellow. The four sides must all be complete and touch the
    edge of the glass (no gap, no thin line of another colour).
  - four squares in the corners: top-left white, top-right cyan,
    bottom-left magenta, bottom-right orange.
  - the big letter F must be upright. Mirrored orientations must show it
    flipped left to right. The triangle points up.
  - the circle in the middle must be round.
"""
import time

import nokia_display
from nokia_display import Display
from nokia_graphics import Screen
from nokia_shapes import Shapes

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4
SPI_MEGABITS_PER_SECOND = 32
HOLD_SECONDS = 4

BLACK = nokia_display.BLACK
WHITE = nokia_display.WHITE
RED = nokia_display.RED
GREEN = nokia_display.GREEN
BLUE = nokia_display.BLUE
YELLOW = nokia_display.YELLOW
CYAN = nokia_display.CYAN
MAGENTA = nokia_display.MAGENTA
ORANGE = nokia_display.make_colour(255, 140, 0)

ROTATION_NAMES = ("portrait", "landscape flex left", "portrait upside down",
                  "landscape flex right")


def draw_test_picture(screen, shapes, rotation, mirrored):
    width = screen.width
    height = screen.height

    # border: top red, right green, bottom blue, left yellow
    screen.fill_rectangle(0, 0, width, 1, RED)
    screen.fill_rectangle(width - 1, 0, 1, height, GREEN)
    screen.fill_rectangle(0, height - 1, width, 1, BLUE)
    screen.fill_rectangle(0, 0, 1, height, YELLOW)

    # corner squares
    screen.fill_rectangle(2, 2, 8, 8, WHITE)
    screen.fill_rectangle(width - 10, 2, 8, 8, CYAN)
    screen.fill_rectangle(2, height - 10, 8, 8, MAGENTA)
    screen.fill_rectangle(width - 10, height - 10, 8, 8, ORANGE)

    # a big F (not the same when mirrored), a triangle pointing up, a circle
    screen.draw_text("F", width // 2 - 40, height // 2 - 24, WHITE, scale=6)
    shapes.fill_triangle(width // 2 + 20, height // 2 - 20, width // 2 + 36, height // 2 + 4,
                         width // 2 + 4, height // 2 + 4, GREEN)
    shapes.draw_circle(width // 2 + 28, height // 2 + 24, 10, CYAN)

    # words
    text = "%dx%d" % (width, height)
    screen.draw_text(text, (width - len(text) * 8) // 2, 14, WHITE)
    label = ROTATION_NAMES[rotation]
    if len(label) * 8 > width - 4:
        label = label[0:(width - 4) // 8]
    screen.draw_text(label, (width - len(label) * 8) // 2, height - 24, YELLOW)
    if mirrored:
        screen.draw_text("mirrored", (width - 64) // 2, height - 34, CYAN)


def main():
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN)
    display.start()
    display.use_hardware_spi(SPI_MEGABITS_PER_SECOND * 1000000)

    screen = Screen(display, budget_bytes=100 * 1024, reserve_bytes=8 * 1024)
    shapes = Shapes(screen)          # follows the screen when it is turned
    screen.fill_screen(BLACK)
    screen.show()
    print(screen.memory_report())
    print()

    results = []
    for mirrored in (False, True):
        for rotation in (0, 1, 2, 3):
            start = time.ticks_ms()
            screen.set_rotation(rotation, mirrored)
            turn_milliseconds = time.ticks_diff(time.ticks_ms(), start)

            def draw_scene(target, rotation=rotation, mirrored=mirrored):
                draw_test_picture(target, shapes, rotation, mirrored)

            start = time.ticks_ms()
            screen.render(draw_scene, background=BLACK)
            draw_milliseconds = time.ticks_diff(time.ticks_ms(), start)

            print("rotation %d %-22s mirrored %-5s -> %dx%d, %s, turn %d ms, first picture %d ms"
                  % (rotation, ROTATION_NAMES[rotation], mirrored, screen.width,
                     screen.height, screen.mode, turn_milliseconds, draw_milliseconds))
            print("   measured RAM use:", screen.memory_used_bytes, "bytes")
            time.sleep(HOLD_SECONDS)

    # the quarter-turn helpers, then back to the normal orientation
    screen.set_rotation(0)
    screen.rotate_clockwise()
    print("rotate_clockwise from 0 gives rotation", screen.rotation)
    screen.rotate_anticlockwise()
    print("rotate_anticlockwise gives rotation", screen.rotation)

    def final_scene(target):
        draw_test_picture(target, shapes, 0, False)
    screen.render(final_scene, background=BLACK)
    print("Done. The display is back to normal portrait.")


main()
