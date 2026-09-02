# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from logic import (
    load_stock, load_salidas, load_oc, load_ingresos,
    build_monthly_consumption, build_oc_tracking, build_analysis,
    quality_report, export_results
)

st.set_page_config(page_title="Abastecimiento Profesional", page_icon="📦", layout="wide")

st.title("📦 Sistema Profesional de Abastecimiento")
st.caption("Objetivo: determinar cuánto abastecer de cada material con base en demanda, stock, Lead Time y abastecimiento vigente.")

with st.sidebar:
    st.header("Carga ERP")
    stock_file = st.file_uploader("1. Stock actual", type=["xlsx", "xls"])
    salidas_file = st.file_uploader("2. Salidas históricas", type=["xlsx", "xls"])
    oc_file = st.file_uploader("3. Órdenes de compra", type=["xlsx", "xls"])
    ingresos_file = st.file_uploader("4. Ingresos de OC", type=["xlsx", "xls"])

    st.divider()
    periodo_revision = st.number_input(
        "Periodo de revisión / cobertura adicional (días)",
        min_value=0.0, value=30.0, step=1.0,
        help="No es una política de 3 meses. Es un parámetro técnico modificable para definir el horizonte adicional de reposición."
    )
    factor_seguridad = st.number_input(
        "Factor de seguridad sobre la variabilidad",
        min_value=0.0, value=0.50, step=0.05
    )

if not all([stock_file, salidas_file, oc_file, ingresos_file]):
    st.info("Carga los cuatro archivos del ERP para iniciar el análisis.")
    st.markdown("""
### El sistema analizará
- Consumo total y número de salidas.
- Consumo de cada mes y año, incluyendo meses sin consumo.
- Última salida y días sin movimiento.
- Demanda reciente, mediana, variabilidad y tendencia.
- Stock actual y cobertura.
- Lead Time real a partir de OC → ingreso.
- OC vigentes y cantidad pendiente realmente utilizable.
- OC cerradas con pendiente: se excluyen del abastecimiento futuro.
- Cantidad recomendada a abastecer.
""")
    st.stop()

try:
    with st.spinner("Procesando los archivos del ERP..."):
        stock = load_stock(stock_file)
        salidas = load_salidas(salidas_file)
        oc = load_oc(oc_file)
        ingresos = load_ingresos(ingresos_file)
        monthly = build_monthly_consumption(salidas)
        tracking = build_oc_tracking(oc, ingresos)
        analysis = build_analysis(
            stock, salidas, oc, ingresos,
            periodo_revision_dias=periodo_revision,
            factor_seguridad=factor_seguridad
        )
        quality = quality_report(stock, salidas, oc, ingresos, tracking)
except Exception as e:
    st.error("No se pudo procesar la información.")
    st.exception(e)
    st.stop()

# ========================= DASHBOARD =========================
st.subheader("📊 Dashboard ejecutivo")

abastecer = analysis["cantidad_abastecer"] > 0
alto = analysis["riesgo"] == "ALTO"
oc_camino = analysis["situacion"] == "OC EN CAMINO / REVISAR"
sin_mov = analysis["situacion"] == "SIN MOVIMIENTO"

k = st.columns(6)
k[0].metric("Materiales", f"{len(analysis):,}")
k[1].metric("Por abastecer", f"{abastecer.sum():,}")
k[2].metric("Riesgo alto", f"{alto.sum():,}")
k[3].metric("OC en camino", f"{oc_camino.sum():,}")
k[4].metric("Sin movimiento", f"{sin_mov.sum():,}")
k[5].metric("Cantidad a abastecer", f"{analysis['cantidad_abastecer'].sum():,.2f}")

g1, g2, g3 = st.columns(3)
g1.metric("Consumo total histórico", f"{analysis['consumo_total'].sum():,.2f}")
g2.metric("Valor inventario valorizable", f"S/ {analysis['valor_inventario'].sum(skipna=True):,.2f}")
g3.metric("Pendiente OC vigente", f"{analysis['oc_pendiente_valido'].sum():,.2f}")

