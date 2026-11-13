# ============================================================
# neighbors.py - Parallel work layer
#
# Two jobs, both using a spatial grid:
#   find()        - which human each zombie should chase
#   find_events() - which fight each zombie proposes
#                   (the MAP step of event processing)
#
# Two versions follow the same rules, so the simulation can use either:
#   SerialFinder   - one CPU core does all the work
#   ParallelFinder - the zombies are split across several CPU cores
# ============================================================

import math
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


# ---------- NEIGHBOR-FINDING ----------
def find_nearest(zombie_positions, human_positions):
    """For each zombie: the index of the nearest human in vision range, or -1."""
    grid = build_grid(human_positions)
    results = []
    for (zx, zy) in zombie_positions:
        best = -1
        best_dist = VISION_RADIUS
        for i in nearby(grid, zx, zy, VISION_RADIUS):
            hx, hy = human_positions[i]
            d = math.hypot(hx - zx, hy - zy)
            if d < best_dist:
                best = i
                best_dist = d
        results.append(best)
    return results


# ---------- EVENT PROCESSING: MAP STEP ----------
def fight_roll(seed, frame, zombie_id, human_id):
    """A dice roll from 0 to 1 that depends ONLY on these four numbers.
    Every core gets the same roll for the same fight, so the results
    don't depend on how many cores are used."""
    x = ((seed * 1_000_003 + frame) * 1_000_033 + zombie_id) * 1_000_037 + human_id
    return random.Random(x).random()


def detect_events(zombie_data, human_data, seed, frame):
    """MAP step (runs on one core, or on each worker).
    zombie_data and human_data are lists of (id, x, y).
    For each zombie, returns its proposed fight:
        (human_index, distance, roll, zombie_id)
    for the closest human it is touching, or None if it touches nobody."""
    grid = build_grid([(x, y) for (_, x, y) in human_data])
    results = []
    for (zid, zx, zy) in zombie_data:
        best = None
        best_dist = TOUCH_DISTANCE
        for i in nearby(grid, zx, zy, TOUCH_DISTANCE):
            _, hx, hy = human_data[i]
            d = math.hypot(hx - zx, hy - zy)
            if d < best_dist:
                best = i
                best_dist = d
        if best is None:
            results.append(None)
        else:
            hid = human_data[best][0]
            results.append((best, best_dist, fight_roll(seed, frame, zid, hid), zid))
    return results


# ---------- SERIAL VERSION ----------
class SerialFinder:
    """One CPU core handles every zombie."""

    def find(self, zombie_positions, human_positions):
        return find_nearest(zombie_positions, human_positions)

    def find_events(self, zombie_data, human_data, seed, frame):
        return detect_events(zombie_data, human_data, seed, frame)

    def close(self):
        pass


# ---------- PARALLEL VERSION ----------
class ParallelFinder:
    """Splits the zombies into chunks, one chunk per CPU core."""

    def __init__(self, workers=4):
        self.workers = workers
        self.pool = multiprocessing.Pool(workers)  # created once, reused every frame

    def _run(self, work, zombie_items, *extra):
        # Split the zombies into chunks, run `work` on every chunk at the
        # same time, then put the results back together in the original order
        if not zombie_items:
            return []
        size = math.ceil(len(zombie_items) / self.workers)
        chunks = [zombie_items[i:i + size] for i in range(0, len(zombie_items), size)]
        parts = self.pool.starmap(work, [(chunk, *extra) for chunk in chunks])
        return [r for part in parts for r in part]

    def find(self, zombie_positions, human_positions):
        return self._run(find_nearest, zombie_positions, human_positions)

    def find_events(self, zombie_data, human_data, seed, frame):
        return self._run(detect_events, zombie_data, human_data, seed, frame)

    def close(self):
        self.pool.close()
        self.pool.join()