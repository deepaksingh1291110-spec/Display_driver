"""
How much RAM does each driver file use once it is imported?

Run this on the Pico TWICE and compare the TOTAL:
  1. with the .py files on the Pico
  2. after you compiled the big files to .mpy and deleted their .py files
     (see the steps in the chat; keep the three *_fast.py files as .py)

Nothing is drawn. It only imports the modules and prints the memory used.
Start it from a fresh start of the Pico (press the reset button, or Ctrl+D
in Thonny) so that nothing is imported yet.
"""
import gc
import sys

MODULES = (
    "nokia_fast",
    "nokia_display",
    "nokia_graphics",
    "nokia_shapes_fast",
    "nokia_shapes",
    "nokia_font_fast",
    "nokia_font",
    "nokia_text_motion",
    "nokia_3d",
    "nokia_dma_link",
)

gc.collect()
free_at_start = gc.mem_free()
print("Free RAM at the start:", free_at_start, "bytes")
print()

total = 0
for name in MODULES:
    if name in sys.modules:
        print("%-20s already imported, run this from a fresh start" % name)
        continue
    gc.collect()
    before = gc.mem_alloc()
    try:
        __import__(name)
    except Exception as error:
        print("%-20s FAILED: %s %s" % (name, type(error).__name__, error))
        continue
    gc.collect()
    used = gc.mem_alloc() - before
    total += used
    print("%-20s %7d bytes" % (name, used))

print()
print("TOTAL used by the imported modules: %d bytes" % total)
print("Free RAM at the end: %d bytes" % gc.mem_free())
