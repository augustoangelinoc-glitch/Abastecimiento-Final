
import io
import streamlit as st
import pandas as pd
import plotly.express as px
from logic import build_analysis

st.set_page_config(page_title="Abastecimiento", page_icon="📦", layout="wide")

st.title("📦 Análisis de Abastecimiento")
st.caption("Objetivo principal: determinar cuánto abastecer con base en consumo, stock y Lead Time real.")

with st.sidebar:
    st.header("Archivos ERP")
    f_stock = st.file_uploader("1. Stock actual", type=["xlsx"], key="stock")
    f_sales = st.file_uploader("2. Salidas", type=["xlsx"], key="sales")
    f_oc = st.file_uploader("3. Órdenes de compra", type=["xlsx"], key="oc")
    f_ing = st.file_uploader("4. Ingresos de OC", type=["xlsx"], key="ing")
    st.divider()
    st.info("Descripción oficial: Stock actual, columna B (campo 'Descripción').")
    st.info("La descripción de Salidas, columna AT ('Descripción.2'), no reemplaza la oficial.")

if not all([f_stock, f_sales, f_oc, f_ing]):
    st.warning("Carga los cuatro archivos del ERP para iniciar el análisis.")
    st.stop()

try:
    stock = pd.read_excel(f_stock)
    sales = pd.read_excel(f_sales)
    oc = pd.read_excel(f_oc)
    ing = pd.read_excel(f_ing)
    view, piv, raw = build_analysis(stock, sales, oc, ing)
except Exception as e:
    st.error(f"No se pudo procesar la información: {e}")
    st.stop()

st.success("Archivos procesados correctamente.")

# ---------- Excel de salida ----------
def make_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Abastecimiento
        cols = [
            "codigo","descripcion","familia","stock_actual","consumo_total",
            "consumo_mensual_promedio","consumo_mensual_mediano",
            "dias_sin_movimiento","lead_time_mediano","stock_seguridad",
            "punto_pedido","stock_objetivo","cantidad_abastecer",
            "tipo_consumo","tendencia","riesgo_stock","explicacion"
        ]
        a = view[[c for c in cols if c in view.columns]].copy()
        a = a.rename(columns={
            "codigo":"Código","descripcion":"Descripción","familia":"Familia",
            "stock_actual":"Stock actual","consumo_total":"Consumo total",
            "consumo_mensual_promedio":"Consumo mensual promedio",
            "consumo_mensual_mediano":"Consumo mensual mediano",
            "dias_sin_movimiento":"Días sin movimiento",
            "lead_time_mediano":"Lead Time mediano (días)",
            "stock_seguridad":"Stock de seguridad",
            "punto_pedido":"Punto de pedido","stock_objetivo":"Stock objetivo",
            "cantidad_abastecer":"Cantidad a abastecer",
            "tipo_consumo":"Tipo de consumo","tendencia":"Tendencia",
            "riesgo_stock":"Riesgo","explicacion":"Diagnóstico"
        })
        a.to_excel(writer, sheet_name="Abastecimiento", index=False)

        # Consumo mensual completo
        cm = piv.copy()
        desc = view.set_index("codigo")["descripcion"].to_dict()
        cm.insert(1, "descripcion", cm["codigo"].map(desc).fillna(""))
        cm = cm.rename(columns={"codigo":"Código","descripcion":"Descripción"})
        cm.to_excel(writer, sheet_name="Consumo mensual", index=False)

        # Lead Time por OC/material
        ld = raw["lead_time"].copy()
        ld = ld.rename(columns={
            "codigo":"Código","emisor":"P. Emis","numero_oc":"Número OC",
            "fecha_oc":"Fecha OC","primera_recepcion":"Primera recepción",
            "unidades_oc":"Unidades OC","unidades_ingresadas":"Unidades ingresadas",
            "lead_time_dias":"Lead Time (días)"
        })
        ld.to_excel(writer, sheet_name="Lead Time", index=False)

        # Anomalías
        an = view.loc[
            (view["riesgo_stock"] != "Normal") |
            (view["pico_anormal"]) |
            (view["tipo_consumo"].isin(["Eventual","Intermitente"])) |
            (view["tendencia"].isin(["Creciente","Decreciente"]))
        ].copy()
        an = an[["codigo","descripcion","tipo_consumo","tendencia","pico_anormal",
                 "riesgo_stock","explicacion"]].rename(columns={
            "codigo":"Código","descripcion":"Descripción","tipo_consumo":"Tipo de consumo",
            "tendencia":"Tendencia","pico_anormal":"Pico anormal",
            "riesgo_stock":"Riesgo","explicacion":"Diagnóstico"
        })
        an.to_excel(writer, sheet_name="Anomalías", index=False)

        # Resumen
        resumen = pd.DataFrame({
            "Indicador": [
                "Materiales","Materiales por abastecer","Materiales sin Lead Time",
                "Materiales con riesgo de stock","Consumo total"
            ],
            "Valor": [
                len(view),
                int((view["cantidad_abastecer"] > 0).sum()),
                int((view["lead_time_mediano"] <= 0).sum()),
                int((view["riesgo_stock"] != "Normal").sum()),
                float(view["consumo_total"].sum())
            ]
        })
        resumen.to_excel(writer, sheet_name="Resumen", index=False)

    output.seek(0)
    return output.getvalue()

