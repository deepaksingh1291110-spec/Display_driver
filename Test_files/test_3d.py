"""
3D shapes test for nokia_3d.py

On the Pico you need:
    nokia_display.py  nokia_fast.py  nokia_graphics.py
    nokia_shapes.py (the new one)  nokia_shapes_fast.py  nokia_3d.py

Four pages, PAGE_SECONDS each, with the FPS of every page printed:
    1. a solid cube with a different colour on every face, and a ball
    2. the three drawing modes: wire, wire with hidden lines removed, solid with edges
    3. six different shapes
    4. a large donut (torus) with its edges
At the end it times the two steps of a frame (prepare and draw) for the donut,
so we can see which one to make faster.
"""
import gc
import time

import nokia_display
from nokia_display import Display, make_colour
from nokia_graphics import Screen
from nokia_shapes import Shapes
from nokia_3d import (Object3D, MODE_SOLID, MODE_WIREFRAME, MODE_WIREFRAME_HIDDEN_LINES,
                      make_cube, make_box, make_sphere, make_cone, make_cylinder,
                      make_pyramid, make_torus, make_octahedron, make_icosahedron)

# ===============================
# SETTINGS - change these
# ===============================
CLOCK_PIN = 6
DATA_PIN = 7
SELECT_PIN = 5
RESET_PIN = 4

ROTATION = nokia_display.PORTRAIT_FLEX_CABLE_AT_TOP
SPI_MEGABITS_PER_SECOND = 32
PAGE_SECONDS = 8

BACKGROUND = make_colour(10, 10, 30)
WHITE = nokia_display.WHITE
RED = nokia_display.RED
GREEN = nokia_display.GREEN
BLUE = nokia_display.BLUE
YELLOW = nokia_display.YELLOW
CYAN = nokia_display.CYAN
MAGENTA = nokia_display.MAGENTA
ORANGE = make_colour(255, 140, 0)
DARK_GREY = make_colour(50, 50, 50)


def build_pages(screen):
    """Make the shapes for every page, placed for the current screen size."""
    width = screen.width
    height = screen.height
    pages = {}

    cube = Object3D(make_cube(), RED, radius_pixels=34,
                    face_colours=(RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA))
    cube.set_position(width // 2, height // 3)
    ball = Object3D(make_sphere(1000, 8, 12), CYAN, radius_pixels=30)
    ball.set_position(width // 2, height * 3 // 4)
    pages["cube_and_ball"] = [cube, ball]

    wire = Object3D(make_cube(), GREEN, radius_pixels=24)
    hidden = Object3D(make_icosahedron(), YELLOW, radius_pixels=24)
    solid = Object3D(make_octahedron(), ORANGE, radius_pixels=24)
    wire.set_position(width // 4, height // 4)
    hidden.set_position(width * 3 // 4, height // 4)
    solid.set_position(width // 2, height * 3 // 4)
    pages["modes"] = [wire, hidden, solid]

    shapes_for_grid = [(make_cone(), GREEN), (make_cylinder(), YELLOW),
                       (make_pyramid(), MAGENTA), (make_icosahedron(), CYAN),
                       (make_octahedron(), ORANGE), (make_box(1400, 600, 800), WHITE)]
    grid = []
    for number in range(6):
        mesh, colour = shapes_for_grid[number]
        shape = Object3D(mesh, colour, radius_pixels=22)
        column = number % 2
        row = number // 2
        shape.set_position(width * (2 * column + 1) // 4, height * (2 * row + 1) // 6)
        grid.append(shape)
    pages["gallery"] = grid

    donut = Object3D(make_torus(700, 300, 14, 8), ORANGE, radius_pixels=48)
    donut.set_position(width // 2, height // 2)
    pages["donut"] = [donut]
    return pages


def main():
    display = Display(CLOCK_PIN, DATA_PIN, SELECT_PIN, RESET_PIN, ROTATION)
    display.start()
    display.use_hardware_spi(SPI_MEGABITS_PER_SECOND * 1000000)

    screen = Screen(display, budget_bytes=100 * 1024, reserve_bytes=16 * 1024)
    screen.fill_screen(BACKGROUND)
    screen.show()
    print(screen.memory_report())

    gc.collect()
    before = gc.mem_alloc()
    shapes = Shapes(screen)
    pages = build_pages(screen)
    gc.collect()
    print()
    print("Shapes + all 3D objects and meshes:", gc.mem_alloc() - before, "bytes")
    print("Fast Shapes helper in use:", shapes.fast_helpers_in_use)

    # (page name, objects, how each object is drawn)
    plan = (
        ("Cube and ball", pages["cube_and_ball"], (MODE_SOLID, MODE_SOLID), (None, None)),
        ("Three modes", pages["modes"], (MODE_WIREFRAME, MODE_WIREFRAME_HIDDEN_LINES, MODE_SOLID),
         (None, None, DARK_GREY)),
        ("Six shapes", pages["gallery"], (MODE_SOLID,) * 6, (None,) * 6),
        ("Donut", pages["donut"], (MODE_SOLID,), (make_colour(70, 35, 0),)),
    )

    for page_name, objects, modes, edge_colours in plan:
        def draw_scene(target, objects=objects, modes=modes, edge_colours=edge_colours):
            for number in range(len(objects)):
                objects[number].draw(shapes, modes[number], edge_colours[number])

        frame_count = 0
        faces_drawn = 0
        start_time = time.ticks_ms()
        end_time = time.ticks_add(start_time, PAGE_SECONDS * 1000)
        while time.ticks_diff(end_time, time.ticks_ms()) > 0:
            elapsed = time.ticks_diff(time.ticks_ms(), start_time)
            for number in range(len(objects)):
                spin = elapsed * (40 + 17 * number) // 1000
                objects[number].set_rotation(spin // 2 + 20 * number, spin, (spin // 3) * (number % 2))
            screen.render(draw_scene, background=BACKGROUND)
            frame_count += 1
            for shape in objects:
                faces_drawn += shape.visible_face_count
        total_milliseconds = time.ticks_diff(time.ticks_ms(), start_time)
        print("%-14s %6.1f FPS   about %d faces drawn per frame"
              % (page_name, frame_count * 1000 / total_milliseconds, faces_drawn // frame_count))

    # where does the time of one frame go? (the donut, 96 faces)
    donut = pages["donut"][0]
    print()
    repeats = 20
    start = time.ticks_us()
    for count in range(repeats):
        donut.set_rotation(count * 5, count * 7, 0)
        donut.prepare()
    prepare_microseconds = time.ticks_diff(time.ticks_us(), start) // repeats
    start = time.ticks_us()
    for count in range(repeats):
        donut.draw(shapes, MODE_SOLID)
    draw_microseconds = time.ticks_diff(time.ticks_us(), start) // repeats
    print("Donut, one frame: prepare (turn, project, light, sort) %d us," % prepare_microseconds)
    print("                  draw (fill the faces) %d us, faces drawn %d"
          % (draw_microseconds, donut.visible_face_count))

    gc.collect()
    print("Free RAM at the end:", gc.mem_free(), "bytes")


main()
