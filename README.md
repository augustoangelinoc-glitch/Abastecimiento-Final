# Abastecimiento Profesional

Sistema Streamlit orientado a una pregunta principal: **¿cuánto abastecer de cada material?**

## Archivos de entrada
1. Stock actual
2. Salidas históricas
3. Órdenes de compra
4. Ingresos de órdenes de compra

## Reglas principales
- El consumo se conserva por año-mes, incluyendo meses con cero consumo.
- Se muestran consumo total, cantidad de salidas, meses con/sin consumo, última salida y días sin movimiento.
- El Lead Time se calcula históricamente desde fecha de OC hasta primera recepción.
- OC cerrada + material pendiente **no** cuenta como abastecimiento futuro.
- Solo las OC vigentes con saldo positivo reducen la cantidad a abastecer.
- Los costos se mantienen con dos fuentes; si ambas son positivas se usa el mayor.
- Los cálculos internos conservan precisión y la presentación/exportación se redondea a 2 decimales.
- Los materiales sin costo valorizable siguen participando en demanda y abastecimiento, pero no en valor económico.

## Importante
El periodo de revisión adicional es un parámetro configurable; no se asume una política fija de tres meses.
