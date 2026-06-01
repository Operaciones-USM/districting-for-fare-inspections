# Importar bibliotecas necesarias
import os
import pandas as pd
from amplpy import AMPL, add_to_path
import time

# Iniciar conteo de tiempo para medir duración del proceso
inicio = time.time()

# Definir rutas de archivos
escritorio = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
ruta_data = os.path.join(escritorio, 'Data Grafo Distritos Quilicura.xlsx')
ruta_matriz_B = os.path.join(escritorio, 'Matriz B(e,v) Quilicura.xlsx')
ruta_ampl = os.path.join(os.path.expanduser('~'), 'Desktop', "Operaciones", "AMPL")

# Cargar archivos de entrada en pandas
data_grafo = pd.ExcelFile(ruta_data)
matriz_B = pd.read_excel(ruta_matriz_B, header=0, index_col=0)

# Cargar listas de conjuntos desde hojas específicas del archivo de datos
V = data_grafo.parse("Conjuntos V y A(v)")['Bus stop'].tolist() 
L = data_grafo.parse("Conjuntos L y Ɛ_{l}")['Bus line'].tolist()
E = data_grafo.parse("Conjuntos E y B_{e}")['Connection'].tolist()

# Crear diccionario A(v): arcos adyacentes a cada parada
A_v = data_grafo.parse("Conjuntos V y A(v)").set_index('Bus stop')['Conjunto A(v)'].apply(
    lambda x: [int(i) for i in x.split(',')] if ',' in str(x) else [int(x)]
).to_dict()

# Crear diccionario Ɛ(l): arcos recorridos por cada línea
Ɛ_l = data_grafo.parse("Conjuntos L y Ɛ_{l}").set_index('Bus line')['Conjunto Ɛ_{l}'].apply(
    lambda x: [int(i) for i in x.split(',')] if ',' in str(x) else [int(x)]
).to_dict()

# Crear diccionario B(e,v): arcos adyacentes al arco e y más cercanos a la parada v
B_ev = {}
for v, row in matriz_B.iterrows():
    for e, value in row.items():
        B_ev[(int(e), v)] = [int(i) for i in value.split(',')] if pd.notna(value) and ',' in str(value) else ([int(value)] if pd.notna(value) else [])

# Cargar parámetros h (frecuencia de buses) y t (tiempo promedio)
h_l = data_grafo.parse("Conjuntos L y Ɛ_{l}").set_index('Bus line')['Frecuencia'].to_dict()
t_e = data_grafo.parse("Conjuntos E y B_{e}").set_index('Connection')['Tiempo Promedio'].to_dict()

# Definir parámetros generales del modelo
T = 14400         # Límite de tiempo por distrito (segundos)
alfa = 0.1          # Límite de desequilibrio entre distritos

# Agregar ruta a AMPL
add_to_path(ruta_ampl)

# Crear instancia de AMPL
ampl = AMPL()

# Definir el modelo AMPL
modelo = """
# Conjuntos
set V;                              # Conjunto de paradas de buses
set L;                              # Conjunto de líneas de buses
set E;                              # Conjunto de arcos
set A{v in V} within E;             # Conjunto A(v): arcos adyacentes a la parada v
set B{e in E, v in V} within E;     # Conjunto B(e,v): arcos adyacentes al arco e y mas cercanos a la parada v
set Ɛ{l in L} within E;             # Conjunto Ɛ(l): arcos seguidos por la linea l

# Parámetros
param h{l in L};            # Cantidad de buses de la línea l
param t{e in E};            # Tiempo del arco e
param T;                    # Tiempo máximo de los distritos   
param alfa;                 # Máximo porcentaje de diferencia de número de buses entre distritos

# Variables
var X{v in V} binary;             # 1 si v es utilizada como representante de distrito, 0 si no
var Y{e in E, v in V} binary;     # 1 si el arco e es parte del distrito v, 0 si no
var H{v in V, l in L} binary;     # 1 si línea l pasa por el distrito de representante v, 0 si no
var q{v in V, l in L} >= 0;       # Número de buses de la linea l en el distrito con representante v
var D{v in V} >= 0;               # Cantidad de buses en el distrito con representante v
var UB >= 0;                      # Número máximo de buses en un distrito
var LB >= 0;                      # Número mínimo de buses en un distrito
var S{v in V} >= 0;               # Tamaño del distrito con representante v

# Función Objetivo
minimize Objetivo:
    sum {v in V} X[v];

# Restricciones

# R1: Todo arco debe pertenecer a un unico distrito
s.t. R1 {e in E}:
    sum {v in V} Y[e, v] = 1;

# R2: Un arco no puede asignarse a un distrito si este no es utilizado
s.t. R2 {e in E, v in V}:
    Y[e, v] <= X[v];

# R3: Al menos un arco adyacente a un representante de distrito utilizado debe ser asignado a dicho distrito
s.t. R3 {v in V}:
    sum {e in A[v]} Y[e, v] >= X[v];

# R4: Un arco 𝑒 no puede ser asignado a un distrito, si todos sus arcos adyacentes y mas cercanos a j no son asignados a ese distrito.
s.t. R4 {v in V, e in E: e not in A[v]}:
    sum {k in B[e, v]} Y[k, v] >= Y[e, v];

# R5 y R6: Restricciones para determinar 𝐻v𝑙, es decir, para determinar si la línea 𝑙 es inspeccionada en un distrito v. Recordar que toda línea que pase por un arco que pertenece al distrito utilizado es inspeccionada en dicho distrito. 
s.t. R5 {v in V, l in L, e in Ɛ[l]}:
    H[v, l] >= Y[e, v];

s.t. R6 {v in V, l in L}:
    H[v, l] <= sum {e in Ɛ[l]} Y[e, v];

# R7: Cantidad de buses de la linea l en el distrito v
s.t. R7 {v in V, l in L}:
    q[v, l] = h[l] * H[v, l];
    
# R8: Cantidad de buses en el distrito v
s.t. R8 {v in V}:
    D[v] = sum {l in L} q[v, l];

# R9: Máxima cantidad de buses en un distrito
s.t. R9 {v in V}:
    UB >= D[v];

# R10: Mínima cantidad de buses en un distrito
s.t. R10 {v in V}:
    LB * X[v] <= D[v];

# R11: Balance de cantidad de buses en un distrito
s.t. R11:
    UB / LB <= 1 + alfa;

# R12: Tamaño de distritos
s.t. R12 {v in V}:
    S[v] = sum {e in E} (Y[e, v] * t[e]);
    
# R13: Limite de tamaño de distritos
s.t. R13 {v in V}:
    S[v] <= T * X[v];
"""

