# ============================================================
# test_events.py - Tests for event processing
#
# Run with:  python test_events.py
# Each test sets up a situation and checks the result is correct.
# ============================================================

import random
import unittest
from simulation import Simulation, resolve_conflicts
from storage import InMemoryStore
from neighbors import SerialFinder, ParallelFinder, detect_events, fight_roll


class TestEventProcessing(unittest.TestCase):

    def test_dice_roll_is_repeatable(self):
        # Same inputs must give the same roll, between 0 and 1
        a = fight_roll(42, 7, 3, 9)
        b = fight_roll(42, 7, 3, 9)
        self.assertEqual(a, b)
        self.assertTrue(0 <= a < 1)

    def test_zombie_picks_closest_human(self):
        # One zombie touching two humans picks the closer one
        zombies = [(1, 100, 100)]
        humans = [(10, 110, 100),   # 10 pixels away
                  (11, 105, 100)]   # 5 pixels away (closer)
        result = detect_events(zombies, humans, 42, 1)
        self.assertEqual(result[0][0], 1)  # index of the closer human

    def test_no_touch_means_no_fight(self):
        # A zombie far from every human proposes no fight
        candidates = detect_events([(1, 0, 0)], [(10, 500, 500)], 42, 1)
        self.assertEqual(resolve_conflicts(candidates), [])

    def test_one_fight_per_human(self):
        # Two zombies touching the same human: only the closer zombie fights
        humans = [(10, 100, 100)]
        zombies = [(1, 95, 100),    # 5 pixels away (closer)
                   (2, 108, 100)]   # 8 pixels away
        candidates = detect_events(zombies, humans, 42, 1)
        fights = resolve_conflicts(candidates)
        self.assertEqual(len(fights), 1)
        self.assertEqual(fights[0][0], 0)  # zombie index 0 wins

    def test_no_agent_duplicated(self):
        # Over 30 frames, no agent id ever appears twice,
        # and the total number of agents never goes up
        random.seed(3)
        sim = Simulation(InMemoryStore(), SerialFinder())
        sim.new_game()
        total_before = len(sim.get_humans()) + len(sim.get_zombies())
        for _ in range(30):
            sim.step()
            ids = [h.id for h in sim.get_humans()] + [z.id for z in sim.get_zombies()]
            self.assertEqual(len(ids), len(set(ids)))
        total_after = len(sim.get_humans()) + len(sim.get_zombies())
        self.assertLessEqual(total_after, total_before)

    def test_serial_and_parallel_match(self):
        # Same starting setup must give the exact same results
        # with 1 core or with several cores
        finders = [SerialFinder(), ParallelFinder(workers=2)]
        results = []
        for finder in finders:
            random.seed(7)
            sim = Simulation(InMemoryStore(), finder)
            sim.new_game()
            for _ in range(20):
                sim.step()
            humans = sorted((h.x, h.y) for h in sim.get_humans())
            zombies = sorted((z.x, z.y) for z in sim.get_zombies())
            results.append((humans, zombies, sim.fights))
        finders[1].close()
        self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()