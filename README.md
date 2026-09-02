# Sistema Profesional de Inventarios y Abastecimiento

Aplicación Streamlit para analizar descargas completas del ERP sin modificar los archivos originales.

## Flujo

ERP → Stock + Salidas + OC + Ingresos → validación → cruce → demanda → ABC/XYZ → Lead Time → cobertura → riesgo → recomendación.

## Archivos de entrada

1. Stock actual
2. Salidas históricas
3. Órdenes de compra
4. Ingresos de OC

Los archivos pueden ser descargas completas del ERP. No es necesario separarlos manualmente.

## Regla de costo

- `C. Kardex > 0`: costo unitario analítico.
- Si C. Kardex no tiene valor y existe Costo Cierre Mes > 0: se utiliza Costo Cierre Mes como respaldo.
- Ambos en cero/sin costo: `SIN COSTO / POSIBLE CONSIGNACION`.
- Los materiales sin costo NO se eliminan: participan en demanda, cobertura y riesgo; se excluyen de valorizaciones económicas.

## Relación de OC

`P. Emis + Número` se normaliza como `oc_id`.

En ingresos se cruza con `P.OC + Número OC`.

Se permiten múltiples ingresos por una misma OC/material para detectar entregas parciales.

## Importante sobre la metodología

Esta primera versión evita parámetros fijos globales de 7 días, 15 días y 20%. El Lead Time se intenta obtener de OC → primera recepción. La protección utiliza la variabilidad observada.

Los umbrales ABC/XYZ y las reglas finales de compra deben validarse con el comportamiento real del histórico antes de convertirlos en política formal.

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub / Streamlit Cloud

Sube al repositorio:
- app.py
- logic.py
- requirements.txt
- README.md

No subas archivos ERP con información sensible al repositorio público.
