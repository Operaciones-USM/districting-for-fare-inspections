# ============================================================
# LIBRARY IMPORTS
# ============================================================
import os
import time
import math
import pandas as pd
import networkx as nx
import gurobipy as gp
from gurobipy import GRB
import random

# Set the seed
random.seed(1234)


# ============================================================
# AUXILIARY FUNCTIONS
# ============================================================

def parsear_lista_excel(valor):
    """
    Converts an Excel cell containing comma-separated elements into a list of ints.

    Parameters
    ----------
    valor : any
        Cell value.

    Returns
    -------
    list[int]
        List of parsed integers.
    """
    if pd.isna(valor):
        return []
    texto = str(valor).strip()
    if texto == "":
        return []
    return [int(x.strip()) for x in texto.split(",")]


def construir_grafo_adyacencia_connections(V, N):
    """
    Builds the global adjacency graph between connections.

    Parameters
    ----------
    V : list[int]
        List of connections.
    N : dict[int, list[int]]
        Adjacency dictionary.

    Returns
    -------
    networkx.Graph
        Undirected adjacency graph between connections.
    """
    G = nx.Graph()
    G.add_nodes_from(V)

    for e in V:
        for k in N.get(e, []):

            if e != k:
                G.add_edge(e, k)

    return G


def obtener_componentes_desconectadas(subgrafo):
    """
    Returns the disconnected connected components of a subgraph, excluding the largest component.

    Parameters
    ----------
    subgrafo : networkx.Graph
        Subgraph of the district.

    Returns
    -------
    list[list[int]]
        List of disconnected components (each represented as a list of nodes).
    """
    if subgrafo.number_of_nodes() == 0:
        return []

    if nx.is_connected(subgrafo):
        return []

    componentes = list(nx.connected_components(subgrafo))
    componentes.sort(key=len, reverse=True)

    # The largest component is excluded
    return [list(comp) for comp in componentes[1:]]


def obtener_frontera_componente(componente, N):
    """
    Retrieves the set of nodes adjacent to a component S,
    i.e.: (union_{k in S} N[k]) \\ S

    Parameters
    ----------
    componente : list[int]
        List of nodes in component S.
    N : dict[int, list[int]]
        Adjacency dictionary by node.

    Returns
    -------
    list[int]
        List of nodes adjacent to S and outside S.
    """
    S = set(componente)
    frontera = set()

    for e in componente:

        for vecino in N.get(e, []):

            if vecino not in S:
                frontera.add(vecino)

    return list(frontera)


def construir_subgrafo_desde_soporte(G_global, soporte):
    """
    Builds the subgraph induced by a set of nodes.

    Parameters
    ----------
    G_global : networkx.Graph
        Global adjacency graph.
    soporte : list[int]
        List of nodes in the district support.

    Returns
    -------
    networkx.Graph
        Induced subgraph.
    """
    return G_global.subgraph(soporte).copy()


def construir_grafo_auxiliar_node_split(subgrafo, y_v, centro, objetivo, inf_cap=1e9):
    """
    Builds the directed auxiliary graph to solve a minimum node cut
    between 'centro' and 'objetivo' using node splitting.

    For each node j:
        j_in -> j_out with capacity:
            - INF if j is center or target
            - y_v[j] in other cases

    For each undirected edge {a, b}:
        a_out -> b_in with capacity INF
        b_out -> a_in with capacity INF

    Parameters
    ----------
    subgrafo : networkx.Graph
        Base subgraph for the auxiliary graph.
    y_v : dict[int, float]
        Dictionary with fractional values Y[v, j] for j in the support.
    centro : int
        Center node of the district.
    objetivo : int
        Target node i.
    inf_cap : float, optional
        Sufficiently large "infinite" capacity.

    Returns
    -------
    networkx.DiGraph
        Directed auxiliary graph.
    """
    G_aux = nx.DiGraph()

    # Create "in" and "out" nodes and node-capacity arcs
    for j in subgrafo.nodes():
        j_in = f"{j}__in"
        j_out = f"{j}__out"

        G_aux.add_node(j_in)
        G_aux.add_node(j_out)

        if j == centro or j == objetivo:
            capacidad = inf_cap
        else:
            capacidad = max(0.0, float(y_v.get(j, 0.0)))

        G_aux.add_edge(j_in, j_out, capacity=capacidad)

    # Create connectivity arcs with infinite capacity
    for a, b in subgrafo.edges():
        a_out = f"{a}__out"
        a_in = f"{a}__in"
        b_out = f"{b}__out"
        b_in = f"{b}__in"

        G_aux.add_edge(a_out, b_in, capacity=inf_cap)
        G_aux.add_edge(b_out, a_in, capacity=inf_cap)

    return G_aux


