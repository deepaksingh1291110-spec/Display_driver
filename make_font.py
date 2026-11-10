"""
make_font.py - runs on your PC (not on the Pico).

Turns a TrueType font (.ttf) into a small .nkf file that nokia_font.py
can read on the Pico.

Needs Pillow once:   pip install pillow

EXAMPLES
    python make_font.py DejaVuSans.ttf 14 sans_14.nkf
    python make_font.py DejaVuSans-Bold.ttf 20 bold_20.nkf
    python make_font.py DejaVuSans.ttf 24 display_24.nkf --set display
    python make_font.py MyFont.ttf 16 my_16.nkf --preview my_16.png

CHARACTER SETS
    --set full      English, accented letters, money signs, Greek,
                    maths symbols, superscripts, subscripts, fractions,
                    arrows and a few more (default)
    --set display   a smaller set for big number displays: digits, English
                    letters, basic signs and the most used maths symbols
    --set ascii     only the plain English keyboard characters

A character that the font does not contain is skipped, and the list of
skipped characters is printed.

FILE FORMAT (.nkf), all numbers little endian
    16 bytes header:
        0-3    the letters NKF1
        4      line height in pixels
        5      ascent (pixels from the top of the line to the baseline)
        6      descent (pixels from the baseline to the bottom of the line)
        7      bits per pixel (always 2: four levels of grey)
        8-9    number of characters
        10-11  size in bytes of the biggest character picture
        12-15  where the pictures start in the file
    then one 10 byte entry per character, sorted by character code:
        0-1    character code
        2-4    where its picture starts, counted from the start of the pictures
        5      picture width
        6      picture height
        7      sideways shift from the pen position (signed)
        8      upward shift from the baseline (signed, negative means above)
        9      how far the pen moves to the right after the character
    then the pictures. A picture is stored row by row, 4 pixels per byte,
    the left pixel in the highest two bits. Each row starts on a new byte.
    Level 0 is empty, level 3 is the full colour.
"""
import argparse
import struct
import sys

from PIL import Image, ImageDraw, ImageFont


def code_range(first, last):
    return [chr(code) for code in range(first, last + 1)]


ASCII_CHARACTERS = code_range(0x20, 0x7E)

DISPLAY_EXTRA = list("−×÷±√π∞°²³⁻₹€£¥")

FULL_EXTRA = (
    code_range(0xA1, 0xFF)                    # Latin-1: accents, £ ¥ © ® ° ± × ÷ ½ ...
    + list("€₹₽₩₺")                           # more money signs
    + code_range(0x100, 0x17F)                # more accented letters
    + code_range(0x391, 0x3A1) + code_range(0x3A3, 0x3A9)   # Greek capitals
    + code_range(0x3B1, 0x3C9)                # Greek small letters
    + list("–—‘’‚“”„†‡•…‰′″‹›")               # punctuation
    + list("⁰ⁱ⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")                  # superscripts
    + list("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₙ")            # subscripts
    + list("⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞")                    # fractions
    + list("℃℉™№ℓℏℂℕℚℝℤ")                    # letter-like signs
    + list("←↑→↓↔↕⇐⇒⇔↵")                      # arrows
    + list("∀∂∃∅∆∇∈∉∋∏∑−∓∕∘∙√∛∜∝∞∠∣∥∧∨∩∪∫∬∭∮∴∵∼≅≈≠≡≤≥≪≫⊂⊃⊆⊇⊕⊗⊥⋅⌈⌉⌊⌋⌫")  # maths
    + list("✓✗★☆♥♦♠♣■□▲▼●○◆◇☐☑☒")             # shapes and ticks
)


def character_set(name):
    if name == "ascii":
        characters = list(ASCII_CHARACTERS)
    elif name == "display":
        characters = list(ASCII_CHARACTERS) + DISPLAY_EXTRA
    else:
        characters = list(ASCII_CHARACTERS) + FULL_EXTRA
    unique = sorted(set(characters))
    return unique


def quantise_table():
    # 0..255 -> 0..3, nearest of 0, 85, 170, 255
    table = []
    for value in range(256):
        if value < 43:
            table.append(0)
        elif value < 128:
            table.append(1)
        elif value < 213:
            table.append(2)
        else:
            table.append(3)
    return table


def read_cmap(font_path):
    try:
        from fontTools.ttLib import TTFont
        return TTFont(font_path, fontNumber=0).getBestCmap()
    except Exception:
        return None


