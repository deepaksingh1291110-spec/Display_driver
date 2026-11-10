# Nokia Display Driver – Complete API Reference

**Platform:** Raspberry Pi Pico 2 (RP2350)  
**Display:** Nokia 128 × 160 colour display  
**Language:** MicroPython  
**Colour format:** RGB565 (16-bit)  
**Purpose:** Complete reference for the APIs provided by this display-driver project.

---

# Table of Contents

1. Project Overview
2. Installation and Requirements
3. Colour System and Constants
4. Display Rotation Constants
5. `nokia_display.py` – Core Display API
6. `nokia_display.py` – BufferedDisplay API
7. `nokia_graphics.py` – Screen and Memory Management API
8. `nokia_shapes.py` – 2D Shapes API
9. `nokia_shapes.py` – Sprite API
10. `nokia_3d.py` – 3D Graphics API
11. `nokia_font.py` – Custom Font API
12. `nokia_text_motion.py` – Text Animation API
13. `nokia_dma_link.py` – DMA Support API
14. Fast Helper Modules
15. Complete Usage Examples
16. Important Notes and Limitations
17. Module Reference Summary

---

# 1. Project Overview

This project provides a MicroPython graphics library for controlling a Nokia 128 × 160 colour display using a Raspberry Pi Pico 2.

It provides APIs for:

- Initialising the display.
- Sending commands to the display controller.
- Hardware SPI communication.
- Bit-banging communication.
- SPI DMA and PIO DMA communication.
- Drawing individual pixels.
- Drawing lines, rectangles and circles.
- Drawing complex 2D shapes.
- Rendering polygons, stars, arcs and rings.
- Displaying raw RGB565 image files.
- Creating and drawing transparent sprites.
- Managing screen memory.
- Rendering graphics using full-frame buffers or strips.
- Detecting changed screen regions.
- Displaying custom fonts.
- Measuring and wrapping text.
- Scrolling and animating text.
- Rendering basic 3D objects.
- Drawing solid and wireframe 3D models.
- Using optional MicroPython Viper acceleration helpers.

The project is divided into the following modules:

| Module | Purpose |
|---|---|
| `nokia_display.py` | Core display control and basic drawing |
| `nokia_graphics.py` | Memory-managed screen rendering |
| `nokia_shapes.py` | Advanced 2D drawing and sprites |
| `nokia_shapes_fast.py` | Accelerated 2D drawing helpers |
| `nokia_3d.py` | 3D meshes and objects |
| `nokia_font.py` | Custom font rendering |
| `nokia_font_fast.py` | Accelerated font rendering |
| `nokia_text_motion.py` | Scrolling and animated text |
| `nokia_dma_link.py` | SPI DMA and PIO DMA communication |
| `nokia_fast.py` | Accelerated display-buffer operations |

---

# 2. Installation and Requirements

Copy the required Python modules to the Raspberry Pi Pico 2.

For complete functionality, keep the modules in the same directory on the Pico.

## Required MicroPython modules

The project uses MicroPython hardware modules, including:

- `machine`
- `framebuf`
- `array`
- `gc`
- `os`
- `time`

The DMA implementation additionally uses:

- `rp2`
- `machine.mem32`
- `machine.freq`

The accelerated modules use:

- `micropython.viper`

## Recommended module dependencies

| Feature | Required modules |
|---|---|
| Basic display | `nokia_display.py` |
| Buffered drawing | `nokia_display.py` |
| Memory-managed graphics | `nokia_display.py`, `nokia_graphics.py` |
| Advanced 2D shapes | `nokia_graphics.py`, `nokia_shapes.py` |
| 2D acceleration | `nokia_shapes_fast.py` |
| Custom fonts | `nokia_font.py` |
| Font acceleration | `nokia_font_fast.py` |
| Text animations | `nokia_font.py`, `nokia_text_motion.py` |
| 3D graphics | `nokia_graphics.py`, `nokia_shapes.py`, `nokia_3d.py` |
| SPI DMA | `nokia_display.py`, `nokia_dma_link.py` |
| PIO DMA | `nokia_display.py`, `nokia_dma_link.py` |

Fast helper modules are optional. The corresponding main modules provide slower Python implementations when acceleration is unavailable.

---

# 3. Colour System and Constants

The display uses RGB565 colour format.

Each pixel contains 16 bits:

- Red: 5 bits
- Green: 6 bits
- Blue: 5 bits

## 3.1 Built-in Colour Constants

These constants are defined in `nokia_display.py`.

| Constant | Hexadecimal | Colour |
|---|---|---|
| `RED` | `0xF800` | Red |
| `GREEN` | `0x07E0` | Green |
| `BLUE` | `0x001F` | Blue |
| `YELLOW` | `0xFFE0` | Yellow |
| `CYAN` | `0x07FF` | Cyan |
| `MAGENTA` | `0xF81F` | Magenta |
| `WHITE` | `0xFFFF` | White |
| `BLACK` | `0x0000` | Black |

Import example:

    from nokia_display import RED, GREEN, BLUE, WHITE, BLACK

## 3.2 make_colour()

**Module:** `nokia_display.py`

Convert separate RGB values into a 16-bit RGB565 colour.

### Function

    make_colour(red, green, blue)

### Parameters

| Parameter | Description |
|---|---|
| `red` | Red intensity, 0–255 |
| `green` | Green intensity, 0–255 |
| `blue` | Blue intensity, 0–255 |

### Returns

A 16-bit RGB565 colour value.

### Example

    from nokia_display import make_colour

    ORANGE = make_colour(255, 165, 0)
    PURPLE = make_colour(128, 0, 128)
    CUSTOM_BLUE = make_colour(0, 100, 255)

Use the returned value in any drawing function that accepts a colour.

---

# 4. Display Rotation Constants

**Module:** `nokia_display.py`

The display supports four orientations.

| Constant | Value | Orientation |
|---|---:|---|
| `PORTRAIT_FLEX_CABLE_AT_TOP` | 0 | Portrait |
| `SIDEWAYS_FLEX_CABLE_ON_LEFT` | 1 | Landscape |
| `PORTRAIT_FLEX_CABLE_AT_BOTTOM` | 2 | Upside-down portrait |
| `SIDEWAYS_FLEX_CABLE_ON_RIGHT` | 3 | Opposite landscape |

Shorter aliases are also available:

| Alias | Original Constant |
|---|---|
| `PORTRAIT` | `PORTRAIT_FLEX_CABLE_AT_TOP` |
| `LANDSCAPE_FLEX_CABLE_ON_LEFT` | `SIDEWAYS_FLEX_CABLE_ON_LEFT` |
| `PORTRAIT_UPSIDE_DOWN` | `PORTRAIT_FLEX_CABLE_AT_BOTTOM` |
| `LANDSCAPE_FLEX_CABLE_ON_RIGHT` | `SIDEWAYS_FLEX_CABLE_ON_RIGHT` |

### Display dimensions

| Orientation | Width | Height |
|---|---:|---:|
| Portrait | 128 | 160 |
| Landscape | 160 | 128 |

These values are also available through the `width` and `height` attributes of the display.

---

# 5. nokia_display.py – Core Display API

This module provides direct access to the display controller.

It handles:

- Display initialisation.
- Hardware communication.
- Rotation.
- Pixel transmission.
- Basic drawing.
- Raw image display.
- Built-in MicroPython text rendering.

## 5.1 Display Class

### Constructor

    Display(
        clock_pin_number,
        data_pin_number,
        select_pin_number,
        reset_pin_number,
        rotation=PORTRAIT_FLEX_CABLE_AT_TOP,
        mirrored=False
    )

### Description

Creates a display-control object.

### Parameters

| Parameter | Description |
|---|---|
| `clock_pin_number` | GPIO pin connected to display clock |
| `data_pin_number` | GPIO pin connected to display data |
| `select_pin_number` | GPIO pin connected to chip select |
| `reset_pin_number` | GPIO pin connected to display reset |
| `rotation` | Initial display orientation |
| `mirrored` | Enable horizontal mirroring |

### Example

    from nokia_display import Display, PORTRAIT

    display = Display(
        clock_pin_number=GP_CLOCK,
        data_pin_number=GP_DATA,
        select_pin_number=GP_SELECT,
        reset_pin_number=GP_RESET,
        rotation=PORTRAIT
    )

Replace the GPIO placeholders with the actual GPIO numbers used by the hardware.

---

## 5.2 Display.start()

### Function

    display.start()

### Description

Initialises the physical display.

The function performs:

1. Hardware reset.
2. Software reset.
3. Sleep-out command.
4. Display pixel-format configuration.
5. Rotation configuration.
6. Display-on command.

### Parameters

None.

### Returns

None.

### Important

Call this function before drawing anything.

---

## 5.3 Display.send_command()

### Function

    display.send_command(command_value, data_values=())

### Description

Sends a command directly to the display controller.

This is a low-level API intended for controller configuration and advanced display operations.

### Parameters

| Parameter | Description |
|---|---|
| `command_value` | Display-controller command byte |
| `data_values` | Optional iterable containing command data bytes |

### Returns

None.

### Example

    display.send_command(0x29)

The command values are controller-specific.

---

## 5.4 Display.use_hardware_spi()

### Function

    display.use_hardware_spi(
        baudrate=16000000,
        spi_number=0
    )

### Description

Switches display communication to hardware SPI.

Hardware SPI is considerably faster than bit-banging.

### Parameters

| Parameter | Default | Description |
|---|---:|---|
| `baudrate` | 16000000 | Requested SPI speed in Hz |
| `spi_number` | 0 | MicroPython SPI peripheral number |

### Returns

None.

### Example

    display.use_hardware_spi()

Custom speed:

    display.use_hardware_spi(24000000)

### Important

The source documents a maximum practical SPI clock of 24 MHz on the target board, regardless of a higher requested value.

The selected GPIO pins must be compatible with the chosen SPI peripheral.

---

## 5.5 Display.use_bit_banging()

### Function

    display.use_bit_banging()

### Description

Returns communication to the simple software-controlled bit-banging method.

### Parameters

None.

### Returns

None.

### Example

    display.use_bit_banging()

Use this when hardware SPI is unavailable or when returning to the simple communication method.

---

## 5.6 Display.use_spi_dma()

### Function

    display.use_spi_dma(baudrate=24000000)

### Description

Enables hardware SPI communication using DMA for pixel transmission.

The CPU can prepare additional data while DMA transfers the current data.

### Parameters

| Parameter | Default | Description |
|---|---:|---|
| `baudrate` | 24000000 | Requested SPI speed in Hz |

### Returns

None.

### Example

    display.use_spi_dma()

Custom speed:

    display.use_spi_dma(20000000)

### Requirements

Requires:

    nokia_dma_link.py

### Important

- Uses hardware SPI.
- Pixel data is packed before transmission.
- Commands continue to use the normal SPI command path.
- Has the same practical SPI speed limit as `use_hardware_spi()`.

---

## 5.7 Display.use_pio_dma()

### Function

    display.use_pio_dma(
        bit_clock_hz=62500000,
        command_delay_microseconds=0
    )

### Description

Enables PIO-based DMA transmission.

Raw pixel bytes are transferred directly from the screen buffer without the normal SPI packing process.

### Parameters

| Parameter | Default | Description |
|---|---:|---|
| `bit_clock_hz` | 62500000 | PIO bit-clock frequency in Hz |
| `command_delay_microseconds` | 0 | Delay used when sending commands through bit-banging |

### Returns

None.

### Example

    display.use_pio_dma(62500000)

Alternative command delay:

    display.use_pio_dma(
        bit_clock_hz=62500000,
        command_delay_microseconds=3
    )

### Requirements

Requires:

    nokia_dma_link.py

### Important

- Designed for use with `Screen`.
- Sends raw RGB565 pixel data.
- The CPU is free while DMA transfers the frame.
- Commands are sent using bit-banging.
- The source documents successful operation on the Nokia display from 25 MHz to 75 MHz.
- The requested PIO clock must also satisfy the hardware clock-frequency check in the implementation.
- Direct drawing methods on `Display` do not use the raw-pixel PIO path in the same way as `Screen`.

---

## 5.8 Display.pixel_backend

### Property

    display.pixel_backend

### Description