def encontrar_separador_minimo(subgrafo, y_v, centro, objetivo):
    """
    Finds a minimum node separator between 'centro' and 'objetivo'
    in the given subgraph, using minimum s-t cut on the auxiliary graph
    with node splitting.

    Parameters
    ----------
    subgrafo : networkx.Graph
        Base subgraph for finding the separator.
    y_v : dict[int, float]
        Fractional values Y[v, j] for the support nodes.
    centro : int
        Center node.
    objetivo : int
        Target node i.

    Returns
    -------
    tuple[float, list[int]]
        (value of the min-cut, separator Z)
    """
    # If center and target are not in the subgraph, there is nothing to do
    if centro not in subgrafo.nodes() or objetivo not in subgrafo.nodes():
        return math.inf, []

    # If center = target, separation does not apply
    if centro == objetivo:
        return math.inf, []

    # If they are already disconnected in the support, the separator can be considered to have capacity 0
    if not nx.has_path(subgrafo, centro, objetivo):
        return math.inf, []

    # “Infinite” capacity that is sufficiently large
    # It is taken to be greater than the sum of all Y[v,j] in the support
    inf_cap = max(1.0, sum(y_v.values()) + 1.0)

    # Build auxiliary graph
    G_aux = construir_grafo_auxiliar_node_split(
        subgrafo=subgrafo,
        y_v=y_v,
        centro=centro,
        objetivo=objetivo,
        inf_cap=inf_cap
    )

    source = f"{centro}__out"
    sink = f"{objetivo}__in"

    # Solve minimum cut
    try:
        cut_value, (lado_source, lado_sink) = nx.minimum_cut(
            G_aux, source, sink, capacity="capacity"
        )
    except Exception as e:
        return math.inf, []

    # Restore the Z separator:
    # if j_in is on the source side and j_out is on the sink side, the edge j_in -> j_out has been cut
    separador = []
    for j in subgrafo.nodes():
        if j == centro or j == objetivo:
            continue

        j_in = f"{j}__in"
        j_out = f"{j}__out"

        if (j_in in lado_source) and (j_out in lado_sink):
            separador.append(j)

    # Minor numerical filtering
    suma_separador = sum(y_v.get(j, 0.0) for j in separador)
    if abs(suma_separador - cut_value) <= 1e-6:
        cut_value = suma_separador

    return cut_value, separador


# ============================================================
# MAIN FUNCTION
# ============================================================

