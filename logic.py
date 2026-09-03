
import re
import unicodedata
import numpy as np
import pandas as pd

def norm(x):
    s = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def find_col(df, candidates):
    """
    Encuentra una única columna. Excel puede traer encabezados repetidos;
    en ese caso pandas devuelve un DataFrame si se accede por nombre.
    Aquí trabajamos siempre por posición para garantizar una Series 1-D.
    """
    names = [norm(c) for c in df.columns]
    cand = [norm(c) for c in candidates]

    # 1) Coincidencia exacta: tomar la primera aparición.
    for c in cand:
        for i, n in enumerate(names):
            if n == c:
                return i

    # 2) Coincidencia parcial, también por posición.
    for c in cand:
        if not c:
            continue
        for i, n in enumerate(names):
            if c in n or n in c:
                return i
    return None

def col_series(df, selector):
    """Devuelve siempre una Series, incluso con encabezados duplicados."""
    if selector is None:
        return None
    if isinstance(selector, int):
        return df.iloc[:, selector]
    x = df[selector]
    if isinstance(x, pd.DataFrame):
        return x.iloc[:, 0]
    return x

def read_excel(file):
    file.seek(0)
    df = pd.read_excel(file)
    raw = [str(c).strip() for c in df.columns]
    seen = {}
    cols = []
    for c in raw:
        n = seen.get(c, 0)
        cols.append(c if n == 0 else f"{c}__dup{n}")
        seen[c] = n + 1
    df.columns = cols
    return df

def read_excel_preserve_codes(file, sheet=0):
    """
    Lee Excel con openpyxl para conservar códigos con ceros iniciales
    cuando el archivo los guarda como texto o mediante formato numérico.
    """
    import openpyxl
    file.seek(0)
    wb = openpyxl.load_workbook(file, data_only=True, read_only=True)
    ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
    rows = list(ws.iter_rows(values_only=False))
    if not rows:
        return pd.DataFrame()
    raw_headers = [str(c.value).strip() if c.value is not None else "" for c in rows[0]]
    seen_headers = {}
    headers = []
    for h in raw_headers:
        n = seen_headers.get(h, 0)
        headers.append(h if n == 0 else f"{h}__dup{n}")
        seen_headers[h] = n + 1
    data = []
    for row in rows[1:]:
        vals = []
        for c in row:
            v = c.value
            if v is None:
                vals.append(None)
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                fmt = c.number_format or ""
                m = re.search(r"0{2,}", fmt)
                if m and float(v).is_integer():
                    vals.append(str(int(v)).zfill(len(m.group(0))))
                elif isinstance(v, float) and v.is_integer():
                    vals.append(str(int(v)))
                else:
                    vals.append(str(v))
            else:
                vals.append(str(v).strip())
        data.append(vals)
    return pd.DataFrame(data, columns=headers)

def load_stock(file):
    d = read_excel_preserve_codes(file)
    code = find_col(d, ["Código", "Codigo", "Material", "Cod. Material", "Item", "SKU"])
    stock = find_col(d, ["Stock actual", "Stock Actual", "Stock", "Existencia", "Saldo"])
    cost = find_col(d, ["Costo unitario", "Costo Unitario", "Costo", "Coste", "Precio unitario"])

    # Estructura conocida del archivo: stock actual columna D, costo columna T.
    if stock is None and len(d.columns) >= 4:
        stock = d.columns[3]
    if cost is None and len(d.columns) >= 20:
        cost = d.columns[19]
    if code is None:
        raise ValueError("No se encontró el código/material en Stock.")

    out = pd.DataFrame()
    out["codigo"] = col_series(d, code).astype(str).str.strip()
    out["stock_actual"] = pd.to_numeric(col_series(d, stock), errors="coerce").fillna(0)
    out["costo_unitario"] = pd.to_numeric(col_series(d, cost), errors="coerce").fillna(0)

    desc = find_col(d, ["Descripción", "Descripcion"])
    unidad = find_col(d, ["Unidad de medida", "Unidad", "U.M."])
    familia = find_col(d, ["Familia"])
    out["descripcion"] = col_series(d, desc).astype(str) if desc else ""
    out["unidad"] = col_series(d, unidad).astype(str) if unidad else ""
    out["familia"] = col_series(d, familia).astype(str) if familia else ""
    return out.drop_duplicates("codigo")

