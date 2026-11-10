"""
Bouncing ball speed test for nokia_display.py

Copy to the Pico next to nokia_display.py and nokia_fast.py, then run it.
It tries three ways of drawing, each for a few seconds, and prints the
frames per second (FPS) of each one at the end.

The ball moves by elapsed time, not by frame, so it looks the same speed
at any FPS. No memory is allocated inside the animation loop.
"""
import gc
import time

import nokia_display
from nokia_display import Display, BufferedDisplay

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4

ROTATION = nokia_display.PORTRAIT_FLEX_CABLE_AT_TOP
SECONDS_PER_TEST = 8
BALL_RADIUS = 10
BALL_SPEED_PIXELS_PER_SECOND_X = 150
BALL_SPEED_PIXELS_PER_SECOND_Y = 110
BACKGROUND = nokia_display.BLACK

# Ball changes colour every time it hits a wall
BALL_COLOURS = (
    nokia_display.RED,
    nokia_display.GREEN,
    nokia_display.YELLOW,
    nokia_display.CYAN,
    nokia_display.MAGENTA,
    nokia_display.WHITE,
)

FIXED_POINT = 256  # positions are whole numbers in 1/256 pixel steps (no floats)


def run_ball_test(screen, test_name, seconds):
    """Animate one ball on 'screen' for 'seconds'. Returns frames per second.
    'screen' may be a Display (draws at once) or a BufferedDisplay
    (draws into memory, then needs show())."""
    show = getattr(screen, "show", None)

    width = screen.width
    height = screen.height
    radius = BALL_RADIUS

    left_limit = radius * FIXED_POINT
    right_limit = (width - 1 - radius) * FIXED_POINT
    top_limit = radius * FIXED_POINT
    bottom_limit = (height - 1 - radius) * FIXED_POINT

    ball_x = width // 3 * FIXED_POINT
    ball_y = height // 3 * FIXED_POINT
    speed_x = BALL_SPEED_PIXELS_PER_SECOND_X * FIXED_POINT
    speed_y = BALL_SPEED_PIXELS_PER_SECOND_Y * FIXED_POINT
    colour_number = 0

    previous_pixel_x = ball_x // FIXED_POINT
    previous_pixel_y = ball_y // FIXED_POINT

    screen.fill_screen(BACKGROUND)
    if show:
        show()

    gc.collect()
    print("Running:", test_name)

    frame_count = 0
    start_time = time.ticks_ms()
    last_time_microseconds = time.ticks_us()
    end_time = time.ticks_add(start_time, seconds * 1000)

    while time.ticks_diff(end_time, time.ticks_ms()) > 0:
        now_microseconds = time.ticks_us()
        elapsed_microseconds = time.ticks_diff(now_microseconds, last_time_microseconds)
        last_time_microseconds = now_microseconds

        # Move the ball by the time that passed
        ball_x += speed_x * elapsed_microseconds // 1000000
        ball_y += speed_y * elapsed_microseconds // 1000000

        hit_wall = False
        if ball_x < left_limit:
            ball_x = left_limit
            speed_x = -speed_x
            hit_wall = True
        elif ball_x > right_limit:
            ball_x = right_limit
            speed_x = -speed_x
            hit_wall = True
        if ball_y < top_limit:
            ball_y = top_limit
            speed_y = -speed_y
            hit_wall = True
        elif ball_y > bottom_limit:
            ball_y = bottom_limit
            speed_y = -speed_y
            hit_wall = True
        if hit_wall:
            colour_number = (colour_number + 1) % len(BALL_COLOURS)

        pixel_x = ball_x // FIXED_POINT
        pixel_y = ball_y // FIXED_POINT

        # Erase only the small square where the ball was, then draw it again
        screen.fill_rectangle(previous_pixel_x - radius, previous_pixel_y - radius,
                              2 * radius + 1, 2 * radius + 1, BACKGROUND)
        screen.fill_circle(pixel_x, pixel_y, radius, BALL_COLOURS[colour_number])
        if show:
            show()

        previous_pixel_x = pixel_x
        previous_pixel_y = pixel_y
        frame_count += 1

    total_milliseconds = time.ticks_diff(time.ticks_ms(), start_time)
    frames_per_second = frame_count * 1000 / total_milliseconds
    print("  frames:", frame_count, " time:", total_milliseconds, "ms",
          " FPS: %.1f" % frames_per_second)
    return frames_per_second


def make_display(megabits_per_second):
    """Create, start and switch to hardware SPI at the given speed."""
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN, ROTATION)
    display.start()
    display.use_hardware_spi(megabits_per_second * 1000000)
    return display


def main():
    results = []

    # Test 1: drawing straight to the screen (no memory copy)
    display = make_display(32)
    name = "Direct drawing, hardware SPI 32 MHz"
    results.append((name, run_ball_test(display, name, SECONDS_PER_TEST)))
    display.fill_screen(BACKGROUND)

    # Test 2 and 3: drawing into memory, sending only changed rows
    for megabits in (16, 32):
        display = make_display(megabits)
        buffered = BufferedDisplay(display)
        name = "Buffered, hardware SPI %d MHz" % megabits
        if buffered.fast_helpers_in_use:
            name += " (nokia_fast)"
        else:
            name += " (slow Python helpers)"
        results.append((name, run_ball_test(buffered, name, SECONDS_PER_TEST)))
        del buffered
        gc.collect()

    print()
    print("===== RESULTS =====")
    for name, frames_per_second in results:
        print("%6.1f FPS  %s" % (frames_per_second, name))


main()
