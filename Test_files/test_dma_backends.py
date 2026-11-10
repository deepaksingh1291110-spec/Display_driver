"""
Test of all the ways to send pixels, through the library (Screen).

On the Pico you need:
    nokia_display.py (new)  nokia_graphics.py (new)  nokia_dma_link.py
    nokia_fast.py

For every way it runs two animations of ANIMATION_SECONDS each and prints the
frames per second:
    A  full-screen change: moving stripes, so every picture is different
       and the whole screen has to be sent every frame
    B  small change: a bouncing ball, only a few rows are sent
WATCH THE DISPLAY. Correct: stripes slide sideways smoothly and the ball moves
smoothly, with no noise, flicker, tearing or wrong colours.
The ways are: hardware SPI, SPI + DMA, and PIO + DMA at several speeds, with the
picture sent in the background (the new way) or with show() waiting (the old way).
"""
import gc
import time

import nokia_display
from nokia_display import Display
from nokia_graphics import Screen

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4
ANIMATION_SECONDS = 4

BLACK = nokia_display.BLACK
WHITE = nokia_display.WHITE
RED = nokia_display.RED
GREEN = nokia_display.GREEN
BLUE = nokia_display.BLUE
YELLOW = nokia_display.YELLOW

results = []


def animate_stripes(screen, seconds):
    """A: the whole picture changes every frame. Returns frames per second."""
    frame = 0
    start = time.ticks_ms()
    end = time.ticks_add(start, seconds * 1000)
    width = screen.width
    height = screen.height

    def draw(target):
        shift = frame % 16
        for number in range(-1, width // 8 + 2):
            colour = RED if number % 2 == 0 else BLUE
            target.fill_rectangle(number * 8 + shift, 0, 8, height // 2, colour)
        for number in range(width // 2):
            target.fill_rectangle(number * 2 + (frame & 1), height // 2, 1, height // 2,
                                  WHITE if number % 2 == 0 else GREEN)

    while time.ticks_diff(end, time.ticks_ms()) > 0:
        screen.render(draw, background=BLACK)
        frame += 1
    return frame * 1000 / time.ticks_diff(time.ticks_ms(), start)


def animate_ball(screen, seconds):
    """B: a ball bounces. Only a few rows change. Returns frames per second."""
    radius = 10
    width = screen.width
    height = screen.height
    fixed = 256
    ball_x = width // 3 * fixed
    ball_y = height // 3 * fixed
    speed_x = 150 * fixed
    speed_y = 110 * fixed
    previous_x = ball_x // fixed
    previous_y = ball_y // fixed
    colours = (RED, GREEN, YELLOW, WHITE)
    colour_number = 0
    screen.fill_screen(BLACK)
    screen.show()

    frames = 0
    start = time.ticks_ms()
    end = time.ticks_add(start, seconds * 1000)
    last = time.ticks_us()
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        now = time.ticks_us()
        elapsed = time.ticks_diff(now, last)
        last = now
        ball_x += speed_x * elapsed // 1000000
        ball_y += speed_y * elapsed // 1000000
        if ball_x < radius * fixed or ball_x > (width - 1 - radius) * fixed:
            speed_x = -speed_x
            ball_x = max(radius * fixed, min(ball_x, (width - 1 - radius) * fixed))
            colour_number = (colour_number + 1) % 4
        if ball_y < radius * fixed or ball_y > (height - 1 - radius) * fixed:
            speed_y = -speed_y
            ball_y = max(radius * fixed, min(ball_y, (height - 1 - radius) * fixed))
            colour_number = (colour_number + 1) % 4
        x = ball_x // fixed
        y = ball_y // fixed
        screen.fill_rectangle(previous_x - radius, previous_y - radius,
                              2 * radius + 1, 2 * radius + 1, BLACK)
        screen.fill_circle(x, y, radius, colours[colour_number])
        screen.show()
        previous_x = x
        previous_y = y
        frames += 1
    return frames * 1000 / time.ticks_diff(time.ticks_ms(), start)


def run(display, screen, name, setup, background=True):
    print()
    print(">>> NOW:", name)
    try:
        setup()
        screen.background_sending = background
        screen.show(full=True, wait=True)
        gc.collect()
        print("    pixels sent by:", display.pixel_backend,
              "| in the background:", background and display.pixel_backend.startswith("PIO"))
        fps_a = animate_stripes(screen, ANIMATION_SECONDS)
        screen.wait_until_sent()
        fps_b = animate_ball(screen, ANIMATION_SECONDS)
        screen.wait_until_sent()
        results.append((name, fps_a, fps_b))
        print("    A full-screen stripes: %.1f FPS    B small ball: %.1f FPS" % (fps_a, fps_b))
    except Exception as error:
        print("    !! FAILED:", type(error).__name__, error)
    screen.background_sending = True


def main():
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN)
    display.start()
    display.use_hardware_spi(24000000)
    screen = Screen(display, budget_bytes=100 * 1024, reserve_bytes=8 * 1024)
    screen.fill_screen(BLACK)
    screen.show()
    print(screen.memory_report())

    run(display, screen, "hardware SPI 24 MHz (the CPU waits)",
        lambda: display.use_hardware_spi(24000000))
    run(display, screen, "SPI + DMA 24 MHz", lambda: display.use_spi_dma(24000000))
    run(display, screen, "PIO 62.5 MHz, command delay 3, show() waits (old way)",
        lambda: display.use_pio_dma(62500000, 3), background=False)
    run(display, screen, "PIO 62.5 MHz, command delay 0, show() waits",
        lambda: display.use_pio_dma(62500000, 0), background=False)
    for megahertz in (25, 50, 62.5, 75):
        run(display, screen, "PIO %.1f MHz, command delay 0, IN THE BACKGROUND" % megahertz,
            lambda megahertz=megahertz: display.use_pio_dma(int(megahertz * 1000000), 0))

    print()
    print("===== SUMMARY =====")
    print("%-60s %10s %10s" % ("way of sending", "A full", "B ball"))
    for name, fps_a, fps_b in results:
        print("%-60s %7.1f FPS %7.1f FPS" % (name, fps_a, fps_b))
    print("Tell me which lines looked correct on the display.")


main()
