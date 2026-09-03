
import io
import re
from datetime import datetime
import numpy as np
import pandas as pd


# ============================================================
# CONFIGURACIÓN DEFINITIVA DE LAS FUENTES
# ============================================================
STOCK_MAP = {
    "codigo": "Codigo",                 # A
    "descripcion": "Descripción",       # B
    "unidad": "U.Medida",              # C
    "stock": "Sistema",                # D
    "familia": "Familia",              # N
    "costo": "Costo Cierre Mes",       # T
}

SALIDAS_MAP = {
    "fecha":  "H",
    "cantidad": "AX",
}

OC_NAMES = {
    "fecha_doc": ["F. Docum.", "F Docum.", "F.Docum.", "Fecha Documento"],
    "fecha_guia": ["Fecha Guia", "Fecha Guía"],
    "estado": ["Estado Item", "Estado Ítem", "Estado"],
    "codigo": ["Codigo", "Código"],
    "cantidad": ["Cantidad", "Cant.", "Cantidad OC", "C. OC"],
}


def _clean(x):
    if pd.isna(x):
        return ""
    return str(x).strip()


def _norm(s):
    s = _clean(s).lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _read_excel(file):
    raw = pd.ExcelFile(file)
    # Prefer a sheet whose name looks relevant; otherwise first sheet.
    names = raw.sheet_names
    return raw, names


def _pick_sheet(xls, keywords):
    for s in xls.sheet_names:
        ns = _norm(s)
        if any(k in ns for k in keywords):
            return s
    return xls.sheet_names[0]


def _find_exact_or_alias(df, aliases, required=True):
    cols = list(df.columns)
    normmap = {_norm(c): c for c in cols}
    for a in aliases:
        if _norm(a) in normmap:
            return normmap[_norm(a)]
    if required:
        raise ValueError(f"No se encontró columna. Se buscó: {aliases}. Columnas disponibles: {cols}")
    return None


def _find_excel_letter(df, letter):
    idx = ord(letter.upper()) - 65
    if idx < 0 or idx >= len(df.columns):
        raise ValueError(f"La columna {letter} no existe en la hoja. Hay {len(df.columns)} columnas.")
    return df.columns[idx]


def _to_num(s):
    # Handles Excel numeric values and common thousands/decimal formats.
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").fillna(0.0)
    x = s.astype(str).str.strip().str.replace("S/", "", regex=False).str.replace(" ", "", regex=False)
    # If both separators exist, assume last separator is decimal.
    def one(v):
        if v in ("", "nan", "None"):
            return np.nan
        v = str(v)
        if "," in v and "." in v:
            if v.rfind(",") > v.rfind("."):
                v = v.replace(".", "").replace(",", ".")
            else:
                v = v.replace(",", "")
        elif "," in v:
            v = v.replace(",", ".")
        return pd.to_numeric(v, errors="coerce")
    return x.map(one).fillna(0.0)


def _as_code(s):
    # Never numeric-convert material codes. Preserve leading zeros.
    return s.map(lambda x: "" if pd.isna(x) else str(x).strip())


def load_stock(file):
    xls, _ = _read_excel(file)
    sheet = _pick_sheet(xls, ["stock", "inventario", "saldo"])
    d = pd.read_excel(file, sheet_name=sheet, dtype=object)

    # Explicit definitive mapping; fallback is only by exact name.
    mapping = {}
    for key, name in STOCK_MAP.items():
        mapping[key] = _find_exact_or_alias(d, [name])

    out = pd.DataFrame(index=d.index)
    out["codigo"] = _as_code(d[mapping["codigo"]])
    out["descripcion"] = d[mapping["descripcion"]].map(_clean)
    out["unidad"] = d[mapping["unidad"]].map(_clean)
    out["stock_actual"] = _to_num(d[mapping["stock"]])
    out["familia"] = d[mapping["familia"]].map(_clean)
    out["costo_unitario"] = _to_num(d[mapping["costo"]])

    # Remove blank codes but retain leading zeros.
    out = out[out["codigo"].ne("")].copy()
    out = out.drop_duplicates("codigo", keep="last")
    return out.reset_index(drop=True)


