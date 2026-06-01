# ============================================================
# IMPORTACION DE BIBLIOTECAS
# ============================================================
import os
import time
import math
import pandas as pd
import networkx as nx
import gurobipy as gp
from gurobipy import GRB


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def parsear_lista_excel(valor):
    """
    Convierte una celda de Excel que contiene elementos separados por coma
    en una lista de strings limpios.

    Parameters
    ----------
    valor : any
        Valor de la celda.

    Returns
    -------
    list[str]
        Lista de elementos parseados.
    """
    if pd.isna(valor):
        return []
    texto = str(valor).strip()
    if texto == "":
        return []
    return [x.strip() for x in texto.split(",")]


def construir_grafo_adyacencia(V, df_arcos_hexagonos):
    """
    Construye el grafo global de adyacencia entre hexágonos.

    Parameters
    ----------
    V : list[str]
        Lista de hexágonos.
    df_arcos_hexagonos : pandas.DataFrame
        DataFrame con las columnas 'Hexagon 1' y 'Hexagon 2'.

    Returns
    -------
    networkx.Graph
        Grafo no dirigido de adyacencia.
    """
    G = nx.Graph()
    G.add_nodes_from(V)

    for _, arco in df_arcos_hexagonos.iterrows():
        hex1 = str(arco["Hexagon 1"]).strip()
        hex2 = str(arco["Hexagon 2"]).strip()
        G.add_edge(hex1, hex2)

    return G


def obtener_componentes_desconectadas(subgrafo):
    """
    Retorna las componentes conexas desconectadas de un subgrafo,
    excluyendo la componente más grande.

    Parameters
    ----------
    subgrafo : networkx.Graph
        Subgrafo del distrito.

    Returns
    -------
    list[list[str]]
        Lista de componentes desconectadas (cada una como lista de nodos).
    """
    if subgrafo.number_of_nodes() == 0:
        return []

    if nx.is_connected(subgrafo):
        return []

    componentes = list(nx.connected_components(subgrafo))
    componentes.sort(key=len, reverse=True)

    # Se excluye la componente más grande
    return [list(comp) for comp in componentes[1:]]


def obtener_frontera_componente(componente, N):
    """
    Obtiene el conjunto de nodos adyacentes a una componente S,
    es decir: (union_{k in S} N[k]) \\ S

    Parameters
    ----------
    componente : list[str]
        Lista de nodos de la componente S.
    N : dict[str, list[str]]
        Diccionario de adyacencia por nodo.

    Returns
    -------
    list[str]
        Lista de nodos adyacentes a S y fuera de S.
    """
    S = set(componente)
    frontera = set()

    for k in componente:
        for vecino in N.get(k, []):
            if vecino not in S:
                frontera.add(vecino)

    return list(frontera)


def construir_subgrafo_desde_soporte(G_global, soporte):
    """
    Construye el subgrafo inducido por un conjunto de nodos.

    Parameters
    ----------
    G_global : networkx.Graph
        Grafo global de adyacencia.
    soporte : list[str]
        Lista de nodos del soporte del distrito.

    Returns
    -------
    networkx.Graph
        Subgrafo inducido.
    """
    return G_global.subgraph(soporte).copy()