def load_salidas(file):
    d = read_excel_preserve_codes(file)
    code = find_col(d, ["Código", "Codigo", "Material", "Cod. Material", "Item", "SKU"])
    fecha = find_col(d, ["Fecha", "Fecha Salida", "Fecha de salida", "F. Fecha"])
    cantidad = find_col(d, ["Cantidad", "Cantidad salida", "Cantidad de salida", "Salida", "Consumo", "Qty"])
    valor = find_col(d, ["Valor salida", "Valor de salida", "Importe", "Monto"])
    # Archivo conocido: Fecha en H.
    if fecha is None and len(d.columns) >= 8:
        fecha = d.columns[7]
    if code is None or cantidad is None:
        raise ValueError("No se encontraron Código/Material y Cantidad en Salidas.")

    out = pd.DataFrame()
    out["codigo"] = col_series(d, code).astype(str).str.strip()
    out["fecha"] = pd.to_datetime(col_series(d, fecha), errors="coerce", dayfirst=True)
    out["cantidad"] = pd.to_numeric(col_series(d, cantidad), errors="coerce").fillna(0)
    out["valor_salida"] = pd.to_numeric(col_series(d, valor), errors="coerce") if valor else np.nan

    desc = find_col(d, ["Descripción", "Descripcion"])
    unidad = find_col(d, ["Unidad de medida", "Unidad", "U.M."])
    familia = find_col(d, ["Familia"])
    out["descripcion"] = col_series(d, desc).astype(str) if desc else ""
    out["unidad"] = col_series(d, unidad).astype(str) if unidad else ""
    out["familia"] = col_series(d, familia).astype(str) if familia else ""
    return out.dropna(subset=["fecha"])

def load_oc(file):
    d = read_excel_preserve_codes(file)
    code = find_col(d, ["Material", "Código", "Codigo", "Cod. Material", "Item"])
    fdoc = find_col(d, ["F. Docum.", "F Docum", "Fecha documento", "Fecha Docum", "Fecha OC"])
    fguia = find_col(d, ["Fecha Guia", "Fecha Guía", "Fecha recepción", "Fecha recepcion", "Fecha de recepción"])
    estado = find_col(d, ["Estado Item", "Estado Ítem", "Estado"])
    if not code or not fdoc or not fguia:
        raise ValueError("Órdenes de Compra debe contener Material, F. Docum. y Fecha Guía.")
    out = pd.DataFrame()
    out["codigo"] = col_series(d, code).astype(str).str.strip()
    out["f_docum"] = pd.to_datetime(d[fdoc], errors="coerce", dayfirst=True)
    out["fecha_guia"] = pd.to_datetime(d[fguia], errors="coerce", dayfirst=True)
    out["estado_item"] = col_series(d, estado).astype(str).str.upper().str.strip() if estado else "COMPRADO"
    return out

