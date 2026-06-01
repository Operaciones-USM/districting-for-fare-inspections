# Districting for Fare Inspections V.0.1

This repository contains the codebase and manuscript for the "Districting for Fare Inspections" project. 

## Structure

- `data/`: Contains Excel datasets (`.xlsx`) used by the Python scripts for graphs and district information.
- `src/`: Python source code for data processing and generating districts.
- `docs/`: Markdown documentation explaining the different districting algorithms.
- `paper/`: LaTeX source files for the manuscript.

## Reproducing Paper Experiments

To run the districting models and algorithms discussed in the paper, please follow these steps:

### 1. Requirements

Ensure you have Python 3 installed. Install the required data-science and optimization packages using the provided `requirements.txt`:

```bash
pip install -r requirements.txt
```

> **Important Note on Gurobi**: The districting models formulate complex Mixed-Integer Programming (MIP) problems and use the `gurobipy` solver. To execute these models, you **must have a valid Gurobi license** (an academic license is free for researchers). Ensure your license is activated on your machine before running the scripts.

### 2. Running the Models

Navigate to the `src/` directory to run the districting algorithms. The primary algorithms generate Excel outputs in the `data/` directory based on different parameters.

For the standard districting model:
```bash
cd src
python districting.py
```

For alternative formulations and tests:
- `python districting_W.py`: Runs the model incorporating walking distances.
- `python districting_connections_radius.py`: Runs the model evaluating connections within a specific radius.
- `python districting_tesselation_radius.py`: Runs the model with tessellation constraints.
- `python modelo1_distritos_ampl.py`: Runs the base model variant.

Output files (like `Separador_Resultados_...xlsx`) will automatically be placed in the `data/` folder.
