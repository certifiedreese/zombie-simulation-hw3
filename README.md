# Zombie Simulation – CPS 310 Assignment 3

**Author:** Reese Franklin

## What This Is
A zombie simulation with thousands of agents. For this assignment, I
designed and built **parallel event processing**: fights between zombies
and humans are found and settled across several CPU cores at the same
time, while always giving the same results as one core.

My proposal for my specialized concentration is in `PROPOSAL.md`.

## How to Run
1. Install pygame-ce: `pip install pygame-ce`
2. Play the game: `python main.py` (press R to restart)
3. Run the tests: `python test_events.py`
4. Run the experiments: `python benchmark.py`

## The Files
| File | Job |
|---|---|
| `main.py` | Opens the window and draws everything |
| `simulation.py` | The game rules, including the reduce and apply steps |
| `neighbors.py` | The parallel work: neighbor-finding and the event map step |
| `storage.py` | Saves the agents (database or memory) |
| `test_events.py` | Tests that prove the event processing is correct |
| `benchmark.py` | Times the simulation for the experiments |
| `results.md` | All experiment results |
| `PROPOSAL.md` | My proposal for my specialized concentration |

## My Parallel Event Processing Design

An **event** is a fight: a zombie touching a human. Each fight has two
possible outcomes: the human kills the zombie (40% chance), or the human
becomes a zombie (60% chance).

The hard part of doing this in parallel is that fights **change things**.
If two cores handled fights at the same time, two zombies could bite the
same human and turn one human into two zombies. My algorithm prevents
that with three steps: **map, reduce, and apply**.

### Step 1: Map (parallel)
Each core takes a group of zombies. Each zombie looks at the humans it is
touching, picks the **closest** one, and rolls the dice for that fight.
This step only *proposes* fights. It doesn't change anything, so it is
safe to do on many cores at once.

### Step 2: Reduce (one core)
If two zombies proposed a fight with the **same human**, the closer
zombie gets the fight (a tie goes to the lower zombie id). After this
step, every zombie and every human is in **at most one fight**.

### Step 3: Apply (one core)
Because no agent is in two fights, the results are applied directly:
dead zombies are removed, and bitten humans become zombies. No human can
ever be bitten twice.

### The dice trick
Each fight's dice roll comes from a formula using the game's seed, the
frame number, the zombie's id, and the human's id. So the same fight
always gets the same roll, **no matter which core rolls it**. This is why
1 core and 8 cores give exactly the same results.

### Splitting the map (spatial partitioning)
The map is cut into vertical **slices**, one per core, with the same
number of zombies in each. Each core gets:
- the zombies in its slice, and
- only the humans in its slice, plus a thin **border (halo)** on each
  side, so a zombie at the edge can still reach a human just across
  the line.

Each core then builds a grid of **only its slice**, so zombies only
check nearby squares.

## Parallelism Techniques Used
- **Processes, not threads:** Python's GIL only lets one thread run
  Python code at a time, so I use separate processes, which truly run
  at the same time.
- **A worker pool:** the processes are created once and reused every
  frame, because starting a process takes time.
- **Data partitioning:** the map is split into slices, so each core
  works on its own piece of the data.
- **Map-reduce:** the parallel part only proposes fights, and the
  conflicts are settled on one core, so there are no race conditions.

## Testing
`test_events.py` runs 6 tests, and all pass:
1. Dice rolls are repeatable.
2. A zombie picks the closest human it touches.
3. No touch means no fight.
4. Only one fight per human: if two zombies grab the same human,
   only the closer one fights.
5. No agent is ever duplicated over 30 frames, and