def construir_grafo_auxiliar_node_split(subgrafo, y_v, centro, objetivo, inf_cap=1e9):
    """
    Construye el grafo auxiliar dirigido para resolver un minimum node cut
    entre 'centro' y 'objetivo' usando node splitting.

    Para cada nodo j:
        j_in -> j_out con capacidad:
            - INF si j es centro u objetivo
            - y_v[j] en otro caso

    Para cada arista no dirigida {a, b}:
        a_out -> b_in con capacidad INF
        b_out -> a_in con capacidad INF

    Parameters
    ----------
    subgrafo : networkx.Graph
        Subgrafo del distrito (soporte de Y[v, i] > eps).
    y_v : dict[str, float]
        Diccionario con valores fraccionales Y[v, j] para j en el soporte.
    centro : str
        Nodo centro del distrito.
    objetivo : str
        Nodo objetivo i.
    inf_cap : float, optional
        Capacidad "infinita" suficientemente grande.

    Returns
    -------
    networkx.DiGraph
        Grafo auxiliar dirigido.
    """
    G_aux = nx.DiGraph()

    # Crear nodos "in" y "out" y arcos de capacidad de nodo
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

    # Crear arcos de conectividad con capacidad infinita
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
    Encuentra un separador de nodos mínimo entre 'centro' y 'objetivo'
    en el subgrafo dado, usando minimum s-t cut sobre un grafo auxiliar
    con node splitting.

    Parameters
    ----------
    subgrafo : networkx.Graph
        Subgrafo inducido por el soporte del distrito.
    y_v : dict[str, float]
        Valores fraccionales Y[v, j] para los nodos del soporte.
    centro : str
        Nodo centro.
    objetivo : str
        Nodo objetivo i.

    Returns
    -------
    tuple[float, list[str]]
        (valor del min-cut, separador Z)
    """
    # Si centro y objetivo no están en el subgrafo, no hay nada que hacer
    if centro not in subgrafo.nodes() or objetivo not in subgrafo.nodes():
        return math.inf, []

    # Si centro = objetivo, no corresponde separar
    if centro == objetivo:
        return math.inf, []

    # Si ya están desconectados en el soporte, el separador puede considerarse de capacidad 0
    if not nx.has_path(subgrafo, centro, objetivo):
        return 0.0, []

    # Capacidad "infinita" suficientemente grande
    # Se toma algo mayor que la suma total de Y[v,j] del soporte
    inf_cap = max(1.0, sum(y_v.values()) + 1.0)

    # Construir grafo auxiliar
    G_aux = construir_grafo_auxiliar_node_split(
        subgrafo=subgrafo,
        y_v=y_v,
        centro=centro,
        objetivo=objetivo,
        inf_cap=inf_cap
    )

    source = f"{centro}__out"
    sink = f"{objetivo}__in"

    # Resolver minimum cut
    cut_value, (lado_source, lado_sink) = nx.minimum_cut(
        G_aux, source, sink, capacity="capacity"
    )

    # Recuperar el separador Z:
    # si j_in queda del lado source y j_out del lado sink, el arco j_in -> j_out fue cortado
    separador = []
    for j in subgrafo.nodes():
        if j == centro or j == objetivo:
            continue

        j_in = f"{j}__in"
        j_out = f"{j}__out"

        if (j_in in lado_source) and (j_out in lado_sink):
            separador.append(j)

    # Filtrado numérico menor
    suma_separador = sum(y_v.get(j, 0.0) for j in separador)
    if abs(suma_separador - cut_value) <= 1e-6:
        cut_value = suma_separador

    return cut_value, separador


# ============================================================
# FUNCION PRINCIPAL
# ============================================================

def ejecutar_instancia(hex, alfa, n, cpu_limit=432000, eps_frac=0.01, eps_int=0.9):
    """
    Ejecuta una instancia del problema de districting con:
    - Restricciones lazy de Drexl-Haase en soluciones enteras (MIPSOL).
    - User cuts de Drexl-Haase y separator constraints en soluciones fraccionales (MIPNODE).

    Parameters
    ----------
    hex : int
        Cantidad de hexágonos.
    alfa : float
        Parámetro de balance.
    n : int
        Máximo número de distritos.
    cpu_limit : int, optional
        Límite de tiempo CPU en segundos.
    eps_frac : float, optional
        Tolerancia para considerar una variable positiva en soluciones fraccionales.
    eps_int : float, optional
        Tolerancia para considerar una variable igual a 1 en soluciones enteras.
    """
    print("\n===========================================================")
    print(f"Se comienza ejecución para {hex} hexagonos con alfa = {alfa} y n = {n}")
    print("===========================================================")

    # --------------------------------------------------------
    # Definicion de rutas
    # --------------------------------------------------------
    escritorio = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

    ruta_hexagonos = os.path.join(escritorio, f"grafo_hexagons_{hex}hex.xlsx")
    ruta_distancias = os.path.join(escritorio, f"distancias_{hex}hex.xlsx")

    # --------------------------------------------------------
    # Carga de archivos de entrada
    # --------------------------------------------------------
    data_grafo = pd.ExcelFile(ruta_hexagonos)
    matriz_distancias = pd.read_excel(ruta_distancias, header=0, index_col=0)
    df_arcos_hexagonos = pd.read_excel(ruta_hexagonos, sheet_name="arcos_hexagonos")

    # --------------------------------------------------------
    # Carga de conjuntos
    # --------------------------------------------------------
    V = data_grafo.parse("hexagons")["Hexagon"].astype(str).str.strip().tolist()
    L = data_grafo.parse("Conjunto L")["Bus line"].astype(str).str.strip().tolist()
    W = V.copy()

    # --------------------------------------------------------
    # Carga de adyacencias N(v)
    # --------------------------------------------------------
    df_hexagons = data_grafo.parse("hexagons").copy()
    df_hexagons["Hexagon"] = df_hexagons["Hexagon"].astype(str).str.strip()

    N = df_hexagons.set_index("Hexagon")["Conjunto Nv"].apply(parsear_lista_excel).to_dict()

    # --------------------------------------------------------
    # Carga de conjuntos Epsilon(l)
    # --------------------------------------------------------
    df_lineas = data_grafo.parse("Conjunto L").copy()
    df_lineas["Bus line"] = df_lineas["Bus line"].astype(str).str.strip()

    Ɛ = df_lineas.set_index("Bus line")["Conjunto Ɛ_{l}"].apply(parsear_lista_excel).to_dict()

    # --------------------------------------------------------
    # Parametros h y M
    # --------------------------------------------------------
    h = df_lineas.set_index("Bus line")["Frecuencia"].to_dict()
    M = sum(h[l] for l in L)

    # --------------------------------------------------------
    # Parametro de distancias d
    # --------------------------------------------------------
    d = {}
    for v, row in matriz_distancias.iterrows():
        v = str(v).strip()
        for v2, value in row.items():
            v2 = str(v2).strip()
            d[(v, v2)] = int(value)

    # --------------------------------------------------------
    # Construccion del grafo global de adyacencia
    # --------------------------------------------------------
    G_global = construir_grafo_adyacencia(V, df_arcos_hexagonos)

    # --------------------------------------------------------
    # Creacion del modelo
    # --------------------------------------------------------
    model = gp.Model("Districting")

    # --------------------------------------------------------
    # Variables de decision
    # --------------------------------------------------------
    X = model.addVars(W, vtype=GRB.BINARY, name="X")
    Y = model.addVars(W, V, vtype=GRB.BINARY, name="Y")
    H = model.addVars(W, L, vtype=GRB.BINARY, name="H")
    Q = model.addVars(W, lb=0, name="Q")
    Qover = model.addVar(lb=0, name="Qover")
    Qunder = model.addVar(lb=0, name="Qunder")

    # --------------------------------------------------------
    # Funcion objetivo
    # --------------------------------------------------------
    model.setObjective(
        gp.quicksum(d[v, v2] * Y[v, v2] for v in W for v2 in V),
        GRB.MINIMIZE
    )

    # ========================================================
    # RESTRICCIONES DEL MODELO
    # ========================================================

    # Restriccion 2: cada hexagono se asigna a exactamente un distrito
    for v2 in V:
        model.addConstr(
            gp.quicksum(Y[v, v2] for v in W) == 1,
            name=f"R2_{v2}"
        )

    # Restriccion 3: solo puede asignarse a un centro activo
    for v in W:
        for v2 in V:
            model.addConstr(
                Y[v, v2] <= X[v],
                name=f"R3_{v}_{v2}"
            )

    # Restriccion 5
    for v in W:
        for l in L:
            for v2 in Ɛ[l]:
                model.addConstr(
                    H[v, l] >= Y[v, v2],
                    name=f"R5_{v}_{l}_{v2}"
                )

    # Restriccion 6
    for v in W:
        for l in L:
            model.addConstr(
                H[v, l] <= gp.quicksum(Y[v, v2] for v2 in Ɛ[l]),
                name=f"R6_{v}_{l}"
            )

    # Restriccion 7
    for v in W:
        model.addConstr(
            Q[v] == gp.quicksum(h[l] * H[v, l] for l in L),
            name=f"R7_{v}"
        )

    # Restriccion 8
    for v in W:
        model.addConstr(
            Qover >= Q[v],
            name=f"R8_{v}"
        )

    # Restriccion 9
    for v in W:
        model.addConstr(
            Q[v] >= Qunder - (1 - X[v]) * M,
            name=f"R9_{v}"
        )

    # Restriccion 10
    model.addConstr(
        Qover <= Qunder * (1 + alfa),
        name="R10"
    )

    # Restriccion 11
    model.addConstr(
        gp.quicksum(X[v] for v in W) <= n,
        name="R11"
    )

    # Restriccion para evitar |S| = 1
    for v in W:
        for v2 in V:
            model.addConstr(
                Y[v, v2] <= gp.quicksum(Y[v, u] for u in N.get(v2, [])),
                name=f"R14_{v}_{v2}"
            )

    # ========================================================
    # CALLBACK DE SEPARACION
    # ========================================================

    def contiguity_and_separator_callback(model, where):
        """
        Callback híbrido:
        - MIPNODE (solución fraccional):
            * separa cortes de Drexl-Haase con cbCut
            * separa separator constraints con cbCut
        - MIPSOL (solución entera):
            * separa Drexl-Haase con cbLazy
        """
        # ----------------------------------------------------
        # Termino por tiempo CPU
        # ----------------------------------------------------
        if time.process_time() - cpu_start > cpu_limit:
            model.terminate()
            return

        # ====================================================
        # CASO 1: SOLUCION FRACCIONAL DEL NODO (MIPNODE)
        # ====================================================
        if where == GRB.Callback.MIPNODE:
            status = model.cbGet(GRB.Callback.MIPNODE_STATUS)

            if status == GRB.OPTIMAL:
                print("\n[DEBUG] --- Nodo MIPNODE (solución fraccional) ---")

            # Solo se puede usar cbGetNodeRel si el estado del nodo es OPTIMAL
            if status != GRB.OPTIMAL:
                return

            # Recuperar relajacion LP actual
            Xrel = model.cbGetNodeRel(X)
            Yrel = model.cbGetNodeRel(Y)

            # ------------------------------------------------
            # Recorrer centros con X[v] > 0
            # ------------------------------------------------
            for v in W:
                if Xrel[v] <= eps_frac:
                    continue

                print(f"[MIPNODE] Centro candidato v = {v}, X[v] = {Xrel[v]:.4f}")

                # Soporte fraccional del distrito de v: nodos con Y[v, i] > 0
                soporte_v = [i for i in V if Yrel[v, i] > eps_frac]

                print(f"[MIPNODE] Soporte de v={v}: tamaño = {len(soporte_v)}")

                # Si el soporte es vacio o tiene un solo nodo, no hay nada relevante
                if len(soporte_v) <= 1:
                    continue

                # Construir subgrafo inducido del soporte
                G_sub = construir_subgrafo_desde_soporte(G_global, soporte_v)

                # ------------------------------------------------
                # 1) Separacion heuristica de Drexl-Haase en MIPNODE
                # ------------------------------------------------
                if G_sub.number_of_nodes() > 0 and not nx.is_connected(G_sub):
                    print(f"[MIPNODE][DH] Subgrafo desconectado para v={v}")
                    componentes_disconexas = obtener_componentes_desconectadas(G_sub)
                    print(f"[MIPNODE][DH] Componentes desconectadas: {componentes_disconexas}")

                    for componente in componentes_disconexas:
                        componente_tuple = tuple(sorted(componente))

                        # Evitar duplicar el mismo subconjunto S como user cut
                        if componente_tuple in model._dh_cuts_added:
                            continue

                        print(f"[MIPNODE][DH] Agregando corte para S={componente}, |S|={len(componente)}")

                        frontera = obtener_frontera_componente(componente, N)
                        rhs = 1 - len(componente)

                        # Agregar el corte para todo centro potencial
                        for vv in W:
                            expr_frontera = gp.quicksum(Y[vv, j] for j in frontera)
                            expr_comp = gp.quicksum(Y[vv, j] for j in componente)

                            # User cut (válido para soluciones fraccionales)
                            model.cbCut(expr_frontera - expr_comp >= rhs)

                        model._dh_cuts_added.add(componente_tuple)
                        model._n_dh_cuts += 1

                # ------------------------------------------------
                # 2) Separacion de separator constraints en MIPNODE
                # ------------------------------------------------
                # Diccionario local de valores Y[v, j] sobre el soporte
                y_v = {j: float(Yrel[v, j]) for j in soporte_v}

                for i in soporte_v:
                    # No tiene sentido separar el centro contra sí mismo
                    if i == v:
                        continue

                    y_vi = float(Yrel[v, i])

                    # Si Y[v, i] es numericamente cero, omitir
                    if y_vi <= eps_frac:
                        continue

                    #print(f"[MIPNODE][SEP] Evaluando par (v={v}, i={i}), Y[v,i]={y_vi:.4f}")

                    # Resolver min-cut de nodos entre v e i
                    cut_value, separador = encontrar_separador_minimo(
                        subgrafo=G_sub,
                        y_v=y_v,
                        centro=v,
                        objetivo=i,
                    )

                    #print(f"[MIPNODE][SEP] Min-cut entre v={v} e i={i}: valor={cut_value:.4f}, Z={separador}")

                    # Si no se obtiene un separador util, continuar
                    if separador is None:
                        continue

                    suma_separador = sum(y_v.get(j, 0.0) for j in separador)

                    #print(f"[MIPNODE][SEP] Comparación: Y[v,i]={y_vi:.4f} vs suma_Z={suma_separador:.4f}")

                    # Verificar violacion: Y[v, i] > sum_{j in Z} Y[v, j]
                    if y_vi > suma_separador + 1e-6:
                        key_sep = (v, i, tuple(sorted(separador)))

                        # Evitar duplicados
                        if key_sep in model._separator_cuts_added:
                            continue

                        print(f"[MIPNODE][SEP] >>> Corte agregado: Y[{v},{i}] <= sum(Y[{v},j] para j en Z)")

                        # Agregar separator constraint como user cut
                        expr_sep = gp.quicksum(Y[v, j] for j in separador)

                        # Si separador = [] => Y[v, i] <= 0
                        model.cbCut(Y[v, i] <= expr_sep)

                        model._separator_cuts_added.add(key_sep)
                        model._n_separator_cuts += 1

        # ====================================================
        # CASO 2: SOLUCION ENTERA INCUMBENTE (MIPSOL)
        # ====================================================
        elif where == GRB.Callback.MIPSOL:
            print("\n[DEBUG] === Nueva solución incumbente encontrada ===")

            # Recuperar solucion incumbente
            Xsol = model.cbGetSolution(X)
            Ysol = model.cbGetSolution(Y)

            # Recuperar centros del incumbente
            centros = [v for v in W if Xsol[v] > eps_int]
            print(f"[MIPSOL] Centros activos: {centros}")

            # Revisar cada distrito del incumbente
            for centro in centros:
                distrito = [i for i in V if Ysol[centro, i] > eps_int]
                print(f"[MIPSOL] Distrito del centro {centro}: tamaño = {len(distrito)}")

                # Si el distrito es vacio o tiene un solo nodo, no hay nada que revisar
                if len(distrito) <= 1:
                    continue

                # Construir subgrafo inducido
                G_sub = construir_subgrafo_desde_soporte(G_global, distrito)

                # Si es conexo, no se requieren lazy constraints
                if G_sub.number_of_nodes() == 0 or nx.is_connected(G_sub):
                    continue

                print(f"[MIPSOL][DH] Distrito desconectado para centro {centro}")

                # Obtener componentes desconectadas (excepto la mayor)
                componentes_disconexas = obtener_componentes_desconectadas(G_sub)
                print(f"[MIPSOL][DH] Componentes desconectadas: {componentes_disconexas}")

                # Contador por incumbente
                n_cortes_it = 0

                # Agregar restricciones lazy de Drexl-Haase
                for componente in componentes_disconexas:
                    componente_tuple = tuple(sorted(componente))

                    # Evitar duplicar la misma lazy constraint
                    if componente_tuple in model._dh_lazy_added:
                        continue

                    frontera = obtener_frontera_componente(componente, N)
                    rhs = 1 - len(componente)

                    n_cortes_it += 1
                    print(f"[MIPSOL][DH] Corte agregado para S={componente}")

                    for v in W:
                        expr_frontera = gp.quicksum(Y[v, j] for j in frontera)
                        expr_comp = gp.quicksum(Y[v, j] for j in componente)

                        model.cbLazy(expr_frontera - expr_comp >= rhs)

                    model._dh_lazy_added.add(componente_tuple)
                    model._n_dh_lazy += 1

                print(f"[MIPSOL][DH] Total cortes agregados para este incumbente: {n_cortes_it}")

    # ========================================================
    # ESTRUCTURAS PARA EVITAR DUPLICADOS
    # ========================================================
    model._dh_cuts_added = set()          # Drexl-Haase agregadas como user cuts (MIPNODE)
    model._separator_cuts_added = set()   # Separator constraints agregadas como user cuts (MIPNODE)
    model._dh_lazy_added = set()          # Drexl-Haase agregadas como lazy constraints (MIPSOL)

    model._n_dh_cuts = 0
    model._n_separator_cuts = 0
    model._n_dh_lazy = 0

    # ========================================================
    # RESOLUCION DEL MODELO
    # ========================================================
    cpu_start = time.process_time()

    # Necesario para lazy constraints
    model.Params.LazyConstraints = 1

    # Recomendado al agregar user cuts propios, para evitar que presolve
    # "aplane" variables y el corte pueda ser ignorado en el modelo presuelto
    model.Params.PreCrush = 1

    model.Params.LogToConsole = 1
    model.Params.Method = 1

    model.optimize(contiguity_and_separator_callback)

    # ========================================================
    # METRICAS DE EJECUCION
    # ========================================================
    duracion_reloj = model.getAttr(GRB.Attr.Runtime)
    duracion_cpu = time.process_time() - cpu_start

    # ========================================================
    # REPORTE EN CONSOLA
    # ========================================================
    print("\n===========================================================")
    print("RESUMEN DE CORTES AGREGADOS")
    print("===========================================================")
    print(f"Drexl-Haase como user cuts (MIPNODE): {model._n_dh_cuts}")
    print(f"Separator constraints como user cuts (MIPNODE): {model._n_separator_cuts}")
    print(f"Drexl-Haase como lazy constraints (MIPSOL): {model._n_dh_lazy}")
    print("===========================================================")

    print(f"\nTiempo reloj: {duracion_reloj:.4f} segundos -> {duracion_reloj / 60:.4f} minutos.")
    print(f"Tiempo CPU: {duracion_cpu:.4f} segundos -> {duracion_cpu / 60:.4f} minutos.")

    # ========================================================
    # GUARDADO DE RESULTADOS
    # ========================================================
    ruta_excel_salida = os.path.join(
        escritorio,
        f"Separador_Resultados_{hex}hex_cpu{cpu_limit}_alfa{alfa}_n{n}.xlsx"
    )

    # Verificar si se encuentra solucion
    if model.SolCount > 0:
        # Rescatar variable X
        X_sol = pd.DataFrame([
            {"Distrito": v, "X": X[v].X}
            for v in W
        ])

        # Identificar centros de distrito utilizados
        centros_distrito = X_sol[X_sol["X"] > eps_int].copy()
        hexagonos_centros = centros_distrito["Distrito"].tolist()

        # Rescatar variable Y
        asignacion_hexagonos_excel = pd.DataFrame([
            {"Distrito": v, "Hexagon": v2}
            for v in W
            for v2 in V
            if Y[v, v2].X > eps_int
        ])

        # Rescatar variable Q
        Q_excel = pd.DataFrame([
            {"Distrito": v, "Q": Q[v].X}
            for v in hexagonos_centros
        ])

        # Resumen de cortes
        resumen_cortes = pd.DataFrame([
            {"Tipo de corte": "Drexl-Haase user cuts (MIPNODE)", "Cantidad": model._n_dh_cuts},
            {"Tipo de corte": "Separator constraints user cuts (MIPNODE)", "Cantidad": model._n_separator_cuts},
            {"Tipo de corte": "Drexl-Haase lazy constraints (MIPSOL)", "Cantidad": model._n_dh_lazy},
            {"Tipo de corte": "Total", "Cantidad": model._n_dh_cuts + model._n_separator_cuts + model._n_dh_lazy}
        ])

        # Guardar resultados
        with pd.ExcelWriter(ruta_excel_salida) as writer:
            asignacion_hexagonos_excel.to_excel(writer, sheet_name="Asignacion", index=False)
            Q_excel.to_excel(writer, sheet_name="Buses por distrito", index=False)
            resumen_cortes.to_excel(writer, sheet_name="Resumen cortes", index=False)

    else:
        print(f"El modelo terminó sin soluciones factibles. Status={model.Status}")


# ============================================================
# BUCLE PRINCIPAL
# ============================================================
alfas = [1]
ns = [5]
hexs = [250]

for hex in hexs:
    for n in ns:
        for alfa in alfas:
            ejecutar_instancia(hex, alfa, n)