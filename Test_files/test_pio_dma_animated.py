"""
Animated experiment: DMA and PIO for sending the picture to the display.

On the Pico you need: nokia_display.py (the new one) and nokia_fast.py.
It does not use Screen.

WHY ANIMATED
A still picture proves nothing: if the display ignored a transfer, the old
picture would stay on the screen and look right. Here the test picture
moves up by ONE row in EVERY frame, so every frame is different. At each
setting the bars scroll upwards. How fast they scroll shows how many
frames per second really arrive.

WHAT TO LOOK FOR (for each setting, written in the console)
  CORRECT   smooth upward scrolling, sharp bars, steady fine lines
  WRONG     noise or sparkles, flickering colours, bars that tear or jump,
            a picture that stops moving, wrong colours, a black screen
Write down the first setting that looks wrong, if any.

THE PICTURE (it repeats every 160 rows so it scrolls without a seam)
  8 colour bars: red green blue yellow cyan magenta white black
  fine 1 pixel white / black vertical lines
  a smooth grey ramp
  a blue / yellow checkerboard

WHAT WE LEARNED FROM THE FIRST EXPERIMENT (so the numbers here make sense)
  The hardware SPI on your Pico runs from a 48 MHz clock, so it can never go
  faster than 24 MHz, however much you ask for. PIO has no such limit.
"""
import time
import framebuf
from machine import Pin, mem32, freq

import nokia_display
from nokia_display import Display

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4

ANIMATION_SECONDS = 5

RUN_SPI_BLOCKING = True
RUN_SPI_WITH_DMA = True
RUN_PIO_WITH_DMA = True

SPI_BLOCKING_SPEEDS_HZ = (12000000, 24000000)
SPI_DMA_SPEEDS_HZ = (24000000,)
PIO_SPEEDS_HZ = (25000000, 32000000, 40000000, 50000000, 62500000, 75000000)

# ---- RP2350 hardware numbers (these worked in the first experiment) ----
SPI_PERIPHERAL_CLOCK_HZ = 48000000     # what the SPI hardware runs from
SPI0_BASE = 0x40080000
SPI_CONTROL_0 = 0x000
SPI_DATA = 0x008
SPI_STATUS = 0x00C
SPI_PRESCALE = 0x010
SPI_DMA_CONTROL = 0x024
DMA_REQUEST_SPI0_TX = 24
PIO0_TX_FIFO_0 = 0x50200010
DMA_REQUEST_PIO0_TX_0 = 0

WIDTH = 128
HEIGHT = 160
ROW_BYTES = WIDTH * 2                   # 256
PACKED_ROW_BYTES = ROW_BYTES // 8 * 9   # 288: the same row as 9-bit words
FRAME_BYTES = ROW_BYTES * HEIGHT        # 40,960
PACKED_FRAME_BYTES = PACKED_ROW_BYTES * HEIGHT   # 46,080

results = []


def swap(colour):
    return ((colour & 0xFF) << 8) | (colour >> 8)


def draw_pattern(frame, top):
    bars = (0xF800, 0x07E0, 0x001F, 0xFFE0, 0x07FF, 0xF81F, 0xFFFF, 0x0000)
    for number in range(8):
        frame.fill_rect(number * 16, top, 16, 40, swap(bars[number]))
    for x in range(WIDTH):
        frame.fill_rect(x, top + 40, 1, 40, swap(0xFFFF if x % 2 == 0 else 0x0000))
    for step in range(32):
        level = step * 8
        grey = ((level & 0xF8) << 8) | ((level & 0xFC) << 3) | (level >> 3)
        frame.fill_rect(step * 4, top + 80, 4, 40, swap(grey))
    for row in range(10):
        for column in range(32):
            colour = 0x001F if (row + column) % 2 == 0 else 0xFFE0
            frame.fill_rect(column * 4, top + 120 + row * 4, 4, 4, swap(colour))