Returns the currently selected pixel-transmission method.

### Possible values

Examples include:

    "bit-banging"

    "hardware SPI"

    "SPI + DMA"

    "PIO + DMA 62.5 MHz"

### Usage

    print(display.pixel_backend)

This is a read-only property.

---

## 5.9 Display.set_rotation()

### Function

    display.set_rotation(rotation, mirrored=False)

### Description

Changes the display orientation while the program is running.

### Parameters

| Parameter | Description |
|---|---|
| `rotation` | One of the four rotation constants |
| `mirrored` | Enables horizontal mirroring |

### Example

    from nokia_display import LANDSCAPE_FLEX_CABLE_ON_LEFT

    display.set_rotation(LANDSCAPE_FLEX_CABLE_ON_LEFT)

Enable mirroring:

    display.set_rotation(
        LANDSCAPE_FLEX_CABLE_ON_LEFT,
        mirrored=True
    )

### Important

The dimensions may change after rotation.

Always read:

    display.width
    display.height

again after changing the orientation.

The existing picture is not redrawn automatically.

---

## 5.10 Display.rotation

### Property

    display.rotation

### Description

Returns the currently selected rotation number.

Possible values:

    0, 1, 2, 3

---

## 5.11 Display.mirrored

### Property

    display.mirrored

### Description

Returns:

- `True` when horizontal mirroring is enabled.
- `False` when mirroring is disabled.

---

## 5.12 Display.is_landscape

### Property

    display.is_landscape

### Description

Returns whether the current display orientation is landscape.

Returns a Boolean value.

---

## 5.13 Display.width and Display.height

These public attributes provide the current display dimensions.

Portrait:

    display.width   # 128
    display.height  # 160

Landscape:

    display.width   # 160
    display.height  # 128

---

## 5.14 Display.bit_delay_microseconds

### Attribute

    display.bit_delay_microseconds

### Description

Controls the software bit-banging delay in microseconds.

The initial value is:

    3

### Example

    display.bit_delay_microseconds = 3

The PIO DMA implementation temporarily changes this value for command transmission and restores it when closed.

---

## 5.15 Display.set_window()

### Function

    display.set_window(
        x_start,
        y_start,
        x_end,
        y_end
    )

### Description

Selects the rectangular region of display memory to receive pixel data.

### Parameters

| Parameter | Description |
|---|---|
| `x_start` | First horizontal coordinate |
| `y_start` | First vertical coordinate |
| `x_end` | Last horizontal coordinate |
| `y_end` | Last vertical coordinate |

### Important

The ending coordinates are inclusive.

This is a low-level function. Most applications should use the higher-level drawing functions instead.

---

## 5.16 Display.fill_screen()

### Function

    display.fill_screen(colour)

### Description

Fills the complete physical display with one colour.

### Parameters

| Parameter | Description |
|---|---|
| `colour` | RGB565 colour |

### Example

    display.fill_screen(BLACK)

---

## 5.17 Display.draw_pixel()

### Function

    display.draw_pixel(x, y, colour)

### Description

Draws one pixel.

### Parameters

| Parameter | Description |
|---|---|
| `x` | Horizontal coordinate |
| `y` | Vertical coordinate |
| `colour` | RGB565 colour |

### Example

    display.draw_pixel(40, 50, RED)

Pixels outside the screen are ignored.

---

## 5.18 Display.fill_rectangle()

### Function

    display.fill_rectangle(
        x,
        y,
        width,
        height,
        colour
    )

### Description

Draws a filled rectangle.

### Parameters

| Parameter | Description |
|---|---|
| `x` | Top-left horizontal coordinate |
| `y` | Top-left vertical coordinate |
| `width` | Rectangle width |
| `height` | Rectangle height |
| `colour` | RGB565 colour |

### Example

    display.fill_rectangle(10, 20, 50, 30, BLUE)

Parts outside the display are clipped automatically.

---

## 5.19 Display.draw_rectangle()

### Function

    display.draw_rectangle(
        x,
        y,
        width,
        height,
        colour
    )

### Description

Draws a one-pixel-thick rectangle outline.

### Example

    display.draw_rectangle(10, 20, 80, 50, WHITE)

---

## 5.20 Display.draw_line()

### Function

    display.draw_line(
        x_start,
        y_start,
        x_end,
        y_end,
        colour
    )

### Description

Draws a straight line between two coordinates.

### Parameters

| Parameter | Description |
|---|---|
| `x_start` | Starting X coordinate |
| `y_start` | Starting Y coordinate |
| `x_end` | Ending X coordinate |
| `y_end` | Ending Y coordinate |
| `colour` | RGB565 colour |

### Example

    display.draw_line(0, 0, 127, 159, RED)

---

## 5.21 Display.draw_circle()

### Function

    display.draw_circle(
        centre_x,
        centre_y,
        radius,
        colour
    )

### Description

Draws a one-pixel-thick circle outline.

### Example

    display.draw_circle(64, 80, 30, GREEN)

---

## 5.22 Display.fill_circle()

### Function

    display.fill_circle(
        centre_x,
        centre_y,
        radius,
        colour
    )

### Description

Draws a solid circle.

### Example

    display.fill_circle(64, 80, 30, BLUE)

---

## 5.23 Display.show_image_file()

### Function

    display.show_image_file(
        filename,
        x=0,
        y=0,
        width=None,
        height=None
    )

### Description

Displays a raw RGB565 image from a file.

### Parameters

| Parameter | Description |
|---|---|
| `filename` | Image file path |
| `x` | Destination X coordinate |
| `y` | Destination Y coordinate |
| `width` | Image width |
| `height` | Image height |

### Example

    display.show_image_file(
        "logo.raw",
        x=0,
        y=0,
        width=128,
        height=160
    )

### Image format

- 16 bits per pixel.
- RGB565.
- High byte first.
- Two bytes per pixel.

The file must contain exactly:

    width * height * 2

bytes.

The image must fit entirely inside the display. Otherwise, a `ValueError` is raised.

When width and height are omitted, the image is expected to cover the complete display.

---

## 5.24 Display.measure_text()

### Function

    display.measure_text(text, scale=1)

### Description

Measures text using the built-in 8 × 8 MicroPython font.

### Parameters

| Parameter | Default | Description |
|---|---:|---|
| `text` | Required | Text to measure |
| `scale` | 1 | Text enlargement factor |

### Returns

A tuple:

    (width, height)

### Example

    size = display.measure_text("Hello", scale=1)

    text_width = size[0]
    text_height = size[1]

Each character occupies 8 × 8 pixels at scale 1.

At scale 2, each character occupies 16 × 16 pixels.

---

## 5.25 Display.draw_text()

### Function

    display.draw_text(
        text,
        x,
        y,
        colour,
        background_colour=None,
        scale=1
    )

### Description

Draws text using the built-in MicroPython font.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `text` | Required | Text to draw |
| `x` | Required | Top-left X coordinate |
| `y` | Required | Top-left Y coordinate |
| `colour` | Required | Text colour |
| `background_colour` | `None` | Optional background colour |
| `scale` | 1 | Text enlargement |

### Example

    display.draw_text(
        "Hello Pico",
        10,
        20,
        WHITE
    )

Larger text:

    display.draw_text(
        "HELLO",
        10,
        40,
        RED,
        scale=2
    )

New lines:

    display.draw_text(
        "Line 1\nLine 2",
        10,
        60,
        GREEN
    )

When `background_colour=None`, the existing picture underneath the text remains visible.

---

# 6. nokia_display.py – BufferedDisplay API

`BufferedDisplay` is an alternative drawing interface that uses a full-screen memory buffer.

Instead of sending every drawing operation immediately to the display, it first draws into RAM.

The image is transferred when `show()` is called.

## 6.1 Constructor

    BufferedDisplay(display, use_fast_helpers=True)

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `display` | Required | Existing Display object |
| `use_fast_helpers` | `True` | Enable optional `nokia_fast.py` |

### Example

    from nokia_display import Display, BufferedDisplay

    display = Display(6, 7, 5, 4)
    display.start()
    display.use_hardware_spi()

    screen = BufferedDisplay(display)

---

## 6.2 Public Attributes

| Attribute | Description |
|---|---|
| `width` | Current buffer width |
| `height` | Current buffer height |
| `fast_helpers_in_use` | Whether accelerated helpers are active |

The constructor allocates full-screen buffers in RAM.

---

## 6.3 BufferedDisplay.fill_screen()

    screen.fill_screen(colour)

Fills the memory buffer with one colour.

The physical display is updated when `show()` is called.

---

## 6.4 BufferedDisplay.draw_pixel()

    screen.draw_pixel(x, y, colour)

Draws one pixel into the memory buffer.

---

## 6.5 BufferedDisplay.fill_rectangle()

    screen.fill_rectangle(x, y, width, height, colour)

Draws a filled rectangle into the memory buffer.

---

## 6.6 BufferedDisplay.draw_rectangle()

    screen.draw_rectangle(x, y, width, height, colour)

Draws a rectangle outline into the memory buffer.

---

## 6.7 BufferedDisplay.draw_line()

    screen.draw_line(
        x_start,
        y_start,
        x_end,
        y_end,
        colour
    )

Draws a line into the memory buffer.

---

## 6.8 BufferedDisplay.draw_circle()

    screen.draw_circle(
        centre_x,
        centre_y,
        radius,
        colour
    )

Draws a circle outline.

---

## 6.9 BufferedDisplay.fill_circle()

    screen.fill_circle(
        centre_x,
        centre_y,
        radius,
        colour
    )

Draws a filled circle.

---

## 6.10 BufferedDisplay.measure_text()

    screen.measure_text(text, scale=1)

Returns:

    (width, height)

Uses the built-in display font.

---

## 6.11 BufferedDisplay.draw_text()

    screen.draw_text(
        text,
        x,
        y,
        colour,
        background_colour=None,
        scale=1
    )

Draws built-in-font text into the memory buffer.

Parameters and behaviour are the same as `Display.draw_text()`.

---

## 6.12 BufferedDisplay.load_image_file()

    screen.load_image_file(
        filename,
        x=0,
        y=0,
        width=None,
        height=None
    )

Loads a raw RGB565 image file into the memory buffer.

Parameters:

| Parameter | Description |
|---|---|
| `filename` | Raw image path |
| `x` | Destination X |
| `y` | Destination Y |
| `width` | Image width |
| `height` | Image height |

The image must:

- Use RGB565 format.
- Store the high byte first.
- Contain exactly two bytes per pixel.
- Fit entirely inside the buffer.

---

## 6.13 BufferedDisplay.show()

    screen.show(full=False)

Sends the buffered picture to the physical display.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `full` | `False` | Force full-screen transmission |

### Normal operation

    screen.show()

Only rows detected as changed are transmitted.

### Force a complete update

    screen.show(full=True)

### Important

`BufferedDisplay` uses full-screen buffers. It does not provide the low-memory strip-rendering system available in `nokia_graphics.Screen`.

---

# 7. nokia_graphics.py – Screen and Memory Management API

This module provides the main memory-managed drawing system.

It is designed to work within a specified RAM budget.

It supports three rendering modes:

1. Full buffer with change tracking.
2. Full buffer.
3. Strips.

## 7.1 Rendering Mode Constants

| Constant | Description |
|---|---|
| `MODE_FULL_BUFFER_WITH_CHANGE_TRACKING` | Keeps the current frame and previous frame to detect changed rows |
| `MODE_FULL_BUFFER` | Keeps the complete picture and transmits the complete frame |
| `MODE_STRIPS` | Draws and sends the display in smaller horizontal bands |

Default RAM budget:

    DEFAULT_BUDGET_BYTES = 100 * 1024

---

## 7.2 plan_memory()

### Function

    plan_memory(
        width,
        height,
        budget_bytes,
        reserve_bytes=0
    )

### Description

Calculates which rendering modes can fit inside a given memory budget.

### Parameters

| Parameter | Description |
|---|---|
| `width` | Display width |
| `height` | Display height |
| `budget_bytes` | Total memory budget |
| `reserve_bytes` | Memory reserved for fonts, 3D objects and other features |

### Returns

A list of tuples:

    (mode, rows_in_buffer, planned_bytes)

The available modes are returned in preferred order:

