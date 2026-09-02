# Abastecimiento Final V8
Separación entre interfaz (`app.py`) y lógica (`logyc.py`).

Campos fijados a los archivos reales:
- Stock Actual: A Código, B Descripción, C U.Medida, D Sistema/Stock, N Familia, T C. Kardex.
- Salidas: AQ Material, AT Descripción.2, H F.Almac., AX Unidades, CB Total S/.
- OC: G F.Docum., H P. Emis, I Número, AO Material.
- Ingresos: H F.Almac., AP Material, BI P.OC, BJ Número OC.

Lead Time: cruce exacto `P. Emis + Número + Material` contra `P.OC + Número OC + Material`, preservando ceros iniciales.
