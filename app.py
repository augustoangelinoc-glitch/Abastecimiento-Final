
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from logic import build_analysis

st.set_page_config(page_title="Abastecimiento", page_icon="📦", layout="wide")
st.title("📦 Análisis de Abastecimiento")
st.caption("Objetivo: determinar cuánto abastecer, usando consumo histórico, stock actual y Lead Time real.")

with st.sidebar:
    st.header("Archivos ERP")
    f_stock=st.file_uploader("1. Stock actual", type=["xlsx"], key="stock")
    f_sales=st.file_uploader("2. Salidas", type=["xlsx"], key="sales")
    f_oc=st.file_uploader("3. Órdenes de compra", type=["xlsx"], key="oc")
    f_ing=st.file_uploader("4. Ingresos de OC", type=["xlsx"], key="ing")
    st.divider()
    st.info("La descripción oficial se toma exclusivamente de Stock actual, columna B (campo 'Descripción').")

if not all([f_stock,f_sales,f_oc,f_ing]):
    st.warning("Carga los cuatro archivos del ERP para iniciar el análisis.")
    st.stop()

try:
    stock=pd.read_excel(f_stock)
    sales=pd.read_excel(f_sales)
    oc=pd.read_excel(f_oc)
    ing=pd.read_excel(f_ing)
    view, piv, raw=build_analysis(stock,sales,oc,ing)
except Exception as e:
    st.error(f"No se pudo procesar la información: {e}")
    st.stop()

st.success("Archivos procesados correctamente.")

c1,c2,c3,c4=st.columns(4)
c1.metric("Materiales", f"{len(view):,}")
c2.metric("Por abastecer", f"{(view['cantidad_abastecer']>0).sum():,}")
c3.metric("Sin Lead Time", f"{(view['lead_time_mediano']<=0).sum():,}")
c4.metric("Riesgo de stock", f"{(~view['riesgo_stock'].eq('Normal')).sum():,}")

tab1,tab2,tab3,tab4=st.tabs(["🛒 Abastecimiento","📊 Consumo mensual","🔎 Diagnóstico","🚚 Lead Time"])

with tab1:
    st.subheader("¿Cuánto debo abastecer?")
    q=st.text_input("Buscar por código o descripción", placeholder="Ej.: 45007 o resaltador")
    v=view.copy()
    if q:
        mask=v.codigo.astype(str).str.contains(q,case=False,na=False) | v.descripcion.astype(str).str.contains(q,case=False,na=False)
        v=v[mask]
    cols=["codigo","descripcion","familia","stock_actual","consumo_mensual_promedio","lead_time_mediano","stock_seguridad","punto_pedido","stock_objetivo","cantidad_abastecer","tipo_consumo","riesgo_stock","modelo_estado"]
    show=v[cols].copy()
    rename={
        "codigo":"Código","descripcion":"Descripción","familia":"Familia","stock_actual":"Stock actual",
        "consumo_mensual_promedio":"Consumo mensual promedio","lead_time_mediano":"Lead Time mediano (días)",
        "stock_seguridad":"Stock de seguridad","punto_pedido":"Punto de pedido","stock_objetivo":"Stock objetivo",
        "cantidad_abastecer":"Cantidad a abastecer","tipo_consumo":"Tipo de consumo","riesgo_stock":"Riesgo",
        "modelo_estado":"Estado del cálculo"
    }
    show=show.rename(columns=rename)
    for c in show.columns:
        if c not in ["Código","Descripción","Familia","Tipo de consumo","Riesgo","Estado del cálculo","Cantidad a abastecer"]:
            show[c]=pd.to_numeric(show[c],errors="coerce").round(2)
    st.dataframe(show,use_container_width=True,hide_index=True,column_config={"Cantidad a abastecer":st.column_config.NumberColumn(format="%d")})
    st.caption("La cantidad a abastecer se redondea siempre hacia arriba al entero siguiente. Si no existe Lead Time calculable, no se inventa uno y la recomendación queda en 0.")

