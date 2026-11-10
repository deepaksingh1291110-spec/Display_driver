"""
nokia_dma_link.py - send the pixels with DMA, through the SPI or through PIO

Copy this file to the Pico next to nokia_display.py. You do not use it
directly. You switch it on with one call on the Display:

    display.use_spi_dma()                # hardware SPI + DMA   (24 MHz at most)
    display.use_pio_dma(62500000)        # PIO + DMA            (25 to 75 MHz tested)
    screen = Screen(display, ...)        # Screen sends its pictures that way

Both ways leave the CPU free while the pixels go out (97 to 99 % in the
test). Only PIO + DMA is faster than the plain hardware SPI.

SPI + DMA
    The 9-bit words are packed in pieces. While the DMA sends one piece the
    CPU packs the next one, so the packing costs no extra time.

PIO + DMA
    The raw picture bytes go straight from the Screen buffer to a PIO state
    machine. The state machine puts a 1 ("this is data") in front of every
    byte and clocks the nine bits out. Nothing is packed. The DMA writes one
    byte at a time and the chip repeats that byte in all four bytes of the
    word that enters the PIO queue; the PIO program reads the top byte.
    The pins belong to PIO only while pixels are being sent. The commands
    (the window before every picture) are sent by bit-banging in between.
    start_raw() comes back at once and the picture goes out in the background;
    wait() finishes it. Screen uses this to draw the next frame meanwhile.

The numbers below are the RP2350 ones, checked on a Pico 2 with this display.
Every wait has a time limit, so a wrong number gives an error, not a hang.
"""
import time
from machine import Pin, mem32, freq
import rp2

# ---- RP2350 hardware numbers ----
SPI0_BASE = 0x40080000
SPI_CONTROL_0 = 0x000
SPI_DATA = 0x008
SPI_STATUS = 0x00C              # bit 4: the SPI is still shifting bits out
SPI_DMA_CONTROL = 0x024         # bit 1: ask the DMA for more data
DMA_REQUEST_SPI0_TX = 24
PIO0_TX_FIFO_0 = 0x50200010     # where bytes enter PIO 0, state machine 0
DMA_REQUEST_PIO0_TX_0 = 0

TIMEOUT_MILLISECONDS = 500


# Sends one byte as a 9-bit word: a 1 first (it means "this is data"), then
# the 8 bits of the byte, most significant bit first. The clock is low while a
# bit is put on the data pin and goes high to make the display take it.
@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_init=rp2.PIO.OUT_LOW,
             set_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT,
             autopull=False)
def _data_byte_writer():
    pull(block)            .side(0)       # wait for the next byte, clock low
    set(pins, 1)           .side(0)       # the "data" bit
    set(x, 7)              .side(1)       # clock high: the bit is taken
    label("next_bit")
    out(pins, 1)           .side(0)       # next bit of the byte, clock low
    jmp(x_dec, "next_bit") .side(1)       # clock high: the bit is taken


class SpiDmaLink:
    name = "SPI + DMA"
    takes_raw_pixels = False
    in_flight = False               # a picture is never left going out between calls

    def __init__(self, display):
        control = mem32[SPI0_BASE + SPI_CONTROL_0]
        if (control & 0xCF) != 0xC7:
            raise RuntimeError("SPI 0 registers are not as expected (control "
                               + hex(control) + "): not using DMA")
        mem32[SPI0_BASE + SPI_DMA_CONTROL] = mem32[SPI0_BASE + SPI_DMA_CONTROL] | 2
        self._dma = rp2.DMA()
        self._control = self._dma.pack_ctrl(size=0, inc_read=True, inc_write=False,
                                            treq_sel=DMA_REQUEST_SPI0_TX)

    def start(self, packed, byte_count):
        """Start sending byte_count bytes of 'packed' and come back at once.
        Chip select must already be low."""
        self._dma.config(read=packed, write=SPI0_BASE + SPI_DATA, count=byte_count,
                         ctrl=self._control)
        self._dma.active(True)

    def wait(self):
        """Wait until everything started has left the SPI."""
        deadline = time.ticks_add(time.ticks_ms(), TIMEOUT_MILLISECONDS)
        while self._dma.active():
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                self._dma.active(False)
                raise RuntimeError("DMA to SPI made no progress")
        while mem32[SPI0_BASE + SPI_STATUS] & 0x10:
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                raise RuntimeError("the SPI did not finish sending")

    def close(self):
        self._dma.active(False)
        self._dma.close()


class PioDmaLink:
    takes_raw_pixels = True

    def __init__(self, display, bit_clock_hz, command_delay_microseconds=0):
        if bit_clock_hz * 2 > freq():
            raise ValueError("bit clock too high: the PIO clock is " + str(freq())
                             + " Hz and it needs two steps per bit")
        self._display = display
        self.bit_clock_hz = bit_clock_hz
        self.name = "PIO + DMA %.1f MHz" % (bit_clock_hz / 1000000)
        self._dma = rp2.DMA()
        self._control = self._dma.pack_ctrl(size=0, inc_read=True, inc_write=False,
                                            treq_sel=DMA_REQUEST_PIO0_TX_0)
        self._state_machine = None
        self.in_flight = False        # True while a picture is going out
        # The commands are bit-banged. Waiting less per bit makes them faster.
        self._saved_delay = display.bit_delay_microseconds
        display.bit_delay_microseconds = command_delay_microseconds

    def start_raw(self, buffer, offset, byte_count):
        """Start sending byte_count bytes of 'buffer' from 'offset' as pixel
        data and COME BACK AT ONCE. The window must already be set. The bytes
        are read from 'buffer' while they go out, so do not change that part
        of the buffer until wait() has returned.
        Until wait() the pins belong to PIO: the display's own commands call
        wait() by themselves first."""
        self.wait()                   # only one picture at a time
        display = self._display
        self._state_machine = rp2.StateMachine(
            0, _data_byte_writer, freq=self.bit_clock_hz * 2,
            sideset_base=Pin(display._clock_pin_number),
            out_base=Pin(display._data_pin_number),
            set_base=Pin(display._data_pin_number))
        self._dma.config(read=memoryview(buffer)[offset:offset + byte_count],
                         write=PIO0_TX_FIFO_0, count=byte_count, ctrl=self._control)
        display._select_pin.low()
        self._state_machine.active(1)
        self._dma.active(True)
        self.in_flight = True

    def wait(self):
        """Wait until the picture started by start_raw() has gone out, then give
        the pins back. Does nothing when nothing is going out."""
        if not self.in_flight:
            return
        display = self._display
        state_machine = self._state_machine
        failed = False
        deadline = time.ticks_add(time.ticks_ms(), TIMEOUT_MILLISECONDS)
        while self._dma.active():
            if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                failed = True
                break
        if not failed:
            while state_machine.tx_fifo() > 0:
                if time.ticks_diff(deadline, time.ticks_ms()) < 0:
                    failed = True
                    break
            time.sleep_us(40)           # the last byte is still being shifted out

        state_machine.active(0)
        self._dma.active(False)
        display._select_pin.high()
        rp2.PIO(0).remove_program()
        display._reclaim_pins()
        self._state_machine = None
        self.in_flight = False
        if failed:
            raise RuntimeError("PIO + DMA made no progress")

    def send_raw(self, buffer, offset, byte_count):
        """Send and wait until it has gone out."""
        self.start_raw(buffer, offset, byte_count)
        self.wait()

    def close(self):
        try:
            self.wait()
        finally:
            self._dma.active(False)
            self._dma.close()
            self._display.bit_delay_microseconds = self._saved_delay
