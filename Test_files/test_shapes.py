"""
2D shapes test for nokia_shapes.py

On the Pico you need:
    nokia_display.py  nokia_fast.py  nokia_graphics.py  nokia_shapes.py

It shows four pages for PAGE_SECONDS each and prints the FPS of every page:
    1. a gallery of filled and outlined shapes
    2. lines, arcs, pies and a ring
    3. a clip rectangle and sprites
    4. an animation (spinning star and polygon, sweeping gauge, moving sprite)
"""
import gc
import time

import nokia_display
from nokia_display import Display, make_colour
from nokia_graphics import Screen
from nokia_shapes import Shapes, Sprite, sine, cosine

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4

ROTATION = nokia_display.PORTRAIT_FLEX_CABLE_AT_TOP
SPI_MEGABITS_PER_SECOND = 32
PAGE_SECONDS = 6

SCREEN_BUDGET_BYTES = 100 * 1024
RESERVE_BYTES = 8 * 1024

BLACK = nokia_display.BLACK
WHITE = nokia_display.WHITE
RED = nokia_display.RED
GREEN = nokia_display.GREEN
BLUE = nokia_display.BLUE
YELLOW = nokia_display.YELLOW
CYAN = nokia_display.CYAN
MAGENTA = nokia_display.MAGENTA
ORANGE = make_colour(255, 140, 0)
DARK_BLUE = make_colour(0, 0, 90)
GREY = make_colour(90, 90, 90)

SMILEY_ROWS = (
    "....yyyyyyyy....",
    "..yyyyyyyyyyyy..",
    ".yyyyyyyyyyyyyy.",
    "yyyykyyyyykyyyyy",
    "yyyykyyyyykyyyyy",
    "yyyyyyyyyyyyyyyy",
    "yykyyyyyyyyyykyy",
    "yyykyyyyyyyykyyy",
    ".yyykkkkkkkkyyy.",
    "..yyyyyyyyyyyy..",
    "....yyyyyyyy....",
)
SMILEY = Sprite.from_text_rows(SMILEY_ROWS, {"y": YELLOW, "k": BLACK}, MAGENTA)


# ===============================
# PAGES - each one draws the WHOLE picture
# ===============================
def page_gallery(screen, shapes, milliseconds):
    shapes.fill_triangle(4, 4, 40, 10, 20, 40, RED)
    shapes.draw_triangle(46, 4, 80, 8, 60, 40, YELLOW)
    shapes.fill_polygon([(90, 4), (122, 10), (110, 22), (124, 40), (96, 34), (86, 20)], GREEN)
    shapes.fill_regular_polygon(22, 68, 16, 6, CYAN)
    shapes.draw_regular_polygon(62, 68, 16, 5, WHITE, rotation_degrees=10)
    shapes.fill_star(104, 68, 18, 8, 5, YELLOW)
    shapes.fill_ellipse(24, 104, 20, 10, MAGENTA)
    shapes.draw_ellipse(70, 104, 22, 12, CYAN)
    shapes.fill_circle(108, 104, 12, ORANGE)
    shapes.draw_circle(108, 104, 15, WHITE)
    shapes.fill_rounded_rectangle(4, 124, 56, 30, 8, BLUE)
    shapes.draw_rounded_rectangle(66, 124, 56, 30, 10, GREEN)


def page_lines_and_arcs(screen, shapes, milliseconds):
    shapes.draw_line(4, 4, 120, 20, WHITE)
    shapes.draw_line(4, 14, 120, 30, RED, thickness=3)
    shapes.draw_line(4, 40, 100, 56, YELLOW, thickness=7, round_caps=True)
    shapes.draw_line(10, 70, 10, 100, CYAN, thickness=4)
    shapes.draw_polyline([(20, 70), (40, 100), (60, 70), (80, 100), (100, 70)], GREEN, thickness=5)
    shapes.draw_arc(30, 130, 24, 0, 270, WHITE)
    shapes.draw_arc(30, 130, 18, 0, 270, ORANGE, thickness=5)
    shapes.fill_pie(84, 130, 24, 200, 340, CYAN)
    shapes.fill_pie(84, 130, 10, 30, 300, BLUE)
    shapes.fill_ring(112, 60, 12, 6, MAGENTA)


