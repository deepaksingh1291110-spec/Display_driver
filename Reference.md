# Nokia-Style 128 × 160 Display Driver

## Engineering Reference --- Raspberry Pi Pico 2 / MicroPython

**Document type:** Project reference and developer guide\
**Target platform:** Raspberry Pi Pico 2 (RP2350)\
**Runtime:** MicroPython v1.29.0\
**Display:** 128 × 160 colour phone display\
**Reference baseline:** Owner-supplied project manual, compiled 24
October 2026\
**Status:** Hardware behaviour and measurements below are reported from
the supplied project documentation. Items explicitly marked *not yet
verified* must not be treated as confirmed.

------------------------------------------------------------------------

## 1. Project overview

This project is a MicroPython display-driver and graphics library for a
small 128 × 160 colour phone display connected to a Raspberry Pi Pico 2.
The display is believed to be a replacement Nokia 1616 panel, and its
controller behaves like an ST7735S or a close clone. The exact panel and
controller identity have not been confirmed.

The project goes beyond a basic display driver. It provides:

-   display reset, initialization, command/data transfer, address-window
    configuration and orientation control;
-   RGB565 colour handling and raw image output;
-   buffered drawing with automatic memory-mode selection;
-   changed-row detection to avoid retransmitting unchanged portions of
    the frame;
-   four pixel-transfer backends: bit-banging, hardware SPI, SPI with
    DMA, and PIO with DMA;
-   2D primitives, clipping, sprites and image drawing;
-   bitmap fonts with four-level coverage and a custom `.nkf` font
    format;
-   time-based text animation effects;
-   basic 3D mesh rendering, lighting and wireframe modes;
-   optional MicroPython Viper-accelerated helpers with runtime
    correctness checks.

The design separates hardware communication from rendering. Higher-level
drawing modules operate on a `Screen` buffer; the `Display` class is
responsible for communicating with the physical panel.

## 2. Hardware configuration

### 2.1 Display characteristics

  -----------------------------------------------------------------------
  Property                            Project value
  ----------------------------------- -----------------------------------
  Visible resolution                  128 × 160 pixels

  Pixel format                        RGB565, 16 bits per pixel

  Serial protocol                     9-bit command/data words

  Signal lines used                   Clock, data, chip select and reset

  Suspected controller                ST7735S-compatible; not confirmed

  Controller address space            132 columns × 162 rows

  Visible glass area                  128 columns × 160 rows

  Backlight                           Reported on whenever the display is
                                      powered; not separately tested
  -----------------------------------------------------------------------

The panel is described as a non-original replacement part. Its Nokia
1616 origin is an informed belief, not a verified identification.

### 2.2 Wiring

The following pin mapping is the one used by the project code. GPIO
numbers refer to Raspberry Pi Pico 2 GPIOs.

    Pico 2 GPIO   Display flex pin Signal        Notes
  ------------- ------------------ ------------- -----------------------------
         GPIO 6                  6 Clock         SPI 0 clock-capable pin
         GPIO 7                  5 Data          SPI 0 transmit-capable pin
         GPIO 5                  3 Chip select   Controlled as a normal GPIO
         GPIO 4                  2 Reset         Controlled as a normal GPIO

GPIO 6 and GPIO 7 allow the project to use SPI 0 without changing the
wiring. The PIO transfer backend also uses these signal pins.

> **Integration note:** The supplied reference does not document the
> display power, ground, logic-voltage or backlight-pin wiring. Confirm
> those details against the actual module and board before connecting
> hardware; do not infer them from the signal table.

### 2.3 Pico 2 resources

  Resource   Reported specification
  ---------- ------------------------------------
  MCU        RP2350
  CPU        Dual-core, 150 MHz
  SRAM       520 KB
  Flash      4 MB
  PIO        3 blocks, 12 state machines
  Wireless   Not present on the standard Pico 2

After creating the display buffers and loading the project as source
modules, the tests reported approximately 350--400 KB of free RAM. The
reference recommends planning for roughly 330 KB for the rest of an
application rather than assuming that all RAM beyond the display budget
is available.

## 3. Display protocol and controller configuration

### 3.1 Nine-bit command/data format

Each transfer word consists of nine serial bits:

1.  A command/data indicator: `0` means command and `1` means data.
2.  Eight payload bits, most-significant bit first.

The display samples data on the low-to-high clock transition.

This protocol is central to the driver architecture. Standard hardware
SPI sends eight-bit bytes, so the hardware-SPI path must pack the
nine-bit words into a byte stream. The PIO path generates the ninth
indicator bit directly and can therefore transmit the raw pixel bytes
without the same packing step.

### 3.2 Initialization sequence

The supplied project reference reports the following sequence as
verified on the owner's hardware:

    Order Operation                                                    Delay after operation
  ------- ---------------------------------------------------------- -----------------------
        1 Drive reset low                                                             100 ms
        2 Drive reset high                                                            100 ms
        3 Send software reset (`0x01`)                                                150 ms
        4 Send sleep-out (`0x11`)                                                     200 ms
        5 Send `0xC9`, data `0x08`                                                      None
        6 Set pixel format (`0x3A`, data `0x05`)                                        None
        7 Set memory access/orientation (`0x36`, orientation byte)                      None
        8 Display on (`0x29`)                                                         100 ms

