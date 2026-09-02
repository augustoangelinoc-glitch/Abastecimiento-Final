# Abastecimiento Final V4

Aplicación Streamlit para análisis de abastecimiento.

## Fuente de descripción
- Stock actual, columna B / `Descripción`: fuente oficial.
- Salidas, columna AT / `Descripción.2`: no reemplaza la descripción oficial.

## Cálculos
- Consumo histórico mensual completo.
- Días sin movimiento.
- Diagnóstico de consumo eventual/intermitente.
- Picos y tendencias.
- Lead Time: `P. Emis + Número + Material` contra `P.OC + Número OC + Material`.
- Lead Time desde fecha de OC hasta primera recepción.
- Stock de seguridad y punto de pedido como modelo provisional.
- Cantidad a abastecer redondeada siempre hacia arriba a entero.

## Descarga
La aplicación genera un Excel con:
- Abastecimiento
- Consumo mensual
- Lead Time
- Anomalías
- Resumen

No subir archivos ERP al repositorio.
