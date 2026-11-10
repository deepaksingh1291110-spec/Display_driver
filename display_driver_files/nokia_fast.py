"""
Fast helper functions for nokia_display.py (Step 6).
Copy this file to the Pico next to nokia_display.py.

These use MicroPython's "viper" mode, which runs close to machine speed.
If this file is missing or does not work, nokia_display.py falls back to
slower Python versions that give exactly the same results.
"""
import micropython


@micropython.viper
def pack_data(source: ptr8, source_offset: int, destination: ptr8, byte_count: int):
    # Turns data bytes into the 9-bit words the display wants.
    # Every 8 data bytes (8 words of 9 bits = 72 bits) become exactly 9 bytes.
    # byte_count must be a multiple of 8.
    read = source_offset
    write = 0
    end = source_offset + byte_count
    while read < end:
        d0 = source[read]
        d1 = source[read + 1]
        d2 = source[read + 2]
        d3 = source[read + 3]
        d4 = source[read + 4]
        d5 = source[read + 5]
        d6 = source[read + 6]
        d7 = source[read + 7]
        destination[write] = 0x80 | (d0 >> 1)
        destination[write + 1] = ((d0 & 1) << 7) | 0x40 | (d1 >> 2)
        destination[write + 2] = ((d1 & 3) << 6) | 0x20 | (d2 >> 3)
        destination[write + 3] = ((d2 & 7) << 5) | 0x10 | (d3 >> 4)
        destination[write + 4] = ((d3 & 15) << 4) | 0x08 | (d4 >> 5)
        destination[write + 5] = ((d4 & 31) << 3) | 0x04 | (d5 >> 6)
        destination[write + 6] = ((d5 & 63) << 2) | 0x02 | (d6 >> 7)
        destination[write + 7] = ((d6 & 127) << 1) | 0x01
        destination[write + 8] = d7
        read += 8
        write += 9


@micropython.viper
def mark_changed_rows(current: ptr32, previous: ptr32, words_per_row: int,
                      first_row: int, last_row: int, flags: ptr8):
    # For each row from first_row to last_row: flags[row] = 1 if the row is
    # different in the two pictures, otherwise 0. Compares 4 bytes at a time.
    row = first_row
    index = first_row * words_per_row
    while row <= last_row:
        changed = 0
        column = 0
        while column < words_per_row:
            if current[index] != previous[index]:
                changed = 1
            index += 1
            column += 1
        flags[row] = changed
        row += 1


@micropython.viper
def copy_region(source: ptr32, destination: ptr32, word_offset: int, word_count: int):
    # Copies word_count words (4 bytes each), starting at word_offset.
    index = word_offset
    end = word_offset + word_count
    while index < end:
        destination[index] = source[index]
        index += 1