st.divider()

# ========================= QUÉ ABASTECER =========================
st.subheader("🛒 ¿Qué debo abastecer?")

compra = analysis[analysis["cantidad_abastecer"] > 0].copy()
compra = compra.sort_values(["prioridad", "cantidad_abastecer"], ascending=[True, False])

cols = [
    "prioridad","codigo","descripcion","familia","unidad",
    "stock_actual","demanda_referencia_mensual","cobertura_dias",
    "lead_time_mediano","oc_pendiente_valido","cantidad_abastecer",
    "situacion","riesgo"
]
cols = [c for c in cols if c in compra.columns]
tabla_compra = compra[cols].rename(columns={
    "prioridad":"Prioridad",
    "codigo":"Código",
    "descripcion":"Descripción",
    "familia":"Familia",
    "unidad":"U.M.",
    "stock_actual":"Stock actual",
    "demanda_referencia_mensual":"Demanda mensual",
    "cobertura_dias":"Cobertura (días)",
    "lead_time_mediano":"Lead Time mediano (días)",
    "oc_pendiente_valido":"OC vigente pendiente",
    "cantidad_abastecer":"Cantidad a abastecer",
    "situacion":"Situación",
    "riesgo":"Riesgo"
})
st.dataframe(tabla_compra.round(2), use_container_width=True, hide_index=True, height=420)

# ========================= BÚSQUEDA =========================
st.subheader("🔎 Buscar material")

b1, b2 = st.columns(2)
busqueda_codigo = b1.text_input("Buscar por código")
busqueda_desc = b2.text_input("Buscar por descripción")

view = analysis.copy()
if busqueda_codigo:
    view = view[view["codigo"].astype(str).str.contains(busqueda_codigo.strip(), case=False, na=False)]
if busqueda_desc:
    view = view[view["descripcion"].fillna("").astype(str).str.contains(busqueda_desc.strip(), case=False, na=False)]

if view.empty:
    st.warning("No se encontraron materiales con esos criterios.")
else:
    # selector combinado: código + descripción
    opciones = view.apply(
        lambda r: f"{r['codigo']} | {r['descripcion'] if pd.notna(r['descripcion']) else 'Sin descripción'}",
        axis=1
    ).tolist()
    seleccionado = st.selectbox("Selecciona el material", opciones)
    codigo_sel = seleccionado.split(" | ", 1)[0]
    row = view[view["codigo"].astype(str) == codigo_sel].iloc[0]

    st.markdown(f"### {row['codigo']} — {row['descripcion'] if pd.notna(row['descripcion']) else 'Descripción no disponible'}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Stock actual", f"{row['stock_actual']:.2f}")
    c2.metric("Cantidad a abastecer", f"{row['cantidad_abastecer']:.2f}")
    c3.metric("Demanda mensual", f"{row['demanda_referencia_mensual']:.2f}")
    c4.metric("Cobertura", "Sin consumo" if not np.isfinite(row["cobertura_dias"]) else f"{row['cobertura_dias']:.2f} días")
    c5.metric("Lead Time", "No calculable" if pd.isna(row["lead_time_mediano"]) else f"{row['lead_time_mediano']:.2f} días")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Consumo total", f"{row['consumo_total']:.2f}")
    d2.metric("Cantidad de salidas", f"{row['cantidad_salidas']:.2f}")
    d3.metric("Meses con consumo", f"{row['meses_con_consumo']:.2f}")
    d4.metric("Días sin movimiento", "Sin historial" if pd.isna(row["dias_sin_movimiento"]) else f"{row['dias_sin_movimiento']:.2f}")

    st.info(row["explicacion"])

    ficha = pd.DataFrame({
        "Indicador": [
            "Familia","Unidad de medida","Costo unitario","Valor inventario",
            "Consumo mediano mensual","Consumo últimos 3 meses","Consumo últimos 6 meses",
            "Variabilidad","Tendencia","Mes de mayor consumo","Consumo del mes de mayor consumo",
            "Stock de seguridad","Punto de pedido","Stock objetivo",
            "OC vigente pendiente","Cantidad de OC vigentes","Calidad del Lead Time",
            "Situación","Riesgo"
        ],
        "Valor": [
            row["familia"],row["unidad"],row["costo_unitario"],row["valor_inventario"],
            row["consumo_mediano_mensual"],row["consumo_ultimos_3_meses"],row["consumo_ultimos_6_meses"],
            row["variabilidad"],row["tendencia"],row["mes_mayor_consumo"],row["consumo_mes_mayor"],
            row["stock_seguridad"],row["punto_pedido"],row["stock_objetivo"],
            row["oc_pendiente_valido"],row["cantidad_oc_vigentes"],row["calidad_lead_time"],
            row["situacion"],row["riesgo"]
        ]
    })
    st.dataframe(ficha, use_container_width=True, hide_index=True)

    # Consumo mensual con ceros explícitos
    pm = monthly[monthly["codigo"].astype(str) == codigo_sel].copy()
    if not pm.empty:
        full = pd.period_range(pm["periodo"].min(), pm["periodo"].max(), freq="M")
        pm = pm.set_index("periodo").reindex(full, fill_value=0).rename_axis("periodo").reset_index()
        pm["periodo_str"] = pm["periodo"].astype(str)
        st.subheader("📅 Consumo por mes y año")
        st.dataframe(
            pm[["periodo_str","consumo"]].rename(columns={"periodo_str":"Año-Mes","consumo":"Consumo"}).round(2),
            use_container_width=True, hide_index=True
        )
        fig = px.bar(pm, x="periodo_str", y="consumo", title="Consumo mensual histórico",
                     labels={"periodo_str":"Año-Mes","consumo":"Consumo"})
        st.plotly_chart(fig, use_container_width=True)

