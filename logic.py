# -*- coding: utf-8 -*-
"""
Motor profesional de abastecimiento.
Objetivo principal: determinar CUÁNTO ABASTECER por material.

Fuentes:
- Stock actual: posición actual y costo.
- Salidas: demanda histórica y comportamiento mensual.
- OC + Ingresos: lead time real y abastecimiento pendiente válido.

Reglas importantes:
- Una OC CERRADA con material PENDIENTE NO se considera abastecimiento futuro.
- Una OC abierta/pending sí puede cubrir necesidad, siempre que el saldo sea positivo.
- Se conserva el historial mensual completo, incluidos meses con cero consumo.
- Los cálculos internos conservan precisión; la presentación se formatea a 2 decimales.
"""

import io
import re
import unicodedata
import numpy as np
import pandas as pd


def norm(x):
    s = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def find_col(df, aliases, required=False, exclude=None):
    exclude = set(exclude or [])
    mp = {norm(c): c for c in df.columns if c not in exclude}
    for a in aliases:
        if norm(a) in mp:
            return mp[norm(a)]
    for a in aliases:
        na = norm(a)
        for n, c in mp.items():
            if na and (na in n or n in na):
                return c
    if required:
        raise ValueError(f"No se encontró columna requerida. Alternativas: {aliases}")
    return None


def find_state_cols(df):
    """Detecta las dos columnas de estado sin depender de nombres exactos."""
    cols = list(df.columns)
    estados = [c for c in cols if norm(c) == "estado"]
    material = find_col(df, [
        "Estado Material", "Estado Item", "Estado Ítem", "Estado del Material",
        "Estado Item OC", "Estado del Item"
    ])
    oc_state = find_col(df, [
        "Estado OC", "Estado Orden", "Estado Orden de Compra",
        "Estado Cabecera", "Estado Documento"
    ])

    # Si el ERP trae dos columnas literalmente 'Estado', usa la primera como OC
    # y la segunda como estado del material.
    if not oc_state and len(estados) >= 2:
        oc_state = estados[0]
        material = material or estados[1]
    elif not oc_state and estados:
        oc_state = estados[0]
    return oc_state, material


def read(file):
    return pd.read_excel(file)


def codes(s):
    return s.astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})


def _preserve_excel_codes(file, column_name):
    """Conserva ceros a la izquierda cuando Excel usa formato numérico 000000."""
    try:
        import openpyxl
        file.seek(0)
        wb = openpyxl.load_workbook(file, data_only=True, read_only=True)
        ws = wb.active
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        headers = [str(h).strip() if h is not None else h for h in headers]
        if column_name not in headers:
            return None
        idx = headers.index(column_name)
        result = []
        for row in ws.iter_rows(min_row=2):
            cell = row[idx]
            v = cell.value
            if v is None or v == "":
                result.append(None)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                nf = cell.number_format or ""
                m = re.search(r"0{2,}", nf)
                if m and set(nf) <= set("0#,.@ "):
                    result.append(str(int(v)).zfill(len(m.group(0))))
                elif float(v).is_integer():
                    result.append(str(int(v)))
                else:
                    result.append(str(v))
            else:
                result.append(str(v).strip())
        file.seek(0)
        return result
    except Exception:
        try:
            file.seek(0)
        except Exception:
            pass
        return None


def clean_text(s):
    s = s.astype(str).str.strip()
    return s.replace({"nan": np.nan, "None": np.nan, "": np.nan})