1. Full buffer with change tracking.
2. Full buffer.
3. Strips.

If no mode fits, an empty list is returned.

### Example

    from nokia_graphics import plan_memory

    plans = plan_memory(
        width=128,
        height=160,
        budget_bytes=100 * 1024,
        reserve_bytes=10000
    )

    print(plans)

---

## 7.3 Screen Class

### Constructor

    Screen(
        display,
        budget_bytes=DEFAULT_BUDGET_BYTES,
        reserve_bytes=0,
        mode=None,
        use_fast_helpers=True
    )

### Description

Creates a memory-managed drawing surface.

The screen automatically selects a suitable rendering mode when `mode=None`.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `display` | Required | Started Display object |
| `budget_bytes` | 100 KB | Maximum RAM budget for this screen |
| `reserve_bytes` | 0 | RAM reserved for other features |
| `mode` | `None` | Automatic selection or forced rendering mode |
| `use_fast_helpers` | `True` | Enable optional `nokia_fast.py` helpers |

### Important requirement

Before constructing `Screen`, initialise the display and enable a fast pixel backend.

Example:

    display.start()
    display.use_hardware_spi()

    screen = Screen(display)

The constructor raises `RuntimeError` when no SPI or DMA backend has been configured.

---

## 7.4 Screen Public Attributes

| Attribute | Description |
|---|---|
| `width` | Current screen width |
| `height` | Current screen height |
| `mode` | Selected rendering mode |
| `strip_height` | Number of rows allocated to the buffer |
| `passes_per_frame` | Number of strip passes needed per frame |
| `budget_bytes` | Configured memory budget |
| `reserve_bytes` | Reserved memory |
| `memory_planned_bytes` | Estimated planned memory |
| `memory_used_bytes` | Measured memory used |
| `background_sending` | Controls background PIO DMA sending |
| `fast_helpers_in_use` | Whether `nokia_fast.py` is active |

Example:

    print(screen.width)
    print(screen.height)
    print(screen.mode)

    print(screen.memory_used_bytes)
    print(screen.memory_planned_bytes)

---

## 7.5 Screen.rotation

    screen.rotation

Returns the current display rotation.

Read-only property.

---

## 7.6 Screen.mirrored

    screen.mirrored

Returns whether horizontal mirroring is enabled.

Read-only property.

---

## 7.7 Screen.is_landscape

    screen.is_landscape

Returns `True` when the current screen is landscape.

---

## 7.8 Screen.set_rotation()

    screen.set_rotation(rotation, mirrored=False)

Changes the display orientation and rebuilds the screen buffers.

### Parameters

| Parameter | Description |
|---|---|
| `rotation` | One of the four display rotation constants |
| `mirrored` | Enable horizontal mirroring |

### Example

    screen.set_rotation(
        LANDSCAPE_FLEX_CABLE_ON_LEFT
    )

### Important

This operation:

- Waits for any background transmission to finish.
- Changes the physical display rotation.
- Reallocates the screen buffers.
- Updates the screen dimensions.
- Clears the display.
- Notifies registered rotation listeners.

Any objects that depend on the old dimensions may need to be recreated.

---

## 7.9 Screen.rotate_clockwise()

    screen.rotate_clockwise()

Rotates the display by one quarter-turn clockwise.

---

## 7.10 Screen.rotate_anticlockwise()

    screen.rotate_anticlockwise()

Rotates the display by one quarter-turn anticlockwise.

---

## 7.11 Screen.add_rotation_listener()

    screen.add_rotation_listener(function)

Registers a callback that is called after every successful `set_rotation()`.

### Parameter

| Parameter | Description |
|---|---|
| `function` | Function accepting one argument: the updated Screen object |

### Example

    def on_rotation_changed(screen):
        print("New size:", screen.width, screen.height)

    screen.add_rotation_listener(on_rotation_changed)

`Shapes` uses this facility internally to update its references after screen rotation.

---

## 7.12 Screen.memory_report()

    screen.memory_report()

Returns a text report containing:

- Pixel transmission backend.
- Selected drawing mode.
- Buffer rows.
- Passes per frame.
- Memory budget.
- Reserved memory.
- Planned memory.
- Measured memory.
- Free RAM, when supported by MicroPython.

### Example

    print(screen.memory_report())

---

## 7.13 Screen.render()

### Function

    screen.render(draw_scene, background=None)

### Description

Draws and transmits one complete frame.

This is the recommended rendering API.

### Parameters

| Parameter | Description |
|---|---|
| `draw_scene` | Function receiving the Screen object |
| `background` | Optional RGB565 background colour |

### Example

    def draw_scene(screen):
        screen.fill_screen(BLACK)
        screen.draw_pixel(30, 30, RED)
        screen.fill_circle(64, 80, 20, GREEN)

    screen.render(
        draw_scene,
        background=BLACK
    )

### Important rendering behaviour

In full-buffer modes:

- The drawing function runs once.
- The complete frame is available in memory.
- Changed rows can be detected and sent.

In strips mode:

- The drawing function runs once for each horizontal band.
- Only the currently selected band exists in the screen buffer.
- The same complete scene must be drawn on every pass.

For this reason, the drawing function should not depend on changing external state during rendering.

In strips mode, provide `background` or explicitly draw every pixel area that must be refreshed.

---

## 7.14 Screen.fill_screen()

    screen.fill_screen(colour)

Fills the screen buffer with one RGB565 colour.

The picture is sent according to the selected rendering mode.

---

## 7.15 Screen.draw_pixel()

    screen.draw_pixel(x, y, colour)

Draws one pixel into the screen buffer.

---

## 7.16 Screen.fill_rectangle()

    screen.fill_rectangle(
        x,
        y,
        width,
        height,
        colour
    )

Draws a filled rectangle into the screen buffer.

---

## 7.17 Screen.draw_rectangle()

    screen.draw_rectangle(
        x,
        y,
        width,
        height,
        colour
    )

Draws a rectangle outline.

---

## 7.18 Screen.draw_line()

    screen.draw_line(
        x_start,
        y_start,
        x_end,
        y_end,
        colour
    )

Draws a line between two points.

---

## 7.19 Screen.draw_circle()

    screen.draw_circle(
        centre_x,
        centre_y,
        radius,
        colour
    )

Draws a circle outline.

---

## 7.20 Screen.fill_circle()

    screen.fill_circle(
        centre_x,
        centre_y,
        radius,
        colour
    )

Draws a filled circle.

---

## 7.21 Screen.measure_text()

    screen.measure_text(text, scale=1)

Measures text using the built-in 8 × 8 MicroPython font.

Returns:

    (width, height)

---

## 7.22 Screen.draw_text()

    screen.draw_text(
        text,
        x,
        y,
        colour,
        background_colour=None,
        scale=1
    )

Draws text using the built-in font.

Supports:

- Multiple lines.
- Text scaling.
- Optional background colour.

This is not the same as the custom-font API in `nokia_font.py`.

---

## 7.23 Screen.draw_image_file()

    screen.draw_image_file(
        filename,
        x=0,
        y=0,
        width=None,
        height=None
    )

Draws a raw RGB565 image into the screen buffer.

### Parameters

| Parameter | Description |
|---|---|
| `filename` | Raw image file |
| `x` | Destination X |
| `y` | Destination Y |
| `width` | Image width |
| `height` | Image height |

The file must contain exactly:

    width * height * 2

bytes.

The image must fit entirely inside the screen.

### Special strips behaviour

In strips mode, only the rows belonging to the current strip are read from the image file.

---

## 7.24 Screen.show()

    screen.show(full=False, wait=False)

Transmits the current buffered picture.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `full` | `False` | Force the complete image to be sent |
| `wait` | `False` | Wait for any background transmission to finish |

### Example

    screen.show()

Force complete update:

    screen.show(full=True)

Wait for transfer completion:

    screen.show(wait=True)

### Important

`show()` is unavailable in strips mode.

Use:

    screen.render(draw_scene, background=BLACK)

for strips-mode rendering.

With PIO DMA, transmission may continue in the background.

---

## 7.25 Screen.wait_until_sent()

    screen.wait_until_sent()

Waits until a background image transmission has finished.

### Example

    screen.show()
    screen.wait_until_sent()

Does nothing when no background transmission is active.

---

## 7.26 Screen.background_sending

### Attribute

    screen.background_sending

Controls background sending for the PIO DMA full-buffer-with-change-tracking path.

Default:

    True

Disable background sending:

    screen.background_sending = False

This does not change the selected drawing mode.

---

# 8. nokia_shapes.py – 2D Shapes API

This module provides advanced drawing operations.

It works with the memory-managed `Screen` object.

Import:

    from nokia_shapes import Shapes

Create one Shapes object:

    shapes = Shapes(screen)

The Shapes object draws directly into the Screen buffer.

It supports:

- Clipping.
- Thick lines.
- Polylines.
- Polygons.
- Triangles.
- Regular polygons.
- Stars.
- Ellipses.
- Circles.
- Rings.
- Arcs.
- Pie slices.
- Rounded rectangles.
- Sprites.

## 8.1 Shapes Constructor

    Shapes(
        screen,
        use_fast_helpers=True,
        _fast_module=None
    )

### Parameters

| Parameter | Description |
|---|---|
| `screen` | Screen object from `nokia_graphics.py` |
| `use_fast_helpers` | Enable optional shape acceleration |
| `_fast_module` | Internal helper-module override |

The `_fast_module` argument is an internal implementation option and is not normally needed by applications.

### Example

    shapes = Shapes(screen)

---

## 8.2 Shapes.memory_bytes()

    shapes.memory_bytes()

Returns an estimate of the RAM used by the Shapes working lists.

It does not include the shared sine table.

---

## 8.3 Shapes.set_clip()

    shapes.set_clip(x, y, width, height)

Restricts Shapes drawing operations to a rectangular area.

### Parameters

| Parameter | Description |
|---|---|
| `x` | Clip rectangle left |
| `y` | Clip rectangle top |
| `width` | Clip rectangle width |
| `height` | Clip rectangle height |

### Example

    shapes.set_clip(10, 10, 100, 80)

All subsequent Shapes drawing calls are clipped to that rectangle.

Important:

The clipping setting affects `Shapes` drawing operations only.

It does not automatically affect:

- Screen drawing methods.
- Font drawing methods.

---

## 8.4 Shapes.clear_clip()

    shapes.clear_clip()

Removes the clipping rectangle.

Drawing is allowed across the complete screen again.

---

## 8.5 Shapes.draw_line()

    shapes.draw_line(
        x_start,
        y_start,
        x_end,
        y_end,
        colour,
        thickness=1,
        round_caps=False
    )

Draws a line with configurable thickness.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `x_start` | Required | Starting X |
| `y_start` | Required | Starting Y |
| `x_end` | Required | Ending X |
| `y_end` | Required | Ending Y |
| `colour` | Required | RGB565 colour |
| `thickness` | 1 | Line thickness in pixels |
| `round_caps` | `False` | Round the line ends |

### Example

    shapes.draw_line(10, 10, 100, 80, RED)

Thick line:

    shapes.draw_line(
        10, 40,
        110, 40,
        GREEN,
        thickness=5,
        round_caps=True
    )

Odd thicknesses such as 3, 5 and 7 generally give the neatest result.

---

## 8.6 Shapes.draw_polyline()

    shapes.draw_polyline(
        points,
        colour,
        thickness=1,
        closed=False
    )

Draws connected lines through a collection of points.

### Parameters

| Parameter | Description |
|---|---|
| `points` | Sequence of `(x, y)` coordinate pairs |
| `colour` | RGB565 colour |
| `thickness` | Line thickness |
| `closed` | Whether the last point connects to the first |

### Example

    points = (
        (10, 10),
        (40, 20),
        (70, 10),
        (100, 50)
    )

    shapes.draw_polyline(
        points,
        WHITE,
        thickness=3,
        closed=False
    )

Joints are rounded when thickness is 3 or greater.

---

## 8.7 Shapes.fill_polygon()

    shapes.fill_polygon(points, colour)

Fills a polygon.

### Parameters

| Parameter | Description |
|---|---|
| `points` | Sequence of `(x, y)` vertices |
| `colour` | RGB565 fill colour |