The command `0xC9` is described in the source as non-standard. The
tested values `0x00`, `0x08` and `0x0F` produced no visible difference;
the project retains `0x08` for compatibility with its observed
behaviour. Its purpose is not established.

A newly initialized panel may show random contents until the first frame
is written. The recommended startup practice is to clear the screen to
black and send that frame immediately after initialization.

### 3.3 Address windows and offsets

The controller memory is larger than the visible glass. The project
applies offsets when defining a drawing window.

  Orientation     Column offset   Row offset
  ------------- --------------- ------------
  Portrait                    2            1
  Landscape                   1            2

The window is configured with:

-   `0x2A`: column start and end;
-   `0x2B`: row start and end;
-   `0x2C`: begin pixel-memory write.

The offsets were checked using a one-pixel border test. Portrait offsets
must not be reused for landscape mode: doing so shifts the image and can
expose coloured edge slivers. The driver applies the
orientation-specific offsets; application code should use the public
rotation API rather than manually adjusting them.

### 3.4 RGB565 colour representation

Pixels use RGB565:

-   5 bits red;
-   6 bits green;
-   5 bits blue;
-   high byte transmitted first.

The supplied reference reports standard red/green/blue ordering, with no
red/blue swap required.

  Colour        RGB565
  --------- ----------
  Red         `0xF800`
  Green       `0x07E0`
  Blue        `0x001F`
  Yellow      `0xFFE0`
  Cyan        `0x07FF`
  Magenta     `0xF81F`
  White       `0xFFFF`
  Black       `0x0000`

Use `make_colour(red, green, blue)` to convert 8-bit RGB channel values
to RGB565.

A full portrait frame contains:

`128 × 160 × 2 = 40,960 bytes`

Raw image files use 16-bit pixels with the high byte first.

### 3.5 Orientation and mirroring

The driver uses command `0x36` to configure display memory access. The
relevant bits are:

    Bit mask Function
  ---------- ------------------------------------------------
      `0x80` Top-to-bottom mirror
      `0x40` Left-to-right mirror
      `0x20` Exchange row and column directions (landscape)

All four rotations in normal and mirrored form---eight total
orientations---are reported as verified.

  -----------------------------------------------------------------------
  Logical        Display dimensions      Register byte   Offsets (column,
  orientation                                                        row)
  -------------- ------------------ ------------------ ------------------
  Portrait, flex          128 × 160             `0x00`             (2, 1)
  at top                                               

  Landscape,              160 × 128             `0x60`             (1, 2)
  flex left                                            

  Portrait, flex          128 × 160             `0xC0`             (2, 1)
  at bottom                                            

  Landscape,              160 × 128             `0xA0`             (1, 2)
  flex right                                           
  -----------------------------------------------------------------------

With `mirrored=True`, the corresponding bytes are `0x40`, `0xE0`, `0x80`
and `0x20`.

A rotation changes the logical width and height. At the `Screen` layer,
use `screen.set_rotation(...)`; the screen reallocates its buffers and
notifies registered listeners. Application objects whose geometry
depends on screen dimensions (for example, text scrollers and clip
rectangles) should be recreated after rotation.

## 4. Software architecture

### 4.1 Layer model

``` text
Application
  ├── Font and text effects
  ├── 2D Shapes and Sprite
  └── 3D renderer
          │
        Screen
  (buffers, memory policy, dirty rows, rotation)
          │
        Display
  (GPIO, initialization, commands, transfer backend)
          │
  ├── Bit-banging
  ├── Hardware SPI
  ├── SPI + DMA
  └── PIO + DMA
```

The rendering modules draw into the screen buffer. They do not directly
operate the display pins. This keeps graphics code independent of the
selected transfer backend.

### 4.2 Module inventory

  ------------------------------------------------------------------------
  Module / resource        Responsibility          Requirement
  ------------------------ ----------------------- -----------------------
  `nokia_display.py`       `Display`,              Core
                           initialization,         
                           orientation, windows,   
                           direct drawing, images, 
                           built-in text           

  `nokia_fast.py`          Fast pixel packing,     Optional; recommended
                           changed-row detection   
                           and row-copy helpers    

  `nokia_graphics.py`      `Screen`, buffer        Core for buffered
                           allocation, memory      graphics
                           modes, rendering and    
                           change tracking         

  `nokia_dma_link.py`      SPI-DMA and PIO-DMA     Required for DMA
                           transfer support        backends

  `nokia_shapes.py`        2D primitives, clipping Optional graphics
                           and `Sprite`            module

  `nokia_shapes_fast.py`   Accelerated shape       Optional; recommended
                           rasterization           

  `nokia_font.py`          `.nkf` font loading,    Required for external
                           caching, measurement    fonts
                           and drawing             

  `nokia_font_fast.py`     Accelerated font        Optional; recommended
                           rendering helper        

  `fonts/*.nkf`            Pre-generated bitmap    Required only for
                           fonts                   selected fonts

  `nokia_text_motion.py`   Scrolling, rolling,     Optional
                           wavy, circular and      
                           timed text effects      

  `nokia_3d.py`            Meshes, 3D transforms,  Optional
                           lighting and            
                           wireframe/solid drawing 

  `make_font.py`           PC-side TrueType-to-NKF Development tool; not
                           converter               needed on Pico
  ------------------------------------------------------------------------

