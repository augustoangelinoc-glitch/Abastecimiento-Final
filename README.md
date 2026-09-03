
# Abastecimiento — versión final

## Archivos
- app.py
- logic.py
- requirements.txt

## Datos de entrada
1. **Stock Actual**
   - Stock actual: columna D.
   - Costo unitario: columna T.
   - El código/material conserva sus ceros iniciales.

2. **Salidas**
   - Fecha: columna H.
   - Cantidad: columna de cantidad.
   - Los meses del análisis se crean automáticamente desde la fecha mínima hasta la máxima existente en Salidas.
   - No se generan meses futuros sin movimientos.

3. **Órdenes de Compra**
   - Material.
   - F. Docum. = fecha de emisión.
   - Fecha Guía = fecha de recepción.
   - Estado Item = COMPRADO.
   - Lead Time = Fecha Guía - F. Docum.
   - No se utiliza la hoja Ingresos para el Lead Time.

## Reglas principales
- Universo de materiales = Stock UNION Salidas.
- Si un material tiene salidas pero no está en Stock, se crea con Stock actual = 0 y se marca ROTURA DE STOCK.
- Consumo mensual promedio = Consumo total / meses con consumo.
- Consumo diario = promedio mensual / 30.
- La última compra no se usa para calcular cuánto comprar.
- Se muestran alternativas de abastecimiento para 1, 2 y 3 meses.
- Cuándo comprar = Stock actual <= Punto de pedido.
- Fecha de último movimiento: dd/mm/aaaa, sin hora.

## Ejecutar
```bash
pip install -r requirements.txt
streamlit run app.py
```