### Example

    triangle = (
        (64, 10),
        (110, 100),
        (20, 100)
    )

    shapes.fill_polygon(triangle, RED)

Supports concave polygons.

If polygon edges cross, the crossing region is left empty according to the implementation's filling rule.

---

## 8.8 Shapes.fill_polygon_flat()

    shapes.fill_polygon_flat(
        coordinates,
        corner_count,
        colour
    )

Fast alternative to `fill_polygon()`.

### Parameters

| Parameter | Description |
|---|---|
| `coordinates` | Flat `array('i')` containing alternating X and Y values |
| `corner_count` | Number of polygon corners |
| `colour` | RGB565 fill colour |

### Expected coordinate structure

    x0, y0, x1, y1, x2, y2, ...

### Example

    import array

    coordinates = array.array(
        'i',
        [64, 10, 110, 100, 20, 100]
    )

    shapes.fill_polygon_flat(
        coordinates,
        3,
        GREEN
    )

Only the first `corner_count` coordinate pairs are used.

---

## 8.9 Shapes.draw_polygon()

    shapes.draw_polygon(
        points,
        colour,
        thickness=1
    )

Draws a polygon outline.

The final vertex connects to the first vertex.

### Example

    points = (
        (20, 20),
        (100, 20),
        (80, 90),
        (30, 100)
    )

    shapes.draw_polygon(points, WHITE, thickness=2)

---

## 8.10 Shapes.fill_triangle()

    shapes.fill_triangle(
        x0, y0,
        x1, y1,
        x2, y2,
        colour
    )

Draws a filled triangle.

### Example

    shapes.fill_triangle(
        64, 10,
        110, 100,
        20, 100,
        RED
    )

---

## 8.11 Shapes.draw_triangle()

    shapes.draw_triangle(
        x0, y0,
        x1, y1,
        x2, y2,
        colour,
        thickness=1
    )

Draws a triangle outline.

### Example

    shapes.draw_triangle(
        64, 10,
        110, 100,
        20, 100,
        WHITE,
        thickness=2
    )

---

## 8.12 Shapes.fill_regular_polygon()

    shapes.fill_regular_polygon(
        centre_x,
        centre_y,
        radius,
        sides,
        colour,
        rotation_degrees=0
    )

Draws a filled regular polygon.

### Parameters

| Parameter | Description |
|---|---|
| `centre_x` | Centre X |
| `centre_y` | Centre Y |
| `radius` | Distance from centre to vertices |
| `sides` | Number of polygon sides |
| `colour` | Fill colour |
| `rotation_degrees` | Rotation in degrees |

### Example

    shapes.fill_regular_polygon(
        64, 80,
        40,
        6,
        BLUE
    )

Possible shapes:

- 3 sides: Triangle
- 4 sides: Square
- 5 sides: Pentagon
- 6 sides: Hexagon

For regular polygons and stars, rotation 0 places the first point straight up.

---

## 8.13 Shapes.draw_regular_polygon()

    shapes.draw_regular_polygon(
        centre_x,
        centre_y,
        radius,
        sides,
        colour,
        rotation_degrees=0,
        thickness=1
    )

Draws the outline of a regular polygon.

### Example

    shapes.draw_regular_polygon(
        64, 80,
        40,
        6,
        GREEN,
        rotation_degrees=15,
        thickness=2
    )

---

## 8.14 Shapes.fill_star()

    shapes.fill_star(
        centre_x,
        centre_y,
        outer_radius,
        inner_radius,
        point_count,
        colour,
        rotation_degrees=0
    )

Draws a filled star.

### Parameters

| Parameter | Description |
|---|---|
| `centre_x` | Star centre X |
| `centre_y` | Star centre Y |
| `outer_radius` | Outer point radius |
| `inner_radius` | Inner point radius |
| `point_count` | Number of star points |
| `colour` | Fill colour |
| `rotation_degrees` | Rotation |

### Example

    shapes.fill_star(
        64, 80,
        40, 18,
        5,
        YELLOW
    )

---

## 8.15 Shapes.draw_star()

    shapes.draw_star(
        centre_x,
        centre_y,
        outer_radius,
        inner_radius,
        point_count,
        colour,
        rotation_degrees=0,
        thickness=1
    )

Draws a star outline.

### Example

    shapes.draw_star(
        64, 80,
        40, 18,
        5,
        WHITE,
        thickness=2
    )

---

## 8.16 Shapes.fill_ellipse()

    shapes.fill_ellipse(
        centre_x,
        centre_y,
        radius_x,
        radius_y,
        colour
    )

Draws a filled ellipse.

### Parameters

| Parameter | Description |
|---|---|
| `centre_x` | Centre X |
| `centre_y` | Centre Y |
| `radius_x` | Horizontal radius |
| `radius_y` | Vertical radius |
| `colour` | Fill colour |

### Example

    shapes.fill_ellipse(
        64, 80,
        40, 20,
        BLUE
    )

---

## 8.17 Shapes.draw_ellipse()

    shapes.draw_ellipse(
        centre_x,
        centre_y,
        radius_x,
        radius_y,
        colour
    )

Draws an ellipse outline.

### Example

    shapes.draw_ellipse(
        64, 80,
        40, 20,
        WHITE
    )

---

## 8.18 Shapes.fill_circle()

    shapes.fill_circle(
        centre_x,
        centre_y,
        radius,
        colour
    )

Draws a filled circle.

This is the advanced Shapes implementation and supports Shapes clipping.

---

## 8.19 Shapes.draw_circle()

    shapes.draw_circle(
        centre_x,
        centre_y,
        radius,
        colour
    )

Draws a circle outline.

---

## 8.20 Shapes.fill_ring()

    shapes.fill_ring(
        centre_x,
        centre_y,
        outer_radius,
        inner_radius,
        colour
    )

Draws a filled ring, also known as a donut shape.

### Parameters

| Parameter | Description |
|---|---|
| `centre_x` | Centre X |
| `centre_y` | Centre Y |
| `outer_radius` | Outside radius |
| `inner_radius` | Inside radius |
| `colour` | Ring colour |

### Example

    shapes.fill_ring(
        64, 80,
        40, 20,
        CYAN
    )

The area inside the inner circle remains empty.

---

## 8.21 Shapes.draw_arc()

    shapes.draw_arc(
        centre_x,
        centre_y,
        radius,
        start_degrees,
        end_degrees,
        colour,
        thickness=1
    )

Draws part of a circle.

### Parameters

| Parameter | Description |
|---|---|
| `centre_x` | Centre X |
| `centre_y` | Centre Y |
| `radius` | Arc radius |
| `start_degrees` | Starting angle |
| `end_degrees` | Ending angle |
| `colour` | Arc colour |
| `thickness` | Arc thickness |

### Example

    shapes.draw_arc(
        64, 80,
        40,
        0, 270,
        RED,
        thickness=4
    )

### Angle convention

- 0° points right.
- 90° points down.
- 180° points left.
- 270° points up.

Angles increase clockwise.

For thickness greater than 1, the arc grows inward from the specified radius.

---

## 8.22 Shapes.fill_pie()

    shapes.fill_pie(
        centre_x,
        centre_y,
        radius,
        start_degrees,
        end_degrees,
        colour
    )

Draws a filled pie-shaped sector.

### Example

    shapes.fill_pie(
        64, 80,
        45,
        0, 120,
        YELLOW
    )

The sector starts at `start_degrees` and proceeds clockwise to `end_degrees`.

---

## 8.23 Shapes.fill_rounded_rectangle()

    shapes.fill_rounded_rectangle(
        x,
        y,
        width,
        height,
        radius,
        colour
    )

Draws a filled rectangle with rounded corners.

### Example

    shapes.fill_rounded_rectangle(
        10, 20,
        108, 50,
        10,
        BLUE
    )

The corner radius is automatically restricted to a value that fits inside the rectangle.

---

## 8.24 Shapes.draw_rounded_rectangle()

    shapes.draw_rounded_rectangle(
        x,
        y,
        width,
        height,
        radius,
        colour
    )

Draws an outline of a rounded rectangle.

### Example

    shapes.draw_rounded_rectangle(
        10, 20,
        108, 50,
        10,
        WHITE
    )

---

## 8.25 Shapes.draw_sprite()

    shapes.draw_sprite(sprite, x, y)

Draws a Sprite object.

### Parameters

| Parameter | Description |
|---|---|
| `sprite` | Sprite object |
| `x` | Destination X |
| `y` | Destination Y |

Pixels matching the sprite's transparent colour are not drawn.

### Example

    from nokia_shapes import Sprite

    sprite = Sprite.from_file(
        "icon.raw",
        16,
        16,
        transparent_colour=MAGENTA
    )

    shapes.draw_sprite(sprite, 40, 40)

---

## 8.26 Angle System

The Shapes module uses whole-number degrees.

| Angle | Direction |
|---:|---|
| 0° | Right |
| 90° | Down |
| 180° | Left |
| 270° | Up |

This convention is used for:

- Arcs.
- Pie slices.
- Regular polygons.
- Stars.

---

## 8.27 Shapes Numeric Helper Functions

These functions are defined in `nokia_shapes.py`.

### sine()

    sine(degrees)

Returns sine multiplied by 4096.

Example:

    value = sine(90)

### cosine()

    cosine(degrees)

Returns cosine multiplied by 4096.

Example:

    value = cosine(0)

### integer_square_root()

    integer_square_root(value)

Returns the largest whole number whose square is not greater than `value`.

Example:

    result = integer_square_root(100)

    # Result: 10

These functions use integer arithmetic rather than floating-point calculations.

---

# 9. nokia_shapes.py – Sprite API

A Sprite is a small image stored in RAM.

It supports transparent pixels.

Import:

    from nokia_shapes import Sprite

## 9.1 Sprite Constructor

    Sprite(
        width,
        height,
        pixel_bytes,
        transparent_colour=None
    )

### Parameters

| Parameter | Description |
|---|---|
| `width` | Sprite width |
| `height` | Sprite height |
| `pixel_bytes` | Raw RGB565 image bytes |
| `transparent_colour` | Colour treated as transparent |

### Image format

- RGB565.
- 16 bits per pixel.
- High byte first.
- Exactly two bytes per pixel.

The constructor checks that the pixel buffer contains exactly:

    width * height * 2

bytes.

### Example

    sprite = Sprite(
        16,
        16,
        pixel_data,
        transparent_colour=MAGENTA
    )

---

## 9.2 Sprite.width

    sprite.width

Returns the sprite width.

---

## 9.3 Sprite.height

    sprite.height

Returns the sprite height.

---

## 9.4 Sprite.transparent_colour

    sprite.transparent_colour

Returns the colour configured as transparent.

Returns `None` when transparency is disabled.

---

## 9.5 Sprite.memory_bytes()

    sprite.memory_bytes()

Returns the number of bytes used by the sprite's pixel buffer.

A sprite requires:

    width * height * 2

bytes for its pixels.

---

## 9.6 Sprite.from_file()

    Sprite.from_file(
        filename,
        width,
        height,
        transparent_colour=None,
        frame=0
    )

Loads a sprite from a raw RGB565 file.

### Parameters

| Parameter | Description |
|---|---|
| `filename` | File path |
| `width` | Sprite width |
| `height` | Sprite height |
| `transparent_colour` | Optional transparent colour |
| `frame` | Frame index, starting from 0 |

A file may contain multiple frames stored consecutively.

### Example

    sprite = Sprite.from_file(
        "animation.raw",
        32,
        32,
        transparent_colour=MAGENTA,
        frame=0
    )

Load the second frame:

    sprite = Sprite.from_file(
        "animation.raw",
        32,
        32,
        transparent_colour=MAGENTA,
        frame=1
    )

Raises `ValueError` if the requested frame is incomplete.

---

## 9.7 Sprite.from_text_rows()

    Sprite.from_text_rows(
        rows,
        colour_for_character,
        transparent_colour=0xF81F
    )

Creates a sprite from text characters.

Each character represents a pixel colour.

Characters missing from the colour dictionary become transparent.

### Example

    sprite = Sprite.from_text_rows(
        (
            "..R..",
            ".RRR.",
            "RRRRR",
            ".RRR.",
            "..R.."
        ),
        {
            "R": RED
        }
    )

