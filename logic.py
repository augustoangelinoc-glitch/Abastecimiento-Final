
import pandas as pd
import numpy as np
import re

def clean_col(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def norm_text(x):
    if pd.isna(x):
        return ""
    return str(x).strip().upper()

def norm_code(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s.lower() in {"nan", "none", "nat"}:
        return ""
    if re.fullmatch(r"-?\d+\.0+", s):
        s = s.split(".")[0]
    if re.fullmatch(r"\d+", s):
        s = s.lstrip("0") or "0"
    return s

def norm_doc(x):
    return norm_code(x)

def to_num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0.0)

def to_date(s):
    return pd.to_datetime(s, errors="coerce", dayfirst=False)

def prepare_stock(df):
    df = clean_col(df)
    required = ["Codigo", "Descripción", "Sistema", "Fisico", "Diferencia",
                "Costo Cierre Mes", "C. Kardex"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Stock actual: faltan columnas {missing}")

    out = pd.DataFrame()
    out["codigo"] = df["Codigo"].map(norm_code)
    # FUENTE OFICIAL: columna B / campo Descripción del Stock Actual
    out["descripcion"] = df["Descripción"].fillna("").astype(str).str.strip()
    out["stock_actual"] = to_num(df["Sistema"])
    out["stock_fisico"] = to_num(df["Fisico"])
    out["diferencia_inventario"] = to_num(df["Diferencia"])
    out["costo_unitario"] = to_num(df["Costo Cierre Mes"])
    out["costo_kardex"] = to_num(df["C. Kardex"])
    out["familia"] = (df["Familia"].fillna("").astype(str).str.strip()
                      if "Familia" in df.columns else "")
    out = out[out["codigo"] != ""].drop_duplicates("codigo", keep="first")
    out["valor_inventario"] = out["stock_actual"] * out["costo_unitario"]
    return out

def prepare_sales(df):
    df = clean_col(df)
    required = ["Material", "F.Contab", "Unidades"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Salidas: faltan columnas {missing}")

    out = pd.DataFrame()
    out["codigo"] = df["Material"].map(norm_code)
    out["fecha"] = to_date(df["F.Contab"])
    out["unidades"] = to_num(df["Unidades"])
    out["descripcion_salida"] = (
        df["Descripción.2"].fillna("").astype(str).str.strip()
        if "Descripción.2" in df.columns else ""
    )
    out = out[(out["codigo"] != "") & out["fecha"].notna() & (out["unidades"] > 0)]
    return out

def prepare_oc(df):
    df = clean_col(df)
    required = ["P. Emis", "Número", "Material", "F.Contab", "Unidades"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Órdenes de compra: faltan columnas {missing}")

    out = pd.DataFrame()
    out["emisor"] = df["P. Emis"].map(norm_text)
    out["numero_oc"] = df["Número"].map(norm_doc)
    out["codigo"] = df["Material"].map(norm_code)
    out["fecha_oc"] = to_date(df["F.Contab"])
    out["unidades_oc"] = to_num(df["Unidades"])
    out["estado_oc"] = (df["Estado"].fillna("").astype(str).str.strip().str.upper()
                         if "Estado" in df.columns else "")
    out["estado_item"] = (df["Estado Item"].fillna("").astype(str).str.strip().str.upper()
                          if "Estado Item" in df.columns else "")
    out["key_oc"] = out["emisor"] + "|" + out["numero_oc"] + "|" + out["codigo"]
    out = out[(out["emisor"] != "") & (out["numero_oc"] != "")
              & (out["codigo"] != "") & out["fecha_oc"].notna()]
    return out

def prepare_ingresos(df):
    df = clean_col(df)
    required = ["P.OC", "Número OC", "Material", "Unidades", "Fecha OC", "F.Almac."]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Ingresos: faltan columnas {missing}")

    out = pd.DataFrame()
    out["emisor"] = df["P.OC"].map(norm_text)
    out["numero_oc"] = df["Número OC"].map(norm_doc)
    out["codigo"] = df["Material"].map(norm_code)
    out["fecha_oc_ingreso"] = to_date(df["Fecha OC"])
    out["fecha_ingreso"] = to_date(df["F.Almac."])
    out["unidades_ingreso"] = to_num(df["Unidades"])
    out["key_oc"] = out["emisor"] + "|" + out["numero_oc"] + "|" + out["codigo"]
    out = out[(out["emisor"] != "") & (out["numero_oc"] != "")
              & (out["codigo"] != "") & out["fecha_ingreso"].notna()]
    return out

def monthly_consumption(sales):
    if sales.empty:
        return pd.DataFrame(), pd.DataFrame()
    minp = sales["fecha"].min().to_period("M")
    maxp = sales["fecha"].max().to_period("M")
    months = pd.period_range(minp, maxp, freq="M")
    tmp = sales.assign(periodo=sales["fecha"].dt.to_period("M"))
    agg = tmp.groupby(["codigo", "periodo"], as_index=False)["unidades"].sum()
    piv = agg.pivot(index="codigo", columns="periodo", values="unidades")
    piv = piv.reindex(columns=months, fill_value=0).fillna(0)
    piv.columns = [p.strftime("%b-%Y").capitalize() for p in months]
    piv = piv.reset_index()
    return agg, piv

def lead_time_detail(oc, ing):
    columns = ["codigo","emisor","numero_oc","fecha_oc","primera_recepcion",
               "unidades_oc","unidades_ingresadas","lead_time_dias"]
    if oc.empty or ing.empty:
        return pd.DataFrame(columns=columns)

    oc_base = oc.groupby(["key_oc","codigo","emisor","numero_oc"], as_index=False).agg(
        fecha_oc=("fecha_oc","min"),
        unidades_oc=("unidades_oc","sum")
    )
    ing_base = ing.groupby(["key_oc","codigo"], as_index=False).agg(
        primera_recepcion=("fecha_ingreso","min"),
        unidades_ingresadas=("unidades_ingreso","sum")
    )
    d = oc_base.merge(ing_base, on=["key_oc","codigo"], how="inner")
    d["lead_time_dias"] = (d["primera_recepcion"] - d["fecha_oc"]).dt.days
    d = d[d["lead_time_dias"] >= 0].copy()
    return d[columns]

def lead_time_by_material(detail):
    cols = ["codigo","lead_time_mediano","lead_time_promedio","lead_time_min",
            "lead_time_max","oc_con_ingreso"]
    if detail.empty:
        return pd.DataFrame(columns=cols)
    return detail.groupby("codigo", as_index=False).agg(
        lead_time_mediano=("lead_time_dias","median"),
        lead_time_promedio=("lead_time_dias","mean"),
        lead_time_min=("lead_time_dias","min"),
        lead_time_max=("lead_time_dias","max"),
        oc_con_ingreso=("lead_time_dias","count")
    )

def classify_demand(row):
    total = row["consumo_total"]
    freq = row["frecuencia_meses"]
    cv = row["desv_consumo_mensual"] / row["consumo_mensual_promedio"] if row["consumo_mensual_promedio"] > 0 else np.nan
    if total <= 0:
        return "Sin consumo"
    if freq <= 0.25:
        return "Eventual"
    if freq < 0.75:
        return "Intermitente"
    if np.isfinite(cv) and cv <= 0.50:
        return "Frecuente / estable"
    return "Frecuente / variable"

def build_analysis(stock, sales, oc, ing):
    stock = prepare_stock(stock)
    sales = prepare_sales(sales)
    oc = prepare_oc(oc)
    ing = prepare_ingresos(ing)

    agg, piv = monthly_consumption(sales)

    if not agg.empty:
        stats = agg.groupby("codigo", as_index=False).agg(
            consumo_total=("unidades","sum"),
            meses_con_consumo=("periodo","nunique")
        )
        last = sales.groupby("codigo", as_index=False)["fecha"].max().rename(
            columns={"fecha":"ultima_salida"}
        )
        stats = stats.merge(last, on="codigo", how="left")

        monthly = agg.pivot(index="codigo", columns="periodo", values="unidades").fillna(0)
        months_all = len(monthly.columns)
        stats2 = pd.DataFrame({
            "codigo": monthly.index,
            "consumo_mensual_promedio": monthly.mean(axis=1),
            "consumo_mensual_mediano": monthly.median(axis=1),
            "desv_consumo_mensual": monthly.std(axis=1, ddof=0),
            "consumo_mensual_max": monthly.max(axis=1),
            "q1_consumo": monthly.quantile(.25, axis=1),
            "q3_consumo": monthly.quantile(.75, axis=1),
        }).reset_index(drop=True)
        stats = stats.merge(stats2, on="codigo", how="outer")
        stats["meses_sin_consumo"] = months_all - stats["meses_con_consumo"]
        stats["frecuencia_meses"] = stats["meses_con_consumo"] / max(months_all, 1)
    else:
        stats = pd.DataFrame(columns=[
            "codigo","consumo_total","meses_con_consumo","ultima_salida",
            "consumo_mensual_promedio","consumo_mensual_mediano",
            "desv_consumo_mensual","consumo_mensual_max","q1_consumo",
            "q3_consumo","meses_sin_consumo","frecuencia_meses"
        ])

    lt_detail = lead_time_detail(oc, ing)
    lt = lead_time_by_material(lt_detail)

    view = stock.merge(stats, on="codigo", how="left").merge(lt, on="codigo", how="left")

    numeric_cols = [
        "consumo_total","meses_con_consumo","meses_sin_consumo","frecuencia_meses",
        "consumo_mensual_promedio","consumo_mensual_mediano","desv_consumo_mensual",
        "consumo_mensual_max","q1_consumo","q3_consumo","lead_time_mediano",
        "lead_time_promedio","lead_time_min","lead_time_max","oc_con_ingreso"
    ]
    for c in numeric_cols:
        if c not in view.columns:
            view[c] = 0.0
        view[c] = pd.to_numeric(view[c], errors="coerce").fillna(0.0)

    if "ultima_salida" in view.columns:
        view["dias_sin_movimiento"] = np.where(
            view["ultima_salida"].notna(),
            (pd.Timestamp.today().normalize() - view["ultima_salida"]).dt.days,
            np.nan
        )
    else:
        view["dias_sin_movimiento"] = np.nan

    view["tipo_consumo"] = view.apply(classify_demand, axis=1)

    iqr = view["q3_consumo"] - view["q1_consumo"]
    view["pico_anormal"] = (
        (view["consumo_mensual_max"] > view["q3_consumo"] + 1.5 * iqr)
        & (view["consumo_mensual_max"] > 0)
    )

    trend_map = {}
    if not agg.empty:
        periods = sorted(agg["periodo"].unique())
        half = max(len(periods)//2, 1)
        first = agg[agg["periodo"].isin(periods[:half])].groupby("codigo")["unidades"].mean()
        second = agg[agg["periodo"].isin(periods[half:])].groupby("codigo")["unidades"].mean()
        for code in set(first.index) | set(second.index):
            a = float(first.get(code, 0))
            b = float(second.get(code, 0))
            if a == 0 and b > 0:
                trend_map[code] = "Creciente"
            elif a > 0 and b < a * 0.80:
                trend_map[code] = "Decreciente"
            elif b > a * 1.20:
                trend_map[code] = "Creciente"
            else:
                trend_map[code] = "Estable"
    view["tendencia"] = view["codigo"].map(trend_map).fillna("Sin datos")

    # Modelo de abastecimiento provisional: demanda durante Lead Time + seguridad.
    # Se mantiene como modelo inicial; más adelante se compararán metodologías.
    lt_days = view["lead_time_mediano"].where(view["lead_time_mediano"] > 0, np.nan)
    daily_mean = view["consumo_mensual_promedio"] / 30.0
    daily_std = view["desv_consumo_mensual"] / np.sqrt(30.0)

    view["demanda_lead_time"] = daily_mean * lt_days
    view["stock_seguridad"] = 1.65 * daily_std * np.sqrt(lt_days)
    view["punto_pedido"] = view["demanda_lead_time"] + view["stock_seguridad"]
    view["stock_objetivo"] = view["punto_pedido"]

    raw = view["stock_objetivo"] - view["stock_actual"]
    view["cantidad_abastecer"] = np.ceil(raw.clip(lower=0)).fillna(0).astype(int)
    view["modelo_estado"] = np.where(
        view["lead_time_mediano"] > 0,
        "Calculado con Lead Time real",
        "Sin Lead Time calculable"
    )

    view["riesgo_stock"] = np.select(
        [
            (view["stock_actual"] <= 0) & (view["frecuencia_meses"] >= .50) &
            (view["consumo_mensual_promedio"] > 0),
            (view["stock_actual"] > 0) &
            (view["stock_actual"] < view["consumo_mensual_promedio"]) &
            (view["frecuencia_meses"] >= .50),
            (view["dias_sin_movimiento"] > 180) & (view["stock_actual"] > 0)
        ],
        [
            "ALTO: consumo recurrente con stock cero",
            "MEDIO: stock menor al consumo mensual",
            "ATENCIÓN: stock con poco movimiento"
        ],
        default="Normal"
    )

    def explain(r):
        msgs = []
        if r["stock_actual"] <= 0 and r["frecuencia_meses"] >= .50 and r["consumo_mensual_promedio"] > 0:
            msgs.append("salidas recurrentes con stock cero")
        if r["tipo_consumo"] == "Eventual":
            msgs.append("consumo eventual")
        if r["tipo_consumo"] == "Intermitente":
            msgs.append("consumo intermitente")
        if bool(r["pico_anormal"]):
            msgs.append("pico mensual anormal")
        if r["tendencia"] in ("Creciente", "Decreciente"):
            msgs.append(f"tendencia {r['tendencia'].lower()}")
        if r["lead_time_mediano"] <= 0:
            msgs.append("sin Lead Time calculable")
        return "; ".join(msgs) if msgs else "Sin anomalías principales detectadas"

    view["explicacion"] = view.apply(explain, axis=1)
    view["valor_inventario"] = view["stock_actual"] * view["costo_unitario"]

    # Keep all monthly columns and make sure zeroes are explicit.
    return view, piv, {
        "stock": stock,
        "sales": sales,
        "oc": oc,
        "ing": ing,
        "lead_time": lt_detail
    }