def ejecutar_instancia(m, alfa, n, cpu_limit=259200, eps_frac=0.2, eps_int=0.9):
    """
    Run an instance of the districting problem using:
    - Lazy constraints of Drexl-Haase in integer solutions (MIPSOL).
    - User cuts of Drexl-Haase and separator constraints in fractional solutions (MIPNODE).

    Parameters
    ----------
    m : int
        Instance size relative to the coverage radius in meters.
    alfa : float
        Balance tolerance.
    n : int
        Maximum number of districts.
    cpu_limit : int, optional
        CPU time limit in seconds.
    eps_frac : float, optional
        Tolerance for considering a variable positive in fractional solutions.
    eps_int : float, optional
        Tolerance for considering a variable equal to 1 in integer solutions.
    """
    print("\n===========================================================")
    print(f"Execution starts for {m} meters with alfa = {alfa} and n = {n}")
    print("===========================================================")

    # --------------------------------------------------------
    # Path definitions
    # --------------------------------------------------------
    carpeta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

    ruta_connections = os.path.join(carpeta, f"grafo_connections_{m}m.xlsx")
    ruta_distancias = os.path.join(carpeta, f"distancias_connections_{m}m.xlsx")

    # --------------------------------------------------------
    # Loading input files
    # --------------------------------------------------------
    data_grafo = pd.ExcelFile(ruta_connections)
    matriz_distancias = pd.read_excel(ruta_distancias, header=0, index_col=0)

    # --------------------------------------------------------
    # Loading sets
    # --------------------------------------------------------
    V = data_grafo.parse("Conjunto V")["Connection"].tolist()
    W = data_grafo.parse("Conjunto W")["Connection"].tolist()
    L = data_grafo.parse("Conjunto L")["Bus line"].tolist()

    # --------------------------------------------------------
    # Loading adjacencies N(v)
    # --------------------------------------------------------
    N = data_grafo.parse("Conjunto V").set_index(
        "Connection"
    )["Conjunto Nv"].apply(parsear_lista_excel).to_dict()

    # --------------------------------------------------------
    # Loading sets O(l)
    # --------------------------------------------------------
    O = data_grafo.parse("Conjunto L").set_index(
        "Bus line"
    )["Conjunto O_{l}"].apply(parsear_lista_excel).to_dict()


    # --------------------------------------------------------
    # Parameters h and M
    # --------------------------------------------------------
    h = data_grafo.parse("Conjunto L").set_index(
        "Bus line"
    )["Frecuencia"].to_dict()
    M = sum(h[l] for l in L)

    # --------------------------------------------------------
    # Distance parameter d
    # --------------------------------------------------------
    d = {}
    for e, row in matriz_distancias.iterrows():
        for k, value in row.items():
            d[(int(e), int(k))] = int(value)


    # --------------------------------------------------------
    # Construction of the global adjacency graph
    # --------------------------------------------------------
    G_global = construir_grafo_adyacencia_connections(V, N)

    # --------------------------------------------------------
    # Model creation
    # --------------------------------------------------------
    model = gp.Model("Districting")

    # --------------------------------------------------------
    # Decision variables
    # --------------------------------------------------------
    X = model.addVars(W, vtype=GRB.BINARY, name="X")
    Y = model.addVars(W, V, vtype=GRB.BINARY, name="Y")
    H = model.addVars(W, L, vtype=GRB.BINARY, name="H")
    Q = model.addVars(W, lb=0, name="Q")
    Qover = model.addVar(lb=0, name="Qover")
    Qunder = model.addVar(lb=0, name="Qunder")

    # --------------------------------------------------------
    # Objective function
    # --------------------------------------------------------
    model.setObjective(
        gp.quicksum(d[v, v2] * Y[v, v2] for v in W for v2 in V),
        GRB.MINIMIZE
    )

    # ========================================================
    # MODEL CONSTRAINTS
    # ========================================================

    # Constraint 2: each hexagon is assigned to exactly one district
    for v2 in V:
        model.addConstr(
            gp.quicksum(Y[v, v2] for v in W) == 1,
            name=f"R2_{v2}"
        )

    # Constraint 3: can only be assigned to an active center
    for v in W:
        for v2 in V:
            model.addConstr(
                Y[v, v2] <= X[v],
                name=f"R3_{v}_{v2}"
            )

    # Constraint 5
    for v in W:
        for l in L:
            for v2 in O[l]:
                model.addConstr(
                    H[v, l] >= Y[v, v2],
                    name=f"R5_{v}_{l}_{v2}"
                )

    # Constraint 6
    for v in W:
        for l in L:
            model.addConstr(
                H[v, l] <= gp.quicksum(Y[v, v2] for v2 in O[l]),
                name=f"R6_{v}_{l}"
            )

    # Constraint 7
    for v in W:
        model.addConstr(
            Q[v] == gp.quicksum(h[l] * H[v, l] for l in L),
            name=f"R7_{v}"
        )

    # Constraint 8
    for v in W:
        model.addConstr(
            Qover >= Q[v],
            name=f"R8_{v}"
        )

    # Constraint 9
    for v in W:
        model.addConstr(
            Q[v] >= Qunder - (1 - X[v]) * M,
            name=f"R9_{v}"
        )

    # Constraint 10
    model.addConstr(
        Qover <= Qunder * (1 + alfa),
        name="R10"
    )

    # Constraint 11
    model.addConstr(
        gp.quicksum(X[v] for v in W) <= n,
        name="R11"
    )

    # Constraint to avoid |S| = 1
    for v in W:
        for v2 in V:
            model.addConstr(
                Y[v, v2] <= gp.quicksum(Y[v, u] for u in N.get(v2, [])),
                name=f"R14_{v}_{v2}"
            )

    # ========================================================
    # SEPARATION CALLBACK
    # ========================================================

    def contiguity_and_separator_callback(model, where):
        """
        Hybrid callback:
        - MIPNODE (fractional solution):
            * separates Drexl-Haase cuts with cbCut
            * separates separator constraints with cbCut
        - MIPSOL (integer solution):
            * separates Drexl-Haase with cbLazy
        """
        # ----------------------------------------------------
        # Termination by CPU time
        # ----------------------------------------------------
        if time.process_time() - cpu_start > cpu_limit:
            model.terminate()
            return

        # ====================================================
        # CASE 1: FRACTIONAL NODE SOLUTION (MIPNODE)
        # ====================================================
        if where == GRB.Callback.MIPNODE:
            status = model.cbGet(GRB.Callback.MIPNODE_STATUS)

            if status == GRB.OPTIMAL:
                print("\n[DEBUG] --- Nodo MIPNODE (fractional solution) ---")

            # cbGetNodeRel can be used only if the node's state is OPTIMAL
            if status != GRB.OPTIMAL:
                return
            
            # ------------------------------------------------
            # Filter to avoid entering all fractional nodes
            # ------------------------------------------------
            elapsed_cpu = time.process_time() - cpu_start

            if elapsed_cpu < 21600:
                prob = 0.6
            elif elapsed_cpu < 64800:
                prob = 0.4
            else:
                prob = 0.2

            # Perform the probabilistic test
            if random.random() > prob:
                return

            # Retrieve current LP relaxation
            Xrel = model.cbGetNodeRel(X)
            Yrel = model.cbGetNodeRel(Y)

            # ------------------------------------------------
            # Iterate over centers with X[v] > 0
            # ------------------------------------------------
            for v in W:
                if Xrel[v] <= eps_frac:
                    continue

                # Fractional support of district v: nodes with Y[v, i] > 0
                soporte_v = [i for i in V if Yrel[v, i] > eps_frac]

                # If the support is empty or has only one node, there is nothing relevant
                if len(soporte_v) <= 1:
                    continue

                # Build induced support subgraph
                G_sub = construir_subgrafo_desde_soporte(G_global, soporte_v)

                # ------------------------------------------------
                # 1) Drexl-Haase separation in MIPNODE
                # ------------------------------------------------
                if G_sub.number_of_nodes() > 0 and not nx.is_connected(G_sub):
                    componentes_disconexas = obtener_componentes_desconectadas(G_sub)

                    for componente in componentes_disconexas:
                        componente_tuple = tuple(sorted(componente))

                        # Avoid duplicating the same subset S as a user cut
                        if componente_tuple in model._dh_cuts_added:
                            continue

                        frontera = obtener_frontera_componente(componente, N)
                        rhs = 1 - len(componente)

                        # Add the cut for all potential centers
                        for vv in W:
                            expr_frontera = gp.quicksum(Y[vv, j] for j in frontera)
                            expr_comp = gp.quicksum(Y[vv, j] for j in componente)

                            # User cut (valid for fractional solutions)
                            model.cbCut(expr_frontera - expr_comp >= rhs)

                        model._dh_cuts_added.add(componente_tuple)
                        model._n_dh_cuts += 1

                # ------------------------------------------------
                # 2) Separator constraints separation in MIPNODE
                # ------------------------------------------------
                # Local dictionary of Y[v, j] values
                y_v = {j: float(Yrel[v, j]) for j in V}

                for i in soporte_v:
                    # It does not make sense to separate the center from itself
                    if i == v:
                        continue

                    y_vi = float(Yrel[v, i])

                    # ------------------------------------------------
                    # Filter 1 to reduce the number of min-cuts: only consider Y[v,i] sufficiently large
                    # ------------------------------------------------
                    if y_vi <= 0.8:
                        continue

                    # ------------------------------------------------
                    # Filter 2 to reduce the number of min-cuts: probability dependent on CPU time
                    # ------------------------------------------------
                    elapsed_cpu = time.process_time() - cpu_start

                    if elapsed_cpu < 25920:
                        prob = 0.8
                    elif elapsed_cpu < 69120:
                        prob = 0.6
                    elif elapsed_cpu < 103680:
                        prob = 0.4
                    elif elapsed_cpu < 138240:
                        prob = 0.2
                    else:
                        prob = 0.1

                    # Perform the probabilistic test
                    if random.random() > prob:
                        continue

                    # Solve the minimum cut problem for nodes v and i
                    cut_value, separador = encontrar_separador_minimo(
                        subgrafo=G_global,
                        y_v=y_v,
                        centro=v,
                        objetivo=i,
                    )

                    # If no useful separator is obtained, continue
                    if separador is None:
                        continue
                    if len(separador) == 0:
                        continue

                    suma_separador = sum(y_v.get(j, 0.0) for j in separador)

                    # Check violation: Y[v, i] > sum_{j in Z} Y[v, j]
                    if y_vi > suma_separador + 1e-6:
                        key_sep = (v, i, tuple(sorted(separador)))

                        # Avoid duplicates
                        if key_sep in model._separator_cuts_added:
                            continue

                        # Add separator constraint as a user cut
                        expr_sep = gp.quicksum(Y[v, j] for j in separador)

                        # If separador = [] => Y[v, i] <= 0
                        model.cbCut(Y[v, i] <= expr_sep)

                        model._separator_cuts_added.add(key_sep)
                        model._n_separator_cuts += 1

        # ====================================================
        # CASE 2: INCUMBENT INTEGER SOLUTION (MIPSOL)
        # ====================================================
        elif where == GRB.Callback.MIPSOL:
            print("\n[DEBUG] === New incumbent solution found ===")

            # Retrieve incumbent solution
            Xsol = model.cbGetSolution(X)
            Ysol = model.cbGetSolution(Y)

            # Retrieve incumbent centers
            centros = [v for v in W if Xsol[v] > eps_int]

            # Check each incumbent district
            for centro in centros:
                distrito = [i for i in V if Ysol[centro, i] > eps_int]

                # If the district is empty or has only one node, there is nothing to check
                if len(distrito) <= 1:
                    continue

                # Build induced subgraph
                G_sub = construir_subgrafo_desde_soporte(G_global, distrito)

                # If it is connected, no lazy constraints are required
                if G_sub.number_of_nodes() == 0 or nx.is_connected(G_sub):
                    continue

                # Obtain disconnected components (except the largest)
                componentes_disconexas = obtener_componentes_desconectadas(G_sub)

                # Counter per incumbent
                n_cortes_it = 0

                # Add Drexl-Haase lazy constraints
                for componente in componentes_disconexas:
                    componente_tuple = tuple(sorted(componente))

                    # Evitar duplicar la misma lazy constraint
                    if componente_tuple in model._dh_lazy_added:
                        continue

                    frontera = obtener_frontera_componente(componente, N)
                    rhs = 1 - len(componente)

                    n_cortes_it += 1

                    for v in W:
                        expr_frontera = gp.quicksum(Y[v, j] for j in frontera)
                        expr_comp = gp.quicksum(Y[v, j] for j in componente)

                        model.cbLazy(expr_frontera - expr_comp >= rhs)

                    model._dh_lazy_added.add(componente_tuple)
                    model._n_dh_lazy += 1

    # ========================================================
    # STRUCTURES TO AVOID DUPLICATES
    # ========================================================
    model._dh_cuts_added = set()          # Drexl-Haase added as user cuts (MIPNODE)
    model._separator_cuts_added = set()   # Separator constraints added as user cuts (MIPNODE)
    model._dh_lazy_added = set()          # Drexl-Haase added as lazy constraints (MIPSOL)

    model._n_dh_cuts = 0
    model._n_separator_cuts = 0
    model._n_dh_lazy = 0

    # ========================================================
    # MODEL SOLUTION
    # ========================================================
    cpu_start = time.process_time()

    # Required for lazy constraints
    model.Params.LazyConstraints = 1

    # Recommended when adding custom user cuts
    model.Params.PreCrush = 1

    model.Params.LogToConsole = 1
    model.Params.Method = 1
    model.Params.MIPFocus = 1

    model.optimize(contiguity_and_separator_callback)

    # ========================================================
    # EXECUTION METRICS
    # ========================================================
    duracion_reloj = model.getAttr(GRB.Attr.Runtime)
    duracion_cpu = time.process_time() - cpu_start

    # ========================================================
    # CONSOLE REPORT
    # ========================================================
    print("\n===========================================================")
    print("SUMMARY OF ADDED CUTS")
    print("===========================================================")
    print(f"Drexl-Haase as user cuts (MIPNODE): {model._n_dh_cuts}")
    print(f"Separator constraints as user cuts (MIPNODE): {model._n_separator_cuts}")
    print(f"Drexl-Haase as lazy constraints (MIPSOL): {model._n_dh_lazy}")
    print("===========================================================")

    print(f"\nWall-clock time: {duracion_reloj:.4f} segundos -> {duracion_reloj / 60:.4f} minutos.")
    print(f"CPU time: {duracion_cpu:.4f} segundos -> {duracion_cpu / 60:.4f} minutos.")

    # ========================================================
    # SAVING RESULTS
    # ========================================================
    ruta_excel_salida = os.path.join(
        carpeta,
        f"Separador_Resultados_Connections_{m}m_cpu{cpu_limit}_alfa{alfa}_n{n}.xlsx"
    )

    # Check whether a solution was found
    if model.SolCount > 0:
        # Retrieve variable X
        X_sol = pd.DataFrame([
            {"Distrito": v, "X": X[v].X}
            for v in W
        ])

        # Identify used district centers
        centros_distrito = X_sol[X_sol["X"] > eps_int].copy()
        hexagonos_centros = centros_distrito["Distrito"].tolist()

        # Retrieve variable Y
        asignacion_hexagonos_excel = pd.DataFrame([
            {"Distrito": v, "Hexagon": v2}
            for v in W
            for v2 in V
            if Y[v, v2].X > eps_int
        ])

        # Retrieve variable Q
        Q_excel = pd.DataFrame([
            {"Distrito": v, "Q": Q[v].X}
            for v in hexagonos_centros
        ])

        # Summary of cuts
        resumen_cortes = pd.DataFrame([
            {"Tipo de corte": "Drexl-Haase user cuts (MIPNODE)", "Cantidad": model._n_dh_cuts},
            {"Tipo de corte": "Separator constraints user cuts (MIPNODE)", "Cantidad": model._n_separator_cuts},
            {"Tipo de corte": "Drexl-Haase lazy constraints (MIPSOL)", "Cantidad": model._n_dh_lazy},
            {"Tipo de corte": "Total", "Cantidad": model._n_dh_cuts + model._n_separator_cuts + model._n_dh_lazy}
        ])

        # Save results
        with pd.ExcelWriter(ruta_excel_salida) as writer:
            asignacion_hexagonos_excel.to_excel(writer, sheet_name="Asignacion", index=False)
            Q_excel.to_excel(writer, sheet_name="Buses por distrito", index=False)
            resumen_cortes.to_excel(writer, sheet_name="Resumen cortes", index=False)

    else:
        print(f"The model finished without feasible solutions. Status={model.Status}")


# ============================================================
# MAIN LOOP
# ============================================================
alfas = [1]
ns = [10]
ms = [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000]

for n in ns:
    for alfa in alfas:
        for m in ms:
            ejecutar_instancia(m, alfa, n)
