
import streamlit as st, pandas as pd, numpy as np
import plotly.express as px
from datetime import datetime
from logic import load_stock,load_salidas,load_oc,analyze

st.set_page_config(page_title="Abastecimiento Ejecutivo",page_icon="📦",layout="wide")
st.title("📦 Análisis Ejecutivo de Inventarios y Abastecimiento")
st.caption("Incluye stock cero con salidas, consumo histórico, ABC/XYZ, Lead Time y abastecimiento por horizonte.")

with st.sidebar:
    st.header("Parámetros")
    horizonte=st.selectbox("Horizonte principal", [1,2,3], format_func=lambda x:f"{x} mes{'es' if x>1 else ''}")
    z=st.selectbox("Nivel de servicio", [1.28,1.65,1.96,2.33], index=1,
                   format_func=lambda x:{1.28:"90%",1.65:"95%",1.96:"97.5%",2.33:"99%"}[x])
    st.info("Cuándo comprar = Punto de pedido. Cuánto comprar = Stock objetivo - Stock actual. La última compra NO se usa.")

a,b,c=st.columns(3)
with a: fstock=st.file_uploader("1. Stock Actual",type=["xlsx","xls"])
with b: fsal=st.file_uploader("2. Salidas",type=["xlsx","xls"])
with c: foc=st.file_uploader("3. Órdenes de Compra",type=["xlsx","xls"])

if st.button("🚀 CALCULAR ANÁLISIS",type="primary",use_container_width=True):
    if not all([fstock,fsal,foc]): st.error("Carga los tres archivos.")
    else:
        try:
            stock=load_stock(fstock); sal=load_salidas(fsal); oc=load_oc(foc)
            df,monthly,periods=analyze(stock,sal,oc,horizonte,z)
            st.session_state.update(df=df,monthly=monthly,periods=periods)
            st.success("Análisis calculado correctamente.")
        except Exception as e: st.exception(e)

df=st.session_state.get("df")
monthly=st.session_state.get("monthly")
periods=st.session_state.get("periods")

if df is not None:
    k=st.columns(5)
    k[0].metric("Materiales",f"{len(df):,}")
    k[1].metric("Rotura de stock",f"{df.rotura_stock.sum():,}")
    k[2].metric("Comprar ahora",f"{(df.momento_compra=='COMPRAR AHORA').sum():,}")
    k[3].metric("Valor inventario",f"S/ {df.valor_inventario.sum():,.0f}")
    k[4].metric("Compra horizonte",f"{df.cantidad_abastecer.sum():,.0f}")

    st.subheader("🚨 Rotura de stock")
    r=df[df.rotura_stock]
    if r.empty: st.success("No hay materiales con stock cero y salidas.")
    else: st.dataframe(r[["codigo","descripcion","unidad","familia","stock_actual","consumo_total","consumo_mensual_promedio","consumo_diario","meses_con_consumo","lead_time","punto_pedido","cantidad_abastecer_1m","cantidad_abastecer_2m","cantidad_abastecer_3m","prioridad"]],use_container_width=True,hide_index=True)

    st.subheader("📊 Indicadores")
    x,y=st.columns(2)
    with x:
        cm=monthly.groupby("periodo_str",as_index=False).consumo.sum()
        st.plotly_chart(px.bar(cm,x="periodo_str",y="consumo",title="Consumo mensual total"),use_container_width=True)
    with y:
        ac=df.clasificacion_abc.value_counts().rename_axis("ABC").reset_index(name="Materiales")
        st.plotly_chart(px.pie(ac,names="ABC",values="Materiales",title="Clasificación ABC"),use_container_width=True)

    st.subheader("📋 Tabla principal")
    q=st.text_input("Buscar código o descripción")
    situ=st.multiselect("Situación",sorted(df.situacion_stock.unique()))
    v=df.copy()
    if q: v=v[v.codigo.str.contains(q,case=False,na=False)|v.descripcion.astype(str).str.contains(q,case=False,na=False)]
    if situ: v=v[v.situacion_stock.isin(situ)]
    out=v.copy()
    out["ultimo_movimiento"]=pd.to_datetime(out.ultimo_movimiento,errors="coerce").dt.strftime("%d/%m/%Y")
    rename={"codigo":"Código","descripcion":"Descripción","unidad":"Unidad de medida","familia":"Familia","stock_actual":"Stock actual","costo_unitario":"Costo unitario (S/)","valor_inventario":"Valor del inventario (S/)","consumo_total":"Consumo total","valor_salidas":"Valor de salidas (S/)","ultimo_movimiento":"Último movimiento","meses_con_consumo":"Meses con consumo","meses_sin_consumo":"Meses sin consumo","consumo_mensual_promedio":"Consumo mensual promedio","consumo_diario":"Consumo diario","dias_cobertura":"Cobertura (días)","lead_time":"Lead Time (días)","tipo_consumo":"Tipo de consumo","situacion_stock":"Situación de stock","rotura_stock":"Rotura de stock","tendencia":"Tendencia del consumo","cv_consumo":"CV del consumo","nivel_variabilidad":"Nivel de variabilidad","anomalía_de_consumo":"Anomalía de consumo","abc_acum_pct":"ABC acumulado (%)","clasificacion_abc":"Clasificación ABC","clasificacion_xyz":"Clasificación XYZ","stock_seguridad":"Stock de seguridad","punto_pedido":"Punto de pedido","stock_objetivo":"Stock objetivo","cantidad_abastecer":"Cantidad a abastecer","stock_objetivo_1m":"Stock objetivo 1 mes","cantidad_abastecer_1m":"Cantidad a abastecer 1 mes","cobertura_post_1m":"Cobertura después 1 mes (días)","stock_objetivo_2m":"Stock objetivo 2 meses","cantidad_abastecer_2m":"Cantidad a abastecer 2 meses","cobertura_post_2m":"Cobertura después 2 meses (días)","stock_objetivo_3m":"Stock objetivo 3 meses","cantidad_abastecer_3m":"Cantidad a abastecer 3 meses","cobertura_post_3m":"Cobertura después 3 meses (días)","momento_compra":"Momento de compra","metodologia_utilizada":"Metodología utilizada","diagnostico":"Diagnóstico","prioridad":"Prioridad","recomendacion":"Recomendación"}
    cols=[c for c in rename if c in out.columns]
    st.dataframe(out[cols].rename(columns=rename),use_container_width=True,hide_index=True,height=650)

    st.subheader("🔎 Ejemplo de decisión por material")
    code=st.selectbox("Material",df.codigo.tolist())
    r=df[df.codigo==code].iloc[0]
    st.write(f"**{r.descripcion}** — {r.codigo}")
    st.write(f"**Cuándo comprar:** {r.momento_compra} | **Punto de pedido:** {r.punto_pedido:,.0f} {r.unidad or ''}")
    st.write(f"**Cuánto comprar para {horizonte} mes(es):** {r.cantidad_abastecer:,.0f} {r.unidad or ''}")
    st.write(f"**Cobertura después de recibir:** {r[f'cobertura_post_{horizonte}m']:.1f} días")
    st.info(r.recomendacion)

    st.subheader("📈 Consumo mensual")
    pm=monthly[monthly.codigo==code].sort_values("periodo_str")
    if not pm.empty: st.plotly_chart(px.line(pm,x="periodo_str",y="consumo",markers=True,title=f"Consumo: {code}"),use_container_width=True)
else:
    st.info("Carga Stock, Salidas y Órdenes de Compra y presiona CALCULAR ANÁLISIS.")