The `*_fast.py` helpers are optional. The source reference says the
library checks accelerated output against its Python implementation and
falls back to the slower implementation if a helper is absent or fails
its check. The intended behaviour is equivalent output, with reduced
performance when the helper is unavailable.

### 4.3 Dependency relationships

-   `nokia_graphics` uses helpers from `nokia_display` and optionally
    `nokia_fast`.
-   `nokia_shapes` operates on a supplied `Screen`.
-   `nokia_font` operates on a supplied `Screen`.
-   `nokia_text_motion` uses `nokia_font`.
-   `nokia_3d` uses `nokia_shapes`.
-   `nokia_display` loads `nokia_dma_link` when an SPI-DMA or PIO-DMA
    backend is selected.

## 5. Rendering and memory management

### 5.1 Memory budget

`Screen` accepts a display-buffer budget. The default documented value
is 100 KB (`102,400` bytes). The planner evaluates available rendering
modes and measures allocated memory after setup. If a candidate exceeds
the requested budget, it releases that allocation and tries the next
suitable mode.

The budget applies to the display buffers and send buffers described by
the project. It is not a complete accounting of the application, Python
runtime, imported modules, fonts, meshes or other user data. Use
`reserve_bytes` to leave room for additional application allocations.

### 5.2 Buffer modes

  -------------------------------------------------------------------------
  Mode             Storage model          Planned portrait Behaviour
                                                    memory 
  ---------------- ---------------- ---------------------- ----------------
  Full buffer with Current frame              90,528 bytes Sends only rows
  change tracking  plus                                    that changed
                   previous-frame                          
                   copy                                    

  Full buffer      One complete               49,408 bytes Sends the full
                   frame                                   frame

  Strips           A reusable band    `rows × 256 + 8,448` Renders and
                   of rows                           bytes sends the frame
                                                           band by band
  -------------------------------------------------------------------------

The planned fixed allowance of 8,448 bytes consists of a 2,304-byte send
buffer and a 6,144-byte safety allowance for Python objects.

Reported portrait-mode examples:

  -----------------------------------------------------------------------
          Budget        Reserve Selected           Planned       Measured
                                mode            allocation     allocation
  -------------- -------------- ----------- -------------- --------------
          100 KB           8 KB Full buffer       90,528 B       86,048 B
                                with change                
                                tracking                   

          100 KB    16 or 24 KB Full buffer       49,408 B       44,880 B

           24 KB              0 Strips, 54        22,272 B     Planner/PC
                                rows per                       check only
                                pass                       

           16 KB              0 Strips, 27        15,360 B        Planner
                                rows per                      calculation
                                pass                       
  -----------------------------------------------------------------------

The reference reports that budgets below approximately 9.5 KB are
rejected as too small. Strip-mode memory figures were not measured on
the physical Pico in the supplied test record.

### 5.3 Rendering contract

The preferred buffered rendering pattern is to put the complete scene in
one function and pass it to `screen.render(...)`.

``` python
def draw_scene(screen):
    shapes.fill_circle(64, 80, 20, RED)
    font.draw(screen, "Hello", 4, 4, WHITE)

screen.render(draw_scene, background=BLACK)
```

Important rules:

-   In full-buffer modes, the scene function runs once per frame.
-   In strips mode, the scene function runs once for each band. It must
    therefore describe the entire scene on every call.
-   Do not update animation state inside the scene function: doing so
    would advance the animation once per strip rather than once per
    frame.
-   Supply a background in strips mode because the same buffer is reused
    for each band.
-   Perform once-per-frame calculations before `render()`. The 3D
    `Object3D` implementation prepares its frame so the work is not
    repeated for every strip.
-   `show()` is unavailable in strips mode; use `render()`.

### 5.4 Reported memory costs

  Item                                                                               Reported RAM
  ------------------------------------- ---------------------------------------------------------
  Screen, change-tracking mode                                                           86,048 B
  Screen, full-buffer mode                                                               44,880 B
  Shapes object including fast helper                                               About 7,392 B
  16 × 11 sprite                                                                            352 B
  Seven fonts and demo text effects                                                      17,872 B
  One font                                3,072-byte default cache, plus optional in-memory index
  Sphere mesh, 6 rings × 10 segments                                                   About 4 KB

## 6. Pixel-transfer backends

Select a backend on the `Display` object. The source recommends using a
buffered `Screen` for normal graphics workloads.

``` python
display.use_bit_banging()
display.use_hardware_spi(24000000)
display.use_spi_dma(24000000)
display.use_pio_dma(50000000)
print(display.pixel_backend)
```