---

## 9.8 Sprite.flipped()

    sprite.flipped(
        horizontally=True,
        vertically=False
    )

Creates and returns a new flipped Sprite.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `horizontally` | `True` | Flip left to right |
| `vertically` | `False` | Flip top to bottom |

### Examples

Horizontal flip:

    mirrored = sprite.flipped()

Vertical flip:

    upside_down = sprite.flipped(
        horizontally=False,
        vertically=True
    )

Both directions:

    flipped = sprite.flipped(
        horizontally=True,
        vertically=True
    )

The returned sprite has its own pixel memory.

---

# 10. nokia_3d.py – 3D Graphics API

This module provides basic 3D graphics.

It uses:

- Mesh objects.
- Vertices.
- Faces.
- Rotation matrices.
- Perspective projection.
- Face visibility.
- Lighting.
- Solid rendering.
- Wireframe rendering.

Import:

    from nokia_3d import (
        Mesh,
        Object3D,
        make_cube,
        MODE_SOLID
    )

The 3D renderer uses the advanced 2D Shapes drawing system.

Create a Shapes object before creating and drawing 3D objects.

---

## 10.1 3D Rendering Mode Constants

| Constant | Description |
|---|---|
| `MODE_SOLID` | Solid faces with lighting |
| `MODE_WIREFRAME` | Draws every model edge |
| `MODE_WIREFRAME_HIDDEN_LINES` | Draws edges belonging to visible faces |

---

## 10.2 Mesh Class

### Constructor

    Mesh(
        vertices,
        faces,
        reference_point=None
    )

### Description

Creates a custom 3D mesh.

### Parameters

| Parameter | Description |
|---|---|
| `vertices` | List of `(x, y, z)` coordinates |
| `faces` | List of faces containing vertex indices |
| `reference_point` | Optional function for determining outward face direction |

### Vertex example

    vertices = [
        (-100, -100, -100),
        (100, -100, -100),
        (100, 100, -100),
        (-100, 100, -100)
    ]

### Face example

    faces = [
        (0, 1, 2, 3)
    ]

### Reference point

For ordinary solid shapes, leave it as:

    reference_point=None

For shapes containing holes, a reference-point function can be supplied.

Expected function format:

    def reference_point(x, y, z):
        return (nearest_x, nearest_y, nearest_z)

### Important

Each face must:

- Contain at least three vertex indices.
- Refer to valid vertices.
- Have all its vertices in one flat plane.
- List its vertices around the face.

---

## 10.3 Mesh.face_count

    mesh.face_count

Returns the total number of faces.

This is a read-only property.

---

## 10.4 Mesh.memory_bytes()

    mesh.memory_bytes()

Returns an approximate memory usage for the mesh.

---

## 10.5 make_box()

    make_box(
        width=1000,
        height=1000,
        depth=1000
    )

Creates a rectangular 3D box.

Dimensions:

- Width is along X.
- Height is along Y.
- Depth is along Z.

Example:

    box = make_box(1000, 600, 400)

---

## 10.6 make_cube()

    make_cube(size=1000)

Creates a cube.

Example:

    cube_mesh = make_cube(1000)

---

## 10.7 make_cylinder()

    make_cylinder(
        radius=500,
        height=1000,
        sides=12
    )

Creates a cylinder.

Parameters:

| Parameter | Description |
|---|---|
| `radius` | Cylinder radius |
| `height` | Cylinder height |
| `sides` | Number of sides around the cylinder |

Example:

    cylinder_mesh = make_cylinder(
        radius=500,
        height=1000,
        sides=12
    )

---

## 10.8 make_cone()

    make_cone(
        radius=500,
        height=1000,
        sides=12
    )

Creates a cone.

Example:

    cone_mesh = make_cone(
        radius=500,
        height=1000,
        sides=12
    )

---

## 10.9 make_pyramid()

    make_pyramid(
        radius=700,
        height=1000,
        sides=4
    )

Creates a pyramid.

Parameters:

| Parameter | Description |
|---|---|
| `radius` | Distance from base centre to a base corner |
| `height` | Pyramid height |
| `sides` | Number of sides in the base |

Example:

    pyramid_mesh = make_pyramid(
        radius=700,
        height=1000,
        sides=4
    )

---

## 10.10 make_sphere()

    make_sphere(
        radius=1000,
        rings=6,
        segments=10
    )

Creates a sphere using flat polygon faces.

Parameters:

| Parameter | Description |
|---|---|
| `radius` | Sphere radius |
| `rings` | Number of latitude divisions |
| `segments` | Number of divisions around each ring |

Example:

    sphere_mesh = make_sphere(
        radius=1000,
        rings=6,
        segments=10
    )

Increasing rings and segments makes the sphere look rounder but increases the amount of geometry and drawing work.

---

## 10.11 make_torus()

    make_torus(
        major_radius=700,
        minor_radius=300,
        rings=12,
        sides=8
    )

Creates a donut-shaped 3D object.

Parameters:

| Parameter | Description |
|---|---|
| `major_radius` | Distance from the centre of the hole to the tube centre |
| `minor_radius` | Radius of the tube |
| `rings` | Divisions around the main ring |
| `sides` | Divisions around the tube |

Example:

    torus_mesh = make_torus(
        major_radius=700,
        minor_radius=300,
        rings=12,
        sides=8
    )

---

## 10.12 make_octahedron()

    make_octahedron(radius=1000)

Creates an octahedron.

Example:

    mesh = make_octahedron(1000)

---

## 10.13 make_icosahedron()

    make_icosahedron(radius=1000)

Creates an icosahedron consisting of 20 triangular faces.

Example:

    mesh = make_icosahedron(1000)

---

## 10.14 rotation_matrix()

    rotation_matrix(
        about_x,
        about_y,
        about_z
    )

Creates a 3 × 3 rotation matrix.

Returns nine integers.

The fixed-point representation uses:

    4096 = 1.0

This is a mathematical helper primarily used by the 3D rendering system.

---

## 10.15 shade_colour()

    shade_colour(colour, brightness)

Adjusts the brightness of an RGB565 colour.

### Parameters

| Parameter | Description |
|---|---|
| `colour` | RGB565 colour |
| `brightness` | Brightness value |

Brightness examples:

| Brightness | Effect |
|---:|---|
| 0 | Black |
| 128 | Approximately half brightness |
| 256 | Original brightness |

Example:

    dark_red = shade_colour(RED, 128)

---

## 10.16 Object3D Class

### Constructor

    Object3D(
        mesh,
        colour,
        radius_pixels=30,
        camera_distance_in_radii=4,
        ambient=60,
        face_colours=None
    )

### Description

Creates a renderable 3D object.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `mesh` | Required | Mesh object |
| `colour` | Required | Main RGB565 colour |
| `radius_pixels` | 30 | Object's screen radius |
| `camera_distance_in_radii` | 4 | Camera distance measured in object radii |
| `ambient` | 60 | Ambient brightness, 0–255 |
| `face_colours` | `None` | Optional colour for every mesh face |

### Example

    cube = Object3D(
        make_cube(),
        RED,
        radius_pixels=35
    )

The object is scaled to its screen-space radius rather than specifying its dimensions directly in display pixels.

Use `camera_distance_in_radii=None` to disable perspective.

---

## 10.17 Object3D.set_rotation()

    object3d.set_rotation(
        about_x,
        about_y,
        about_z=0
    )

Changes the object's rotation in whole degrees.

### Parameters

| Parameter | Description |
|---|---|
| `about_x` | Rotation around X |
| `about_y` | Rotation around Y |
| `about_z` | Rotation around Z |

Example:

    cube.set_rotation(30, 45, 0)

### Coordinate convention

- X points right.
- Y points up.
- Z points away from the viewer.

The rotation order is:

1. Z rotation.
2. X rotation.
3. Y rotation.

Positive Z and Y rotation are clockwise according to the module's documented viewing conventions.

---

## 10.18 Object3D.set_position()

    object3d.set_position(centre_x, centre_y)

Sets the centre position of the 3D object on the display.

Example:

    cube.set_position(64, 80)

---

## 10.19 Object3D.set_colour()

    object3d.set_colour(colour)

Changes the main object colour.

Example:

    cube.set_colour(BLUE)

---

## 10.20 Object3D.set_light()

    object3d.set_light(x, y, z)

Changes the light direction.

The direction points TOWARDS the light in the object's own coordinate system.

### Coordinate directions

- X: right.
- Y: up.
- Z: away from the viewer.

Example:

    cube.set_light(-1800, 2200, -3000)

The direction is normalised internally.

---

## 10.21 Object3D.visible_face_count

    object3d.visible_face_count

Returns the number of visible faces prepared for rendering.

This is a read-only property.

---

## 10.22 Object3D.bounding_box()

    object3d.bounding_box()

Returns:

    (left, top, right, bottom)

The coordinates represent the projected screen-space bounding box.

Useful for clearing only the object's previous drawing area before the next frame.

---

## 10.23 Object3D.prepare()

    object3d.prepare()

Prepares a 3D object for rendering.

The function:

1. Rotates the vertices.
2. Projects the vertices onto the screen.
3. Removes faces pointing away from the viewer.
4. Calculates face lighting.
5. Sorts visible faces by depth.

Normally, calling `draw()` is enough because it automatically calls `prepare()` when required.

---

## 10.24 Object3D.draw()

    object3d.draw(
        shapes,
        mode=MODE_SOLID,
        edge_colour=None
    )

Draws the 3D object using a Shapes object.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `shapes` | Required | Shapes drawing object |
| `mode` | `MODE_SOLID` | Rendering mode |
| `edge_colour` | `None` | Optional edge colour |

### Solid example

    cube.draw(
        shapes,
        mode=MODE_SOLID
    )

### Solid with edges

    cube.draw(
        shapes,
        mode=MODE_SOLID,
        edge_colour=WHITE
    )

### Wireframe

    cube.draw(
        shapes,
        mode=MODE_WIREFRAME,
        edge_colour=GREEN
    )

### Hidden-line wireframe

    cube.draw(
        shapes,
        mode=MODE_WIREFRAME_HIDDEN_LINES,
        edge_colour=WHITE
    )

---

# 11. nokia_font.py – Custom Font API

This module provides custom font rendering.

Unlike the built-in font in `nokia_display.py`, this module supports:

- Custom NKF font files.
- Variable character widths.
- Smooth 2-bit glyph coverage.
- Text measurement.
- Word wrapping.
- Text alignment.
- Underlining.
- Strikethrough.
- Baseline positioning.
- Clipping.

Import:

    from nokia_font import Font

A font file must use the NKF format expected by this implementation.

---

## 11.1 Font Alignment Constants

| Constant | Value |
|---|---|
| `ALIGN_LEFT` | `"left"` |
| `ALIGN_CENTRE` | `"centre"` |
| `ALIGN_RIGHT` | `"right"` |

Example:

    from nokia_font import (
        ALIGN_LEFT,
        ALIGN_CENTRE,
        ALIGN_RIGHT
    )

---

## 11.2 Font Constructor

    Font(
        filename,
        keep_index_in_memory=False,
        cache_bytes=3072,
        use_fast_helpers=True
    )

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `filename` | Required | NKF font file path |
| `keep_index_in_memory` | `False` | Keep the font character index in RAM |
| `cache_bytes` | 3072 | Maximum glyph-cache memory |
| `use_fast_helpers` | `True` | Enable optional accelerated glyph rendering |

### Example

    font = Font("fonts/sans_14.nkf")

Memory-optimised:

    font = Font(
        "fonts/sans_14.nkf",
        keep_index_in_memory=False,
        cache_bytes=3072
    )

Faster character lookup:

    font = Font(
        "fonts/sans_14.nkf",
        keep_index_in_memory=True
    )

Keeping the index in RAM uses approximately 10 bytes per character.

---

## 11.3 Font Public Attributes

| Attribute | Description |
|---|---|
| `filename` | Font file path |
| `line_height` | Height of one line |
| `ascent` | Font ascent |
| `descent` | Font descent |
| `fast_helpers_in_use` | Whether the accelerated glyph helper is active |

These values are read from the NKF font header or set during initialisation.

---

## 11.4 Font.close()

    font.close()

Closes the font file.