def load_salidas(file):
    xls, _ = _read_excel(file)
    sheet = _pick_sheet(xls, ["salida", "salidas", "movimiento", "movimientos", "kardex"])
    d = pd.read_excel(file, sheet_name=sheet, dtype=object)

    codigo_col = _find_exact_or_alias(d, ["Codigo", "Código", "Cod.Origen", "Cod. Origen", "Cod"])
    fecha_col = _find_exact_or_alias(d, ["Fecha", "F. Docum.", "F Docum.", "Fecha Salida", "Fecha movimiento"])
    # User's definitive source is AX for quantity. If the sheet has 50+ columns, use AX.
    if len(d.columns) >= 50:
        qty_col = _find_excel_letter(d, SALIDAS_MAP["cantidad"])
    else:
        qty_col = _find_exact_or_alias(d, ["Cantidad", "Cantidad salida", "Cantidad Salida", "Cant.", "Qty"])

    out = pd.DataFrame({
        "codigo": _as_code(d[codigo_col]),
        "fecha": pd.to_datetime(d[fecha_col], errors="coerce", dayfirst=True),
        "cantidad": _to_num(d[qty_col]).abs(),
    })
    return out.dropna(subset=["fecha"]).query("codigo != ''").reset_index(drop=True)


def load_oc(file):
    xls, _ = _read_excel(file)
    sheet = _pick_sheet(xls, ["orden", "compra", "oc"])
    d = pd.read_excel(file, sheet_name=sheet, dtype=object)

    fdoc = _find_exact_or_alias(d, OC_NAMES["fecha_doc"])
    fguia = _find_exact_or_alias(d, OC_NAMES["fecha_guia"])
    estado = _find_exact_or_alias(d, OC_NAMES["estado"])
    codigo = _find_exact_or_alias(d, OC_NAMES["codigo"])

    qcol = _find_exact_or_alias(d, OC_NAMES["cantidad"], required=False)
    if qcol is None:
        # If quantity is not needed by the input, derive last purchase quantity
        # from the first plausible numeric column only as a last resort.
        qcol = None

    out = pd.DataFrame({
        "codigo": _as_code(d[codigo]),
        "f_docum": pd.to_datetime(d[fdoc], errors="coerce", dayfirst=True),
        "fecha_guia": pd.to_datetime(d[fguia], errors="coerce", dayfirst=True),
        "estado": d[estado].map(_clean).str.upper(),
        "cantidad": _to_num(d[qcol]) if qcol else 0.0,
    })
    out["lead_time"] = (out["fecha_guia"] - out["f_docum"]).dt.days
    out.loc[(out["lead_time"] < 0) | (out["lead_time"] > 365), "lead_time"] = np.nan
    out = out[out["codigo"].ne("")].copy()
    return out.reset_index(drop=True)


def _trend(vals):
    x = np.arange(len(vals), dtype=float)
    y = np.asarray(vals, dtype=float)
    if len(y) < 2 or np.allclose(y, y[0]):
        return "Estable"
    slope = np.polyfit(x, y, 1)[0]
    scale = max(np.mean(np.abs(y)), 1.0)
    if slope > 0.03 * scale:
        return "Creciente"
    if slope < -0.03 * scale:
        return "Decreciente"
    return "Estable"


def _abc(df):
    # ABC by total consumption value. If all values are zero, assign C.
    v = df["consumo_total"] * df["costo_unitario"]
    total = v.sum()
    if total <= 0:
        return pd.Series(["C"] * len(df), index=df.index), pd.Series([100.0] * len(df), index=df.index)
    order = v.sort_values(ascending=False).index
    cum = v.loc[order].cumsum() / total * 100
    cls = pd.Series(index=df.index, dtype=object)
    for i in order:
        p = cum.loc[i]
        cls.loc[i] = "A" if p <= 80 else ("B" if p <= 95 else "C")
    pct = cum.reindex(df.index).fillna(100.0)
    return cls, pct


def _xyz(cv):
    if pd.isna(cv):
        return "Z"
    if cv <= 0.20:
        return "X"
    if cv <= 0.50:
        return "Y"
    return "Z"


