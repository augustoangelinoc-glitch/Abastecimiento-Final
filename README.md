# ABASTECIMIENTO - versión final

Archivos:
- app.py: interfaz Streamlit.
- logyc.py: lógica de cálculo.

Campos fijados:
- Stock Actual: A código, B descripción, C unidad, D stock, N familia, T costo.
- Salidas: H fecha, AT descripción, Unidades cantidad.
- Lead Time: OC `P. Emis + Número + Material` contra Ingresos `P.OC + Número OC + Material`.
- Se conservan ceros iniciales de identificadores.
- Fechas visibles DD/MM/AAAA sin hora.
- Consumo mensual termina en el último mes real disponible en Salidas.
- No se usan movimientos futuros.

La tabla y el Excel presentan nombres comprensibles en español; los nombres técnicos quedan solo dentro de la lógica.
