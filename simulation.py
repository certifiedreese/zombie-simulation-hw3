# ============================================================
# simulation.py - Simulation logic layer
#
# All the game RULES live here: how agents move, chase, and fight.
# State is read and written ONLY through a StateStore, and the heavy
# work is done ONLY through a finder object (serial or parallel).
# ============================================================

import random
import math
import time

# ---------- SETTINGS ----------
WIDTH, HEIGHT = 800, 600
NUM_HUMANS = 1000
NUM_ZOMBIES = 50
FIGHT_CHANCE = 0.4    # chance a human kills the zombie instead of being infected
TIME_LIMIT = 45       # seconds until rescue arrives
FPS = 60
CELL_SIZE = 50        # size of each grid square, in pixels
VISION_RADIUS = 100   # how far a zombie can see a human
TOUCH_DISTANCE = 13   # human radius 6 + zombie radius 7


# ---------- EVENT PROCESSING: REDUCE STEP ----------
def resolve_conflicts(candidates):
    """REDUCE step (one core).
    candidates[i] is zombie i's proposed fight:
        (human_index, distance, roll, zombie_id), or None.
    If several zombies want the same human, the closest zombie wins
    (a tie goes to the lowest zombie id).
    Returns a list of (zombie_index, human_index, roll) where every
    zombie and every human appears AT MOST ONCE."""
    winners = {}  # human_index -> ((distance, zombie_id), zombie_index, roll)
    for zi, cand in enumerate(candidates):
        if cand is None:
            continue
        hi, dist, roll, zid = cand
        key = (dist, zid)
        if hi not in winners or key < winners[hi][0]:
            winners[hi] = (key, zi, roll)
    return [(zi, hi, roll) for hi, (key, zi, roll) in sorted(winners.items())]


# ---------- HUMAN AGENT ----------
class Human:
    def __init__(self):
        self.id = None
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(0, HEIGHT)
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.5, 1.4)
        self.dx = math.cos(angle) * speed
        self.dy = math.sin(angle) * speed

    def to_dict(self):
        return {"id": self.id, "kind": "human",
                "x": self.x, "y": self.y,
                "dx": self.dx, "dy": self.dy, "speed": 0}

    @classmethod
    def from_dict(cls, data):
        h = cls()
        h.id = data["id"]
        h.x, h.y = data["x"], data["y"]
        h.dx, h.dy = data["dx"], data["dy"]
        return h

    def update(self):
        self.x += self.dx
        self.y += self.dy
        if self.x < 0 or self.x > WIDTH:
            self.dx = -self.dx
        if self.y < 0 or self.y > HEIGHT:
            self.dy = -self.dy


# ---------- ZOMBIE AGENT ----------
class Zombie:
    def __init__(self, x=None, y=None):
        self.id = None
        self.x = x if x is not None else random.randint(0, WIDTH)
        self.y = y if y is not None else random.randint(0, HEIGHT)
        self.speed = 1.5
        angle = random.uniform(0, 2 * math.pi)
        self.dx = math.cos(angle)
        self.dy = math.sin(angle)

    def to_dict(self):
        return {"id": self.id, "kind": "zombie",
                "x": self.x, "y": self.y,
                "dx": self.dx, "dy": self.dy, "speed": self.speed}

    @classmethod
    def from_dict(cls, data):
        z = cls(data["x"], data["y"])
        z.id = data["id"]
        z.dx, z.dy = data["dx"], data["dy"]
        z.speed = data["speed"]
        return z

    def chase(self, human):
        dx = human.x - self.x
        dy = human.y - self.y
        dist = math.hypot(dx, dy)
        if dist > 0:
            self.x += dx / dist * self.speed
            self.y += dy / dist * self.speed

    def wander(self):
        self.x += self.dx
        self.y += self.dy
        if self.x < 0 or self.x > WIDTH:
            self.dx = -self.dx
        if self.y < 0 or self.y > HEIGHT:
            self.dy = -self.dy