### 6.1 Backend comparison

  -----------------------------------------------------------------------
  Backend           9-bit handling    CPU behaviour     Project guidance
  ----------------- ----------------- ----------------- -----------------
  Bit-banging       Software toggles  CPU performs      Simple fallback;
                    command/data and  transfer          slow
                    clock pins                          

  Hardware SPI      Packs eight 9-bit CPU waits during  Straightforward
                    words into nine   transfer          general-purpose
                    bytes                               backend

  SPI + DMA         Packs data into   CPU can prepare   High CPU
                    chunks; DMA feeds another chunk     availability, but
                    SPI               while DMA sends   setup overhead

  PIO + DMA         PIO emits the     DMA feeds PIO;    Preferred
                    command/data bit  CPU can draw      high-throughput
                    and eight payload concurrently      option in this
                    bits                                project
  -----------------------------------------------------------------------

### 6.2 Hardware SPI limit

The project measured the SPI clock source as 48 MHz, limiting the
effective SPI bit clock to 24 MHz. Asking the API for a higher value
does not increase the actual clock on the tested configuration.

A full-screen transfer at 24 MHz is reported at approximately 15.4 ms
for the packed stream. Hardware SPI occupies the CPU while the transfer
runs.

### 6.3 SPI + DMA

The SPI-DMA path uses two small packed-data buffers. While DMA sends one
chunk, the CPU can pack the next chunk.

Reported observations:

-   Correct display output on the tested hardware.
-   Approximately 97--99% CPU availability during transfer.
-   Similar raw wire time to hardware SPI because the SPI clock remains
    capped at 24 MHz.
-   Chunk setup overhead can make full-screen updates slower than plain
    hardware SPI in the project's end-to-end benchmark.

### 6.4 PIO + DMA

The PIO program transmits the nine-bit word directly: a data-indicator
bit followed by the eight bits of each pixel byte. The raw pixel data
does not require the hardware-SPI packing stage.

The reference reports correct animated output at PIO bit clocks of 25,
32, 40, 50, 62.5 and 75 MHz. The measured pixel-stream transfer times
ranged from approximately 15.83 ms at 25 MHz to 5.27 ms at 75 MHz.

The PIO pins are temporarily claimed while pixels are transmitted.
Window commands are bit-banged before the pixel transfer. If artefacts
appear at the start of a frame, the reference recommends trying a 3 µs
command delay rather than zero.

**Recommended project setting:** `display.use_pio_dma(50000000)`. With
background sending enabled in change-tracking mode, the benchmark
reached approximately 46 FPS for full-screen changes. The reference
found that rendering time, rather than transfer speed, became the
limiting factor.

### 6.5 Background sending

Background sending is documented for PIO + DMA when `Screen` uses
full-buffer-with-change-tracking mode.

The implementation copies a changed band into the previous-frame buffer,
then starts DMA from that stable copy. The application can draw the next
frame into the main buffer while the transfer is in progress.

Synchronize before operations that depend on transfer completion:

``` python
screen.wait_until_sent()
```

The next `show()`, a display command, a rotation change or a backend
switch waits for the outstanding transfer. If a transfer fails, the next
`show()` sends the full frame again.

Do not destroy a `Screen` object while a background transfer is active;
call `wait_until_sent()` first.

## 7. Public API reference

This section summarizes the documented public surface. The supplied
material is a project manual rather than the Python source files
themselves; signatures and behaviour should be checked against the
actual module version before publishing a package release.

### 7.1 `Display` --- `nokia_display.py`

Create and initialize the physical display:

``` python
from nokia_display import Display
display = Display(6, 7, 5, 4)
display.start()
display.use_pio_dma(50000000)
```

Constructor:

``` python
Display(
    clock_pin_number,
    data_pin_number,
    select_pin_number,
    reset_pin_number,
    rotation=PORTRAIT_FLEX_CABLE_AT_TOP,
    mirrored=False
)
```

Key properties:

-   `width`, `height`: dimensions for the active orientation;
-   `rotation`, `mirrored`, `is_landscape`: orientation state;
-   `bit_delay_microseconds`: bit-bang timing delay;
-   `pixel_backend`: selected transfer backend.

Key control methods:

  --------------------------------------------------------------------------------------------------------
  Method                                                               Purpose
  -------------------------------------------------------------------- -----------------------------------
  `start()`                                                            Reset and initialize the panel

  `set_rotation(rotation, mirrored=False)`                             Set panel orientation

  `send_command(command, data_values=())`                              Send a controller command and data

  `set_window(x_start, y_start, x_end, y_end)`                         Configure the pixel address window

  `use_bit_banging()`                                                  Select software-driven transfer

  `use_hardware_spi(baudrate=16000000, spi_number=0)`                  Select hardware SPI

  `use_spi_dma(baudrate=24000000)`                                     Select SPI with DMA

  `use_pio_dma(bit_clock_hz=62500000, command_delay_microseconds=0)`   Select PIO with DMA
  --------------------------------------------------------------------------------------------------------

Direct drawing methods include `fill_screen`, `draw_pixel`,
`fill_rectangle`, `draw_rectangle`, `draw_line`, `draw_circle`,
`fill_circle`, `show_image_file`, `measure_text` and `draw_text`.

Direct drawing sends operations to the panel rather than building a
complete frame in a `Screen` buffer. The reference recommends buffered
drawing for anything beyond simple tests.

