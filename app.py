
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from logic import load_stock, load_salidas, load_oc, analyze

st.set_page_config(page_title="Abastecimiento", page_icon="📦", layout="wide")
st.title("📦 Análisis de Inventarios y Abastecimiento")
st.caption("Base anterior conservada; se agregan rotura de stock, Lead Time y escenarios de compra.")

with st.sidebar:
    st.header("Parámetros de abastecimiento")
    z = st.selectbox(
        "Nivel de servicio",
        [1.28, 1.65, 1.96, 2.33],
        index=1,
        format_func=lambda x: {1.28:"90%",1.65:"95%",1.96:"97.5%",2.33:"99%"}[x]
    )
    st.info(
        "Los meses se generan únicamente con las fechas existentes en Salidas. "
        "La última compra no se utiliza. Lead Time proviene de Órdenes de Compra."
    )

c1,c2,c3 = st.columns(3)
with c1: fstock = st.file_uploader("1. Stock Actual", type=["xlsx","xls"])
with c2: fsal = st.file_uploader("2. Salidas", type=["xlsx","xls"])
with c3: foc = st.file_uploader("3. Órdenes de Compra", type=["xlsx","xls"])

if st.button("🚀 CALCULAR ANÁLISIS", type="primary", use_container_width=True):
    if not all([fstock, fsal, foc]):
        st.error("Carga los tres archivos.")
    else:
        try:
            stock = load_stock(fstock)
            sal = load_salidas(fsal)
            oc = load_oc(foc)
            df, monthly, periodos = analyze(stock, sal, oc, z=z)
            st.session_state["df"] = df
            st.session_state["monthly"] = monthly
            st.session_state["periodos"] = periodos
            st.success(f"Análisis realizado con {len(periodos)} meses reales de Salidas: {periodos[0]} a {periodos[-1]}.")
        except Exception as e:
            st.exception(e)

df = st.session_state.get("df")
monthly = st.session_state.get("monthly")
periodos = st.session_state.get("periodos")

