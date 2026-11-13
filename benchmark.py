# ============================================================
# benchmark.py - Experiments for parallel event processing
#
# Runs the simulation with no window and no FPS cap, at several
# sizes and core counts, and times the event processing steps.
# The map grows with the number of agents so the crowding stays
# the same at every size. Prints a table for results.md.
# ============================================================

import time
import math
import random
import simulation
from simulation import Simulation
from storage import InMemoryStore
from neighbors import SerialFinder, ParallelFinder

FRAMES = 30     # frames per run
REPEATS = 3     # runs per test, averaged
SIZES = [(5000, 250), (10000, 500), (20000, 1000)]  # (humans, zombies)
CORES = [1, 2, 4, 8]                                 # 1 = serial
BASE_HUMANS = 1000  # 1,000 humans on an 800x600 map is the crowding we keep


class TimedFinder:
    """Wraps any finder and times the event map step."""

    def __init__(self, finder):
        self.finder = finder
        self.event_time = 0.0

    def find(self, zombie_positions, human_positions):
        return self.finder.find(zombie_positions, human_positions)

    def find_events(self, zombie_data, human_data, seed, frame):
        start = time.perf_counter()
        result = self.finder.find_events(zombie_data, human_data, seed, frame)
        self.event_time += time.perf_counter() - start
        return result


def map_size(humans):
    scale = math.sqrt(humans / BASE_HUMANS)
    return int(800 * scale), int(600 * scale)


def run_once(finder, humans, zombies):
    # Grow the map so the crowding stays the same at every size
    simulation.WIDTH, simulation.HEIGHT = map_size(humans)
    simulation.NUM_HUMANS = humans
    simulation.NUM_ZOMBIES = zombies

    timed = TimedFinder(finder)
    sim = Simulation(InMemoryStore(), timed)
    random.seed(42)  # same random start every time, so tests are fair
    sim.new_game()

    start = time.perf_counter()
    frames = 0
    for _ in range(FRAMES):
        if sim.result() is not None:
            break
        sim.step()
        frames += 1
    total = time.perf_counter() - start

    return (total / frames * 1000,             # ms per frame
            timed.event_time / frames * 1000,  # event map ms (parallel part)
            sim.resolve_time / frames * 1000,  # event reduce + apply ms (one core)
            sim.fights,                        # total fights processed
            len(sim.get_humans()))             # humans left at the end


def run(finder, humans, zombies):
    # Run the test REPEATS times and average the times
    frame_ms = map_ms = reduce_ms = 0.0
    for _ in range(REPEATS):
        f, m, r, fights, left = run_once(finder, humans, zombies)
        frame_ms += f
        map_ms += m
        reduce_ms += r
    return frame_ms / REPEATS, map_ms / REPEATS, reduce_ms / REPEATS, fights, left


def main():
    results = {}
    for cores in CORES:
        finder = SerialFinder() if cores == 1 else ParallelFinder(workers=cores)
        for humans, zombies in SIZES:
            results[(humans, cores)] = run(finder, humans, zombies)
            print(f"done: {humans} humans, {cores} core(s)")
        finder.close()

    print()
    print("| Agents (H/Z) | Map size | Cores | ms per frame | event map ms | event reduce+apply ms | fights | humans left |")
    print("|---|---|---|---|---|---|---|---|")
    for humans, zombies in SIZES:
        w, h = map_size(humans)
        for cores in CORES:
            f, m, r, fights, left = results[(humans, cores)]
            print(f"| {humans}/{zombies} | {w}x{h} | {cores} | {f:.1f} | {m:.1f} | {r:.2f} | {fights} | {left} |")


if __name__ == "__main__":
    main()