def make_tall_pictures():
    """Two copies of the picture, one under the other (320 rows). Sending 160
    rows that start at row k shows the picture scrolled up by k rows.
    Returns (raw pixels, the same packed into 9-bit words)."""
    pixels = bytearray(ROW_BYTES * HEIGHT * 2)
    frame = framebuf.FrameBuffer(pixels, WIDTH, HEIGHT * 2, framebuf.RGB565)
    draw_pattern(frame, 0)
    draw_pattern(frame, HEIGHT)
    packed = bytearray(len(pixels) // 8 * 9)
    try:
        import nokia_fast
        nokia_fast.pack_data(pixels, 0, packed, len(pixels))
    except Exception:
        packed = Display._pack_data_bytes(pixels)
    return pixels, packed


def spin():
    total = 0
    for number in range(100):
        total += number
    return total


def spins_per_millisecond():
    count = 0
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 100:
        spin()
        count += 1
    return count / 100


def spi_real_speed():
    control = mem32[SPI0_BASE + SPI_CONTROL_0]
    prescale = mem32[SPI0_BASE + SPI_PRESCALE] & 0xFF
    divider = (control >> 8) & 0xFF
    looks_right = (control & 0xCF) == 0xC7
    if prescale == 0:
        return (0, False)
    return (SPI_PERIPHERAL_CLOCK_HZ / (prescale * (divider + 1)), looks_right)


def prepare_window(display):
    display.set_window(0, 0, WIDTH - 1, HEIGHT - 1)


def announce(text):
    print()
    print(">>> NOW ON THE DISPLAY:", text)
    print("    correct = bars scroll upward smoothly; wrong = noise, flicker, tearing, frozen")


def finish(name, setting, frames, milliseconds, send_microseconds, spins, idle_spins):
    fps = frames * 1000 / milliseconds
    send_ms = send_microseconds / frames / 1000
    cpu_free = None
    if spins is not None:
        expected = idle_spins * send_microseconds / 1000
        cpu_free = min(100, 100 * spins / expected) if expected > 0 else 0
    results.append((name, setting, fps, send_ms, cpu_free))
    text = "    %d frames in %.1f s = %.1f FPS   (sending one picture takes %.2f ms)" % (
        frames, milliseconds / 1000, fps, send_ms)
    if cpu_free is not None:
        text += "   CPU free %.0f %%" % cpu_free
    print(text)


# ===============================
# SPI, the CPU waits
# ===============================
def animate_spi_blocking(display, packed_view, requested_hz, idle_spins):
    display.use_hardware_spi(requested_hz)
    real, looks_right = spi_real_speed()
    setting = "%.1f MHz" % (real / 1000000)
    announce("SPI %s, the CPU waits" % setting)
    frames = 0
    send_total = 0
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < ANIMATION_SECONDS * 1000:
        offset = (frames % HEIGHT) * PACKED_ROW_BYTES
        prepare_window(display)
        display._select_pin.low()
        started = time.ticks_us()
        display._spi.write(packed_view[offset:offset + PACKED_FRAME_BYTES])
        send_total += time.ticks_diff(time.ticks_us(), started)
        display._select_pin.high()
        frames += 1
    milliseconds = time.ticks_diff(time.ticks_ms(), start)
    finish("SPI, CPU waits", setting, frames, milliseconds, send_total, None, idle_spins)


# ===============================
# SPI with DMA
# ===============================
def animate_spi_dma(display, packed_view, requested_hz, idle_spins):
    import rp2
    display.use_hardware_spi(requested_hz)
    mem32[SPI0_BASE + SPI_DMA_CONTROL] = mem32[SPI0_BASE + SPI_DMA_CONTROL] | 2
    real, looks_right = spi_real_speed()
    if not looks_right:
        raise RuntimeError("SPI 0 registers are not where I expected: not touching them")
    setting = "%.1f MHz" % (real / 1000000)
    announce("SPI %s with DMA" % setting)

    dma = rp2.DMA()
    control = dma.pack_ctrl(size=0, inc_read=True, inc_write=False,
                            treq_sel=DMA_REQUEST_SPI0_TX)
    frames = 0
    send_total = 0
    spin_total = 0
    start = time.ticks_ms()
    try:
        while time.ticks_diff(time.ticks_ms(), start) < ANIMATION_SECONDS * 1000:
            offset = (frames % HEIGHT) * PACKED_ROW_BYTES
            prepare_window(display)
            dma.config(read=packed_view[offset:offset + PACKED_FRAME_BYTES],
                       write=SPI0_BASE + SPI_DATA, count=PACKED_FRAME_BYTES, ctrl=control)
            display._select_pin.low()
            started = time.ticks_us()
            dma.active(True)
            deadline = time.ticks_add(time.ticks_ms(), 300)
            while dma.active():
                spin()
                spin_total += 1
                if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                    raise RuntimeError("DMA to SPI made no progress")
            while mem32[SPI0_BASE + SPI_STATUS] & 0x10:
                pass
            send_total += time.ticks_diff(time.ticks_us(), started)
            display._select_pin.high()
            frames += 1
    finally:
        dma.active(False)
        dma.close()
        display._select_pin.high()
    milliseconds = time.ticks_diff(time.ticks_ms(), start)
    finish("SPI + DMA", setting, frames, milliseconds, send_total, spin_total, idle_spins)


# ===============================
# PIO with DMA
# ===============================
PIO_PROGRAM_ERROR = None
try:
    import rp2

    # Sends one byte as a 9-bit word: a 1 first (it means "this is data"),
    # then the 8 bits of the byte, most significant bit first.
    @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=rp2.PIO.OUT_LOW,
                 set_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT,
                 autopull=False)
    def data_byte_writer():
        pull(block)            .side(0)
        set(pins, 1)           .side(0)
        set(x, 7)              .side(1)
        label("next_bit")
        out(pins, 1)           .side(0)
        jmp(x_dec, "next_bit") .side(1)