def load_stock(file):
    d = read(file)
    c = find_col(d, ["Código", "Codigo", "Material", "Item", "SKU"], True)
    raw = _preserve_excel_codes(file, c)
    stock = find_col(d, ["Stock Actual", "Stock", "Existencia", "Saldo", "Cantidad", "Sistema"], True)
    desc = find_col(d, ["Descripción", "Descripcion", "Nombre", "Material Descripción", "Descripcion Material"])
    fam = find_col(d, ["Familia", "Grupo", "Categoria", "Categoría", "Línea"])
    um = find_col(d, ["U.M.", "UM", "Unidad de Medida", "Unidad", "Unid"])
    ck = find_col(d, ["C. Kardex", "Costo Kardex", "Costo Unitario Kardex", "Kardex"])
    cc = find_col(d, ["Costo Cierre Mes", "Costo Cierre", "Costo Cierre Mensual"])
    tipo = find_col(d, ["Tipo", "Tipo Material", "Clase"])

    out = pd.DataFrame({
        "codigo": codes(d[c]),
        "descripcion": clean_text(d[desc]) if desc else np.nan,
        "familia": clean_text(d[fam]) if fam else np.nan,
        "unidad": clean_text(d[um]).str.upper() if um else np.nan,
        "stock_actual": pd.to_numeric(d[stock], errors="coerce"),
        "costo_kardex": pd.to_numeric(d[ck], errors="coerce") if ck else 0.0,
        "costo_cierre": pd.to_numeric(d[cc], errors="coerce") if cc else 0.0,
        "tipo": clean_text(d[tipo]) if tipo else np.nan,
    })
    if raw and len(raw) == len(out):
        out["codigo"] = pd.Series(raw, index=out.index)

    # Si ambos costos existen, usa el mayor; si solo uno existe, usa ese.
    k = out["costo_kardex"].fillna(0)
    c2 = out["costo_cierre"].fillna(0)
    out["costo_unitario"] = np.where(
        (k > 0) & (c2 > 0), np.maximum(k, c2),
        np.where(k > 0, k, np.where(c2 > 0, c2, np.nan))
    )
    out["tipo_costo"] = np.where(
        out["costo_unitario"].notna(), "VALORIZABLE",
        "SIN COSTO / POSIBLE CONSIGNACIÓN"
    )
    return out.drop_duplicates("codigo", keep="last")


def load_salidas(file):
    d = read(file)
    c = find_col(d, ["Código", "Codigo", "Material", "Item", "SKU"], True)
    raw = _preserve_excel_codes(file, c)
    f = find_col(d, ["Fecha", "Fecha Salida", "Fecha de Salida", "Fecha Movimiento"], True)
    q = find_col(d, ["Cantidad Salida", "Cantidad de Salida", "Salida", "Consumo", "Unidades", "Cantidad"], True)
    desc = find_col(d, ["Descripción", "Descripcion", "Nombre", "Descripcion Material"])
    fam = find_col(d, ["Familia", "Grupo", "Categoria", "Categoría"])
    um = find_col(d, ["U.M.", "UM", "Unidad", "Unidad de Medida"])
    out = pd.DataFrame({
        "codigo": codes(d[c]),
        "descripcion": clean_text(d[desc]) if desc else np.nan,
        "familia": clean_text(d[fam]) if fam else np.nan,
        "unidad": clean_text(d[um]).str.upper() if um else np.nan,
        "fecha": pd.to_datetime(d[f], errors="coerce", dayfirst=True),
        "cantidad": pd.to_numeric(d[q], errors="coerce")
    })
    if raw and len(raw) == len(out):
        out["codigo"] = pd.Series(raw, index=out.index)
    return out