with tab2:
    st.subheader("Consumo histórico completo por mes")
    if piv.empty:
        st.info("No hay salidas válidas.")
    else:
        q2=st.text_input("Filtrar por código o descripción", key="q2")
        mp=piv.copy()
        if q2:
            desc=view.set_index("codigo")["descripcion"].to_dict()
            mp["descripcion"]=mp["codigo"].map(desc).fillna("")
            m=mp.codigo.astype(str).str.contains(q2,case=False,na=False)|mp.descripcion.str.contains(q2,case=False,na=False)
            mp=mp[m]
            mp=mp.drop(columns=["descripcion"])
        st.dataframe(mp,use_container_width=True,hide_index=True)
        st.caption("Se muestran todos los meses disponibles en las salidas. Un mes sin consumo aparece como 0.00.")

with tab3:
    st.subheader("Anomalías y comportamiento")
    alerts=view[view["riesgo_stock"]!="Normal"].copy()
    anom=view[(view["pico_anormal"]) | (view["tipo_consumo"]=="Eventual") | (view["tendencia"]!="Estable")].copy()
    st.markdown("**Riesgos de stock**")
    st.dataframe(alerts[["codigo","descripcion","stock_actual","consumo_mensual_promedio","dias_sin_movimiento","riesgo_stock"]].rename(columns={"codigo":"Código","descripcion":"Descripción","stock_actual":"Stock actual","consumo_mensual_promedio":"Consumo mensual promedio","dias_sin_movimiento":"Días sin movimiento","riesgo_stock":"Diagnóstico"}).round(2),use_container_width=True,hide_index=True)
    st.markdown("**Anomalías / comportamiento**")
    st.dataframe(anom[["codigo","descripcion","tipo_consumo","tendencia","pico_anormal","explicacion"]].rename(columns={"codigo":"Código","descripcion":"Descripción","tipo_consumo":"Tipo de consumo","tendencia":"Tendencia","pico_anormal":"Pico anormal","explicacion":"Explicación"}),use_container_width=True,hide_index=True)

with tab4:
    st.subheader("Lead Time real")
    lt=view[view["lead_time_mediano"]>0][["codigo","descripcion","lead_time_mediano","lead_time_promedio","lead_time_min","lead_time_max","oc_con_ingreso"]].copy()
    lt=lt.rename(columns={"codigo":"Código","descripcion":"Descripción","lead_time_mediano":"Mediana (días)","lead_time_promedio":"Promedio (días)","lead_time_min":"Mínimo (días)","lead_time_max":"Máximo (días)","oc_con_ingreso":"OC con ingreso"})
    for c in ["Mediana (días)","Promedio (días)","Mínimo (días)","Máximo (días)"]:
        lt[c]=lt[c].round(2)
    st.dataframe(lt,use_container_width=True,hide_index=True)
    st.caption("Cruce: P. Emis + Número + Material de OC ↔ P.OC + Número OC + Material de Ingresos. Lead Time = primera fecha de ingreso - fecha de OC.")

st.divider()
st.subheader("Material seleccionado")
if len(view):
    selected=st.selectbox("Selecciona un material", view["codigo"].tolist(), format_func=lambda x: f"{x} — {view.loc[view.codigo==x,'descripcion'].iloc[0]}")
    r=view[view.codigo==selected].iloc[0]
    a,b,c,d=st.columns(4)
    a.metric("Stock actual", f"{r.stock_actual:,.2f}")
    b.metric("Consumo total", f"{r.consumo_total:,.2f}")
    c.metric("Lead Time", f"{r.lead_time_mediano:,.2f} días" if r.lead_time_mediano>0 else "No calculable")
    d.metric("Cantidad a abastecer", f"{int(r.cantidad_abastecer)}")
    st.write(f"**Diagnóstico:** {r.explicacion}")
