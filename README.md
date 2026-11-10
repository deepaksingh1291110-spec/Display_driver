
# Nokia Display Driver for Raspberry Pi Pico 2

A MicroPython display-driver project for a 128 × 160 colour phone display, developed for the Raspberry Pi Pico 2 (RP2350).

> **AI-assisted development:** I used **Claude (Anthropic)** to help create the driver files in this project. The code and project structure were developed with Claude's assistance. Please review and test the code on your own hardware before relying on it.

## Project Overview

This project provides a collection of MicroPython modules for controlling a small colour display and drawing graphics on it.

The display is believed to be a Nokia 1616 replacement display. Its controller is thought to be ST7735S-compatible, but that identification has not been confirmed.

The project explores several ways to transfer display data, including software bit-banging, hardware SPI, SPI with DMA, and PIO with DMA.

## Hardware and Interface

| Item | Configuration |
|---|---|
| Microcontroller | Raspberry Pi Pico 2 (RP2350) |
| Runtime | MicroPython v1.29.0 |
| Display resolution | 128 × 160 pixels |
| Pixel format | RGB565 |
| Serial protocol | 9-bit command/data transfer |
| Clock | GPIO 6 |
| Data | GPIO 7 |
| Chip select (CS) | GPIO 5 |
| Reset | GPIO 4 |

**Important:** The display-controller identification and some hardware/protocol details are not fully confirmed.

## Main Features

- Display initialization and pixel drawing
- RGB565 colour handling
- Full-frame and strip-based rendering
- Framebuffer change tracking
- Bit-banging transfer
- Hardware SPI
- SPI + DMA
- PIO + DMA
- 2D drawing primitives
- Graphics and shape helpers
- Sprite support
- NKF bitmap-font support
- Font-generation utility
- Text animation
- Experimental 3D mesh rendering

## Project Files

| File | Purpose |
|---|---|
| `nokia_display.py` | Main display-driver implementation |
| `nokia_fast.py` | Faster display implementation |
| `nokia_graphics.py` | Graphics helpers |
| `nokia_dma_link.py` | DMA-related transfer support |
| `nokia_shapes.py` | Shape-drawing helpers |
| `nokia_shapes_fast.py` | Faster shape-drawing helpers |
| `nokia_font.py` | Font rendering support |
| `nokia_font_fast.py` | Faster font rendering support |
| `nokia_text_motion.py` | Text animation helpers |
| `nokia_3d.py` | 3D rendering experiments |
| `make_font.py` | Font-generation utility |
| `*.nkf` | Project font files |

## Getting Started

1. Use a Raspberry Pi Pico 2 with a compatible MicroPython build.
2. Connect the display using the GPIO assignments listed above.
3. Copy the required driver modules and assets to the Pico 2.
4. Review the initialization and example code in the selected module.
5. Run the relevant test or example script.

Different modules may have different initialization requirements and APIs.

## Performance Notes

The project contains multiple rendering and transfer approaches.

PIO + DMA is the recommended direction in the project reference documentation. Actual performance depends on the hardware, MicroPython build, and test conditions.

## Documentation

See [`Reference.md`](Reference.md) for detailed information about:

- Hardware and display protocol
- Driver architecture
- Rendering and memory modes
- Transfer backends
- Graphics and font systems
- Performance benchmarks
- Troubleshooting
- Known limitations

## Status and Limitations

This is an experimental hardware-specific project.

- The exact display controller has not been conclusively identified.
- Not every hardware or protocol detail has been independently verified.
- Some modules and features may be experimental.
- Verify pin assignments, voltage requirements, and initialization sequences before using different hardware.
- Review and test AI-assisted code carefully.

## Development Credit

The driver files were created with assistance from **Claude by Anthropic**, which I used during development.

This note is included for transparency about the use of AI assistance.

## License

No license is specified yet. Add a `LICENSE` file if you want to grant others explicit permission to use, modify, or distribute this project.