def load_oc(file):
    d = read(file)
    pe = find_col(d, ["P. Emis", "P Emis", "P.Emis"], True)
    no = find_col(d, ["Número", "Numero", "N°", "Nro", "Nro OC"], True)
    mat = find_col(d, ["Material", "Código", "Codigo", "Item", "SKU"], True)
    fecha = find_col(d, ["Fecha Creación", "Fecha Creacion", "Fecha OC", "Fecha Emisión", "Fecha Emision"])
    prov = find_col(d, ["Razón Social", "Razon Social", "Proveedor", "Nombre Proveedor"])
    qty = find_col(d, ["Unidades", "Cantidad", "Cantidad OC", "Qty"])
    saldo = find_col(d, ["Saldo", "Saldo Item", "Cantidad Pendiente", "Saldo Pendiente"])
    precio = find_col(d, ["Precio", "Valor Unitario", "Costo", "Precio Unitario"])
    estado_oc, estado_mat = find_state_cols(d)

    out = pd.DataFrame({
        "oc_tipo": codes(d[pe]),
        "numero_oc": codes(d[no]),
        "oc_id": codes(d[pe]) + "-" + codes(d[no]),
        "codigo": codes(d[mat]),
        "fecha_oc": pd.to_datetime(d[fecha], errors="coerce", dayfirst=True) if fecha else pd.NaT,
        "proveedor": clean_text(d[prov]) if prov else np.nan,
        "cantidad_oc": pd.to_numeric(d[qty], errors="coerce") if qty else np.nan,
        "saldo_oc": pd.to_numeric(d[saldo], errors="coerce") if saldo else np.nan,
        "precio_oc": pd.to_numeric(d[precio], errors="coerce") if precio else np.nan,
        "estado_oc": clean_text(d[estado_oc]) if estado_oc else np.nan,
        "estado_material": clean_text(d[estado_mat]) if estado_mat else np.nan,
    })
    return out


def load_ingresos(file):
    d = read(file)
    pe = find_col(d, ["P. Emis", "P Emis", "P.Emis"], True)
    no = find_col(d, ["Número", "Numero", "N°", "Nro"], True)
    po = find_col(d, ["P.OC", "P OC", "P. O.C."], True)
    noc = find_col(d, ["Número OC", "Numero OC", "N OC", "Nro OC"], True)
    mat = find_col(d, ["Material", "Código", "Codigo", "Item", "SKU"], True)
    fi = find_col(d, ["F.Contab", "F Contab", "Fecha Contable", "Fecha Ingreso", "Fecha de Ingreso"])
    qty = find_col(d, ["Unidades", "Cantidad", "Cantidad Ingresada", "Qty"])
    prov = find_col(d, ["Razón Social", "Razon Social", "Proveedor"])
    out = pd.DataFrame({
        "ingreso_id": codes(d[pe]) + "-" + codes(d[no]),
        "oc_tipo": codes(d[po]), "numero_oc": codes(d[noc]),
        "oc_id": codes(d[po]) + "-" + codes(d[noc]),
        "codigo": codes(d[mat]),
        "fecha_ingreso": pd.to_datetime(d[fi], errors="coerce", dayfirst=True) if fi else pd.NaT,
        "cantidad_ingresada": pd.to_numeric(d[qty], errors="coerce") if qty else 0.0,
        "proveedor": clean_text(d[prov]) if prov else np.nan,
    })
    return out


def build_monthly_consumption(salidas):
    d = salidas.dropna(subset=["codigo", "fecha", "cantidad"]).copy()
    d = d[d["cantidad"] >= 0]
    if d.empty:
        return pd.DataFrame(columns=["codigo", "periodo", "periodo_str", "consumo"])
    d["periodo"] = d["fecha"].dt.to_period("M")
    m = d.groupby(["codigo", "periodo"], as_index=False)["cantidad"].sum().rename(columns={"cantidad": "consumo"})
    m["periodo_str"] = m["periodo"].astype(str)
    return m


