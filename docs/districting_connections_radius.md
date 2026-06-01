# Districting Model with Connectivity Separation Cuts

## Overview

This repository contains a Python implementation of a districting optimization model solved with Gurobi.

The model incorporates:
- Classical districting constraints
- Workload balancing constraints
- Connectivity constraints
- Drexl-Haase connectivity cuts
- Separator constraints based on minimum node cuts

The implementation uses:
- Lazy constraints (`cbLazy`) for integer incumbent solutions
- User cuts (`cbCut`) for fractional node solutions

The objective is to generate connected districts while minimizing the total assignment distance between basic units and district centers.

---

## Main Features

### Optimization Model

The model is formulated as a mixed-integer programming (MIP) problem using:
- `gurobipy`
- `networkx`
- `pandas`

### Connectivity Enforcement

Connectivity is handled dynamically during the branch-and-cut process through:
- Drexl-Haase cuts
- Separator constraints generated from minimum node cuts

### Fractional and Integer Separation

The callback implementation distinguishes between:
- Fractional LP solutions (`MIPNODE`)
- Integer incumbent solutions (`MIPSOL`)

Different classes of cuts are added depending on the solution type.

---

## Input Files

The code expects the following Excel files:

- `grafo_connections_<m>m.xlsx`
- `distancias_connections_<m>m.xlsx`

These files contain:
- Connections sets
- Bus lines
- Adjacency relations
- Distance matrices
- Frequency parameters

---

## Main Libraries

The following Python libraries are required:

```python
pandas
networkx
gurobipy
openpyxl
```

---

## Code Structure

The script is organized into the following sections:

1. Library imports
2. Auxiliary functions
3. Graph construction procedures
4. Minimum separator generation
5. Mathematical model construction
6. Callback-based cut separation
7. Optimization execution
8. Result export

---

## Callback Logic

The callback performs two main tasks.

### MIPNODE

For fractional solutions:
- Separates Drexl-Haase cuts
- Separates separator constraints

Cuts are added using:

```python
model.cbCut(...)
```

### MIPSOL

For integer incumbent solutions:
- Detects disconnected districts
- Adds lazy connectivity constraints

Constraints are added using:

```python
model.cbLazy(...)
```

---

## Output

The code generates an Excel file containing:
- Basic units assignments
- District workloads
- Summary of generated cuts

---

## Notes

- The implementation was designed for computational experiments on districting problems.
- The callback uses probabilistic filtering to reduce the number of separation procedures evaluated during optimization.
- CPU-time limits can be configured through the `cpu_limit` parameter.

---

## Author Notes

This code was prepared as part of academic research on districting optimization problems with connectivity constraints.
