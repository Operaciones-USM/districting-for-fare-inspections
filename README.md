# Balanced fare inspection districts for large-scale urban bus transportation systems: a workload-sharing approach V.0.1

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
- `python districting_connections_radius.py`: Runs the model evaluating connections within a specific radius, in accordance with the experiments described in Section 5.1.1 of the paper.
- `python districting_tesselation_radius.py`: Runs the model evaluating polygonal areas (tessellation technique) within a specific radius, in accordance with the experiments described in Section 5.1.2 of the paper.
- `python districting.py`: Runs the model considering polygonal areas (tessellation technique) for different values of parameters and considering W=V, in accordance with the experiments described in Section 5.2 of the paper.
- `python districting_W.py`: Runs the model considering polygonal areas (tessellation technique) for different values of parameters and considering a good quality set W, in accordance with the experiments described in Section 5.2 of the paper.

Output files (like `Districting_...xlsx`) will automatically be placed in the `data/` folder.

## Citation

If you use this code in your research, please cite the corresponding manuscript:

```bibtex
@article{escalona_districting,
  title={Urban bus transportation system districting for fare inspections},
  author={Escalona, Pablo and Brotcorne, Luce and Cerda, Daniel and Wolf, Nathalia and Torrealba, Pablo},
  year={2026}
}
```