### 7.2 `Screen` --- `nokia_graphics.py`

Create `Screen` after `display.start()` and after selecting a supported
fast transfer backend:

``` python
from nokia_graphics import Screen

screen = Screen(
    display,
    budget_bytes=100 * 1024,
    reserve_bytes=8 * 1024
)
print(screen.memory_report())
```

Constructor:

``` python
Screen(
    display,
    budget_bytes=102400,
    reserve_bytes=0,
    mode=None,
    use_fast_helpers=True
)
```

The `mode=None` setting asks the memory planner to choose the best mode
that fits. Explicit modes are:

-   `MODE_FULL_BUFFER_WITH_CHANGE_TRACKING`
-   `MODE_FULL_BUFFER`
-   `MODE_STRIPS`

Key methods:

  ------------------------------------------------------------------------------
  Method                                     Purpose
  ------------------------------------------ -----------------------------------
  `render(draw_scene, background=None)`      Draw and send a complete frame

  `show(full=False, wait=False)`             Send changed rows, or the full
                                             frame

  `wait_until_sent()`                        Wait for background transmission

  `set_rotation(rotation, mirrored=False)`   Change orientation and reallocate
                                             screen memory

  `rotate_clockwise()` /                     Rotate by one quarter-turn
  `rotate_anticlockwise()`                   

  `add_rotation_listener(function)`          Register a callback after rotation
                                             changes

  `memory_report()`                          Report mode, buffer sizes and free
                                             RAM
  ------------------------------------------------------------------------------

The drawing interface includes the common pixel, rectangle, line,
circle, text and image operations. `draw_image_file` reads only the
active band in strips mode.

`plan_memory(width, height, budget_bytes, reserve_bytes=0)` reports
candidate modes, rows per buffer and planned memory use.

### 7.3 `Shapes` and `Sprite` --- `nokia_shapes.py`

Initialize once with a `Screen`:

``` python
from nokia_shapes import Shapes, Sprite
shapes = Shapes(screen)
```

`Shapes` provides lines, polylines, polygons, triangles, regular
polygons, stars, ellipses, circles, rings, arcs, pie sectors, rounded
rectangles and sprites.

Common calls include:

-   `draw_line(...)`, `draw_polyline(...)`
-   `fill_polygon(...)`, `draw_polygon(...)`
-   `fill_triangle(...)`, `draw_triangle(...)`
-   `fill_regular_polygon(...)`, `draw_regular_polygon(...)`
-   `fill_star(...)`, `draw_star(...)`
-   `fill_ellipse(...)`, `draw_ellipse(...)`
-   `fill_circle(...)`, `draw_circle(...)`
-   `fill_ring(...)`, `draw_arc(...)`, `fill_pie(...)`
-   `fill_rounded_rectangle(...)`, `draw_rounded_rectangle(...)`
-   `draw_sprite(sprite, x, y)`

Angles are integer degrees, with 0° pointing right and 90° pointing
down. Coordinates outside the screen are clipped to the visible area.
`set_clip(x, y, width, height)` applies a clipping rectangle to `Shapes`
operations; `clear_clip()` removes it. This clip does not automatically
apply to `Screen` drawing or `Font`.

A `Sprite` stores 16-bit pixels in high-byte-first order. A configurable
transparent colour leaves corresponding destination pixels untouched.
Sprites can be constructed from bytes, raw files or text rows, and can
be flipped horizontally or vertically.

### 7.4 Fonts --- `nokia_font.py`

Fonts are stored in flash as `.nkf` files and loaded on demand into a
small cache. Glyphs use 2 bits per pixel, representing four coverage
levels. This provides smoother text edges than the project's basic
built-in 8 × 8 font.

``` python
from nokia_font import Font, ALIGN_LEFT, ALIGN_CENTRE, ALIGN_RIGHT

font = Font("fonts/sans_14.nkf")
font.draw(screen, "Display ready", 4, 4, WHITE)
```

Important methods:

-   `has_character(character)`
-   `character_width(character)`
-   `measure_line(text)` and `measure(text)`
-   `wrap(text, max_width)`
-   `draw(...)`
-   `draw_aligned(...)`
-   `draw_wrapped(...)`
-   `close()` and `memory_bytes()`

The text API supports clipping, alignment, optional background fill,
underline and strikethrough. It does not implement kerning. Unsupported
characters are replaced by U+FFFD when available, otherwise by `?`.

### 7.5 NKF font file format

The documented `.nkf` format uses little-endian numeric fields.

The 16-byte header contains:

    Offset Field
  -------- -----------------------------
      0--3 Magic bytes `NKF1`
         4 Line height
         5 Ascent
         6 Descent
         7 Bits per pixel (2)
      8--9 Character count
    10--11 Maximum glyph bitmap size
    12--15 Offset to glyph bitmap data

The header is followed by a 10-byte entry for each character, sorted by
character code. Entries describe the character code, bitmap offset,
glyph width and height, horizontal and vertical offsets, and pen
advance. Glyph bitmaps are stored row by row, four 2-bit pixels per
byte, with the leftmost pixel in the highest two bits. Each glyph row
starts on a new byte.

