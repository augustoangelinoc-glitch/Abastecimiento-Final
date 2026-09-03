
import streamlit as st
import pandas as pd
from logic import load_stock, load_salidas, load_oc, analyze, to_excel

st.set_page_config(page_title="ABASTECIMIENTO", layout="wide")
st.title("ABASTECIMIENTO – Análisis de inventario")

st.info(
    "Mapeo fijo: Stock → Codigo, Descripción, U.Medida, Sistema, Familia, Costo Cierre Mes | "
    "Salidas → fecha H y cantidad AX | OC → F. Docum., Fecha Guia, Estado Item."
)

c1, c2, c3 = st.columns(3)
with c1:
    f_stock = st.file_uploader("1. Archivo STOCK", type=["xlsx", "xls"], key="stock_file")
with c2:
    f_sal = st.file_uploader("2. Archivo SALIDAS", type=["xlsx", "xls"], key="sal_file")
with c3:
    f_oc = st.file_uploader("3. Archivo ÓRDENES DE COMPRA", type=["xlsx", "xls"], key="oc_file")

a, b = st.columns(2)
with a:
    horizonte = st.number_input("Horizonte de abastecimiento (meses)", min_value=1, max_value=12, value=3)
with b:
    z = st.number_input("Factor de seguridad Z", min_value=0.0, max_value=3.0, value=1.65, step=0.05)

if f_stock and f_sal and f_oc:
    try:
        stock = load_stock(f_stock)
        sal = load_salidas(f_sal)
        oc = load_oc(f_oc)

        df, periods = analyze(stock, sal, oc, horizon_months=horizonte, z=z)

        st.success(f"Análisis generado: {len(df):,} materiales.")
        st.dataframe(df, use_container_width=True, height=650)

        xlsx = to_excel(df)
        st.download_button(
            "⬇️ Descargar análisis en Excel",
            data=xlsx,
            file_name="Analisis_Abastecimiento.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_analysis",
        )

    except Exception as e:
        st.error("No se pudo procesar uno de los archivos.")
        st.exception(e)
else:
    st.warning("Carga los 3 archivos para ejecutar el análisis.")
