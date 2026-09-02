import io
from datetime import datetime
import pandas as pd
import streamlit as st

from logic import (
    load_stock, load_salidas, load_oc, load_ingresos,
    build_analysis, build_oc_tracking, quality_report, export_results
)

st.set_page_config(page_title="Abastecimiento Profesional", page_icon="📦", layout="wide")

st.title("📦 Sistema Profesional de Inventarios y Abastecimiento")
st.caption("ERP → carga completa → validación → análisis → decisión de abastecimiento")

with st.sidebar:
    st.header("Archivos ERP")
    stock_file = st.file_uploader("Stock actual", type=["xlsx","xls"], key="stock")
    salidas_file = st.file_uploader("Salidas históricas", type=["xlsx","xls"], key="salidas")
    oc_file = st.file_uploader("Órdenes de compra", type=["xlsx","xls"], key="oc")
    ingresos_file = st.file_uploader("Ingresos de OC", type=["xlsx","xls"], key="ingresos")
    st.divider()
    st.info("Los archivos originales no se modifican. El sistema solo transforma internamente los campos necesarios.")

if not all([stock_file, salidas_file, oc_file, ingresos_file]):
    st.warning("Carga los 4 archivos completos descargados del ERP para ejecutar el análisis.")
    st.markdown("""
### Flujo
1. **Stock actual:** fotografía confiable del inventario.
2. **Salidas:** demanda observada desde enero.
3. **OC:** compras solicitadas.
4. **Ingresos:** compras realmente recibidas y entregas parciales.
5. El sistema cruza OC + ingresos mediante **P. Emis + Número** ↔ **P.OC + Número OC**.
6. El costo analítico prioriza **C. Kardex**; costo 0 queda como **sin costo / posible consignación**.
""")
    st.stop()

try:
    with st.spinner("Leyendo y validando archivos del ERP..."):
        stock = load_stock(stock_file)
        salidas = load_salidas(salidas_file)
        oc = load_oc(oc_file)
        ingresos = load_ingresos(ingresos_file)
        q = quality_report(stock, salidas, oc, ingresos)
        analysis = build_analysis(stock, salidas, oc, ingresos)
        tracking = build_oc_tracking(oc, ingresos)
except Exception as e:
    st.error(f"No se pudo procesar la carga: {e}")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", "🚦 Abastecimiento", "🧾 OC e Ingresos", "🔎 Calidad de datos", "⬇️ Exportar"
])

with tab1:
    c = st.columns(6)
    c[0].metric("Materiales", f"{len(analysis):,}")
    c[1].metric("Stock", f"{analysis['stock_actual'].sum():,.0f}")
    c[2].metric("Valor inventario", f"S/ {analysis['valor_inventario'].sum():,.2f}")
    c[3].metric("Riesgo alto", f"{(analysis['riesgo']=='ALTO').sum():,}")
    c[4].metric("Exceso", f"{(analysis['situacion']=='EXCESO').sum():,}")
    c[5].metric("Sin movimiento", f"{(analysis['situacion']=='SIN MOVIMIENTO').sum():,}")

    st.subheader("Prioridad de abastecimiento")
    cols = ["prioridad","codigo","descripcion","stock_actual","consumo_mensual","cobertura_dias",
            "abc","xyz","oc_pendiente","riesgo","situacion","cantidad_recomendada","explicacion"]
    st.dataframe(analysis.sort_values(["prioridad","riesgo","cantidad_recomendada"], ascending=[True,True,False])[cols],
                 use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Motor de decisión")
    filtros = st.multiselect("Mostrar situaciones", sorted(analysis["situacion"].dropna().unique()),
                             default=sorted(analysis["situacion"].dropna().unique()))
    view = analysis[analysis["situacion"].isin(filtros)].copy()
    st.dataframe(view[[
        "codigo","descripcion","familia","stock_actual","costo_unitario","valor_inventario",
        "consumo_mensual","consumo_reciente","variabilidad_cv","tendencia","abc","xyz",
        "lead_time_mediano","oc_pendiente","cobertura_dias","stock_seguridad",
        "punto_pedido","stock_objetivo","cantidad_recomendada","riesgo","situacion","explicacion"
    ]], use_container_width=True, hide_index=True)

    st.subheader("Detalle de material")
    selected = st.selectbox("Código", analysis["codigo"].astype(str).tolist())
    row = analysis[analysis["codigo"].astype(str)==selected].iloc[0]
    st.write(f"**{row['descripcion']}**")
    st.json({
        "Stock actual": row["stock_actual"],
        "Costo unitario": row["costo_unitario"],
        "Consumo mensual": row["consumo_mensual"],
        "Cobertura (días)": row["cobertura_dias"],
        "ABC": row["abc"],
        "XYZ": row["xyz"],
        "Lead Time mediano": row["lead_time_mediano"],
        "OC pendiente": row["oc_pendiente"],
        "Cantidad recomendada": row["cantidad_recomendada"],
        "Riesgo": row["riesgo"],
        "Situación": row["situacion"],
        "Explicación": row["explicacion"],
    })

with tab3:
    st.subheader("Seguimiento OC → Ingresos")
    st.dataframe(tracking, use_container_width=True, hide_index=True)

with tab4:
    st.subheader("Auditoría de calidad")
    for k, v in q.items():
        st.metric(k, f"{v:,}" if isinstance(v, int) else str(v))
    st.caption("Los problemas de calidad no se corrigen silenciosamente: se reportan para trazabilidad.")

with tab5:
    st.subheader("Descargar resultados")
    data = export_results(analysis, tracking, q)
    st.download_button(
        "📥 Descargar Excel de análisis",
        data=data,
        file_name=f"abastecimiento_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