except Exception as error:
    PIO_PROGRAM_ERROR = error


def animate_pio_dma(display, pixel_view, bit_clock_hz, idle_spins):
    if PIO_PROGRAM_ERROR is not None:
        raise RuntimeError("the PIO program did not assemble: " + str(PIO_PROGRAM_ERROR))
    state_machine_speed = bit_clock_hz * 2
    if state_machine_speed > freq():
        print("    skipping %.1f MHz (faster than the PIO clock)" % (bit_clock_hz / 1000000))
        return
    setting = "%.1f MHz" % (bit_clock_hz / 1000000)
    announce("PIO + DMA at %s" % setting)

    frames = 0
    send_total = 0
    spin_total = 0
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < ANIMATION_SECONDS * 1000:
        offset = (frames % HEIGHT) * ROW_BYTES
        display.use_bit_banging()          # pins back to normal outputs for the commands
        prepare_window(display)

        state_machine = rp2.StateMachine(
            0, data_byte_writer, freq=state_machine_speed,
            sideset_base=Pin(CLOCK_PIN), out_base=Pin(DATA_PIN), set_base=Pin(DATA_PIN))
        dma = rp2.DMA()
        control = dma.pack_ctrl(size=0, inc_read=True, inc_write=False,
                                treq_sel=DMA_REQUEST_PIO0_TX_0)
        dma.config(read=pixel_view[offset:offset + FRAME_BYTES], write=PIO0_TX_FIFO_0,
                   count=FRAME_BYTES, ctrl=control)

        display._select_pin.low()
        state_machine.active(1)
        started = time.ticks_us()
        dma.active(True)
        failed = False
        deadline = time.ticks_add(time.ticks_ms(), 300)
        while dma.active():
            spin()
            spin_total += 1
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                failed = True
                break
        if not failed:
            while state_machine.tx_fifo() > 0:
                if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                    failed = True
                    break
            time.sleep_us(40)
        send_total += time.ticks_diff(time.ticks_us(), started)

        state_machine.active(0)
        dma.active(False)
        dma.close()
        display._select_pin.high()
        rp2.PIO(0).remove_program()
        if failed:
            display.use_bit_banging()
            raise RuntimeError("PIO + DMA made no progress")
        frames += 1
    display.use_bit_banging()
    milliseconds = time.ticks_diff(time.ticks_ms(), start)
    finish("PIO + DMA", setting, frames, milliseconds, send_total, spin_total, idle_spins)


def main():
    print("System clock:", freq() // 1000000, "MHz")
    pixels, packed = make_tall_pictures()
    pixel_view = memoryview(pixels)
    packed_view = memoryview(packed)
    idle_spins = spins_per_millisecond()
    print("Idle CPU: %.1f work units per millisecond" % idle_spins)

    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN)
    display.start()
    display.use_hardware_spi(24000000)

    runs = []
    if RUN_SPI_BLOCKING:
        for speed in SPI_BLOCKING_SPEEDS_HZ:
            runs.append(("SPI blocking %d" % speed,
                         lambda speed=speed: animate_spi_blocking(display, packed_view, speed, idle_spins)))
    if RUN_SPI_WITH_DMA:
        for speed in SPI_DMA_SPEEDS_HZ:
            runs.append(("SPI + DMA %d" % speed,
                         lambda speed=speed: animate_spi_dma(display, packed_view, speed, idle_spins)))
    if RUN_PIO_WITH_DMA:
        for speed in PIO_SPEEDS_HZ:
            runs.append(("PIO + DMA %d" % speed,
                         lambda speed=speed: animate_pio_dma(display, pixel_view, speed, idle_spins)))

    for name, run in runs:
        try:
            run()
        except Exception as error:
            print("   !!", name, "FAILED:", type(error).__name__, error)
            try:
                display._select_pin.high()
            except Exception:
                pass
        time.sleep(1)

    print()
    print("===== SUMMARY: full-screen frames per second (every frame different) =====")
    base = None
    for name, setting, fps, send_ms, cpu_free in results:
        if name == "SPI, CPU waits" and setting.startswith("24"):
            base = fps
    for name, setting, fps, send_ms, cpu_free in results:
        line = "%-16s %-10s %6.1f FPS   send %5.2f ms" % (name, setting, fps, send_ms)
        if cpu_free is not None:
            line += "   CPU free %3.0f %%" % cpu_free
        if base:
            line += "   (%.1fx the 24 MHz SPI)" % (fps / base)
        print(line)
    print("Now tell me, for each setting, if the scrolling looked CORRECT or WRONG.")


main()