def demand_metrics(salidas):
    d = salidas.dropna(subset=["codigo", "fecha", "cantidad"]).copy()
    d = d[d["cantidad"] >= 0]
    if d.empty:
        return pd.DataFrame()

    all_periods = pd.period_range(d["fecha"].min().to_period("M"), d["fecha"].max().to_period("M"), freq="M")
    monthly = build_monthly_consumption(d)
    pivot = monthly.pivot_table(index="codigo", columns="periodo", values="consumo", aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(columns=all_periods, fill_value=0)

    rows = []
    for codigo, serie in pivot.iterrows():
        vals = serie.astype(float).values
        total = float(vals.sum())
        meses = len(vals)
        mean = float(vals.mean()) if meses else 0.0
        mediana = float(np.median(vals)) if meses else 0.0
        std = float(vals.std(ddof=0)) if meses else 0.0
        cv = std / mean if mean > 0 else np.nan
        positivos = vals[vals > 0]
        meses_con = int((vals > 0).sum())
        meses_sin = int((vals == 0).sum())
        ultimos3 = float(vals[-min(3, meses):].mean()) if meses else 0.0
        ultimos6 = float(vals[-min(6, meses):].mean()) if meses else 0.0
        reciente = ultimos3

        if meses >= 2:
            mitad = max(meses // 2, 1)
            a, b = float(vals[:mitad].mean()), float(vals[mitad:].mean())
            variacion = ((b-a)/a*100) if a > 0 else (100.0 if b > 0 else 0.0)
        else:
            variacion = 0.0
        tendencia = "CRECIENTE" if variacion > 10 else ("DECRECIENTE" if variacion < -10 else "ESTABLE")

        if total > 0:
            # Demanda intermitente si muchos meses son cero.
            intermitente = meses_sin / meses >= 0.40
        else:
            intermitente = True

        rows.append({
            "codigo": codigo,
            "consumo_total": total,
            "cantidad_salidas": int((d["codigo"] == codigo).sum()),
            "meses_analizados": meses,
            "meses_con_consumo": meses_con,
            "meses_sin_consumo": meses_sin,
            "consumo_mensual": mean,
            "consumo_mediano_mensual": mediana,
            "consumo_ultimos_3_meses": ultimos3,
            "consumo_ultimos_6_meses": ultimos6,
            "consumo_diario": total / max((d["fecha"].max()-d["fecha"].min()).days + 1, 1),
            "cv": cv,
            "variabilidad": "INTERMITENTE" if intermitente else ("ALTA" if cv > 1 else ("MEDIA" if cv > .5 else "BAJA")),
            "tendencia": tendencia,
            "variacion_tendencia_pct": variacion,
            "mes_mayor_consumo": str(serie.idxmax()) if total > 0 else None,
            "consumo_mes_mayor": float(serie.max()) if total > 0 else 0.0,
            "ultima_salida": d.loc[d["codigo"] == codigo, "fecha"].max(),
            "primera_salida": d.loc[d["codigo"] == codigo, "fecha"].min(),
        })
    return pd.DataFrame(rows)


def build_oc_tracking(oc, ing):
    o = oc.groupby(["oc_id", "codigo"], dropna=False).agg(
        fecha_oc=("fecha_oc", "min"),
        proveedor=("proveedor", "first"),
        cantidad_oc=("cantidad_oc", "sum"),
        saldo_reportado=("saldo_oc", "sum"),
        estado_oc=("estado_oc", "last"),
        estado_material=("estado_material", "last")
    ).reset_index()

    i = ing.groupby(["oc_id", "codigo"], dropna=False).agg(
        primera_recepcion=("fecha_ingreso", "min"),
        ultima_recepcion=("fecha_ingreso", "max"),
        cantidad_ingresada=("cantidad_ingresada", "sum"),
        numero_ingresos=("ingreso_id", "nunique")
    ).reset_index()

    t = o.merge(i, on=["oc_id", "codigo"], how="left")
    t["cantidad_ingresada"] = t["cantidad_ingresada"].fillna(0)
    t["pendiente_calculado"] = (t["cantidad_oc"].fillna(0) - t["cantidad_ingresada"]).clip(lower=0)

    t["lead_time_primera_recepcion_dias"] = (t["primera_recepcion"] - t["fecha_oc"]).dt.total_seconds()/86400
    t["lead_time_completo_dias"] = (t["ultima_recepcion"] - t["fecha_oc"]).dt.total_seconds()/86400
    t["entrega_parcial"] = (t["cantidad_ingresada"] > 0) & (t["cantidad_ingresada"] < t["cantidad_oc"])

    def is_closed(x):
        s = norm(x)
        return any(k in s for k in ["cerrada", "cerrado", "cancelada", "cancelado", "anulada", "anulado"])

    t["oc_cerrada"] = t["estado_oc"].map(is_closed)
    # Regla explícita: OC cerrada + pendiente no es abastecimiento futuro.
    t["pendiente_valido"] = np.where(
        (~t["oc_cerrada"]) & (t["pendiente_calculado"] > 0),
        t["pendiente_calculado"], 0.0
    )
    t["oc_vigente"] = t["pendiente_valido"] > 0
    return t


def _lead_time_por_material(tracking):
    valid = tracking.dropna(subset=["codigo", "lead_time_primera_recepcion_dias"]).copy()
    valid = valid[valid["lead_time_primera_recepcion_dias"] >= 0]
    if valid.empty:
        return pd.DataFrame(columns=["codigo", "lead_time_mediano", "lead_time_promedio", "lead_time_minimo", "lead_time_maximo", "oc_con_lead_time"])
    return valid.groupby("codigo").agg(
        lead_time_mediano=("lead_time_primera_recepcion_dias", "median"),
        lead_time_promedio=("lead_time_primera_recepcion_dias", "mean"),
        lead_time_minimo=("lead_time_primera_recepcion_dias", "min"),
        lead_time_maximo=("lead_time_primera_recepcion_dias", "max"),
        oc_con_lead_time=("lead_time_primera_recepcion_dias", "count")
    ).reset_index()


def build_analysis(stock, salidas, oc, ingresos, periodo_revision_dias=30, factor_seguridad=0.50):
    dm = demand_metrics(salidas)
    tr = build_oc_tracking(oc, ingresos)
    lt = _lead_time_por_material(tr)
    pend = tr.groupby("codigo", as_index=False).agg(
        oc_pendiente_valido=("pendiente_valido", "sum"),
        cantidad_oc_vigentes=("oc_vigente", "sum"),
        ultima_oc_vigente=("fecha_oc", "max")
    )

    # Enriquecimiento de descripción/familia/UM desde salidas si Stock no trae esos datos.
    attrs = salidas.dropna(subset=["codigo"]).sort_values("fecha").drop_duplicates("codigo", keep="last")
    attrs = attrs[["codigo", "descripcion", "familia", "unidad"]]

    out = stock.merge(attrs, on="codigo", how="left", suffixes=("", "_salidas"))
    for col in ["descripcion", "familia", "unidad"]:
        out[col] = out[col].fillna(out[f"{col}_salidas"])
        out.drop(columns=[f"{col}_salidas"], inplace=True)

    out = out.merge(dm, on="codigo", how="left").merge(lt, on="codigo", how="left").merge(pend, on="codigo", how="left")

    numeric_zero = [
        "consumo_total","cantidad_salidas","meses_analizados","meses_con_consumo","meses_sin_consumo",
        "consumo_mensual","consumo_mediano_mensual","consumo_ultimos_3_meses","consumo_ultimos_6_meses",
        "consumo_diario","oc_pendiente_valido","cantidad_oc_vigentes"
    ]
    for c in numeric_zero:
        out[c] = out[c].fillna(0)

    out["variabilidad"] = out["variabilidad"].fillna("SIN DATOS")
    out["tendencia"] = out["tendencia"].fillna("SIN DATOS")

    # Demanda de referencia: pondera histórico reciente sin borrar el histórico.
    out["demanda_referencia_mensual"] = np.where(
        out["meses_analizados"] >= 6,
        0.50*out["consumo_ultimos_3_meses"] + 0.30*out["consumo_ultimos_6_meses"] + 0.20*out["consumo_mensual"],
        out["consumo_mensual"]
    )
    # Para demanda intermitente, la mediana ayuda a no sobrerreaccionar a picos aislados.
    out["demanda_referencia_mensual"] = np.where(
        out["variabilidad"].eq("INTERMITENTE") & (out["consumo_mediano_mensual"] > 0),
        0.50*out["consumo_mensual"] + 0.50*out["consumo_mediano_mensual"],
        out["demanda_referencia_mensual"]
    )
    out["demanda_referencia_diaria"] = out["demanda_referencia_mensual"] / 30.44

    # Seguridad proporcional a variabilidad observada. Si no hay suficiente historial, no inventa variabilidad.
    cv = out["cv"].fillna(0).clip(lower=0)
    out["stock_seguridad"] = np.where(
        out["consumo_mensual"] > 0,
        out["demanda_referencia_diaria"] * out["lead_time_mediano"].fillna(0) * (1 + factor_seguridad*cv),
        0.0
    )
    lt_days = out["lead_time_mediano"].fillna(0).clip(lower=0)
    out["punto_pedido"] = out["demanda_referencia_diaria"] * lt_days + out["stock_seguridad"]
    out["stock_objetivo"] = out["demanda_referencia_diaria"] * (lt_days + periodo_revision_dias) + out["stock_seguridad"]

    out["valor_inventario"] = np.where(out["costo_unitario"].notna(), out["stock_actual"].fillna(0)*out["costo_unitario"], np.nan)
    out["valor_consumo_mensual"] = np.where(out["costo_unitario"].notna(), out["demanda_referencia_mensual"]*out["costo_unitario"], np.nan)

    out["cobertura_dias"] = np.where(
        out["demanda_referencia_diaria"] > 0,
        out["stock_actual"] / out["demanda_referencia_diaria"], np.inf
    )
    out["dias_sin_movimiento"] = np.where(
        out["ultima_salida"].notna(),
        (pd.Timestamp.today().normalize() - pd.to_datetime(out["ultima_salida"]).dt.normalize()).dt.days,
        np.nan
    )

    # Posición disponible = stock actual + OC que realmente siguen vigentes.
    out["posicion_con_oc"] = out["stock_actual"].fillna(0) + out["oc_pendiente_valido"].fillna(0)
    out["necesidad_bruta"] = (out["stock_objetivo"] - out["stock_actual"].fillna(0)).clip(lower=0)
    out["cantidad_abastecer"] = (out["stock_objetivo"] - out["posicion_con_oc"]).clip(lower=0)

    out["situacion"] = "NORMAL"
    out.loc[(out["stock_actual"] <= 0) & (out["consumo_total"] > 0) & (out["oc_pendiente_valido"] <= 0), "situacion"] = "QUIEBRE / SIN STOCK"
    out.loc[(out["consumo_total"] > 0) & (out["stock_actual"] < out["punto_pedido"]) & (out["oc_pendiente_valido"] <= 0), "situacion"] = "ABASTECER"
    out.loc[(out["consumo_total"] > 0) & (out["stock_actual"] < out["punto_pedido"]) & (out["oc_pendiente_valido"] > 0), "situacion"] = "OC EN CAMINO / REVISAR"
    out.loc[(out["consumo_total"] <= 0) & (out["stock_actual"] > 0), "situacion"] = "SIN MOVIMIENTO"
    out.loc[(out["consumo_total"] > 0) & (out["cobertura_dias"] > 365), "situacion"] = "COBERTURA ALTA"
    out.loc[(out["cantidad_abastecer"] > 0) & (out["situacion"] == "NORMAL"), "situacion"] = "PLANIFICAR ABASTECIMIENTO"

    out["riesgo"] = "BAJO"
    out.loc[out["situacion"].eq("QUIEBRE / SIN STOCK"), "riesgo"] = "ALTO"
    out.loc[out["situacion"].isin(["ABASTECER", "OC EN CAMINO / REVISAR"]), "riesgo"] = "MEDIO"

    # Si no hay LT histórico suficiente, la recomendación se marca como condicionada.
    out["calidad_lead_time"] = np.select(
        [out["oc_con_lead_time"].fillna(0) >= 5, out["oc_con_lead_time"].fillna(0) >= 2, out["oc_con_lead_time"].fillna(0) == 1],
        ["ALTA", "MEDIA", "BAJA"], default="NO CALCULABLE"
    )

    out["prioridad"] = 4
    out.loc[out["situacion"].eq("QUIEBRE / SIN STOCK"), "prioridad"] = 1
    out.loc[out["situacion"].eq("ABASTECER"), "prioridad"] = 2
    out.loc[out["situacion"].eq("OC EN CAMINO / REVISAR"), "prioridad"] = 3

    out["explicacion"] = "No requiere abastecimiento inmediato."
    out.loc[out["situacion"].eq("QUIEBRE / SIN STOCK"), "explicacion"] = "No hay stock y existe consumo histórico; no existe OC vigente suficiente."
    out.loc[out["situacion"].eq("ABASTECER"), "explicacion"] = "El stock está por debajo del punto de pedido y no existe abastecimiento vigente suficiente."
    out.loc[out["situacion"].eq("OC EN CAMINO / REVISAR"), "explicacion"] = "El stock está bajo, pero existe una OC vigente pendiente; no duplicar la compra sin revisar su fecha."
    out.loc[out["situacion"].eq("SIN MOVIMIENTO"), "explicacion"] = "Existe stock, pero no se registró consumo durante el periodo histórico analizado."
    out.loc[out["situacion"].eq("COBERTURA ALTA"), "explicacion"] = "La cobertura supera 365 días; revisar antes de generar nuevas compras."
    out.loc[out["situacion"].eq("PLANIFICAR ABASTECIMIENTO"), "explicacion"] = "El modelo identifica una necesidad futura de reposición."

    out["explicacion"] += np.where(
        out["calidad_lead_time"].eq("NO CALCULABLE"),
        " Lead Time no calculable por falta de recepciones históricas válidas.",
        ""
    )
    return out


def quality_report(stock, salidas, oc, ingresos, tracking):
    q = {
        "Materiales en stock": int(stock.codigo.nunique()),
        "Materiales con salidas": int(salidas.codigo.nunique()),
        "Materiales con OC": int(oc.codigo.nunique()),
        "Materiales con ingresos": int(ingresos.codigo.nunique()),
        "OC analizadas": int(tracking.oc_id.nunique()),
        "OC con Lead Time": int(tracking["lead_time_primera_recepcion_dias"].notna().sum()),
        "OC vigentes con pendiente": int(tracking["oc_vigente"].sum()),
        "Pendiente excluido por OC cerrada": float(tracking.loc[tracking["oc_cerrada"], "pendiente_calculado"].sum()),
        "Entregas parciales": int(tracking["entrega_parcial"].sum()),
        "Materiales sin descripción en Stock": int(stock["descripcion"].isna().sum()),
        "Materiales sin costo valorizable": int(stock["costo_unitario"].isna().sum()),
    }
    return q


def format_excel(df, decimals=2):
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].round(decimals)
    return out


def export_results(analysis, monthly, tracking, quality):
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter

    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        cols = [
            "codigo","descripcion","familia","unidad","stock_actual","costo_unitario","valor_inventario",
            "consumo_total","cantidad_salidas","meses_con_consumo","meses_sin_consumo","ultima_salida",
            "dias_sin_movimiento","demanda_referencia_mensual","lead_time_mediano","oc_pendiente_valido",
            "cobertura_dias","stock_seguridad","punto_pedido","stock_objetivo","cantidad_abastecer",
            "situacion","riesgo","prioridad","calidad_lead_time","explicacion"
        ]
        a = format_excel(analysis[[c for c in cols if c in analysis.columns]])
        a.to_excel(writer, sheet_name="Abastecimiento", index=False)

        m = monthly.copy()
        if not m.empty:
            p = m.pivot_table(index="codigo", columns="periodo_str", values="consumo", aggfunc="sum", fill_value=0).reset_index()
            format_excel(p).to_excel(writer, sheet_name="Consumo Mensual", index=False)

        format_excel(tracking).to_excel(writer, sheet_name="OC e Ingresos", index=False)
        pd.DataFrame({"Indicador": list(quality.keys()), "Valor": list(quality.values())}).to_excel(writer, sheet_name="Calidad", index=False)

        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            for col in ws.columns:
                width = min(max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 45)
                ws.column_dimensions[get_column_letter(col[0].column)].width = max(width, 10)
    bio.seek(0)
    return bio.getvalue()