### 7.6 Font generation --- `make_font.py`

This utility runs on a computer, not on the Pico. It converts a TrueType
font into the project's NKF format and can optionally generate a
preview.

Example commands from the project reference:

``` bash
pip install pillow
python make_font.py DejaVuSans.ttf 14 sans_14.nkf
python make_font.py DejaVuSans-Bold.ttf 20 bold_20.nkf
python make_font.py DejaVuSans.ttf 24 display_24.nkf --set display
python make_font.py MyFont.ttf 16 my_16.nkf --preview my_16.png
```

The documented character sets are `full`, `display` and `ascii`. The
source lists ten supplied font files: regular sans at 11, 14 and 20 px;
bold at 11, 14 and 20 px; italic at 14 px; monospace at 12 and 16 px;
and a 24 px display font.

### 7.7 Text motion --- `nokia_text_motion.py`

Text effects are time-based. The caller supplies elapsed milliseconds,
so motion is based on time rather than the number of frames rendered.

Documented effects include:

-   `Marquee`: repeating horizontal ticker;
-   `VerticalScroller`: multi-line vertical scroll;
-   `MessageRoller`: sequential message transitions;
-   `draw_wavy_text`: animated wave or bounce effect;
-   `draw_text_on_circle`: upright characters arranged around a circle;
-   `draw_typewriter`: timed character reveal;
-   `fly_in_position`: eased position interpolation;
-   `fade_colour`: colour transition against a specified background.

Easing helpers include `linear`, `ease_in`, `ease_out`, `ease_in_out`
and `bounce_out`. Direction constants include `SCROLL_LEFT`,
`SCROLL_RIGHT`, `SCROLL_UP` and `SCROLL_DOWN`.

The glyphs are fixed bitmaps: they do not rotate or scale. Recreate
motion objects after a screen rotation if their geometry depends on
screen dimensions.

### 7.8 3D renderer --- `nokia_3d.py`

The 3D module provides mesh generation and rendering through `Shapes`.

Built-in mesh generators include:

-   `make_cube`, `make_box`;
-   `make_pyramid`, `make_cone`, `make_cylinder`;
-   `make_sphere`, `make_torus`;
-   `make_octahedron`, `make_icosahedron`.

`Mesh` stores vertices and polygon faces. `Object3D` supports position,
rotation, colour, lighting, perspective distance, preparation, drawing
and bounding-box queries.

Rendering modes:

-   `MODE_SOLID`: lit faces, optionally with edge outlines;
-   `MODE_WIREFRAME`: all mesh edges;
-   `MODE_WIREFRAME_HIDDEN_LINES`: visible edges only.

The documented renderer uses flat face shading and depth-sorts faces. It
does not provide smooth shading or a general solution for intersecting
objects. Some torus overlaps may be incorrect at certain viewing angles.
The project reports visual checks of the supplied shapes, but no
measured 3D frame rates.

## 8. Recommended quick start

The following is the basic startup pattern documented by the project:

``` python
from nokia_display import Display, BLACK
from nokia_graphics import Screen

display = Display(6, 7, 5, 4)
display.start()

# Recommended high-throughput backend for this project.
display.use_pio_dma(50000000)

screen = Screen(
    display,
    budget_bytes=100 * 1024,
    reserve_bytes=8 * 1024
)

# Clear the panel's initial contents.
screen.fill_screen(BLACK)
screen.show(wait=True)

print(screen.memory_report())
```

For a complete application, create `Shapes` and any `Font` objects after
the `Screen` is ready. Keep animation state updates outside the
`draw_scene` function, then call
`screen.render(draw_scene, background=BLACK)` for each frame.

## 9. Performance results

All figures below are copied from the supplied project reference and are
reported as measurements on the owner's Pico 2 and display using
MicroPython v1.29.0. They are benchmark results for the stated test
conditions, not universal guarantees.

### 9.1 End-to-end backend benchmark

The project compares a full-screen changing pattern with a small moving
object. The last reported run used background sending where supported.

  Backend/configuration           Full-screen update   Small-object update
  ----------------------------- -------------------- ---------------------
  Hardware SPI, 24 MHz                      22.3 FPS             167.3 FPS
  SPI + DMA, 24 MHz                         19.0 FPS             198.3 FPS
  PIO 62.5 MHz, wait for send               36.6 FPS             188.5 FPS
  PIO 25 MHz, background                    45.5 FPS             222.6 FPS
  PIO 50 MHz, background                    46.2 FPS             214.0 FPS
  PIO 62.5 MHz, background                  46.1 FPS             216.5 FPS
  PIO 75 MHz, background                    46.1 FPS             215.0 FPS

The reference concludes that, with background PIO sending, full-screen
rendering becomes CPU/drawing-limited at approximately 46 FPS. Raising
the PIO clock beyond 25 MHz did not materially improve that end-to-end
result in this benchmark.

### 9.2 Shape acceleration

