# Importar bibliotecas necesarias
import os
import pandas as pd
import networkx as nx
import time
import random
from itertools import product

inicio = time.time()

# ============================
# Parámetros de configuración
# ============================

INICIO_DISTRIBUCION_TIEMPO_TRANSFERENCIA = 240  # Tiempo mínimo de transferencia entre líneas (segundos)
TERMINO_DISTRIBUCION_TIEMPO_TRANSFERENCIA = 420  # Tiempo máximo de transferencia entre líneas (segundos)
INICIO_DISTRIBUCION_TIEMPO_DETENCION = 10  # Tiempo mínimo de detención en una parada (segundos)
TERMINO_DISTRIBUCION_TIEMPO_DETENCION = 30  # Tiempo máximo de detención en una parada (segundos)
K = 5  # Número de caminos más cortos a calcular entre cada par de paradas

# =====================
# Carga de los datos
# =====================

# Ruta al escritorio donde se encuentra el archivo
escritorio = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

# Ruta al archivo Excel con los datos del grafo
ruta_excel = os.path.join(escritorio, 'Data Grafo Distritos.xlsx')

# Lectura de las hojas necesarias
df_paradas = pd.read_excel(ruta_excel, sheet_name='Conjuntos V y A(v)')
df_arcos = pd.read_excel(ruta_excel, sheet_name='Conjuntos E y B_{e}')
paradas = df_paradas['Bus stop'].unique()

# Diccionario para mapear pares de paradas a su "Connection"
arco_a_connection = {
    (str(row['Bus stop 1']), str(row['Bus stop 2'])): row['Connection']
    for _, row in df_arcos.iterrows()
}

# ==============================
# Construcción del grafo base
# ==============================

G = nx.DiGraph()

# Agrega los nodos con su posición geográfica
for _, row in df_paradas.iterrows():
    G.add_node(row['Bus stop'], pos=(row['Longitud'], row['Latitud']))

# Agrega los arcos con el tiempo promedio y las líneas de bus
for _, row in df_arcos.iterrows():
    origen, destino = row['Bus stop 1'], row['Bus stop 2']
    tiempo = row['Tiempo Promedio']
    lineas = [linea.strip() for linea in str(row['Bus lines']).split(',')]
    G.add_edge(origen, destino, tiempo=tiempo, lineas=lineas)

# ===================================
# Expansión del grafo con líneas
# ===================================

G_exp = nx.DiGraph()

# Cada arco se descompone por línea
for u, v, datos in G.edges(data=True):
    for linea in datos['lineas']:
        G_exp.add_edge((u, linea), (v, linea), peso=datos['tiempo'], tipo='viaje')

# Se agregan nodos con detención y transferencias entre líneas en la misma parada
for parada in paradas:
    lineas = set()
    for _, _, datos in G.edges(parada, data=True):
        lineas.update(datos['lineas'])

    # Añade tiempo de detención a cada nodo (parada, línea)
    for linea in lineas:
        TIEMPO_DETENCION = random.randint(INICIO_DISTRIBUCION_TIEMPO_DETENCION, TERMINO_DISTRIBUCION_TIEMPO_DETENCION)
        G_exp.add_node((parada, linea), tiempo_detencion=TIEMPO_DETENCION)

    # Añade transferencias entre líneas en una misma parada
    for l1, l2 in product(lineas, repeat=2):
        if l1 != l2:
            TIEMPO_TRANSFERENCIA = random.randint(INICIO_DISTRIBUCION_TIEMPO_TRANSFERENCIA, TERMINO_DISTRIBUCION_TIEMPO_TRANSFERENCIA)
            G_exp.add_edge((parada, l1), (parada, l2), peso=TIEMPO_TRANSFERENCIA, tipo='transferencia')

# ===============================
# Índices de líneas por parada
# ===============================

# Diccionario de líneas salientes por parada
parada_a_lineas_salida = {
    parada: list({linea for _, _, datos in G.edges(parada, data=True) for linea in datos['lineas']})
    for parada in paradas
}

# Diccionario de líneas entrantes por parada
parada_a_lineas_llegada = {
    parada: list({linea for _, _, datos in G.in_edges(parada, data=True) for linea in datos['lineas']})
    for parada in paradas
}

