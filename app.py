# -*- coding: utf-8 -*-
import io
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st

from logic import (
    load_stock_file, load_salidas_file, load_oc_file,
    compute_analysis, build_export_excel, validate_data
)

st.set_page_config(page_title="Control de Inventarios y Abastecimiento", page_icon="📦", layout="wide")
st.title("📦 Control de Inventarios y Abastecimiento")
st.caption("Análisis integrado de Stock, Salidas y Órdenes de Compra.")

st.sidebar.header("⚙️ Parámetros")
z = st.sidebar.number_input("Factor Z de seguridad", min_value=0.0, value=1.65, step=0.05)
dias_objetivo = st.sidebar.number_input("Días de cobertura objetivo", min_value=1, value=90, step=1)

c1, c2, c3 = st.columns(3)
with c1:
    f_stock = st.file_uploader("1️⃣ Stock Actual", type=["xlsx", "xls"], key="stock")
with c2:
    f_sal = st.file_uploader("2️⃣ Salidas Históricas", type=["xlsx", "xls"], key="sal")
with c3:
    f_oc = st.file_uploader("3️⃣ Órdenes de Compra", type=["xlsx", "xls"], key="oc")

if st.button("🚀 CALCULAR ABASTECIMIENTO", type="primary", use_container_width=True):
    if not f_stock or not f_sal:
        st.error("Debes cargar Stock Actual y Salidas Históricas.")
    else:
        try:
            stock = load_stock_file(f_stock)
            sal = load_salidas_file(f_sal)
            oc = load_oc_file(f_oc) if f_oc else pd.DataFrame()
            issues = validate_data(stock, sal, oc)
            result, monthly, periods = compute_analysis(
                stock, sal, oc, z=z, dias_objetivo=dias_objetivo
            )
            st.session_state["result"] = result
            st.session_state["monthly"] = monthly
            st.session_state["oc"] = oc
            st.session_state["issues"] = issues
            st.session_state["params"] = {
                "z": z, "dias_objetivo": dias_objetivo, "oc": oc
            }
            st.success("Análisis calculado correctamente.")
        except Exception as e:
            st.exception(e)

result = st.session_state.get("result")
if result is not None:
    monthly = st.session_state["monthly"]
    oc = st.session_state["oc"]
    issues = st.session_state["issues"]
    params = st.session_state["params"]

    st.subheader("📊 Resumen")
    a,b,c,d,e = st.columns(5)
    a.metric("Materiales analizados", f"{len(result):,}")
    b.metric("Con rotura de stock", f"{(result['Rotura de stock']=='VERDADERO').sum():,}")
    c.metric("Consumo histórico", f"{result['Consumo total'].sum():,.0f}")
    d.metric("Compra 1 mes", f"{result['Compra para 1 mes'].sum():,.0f}")
    e.metric("Prioridad crítica", f"{(result['Prioridad']=='CRÍTICO').sum():,}")

    st.subheader("🔎 Filtros")
    f1,f2,f3,f4 = st.columns(4)
    texto = f1.text_input("Código o descripción")
    familias = f2.multiselect("Familia", sorted(result["Familia"].dropna().astype(str).unique()))
    situ = f3.multiselect("Situación", sorted(result["Situación de stock"].unique()))
    rot = f4.multiselect("Rotura de stock", ["VERDADERO","FALSO"])

    view = result.copy()
    if texto:
        q = texto.lower()
        view = view[
            view["Código"].str.lower().str.contains(q, na=False)
            | view["Descripción"].fillna("").str.lower().str.contains(q, na=False)
        ]
    if familias:
        view = view[view["Familia"].isin(familias)]
    if situ:
        view = view[view["Situación de stock"].isin(situ)]
    if rot:
        view = view[view["Rotura de stock"].isin(rot)]

    st.subheader("📑 Tabla Principal")
    st.dataframe(view, use_container_width=True, hide_index=True, height=650)

    st.subheader("📌 Material seleccionado")
    if not view.empty:
        codigo = st.selectbox("Selecciona un material", view["Código"].tolist())
        p = view[view["Código"] == codigo].iloc[0]
        datos = [
            ("Código", p["Código"]),
            ("Descripción", p["Descripción"]),
            ("Stock actual", p["Stock actual"]),
            ("Consumo total", p["Consumo total"]),
            ("Meses con consumo", p["Meses con consumo"]),
            ("Consumo mensual promedio", p["Consumo mensual promedio"]),
            ("Consumo diario", p["Consumo diario"]),
            ("Última salida", p["Última salida"]),
            ("Días sin movimiento", p["Días sin movimiento"]),
            ("Cobertura actual (días)", p["Cobertura (días)"]),
            ("Lead Time (días)", p["Lead Time (días)"]),
            ("Última compra", p["Última compra"]),
            ("Fecha última compra", p["Fecha última compra"]),
            ("Stock de seguridad", p["Stock de seguridad"]),
            ("Punto de pedido", p["Punto de pedido"]),
            ("Comprar 1 mes", p["Compra para 1 mes"]),
            ("Duración 1 mes (días)", p["Duración después de comprar 1 mes (días)"]),
            ("Comprar 2 meses", p["Compra para 2 meses"]),
            ("Duración 2 meses (días)", p["Duración después de comprar 2 meses (días)"]),
            ("Comprar 3 meses", p["Compra para 3 meses"]),
            ("Duración 3 meses (días)", p["Duración después de comprar 3 meses (días)"]),
            ("Cuándo comprar", p["Cuándo comprar"]),
            ("Situación", p["Situación de stock"]),
            ("Rotura de stock", p["Rotura de stock"]),
            ("Prioridad", p["Prioridad"]),
            ("Recomendación", p["Recomendación"]),
        ]
        st.dataframe(pd.DataFrame(datos, columns=["Indicador","Resultado"]), use_container_width=True, hide_index=True)

    st.subheader("⬇️ Descargar")
    if st.button("Generar Excel completo"):
        path = "/tmp/resultado_abastecimiento.xlsx"
        build_export_excel(result, monthly, issues, params, path)
        with open(path, "rb") as fh:
            data = fh.read()
        st.download_button(
            "📥 Descargar Excel",
            data=data,
            file_name=f"resultado_abastecimiento_{datetime.now():%Y%m%d_%H%M}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
