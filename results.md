# HW3 Results

## Tests (python test_events.py)
Ran 6 tests: all passed (OK).
- Dice rolls are repeatable
- A zombie picks the closest human it touches
- No touch means no fight
- Only one fight per human (no double bites)
- No agent is ever duplicated over 30 frames
- Serial and parallel give exactly the same results
## Version 1: every core gets the whole map
done: 5000 humans, 1 core(s)
done: 10000 humans, 1 core(s)
done: 20000 humans, 1 core(s)
done: 5000 humans, 2 core(s)
done: 10000 humans, 2 core(s)
done: 20000 humans, 2 core(s)
done: 5000 humans, 4 core(s)
done: 10000 humans, 4 core(s)
done: 20000 humans, 4 core(s)
done: 5000 humans, 8 core(s)
done: 10000 humans, 8 core(s)
done: 20000 humans, 8 core(s)

| Agents (H/Z) | Map size | Cores | ms per frame | event map ms | event reduce+apply ms | fights | humans left |
|---|---|---|---|---|---|---|---|
| 5000/250 | 1788x1341 | 1 | 69.3 | 10.4 | 0.16 | 2122 | 3695 |
| 5000/250 | 1788x1341 | 2 | 144.6 | 20.3 | 0.30 | 2122 | 3695 |
| 5000/250 | 1788x1341 | 4 | 97.8 | 18.0 | 0.25 | 2122 | 3695 |
| 5000/250 | 1788x1341 | 8 | 136.3 | 28.4 | 0.31 | 2122 | 3695 |
| 10000/500 | 2529x1897 | 1 | 165.5 | 24.7 | 0.36 | 4328 | 7368 |
| 10000/500 | 2529x1897 | 2 | 325.2 | 48.8 | 0.60 | 4328 | 7368 |
| 10000/500 | 2529x1897 | 4 | 277.6 | 44.9 | 0.54 | 4328 | 7368 |
| 10000/500 | 2529x1897 | 8 | 343.4 | 71.9 | 0.62 | 4328 | 7368 |
| 20000/1000 | 3577x2683 | 1 | 532.4 | 78.2 | 0.78 | 7894 | 15254 |
| 20000/1000 | 3577x2683 | 2 | 523.9 | 79.1 | 0.93 | 7894 | 15254 |
| 20000/1000 | 3577x2683 | 4 | 701.3 | 106.5 | 0.99 | 7894 | 15254 |
| 20000/1000 | 3577x2683 | 8 | 748.1 | 142.1 | 1.06 | 7894 | 15254 |

Parallel was slower at every size because each core copied
and gridded the whole map.
## Version 2: each core gets only its slice of the map
(paste the new table here)

### Summary
- Correctness: fights and humans left are identical for 1, 2, 4,
  and 8 cores, and identical to Version 1. Parallelism changed the
  speed, not the results.
- Version 1 problem: every core copied and gridded the whole map,
  so adding cores made it slower (event map at 20,000 humans:
  78.2 ms on 1 core, 142.1 ms on 8).
- Version 2 fix: each core gets only its slice of the map plus a
  thin border (halo). At 20,000 humans with 8 cores, the event map
  step dropped from 142.1 ms (Version 1) to 39.5 ms.
- Version 2 scaling: at 20,000 humans the event map step went from
  64.4 ms (1 core) to 39.5 ms (8 cores), about 1.6x faster.
  At 5,000 humans: 16.0 ms to 10.6 ms, about 1.5x faster.
- The reduce + apply step (one core) takes under 1 ms at every size,
  so it is not a bottleneck.
- At 10,000 humans parallel was slower than 1 core; the 1-core time
  looks unusually low compared to other sizes, so this is likely
  measurement noise.
- Speedup is limited by overhead (sorting and sending slices every
  frame) and by the parts of each frame that still run on one core,
  like loading and saving agents.