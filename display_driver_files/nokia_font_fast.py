"""
Fast helper for nokia_font.py.
Copy this file to the Pico next to nokia_font.py.

It uses MicroPython's "viper" mode, which runs close to machine speed.
If this file is missing or does not work, nokia_font.py falls back to a
slower Python version that gives exactly the same pixels.
"""
import micropython


@micropython.viper
def blend_glyph(destination: ptr8, glyph: ptr8, parameters: ptr32):
    # Blends one character picture into the screen buffer.
    # See _python_blend_glyph in nokia_font.py for what each number means.
    glyph_row_bytes = int(parameters[0])
    first_row = int(parameters[1])
    last_row = int(parameters[2])
    first_column = int(parameters[3])
    last_column = int(parameters[4])
    destination_start = int(parameters[5])
    destination_row_bytes = int(parameters[6])
    colour_red = int(parameters[7])
    colour_green = int(parameters[8])
    colour_blue = int(parameters[9])
    colour_high_byte = int(parameters[10])
    colour_low_byte = int(parameters[11])

    row = first_row
    while row < last_row:
        index = destination_start + (row - first_row) * destination_row_bytes
        glyph_row_start = row * glyph_row_bytes
        column = first_column
        while column < last_column:
            level = (int(glyph[glyph_row_start + (column >> 2)]) >> (6 - ((column & 3) << 1))) & 3
            if level == 3:
                destination[index] = colour_high_byte
                destination[index + 1] = colour_low_byte
            elif level != 0:
                strength = 85
                if level == 2:
                    strength = 170
                current = (int(destination[index]) << 8) | int(destination[index + 1])
                red = (((current >> 11) & 31) * (256 - strength) + colour_red * strength) >> 8
                green = (((current >> 5) & 63) * (256 - strength) + colour_green * strength) >> 8
                blue = ((current & 31) * (256 - strength) + colour_blue * strength) >> 8
                mixed = (red << 11) | (green << 5) | blue
                destination[index] = mixed >> 8
                destination[index + 1] = mixed & 255
            index += 2
            column += 1
        row += 1
