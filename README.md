# Themis

An orbital traffic simulation platform for studying satellite propagation, conjunction detection, and autonomous collision avoidance.

---

## Overview

Themis is a space systems project focused on the growing challenge of orbital congestion.

Modern Earth orbit contains thousands of active satellites and an increasing number of potential conjunction events. As launch rates continue to rise, future space traffic management systems will need to coordinate large numbers of spacecraft efficiently and safely.

The long-term goal of Themis is to provide a simulation environment for:

- Orbit propagation
- Conjunction detection
- Collision risk assessment
- Autonomous maneuver planning
- Multi-agent satellite coordination
- Space traffic management research

The project is being developed incrementally, beginning with accurate orbital propagation using real-world satellite data.

---

## Current Status

### Phase 1: Orbital Propagation ✅

Themis can currently:

- Load real satellite TLE data
- Parse TLEs into propagatable satellite objects
- Propagate satellite positions using SGP4
- Generate future ECI position vectors
- Produce position tables across configurable time horizons

### Phase 2: Conjunction Detection ✅

- Calculate pairwise satellite distances
- Detect close approaches below configurable thresholds
- Scan orbital trajectories across multiple timestamps
- Export conjunction events to CSV
- Track closest observed approaches between satellite pairs

Current demonstration:

- 25 active satellites
- 24 hour propagation horizon
- 30 minute timestep
- 1000 km conjunction threshold

Output:

- Conjunction event reports
- Closest approach statistics
- CSV exports for downstream analysis

---

## Example Workflow

```text
TLE Data
    ↓
Satellite Objects
    ↓
SGP4 Propagation
    ↓
ECI Position Vectors
    ↓
Position Tables
```

---

## Why Themis Exists

Space traffic management is becoming increasingly difficult as orbital density rises.

Before a collision can be predicted or avoided, a system must answer a simpler question:

> Where will every satellite be?

Themis begins by solving that problem and gradually expands toward large-scale autonomous coordination and collision avoidance.

---

## Architecture

Current architecture:

```text
CelesTrak TLE
      │
      ▼
Propagation Engine
      │
      ▼
Position Tables
      │
      ▼
Conjunction Detector
      │
      ▼
Event Reports
      │
      ▼
CSV Export
```

Planned architecture:

```text
TLE Data
     │
     ▼
Propagation Engine
     │
     ▼
Conjunction Detection
     │
     ▼
Risk Assessment
     │
     ▼
Maneuver Planning
     │
     ▼
Satellite Agents
     │
     ▼
Coordination Engine
     │
     ▼
Simulation Dashboard
```

---

## Technology Stack

Current:

- Python
- Skyfield
- SGP4
- NumPy
- Pandas

Planned:

- Plotly
- FastAPI
- PostgreSQL
- Agent frameworks
- Scientific Python ecosystem

---

## Project Roadmap

### Phase 1 — Propagation
- [x] Load TLE data
- [x] Create satellite objects
- [x] Propagate positions using SGP4
- [x] Generate future position tables

### Phase 2 — Conjunction Detection
- [x] Pairwise distance calculations
- [x] Close approach identification
- [x] Configurable warning thresholds
- [x] Conjunction event reporting

### Protocol Arena — Distributed Autonomy Foundation
- [x] Deterministic simulation runtime
- [x] Satellite agent model
- [x] Constrained network simulator
- [x] Centralized and greedy coordination protocols
- [x] Metrics summary and CLI experiment runner

Run the first protocol experiment:

```bash
python -m src.simulation.runner --scenario simple_10 --protocol greedy --seed 42
```

See [docs/protocol_arena.md](docs/protocol_arena.md) for details.

### Phase 3 — Collision Risk Analysis
- [ ] Risk scoring
- [ ] Orbital density studies
- [ ] Statistical conjunction analysis

### Phase 4 — Autonomous Coordination
- [ ] Satellite agents
- [ ] Maneuver negotiation
- [ ] Conflict resolution strategies

### Phase 5 — Large Scale Simulation
- [ ] Thousands of satellites
- [ ] Performance benchmarking
- [ ] Coordination experiments

---

## Future Research Questions

Themis is intended to investigate questions such as:

- How does conjunction frequency change as orbital density increases?
- Can decentralized coordination outperform centralized control?
- How many maneuvers can be avoided through negotiation?
- What tradeoffs exist between fuel usage and collision risk?
- How well do different coordination strategies scale?

---

## Current Limitations

Themis is still in active development.

Not yet implemented:

- Maneuver planning
- Agent coordination
- Visualization dashboard

Current propagation accuracy is dependent on publicly available TLE data and standard SGP4 modeling assumptions.

---

## Example Usage

```python
from themis.propagator import get_position

position = get_position(satellite)

print(position)
```

Example output:

```python
{
    "satellite": 'CALSPHERE1'
    'time': '2026-06-03T22:59:26Z'
    "x_km": -5231.8,
    "y_km": 1244.3,
    "z_km": 4087.6
}
```

---

## Development Philosophy

Themis is being developed as an engineering and research project rather than a simple software application.

The project emphasizes:

- Measurable experiments
- System architecture
- Scientific reproducibility
- Technical documentation
- Performance evaluation

---

## Author

Hem Vadgama

Computer Engineering
Penn State University (Schreyer Honors College)

Building systems at the intersection of space, simulation, autonomy, and software engineering.