The reference reports that Viper helpers accelerated many shape
operations by approximately 3.7× to 20×. Examples include:

  Operation                     Python implementation   Fast helper   Reported speed-up
  --------------------------- ----------------------- ------------- -------------------
  Filled triangle, 40 × 40                   6,215 µs        800 µs                7.8×
  Filled six-corner polygon                  9,894 µs      1,366 µs                7.2×
  Filled circle, radius 12                   3,301 µs        490 µs                6.7×
  Draw rounded rectangle                    11,156 µs        558 µs               20.0×
  Thick line, thickness 7                   10,091 µs      1,087 µs                9.3×

Thin line drawing and sprite drawing were already implemented through
efficient MicroPython/C routines and showed little difference.

### 9.3 Text animation

Reported full-buffer-mode frame rates for the text-motion demo:

  Test page                        FPS
  ----------------------------- ------
  Marquees and message roller     14.8
  Vertical scrolling              16.2
  Letter motion                   17.1
  Entrance animations             21.6

## 10. Deployment

### 10.1 Files to copy to the Pico

Copy only the modules needed by the application.

  -----------------------------------------------------------------------
  Feature                             Required project files
  ----------------------------------- -----------------------------------
  Buffered display                    `nokia_display.py`,
                                      `nokia_fast.py`,
                                      `nokia_graphics.py`

  PIO or DMA                          Add `nokia_dma_link.py`

  2D shapes and sprites               Add `nokia_shapes.py`; optionally
                                      `nokia_shapes_fast.py`

  External fonts                      Add `nokia_font.py`, optionally
                                      `nokia_font_fast.py`, and the
                                      required `.nkf` files

  Text effects                        Add `nokia_text_motion.py`

  3D rendering                        Add `nokia_3d.py` and
                                      `nokia_shapes.py`
  -----------------------------------------------------------------------

### 10.2 Optional `.mpy` compilation

The source describes compiling selected modules with `mpy-cross`
matching the MicroPython version installed on the Pico. It notes that
`.mpy` can reduce import-time compilation overhead and may reduce memory
pressure, but the actual RAM savings for this project have not been
measured.

Keep the original `.py` files on the development computer. The source
warns that if both `.py` and `.mpy` versions of a module are present on
the Pico, the `.py` version takes precedence. Viper-based fast modules
require particular care: compile with a compatible target and rerun the
built-in correctness checks. The reference specifically says the `.mpy`
RAM saving remains unmeasured.

## 11. Troubleshooting

  --------------------------------------------------------------------------------
  Symptom                 Likely explanation in   Suggested check
                          the project reference   
  ----------------------- ----------------------- --------------------------------
  Random noise after      Panel memory has not    Send a black frame immediately
  startup                 yet been overwritten    after initialization

  `Screen` rejects the    `Screen` requires a     Select hardware SPI, SPI-DMA or
  selected backend        supported fast transfer PIO-DMA before creating `Screen`
                          backend                 

  `Budget too small`      Requested budget cannot Increase budget, reduce reserve
                          fit a supported mode    or inspect `plan_memory()`

  Fast-helper warning     Optional helper is      Copy the helper module; verify
                          absent or its check     that fallback rendering works
                          failed                  

  Garbage at start of PIO Window-command timing   Try
  frame                   may be too short        `command_delay_microseconds=3`

  DMA/PIO makes no        Transfer setup,         Run the relevant PIO/DMA test
  progress                hardware constants or   script and inspect the failing
                          wiring may be wrong     stage

  SPI speed stops         Tested SPI source clock Use PIO-DMA if higher transfer
  increasing              limits transfer to 24   speed is needed
                          MHz                     

  Direct drawing is slow  Direct `Display`        Draw through `Screen`
  in PIO mode             drawing uses bit-banged 
                          commands                

  Image shifted or        Incorrect orientation   Use the rotation API; do not
  coloured edge slivers   offsets                 manually reuse portrait offsets

  Missing glyph appears   Glyph is absent from    Select a font with the glyph or
  as `?`                  the selected font       regenerate one

  Strips mode produces    Scene callback is not   Redraw the full scene on every
  incomplete output       drawing the complete    callback and provide
                          scene, or background is `background`
                          omitted                 

  Layout is wrong after   Object geometry was     Recreate dimension-dependent
  rotation                created for the         objects
                          previous dimensions     

  Two bright vertical     Reported panel/flex     Compare across colours and
  lines remain fixed on   fault                   rotations; software cannot
  glass                                           correct a physical panel defect

  `.mpy` file is          Compiler/runtime        Use a matching `mpy-cross`
  incompatible            versions do not match   release

  Font or mesh allocation Application RAM usage   Reduce caches, loaded fonts or
  raises `MemoryError`    is too high             mesh complexity; reconsider
                                                  screen budget
  --------------------------------------------------------------------------------

## 12. Verification status and known limitations

### 12.1 Reported as verified on the physical display

The supplied reference reports physical-hardware checks for:

-   display initialization and RGB565 output;
-   portrait and landscape window offsets;
-   all eight normal/mirrored orientations;
-   inversion and reduced-colour mode commands;
-   shape and font rendering;
-   animated PIO-DMA output at the listed clock settings;
-   DMA backend operation and background PIO sending.

### 12.2 Known limitations