# ---------- THE SIMULATION ----------
class Simulation:
    def __init__(self, store, finder):
        # store:  ANY StateStore (in-memory, SQLite, ...)
        # finder: ANY finder (serial or parallel)
        self.store = store
        self.finder = finder
        self.resolve_time = 0.0  # time spent in the reduce + apply steps
        self.fights = 0          # total fights processed

    def new_game(self):
        self.store.clear()
        self.store.set_value("width", WIDTH)
        self.store.set_value("height", HEIGHT)
        self.store.set_value("frames", 0)
        self.store.set_value("seed", random.randrange(1_000_000_000))  # for fight rolls
        self.resolve_time = 0.0
        self.fights = 0
        for _ in range(NUM_HUMANS):
            h = Human()
            h.id = self.store.add_agent(h.to_dict())
        for _ in range(NUM_ZOMBIES):
            z = Zombie()
            z.id = self.store.add_agent(z.to_dict())
        self.store.save()

    def get_humans(self):
        return [Human.from_dict(d) for d in self.store.get_agents("human")]

    def get_zombies(self):
        return [Zombie.from_dict(d) for d in self.store.get_agents("zombie")]

    def seconds(self):
        return self.store.get_value("frames", 0) // FPS

    def result(self):
        if len(self.get_zombies()) == 0:
            return "Humans survived!"
        if len(self.get_humans()) == 0:
            return "Zombies took over!"
        if self.seconds() >= TIME_LIMIT:
            return "Rescue arrived!"
        return None

    def step(self):
        if self.result() is not None:
            return  # game over: nothing changes

        # 1) Load the current state from storage
        humans = self.get_humans()
        zombies = self.get_zombies()
        frame = self.store.get_value("frames", 0) + 1
        self.store.set_value("frames", frame)
        seed = self.store.get_value("seed", 0)

        # 2) Humans move
        for h in humans:
            h.update()
        human_positions = [(h.x, h.y) for h in humans]

        # 3) NEIGHBOR-FINDING: which human each zombie chases (serial or parallel)
        zombie_positions = [(z.x, z.y) for z in zombies]
        targets = self.finder.find(zombie_positions, human_positions)
        for z, t in zip(zombies, targets):
            if t >= 0:
                z.chase(humans[t])
            else:
                z.wander()

        # 4) EVENT PROCESSING
        # 4a) MAP (serial or parallel): each zombie proposes at most one
        #     fight with the closest human it touches, and rolls the dice
        zombie_data = [(z.id, z.x, z.y) for z in zombies]
        human_data = [(h.id, h.x, h.y) for h in humans]
        candidates = self.finder.find_events(zombie_data, human_data, seed, frame)

        start = time.perf_counter()
        # 4b) REDUCE (one core): if zombies want the same human, the closest wins
        fights = resolve_conflicts(candidates)

        # 4c) APPLY: every agent is in at most one fight, so no conflicts
        dead = set()      # indexes of zombies killed
        infected = set()  # indexes of humans bitten
        new_zombies = []
        for zi, hi, roll in fights:
            if roll < FIGHT_CHANCE:
                dead.add(zi)                       # human wins
            else:
                infected.add(hi)                   # zombie wins
                h = humans[hi]
                new_zombies.append(Zombie(h.x, h.y))
        self.resolve_time += time.perf_counter() - start
        self.fights += len(fights)

        for zi in dead:
            self.store.remove_agent(zombies[zi].id)
        for hi in infected:
            self.store.remove_agent(humans[hi].id)
        zombies = [z for i, z in enumerate(zombies) if i not in dead]
        humans = [h for i, h in enumerate(humans) if i not in infected]

        # 5) Save the new state back to storage
        for h in humans:
            self.store.update_agent(h.to_dict())
        for z in zombies:
            self.store.update_agent(z.to_dict())
        for z in new_zombies:
            z.id = self.store.add_agent(z.to_dict())
        self.store.save()