def render_character(font, character, pixel_size, table):
    """Returns (levels, width, height, x_shift, y_shift, advance).
    levels is a list of rows, each row a list of numbers 0..3."""
    canvas_size = pixel_size * 4
    origin_x = pixel_size
    origin_y = pixel_size * 3

    picture = Image.new("L", (canvas_size, canvas_size), 0)
    ImageDraw.Draw(picture).text((origin_x, origin_y), character, font=font,
                                 fill=255, anchor="ls")
    picture = picture.point(table, "L")  # now values are 0..3
    box = picture.getbbox()

    advance = int(round(font.getlength(character)))
    if advance < 0:
        advance = 0
    if advance > 255:
        advance = 255

    if box is None:
        return ([], 0, 0, 0, 0, advance)

    cropped = picture.crop(box)
    width, height = cropped.size
    pixels = list(cropped.tobytes())
    rows = [pixels[row * width:(row + 1) * width] for row in range(height)]
    return (rows, width, height, box[0] - origin_x, box[1] - origin_y, advance)


def pack_rows(rows, width):
    packed = bytearray()
    for row in rows:
        for column_start in range(0, width, 4):
            byte_value = 0
            for position in range(4):
                column = column_start + position
                level = row[column] if column < width else 0
                byte_value |= (level & 3) << (6 - 2 * position)
            packed.append(byte_value)
    return packed


def build_font(font_path, pixel_size, characters):
    font = ImageFont.truetype(font_path, pixel_size, layout_engine=ImageFont.Layout.BASIC)
    ascent, descent = font.getmetrics()
    table = quantise_table()
    cmap = read_cmap(font_path)

    entries = []
    pictures = bytearray()
    skipped = []
    biggest = 0

    for character in characters:
        if cmap is not None and ord(character) not in cmap:
            skipped.append(character)
            continue
        rows, width, height, x_shift, y_shift, advance = render_character(
            font, character, pixel_size, table)
        if not (-128 <= x_shift <= 127 and -128 <= y_shift <= 127 and width < 256 and height < 256):
            skipped.append(character)
            continue
        data = pack_rows(rows, width)
        biggest = max(biggest, len(data))
        entries.append((ord(character), len(pictures), width, height, x_shift, y_shift, advance))
        pictures += data

    if len(entries) > 65535 or len(pictures) >= (1 << 24):
        sys.exit("Too many characters or pictures for the file format.")

    line_height = ascent + descent
    header_bytes = 16
    data_start = header_bytes + 10 * len(entries)

    output = bytearray()
    output += b"NKF1"
    output += struct.pack("<BBBB", line_height, ascent, descent, 2)
    output += struct.pack("<HHI", len(entries), biggest, data_start)
    for code, offset, width, height, x_shift, y_shift, advance in entries:
        output += struct.pack("<H", code)
        output += struct.pack("<I", offset)[0:3]
        output += struct.pack("<BBbbB", width, height, x_shift, y_shift, advance)
    output += pictures
    return bytes(output), len(entries), skipped, (line_height, ascent, descent)


def make_preview(font_path, pixel_size, characters, preview_path):
    """A picture of the characters, made with the same rendering as the file."""
    font = ImageFont.truetype(font_path, pixel_size, layout_engine=ImageFont.Layout.BASIC)
    table = quantise_table()
    columns = 24
    cell = pixel_size + 6
    rows = (len(characters) + columns - 1) // columns
    sheet = Image.new("L", (columns * cell, rows * cell), 0)
    for number, character in enumerate(characters):
        picture = Image.new("L", (cell, cell), 0)
        ImageDraw.Draw(picture).text((3, cell - 6 - pixel_size // 4), character,
                                     font=font, fill=255, anchor="ls")
        picture = picture.point(table, "L").point(lambda value: value * 85)
        sheet.paste(picture, ((number % columns) * cell, (number // columns) * cell))
    sheet = sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST)
    sheet.save(preview_path)


def main():
    parser = argparse.ArgumentParser(description="Make a .nkf font file from a TrueType font.")
    parser.add_argument("font_file", help="path to the .ttf file")
    parser.add_argument("pixel_size", type=int, help="text size in pixels, for example 14")
    parser.add_argument("output_file", help="name of the .nkf file to write")
    parser.add_argument("--set", dest="character_set", default="full",
                        choices=["full", "display", "ascii"])
    parser.add_argument("--preview", help="also write a PNG picture of all characters")
    arguments = parser.parse_args()

    characters = character_set(arguments.character_set)
    data, count, skipped, metrics = build_font(arguments.font_file, arguments.pixel_size, characters)

    with open(arguments.output_file, "wb") as output_file:
        output_file.write(data)

    print("Wrote", arguments.output_file, "-", len(data), "bytes,", count, "characters")
    print("Line height", metrics[0], "(ascent", metrics[1], ", descent", metrics[2], ")")
    if skipped:
        print("Skipped (not in this font):", "".join(skipped))

    if arguments.preview:
        make_preview(arguments.font_file, arguments.pixel_size, characters, arguments.preview)
        print("Preview written to", arguments.preview)


if __name__ == "__main__":
    main()