ampl.eval(modelo)

# Asignar conjuntos y parámetros al modelo AMPL
try:
    ampl.getSet("V").setValues(V)
    ampl.getSet("L").setValues(L)
    ampl.getSet("E").setValues(E)
    ampl.getSet("A").setValues(A_v)
    ampl.getSet("B").setValues(B_ev)
    ampl.getSet("Ɛ").setValues(Ɛ_l)
    ampl.getParameter("h").setValues(h_l)
    ampl.getParameter("t").setValues(t_e)
    ampl.getParameter("T").set(T)
    ampl.getParameter("alfa").set(alfa)
except Exception as e:
    raise ValueError("Error al asignar datos en AMPL.") from e

# Resolver el modelo usando Gurobi
ampl.solve(solver="gurobi")

# Obtener variables del modelo y convertirlas a DataFrames de pandas
X = ampl.getVariable("X").getValues().toPandas()
Y = ampl.getVariable("Y").getValues().toPandas()
H = ampl.getVariable("H").getValues().toPandas()
q = ampl.getVariable("q").getValues().toPandas()
D = ampl.getVariable("D").getValues().toPandas()
S = ampl.getVariable("S").getValues().toPandas()
UB = ampl.getVariable("UB").value()
LB = ampl.getVariable("LB").value()

# Identificar paradas utilizadas como representantes de distrito
representantes_distrito = X[X['X.val'] == 1].copy()
paradas_representantes = representantes_distrito.index.get_level_values(0)

# Crear hoja de asignación de arcos
asignacion_arcos_excel = Y[Y['Y.val'] == 1].copy().reset_index()
asignacion_arcos_excel.columns = ['Connection', 'Distrito', 'Y.val']
asignacion_arcos_excel = asignacion_arcos_excel.drop('Y.val', axis=1)

# Crear hoja de cantidad de buses por línea y distrito (solo representantes)
q_excel = q[q.index.get_level_values(0).isin(paradas_representantes)].copy().reset_index()
q_excel.columns = ['Distrito', 'Bus line', 'q']

# Crear hoja de cantidad total de buses por distrito (solo representantes)
D_excel = D[D.index.get_level_values(0).isin(paradas_representantes)].copy().reset_index()
D_excel.columns = ['Distrito', 'D']

# Crear hoja con el tamaño de cada distrito (solo representantes)
S_excel = S[S.index.get_level_values(0).isin(paradas_representantes)].copy().reset_index()
S_excel.columns = ['Distrito', 'S']

# Guardar resultados en un archivo Excel
ruta_excel_salida = os.path.join(escritorio, f'Distritos_Quilicura_modelo1_T{T}_alfa{alfa}.xlsx')
with pd.ExcelWriter(ruta_excel_salida) as writer:
    asignacion_arcos_excel.to_excel(writer, sheet_name='Asignacion', index=False)
    q_excel.to_excel(writer, sheet_name='Buses por linea', index=False)
    D_excel.to_excel(writer, sheet_name='Buses por distrito', index=False)
    S_excel.to_excel(writer, sheet_name='Tamaño distritos', index=False)

# Imprimir tiempo de ejecución
fin = time.time()
duracion = fin - inicio
print(f"Tiempo de ejecución: {duracion} segundos -> {duracion / 60} minutos")