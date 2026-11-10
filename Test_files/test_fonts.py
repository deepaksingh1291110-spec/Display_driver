"""
Font test for nokia_font.py

On the Pico you need these files:
    nokia_display.py  nokia_fast.py  nokia_graphics.py
    nokia_font.py     nokia_font_fast.py
    a folder called  fonts  holding the .nkf files

It shows four pages for PAGE_SECONDS each, and prints the FPS of every
page and the memory used by the screen and by the fonts.
"""
import gc
import time

import nokia_display
from nokia_display import Display, make_colour
from nokia_graphics import Screen
from nokia_font import Font, ALIGN_LEFT, ALIGN_CENTRE, ALIGN_RIGHT

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4

ROTATION = nokia_display.PORTRAIT_FLEX_CABLE_AT_TOP
SPI_MEGABITS_PER_SECOND = 32
PAGE_SECONDS = 5

FONT_FOLDER = "fonts"

# Memory kept free inside the 100 KB budget for fonts and your own data.
SCREEN_BUDGET_BYTES = 100 * 1024
FONT_RESERVE_BYTES = 24 * 1024

BLACK = nokia_display.BLACK
WHITE = nokia_display.WHITE
YELLOW = nokia_display.YELLOW
CYAN = nokia_display.CYAN
GREEN = nokia_display.GREEN
PANEL = make_colour(40, 40, 48)
KEY = make_colour(70, 70, 90)
KEY_ACCENT = make_colour(200, 110, 20)


def load_fonts():
    names = ("sans_11", "sans_14", "sans_20", "bold_14", "italic_14",
             "mono_12", "display_24")
    fonts = {}
    for name in names:
        fonts[name] = Font(FONT_FOLDER + "/" + name + ".nkf")
    return fonts


# ===============================
# THE FOUR PAGES
# Each one draws the WHOLE picture, so it works in every memory mode.
# ===============================
def page_sizes_and_styles(screen, fonts):
    fonts["bold_14"].draw_aligned(screen, "Sizes & styles", 0, 2, screen.width, YELLOW,
                                  ALIGN_CENTRE, underline=True)
    fonts["sans_11"].draw(screen, "Small 11 px", 4, 28, WHITE)
    fonts["sans_14"].draw(screen, "Normal 14 px", 4, 44, WHITE)
    fonts["sans_20"].draw(screen, "Large 20 px", 4, 62, WHITE)
    fonts["bold_14"].draw(screen, "Bold 14 px", 4, 88, YELLOW)
    fonts["italic_14"].draw(screen, "Italic 14 px", 4, 106, CYAN)
    fonts["mono_12"].draw(screen, "Mono 0123 [x]", 4, 124, GREEN)
    fonts["sans_11"].draw(screen, "underline", 4, 142, WHITE, underline=True)
    fonts["sans_11"].draw(screen, "strike", 70, 142, WHITE, strikethrough=True)


def page_symbols(screen, fonts):
    font = fonts["sans_14"]
    fonts["bold_14"].draw_aligned(screen, "Symbols", 0, 2, screen.width, YELLOW,
                                  ALIGN_CENTRE, underline=True)
    rows = (
        "+ − × ÷ = ± %",
        "√ ∛ π ∞ ° ∑ ∫",
        "≤ ≥ ≠ ≈ → ⇒ ⇔",
        "x² x³ x⁻¹ ½ ¾",
        "H₂O Δ α β γ Ω",
        "@ # & $ € ¥ £ ₹",
    )
    for row_number in range(len(rows)):
        font.draw(screen, rows[row_number], 4, 26 + row_number * 20, WHITE)


def page_calculator(screen, fonts):
    width = screen.width
    screen.fill_rectangle(0, 0, width, 56, PANEL)
    fonts["sans_11"].draw_aligned(screen, "√(2) × π =", 0, 4, width - 4, CYAN, ALIGN_RIGHT)
    fonts["display_24"].draw_aligned(screen, "−4.44288", 0, 22, width - 4, WHITE, ALIGN_RIGHT)

    labels = (("7", "8", "9", "÷"),
              ("4", "5", "6", "×"),
              ("1", "2", "3", "−"),
              ("0", ".", "=", "+"))
    key_width = 30
    key_height = 22
    for row_number in range(4):
        for column_number in range(4):
            key_x = 2 + column_number * (key_width + 2)
            key_y = 60 + row_number * (key_height + 2)
            label = labels[row_number][column_number]
            colour = KEY_ACCENT if column_number == 3 else KEY
            screen.fill_rectangle(key_x, key_y, key_width, key_height, colour)
            fonts["sans_14"].draw_aligned(screen, label, key_x, key_y + 3, key_width,
                                          WHITE, ALIGN_CENTRE)


def page_word_wrap(screen, fonts):
    fonts["bold_14"].draw_aligned(screen, "Word wrap", 0, 2, screen.width, YELLOW,
                                  ALIGN_CENTRE, underline=True)
    used = fonts["sans_11"].draw_wrapped(
        screen,
        "Long text is cut into lines at the spaces so that it fits the screen "
        "width. A very long word like unbelievablylongwordcut is split.",
        3, 26, screen.width - 6, WHITE)
    fonts["italic_14"].draw_aligned(screen, "right aligned", 0, 26 + used + 6,
                                    screen.width - 3, CYAN, ALIGN_RIGHT)


PAGES = (
    ("Sizes and styles", page_sizes_and_styles),
    ("Symbols", page_symbols),
    ("Calculator", page_calculator),
    ("Word wrap", page_word_wrap),
)


def main():
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN, ROTATION)
    display.start()
    display.use_hardware_spi(SPI_MEGABITS_PER_SECOND * 1000000)

    screen = Screen(display, budget_bytes=SCREEN_BUDGET_BYTES,
                    reserve_bytes=FONT_RESERVE_BYTES)
    print(screen.memory_report())

    gc.collect()
    before_fonts = gc.mem_alloc()
    fonts = load_fonts()
    gc.collect()
    font_bytes = gc.mem_alloc() - before_fonts
    print()
    print("Fonts loaded     :", len(fonts))
    print("Fast font helper :", fonts["sans_14"].fast_helpers_in_use)
    print("Memory for fonts :", font_bytes, "bytes (before any text is drawn)")

    results = []
    for page_name, page_function in PAGES:
        def draw_page(target, page_function=page_function):
            page_function(target, fonts)

        frame_count = 0
        start_time = time.ticks_ms()
        end_time = time.ticks_add(start_time, PAGE_SECONDS * 1000)
        while time.ticks_diff(end_time, time.ticks_ms()) > 0:
            screen.render(draw_page, background=BLACK)
            frame_count += 1
        total_milliseconds = time.ticks_diff(time.ticks_ms(), start_time)
        frames_per_second = frame_count * 1000 / total_milliseconds
        results.append((page_name, frames_per_second))
        print("%-18s %6.1f FPS" % (page_name, frames_per_second))

    gc.collect()
    total_used = screen.memory_used_bytes + (gc.mem_alloc() - before_fonts)
    print()
    print("Screen + fonts (with caches filled):", total_used, "bytes of",
          SCREEN_BUDGET_BYTES, "budget")


main()
