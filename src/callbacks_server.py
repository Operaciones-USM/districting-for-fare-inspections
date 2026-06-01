# Importar bibliotecas necesarias
import os
import time
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import gurobipy as gp
from gurobipy import GRB

# ----------------------------
# Función principal de ejecución
# ----------------------------
def ejecutar_instancia(hex, alfa, n, cpu_limit=432000):

    print(f"\n===========================================================")
    print(f"Se comienza ejecución para {hex} hexagonos con alfa = {alfa} y n = {n}")
    print(f"===========================================================")

    # Definir rutas de archivos
    escritorio = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    ruta_hexagonos = os.path.join(escritorio, f"grafo_hexagons_{hex}hex.xlsx")
    ruta_distancias = os.path.join(escritorio, f'distancias_{hex}hex.xlsx')

    # Cargar archivos de entrada en pandas
    data_grafo = pd.ExcelFile(ruta_hexagonos)
    matriz_distancias = pd.read_excel(ruta_distancias, header=0, index_col=0)
    df_arcos_hexagonos = pd.read_excel(ruta_hexagonos, sheet_name='arcos_hexagonos')

    # Cargar listas de conjuntos desde hojas específicas del archivo de datos
    V = data_grafo.parse("hexagons")['Hexagon'].tolist()
    L = data_grafo.parse("Conjunto L")['Bus line'].tolist()
    W = V

    # Crear diccionario Nv: hexagonos adyacentes a cada hexagono
    N = data_grafo.parse("hexagons").set_index('Hexagon')['Conjunto Nv'].apply(
        lambda x: [i for i in x.split(',')] if ',' in str(x) else [x]
    ).to_dict()

    # Crear diccionario Ɛ(l): hexagonos recorridos por cada línea
    Ɛ = data_grafo.parse("Conjunto L").set_index('Bus line')['Conjunto Ɛ_{l}'].apply(
        lambda x: [i for i in x.split(',')] if ',' in str(x) else [x]
    ).to_dict()

    # Cargar parámetros h (frecuencia de buses)
    h = data_grafo.parse("Conjunto L").set_index('Bus line')['Frecuencia'].to_dict()

    # Cargar parámetro M grande (cota superior de cantidad de buses)
    M = sum(h[l] for l in L)

    # Cargar parámetro d (distancia entre hexagonos)
    d = {}
    for v, row in matriz_distancias.iterrows():
        for v2, value in row.items():
            d[(v, v2)] = int(value)

    # Crear modelo
    model = gp.Model("Districting")

    # Definir variables
    X = model.addVars(W, vtype=GRB.BINARY, name="X")
    Y = model.addVars(W, V, vtype=GRB.BINARY, name="Y")
    H = model.addVars(W, L, vtype=GRB.BINARY, name="H")
    Q = model.addVars(W, lb=0, name="Q")
    Qover = model.addVar(lb=0, name="Qover")
    Qunder = model.addVar(lb=0, name="Qunder")

    # Función objetivo
    model.setObjective(
        gp.quicksum(d[v, v2] * Y[v, v2] for v in W for v2 in V),
        GRB.MINIMIZE
    )

    # ----------------------------
    # Restricciones
    # ----------------------------

    # Restricción 2
    for v2 in V:
        model.addConstr(gp.quicksum(Y[v, v2] for v in W) == 1, name=f"R2_{v2}")

    # Restricción 3
    for v in W:
        for v2 in V:
            model.addConstr(Y[v, v2] <= X[v], name=f"R3_{v}_{v2}")

    # Restricción 5
    for v in W:
        for l in L:
            for v2 in Ɛ[l]:
                model.addConstr(H[v, l] >= Y[v, v2], name=f"R5_{v}_{l}_{v2}")

    # Restricción 6
    for v in W:
        for l in L:
            model.addConstr(H[v, l] <= gp.quicksum(Y[v, v2] for v2 in Ɛ[l]), name=f"R6_{v}_{l}")

    # Restricción 7
    for v in W:
        model.addConstr(Q[v] == gp.quicksum(h[l] * H[v, l] for l in L), name=f"R7_{v}")

    # Restricción 8
    for v in W:
        model.addConstr(Qover >= Q[v], name=f"R8_{v}")

    # Restricción 9
    for v in W:
        model.addConstr(Q[v] >= Qunder - (1 - X[v]) * M, name=f"R9_{v}")

    # Restricción 10
    model.addConstr(Qover <= Qunder * (1 + alfa), name="R10")

    # Restricción 11
    model.addConstr(gp.quicksum(X[v] for v in W) <= n, name="R11")

    # Restricción para evitar |S|=1
    for v in W:
        for v2 in V:
            model.addConstr(
                Y[v, v2] <= gp.quicksum(Y[v, u] for u in N[v2]),
                name=f"R14_{v}_{v2}"
            )

    # ----------------------------
    # Callback contigüidad
    # ----------------------------
    def contiguity_callback(model, where):
        if time.process_time() - cpu_start > cpu_limit:
            model.terminate()

        if where == GRB.Callback.MIPSOL:
        
            # Recuperar solución incumbente
            Xsol = model.cbGetSolution(X)
            Ysol = model.cbGetSolution(Y)

            # Recuperar centros del incumbente
            centros = []
            for v, val in Xsol.items():
                if val > 0.9:
                    centros.append(v)

            # Recuperar distritos del incumbente
            distritos = dict()
            for v in centros:
                distrito_v = []
                for (vv, v2), val in Ysol.items():
                    if vv == v and val > 0.9:
                        distrito_v.append(v2)
                distritos[v] = distrito_v

            # Revisar cada distrito del incumbente
            componentes_disconexas_hexagonos = []
            for centro, distrito in distritos.items():
                # Crear subgrafo de cada distrito
                G = nx.Graph()
                for hexagono in distrito:
                    G.add_node(hexagono)
                for idx, arco in df_arcos_hexagonos.iterrows():
                    hex1 = arco["Hexagon 1"]
                    hex2 = arco["Hexagon 2"]
                    if hex1 in distrito and hex2 in distrito:
                        G.add_edge(hex1, hex2, id_arco=arco["Arco"])

                # Verificar si el subgrafo es conexo
                if not nx.is_connected(G):
                    # Obtener las componentes conexas
                    componentes = list(nx.connected_components(G))

                    # Ordenar las componentes por tamaño (descendente)
                    componentes.sort(key=len, reverse=True)

                    # Construir lista de componentes disconexas
                    for comp in componentes[1:]:  # Excluir la más grande
                        subgrafo = G.subgraph(comp)
                        hexagonos_componente = list(subgrafo.nodes())
                        componentes_disconexas_hexagonos.append(hexagonos_componente)

            # Construir restricciones lazy
            n_cortes_it = 0
            print(f"Componentes disconexas: {componentes_disconexas_hexagonos}")
            for componente in componentes_disconexas_hexagonos:
                # Verificar si las restricciones de la componente ya han sido agregadas
                componente_tuple = tuple(sorted(componente))  # Convertir lista en tupla ordenada
                if componente_tuple not in model._lazy_constraints_added:
                    right_eq = 1 - len(componente)
                    adyacentes_componente = []
                    for connection in componente:
                        for k in N[connection]:
                            if k not in componente and k not in adyacentes_componente:
                                adyacentes_componente.append(k)
                    for v in W:
                        expr1 = gp.quicksum(Y[v, v2] for v2 in adyacentes_componente)
                        expr2 = gp.quicksum(Y[v, v2] for v2 in componente)
                        model.cbLazy(expr1 - expr2 >= right_eq)
                    # Guardar la componente agregada
                    model._lazy_constraints_added.add(componente_tuple)
                    n_cortes_it += 1
            # Imprimir numero de cortes agregados
            print(f"Para este candidato a incumbente, se agregan restricciones de contiguidad para {n_cortes_it} subconjuntos.")
            

    # Para almacenar restricciones de contiguidad agregadas
    model._lazy_constraints_added = set()

    # ----------------------------
    # Resolver modelo
    # ----------------------------
    cpu_start = time.process_time()
    model.Params.LazyConstraints = 1
    model.Params.LogToConsole = 1
    model.Params.Method = 1
    model.optimize(contiguity_callback)

    duracion_reloj = model.getAttr(GRB.Attr.Runtime)
    duracion_cpu = time.process_time() - cpu_start
    n_cortes = len(model._lazy_constraints_added)

    # ----------------------------
    # Guardar resultados
    # ----------------------------

    ruta_excel_salida = os.path.join(escritorio, f'Resultados_{hex}hex_cpu{cpu_limit}_alfa{alfa}_n{n}.xlsx')

    print(f"\nSe añadieron cortes para {n_cortes} subconjuntos.")
    print(f"\nTiempo reloj: {duracion_reloj} segundos -> {duracion_reloj / 60} minutos.")
    print(f"\nTiempo CPU: {duracion_cpu} segundos -> {duracion_cpu / 60} minutos.")

    # Verificar si se encuentra solución
    if model.SolCount > 0:
        # Rescatar variable X
        X_sol = pd.DataFrame([
            {"Distrito": v, "X": X[v].X}
            for v in W
        ])

        # Identificar centros de distrito utilizados
        centros_distrito = X_sol[X_sol["X"] > 0.9].copy()
        hexagonos_centros = centros_distrito["Distrito"].tolist()

        # Rescatar variable Y
        asignacion_hexagonos_excel = pd.DataFrame([
            {"Distrito": v, "Hexagon": v2}
            for v in W
            for v2 in V
            if Y[v,v2].X > 0.9
        ])

        # Rescatar variable Q
        Q_excel = pd.DataFrame([
            {"Distrito": v, "Q": Q[v].X}
            for v in hexagonos_centros
        ])

        # Guardar resultados en un archivo Excel
        with pd.ExcelWriter(ruta_excel_salida) as writer:
            asignacion_hexagonos_excel.to_excel(writer, sheet_name='Asignacion', index=False)
            Q_excel.to_excel(writer, sheet_name='Buses por distrito', index=False)

    else:
        print(f"El modelo terminó sin soluciones factibles. Status={model.Status}")

# ----------------------------
# Bucle principal
# ----------------------------
alfas = [1.25, 1, 0.75, 0.5, 0.25]
ns = [10]
hexs = [250]

for hex in hexs:
    for n in ns:
        for alfa in alfas:
            ejecutar_instancia(hex, alfa, n)