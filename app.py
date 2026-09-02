
import io
import pandas as pd
import numpy as np
import streamlit as st
from logyc import calculate

st.set_page_config(page_title="ABASTECIMIENTO",page_icon="📦",layout="wide")

st.title("📦 ABASTECIMIENTO")
st.caption("Análisis ejecutivo para determinar cuánto abastecer, cuándo y por qué.")

def read_file(f):
    if f.name.lower().endswith(".csv"): return {"CSV":pd.read_csv(f,dtype=str)}
    x=pd.ExcelFile(f)
    return {s:pd.read_excel(f,sheet_name=s,dtype=str) for s in x.sheet_names}

def choose(d,words):
    for n,v in d.items():
        if any(w.lower() in n.lower() for w in words): return v
    return next(iter(d.values()))

with st.sidebar:
    st.header("Datos ERP")
    fs=st.file_uploader("Stock Actual",type=["xlsx","xls","csv"])
    fsa=st.file_uploader("Salidas",type=["xlsx","xls","csv"])
    foc=st.file_uploader("OC (opcional)",type=["xlsx","xls","csv"])
    fing=st.file_uploader("Ingresos (opcional)",type=["xlsx","xls","csv"])

if not fs or not fsa:
    st.info("Carga Stock Actual y Salidas. Para calcular Lead Time real, carga también OC e Ingresos.")
    st.stop()

try:
    ds=read_file(fs); dsa=read_file(fsa)
    stock=choose(ds,["stock","existencia"])
    sal=choose(dsa,["salida","consumo"])
    oc=choose(read_file(foc),["oc","orden"]) if foc else None
    ing=choose(read_file(fing),["ingreso","recepcion"]) if fing else None
    df,months=calculate(stock,sal,oc,ing)
except Exception as e:
    st.exception(e)
    st.stop()

with st.sidebar:
    st.header("Filtros")
    pr=st.multiselect("Prioridad",sorted(df.prioridad.unique()))
    fam=st.multiselect("Familia",sorted(df.familia.astype(str).unique()))
    search=st.text_input("Código o descripción")
    only=st.checkbox("Solo con cantidad a comprar")
view=df.copy()
if pr:view=view[view.prioridad.isin(pr)]
if fam:view=view[view.familia.astype(str).isin(fam)]
if search:view=view[view.codigo.str.contains(search,case=False,na=False)|view.descripcion.str.contains(search,case=False,na=False)]
if only:view=view[view.cantidad_a_comprar>0]

a,b,c,d,e=st.columns(5)
a.metric("Materiales",len(df))
b.metric("Valor inventario",f"S/ {df.valor_inventario.sum():,.2f}")
c.metric("Valor salidas",f"S/ {df.valor_salidas.sum():,.2f}")
d.metric("Cantidad a comprar",f"{int(df.cantidad_a_comprar.sum()):,}")
e.metric("Críticos",int((df.prioridad=="CRÍTICO").sum()))

tabs=st.tabs(["📊 Abastecimiento","📈 Dashboard ejecutivo","🔎 Demanda","📥 Descargar"])

with tabs[0]:
    st.subheader("Tabla principal")
    cols=["codigo","descripcion","familia","unidad_medida","stock_actual","costo_unitario","valor_inventario","valor_salidas","consumo_total"]+months+[
        "meses_con_consumo","meses_sin_consumo","consumo_mensual_prom","consumo_diario","ultimo_movimiento","dias_sin_movimiento",
        "cobertura_dias","lead_time_dias","stock_seguridad","punto_pedido","stock_objetivo","cantidad_a_comprar",
        "tipo_consumo","variabilidad","tendencia","anomalia","abc","xyz","prioridad","metodologia","recomendacion","diagnostico"]
    x=view[[c for c in cols if c in view.columns]].copy()
    for c in x.select_dtypes(include="number").columns:
        if c!="cantidad_a_comprar": x[c]=x[c].round(2)
    st.dataframe(x,use_container_width=True,hide_index=True,height=680)

with tabs[1]:
    st.subheader("Resumen para decisión")
    st.bar_chart(df.prioridad.value_counts())
    st.subheader("Valor de inventario por ABC")
    st.bar_chart(df.groupby("abc")["valor_inventario"].sum())
    st.subheader("Top 10 por cantidad a comprar")
    st.dataframe(df.nlargest(10,"cantidad_a_comprar")[["codigo","descripcion","cantidad_a_comprar","prioridad","metodologia","recomendacion"]],use_container_width=True,hide_index=True)
    st.subheader("Top 10 por valor de inventario")
    st.dataframe(df.nlargest(10,"valor_inventario")[["codigo","descripcion","valor_inventario","abc","xyz"]],use_container_width=True,hide_index=True)

with tabs[2]:
    st.subheader("Consumo mensual total")
    if months:
        m=df[months].sum().to_frame("consumo")
        st.line_chart(m)
    c1,c2=st.columns(2)
    c1.bar_chart(df.tipo_consumo.value_counts())
    c2.bar_chart(df.tendencia.value_counts())
    st.subheader("Anomalías")
    st.dataframe(df[df.anomalia=="Pico anormal"][["codigo","descripcion","consumo_total","tendencia","anomalia"]],use_container_width=True,hide_index=True)

with tabs[3]:
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as w:
        df.to_excel(w,index=False,sheet_name="Abastecimiento")
        df[["codigo","descripcion"]+months].to_excel(w,index=False,sheet_name="Consumo mensual")
        df.groupby("prioridad").agg(materiales=("codigo","count"),cantidad_a_comprar=("cantidad_a_comprar","sum"),valor_inventario=("valor_inventario","sum")).reset_index().to_excel(w,index=False,sheet_name="Resumen")
    st.download_button("⬇️ Descargar Excel completo",out.getvalue(),"Analisis_Abastecimiento.xlsx")
    st.download_button("⬇️ Descargar CSV",df.to_csv(index=False).encode("utf-8-sig"),"Abastecimiento.csv")

st.caption("Nota: no se inventa Lead Time si OC e ingreso no pueden cruzarse por código + OC + fechas.")