# =============================
# Función de traducción de camino
# =============================

def traducir_camino(camino):
    """
    Traduce un camino de nodos (parada, línea) a una secuencia de (Connection, línea).
    """
    secuencia = []
    for i in range(len(camino) - 1):
        (u, linea_u) = camino[i]
        (v, linea_v) = camino[i + 1]
        if u != v:
            connection = arco_a_connection.get((str(u), str(v)))
            if connection is not None:
                secuencia.append((connection, linea_u))
    return secuencia

# =====================================
# Cálculo de los caminos más cortos
# =====================================

paradas_lista = list(paradas)

# Define el bloque de paradas a procesar
inicio_idx = 0
fin_idx = 500
paradas_bloque = paradas_lista[inicio_idx:fin_idx]

# Diccionario donde se almacenarán los caminos
caminos_dict_bloque = {origen: {} for origen in paradas_bloque}

for origen in paradas_bloque:
    lineas_origen = parada_a_lineas_salida.get(origen, [])
    caminos_desde_origen = {}

    for linea_o in lineas_origen:
        nodo_origen = (origen, linea_o)
        if nodo_origen not in G_exp:
            continue

        # Ejecuta Dijkstra desde el nodo origen (parada, linea)
        longitudes, rutas = nx.single_source_dijkstra(G_exp, nodo_origen, weight='peso')

        for nodo_destino, tiempo in longitudes.items():
            parada_destino, _ = nodo_destino
            if parada_destino == origen:
                continue

            camino = rutas[nodo_destino]
            
            # Calcula tiempo de detenciones en el camino
            tiempo_detenciones = sum(
                G_exp.nodes[nodo].get('tiempo_detencion', 0) 
                for idx, nodo in enumerate(camino) if idx > 0
            )

            tiempo_total = tiempo + tiempo_detenciones

            if parada_destino not in caminos_desde_origen:
                caminos_desde_origen[parada_destino] = []

            caminos_desde_origen[parada_destino].append((tiempo_total, camino))

    for destino in paradas:
        if origen == destino or destino not in caminos_desde_origen:
            caminos_dict_bloque[origen][destino] = ",".join(["[]"] * K)
            continue

        # Traduce los caminos a secuencias únicas
        todos_caminos = caminos_desde_origen[destino]
        secuencias_dict = {}

        for tiempo, camino in todos_caminos:
            secuencia = traducir_camino(camino)
            secuencia_tuple = tuple(secuencia)
            if secuencia_tuple not in secuencias_dict or tiempo < secuencias_dict[secuencia_tuple]:
                secuencias_dict[secuencia_tuple] = tiempo

        # Ordena por menor tiempo y elige los K mejores
        lista_caminos = sorted(secuencias_dict.items(), key=lambda x: x[1])[:K]
        lista_caminos = [list(secuencia) for secuencia, _ in lista_caminos]

        while len(lista_caminos) < K:
            lista_caminos.append([])

        caminos_str = ",".join([str(camino) for camino in lista_caminos])
        caminos_dict_bloque[origen][destino] = caminos_str

    print(f"Caminos calculados para {origen}.")

# ================================
# Exportación de resultados
# ================================

# Se crea un DataFrame desde el diccionario
matriz_caminos = pd.DataFrame.from_dict(caminos_dict_bloque, orient='index')

# Tiempo de ejecución del algoritmo de caminos
fin1 = time.time()
print(f"Tiempo de ejecución {K}-shortest path: {fin1 - inicio:.2f} segundos -> {(fin1 - inicio)/60 :.2f} minutos.")

# Ruta de salida del archivo Excel
ruta_salida = os.path.join(escritorio, f'Caminos {K}-Shortest Path Dirigido {inicio_idx + 1}-{fin_idx}.xlsx')

# Guardado en Excel con soporte para archivos grandes
with pd.ExcelWriter(ruta_salida, engine='xlsxwriter') as writer:
    writer.book.use_zip64()
    matriz_caminos.to_excel(writer)

# Tiempo total de ejecución
fin2 = time.time()
print(f"Tiempo de ejecución total: {fin2 - inicio:.2f} segundos -> {(fin2 - inicio)/60 :.2f} minutos.")