# ---------- KPIs ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Materiales", f"{len(view):,}")
c2.metric("Por abastecer", f"{(view['cantidad_abastecer'] > 0).sum():,}")
c3.metric("Sin Lead Time", f"{(view['lead_time_mediano'] <= 0).sum():,}")
c4.metric("Riesgo de stock", f"{(view['riesgo_stock'] != 'Normal').sum():,}")

st.download_button(
    "📥 Descargar análisis completo en Excel",
    data=make_excel(),
    file_name="analisis_abastecimiento.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

tab1, tab2, tab3, tab4 = st.tabs([
    "🛒 Abastecimiento", "📊 Consumo mensual", "🔎 Diagnóstico", "🚚 Lead Time"
])

with tab1:
    st.subheader("¿Cuánto debo abastecer?")
    q = st.text_input("Buscar por código o descripción",
                      placeholder="Ej.: 45007 o nombre del material")
    v = view.copy()
    if q:
        mask = (
            v["codigo"].astype(str).str.contains(q, case=False, na=False) |
            v["descripcion"].astype(str).str.contains(q, case=False, na=False)
        )
        v = v[mask]

    cols = [
        "codigo","descripcion","familia","stock_actual","consumo_total",
        "consumo_mensual_promedio","dias_sin_movimiento","lead_time_mediano",
        "stock_seguridad","punto_pedido","stock_objetivo","cantidad_abastecer",
        "tipo_consumo","riesgo_stock","explicacion"
    ]
    show = v[[c for c in cols if c in v.columns]].copy()
    show = show.rename(columns={
        "codigo":"Código","descripcion":"Descripción","familia":"Familia",
        "stock_actual":"Stock actual","consumo_total":"Consumo total",
        "consumo_mensual_promedio":"Consumo mensual promedio",
        "dias_sin_movimiento":"Días sin movimiento",
        "lead_time_mediano":"Lead Time mediano (días)",
        "stock_seguridad":"Stock de seguridad","punto_pedido":"Punto de pedido",
        "stock_objetivo":"Stock objetivo","cantidad_abastecer":"Cantidad a abastecer",
        "tipo_consumo":"Tipo de consumo","riesgo_stock":"Riesgo","explicacion":"Diagnóstico"
    })
    numeric = [
        c for c in show.columns if c not in [
            "Código","Descripción","Familia","Tipo de consumo","Riesgo",
            "Diagnóstico","Cantidad a abastecer"
        ]
    ]
    for c in numeric:
        show[c] = pd.to_numeric(show[c], errors="coerce").round(2)

    st.dataframe(
        show, use_container_width=True, hide_index=True,
        column_config={
            "Cantidad a abastecer": st.column_config.NumberColumn(format="%d")
        }
    )

with tab2:
    st.subheader("Consumo histórico completo por mes y año")
    if piv.empty:
        st.info("No hay salidas válidas.")
    else:
        q2 = st.text_input("Filtrar por código o descripción", key="q2")
        mp = piv.copy()
        desc = view.set_index("codigo")["descripcion"].to_dict()
        mp.insert(1, "descripcion", mp["codigo"].map(desc).fillna(""))
        if q2:
            m = (
                mp["codigo"].astype(str).str.contains(q2, case=False, na=False) |
                mp["descripcion"].astype(str).str.contains(q2, case=False, na=False)
            )
            mp = mp[m]
        mp = mp.rename(columns={"codigo":"Código","descripcion":"Descripción"})
        for c in mp.columns[2:]:
            mp[c] = pd.to_numeric(mp[c], errors="coerce").fillna(0).round(2)
        st.dataframe(mp, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Diagnóstico y anomalías")
    d = view[[
        "codigo","descripcion","tipo_consumo","tendencia","pico_anormal",
        "dias_sin_movimiento","stock_actual","consumo_mensual_promedio",
        "riesgo_stock","explicacion"
    ]].copy()
    d = d.rename(columns={
        "codigo":"Código","descripcion":"Descripción","tipo_consumo":"Tipo de consumo",
        "tendencia":"Tendencia","pico_anormal":"Pico anormal",
        "dias_sin_movimiento":"Días sin movimiento","stock_actual":"Stock actual",
        "consumo_mensual_promedio":"Consumo mensual promedio",
        "riesgo_stock":"Riesgo","explicacion":"Diagnóstico"
    })
    st.dataframe(d, use_container_width=True, hide_index=True)

with tab4:
    st.subheader("Lead Time real por OC y material")
    if raw["lead_time"].empty:
        st.warning("No se pudo calcular ningún Lead Time con el cruce actual.")
        st.caption("Cruce: P. Emis + Número + Material ↔ P.OC + Número OC + Material.")
    else:
        ld = raw["lead_time"].copy()
        ld = ld.rename(columns={
            "codigo":"Código","emisor":"P. Emis","numero_oc":"Número OC",
            "fecha_oc":"Fecha OC","primera_recepcion":"Primera recepción",
            "unidades_oc":"Unidades OC","unidades_ingresadas":"Unidades ingresadas",
            "lead_time_dias":"Lead Time (días)"
        })
        st.dataframe(ld, use_container_width=True, hide_index=True)
        st.caption("El Lead Time se mide desde la fecha de la OC hasta la primera recepción. Los ingresos parciales se consolidan por OC/material.")

st.divider()
st.caption("El modelo de abastecimiento mostrado es provisional. La siguiente etapa será comparar metodologías de abastecimiento con el histórico real antes de fijar una política definitiva.")
