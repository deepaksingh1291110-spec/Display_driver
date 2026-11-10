"""
Experiment: DMA and PIO for sending the picture to the display.

On the Pico you need: nokia_display.py (the new one) and nokia_fast.py.
Nothing else. It does not use Screen.

WHAT IT ANSWERS
  Stage 1  Does DMA work at all on your Pico? (memory to memory, no display)
  Stage 2  What SPI speed do you REALLY get when you ask for 32 MHz, and does
           the display work at the faster speeds the SPI can make (37.5 and 75 MHz)?
  Stage 3  Can DMA send the picture through the SPI while the CPU does other work?
  Stage 4  Does PIO + DMA work, how fast can the display be driven, and how much
           CPU is left over?

HOW TO READ THE SCREEN
  After every setting the test picture stays on the display for SHOW_SECONDS.
  Look at it. A correct picture has:
     top band     8 colour bars: red green blue yellow cyan magenta white black
     2nd band     fine white / black vertical lines (1 pixel each)
     3rd band     a smooth grey ramp from black to white
     bottom band  a blue / yellow checkerboard
  If the speed is too high for the display you will see noise, wrong colours,
  shifted bars or a black screen. Write down which settings looked right.
  The console says which setting is on the screen at that moment.

Each stage is separate: if one fails it prints the reason and the next
stage still runs. Every wait has a time limit, so the Pico cannot hang.
You can switch stages off below.
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

RUN_STAGE_1_DMA_COPY = True
RUN_STAGE_2_SPI_SPEEDS = True
RUN_STAGE_3_DMA_THROUGH_SPI = True
RUN_STAGE_4_PIO_AND_DMA = True

SHOW_SECONDS = 3
REPEATS = 5

# Speeds the SPI hardware can make from a 150 MHz clock: 150 / (2 * n)
SPI_SPEEDS_HZ = (18750000, 25000000, 37500000, 75000000)
# Bit clocks to try with PIO (it can make almost any speed)
PIO_SPEEDS_HZ = (25000000, 32000000, 40000000, 50000000, 62500000, 75000000)

# ---- RP2350 hardware numbers (from the RP2350 datasheet) ----
SPI0_BASE = 0x40080000          # SPI 0 registers
SPI_CONTROL_0 = 0x000
SPI_DATA = 0x008
SPI_STATUS = 0x00C              # bit 4 = still shifting bits out
SPI_PRESCALE = 0x010
SPI_DMA_CONTROL = 0x024         # bit 1 = ask the DMA for more data
DMA_REQUEST_SPI0_TX = 24        # on the RP2040 this number was 16
PIO0_TX_FIFO_0 = 0x50200010     # where bytes go into PIO 0 state machine 0
DMA_REQUEST_PIO0_TX_0 = 0
DMA_REQUEST_ALWAYS = 0x3F       # "no pacing": for memory to memory

WIDTH = 128
HEIGHT = 160

results = []


def swap(colour):
    return ((colour & 0xFF) << 8) | (colour >> 8)


def make_test_picture():
    pixels = bytearray(WIDTH * HEIGHT * 2)
    frame = framebuf.FrameBuffer(pixels, WIDTH, HEIGHT, framebuf.RGB565)
    bars = (0xF800, 0x07E0, 0x001F, 0xFFE0, 0x07FF, 0xF81F, 0xFFFF, 0x0000)
    for number in range(8):
        frame.fill_rect(number * 16, 0, 16, 40, swap(bars[number]))
    for x in range(WIDTH):
        frame.fill_rect(x, 40, 1, 40, swap(0xFFFF if x % 2 == 0 else 0x0000))
    for step in range(32):
        level = step * 8
        grey = ((level & 0xF8) << 8) | ((level & 0xFC) << 3) | (level >> 3)
        frame.fill_rect(step * 4, 80, 4, 40, swap(grey))
    for row in range(10):
        for column in range(32):
            colour = 0x001F if (row + column) % 2 == 0 else 0xFFE0
            frame.fill_rect(column * 4, 120 + row * 4, 4, 4, swap(colour))
    return pixels


def spin():
    # A small piece of Python work. How many we manage while the picture is
    # being sent tells us how much of the CPU is left over.
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


def cpu_free_percent(spin_count, microseconds, idle_spins_per_ms):
    expected = idle_spins_per_ms * microseconds / 1000
    if expected <= 0:
        return 0
    return min(100, 100 * spin_count / expected)


def pack_picture(pixels):
    packed = bytearray(len(pixels) // 8 * 9)
    try:
        import nokia_fast
        nokia_fast.pack_data(pixels, 0, packed, len(pixels))
    except Exception:
        packed = Display._pack_data_bytes(pixels)
    return packed


def spi_real_speed():
    """The real SPI 0 speed, read back from the chip's registers.
    Returns (speed_hz, registers_look_right)."""
    control = mem32[SPI0_BASE + SPI_CONTROL_0]
    prescale = mem32[SPI0_BASE + SPI_PRESCALE] & 0xFF
    divider = (control >> 8) & 0xFF
    looks_right = (control & 0xCF) == 0xC7           # 8 bit words, mode 3
    if prescale == 0:
        return (0, False)
    return (freq() / (prescale * (divider + 1)), looks_right)


def prepare_window(display):
    display.set_window(0, 0, WIDTH - 1, HEIGHT - 1)


def send_blocking(display, packed):
    display._select_pin.low()
    start = time.ticks_us()
    display._spi.write(packed)
    elapsed = time.ticks_diff(time.ticks_us(), start)
    display._select_pin.high()
    return elapsed


def record(name, setting, microseconds, cpu_free):
    results.append((name, setting, microseconds, cpu_free))
    text = "   %-26s %-14s send %6.2f ms  -> at most %5.1f FPS" % (
        name, setting, microseconds / 1000, 1000000 / microseconds)
    if cpu_free is not None:
        text += "   CPU free %3.0f %%" % cpu_free
    print(text)


# ===============================
# STAGE 1: DMA memory to memory
# ===============================
def stage_1():
    import rp2
    print("\n=== STAGE 1: does DMA work? ===")
    source = bytearray([(number * 7 + 3) & 0xFF for number in range(8192)])
    target = bytearray(8192)
    dma = rp2.DMA()
    control = dma.pack_ctrl(size=2, inc_read=True, inc_write=True,
                            treq_sel=DMA_REQUEST_ALWAYS)
    start = time.ticks_us()
    for repeat in range(REPEATS):
        dma.config(read=source, write=target, count=len(source) // 4, ctrl=control,
                   trigger=True)
        deadline = time.ticks_add(time.ticks_ms(), 200)
        while dma.active():
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                raise RuntimeError("DMA copy did not finish in 200 ms")
    elapsed = time.ticks_diff(time.ticks_us(), start) // REPEATS
    dma.close()
    print("   copy correct:", source == target)
    print("   8192 bytes in %d us = %.1f MB per second" % (elapsed, 8192 / elapsed))


# ===============================
# STAGE 2: SPI speeds, blocking writes
# ===============================
def stage_2(display, packed):
    print("\n=== STAGE 2: real SPI speed and fast SPI speeds (the CPU waits) ===")
    for requested in SPI_SPEEDS_HZ:
        display.use_hardware_spi(requested)
        real, looks_right = spi_real_speed()
        prepare_window(display)
        total = 0
        for repeat in range(REPEATS):
            prepare_window(display)
            total += send_blocking(display, packed)
        record("SPI, CPU waits", "%.2f MHz" % (real / 1000000), total // REPEATS, 0)
        print("      asked for %.2f MHz, the registers say %.2f MHz (registers look %s)"
              % (requested / 1000000, real / 1000000, "right" if looks_right else "WRONG"))
        print("      >>> LOOK AT THE DISPLAY NOW (SPI %.2f MHz)" % (real / 1000000))
        time.sleep(SHOW_SECONDS)


# ===============================
# STAGE 3: DMA through the SPI
# ===============================
def stage_3(display, packed, idle_spins):
    import rp2
    print("\n=== STAGE 3: DMA through the SPI (the CPU is free while it sends) ===")
    display.use_hardware_spi(25000000)
    real, looks_right = spi_real_speed()
    print("   SPI registers look %s (control %s)" % (
        "right" if looks_right else "WRONG",
        hex(mem32[SPI0_BASE + SPI_CONTROL_0])))
    if not looks_right:
        raise RuntimeError("SPI 0 registers are not where I expected: not touching them")

    mem32[SPI0_BASE + SPI_DMA_CONTROL] = mem32[SPI0_BASE + SPI_DMA_CONTROL] | 2

    for requested in (25000000, 37500000):
        display.use_hardware_spi(requested)
        mem32[SPI0_BASE + SPI_DMA_CONTROL] = mem32[SPI0_BASE + SPI_DMA_CONTROL] | 2
        real, looks_right = spi_real_speed()
        dma = rp2.DMA()
        control = dma.pack_ctrl(size=0, inc_read=True, inc_write=False,
                                treq_sel=DMA_REQUEST_SPI0_TX)
        total_time = 0
        total_spins = 0
        for repeat in range(REPEATS):
            prepare_window(display)
            dma.config(read=packed, write=SPI0_BASE + SPI_DATA, count=len(packed),
                       ctrl=control)
            display._select_pin.low()
            start = time.ticks_us()
            dma.active(True)
            spins = 0
            deadline = time.ticks_add(time.ticks_ms(), 300)
            while dma.active():
                spin()
                spins += 1
                if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                    dma.active(False)
                    dma.close()
                    display._select_pin.high()
                    raise RuntimeError("DMA to SPI made no progress (wrong request number "
                                       "%d?)" % DMA_REQUEST_SPI0_TX)
            # the last bytes are still in the SPI FIFO
            while mem32[SPI0_BASE + SPI_STATUS] & 0x10:
                pass
            elapsed = time.ticks_diff(time.ticks_us(), start)
            display._select_pin.high()
            total_time += elapsed
            total_spins += spins
        dma.close()
        average = total_time // REPEATS
        record("SPI + DMA", "%.2f MHz" % (real / 1000000), average,
               cpu_free_percent(total_spins // REPEATS, average, idle_spins))
        print("      >>> LOOK AT THE DISPLAY NOW (SPI + DMA %.2f MHz)" % (real / 1000000))
        time.sleep(SHOW_SECONDS)


# ===============================
# STAGE 4: PIO + DMA
# ===============================
PIO_PROGRAM_ERROR = None
try:
    import rp2

    # Sends one byte as a 9-bit word: a 1 first (it means "this is data"),
    # then the 8 bits of the byte, most significant bit first. The clock
    # goes low while a bit is put on the data pin, then high.
    @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=rp2.PIO.OUT_LOW,
                 set_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT,
                 autopull=False)
    def data_byte_writer():
        pull(block)            .side(0)       # wait for the next byte, clock low
        set(pins, 1)           .side(0)       # the "data" bit
        set(x, 7)              .side(1)       # clock high: the bit is taken
        label("next_bit")
        out(pins, 1)           .side(0)       # next bit of the byte, clock low
        jmp(x_dec, "next_bit") .side(1)       # clock high: the bit is taken
except Exception as error:
    PIO_PROGRAM_ERROR = error


def stage_4(display, pixels, idle_spins):
    print("\n=== STAGE 4: PIO + DMA (no packing: the raw picture bytes go straight out) ===")
    if PIO_PROGRAM_ERROR is not None:
        raise RuntimeError("the PIO program did not assemble: " + str(PIO_PROGRAM_ERROR))

    for bit_clock in PIO_SPEEDS_HZ:
        state_machine_speed = bit_clock * 2
        if state_machine_speed > freq():
            print("   skipping %.1f MHz (faster than the PIO clock %d MHz / 2)"
                  % (bit_clock / 1000000, freq() // 1000000))
            continue

        total_time = 0
        total_spins = 0
        for repeat in range(REPEATS):
            display.use_bit_banging()          # the pins go back to normal outputs
            prepare_window(display)            # commands are sent slowly, that is fine

            state_machine = rp2.StateMachine(
                0, data_byte_writer, freq=state_machine_speed,
                sideset_base=Pin(CLOCK_PIN), out_base=Pin(DATA_PIN),
                set_base=Pin(DATA_PIN))
            dma = rp2.DMA()
            control = dma.pack_ctrl(size=0, inc_read=True, inc_write=False,
                                    treq_sel=DMA_REQUEST_PIO0_TX_0)
            dma.config(read=pixels, write=PIO0_TX_FIFO_0, count=len(pixels), ctrl=control)

            display._select_pin.low()
            state_machine.active(1)
            start = time.ticks_us()
            dma.active(True)
            spins = 0
            failed = False
            deadline = time.ticks_add(time.ticks_ms(), 300)
            while dma.active():
                spin()
                spins += 1
                if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                    failed = True
                    break
            if not failed:
                while state_machine.tx_fifo() > 0:
                    if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                        failed = True
                        break
                time.sleep_us(40)              # the last byte is still being shifted out
            elapsed = time.ticks_diff(time.ticks_us(), start)

            state_machine.active(0)
            dma.active(False)
            dma.close()
            display._select_pin.high()
            rp2.PIO(0).remove_program()
            if failed:
                display.use_bit_banging()
                raise RuntimeError("PIO + DMA made no progress (request number or "
                                   "FIFO address wrong?)")
            total_time += elapsed
            total_spins += spins

        average = total_time // REPEATS
        record("PIO + DMA", "%.1f MHz" % (bit_clock / 1000000), average,
               cpu_free_percent(total_spins // REPEATS, average, idle_spins))
        print("      >>> LOOK AT THE DISPLAY NOW (PIO + DMA %.1f MHz)" % (bit_clock / 1000000))
        time.sleep(SHOW_SECONDS)
    display.use_bit_banging()


def main():
    print("System clock:", freq() // 1000000, "MHz")
    pixels = make_test_picture()
    packed = pack_picture(pixels)
    idle_spins = spins_per_millisecond()
    print("Idle CPU: %.1f work units per millisecond" % idle_spins)

    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN)
    display.start()
    display.use_hardware_spi(25000000)

    stages = (
        (RUN_STAGE_1_DMA_COPY, "stage 1", lambda: stage_1()),
        (RUN_STAGE_2_SPI_SPEEDS, "stage 2", lambda: stage_2(display, packed)),
        (RUN_STAGE_3_DMA_THROUGH_SPI, "stage 3", lambda: stage_3(display, packed, idle_spins)),
        (RUN_STAGE_4_PIO_AND_DMA, "stage 4", lambda: stage_4(display, pixels, idle_spins)),
    )
    for enabled, name, run in stages:
        if not enabled:
            continue
        try:
            run()
        except Exception as error:
            print("   !!", name, "FAILED:", type(error).__name__, error)
            try:
                display._select_pin.high()
            except Exception:
                pass

    print("\n===== SUMMARY (time to send one full picture) =====")
    for name, setting, microseconds, cpu_free in results:
        line = "%-16s %-12s %6.2f ms  (%5.1f FPS at most)" % (
            name, setting, microseconds / 1000, 1000000 / microseconds)
        if cpu_free is not None and cpu_free > 0:
            line += "  CPU free %3.0f %%" % cpu_free
        print(line)
    print("Now tell me which settings showed a CORRECT picture on the display.")


main()