# ========================= OC / INGRESOS =========================
st.subheader("📦 Trazabilidad de OC e ingresos")

tr_cols = [
    "oc_id","codigo","fecha_oc","proveedor","cantidad_oc","cantidad_ingresada",
    "pendiente_calculado","pendiente_valido","estado_oc","estado_material",
    "primera_recepcion","ultima_recepcion","lead_time_primera_recepcion_dias",
    "entrega_parcial","oc_cerrada","oc_vigente"
]
tr_cols = [c for c in tr_cols if c in tracking.columns]
tr_view = tracking[tr_cols].rename(columns={
    "oc_id":"OC","codigo":"Código","fecha_oc":"Fecha OC","proveedor":"Proveedor",
    "cantidad_oc":"Cantidad OC","cantidad_ingresada":"Cantidad ingresada",
    "pendiente_calculado":"Pendiente calculado","pendiente_valido":"Pendiente utilizable",
    "estado_oc":"Estado OC","estado_material":"Estado material",
    "primera_recepcion":"Primera recepción","ultima_recepcion":"Última recepción",
    "lead_time_primera_recepcion_dias":"Lead Time (días)",
    "entrega_parcial":"Entrega parcial","oc_cerrada":"OC cerrada","oc_vigente":"OC vigente"
})
st.dataframe(tr_view.round(2), use_container_width=True, hide_index=True, height=350)

st.caption("Regla: una OC CERRADA con material PENDIENTE no se considera abastecimiento futuro. Se conserva para trazabilidad histórica.")

# ========================= CALIDAD =========================
with st.expander("🔍 Calidad y cobertura de datos"):
    qdf = pd.DataFrame({"Indicador": quality.keys(), "Valor": quality.values()})
    st.dataframe(qdf, use_container_width=True, hide_index=True)

# ========================= EXPORTAR =========================
st.subheader("⬇️ Exportar análisis completo")
excel_bytes = export_results(analysis, monthly, tracking, quality)
st.download_button(
    "📥 Descargar Excel profesional",
    data=excel_bytes,
    file_name="abastecimiento_profesional.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