def analyze(stock, sal, oc, as_of=None, horizon_months=3, z=1.65):
    if as_of is None:
        as_of = max([d.max() for d in [sal["fecha"].dropna(), oc["f_docum"].dropna(), oc["fecha_guia"].dropna()] if len(d)], default=pd.Timestamp.today())
    as_of = pd.Timestamp(as_of).normalize()

    # Monthly period range is based on actual sales dates, ending at as_of month.
    start = sal["fecha"].min()
    if pd.isna(start):
        periods = pd.period_range(as_of.to_period("M"), as_of.to_period("M"), freq="M")
    else:
        periods = pd.period_range(start.to_period("M"), as_of.to_period("M"), freq="M")

    rows = []
    for _, r in stock.iterrows():
        code = r["codigo"]
        s = sal[sal["codigo"] == code].copy()
        s["period"] = s["fecha"].dt.to_period("M")
        monthly = s.groupby("period")["cantidad"].sum()

        # Include only periods in the analysis window.
        vals = np.array([float(monthly.get(p, 0.0)) for p in periods])
        positive = vals[vals > 0]
        total = float(vals.sum())
        months_with = int((vals > 0).sum())
        months_without = int(len(vals) - months_with)
        avg = total / months_with if months_with else 0.0
        daily = avg / 30.0 if avg > 0 else 0.0

        last_out = s["fecha"].max() if len(s) else pd.NaT
        days_no_move = int((as_of - last_out.normalize()).days) if pd.notna(last_out) else np.nan
        coverage = float(r["stock_actual"] / daily) if daily > 0 else np.inf

        # OC: only COMPRADO is valid for purchase/lead-time analysis.
        o = oc[(oc["codigo"] == code) & (oc["estado"].eq("COMPRADO"))].copy()
        o = o.sort_values(["f_docum", "fecha_guia"])
        valid_lt = o["lead_time"].dropna()
        lead_time = float(valid_lt.median()) if len(valid_lt) else np.nan

        if len(o):
            last_oc = o.iloc[-1]
            last_buy_qty = float(last_oc["cantidad"])
            last_buy_date = last_oc["f_docum"]
            days_since_buy = int((as_of - last_buy_date.normalize()).days) if pd.notna(last_buy_date) else np.nan
            buy_coverage = last_buy_qty / avg if avg > 0 else np.nan
        else:
            last_buy_qty = np.nan
            last_buy_date = pd.NaT
            days_since_buy = np.nan
            buy_coverage = np.nan

        mean = float(vals.mean())
        std = float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
        cv = std / mean if mean > 0 else np.nan

        # Intermittency: distinguish frequent from occasional/intermittent.
        if months_with == 0:
            consumption_type = "Sin consumo"
        elif months_with == 1:
            consumption_type = "Ocasional"
        elif months_with / max(len(vals), 1) < 0.50:
            consumption_type = "Intermitente"
        else:
            consumption_type = "Frecuente"

        trend = _trend(vals)
        variability = "Baja" if pd.isna(cv) or cv <= 0.20 else ("Media" if cv <= 0.50 else "Alta")
        anomaly = "Sí" if len(vals) >= 4 and np.any(np.abs(vals - mean) > 3 * max(std, 1e-9)) else "No"

        # Service-level safety stock. Use LT in days when available; otherwise 0.
        lt_days = lead_time if pd.notna(lead_time) else 0.0
        safety = z * daily * np.sqrt(max(lt_days, 0.0)) if daily > 0 else 0.0
        reorder = daily * lt_days + safety
        target = avg * max(float(horizon_months), 1.0) + safety
        replenish = max(target - float(r["stock_actual"]), 0.0)

        situation = "SIN CONSUMO"
        rupture = "FALSO"
        if total > 0:
            if r["stock_actual"] <= 0:
                situation = "ROTURA DE STOCK"
                rupture = "VERDADERO"
            elif pd.notna(coverage) and coverage < lt_days:
                situation = "RIESGO DE ROTURA"
            elif pd.notna(coverage) and coverage < avg and avg > 0:
                situation = "STOCK BAJO"
            else:
                situation = "STOCK SUFICIENTE"

        # Scenarios: purchase quantity and resulting total coverage.
        def scenario(months):
            q = avg * months
            dur = ((float(r["stock_actual"]) + q) / daily) if daily > 0 else np.inf
            return q, dur

        q1, d1 = scenario(1)
        q2, d2 = scenario(2)
        q3, d3 = scenario(3)

        when = "NO COMPRAR" if total == 0 else ("AHORA" if float(r["stock_actual"]) <= reorder else "PROGRAMAR")
        priority = "ALTO" if situation in ("ROTURA DE STOCK", "RIESGO DE ROTURA") else ("MEDIO" if situation == "STOCK BAJO" else "REVISAR")
        diagnosis = f"{situation}. {consumption_type}. {months_with} meses con consumo de {len(vals)}."
        recommendation = f"Abastecer {replenish:.2f} {r['unidad']}." if replenish > 0 else "No requiere abastecimiento inmediato."

        rows.append({
            "Código": code,
            "Descripción": r["descripcion"],
            "Unidad de medida": r["unidad"],
            "Familia": r["familia"],
            "Stock actual": float(r["stock_actual"]),
            "Costo unitario (S/)": float(r["costo_unitario"]),
            "Valor del inventario (S/)": float(r["stock_actual"] * r["costo_unitario"]),
            "Consumo total": total,
            "Valor de salidas (S/)": total * float(r["costo_unitario"]),
            "Última salida": last_out,
            **{str(p): float(monthly.get(p, 0.0)) for p in periods},
            "Meses con consumo": months_with,
            "Meses sin consumo": months_without,
            "Consumo mensual promedio": avg,
            "Consumo diario": daily,
            "Días sin movimiento": days_no_move,
            "Cobertura (días)": coverage,
            "Lead Time (días)": lead_time,
            "Tipo de consumo": consumption_type,
            "Situación de stock": situation,
            "Rotura de stock": rupture,
            "Tendencia del consumo": trend,
            "Coeficiente de variación": cv,
            "Nivel de variabilidad": variability,
            "Anomalía de consumo": anomaly,
            "Stock de seguridad": safety,
            "Punto de pedido": reorder,
            "Stock objetivo": target,
            "Cantidad a abastecer": replenish,
            "Última compra": last_buy_qty,
            "Fecha última compra": last_buy_date,
            "Días desde última compra": days_since_buy,
            "Cobertura última compra (meses)": buy_coverage,
            "Compra para 1 mes": q1,
            "Duración después de comprar 1 mes (días)": d1,
            "Compra para 2 meses": q2,
            "Duración después de comprar 2 meses (días)": d2,
            "Compra para 3 meses": q3,
            "Duración después de comprar 3 meses (días)": d3,
            "Cuándo comprar": when,
            "Metodología utilizada": "Promedio de meses con consumo + variabilidad + Lead Time de OC COMPRADO",
            "Diagnóstico": diagnosis,
            "Prioridad": priority,
            "Recomendación": recommendation,
        })

    result = pd.DataFrame(rows)
    result["Clasificación ABC"], result["ABC acumulado (%)"] = _abc(result)
    result["Clasificación XYZ"] = result["Coeficiente de variación"].map(_xyz)

    # Put columns in the exact requested order.
    fixed = [
        "Código","Descripción","Unidad de medida","Familia","Stock actual",
        "Costo unitario (S/)","Valor del inventario (S/)","Consumo total",
        "Valor de salidas (S/)","Última salida"
    ]
    month_cols = [str(p) for p in periods]
    rest = [
        "Meses con consumo","Meses sin consumo","Consumo mensual promedio","Consumo diario",
        "Días sin movimiento","Cobertura (días)","Lead Time (días)","Tipo de consumo",
        "Situación de stock","Rotura de stock","Tendencia del consumo","Coeficiente de variación",
        "Nivel de variabilidad","Anomalía de consumo","ABC acumulado (%)","Clasificación ABC",
        "Clasificación XYZ","Stock de seguridad","Punto de pedido","Stock objetivo",
        "Cantidad a abastecer","Última compra","Fecha última compra","Días desde última compra",
        "Cobertura última compra (meses)","Compra para 1 mes","Duración después de comprar 1 mes (días)",
        "Compra para 2 meses","Duración después de comprar 2 meses (días)",
        "Compra para 3 meses","Duración después de comprar 3 meses (días)",
        "Cuándo comprar","Metodología utilizada","Diagnóstico","Prioridad","Recomendación"
    ]
    result = result[fixed + month_cols + rest]
    return result, periods


def to_excel(df):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        # Force Código to text and preserve zeros in Excel.
        out = df.copy()
        out.to_excel(writer, index=False, sheet_name="Analisis")
        ws = writer.book["Analisis"]
        headers = {cell.value: cell.column for cell in ws[1]}
        if "Código" in headers:
            c = headers["Código"]
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=c).number_format = "@"
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            maxlen = min(max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 45)
            ws.column_dimensions[col[0].column_letter].width = maxlen
    bio.seek(0)
    return bio.getvalue()
