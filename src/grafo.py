"""
Módulo para cargar y procesar información de la red de buses de
Santiago desde el archivo Excel. Se generan listas y diccionarios 
de nodos, conexiones y líneas de buses que permiten trabajar con 
el grafo de manera estructurada.
"""
# Este es un comentario de testeo para git

# Importar bibliotecas necesarias
import os
import pandas as pd

# ----------------------------------------------------------------------
# Definición de rutas y carga de datos
# ----------------------------------------------------------------------

# Definir la ruta del archivo Excel que contiene la información del grafo
ruta_grafo = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data',
    'Data Grafo.xlsx'
)

# Cargar las hojas del archivo Excel en dataframes
nodos_df = pd.read_excel(ruta_grafo, sheet_name="Nodos", engine='openpyxl')
arcos_df = pd.read_excel(ruta_grafo, sheet_name="Arcos", engine='openpyxl')
lineas_df = pd.read_excel(ruta_grafo, sheet_name="Lineas", engine='openpyxl')

# ----------------------------------------------------------------------
# Procesamiento de nodos
# ----------------------------------------------------------------------

# Lista con todos los "bus stops" (paraderos) del grafo
bus_stops = nodos_df["Bus stop"].tolist()

# Diccionario que asocia cada "bus stop" con sus coordenadas (latitud, longitud)
coordenadas_bus_stops = {
    row["Bus stop"]: (row["Latitud"], row["Longitud"])
    for _, row in nodos_df.iterrows()
}

# ----------------------------------------------------------------------
# Procesamiento de conexiones
# ----------------------------------------------------------------------

# Lista con todas las conexiones del grafo
connections = arcos_df["Connection"].tolist()

# Diccionario que asocia cada conexión con los dos "bus stops" que une
bus_stops_connections = {
    row["Connection"]: (row["Bus stop 1"], row["Bus stop 2"])
    for _, row in arcos_df.iterrows()
}

# Diccionario que asocia cada conexión con el conjunto de líneas de buses que la recorren
bus_lines_connections = {
    row["Connection"]: set(map(str.strip, row["Bus lines"].split(",")))
    if pd.notna(row["Bus lines"]) else set()
    for _, row in arcos_df.iterrows()
}

# ----------------------------------------------------------------------
# Sección opcional (comentada) - Información adicional
# ----------------------------------------------------------------------
"""
# Diccionario que asocia cada "bus stop" con su comuna
comuna_bus_stops = {
    row["Bus stop"]: row["Comuna"]
    for _, row in nodos_df.iterrows()
}

# Diccionario que asocia cada "bus stop" con el conjunto de líneas de buses que pasan por él
bus_lines_bus_stops = {
    row["Bus stop"]: set(map(str.strip, row["Bus lines"].split(",")))
    if pd.notna(row["Bus lines"]) else set()
    for _, row in nodos_df.iterrows()
}

# Diccionario que asocia cada "bus stop" con las conexiones adyacentes
connection_adjacentes_bus_stops = {
    row["Bus stop"]: set(map(str.strip, row["Connection adyacentes"].split(",")))
    if pd.notna(row["Connection adyacentes"]) else set()
    for _, row in nodos_df.iterrows()
}

# Diccionario que asocia cada "bus stop" con los "bus stops" adyacentes
bus_stop_adjacentes_bus_stops = {
    row["Bus stop"]: set(map(str.strip, row["Bus stop adyacentes"].split(",")))
    if pd.notna(row["Bus stop adyacentes"]) else set()
    for _, row in nodos_df.iterrows()
}

# Diccionario que asocia cada conexión con el tiempo promedio de recorrido
tiempo_connections = {
    row["Connection"]: round(row["Tiempo Promedio"])
    for _, row in arcos_df.iterrows()
}

# Diccionario que asocia cada conexión con sus conexiones adyacentes
connection_adjacentes_connections = {
    row["Connection"]: set(map(str.strip, row["Connection adyacentes"].split(",")))
    if pd.notna(row["Connection adyacentes"]) else set()
    for _, row in arcos_df.iterrows()
}

# Lista con todas las líneas de buses
bus_lines = lineas_df["Bus line"].tolist()

# Diccionario que asocia cada línea de bus con su frecuencia
frecuencia_bus_lines = {
    row["Bus line"]: row["Frecuencia"]
    for _, row in lineas_df.iterrows()
}

# Diccionario que asocia cada línea de bus con la secuencia de conexiones que recorre
connection_bus_lines = {
    row["Bus line"]: list(map(str.strip, row["Conjunto Ɛ_{l}"].split(",")))
    if pd.notna(row["Conjunto Ɛ_{l}"]) else set()
    for _, row in lineas_df.iterrows()
}
"""