Call this when the font is no longer required.

---

## 11.5 Font.memory_bytes()

    font.memory_bytes()

Returns the approximate maximum memory reserved for the font index and glyph cache.

The font data itself remains in the file until glyphs are loaded.

---

## 11.6 Font.has_character()

    font.has_character(character)

Checks whether a character exists in the font's character index.

### Example

    if font.has_character("A"):
        print("Character exists")

Returns a Boolean.

---

## 11.7 Font.measure_line()

    font.measure_line(text)

Measures the pixel width of a single line of text.

New lines are not treated as line separators by this function.

### Example

    width = font.measure_line("Hello World")

Returns an integer width in pixels.

---

## 11.8 Font.measure()

    font.measure(text)

Measures text that may contain multiple lines.

### Example

    width, height = font.measure(
        "Hello\nWorld"
    )

Returns:

    (width, height)

The width is the widest line. The height is the number of lines multiplied by `line_height`.

---

## 11.9 Font.wrap()

    font.wrap(text, max_width)

Breaks text into lines that fit within a given width.

### Parameters

| Parameter | Description |
|---|---|
| `text` | Text to wrap |
| `max_width` | Maximum line width in pixels |

### Example

    lines = font.wrap(
        "This is a long sentence",
        100
    )

Returns a list of strings.

Wrapping occurs at spaces. An individual word that exceeds the available width is split.

---

## 11.10 Font.character_width()

    font.character_width(character)

Returns the horizontal distance the text pen moves after drawing a character.

This value is the character's advance width.

### Example

    width = font.character_width("A")

Returns an integer.

---

## 11.11 Font.draw()

### Function

    font.draw(
        screen,
        text,
        x,
        y,
        colour,
        background=None,
        underline=False,
        strikethrough=False,
        y_is_baseline=False,
        clip=None
    )

### Description

Draws custom-font text on a compatible screen buffer.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `screen` | Required | Screen-compatible drawing surface |
| `text` | Required | Text to draw |
| `x` | Required | Text X position |
| `y` | Required | Text Y position |
| `colour` | Required | RGB565 text colour |
| `background` | `None` | Optional background colour |
| `underline` | `False` | Draw an underline |
| `strikethrough` | `False` | Draw a strikethrough |
| `y_is_baseline` | `False` | Treat Y as the text baseline |
| `clip` | `None` | Optional clipping rectangle |

### Example

    font.draw(
        screen,
        "Hello Pico",
        10,
        20,
        WHITE
    )

Underline:

    font.draw(
        screen,
        "Important",
        10,
        40,
        RED,
        underline=True
    )

Strikethrough:

    font.draw(
        screen,
        "Old Price",
        10,
        60,
        WHITE,
        strikethrough=True
    )

### Return value

Returns:

    (width, height)

---

## 11.12 Font.draw_aligned()

### Function

    font.draw_aligned(
        screen,
        text,
        x,
        y,
        width,
        colour,
        alignment=ALIGN_LEFT,
        background=None,
        underline=False,
        strikethrough=False,
        clip=None
    )

### Description

Draws text inside a box and aligns each line independently.

### Parameters

| Parameter | Description |
|---|---|
| `screen` | Drawing surface |
| `text` | Text to draw |
| `x` | Box left position |
| `y` | Text top position |
| `width` | Box width |
| `colour` | Text colour |
| `alignment` | Left, centre or right |
| `background` | Optional background |
| `underline` | Underline enabled/disabled |
| `strikethrough` | Strikethrough enabled/disabled |
| `clip` | Optional clipping rectangle |

### Example

Centred text:

    font.draw_aligned(
        screen,
        "CENTRED",
        0,
        40,
        screen.width,
        WHITE,
        alignment=ALIGN_CENTRE
    )

Right-aligned text:

    font.draw_aligned(
        screen,
        "RIGHT",
        0,
        60,
        screen.width,
        GREEN,
        alignment=ALIGN_RIGHT
    )

### Return value

Returns the total text height in pixels.

---

## 11.13 Font.draw_wrapped()

### Function

    font.draw_wrapped(
        screen,
        text,
        x,
        y,
        width,
        colour,
        alignment=ALIGN_LEFT,
        background=None,
        extra_line_spacing=0,
        clip=None
    )

### Description

Automatically wraps and draws text inside a specified width.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `screen` | Required | Drawing surface |
| `text` | Required | Text |
| `x` | Required | Left position |
| `y` | Required | Top position |
| `width` | Required | Maximum text width |
| `colour` | Required | Text colour |
| `alignment` | `ALIGN_LEFT` | Text alignment |
| `background` | `None` | Optional background |
| `extra_line_spacing` | 0 | Additional spacing between lines |
| `clip` | `None` | Optional clipping rectangle |

### Example

    height = font.draw_wrapped(
        screen,
        "This is a long paragraph that needs automatic wrapping.",
        5,
        20,
        118,
        WHITE,
        alignment=ALIGN_LEFT,
        extra_line_spacing=2
    )

### Return value

Returns the total height used.

---

## 11.14 Font Clipping

The `draw()`, `draw_aligned()` and `draw_wrapped()` methods accept a `clip` argument.

Expected structure:

    (left, top, right, bottom)

All four coordinates are inclusive.

Example:

    clip_area = (10, 20, 110, 100)

    font.draw(
        screen,
        "Scrolling text",
        0,
        40,
        WHITE,
        clip=clip_area
    )

Only the visible portion inside the clipping rectangle is drawn.

---

# 12. nokia_text_motion.py – Text Animation API

This module provides time-based text movement and animation.

The animations depend on elapsed time rather than frame count.

This means animation speed does not depend directly on the display frame rate.

Import:

    from nokia_text_motion import (
        Marquee,
        VerticalScroller,
        MessageRoller,
        draw_wavy_text,
        draw_text_on_circle,
        draw_typewriter
    )

The module requires the custom `Font` API.

---

## 12.1 Scrolling Direction Constants

| Constant | Value |
|---|---|
| `SCROLL_LEFT` | `"left"` |
| `SCROLL_RIGHT` | `"right"` |
| `SCROLL_UP` | `"up"` |
| `SCROLL_DOWN` | `"down"` |

---

## 12.2 Easing Functions

Animation functions use progress values from 0 to 1024.

| Value | Meaning |
|---:|---|
| 0 | Beginning |
| 512 | Halfway |
| 1024 | Complete |

### linear()

    linear(progress)

Constant-speed movement.

### ease_in()

    ease_in(progress)

Starts slowly and accelerates.

### ease_out()

    ease_out(progress)

Starts quickly and slows down.

### ease_in_out()

    ease_in_out(progress)

Slow start, fast middle and slow finish.

### bounce_out()

    bounce_out(progress)

Finishes with a bouncing movement.

Example:

    from nokia_text_motion import ease_out

    result = ease_out(512)

Each easing function accepts a progress integer and returns an adjusted progress value.

---

## 12.3 progress_of()

### Function

    progress_of(
        elapsed_milliseconds,
        duration_milliseconds,
        delay_milliseconds=0
    )

### Description

Calculates animation progress.

### Parameters

| Parameter | Description |
|---|---|
| `elapsed_milliseconds` | Time since animation start |
| `duration_milliseconds` | Animation duration |
| `delay_milliseconds` | Optional starting delay |

### Returns

Integer from 0 to 1024.

### Example

    progress = progress_of(
        500,
        1000
    )

A completed or non-positive-duration movement returns 1024 once its delay has passed.

---

## 12.4 fly_in_position()

### Function

    fly_in_position(
        from_x,
        from_y,
        to_x,
        to_y,
        elapsed_milliseconds,
        duration_milliseconds,
        easing=ease_out,
        delay_milliseconds=0
    )

### Description

Calculates a moving text or object position between two points.

### Parameters

| Parameter | Description |
|---|---|
| `from_x` | Starting X |
| `from_y` | Starting Y |
| `to_x` | Destination X |
| `to_y` | Destination Y |
| `elapsed_milliseconds` | Elapsed time |
| `duration_milliseconds` | Movement duration |
| `easing` | Easing function |
| `delay_milliseconds` | Optional delay |

### Returns

    (x, y)

### Example

    x, y = fly_in_position(
        0, 80,
        50, 80,
        500, 1000,
        easing=ease_out
    )

Use the returned coordinates when drawing the object.

---

## 12.5 blend_colours()

### Function

    blend_colours(
        first_colour,
        second_colour,
        amount
    )

### Description

Blends two RGB565 colours.

### Parameters

| Parameter | Description |
|---|---|
| `first_colour` | Starting colour |
| `second_colour` | Ending colour |
| `amount` | Blend amount, 0–256 |

### Examples

    result = blend_colours(
        BLACK,
        WHITE,
        128
    )

Amount 0:

Returns the first colour.

Amount 256:

Returns the second colour.

---

## 12.6 fade_colour()

### Function

    fade_colour(
        text_colour,
        background_colour,
        elapsed_milliseconds,
        duration_milliseconds,
        fade_in=True,
        delay_milliseconds=0
    )

### Description

Calculates the text colour during a fade-in or fade-out effect.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `text_colour` | Required | Text colour |
| `background_colour` | Required | Background colour |
| `elapsed_milliseconds` | Required | Elapsed time |
| `duration_milliseconds` | Required | Fade duration |
| `fade_in` | `True` | Fade in or out |
| `delay_milliseconds` | 0 | Optional delay |

### Example

    current_colour = fade_colour(
        WHITE,
        BLACK,
        500,
        1000,
        fade_in=True
    )

Returns a blended RGB565 colour.

---

## 12.7 Marquee Class

### Constructor

    Marquee(
        font,
        text,
        x,
        y,
        width,
        colour,
        pixels_per_second=40,
        direction=SCROLL_LEFT,
        gap=24,
        background=None
    )

### Description

Creates a continuously scrolling, single-line text window.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `font` | Required | Font object |
| `text` | Required | Scrolling text |
| `x` | Required | Window X |
| `y` | Required | Window Y |
| `width` | Required | Window width |
| `colour` | Required | Text colour |
| `pixels_per_second` | 40 | Scrolling speed |
| `direction` | `SCROLL_LEFT` | Left or right |
| `gap` | 24 | Space between repeated text |
| `background` | `None` | Optional window background |

### Example

    marquee = Marquee(
        font,
        "Welcome to Raspberry Pi Pico 2",
        0,
        20,
        128,
        WHITE,
        pixels_per_second=40,
        direction=SCROLL_LEFT,
        gap=24,
        background=BLACK
    )

### Marquee.draw()

    marquee.draw(screen, elapsed_milliseconds)

Draws the marquee at the supplied elapsed time.

Example:

    marquee.draw(screen, elapsed)

The animation repeats continuously.

---

## 12.8 VerticalScroller Class

### Constructor

    VerticalScroller(
        font,
        text,
        x,
        y,
        width,
        height,
        colour,
        pixels_per_second=15,
        direction=SCROLL_UP,
        alignment=ALIGN_LEFT,
        extra_line_spacing=0,
        loop=True,
        background=None
    )

### Description

Creates a vertically scrolling text window.

Text is wrapped into lines when the object is created.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `font` | Required | Font object |
| `text` | Required | Text to scroll |
| `x` | Required | Window X |
| `y` | Required | Window Y |
| `width` | Required | Window width |
| `height` | Required | Window height |
| `colour` | Required | Text colour |
| `pixels_per_second` | 15 | Scrolling speed |
| `direction` | `SCROLL_UP` | Up or down |
| `alignment` | `ALIGN_LEFT` | Line alignment |
| `extra_line_spacing` | 0 | Extra line spacing |
| `loop` | `True` | Repeat scrolling |
| `background` | `None` | Optional background |

### Example

    scroller = VerticalScroller(
        font,
        "First line\nSecond line\nThird line",
        10,
        20,
        108,
        100,
        WHITE,
        pixels_per_second=15,
        direction=SCROLL_UP,
        loop=True,
        background=BLACK
    )

### VerticalScroller.finished()

    scroller.finished(elapsed_milliseconds)

Returns `True` when a non-looping scroller has completed its movement.

When `loop=True`, this function returns `False`.

### VerticalScroller.draw()

    scroller.draw(screen, elapsed_milliseconds)