-   The exact display model and controller identity are not confirmed.
-   Hardware SPI is limited to 24 MHz in the tested configuration.
-   Full-screen rendering is limited by Python drawing time in the
    benchmarked scene.
-   Font rendering has no kerning; glyphs cannot be rotated or scaled.
-   Shape edges are not anti-aliased; text uses four coverage levels.
-   3D shading is flat and depth sorting is per face.
-   Intersecting 3D objects are not resolved.
-   Background sending is documented only for PIO-DMA with full-buffer
    change tracking.
-   Strips mode and plain full-buffer mode wait for transfer completion.
-   PIO window commands are bit-banged.
-   SPI-DMA has chunk setup overhead and may be slower than plain SPI
    for full-screen updates.

### 12.3 Items not yet verified according to the source

-   Actual RAM savings from `.mpy` deployment.
-   3D frame rates on the Pico.
-   Long-duration stability at 62.5 MHz and 75 MHz; animated tests were
    approximately five seconds per setting.
-   The function or effect of command `0xC9`.
-   Reading controller identity bytes.
-   Gamma, brightness and sleep behaviour.
-   Whether the panel's blue-looking whites are caused by the backlight
    or camera.
-   Physical-Pico memory usage in strips mode.

## 13. Test suite inventory

  -----------------------------------------------------------------------
  Test script                         Coverage
  ----------------------------------- -----------------------------------
  `test_bouncing_ball.py`             Direct versus buffered drawing
                                      performance

  `test_memory_modes.py`              Memory planner and rendering modes

  `test_fonts.py`                     Font sizes, styles, symbols and
                                      wrapping

  `test_shapes.py`                    Shape gallery, lines, arcs,
                                      clipping, sprites and animation

  `test_shapes_speed.py`              Shape timings with and without fast
                                      helpers

  `test_text_motion.py`               Text animation effects

  `test_rotation.py`                  Eight orientations, borders and
                                      geometric checks

  `test_3d.py`                        3D solids, wireframes and mesh
                                      checks

  `test_pio_dma.py`                   DMA, SPI and PIO transfer stages

  `test_pio_dma_animated.py`          Animated transfer integrity

  `test_dma_backends.py`              End-to-end backend comparison
  -----------------------------------------------------------------------

## 14. Development recommendations

1.  **Keep the hardware layer stable.** Treat the tested pin mapping,
    startup sequence, orientation offsets and RGB565 format as the
    hardware baseline.
2.  **Use `Screen` for application rendering.** Keep direct `Display`
    drawing for bring-up and simple diagnostics.
3.  **Prefer PIO-DMA at 50 MHz for the documented setup.** The project
    benchmark indicates that this provides a useful margin without
    reducing the measured application frame rate.
4.  **Use change tracking for mostly static interfaces.** It avoids
    retransmitting unchanged rows and is well suited to dashboards,
    menus and small animated elements.
5.  **Use strips when RAM is constrained.** Ensure drawing callbacks are
    deterministic and redraw the complete scene for each band.
6.  **Keep optional acceleration optional.** The Python implementation
    should remain a correctness fallback.
7.  **Separate verified facts from assumptions.** In particular, do not
    describe the panel as definitively Nokia 1616 or the controller as
    definitively ST7735S.
8.  **Re-run tests after low-level changes.** Changes to packing, DMA
    register values, PIO timing, offsets or rotation should be followed
    by the corresponding hardware tests.

## 15. Glossary

  -----------------------------------------------------------------------
  Term                                Meaning
  ----------------------------------- -----------------------------------
  Bit-banging                         Software manually changes GPIO
                                      levels to create a serial protocol

  SPI                                 Serial Peripheral Interface
                                      hardware

  DMA                                 Direct Memory Access; hardware
                                      transfers data without the CPU
                                      copying each byte

  PIO                                 Programmable I/O state machines
                                      available on the RP2350

  Viper                               MicroPython native-code emitter
                                      used to accelerate selected
                                      functions

  RGB565                              16-bit pixel format with 5 red, 6
                                      green and 5 blue bits

  Buffer                              RAM region holding pixel data

  Strip / band                        A subset of consecutive display
                                      rows rendered as one unit

  Window                              Controller memory region selected
                                      for the next pixel write

  Offset                              Difference between controller
                                      memory coordinates and visible
                                      glass coordinates

  Change tracking                     Comparison of current and previous
                                      frames to find rows requiring
                                      transmission

  Sprite                              Small bitmap image with a
                                      transparent colour

  Mesh                                Vertices and faces defining a 3D
                                      object

  FPS                                 Frames per second

  Mock display                        Software stand-in used to test code
                                      on a computer without physical
                                      display hardware
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Source and scope note

This reference was reorganized and professionally edited from the
user-provided `Nokia_Display_Complete_Reference.md`. It preserves the
project-specific values, API names, test claims, performance figures and
verification caveats contained in that source. It does **not**
independently inspect the Python implementation, validate electrical
compatibility, or re-run hardware tests. Where the source itself
identifies uncertainty or incomplete testing, that status is retained
here.

**Suggested next release step:** validate every documented public method
against the current `.py` files, then add a version number, changelog
and tested module revision identifiers.
