ABASTECIMIENTO - versión con mapeo explícito

STOCK:
A Codigo
B Descripción
C U.Medida
D Sistema -> Stock actual
N Familia
T Costo Cierre Mes

SALIDAS:
H -> fecha
AX -> cantidad

OC:
F. Docum. -> fecha documento
Fecha Guia -> recepción
Estado Item -> debe ser COMPRADO
Codigo -> código

El código se conserva como texto para no perder ceros iniciales.
No se utiliza Ingresos para calcular Lead Time.
No se modifica st.session_state después de crear widgets.