Draws the current scrolling frame.

---

## 12.9 MessageRoller Class

### Constructor

    MessageRoller(
        font,
        messages,
        x,
        y,
        width,
        colour,
        hold_milliseconds=1500,
        slide_milliseconds=300,
        direction=SCROLL_UP,
        alignment=ALIGN_CENTRE,
        background=None,
        height=None,
        easing=ease_in_out
    )

### Description

Displays a sequence of messages.

One message is displayed at a time. The next message rolls in while the previous message rolls out.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `font` | Required | Font object |
| `messages` | Required | Sequence of message strings |
| `x` | Required | Window X |
| `y` | Required | Window Y |
| `width` | Required | Window width |
| `colour` | Required | Text colour |
| `hold_milliseconds` | 1500 | Time to hold each message |
| `slide_milliseconds` | 300 | Transition duration |
| `direction` | `SCROLL_UP` | Up or down |
| `alignment` | `ALIGN_CENTRE` | Text alignment |
| `background` | `None` | Optional background |
| `height` | `None` | Window height |
| `easing` | `ease_in_out` | Transition easing function |

### Example

    messages = [
        "Welcome",
        "System Ready",
        "Raspberry Pi Pico 2"
    ]

    roller = MessageRoller(
        font,
        messages,
        0,
        60,
        128,
        WHITE,
        hold_milliseconds=1500,
        slide_milliseconds=300,
        direction=SCROLL_UP,
        alignment=ALIGN_CENTRE,
        background=BLACK
    )

### MessageRoller.current_index()

    roller.current_index(elapsed_milliseconds)

Returns the index of the message currently being displayed or rolled in.

### MessageRoller.draw()

    roller.draw(screen, elapsed_milliseconds)

Draws the current message-rolling frame.

---

## 12.10 draw_wavy_text()

### Function

    draw_wavy_text(
        screen,
        font,
        text,
        x,
        y,
        colour,
        elapsed_milliseconds,
        amplitude=4,
        wavelength=48,
        speed_pixels_per_second=60,
        bounce=False,
        clip=None
    )

### Description

Draws text with animated vertical wave movement.

Each character moves independently according to its position in the wave.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `screen` | Required | Drawing surface |
| `font` | Required | Custom Font object |
| `text` | Required | Text to draw |
| `x` | Required | Starting X |
| `y` | Required | Starting Y |
| `colour` | Required | Text colour |
| `elapsed_milliseconds` | Required | Animation time |
| `amplitude` | 4 | Wave height |
| `wavelength` | 48 | Distance between wave tops |
| `speed_pixels_per_second` | 60 | Wave speed |
| `bounce` | `False` | Enable upward-only bouncing |
| `clip` | `None` | Optional clipping rectangle |

### Example

    draw_wavy_text(
        screen,
        font,
        "WAVY TEXT",
        5,
        60,
        GREEN,
        elapsed,
        amplitude=5,
        wavelength=48,
        speed_pixels_per_second=60
    )

---

## 12.11 draw_text_on_circle()

### Function

    draw_text_on_circle(
        screen,
        font,
        text,
        centre_x,
        centre_y,
        radius,
        colour,
        start_degrees=0,
        clip=None
    )

### Description

Places individual text characters around a circle.

The letters remain upright.

### Parameters

| Parameter | Description |
|---|---|
| `screen` | Drawing surface |
| `font` | Font object |
| `text` | Text to place around circle |
| `centre_x` | Circle centre X |
| `centre_y` | Circle centre Y |
| `radius` | Circle radius |
| `colour` | Text colour |
| `start_degrees` | First character angle |
| `clip` | Optional clip rectangle |

### Example

    draw_text_on_circle(
        screen,
        font,
        "HELLO PICO",
        64,
        80,
        45,
        WHITE,
        start_degrees=0
    )

### Rotation

Change `start_degrees` over time to rotate the text.

Example:

    start_degrees = elapsed * 60 // 1000

This produces a rotation rate of approximately 60 degrees per second.

Angle convention:

- 0° is right.
- 90° is down.
- 270° is up.

---

## 12.12 draw_typewriter()

### Function

    draw_typewriter(
        screen,
        font,
        text,
        x,
        y,
        colour,
        elapsed_milliseconds,
        characters_per_second=12,
        cursor=True,
        clip=None
    )

### Description

Reveals text one character at a time.

It can also display a blinking cursor.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `screen` | Required | Drawing surface |
| `font` | Required | Font object |
| `text` | Required | Full text |
| `x` | Required | Starting X |
| `y` | Required | Starting Y |
| `colour` | Required | Text colour |
| `elapsed_milliseconds` | Required | Animation time |
| `characters_per_second` | 12 | Character appearance speed |
| `cursor` | `True` | Enable blinking cursor |
| `clip` | `None` | Optional clipping rectangle |

### Example

    finished = draw_typewriter(
        screen,
        font,
        "Hello Raspberry Pi Pico 2",
        5,
        60,
        WHITE,
        elapsed,
        characters_per_second=12,
        cursor=True
    )

### Return value

Returns:

- `False` while the text is being revealed.
- `True` when all text is visible.

---

## 12.13 Recommended Animation Timing

The animation module expects elapsed milliseconds.

A typical MicroPython timing pattern is:

    import time

    start_time = time.ticks_ms()

    while True:
        elapsed = time.ticks_diff(
            time.ticks_ms(),
            start_time
        )

        # Draw animation using elapsed.

This keeps animation movement based on time rather than the number of rendered frames.

---

# 13. nokia_dma_link.py – DMA Support API

This module implements the low-level communication links used by:

    display.use_spi_dma()

and:

    display.use_pio_dma()

It is primarily an internal support module.

Applications normally do not need to instantiate its classes directly.

---

## 13.1 SpiDmaLink Class

### Constructor

    SpiDmaLink(display)

Creates a hardware SPI DMA link.

### Parameters

| Parameter | Description |
|---|---|
| `display` | Display object |

### Public Attributes

| Attribute | Description |
|---|---|
| `name` | `"SPI + DMA"` |
| `takes_raw_pixels` | `False` |
| `in_flight` | Whether a transfer is considered active |

### SpiDmaLink.start()

    link.start(packed, byte_count)

Starts a DMA transfer using an already packed buffer.

Parameters:

| Parameter | Description |
|---|---|
| `packed` | Packed transmission buffer |
| `byte_count` | Number of bytes to send |

The chip-select line must already be low.

The call starts transmission and returns without waiting for all data to leave the SPI peripheral.

### SpiDmaLink.wait()

    link.wait()

Waits for the DMA and SPI transmission to finish.

The implementation uses a timeout and raises `RuntimeError` if transmission does not progress or the SPI does not finish.

### SpiDmaLink.close()

    link.close()

Stops and releases the DMA resource.

---

## 13.2 PioDmaLink Class

### Constructor

    PioDmaLink(
        display,
        bit_clock_hz,
        command_delay_microseconds=0
    )

Creates a PIO DMA communication link.

### Parameters

| Parameter | Description |
|---|---|
| `display` | Display object |
| `bit_clock_hz` | PIO clock frequency |
| `command_delay_microseconds` | Bit-banging command delay |

### Public Attributes

| Attribute | Description |
|---|---|
| `takes_raw_pixels` | `True` |
| `name` | Descriptive PIO DMA backend name |
| `bit_clock_hz` | Configured PIO clock |
| `in_flight` | Whether a transfer is active |

---

## 13.3 PioDmaLink.start_raw()

    link.start_raw(
        buffer,
        offset,
        byte_count
    )

Starts a raw-pixel DMA transmission.

### Parameters

| Parameter | Description |
|---|---|
| `buffer` | Source pixel buffer |
| `offset` | Starting byte position |
| `byte_count` | Number of bytes to transfer |

### Important

- The display window must already be selected.
- The function returns immediately after starting transmission.
- Do not modify the source buffer region until `wait()` finishes.
- The PIO hardware temporarily owns the clock and data pins.

---

## 13.4 PioDmaLink.wait()

    link.wait()

Waits for the active PIO DMA transfer to complete.

The function then releases the PIO resources and restores normal pin ownership.

Does nothing if no transmission is active.

---

## 13.5 PioDmaLink.send_raw()

    link.send_raw(
        buffer,
        offset,
        byte_count
    )

Convenience method that:

1. Starts raw transmission.
2. Waits until the transfer finishes.

---

## 13.6 PioDmaLink.close()

    link.close()

Waits for any active transfer, releases DMA resources and restores the original command delay.

---

## 13.7 DMA Hardware Constants

The module contains these implementation constants:

| Constant | Description |
|---|---|
| `SPI0_BASE` | SPI0 hardware base address |
| `SPI_CONTROL_0` | SPI control register offset |
| `SPI_DATA` | SPI data register offset |
| `SPI_STATUS` | SPI status register offset |
| `SPI_DMA_CONTROL` | SPI DMA control register offset |
| `DMA_REQUEST_SPI0_TX` | SPI0 DMA request number |
| `PIO0_TX_FIFO_0` | PIO0 state-machine-0 transmit FIFO address |
| `DMA_REQUEST_PIO0_TX_0` | PIO0 DMA request number |
| `TIMEOUT_MILLISECONDS` | DMA timeout, 500 milliseconds |

These are hardware implementation details rather than normal application drawing APIs.

---

# 14. Fast Helper Modules

The project includes optional accelerated implementations written using MicroPython Viper.

They replace selected Python functions when available and when their built-in checks succeed.

The normal drawing APIs remain unchanged.

---

## 14.1 nokia_fast.py

Provides accelerated display-buffer operations.

### pack_data()

    pack_data(
        source,
        source_offset,
        destination,
        byte_count
    )

Converts RGB565 data bytes into the packed 9-bit display transmission format.

`byte_count` must be a multiple of 8.

### mark_changed_rows()

    mark_changed_rows(
        current,
        previous,
        words_per_row,
        first_row,
        last_row,
        flags
    )

Compares the current and previous image buffers and marks rows that have changed.

### copy_region()

    copy_region(
        source,
        destination,
        word_offset,
        word_count
    )

Copies a region of a buffer using 32-bit words.

These functions are used internally by the display and graphics modules.

---

## 14.2 nokia_font_fast.py

Provides accelerated custom glyph blending.

### blend_glyph()

    blend_glyph(
        destination,
        glyph,
        parameters
    )

Blends a custom 2-bit-per-pixel glyph into the display buffer.

This function is called internally by `Font.draw()`.

Applications should use the normal Font API rather than calling this helper directly.

---

## 14.3 nokia_shapes_fast.py

Provides accelerated 2D shape operations.

### Public helper functions

#### fill_polygon_rows()

    fill_polygon_rows(
        destination,
        coordinates,
        crossings,
        parameters
    )

Accelerated polygon scan-line filling.

#### fill_spans()

    fill_spans(
        destination,
        lefts,
        rights,
        parameters
    )

Fills horizontal pixel spans.

#### outline_spans()

    outline_spans(
        destination,
        lefts,
        rights,
        parameters
    )

Draws outlines around calculated horizontal spans.

#### fill_ring_spans()

    fill_ring_spans(
        destination,
        outer_lefts,
        outer_rights,
        inner_lefts,
        inner_rights,
        parameters
    )

Fills horizontal spans belonging to a ring.

#### ellipse_extents()

    ellipse_extents(
        lefts,
        rights,
        parameters
    )

Calculates horizontal extents for ellipse rows.

#### rounded_extents()

    rounded_extents(
        lefts,
        rights,
        parameters
    )

Calculates horizontal extents for rounded rectangles.

#### arc_polygon_points()

    arc_polygon_points(
        coordinates,
        table,
        parameters
    )

Calculates the polygon coordinates used by arc and pie operations.

These are low-level Viper functions. They are selected automatically by `Shapes` when available and working.

---

# 15. Complete Usage Examples

The following examples demonstrate how the public APIs can be combined.

## 15.1 Basic Display Initialisation

    from nokia_display import (
        Display,
        RED,
        GREEN,
        BLUE,
        BLACK
    )

    display = Display(
        6, 7, 5, 4
    )

    display.start()

    display.use_hardware_spi()

    display.fill_screen(BLACK)

    display.draw_pixel(64, 80, RED)

    display.fill_rectangle(
        10, 10,
        50, 30,
        GREEN
    )

    display.draw_circle(
        64, 80,
        25,
        BLUE
    )