if df is not None:
    cols = st.columns(5)
    cols[0].metric("Materiales analizados", f"{len(df):,}")
    cols[1].metric("Rotura de stock", f"{int(df.rotura_stock.sum()):,}")
    cols[2].metric("Comprar ahora", f"{int((df.momento_compra=='COMPRAR AHORA').sum()):,}")
    cols[3].metric("Valor inventario", f"S/ {df.valor_inventario.sum():,.0f}")
    cols[4].metric("Compra 1 mes", f"{df.cantidad_abastecer_1m.sum():,.0f}")

    st.subheader("🚨 Materiales con rotura de stock")
    crit = df[df.rotura_stock].copy()
    if crit.empty:
        st.success("No hay materiales con stock cero y consumo registrado.")
    else:
        show = [
            "codigo","descripcion","unidad","familia","stock_actual",
            "consumo_total","meses_con_consumo","consumo_mensual_promedio",
            "consumo_diario","lead_time","punto_pedido",
            "cantidad_abastecer_1m","cantidad_abastecer_2m","cantidad_abastecer_3m",
            "prioridad"
        ]
        st.dataframe(crit[[c for c in show if c in crit.columns]], use_container_width=True, hide_index=True)

    st.subheader("📋 Tabla principal")
    q = st.text_input("Buscar código o descripción")
    situ = st.multiselect("Filtrar situación", sorted(df.situacion_stock.unique()))
    v = df.copy()
    if q:
        v = v[
            v.codigo.astype(str).str.contains(q, case=False, na=False) |
            v.descripcion.astype(str).str.contains(q, case=False, na=False)
        ]
    if situ:
        v = v[v.situacion_stock.isin(situ)]

    rename = {
        "codigo":"Código","descripcion":"Descripción","unidad":"Unidad de medida",
        "familia":"Familia","stock_actual":"Stock actual","costo_unitario":"Costo unitario (S/)",
        "valor_inventario":"Valor del inventario (S/)","consumo_total":"Consumo total",
        "valor_salidas":"Valor de salidas (S/)","ultimo_movimiento":"Último movimiento",
        "meses_con_consumo":"Meses con consumo","meses_sin_consumo":"Meses sin consumo",
        "consumo_mensual_promedio":"Consumo mensual promedio","consumo_diario":"Consumo diario",
        "cobertura_dias":"Cobertura (días)","lead_time":"Lead Time (días)",
        "tipo_consumo":"Tipo de consumo","situacion_stock":"Situación de stock",
        "rotura_stock":"Rotura de stock","tendencia":"Tendencia del consumo",
        "cv_consumo":"CV del consumo","nivel_variabilidad":"Nivel de variabilidad",
        "anomalía_de_consumo":"Anomalía de consumo","abc_acum_pct":"ABC acumulado (%)",
        "clasificacion_abc":"Clasificación ABC","clasificacion_xyz":"Clasificación XYZ",
        "stock_seguridad":"Stock de seguridad","punto_pedido":"Punto de pedido",
        "stock_objetivo_1m":"Stock objetivo 1 mes","cantidad_abastecer_1m":"Cantidad a comprar 1 mes",
        "cobertura_post_1m":"Cobertura después de comprar 1 mes (días)",
        "stock_objetivo_2m":"Stock objetivo 2 meses","cantidad_abastecer_2m":"Cantidad a comprar 2 meses",
        "cobertura_post_2m":"Cobertura después de comprar 2 meses (días)",
        "stock_objetivo_3m":"Stock objetivo 3 meses","cantidad_abastecer_3m":"Cantidad a comprar 3 meses",
        "cobertura_post_3m":"Cobertura después de comprar 3 meses (días)",
        "momento_compra":"Cuándo comprar","prioridad":"Prioridad",
        "diagnostico":"Diagnóstico","recomendacion":"Recomendación"
    }

    # Primero los campos de negocio, luego los meses dinámicos.
    base_cols = [
        "codigo","descripcion","unidad","familia","stock_actual","costo_unitario",
        "valor_inventario","consumo_total","valor_salidas","ultimo_movimiento"
    ]
    metric_cols = [
        "meses_con_consumo","meses_sin_consumo","consumo_mensual_promedio","consumo_diario",
        "cobertura_dias","lead_time","tipo_consumo","situacion_stock","rotura_stock",
        "tendencia","cv_consumo","nivel_variabilidad","anomalía_de_consumo",
        "abc_acum_pct","clasificacion_abc","clasificacion_xyz","stock_seguridad","punto_pedido",
        "stock_objetivo_1m","cantidad_abastecer_1m","cobertura_post_1m",
        "stock_objetivo_2m","cantidad_abastecer_2m","cobertura_post_2m",
        "stock_objetivo_3m","cantidad_abastecer_3m","cobertura_post_3m",
        "momento_compra","prioridad","diagnostico","recomendacion"
    ]
    month_cols = [str(p) for p in periodos]
    final_cols = [c for c in base_cols if c in v.columns] + [c for c in month_cols if c in v.columns] + [c for c in metric_cols if c in v.columns]
    out = v[final_cols].copy()

    if "ultimo_movimiento" in out:
        out["ultimo_movimiento"] = pd.to_datetime(out["ultimo_movimiento"], errors="coerce").dt.strftime("%d/%m/%Y")

    st.dataframe(out.rename(columns=rename), use_container_width=True, hide_index=True, height=650)

    st.subheader("📌 Decisión de compra por material")
    code = st.selectbox("Selecciona un material", df.codigo.astype(str).tolist())
    r = df[df.codigo.astype(str) == str(code)].iloc[0]
    st.write(f"**{r.descripcion}** — `{r.codigo}`")
    a,b,c,d = st.columns(4)
    a.metric("Consumo mensual promedio", f"{r.consumo_mensual_promedio:,.0f} {r.unidad}")
    b.metric("Stock actual", f"{r.stock_actual:,.0f} {r.unidad}")
    c.metric("Lead Time", f"{r.lead_time_utilizado:.0f} días")
    d.metric("Punto de pedido", f"{r.punto_pedido:,.0f} {r.unidad}")
    st.write(f"**Cuándo comprar:** {r.momento_compra}")
    st.write(f"**1 mes:** comprar **{r.cantidad_abastecer_1m:,.0f} {r.unidad}** → cobertura {r.cobertura_post_1m:.1f} días.")
    st.write(f"**2 meses:** comprar **{r.cantidad_abastecer_2m:,.0f} {r.unidad}** → cobertura {r.cobertura_post_2m:.1f} días.")
    st.write(f"**3 meses:** comprar **{r.cantidad_abastecer_3m:,.0f} {r.unidad}** → cobertura {r.cobertura_post_3m:.1f} días.")
    st.info(r.diagnostico)

    st.subheader("📈 Consumo mensual")
    pm = monthly[monthly.codigo.astype(str) == str(code)].sort_values("periodo")
    if not pm.empty:
        st.plotly_chart(
            px.line(pm, x="periodo_str", y="consumo", markers=True, title=f"Consumo mensual — {code}"),
            use_container_width=True
        )
else:
    st.info("Carga Stock, Salidas y Órdenes de Compra y presiona CALCULAR ANÁLISIS.")
