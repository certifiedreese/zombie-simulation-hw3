# Proposal: Zombies With Different Alignments

**Author:** Reese Franklin
**Course:** CPS 310 – Zombie Game Simulation

## 1. Motivation
Most zombie simulations treat every zombie the same: every zombie is
hostile and chases humans. Inspired by stories like Tokyo Ghoul, where
not every monster is an enemy, I want to study what happens when
zombies are different from each other. Some zombies may protect
humans, some may ignore them, and some may attack them.

## 2. The Problem
**Main question:** How does the mix of zombie types change whether
humans survive?

Each zombie will have an **alignment**:
- **Hostile:** chases and attacks humans (like the current zombies).
- **Neutral:** ignores humans, but gets hungry over time. When its
  hunger gets too high, it turns hostile.
- **Protective:** stays near humans and fights hostile zombies to
  defend them.

**Specific questions:**
1. What percentage of protective zombies is needed for humans to
   survive most of the time?
2. How does the hunger speed of neutral zombies change the outcome?
3. Does the result change as the simulation gets bigger
   (1,000 vs. 10,000 humans)?

## 3. Hypotheses (my predictions)
- More protective zombies will lead to more humans surviving, but
  only up to a point, because protective zombies can also be killed.
- Faster hunger will make neutral zombies turn hostile sooner, so
  humans will survive less often.
- The results will stay similar at larger sizes, because the map
  grows with the number of agents and the crowding stays the same.

## 4. How I Will Study It

### 4.1 Changes to the simulation
- **New data for each zombie:** an `alignment` (hostile, neutral, or
  protective) and a `hunger` number. These become new columns in the
  database table, so the storage design from the midterm still works.
- **New behaviors:**
  - Neutral zombies wander, and their hunger goes up each frame.
    When it passes a limit, they become hostile.
  - Protective zombies move toward the nearest human and stay close.
  - Hostile zombies chase humans, as they do now.
- **New events:** besides "zombie bites human," there will be
  "protective zombie fights hostile zombie." These events will use
  the same parallel event processing from HW3: the cores propose
  events at the same time (map), conflicts are settled so every
  agent is in at most one event per frame (reduce), and then the
  results are applied.

### 4.2 Experiments
I will change one thing at a time and keep everything else the same:

| Experiment | What changes | Values tested |
|---|---|---|
| 1 | Percentage of protective zombies | 0%, 10%, 25%, 50% |
| 2 | Hunger speed of neutral zombies | slow, medium, fast |
| 3 | Simulation size | 1,000, 5,000, 10,000 humans |

For each setting, I will:
- Run the simulation **10 times** with different random seeds and
  average the results, so one lucky run doesn't decide the answer.
- Use the benchmark mode (no window, no FPS cap) so it runs quickly.

### 4.3 What I will measure
- **Survival rate:** how often humans survive until rescue.
- **Humans left** at the end of each run.
- **Time to takeover:** how long until zombies win, if they do.
- **Population over time:** how many humans and zombies of each
  type exist at each moment, saved to the database so I can
  query it with SQL and make graphs.

### 4.4 How I will check the results are correct
- Tests (like in HW3) for the new rules, for example: a neutral
  zombie turns hostile when hunger passes the limit, and a
  protective zombie never bites a human.
- Checking that serial and parallel versions still give the exact
  same results.

## 5. Plan
1. Add alignment and hunger to the zombie data and database.
2. Add the new behaviors for each zombie type.
3. Add the new event type and extend the parallel event processing.
4. Write tests for the new rules.
5. Run the three experiments and record the results.
6. Analyze the results with graphs and a written summary.

## 6. Expected Outcome
A clear answer, backed by experiments, to the question: how many
"good" zombies does it take to save the humans? This turns the
simulation from a simple chase into a study of how different kinds
of agents affect each other.