The GPIO numbers are examples and must match the actual hardware wiring and SPI configuration.

---

## 15.2 Screen API Example

    from nokia_display import (
        Display,
        RED,
        GREEN,
        WHITE,
        BLACK
    )

    from nokia_graphics import Screen

    display = Display(6, 7, 5, 4)

    display.start()
    display.use_hardware_spi()

    screen = Screen(
        display,
        budget_bytes=100 * 1024
    )

    def draw_scene(screen):

        screen.fill_screen(BLACK)

        screen.draw_text(
            "HELLO PICO",
            15, 10,
            WHITE
        )

        screen.fill_circle(
            64, 80,
            25,
            RED
        )

        screen.draw_rectangle(
            10, 120,
            108, 25,
            GREEN
        )

    screen.render(
        draw_scene,
        background=BLACK
    )

---

## 15.3 Advanced 2D Shapes Example

    from nokia_display import (
        Display,
        RED,
        GREEN,
        BLUE,
        YELLOW,
        WHITE,
        BLACK
    )

    from nokia_graphics import Screen
    from nokia_shapes import Shapes

    display = Display(6, 7, 5, 4)

    display.start()
    display.use_hardware_spi()

    screen = Screen(display)

    shapes = Shapes(screen)

    def draw_scene(screen):

        screen.fill_screen(BLACK)

        shapes.fill_triangle(
            64, 10,
            110, 90,
            20, 90,
            RED
        )

        shapes.fill_star(
            64, 80,
            35, 15,
            5,
            YELLOW
        )

        shapes.draw_arc(
            64, 80,
            45,
            0, 270,
            GREEN,
            thickness=3
        )

        shapes.fill_rounded_rectangle(
            10, 115,
            108, 35,
            8,
            BLUE
        )

        shapes.draw_line(
            0, 0,
            127, 159,
            WHITE,
            thickness=2
        )

    screen.render(
        draw_scene,
        background=BLACK
    )

---

## 15.4 Custom Font Example

    from nokia_display import (
        Display,
        WHITE,
        BLACK
    )

    from nokia_graphics import Screen
    from nokia_font import (
        Font,
        ALIGN_CENTRE
    )

    display = Display(6, 7, 5, 4)

    display.start()
    display.use_hardware_spi()

    screen = Screen(display)

    font = Font(
        "fonts/sans_14.nkf"
    )

    def draw_scene(screen):

        screen.fill_screen(BLACK)

        font.draw(
            screen,
            "Hello Raspberry Pi",
            5, 20,
            WHITE
        )

        font.draw_aligned(
            screen,
            "CENTRED TEXT",
            0, 60,
            screen.width,
            WHITE,
            alignment=ALIGN_CENTRE
        )

    screen.render(
        draw_scene,
        background=BLACK
    )

    # Close the font when it is no longer needed.
    # font.close()

---

## 15.5 Sprite Example

    from nokia_display import (
        Display,
        MAGENTA,
        BLACK
    )

    from nokia_graphics import Screen
    from nokia_shapes import (
        Shapes,
        Sprite
    )

    display = Display(6, 7, 5, 4)

    display.start()
    display.use_hardware_spi()

    screen = Screen(display)

    shapes = Shapes(screen)

    sprite = Sprite.from_file(
        "icon.raw",
        16,
        16,
        transparent_colour=MAGENTA
    )

    def draw_scene(screen):

        screen.fill_screen(BLACK)

        shapes.draw_sprite(
            sprite,
            50,
            70
        )

    screen.render(
        draw_scene,
        background=BLACK
    )

---

## 15.6 3D Cube Example

    import time

    from nokia_display import (
        Display,
        RED,
        BLACK
    )

    from nokia_graphics import Screen
    from nokia_shapes import Shapes

    from nokia_3d import (
        Object3D,
        make_cube,
        MODE_SOLID
    )

    display = Display(6, 7, 5, 4)

    display.start()
    display.use_hardware_spi()

    screen = Screen(display)

    shapes = Shapes(screen)

    cube = Object3D(
        make_cube(),
        RED,
        radius_pixels=35
    )

    cube.set_position(64, 80)

    angle = 0

    while True:

        cube.set_rotation(
            angle,
            angle * 2,
            0
        )

        def draw_scene(screen):
            cube.draw(
                shapes,
                mode=MODE_SOLID
            )

        screen.render(
            draw_scene,
            background=BLACK
        )

        angle += 3

---

## 15.7 Marquee Example

    import time

    from nokia_text_motion import (
        Marquee,
        SCROLL_LEFT
    )

    from nokia_font import Font

    font = Font(
        "fonts/sans_14.nkf"
    )

    marquee = Marquee(
        font,
        "Welcome to Raspberry Pi Pico 2",
        0, 20,
        128,
        WHITE,
        pixels_per_second=40,
        direction=SCROLL_LEFT,
        gap=24,
        background=BLACK
    )

    start_time = time.ticks_ms()

    while True:

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            start_time
        )

        def draw_scene(screen):
            marquee.draw(
                screen,
                elapsed
            )

        screen.render(
            draw_scene,
            background=BLACK
        )

---

## 15.8 DMA Example

### Hardware SPI DMA

    display.start()

    display.use_spi_dma(
        baudrate=24000000
    )

    screen = Screen(display)

### PIO DMA

    display.start()

    display.use_pio_dma(
        bit_clock_hz=62500000,
        command_delay_microseconds=0
    )

    screen = Screen(display)

With PIO DMA, a full-buffer screen may start transmission in the background.

Use:

    screen.wait_until_sent()

when the program needs to ensure that the transfer has completed.

---

# 16. Important Notes and Limitations

## 16.1 Coordinate System

The display uses the following coordinate system:

- X increases from left to right.
- Y increases from top to bottom.
- The top-left pixel is `(0, 0)`.

Portrait dimensions:

    128 × 160

Landscape dimensions:

    160 × 128

The last valid pixel coordinates are:

Portrait:

    x = 127
    y = 159

Landscape:

    x = 159
    y = 127

---

## 16.2 Colour Format

All drawing functions that accept a colour expect RGB565.

Do not pass ordinary 24-bit RGB values directly.

Use:

    make_colour(red, green, blue)

when converting from 8-bit RGB components.

---

## 16.3 Raw Image Files

Raw image files must use:

- RGB565.
- Two bytes per pixel.
- High byte first.

Expected file size:

    width * height * 2

Incorrect file sizes result in `ValueError`.

The image-display functions do not automatically resize images.

---

## 16.4 Display and Screen Are Different APIs

`Display` and `Screen` are not interchangeable.

### Display

    display.draw_pixel(...)

Sends drawing operations directly to the physical display.

### Screen

    screen.draw_pixel(...)

Draws into a RAM buffer.

The frame is transmitted separately using:

    screen.show()

or:

    screen.render()

Use `Screen` for applications requiring advanced shapes, custom fonts, 3D rendering and memory-managed graphics.

---

## 16.5 BufferedDisplay and Screen Are Different

Both use memory buffers.

However:

`BufferedDisplay` allocates full-screen drawing and previous-frame buffers.

`Screen` provides three memory-management strategies, including strips mode.

Use `Screen` when RAM usage is important.

---

## 16.6 Strips Rendering

When the selected mode is:

    MODE_STRIPS

The complete frame is not stored in RAM.

Instead, the drawing function runs once for every horizontal strip.

For correct results:

1. Put scene drawing inside one function.
2. Draw the entire scene on each call.
3. Use a background colour or redraw the background.
4. Avoid changing application state inside the drawing function.

Use:

    screen.render(draw_scene, background=BLACK)

Do not use `screen.show()` in strips mode.

---

## 16.7 Custom Fonts

The custom font system requires NKF font files.

The font file must:

- Use the NKF format.
- Have the expected NKF header.
- Use the 2-bits-per-pixel glyph format supported by the implementation.

The font-generation utility mentioned in the source documentation is not included in this ZIP.

---

## 16.8 Optional Fast Helpers

These modules provide acceleration:

- `nokia_fast.py`
- `nokia_font_fast.py`
- `nokia_shapes_fast.py`

If an accelerated implementation is missing or fails its internal checks, the main modules use their Python implementations.

The application-facing function names and calling conventions remain the same.

---

## 16.9 DMA Requirements

DMA support is hardware-specific.

The DMA implementation uses RP2350 register addresses and MicroPython RP2 functionality.

Use the DMA API on the supported target hardware and firmware.

PIO DMA source buffers must not be modified while the transfer is using them.

---

## 16.10 Rotation and Existing Objects

Changing display orientation can change:

- Screen width.
- Screen height.
- Screen buffers.
- Clip boundaries.
- Positioning of existing graphics.

Recreate objects that store dimensions or clip areas based on the old screen size.

`Shapes` automatically registers a rotation callback and updates its internal drawing-buffer reference.

---

# 17. Module Reference Summary

This table provides a quick overview of the main application-facing APIs.

| Module | Class / Function | Main Purpose |
|---|---|---|
| `nokia_display.py` | `Display` | Physical display control |
| `nokia_display.py` | `make_colour()` | RGB to RGB565 conversion |
| `nokia_display.py` | `BufferedDisplay` | Full-screen buffered drawing |
| `nokia_graphics.py` | `Screen` | Memory-managed rendering |
| `nokia_graphics.py` | `plan_memory()` | Memory planning |
| `nokia_shapes.py` | `Shapes` | Advanced 2D graphics |
| `nokia_shapes.py` | `Sprite` | Transparent image objects |
| `nokia_shapes.py` | `sine()` | Integer sine calculation |
| `nokia_shapes.py` | `cosine()` | Integer cosine calculation |
| `nokia_shapes.py` | `integer_square_root()` | Integer square root |
| `nokia_3d.py` | `Mesh` | Custom 3D geometry |
| `nokia_3d.py` | `Object3D` | 3D rendering |
| `nokia_3d.py` | `make_box()` | Box geometry |
| `nokia_3d.py` | `make_cube()` | Cube geometry |
| `nokia_3d.py` | `make_cylinder()` | Cylinder geometry |
| `nokia_3d.py` | `make_cone()` | Cone geometry |
| `nokia_3d.py` | `make_pyramid()` | Pyramid geometry |
| `nokia_3d.py` | `make_sphere()` | Sphere geometry |
| `nokia_3d.py` | `make_torus()` | Torus geometry |
| `nokia_3d.py` | `make_octahedron()` | Octahedron geometry |
| `nokia_3d.py` | `make_icosahedron()` | Icosahedron geometry |
| `nokia_3d.py` | `rotation_matrix()` | 3D rotation calculation |
| `nokia_3d.py` | `shade_colour()` | RGB565 brightness adjustment |
| `nokia_font.py` | `Font` | Custom font rendering |
| `nokia_text_motion.py` | `Marquee` | Horizontal scrolling text |
| `nokia_text_motion.py` | `VerticalScroller` | Vertical scrolling text |
| `nokia_text_motion.py` | `MessageRoller` | Rolling messages |
| `nokia_text_motion.py` | `draw_wavy_text()` | Wave animation |
| `nokia_text_motion.py` | `draw_text_on_circle()` | Circular text |
| `nokia_text_motion.py` | `draw_typewriter()` | Typewriter animation |
| `nokia_text_motion.py` | `fly_in_position()` | Animated position calculation |
| `nokia_text_motion.py` | `fade_colour()` | Text fade effect |
| `nokia_text_motion.py` | `blend_colours()` | RGB565 colour blending |
| `nokia_text_motion.py` | `progress_of()` | Animation progress calculation |
| `nokia_dma_link.py` | `SpiDmaLink` | Hardware SPI DMA |
| `nokia_dma_link.py` | `PioDmaLink` | PIO DMA |

---

# End of API Reference

This document describes the application-facing APIs and the low-level DMA and acceleration helpers found in the supplied project files.

For normal application development, the main classes to use are:

    Display
    Screen
    Shapes
    Sprite
    Font
    Object3D
    Marquee
    VerticalScroller
    MessageRoller

The optional fast-helper modules are selected automatically by their corresponding main modules.