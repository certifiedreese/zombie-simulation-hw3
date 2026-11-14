# ============================================================
# neighbors.py - Parallel work layer
#
# Two jobs, both using a spatial grid:
#   find()        - which human each zombie should chase
#   find_events() - which fight each zombie proposes
#                   (the MAP step of event processing)
#
# SPATIAL PARTITIONING: the map is cut into vertical slices, one per
# core. Each core gets the zombies in its slice and ONLY the humans
# in that slice plus a thin border (the "halo"), so no core copies
# or grids the whole map.
#
#   SerialFinder   - one slice, one CPU core
#   ParallelFinder - one slice per core, all cores at the same time
# ============================================================

import math
import bisect
import random
import multiprocessing
from simulation import CELL_SIZE, VISION_RADIUS, TOUCH_DISTANCE


# ---------- SPATIAL GRID HELPERS ----------
def build_grid(positions):
    """(column, row) -> list of indexes of the agents in that square."""
    grid = {}
    for i, (x, y) in enumerate(positions):
        key = (int(x // CELL_SIZE), int(y // CELL_SIZE))
        grid.setdefault(key, []).append(i)
    return grid


def nearby(grid, x, y, radius):
    """Every index in the squares within `radius` pixels of (x, y)."""
    r = math.ceil(radius / CELL_SIZE)
    cx, cy = int(x // CELL_SIZE), int(y // CELL_SIZE)
    for gx in range(cx - r, cx + r + 1):
        for gy in range(cy - r, cy + r + 1):
            yield from grid.get((gx, gy), ())


# ---------- SPLITTING THE MAP INTO SLICES ----------
def with_index(items):
    """Add each item's position in the list to the front of it."""
    return [(i, *item) for i, item in enumerate(items)]


def split_by_x(zombie_items, human_items, parts, halo):
    """Cut the map into `parts` vertical slices with equal numbers of
    zombies. Each slice gets its zombies, plus the humans inside the
    slice or within `halo` pixels of its edges. (x is item[-2].)"""
    zombies = sorted(zombie_items, key=lambda it: it[-2])
    humans = sorted(human_items, key=lambda it: it[-2])
    human_x = [it[-2] for it in humans]
    if not zombies:
        return []
    size = math.ceil(len(zombies) / parts)
    jobs = []
    for start in range(0, len(zombies), size):
        group = zombies[start:start + size]
        left = group[0][-2] - halo
        right = group[-1][-2] + halo
        a = bisect.bisect_left(human_x, left)
        b = bisect.bisect_right(human_x, right)
        jobs.append((group, humans[a:b]))
    return jobs


def assemble(parts, count, empty):
    """Put each slice's answers back in the original zombie order."""
    results = [empty] * count
    for part in parts:
        for zombie_index, answer in part:
            results[zombie_index] = answer
    return results


# ---------- THE WORK FOR ONE SLICE ----------
def nearest_part(zombie_items, human_items):
    """zombie_items: (zombie_index, x, y). human_items: (human_index, x, y).
    For each zombie: (zombie_index, index of nearest human in sight or -1)."""
    grid = build_grid([(x, y) for (_, x, y) in human_items])
    out = []
    for (zi, zx, zy) in zombie_items:
        best = -1
        best_dist = VISION_RADIUS
        for k in nearby(grid, zx, zy, VISION_RADIUS):
            hi, hx, hy = human_items[k]
            d = math.hypot(hx - zx, hy - zy)
            if d < best_dist:
                best = hi
                best_dist = d
        out.append((zi, best))
    return out


def fight_roll(seed, frame, zombie_id, human_id):
    """A dice roll from 0 to 1 that depends ONLY on these four numbers.
    Every core gets the same roll for the same fight, so the results
    don't depend on how many cores are used."""
    x = ((seed * 1_000_003 + frame) * 1_000_033 + zombie_id) * 1_000_037 + human_id
    return random.Random(x).random()


def events_part(zombie_items, human_items, seed, frame):
    """MAP step for one slice.
    zombie_items: (zombie_index, zombie_id, x, y).
    human_items:  (human_index, human_id, x, y).
    For each zombie: (zombie_index, proposal), where proposal is
    (human_index, distance, roll, zombie_id) for the closest human it
    is touching, or None if it touches nobody."""
    grid = build_grid([(x, y) for (_, _, x, y) in human_items])
    out = []
    for (zi, zid, zx, zy) in zombie_items:
        best = None
        best_dist = TOUCH_DISTANCE
        for k in nearby(grid, zx, zy, TOUCH_DISTANCE):
            hi, hid, hx, hy = human_items[k]
            d = math.hypot(hx - zx, hy - zy)
            if d < best_dist:
                best = (hi, hid)
                best_dist = d
        if best is None:
            out.append((zi, None))
        else:
            hi, hid = best
            out.append((zi, (hi, best_dist, fight_roll(seed, frame, zid, hid), zid)))
    return out


# ---------- SERIAL VERSION ----------
class SerialFinder:
    """One slice: one CPU core does all the work."""
    workers = 1

    def _run(self, work, zombie_items, human_items, halo, empty, *extra):
        jobs = split_by_x(zombie_items, human_items, self.workers, halo)
        parts = [work(z, h, *extra) for z, h in jobs]
        return assemble(parts, len(zombie_items), empty)

    def find(self, zombie_positions, human_positions):
        return self._run(nearest_part, with_index(zombie_positions),
                         with_index(human_positions), VISION_RADIUS, -1)

    def find_events(self, zombie_data, human_data, seed, frame):
        return self._run(events_part, with_index(zombie_data),
                         with_index(human_data), TOUCH_DISTANCE, None, seed, frame)

    def close(self):
        pass


# ---------- PARALLEL VERSION ----------
class ParallelFinder(SerialFinder):
    """One slice per core. All slices are processed at the same time."""

    def __init__(self, workers=4):
        self.workers = workers
        self.pool = multiprocessing.Pool(workers)  # created once, reused every frame

    def _run(self, work, zombie_items, human_items, halo, empty, *extra):
        jobs = split_by_x(zombie_items, human_items, self.workers, halo)
        parts = self.pool.starmap(work, [(z, h, *extra) for z, h in jobs])
        return assemble(parts, len(zombie_items), empty)

    def close(self):
        self.pool.close()
        self.pool.join()


# ---------- SHORTCUTS (used by the tests) ----------
def find_nearest(zombie_positions, human_positions):
    return SerialFinder().find(zombie_positions, human_positions)


def detect_events(zombie_data, human_data, seed, frame):
    return SerialFinder().find_events(zombie_data, human_data, seed, frame)