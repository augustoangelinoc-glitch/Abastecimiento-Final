
import io
import pandas as pd
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
    foc=st.file_uploader("OC",type=["xlsx","xls","csv"])
    fing=st.file_uploader("Ingresos",type=["xlsx","xls","csv"])

if not fs or not fsa:
    st.info("Carga Stock Actual y Salidas. OC e Ingresos son necesarios para calcular Lead Time.")
    st.stop()

try:
    stock=choose(read_file(fs),["stock","existencia"])
    sal=choose(read_file(fsa),["salida","consumo"])
    oc=choose(read_file(foc),["oc","orden"]) if foc else None
    ing=choose(read_file(fing),["ingreso","recepcion"]) if fing else None
    df,months=calculate(stock,sal,oc,ing)
except Exception as e:
    st.exception(e); st.stop()

# Nombres visibles: NO mostrar nombres técnicos.
labels={
"codigo":"Código","descripcion":"Descripción","familia":"Familia","unidad_medida":"Unidad de medida",
"stock_actual":"Stock actual","costo_unitario":"Costo unitario (S/)","valor_inventario":"Valor del inventario (S/)",
"valor_salidas":"Valor de salidas (S/)","consumo_total":"Consumo total","meses_con_consumo":"Meses con consumo",
"meses_sin_consumo":"Meses sin consumo","consumo_mensual_prom":"Consumo mensual promedio",
"consumo_diario":"Consumo diario","ultimo_movimiento":"Último movimiento","dias_sin_movimiento":"Días sin movimiento",
"cobertura_dias":"Cobertura (días)","lead_time_dias":"Lead Time (días)","stock_seguridad":"Stock de seguridad",
"punto_pedido":"Punto de pedido","stock_objetivo":"Stock objetivo","cantidad_a_comprar":"Cantidad a abastecer",
"tipo_consumo":"Tipo de consumo","variabilidad":"Nivel de variabilidad","tendencia":"Tendencia del consumo",
"anomalia":"Anomalía de consumo","abc":"Clasificación ABC","xyz":"Clasificación XYZ","prioridad":"Prioridad",
"metodologia":"Metodología utilizada","recomendacion":"Recomendación","diagnostico":"Diagnóstico"
}

with st.sidebar:
    st.header("Filtros")
    pr=st.multiselect("Prioridad",sorted(df.prioridad.dropna().unique()))
    fam=st.multiselect("Familia",sorted(df.familia.astype(str).unique()))
    search=st.text_input("Buscar por código o descripción")
    only=st.checkbox("Solo materiales con cantidad a abastecer")

view=df.copy()
if pr:view=view[view.prioridad.isin(pr)]
if fam:view=view[view.familia.astype(str).isin(fam)]
if search:
    q=search.strip()
    view=view[view.codigo.str.contains(q,case=False,na=False)|view.descripcion.str.contains(q,case=False,na=False)]
if only:view=view[view.cantidad_a_comprar>0]

a,b,c,d,e=st.columns(5)
a.metric("Materiales",len(df))
b.metric("Valor del inventario",f"S/ {df.valor_inventario.sum():,.2f}")
c.metric("Valor de salidas",f"S/ {df.valor_salidas.sum():,.2f}")
d.metric("Cantidad a abastecer",f"{int(df.cantidad_a_comprar.sum()):,}")
e.metric("Críticos",int((df.prioridad=="CRÍTICO").sum()))

tabs=st.tabs(["📊 Abastecimiento","📈 Dashboard ejecutivo","🔎 Análisis de consumo","📥 Descargar"])

with tabs[0]:
    st.subheader("Tabla principal de abastecimiento")
    cols=["codigo","descripcion","familia","unidad_medida","stock_actual","costo_unitario","valor_inventario","valor_salidas","consumo_total"]+months+[
        "meses_con_consumo","meses_sin_consumo","consumo_mensual_prom","consumo_diario","ultimo_movimiento",
        "dias_sin_movimiento","cobertura_dias","lead_time_dias","stock_seguridad","punto_pedido","stock_objetivo",
        "cantidad_a_comprar","tipo_consumo","variabilidad","tendencia","anomalia","abc","xyz","prioridad",
        "metodologia","recomendacion","diagnostico"
    ]
    x=view[[c for c in cols if c in view.columns]].copy()
    for c in x.select_dtypes(include="number").columns:
        if c!="cantidad_a_comprar": x[c]=x[c].round(2)
    if "ultimo_movimiento" in x.columns:
        x["ultimo_movimiento"]=pd.to_datetime(x["ultimo_movimiento"],errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
    x=x.rename(columns=labels)
    st.dataframe(x,use_container_width=True,hide_index=True,height=700)

with tabs[1]:
    st.subheader("Resumen ejecutivo")
    st.bar_chart(df["prioridad"].value_counts())
    st.subheader("Valor del inventario por clasificación ABC")
    st.bar_chart(df.groupby("abc")["valor_inventario"].sum())
    st.subheader("Top 10 materiales por cantidad a abastecer")
    top=df.nlargest(10,"cantidad_a_comprar")[["codigo","descripcion","cantidad_a_comprar","prioridad","metodologia","recomendacion"]].rename(columns=labels)
    st.dataframe(top,use_container_width=True,hide_index=True)
    st.subheader("Top 10 por valor del inventario")
    top2=df.nlargest(10,"valor_inventario")[["codigo","descripcion","valor_inventario","abc","xyz"]].rename(columns=labels)
    st.dataframe(top2,use_container_width=True,hide_index=True)

with tabs[2]:
    st.subheader("Consumo mensual")
    if months:
        m=df[months].sum().to_frame("Consumo")
        st.line_chart(m)
    c1,c2=st.columns(2)
    with c1:
        st.subheader("Tipo de consumo")
        st.bar_chart(df.tipo_consumo.value_counts())
    with c2:
        st.subheader("Tendencia")
        st.bar_chart(df.tendencia.value_counts())
    st.subheader("Anomalías detectadas")
    an=df[df.anomalia=="Pico anormal"][["codigo","descripcion","consumo_total","tendencia","anomalia"]].rename(columns=labels)
    st.dataframe(an,use_container_width=True,hide_index=True)

with tabs[3]:
    out=io.BytesIO()
    export=df.copy()
    # El Excel también debe ser entendible en español.
    export=export.rename(columns=labels)
    # Fecha sin hora.
    if "Último movimiento" in export.columns:
        export["Último movimiento"]=pd.to_datetime(export["Último movimiento"],errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
    with pd.ExcelWriter(out,engine="openpyxl") as w:
        export.to_excel(w,index=False,sheet_name="Abastecimiento")
        monthly=df[["codigo","descripcion"]+months].copy().rename(columns=labels)
        monthly.to_excel(w,index=False,sheet_name="Consumo mensual")
        resumen=df.groupby("prioridad").agg(
            materiales=("codigo","count"),
            cantidad_a_abastecer=("cantidad_a_comprar","sum"),
            valor_inventario=("valor_inventario","sum")
        ).reset_index().rename(columns=labels)
        resumen.to_excel(w,index=False,sheet_name="Resumen")
    st.download_button("⬇️ Descargar Excel completo",out.getvalue(),"Analisis_Abastecimiento.xlsx")
    st.download_button("⬇️ Descargar CSV",export.to_csv(index=False).encode("utf-8-sig"),"Abastecimiento.csv")

st.caption("Los identificadores conservan ceros iniciales. Las fechas se muestran como DD/MM/AAAA. Los meses de consumo llegan solo hasta el último mes real de Salidas.")