def analyze(stock, salidas, oc, z=1.65):
    # PERIODO = exclusivamente las fechas reales de SALIDAS.
    s = salidas.copy()
    s = s[(s["fecha"].notna()) & (s["cantidad"] >= 0)].copy()
    if s.empty:
        raise ValueError("No existen salidas válidas para analizar.")

    periodos = pd.period_range(s["fecha"].min().to_period("M"),
                               s["fecha"].max().to_period("M"), freq="M")
    s["periodo"] = s["fecha"].dt.to_period("M")

    # Universo = Stock UNION Salidas. Así aparecen los materiales con stock 0.
    universo = pd.DataFrame({"codigo": sorted(set(stock.codigo.astype(str)) |
                                               set(s.codigo.astype(str)))})

    d = universo.merge(stock, on="codigo", how="left")
    ultimo = s.sort_values("fecha").groupby("codigo").agg(
        descripcion=("descripcion", "last"),
        unidad=("unidad", "last"),
        familia=("familia", "last"),
        ultimo_movimiento=("fecha", "max")
    ).reset_index()
    d = d.merge(ultimo, on="codigo", how="left", suffixes=("", "_sal"))
    for c in ["descripcion", "unidad", "familia"]:
        d[c] = d[c].replace(["nan", "None"], np.nan)
        d[c] = d[c].fillna(d[c + "_sal"])
        d.drop(columns=[c + "_sal"], inplace=True)
    d["stock_actual"] = d["stock_actual"].fillna(0)
    d["costo_unitario"] = d["costo_unitario"].fillna(0)

    # Consumo mensual. Los meses son dinámicos según Salidas.
    monthly = s.groupby(["codigo", "periodo"], as_index=False)["cantidad"].sum()
    monthly = monthly.rename(columns={"cantidad": "consumo"})
    pivot = monthly.pivot(index="codigo", columns="periodo", values="consumo").fillna(0)
    pivot = pivot.reindex(columns=periodos, fill_value=0).reset_index()
    pivot.columns = ["codigo"] + [str(p) for p in periodos]
    d = d.merge(pivot, on="codigo", how="left")
    for p in periodos:
        d[str(p)] = d[str(p)].fillna(0)

    # Métricas sobre meses con consumo: promedio pedido por el usuario.
    vals = d[[str(p) for p in periodos]].to_numpy(dtype=float)
    d["consumo_total"] = vals.sum(axis=1)
    d["meses_con_consumo"] = (vals > 0).sum(axis=1)
    d["meses_sin_consumo"] = len(periodos) - d["meses_con_consumo"]
    d["consumo_mensual_promedio"] = np.where(
        d["meses_con_consumo"] > 0,
        d["consumo_total"] / d["meses_con_consumo"],
        0
    )
    d["consumo_diario"] = d["consumo_mensual_promedio"] / 30
    d["desv_mensual"] = np.where(
        d["meses_con_consumo"] > 1,
        np.std(np.where(vals > 0, vals, np.nan), axis=1, ddof=1),
        0
    )
    d["desv_mensual"] = np.nan_to_num(d["desv_mensual"])
    d["cv_consumo"] = np.where(d["consumo_mensual_promedio"] > 0,
                               d["desv_mensual"] / d["consumo_mensual_promedio"], 0)

    # Tendencia lineal sobre los meses disponibles, incluyendo ceros.
    x = np.arange(len(periodos), dtype=float)
    tendencias, r2s = [], []
    for row in vals:
        if len(row) >= 2 and np.std(row) > 0:
            slope, intercept = np.polyfit(x, row, 1)
            pred = slope*x + intercept
            ss_res = np.sum((row-pred)**2)
            ss_tot = np.sum((row-row.mean())**2)
            r2 = 1-ss_res/ss_tot if ss_tot else 0
            umbral = max(row.mean()*0.01, 1e-9)
            tendencias.append("Constante" if abs(slope) < umbral else
                              ("Creciente" if slope > 0 else "Decreciente"))
            r2s.append(r2)
        else:
            tendencias.append("No concluyente")
            r2s.append(np.nan)
    d["tendencia"] = tendencias
    d["r2_regresion"] = r2s

    # Valor de salidas: usa valor de salida si existe; si no, cantidad*costo.
    costo_map = d.set_index("codigo")["costo_unitario"]
    s["valor_calculado"] = s["valor_salida"]
    falt = s["valor_calculado"].isna()
    s.loc[falt, "valor_calculado"] = s.loc[falt, "cantidad"] * s.loc[falt, "codigo"].map(costo_map).fillna(0)
    valor_sal = s.groupby("codigo")["valor_calculado"].sum().rename("valor_salidas")
    d = d.join(valor_sal, on="codigo")
    d["valor_salidas"] = d["valor_salidas"].fillna(0)
    d["valor_inventario"] = d["stock_actual"] * d["costo_unitario"]

    # Lead Time SOLO desde Órdenes de Compra: F. Docum. -> Fecha Guía,
    # con Estado Item = COMPRADO. No se usa Ingresos.
    o = oc.copy()
    o["estado_item"] = o["estado_item"].astype(str).str.upper().str.strip()
    o = o[(o["estado_item"] == "COMPRADO") &
          o["f_docum"].notna() & o["fecha_guia"].notna()].copy()
    o["lead_time_calc"] = (o["fecha_guia"] - o["f_docum"]).dt.days
    o = o[(o["lead_time_calc"] >= 0) & (o["lead_time_calc"] <= 365)]
    lt = o.groupby("codigo")["lead_time_calc"].median().rename("lead_time")
    d = d.join(lt, on="codigo")
    # Cuando no hay historial calculable, se usa 12 días como parámetro operativo.
    d["lead_time_estimado"] = d["lead_time"].isna()
    d["lead_time_utilizado"] = d["lead_time"].fillna(12)

    # Seguridad / punto de pedido.
    d["stock_seguridad"] = z * d["desv_mensual"] * np.sqrt(d["lead_time_utilizado"]/30)
    # Si no existe variabilidad suficiente, reserva 20% de la demanda del lead time.
    fallback = (d["stock_seguridad"] <= 0) & (d["consumo_mensual_promedio"] > 0)
    d.loc[fallback, "stock_seguridad"] = (
        d.loc[fallback, "consumo_mensual_promedio"] *
        d.loc[fallback, "lead_time_utilizado"]/30 * 0.20
    )
    d["punto_pedido"] = d["consumo_diario"] * d["lead_time_utilizado"] + d["stock_seguridad"]

    # Cobertura actual.
    d["cobertura_dias"] = np.where(d["consumo_diario"] > 0,
                                   d["stock_actual"]/d["consumo_diario"], np.inf)

    # Objetivos y compra para 1, 2 y 3 meses.
    for meses in [1, 2, 3]:
        d[f"stock_objetivo_{meses}m"] = (
            d["consumo_mensual_promedio"] * meses + d["stock_seguridad"]
        )
        d[f"cantidad_abastecer_{meses}m"] = np.ceil(np.maximum(
            0, d[f"stock_objetivo_{meses}m"] - d["stock_actual"]
        ))
        d[f"cobertura_post_{meses}m"] = np.where(
            d["consumo_diario"] > 0,
            (d["stock_actual"] + d[f"cantidad_abastecer_{meses}m"]) / d["consumo_diario"],
            np.inf
        )

    # Situación / rotura: material con salidas y stock <= 0.
    d["rotura_stock"] = (d["stock_actual"] <= 0) & (d["consumo_total"] > 0)
    d["situacion_stock"] = np.select(
        [d["rotura_stock"], d["stock_actual"] <= d["punto_pedido"]],
        ["ROTURA DE STOCK", "POR DEBAJO DEL PUNTO DE PEDIDO"],
        default="STOCK SUFICIENTE"
    )
    d["momento_compra"] = np.where(
        d["stock_actual"] <= d["punto_pedido"], "COMPRAR AHORA", "NO COMPRAR AÚN"
    )

    d["tipo_consumo"] = np.select(
        [
            d["meses_con_consumo"] <= 1,
            d["meses_con_consumo"] / len(periodos) < 0.67
        ],
        ["Eventual", "Intermitente"],
        default="Frecuente"
    )
    d["nivel_variabilidad"] = np.select(
        [d["cv_consumo"] <= 0.5, d["cv_consumo"] <= 1],
        ["Baja", "Media"], default="Alta"
    )
    d["anomalía_de_consumo"] = np.where(
        (d["desv_mensual"] > 0) &
        (vals.max(axis=1) > d["consumo_mensual_promedio"] + 2*d["desv_mensual"]),
        "Pico anormal", "No"
    )

    # ABC por valor acumulado de salidas.
    r = d.sort_values("valor_salidas", ascending=False).copy()
    total_valor = r["valor_salidas"].sum()
    if total_valor > 0:
        r["abc_acum_pct"] = r["valor_salidas"].cumsum()/total_valor*100
        r["clasificacion_abc"] = np.select(
            [r["abc_acum_pct"] <= 80, r["abc_acum_pct"] <= 95],
            ["A", "B"], default="C"
        )
    else:
        r["abc_acum_pct"] = 0
        r["clasificacion_abc"] = "C"
    d = d.drop(columns=["abc_acum_pct", "clasificacion_abc"], errors="ignore").merge(
        r[["codigo", "abc_acum_pct", "clasificacion_abc"]], on="codigo", how="left"
    )
    d["clasificacion_xyz"] = np.select(
        [d["cv_consumo"] <= 0.5, d["cv_consumo"] <= 1],
        ["X", "Y"], default="Z"
    )

    d["prioridad"] = np.select(
        [
            d["rotura_stock"],
            (d["stock_actual"] <= d["punto_pedido"]) &
            (d["cobertura_dias"] < d["lead_time_utilizado"])
        ],
        ["CRÍTICO", "ALTO"], default="REVISAR"
    )

    d["diagnostico"] = d.apply(
        lambda r: (
            "ROTURA DE STOCK: stock 0 con salidas registradas. "
            if r["rotura_stock"] else
            ("Stock por debajo del punto de pedido. "
             if r["stock_actual"] <= r["punto_pedido"] else
             "Stock por encima del punto de pedido. ")
        ) +
        f"Consumo promedio {r['consumo_mensual_promedio']:,.2f} por mes; "
        f"tendencia {r['tendencia'].lower()}.",
        axis=1
    )
    d["recomendacion"] = d.apply(
        lambda r: (
            f"{r['momento_compra']}. Para 1 mes: comprar "
            f"{r['cantidad_abastecer_1m']:,.0f} {r['unidad']}; "
            f"para 2 meses: {r['cantidad_abastecer_2m']:,.0f}; "
            f"para 3 meses: {r['cantidad_abastecer_3m']:,.0f}. "
            f"Cobertura después de comprar para 1 mes: "
            f"{r['cobertura_post_1m']:.1f} días."
        ),
        axis=1
    )

    monthly["periodo_str"] = monthly["periodo"].astype(str)
    return d, monthly, periodos
