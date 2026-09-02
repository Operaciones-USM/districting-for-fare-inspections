# Districting Model with Connectivity Separation Cuts

## Overview

This repository contains a Python implementation of a districting optimization model solved with Gurobi.

The model incorporates:
- Classical districting constraints
- Workload balancing constraints
- Connectivity constraints based on vertex-separators

The implementation uses:
- Lazy constraints (`cbLazy`) for integer incumbent solutions
- User cuts (`cbCut`) for fractional node solutions when the parameter use_fractional_mincut is activated in the main function ejecutar_instancia 

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
- Separator constraints generated for the minimal separators, obtained through the procedure of Validi et al. or solving a min-cut problem

### Fractional and Integer Separation

The callback implementation distinguishes between:
- Fractional LP solutions (`MIPNODE`)
- Integer incumbent solutions (`MIPSOL`)

Different classes of cuts are added depending on the solution type.

---

## Input Files

The code expects the following Excel files:

- `grafo_hexagons_<m>m.xlsx`
- `distancias_<m>m.xlsx`

These files contain:
- Hexagon sets
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
deque
```

---

## Code Structure

The script is organized into the following sections:

1. Library imports
2. Auxiliary functions
3. Graph construction procedures
4. Minimal (Validi et al.) and minimum (min-cut) separator generation
5. Mathematical model construction
6. Callback-based cut separation
7. Optimization execution
8. Result export

---

## Callback Logic

The callback performs a main task.

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
- When parameter use_fractional_mincut is acitvated, the callback uses probabilistic filtering to reduce the number of separation procedures evaluated during fractional separation.
- CPU-time limits can be configured through the `cpu_limit` parameter.

---

## Author Notes

This code was prepared as part of academic research on districting optimization problems with connectivity constraints.