def page_clip_and_sprites(screen, shapes, milliseconds):
    screen.fill_rectangle(0, 0, screen.width, screen.height, DARK_BLUE)
    shapes.draw_sprite(SMILEY, 8, 8)
    shapes.draw_sprite(SMILEY, 40, 8)
    shapes.draw_sprite(SMILEY, -8, 30)           # half outside on the left
    shapes.draw_sprite(SMILEY, screen.width - 8, 30)   # half outside on the right

    shapes.set_clip(20, 60, 70, 60)              # everything below stays inside this box
    shapes.fill_circle(30, 70, 25, CYAN)
    shapes.draw_line(0, 60, 127, 130, WHITE)
    shapes.draw_line(0, 70, 127, 150, RED, thickness=5)
    shapes.fill_star(60, 95, 40, 15, 5, GREEN)
    shapes.draw_sprite(SMILEY, 80, 100)
    shapes.clear_clip()
    shapes.draw_rounded_rectangle(20, 60, 71, 61, 6, WHITE)


def page_animation(screen, shapes, milliseconds):
    degrees = (milliseconds * 90 // 1000) % 360  # 90 degrees every second
    width = screen.width

    shapes.fill_star(32, 34, 28, 12, 5, YELLOW, rotation_degrees=degrees)
    shapes.draw_regular_polygon(96, 34, 26, 6, CYAN, rotation_degrees=-degrees, thickness=3)

    # a gauge that sweeps up and down
    sweep = (milliseconds * 120 // 1000) % 600
    if sweep > 300:
        sweep = 600 - sweep
    shapes.draw_arc(32, 104, 28, 135, 405, GREY, thickness=7)
    if sweep > 0:
        shapes.draw_arc(32, 104, 28, 135, 135 + (sweep * 270) // 300, ORANGE, thickness=7)

    # a sprite that circles inside a clipped window
    shapes.set_clip(64, 72, width - 68, 84)
    shapes.fill_rounded_rectangle(64, 72, width - 68, 84, 6, DARK_BLUE)
    centre_x = 64 + (width - 68) // 2
    centre_y = 72 + 42
    sprite_x = centre_x + (20 * cosine(degrees)) // 4096 - SMILEY.width // 2
    sprite_y = centre_y + (30 * sine(degrees)) // 4096 - SMILEY.height // 2
    shapes.draw_sprite(SMILEY, sprite_x, sprite_y)
    shapes.clear_clip()


PAGES = (
    ("Shape gallery", page_gallery),
    ("Lines and arcs", page_lines_and_arcs),
    ("Clip and sprites", page_clip_and_sprites),
    ("Animation", page_animation),
)


def main():
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN, ROTATION)
    display.start()
    display.use_hardware_spi(SPI_MEGABITS_PER_SECOND * 1000000)

    screen = Screen(display, budget_bytes=SCREEN_BUDGET_BYTES, reserve_bytes=RESERVE_BYTES)
    print(screen.memory_report())

    gc.collect()
    before_shapes = gc.mem_alloc()
    shapes = Shapes(screen)
    gc.collect()
    print("Shapes object    :", gc.mem_alloc() - before_shapes, "bytes")
    print("Sprite in memory :", SMILEY.memory_bytes(), "bytes")

    animation_clock = [0]

    for page_name, page_function in PAGES:
        def draw_page(target, page_function=page_function):
            page_function(target, shapes, animation_clock[0])

        frame_count = 0
        start_time = time.ticks_ms()
        end_time = time.ticks_add(start_time, PAGE_SECONDS * 1000)
        while time.ticks_diff(end_time, time.ticks_ms()) > 0:
            animation_clock[0] = time.ticks_diff(time.ticks_ms(), start_time)   # milliseconds
            screen.render(draw_page, background=BLACK)
            frame_count += 1
        total_milliseconds = time.ticks_diff(time.ticks_ms(), start_time)
        print("%-18s %6.1f FPS" % (page_name, frame_count * 1000 / total_milliseconds))

    gc.collect()
    print()
    print("Free RAM at the end:", gc.mem_free(), "bytes")


main()
