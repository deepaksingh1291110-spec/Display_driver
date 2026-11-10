"""
Memory budget test for nokia_graphics.py

Copy to the Pico next to nokia_display.py, nokia_fast.py and
nokia_graphics.py, then run it.

The SAME scene function is drawn under four different memory budgets.
Screen picks the way of drawing by itself. For each budget this prints
the way chosen, the memory it planned, the memory it really used, and
the FPS.
"""
import gc
import time

import nokia_display
from nokia_display import Display, make_colour
from nokia_graphics import Screen

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4

ROTATION = nokia_display.PORTRAIT_FLEX_CABLE_AT_TOP
SPI_MEGABITS_PER_SECOND = 32
SECONDS_PER_TEST = 8

BUDGETS_TO_TRY = (
    ("100 KB", 100 * 1024),
    ("60 KB", 60 * 1024),
    ("24 KB", 24 * 1024),
    ("16 KB", 16 * 1024),
)

BACKGROUND = nokia_display.BLACK
GRID_COLOUR = make_colour(50, 50, 50)
BALL_COLOURS = (
    nokia_display.RED, nokia_display.GREEN, nokia_display.YELLOW,
    nokia_display.CYAN, nokia_display.MAGENTA, nokia_display.WHITE,
)
BALL_RADIUS = 10
FIXED_POINT = 256     # positions in 1/256 pixel steps, so no floats are used


class BouncingBallScene:
    """The whole picture: grid, border, a label and one bouncing ball.
    draw() draws everything, so it works in every way of drawing."""

    def __init__(self, width, height, label):
        self.width = width
        self.height = height
        self.label = label
        self.ball_x = width // 3 * FIXED_POINT
        self.ball_y = height // 3 * FIXED_POINT
        self.speed_x = 150 * FIXED_POINT
        self.speed_y = 110 * FIXED_POINT
        self.colour_number = 0

    def update(self, elapsed_microseconds):
        self.ball_x += self.speed_x * elapsed_microseconds // 1000000
        self.ball_y += self.speed_y * elapsed_microseconds // 1000000

        left = BALL_RADIUS * FIXED_POINT
        right = (self.width - 1 - BALL_RADIUS) * FIXED_POINT
        top = BALL_RADIUS * FIXED_POINT
        bottom = (self.height - 1 - BALL_RADIUS) * FIXED_POINT
        hit_wall = False

        if self.ball_x < left:
            self.ball_x = left
            self.speed_x = -self.speed_x
            hit_wall = True
        elif self.ball_x > right:
            self.ball_x = right
            self.speed_x = -self.speed_x
            hit_wall = True
        if self.ball_y < top:
            self.ball_y = top
            self.speed_y = -self.speed_y
            hit_wall = True
        elif self.ball_y > bottom:
            self.ball_y = bottom
            self.speed_y = -self.speed_y
            hit_wall = True
        if hit_wall:
            self.colour_number = (self.colour_number + 1) % len(BALL_COLOURS)

    def draw(self, screen):
        for x in range(32, self.width, 32):
            screen.draw_line(x, 0, x, self.height - 1, GRID_COLOUR)
        for y in range(32, self.height, 32):
            screen.draw_line(0, y, self.width - 1, y, GRID_COLOUR)
        screen.draw_rectangle(0, 0, self.width, self.height, nokia_display.BLUE)
        screen.draw_text(self.label, 4, self.height - 12, nokia_display.WHITE)
        screen.fill_circle(self.ball_x // FIXED_POINT, self.ball_y // FIXED_POINT,
                           BALL_RADIUS, BALL_COLOURS[self.colour_number])


def run_one_test(display, budget_name, budget_bytes):
    print()
    print("=== Budget", budget_name, "===")
    screen = Screen(display, budget_bytes=budget_bytes)
    print(screen.memory_report())

    label = "%s %dx%d" % (budget_name, screen.passes_per_frame, screen.strip_height)
    scene = BouncingBallScene(screen.width, screen.height, label)
    draw_scene = scene.draw       # made once, so nothing is created per frame

    gc.collect()
    frame_count = 0
    start_time = time.ticks_ms()
    end_time = time.ticks_add(start_time, SECONDS_PER_TEST * 1000)
    last_microseconds = time.ticks_us()

    while time.ticks_diff(end_time, time.ticks_ms()) > 0:
        now_microseconds = time.ticks_us()
        scene.update(time.ticks_diff(now_microseconds, last_microseconds))
        last_microseconds = now_microseconds
        screen.render(draw_scene, background=BACKGROUND)
        frame_count += 1

    total_milliseconds = time.ticks_diff(time.ticks_ms(), start_time)
    frames_per_second = frame_count * 1000 / total_milliseconds
    print("FPS: %.1f" % frames_per_second)
    return (budget_name, screen.mode, screen.memory_used_bytes, frames_per_second)


def main():
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN, ROTATION)
    display.start()
    display.use_hardware_spi(SPI_MEGABITS_PER_SECOND * 1000000)

    results = []
    for budget_name, budget_bytes in BUDGETS_TO_TRY:
        results.append(run_one_test(display, budget_name, budget_bytes))
        gc.collect()

    print()
    print("===== RESULTS =====")
    for budget_name, mode, used_bytes, frames_per_second in results:
        print("%7s budget | %6.1f FPS | %6d bytes used | %s"
              % (budget_name, frames_per_second, used_bytes, mode))


main()
