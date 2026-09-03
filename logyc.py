
import math, re
import numpy as np
import pandas as pd

# ============================================================
# LOGYC.PY - Lógica de análisis de abastecimiento
# Los nombres técnicos se mantienen SOLO internamente.
# La interfaz los traduce a nombres comprensibles en español.
# ============================================================

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())

def to_num(s):
    def f(v):
        if pd.isna(v): return np.nan
        x=str(v).strip().replace("S/","").replace("$","").replace(" ","")
        if not x or x.lower() in ("nan","none","null"): return np.nan
        if "," in x and "." in x:
            x=x.replace(".","").replace(",",".") if x.rfind(",")>x.rfind(".") else x.replace(",","")
        elif "," in x:
            p=x.split(",")
            x="".join(p[:-1])+"."+p[-1] if len(p[-1])<=2 else "".join(p)
        try: return float(x)
        except: return np.nan
    return s.map(f)

def dates(s):
    return pd.to_datetime(s, errors="coerce", dayfirst=True)

def clean_id(s):
    # Todos los identificadores se tratan como TEXTO para no perder ceros.
    return s.fillna("").astype(str).str.strip().str.replace(r"\.0$","",regex=True)

def calculate(stock, salidas, oc=None, ingresos=None):
    stock=stock.copy()
    salidas=salidas.copy()
    stock.columns=[str(x).strip() for x in stock.columns]
    salidas.columns=[str(x).strip() for x in salidas.columns]

    # ---------------- STOCK ACTUAL ----------------
    # Columnas reales definidas por el usuario:
    # A código, B descripción, C unidad, D stock, N familia, T costo.
    code_s=stock.columns[0]
    desc_s=stock.columns[1]
    um_s=stock.columns[2] if len(stock.columns)>2 else None
    st_s=stock.columns[3] if len(stock.columns)>3 else None
    fam_s=stock.columns[13] if len(stock.columns)>13 else None
    cost_s=stock.columns[19] if len(stock.columns)>19 else None

    b=pd.DataFrame({
        "codigo":clean_id(stock[code_s]),
        "descripcion":stock[desc_s].fillna("").astype(str).str.strip(),
        "unidad_medida":stock[um_s].fillna("").astype(str).str.strip() if um_s else "",
        "familia":stock[fam_s].fillna("").astype(str).str.strip() if fam_s else "",
        "stock_actual":to_num(stock[st_s]).fillna(0) if st_s else 0.0,
        "costo_unitario":to_num(stock[cost_s]).fillna(0) if cost_s else 0.0,
    })
    b["valor_inventario"]=b.stock_actual*b.costo_unitario
    b=b[b.codigo!=""].drop_duplicates("codigo")

    # ---------------- SALIDAS ----------------
    # Columnas reales definidas:
    # H = fecha; AT = descripción; Unidades = cantidad.
    # El código de material se localiza por encabezado/campo de material.
    code_o=None
    for c in salidas.columns:
        n=norm(c)
        if n in ("material","codmaterial","codigomaterial","codigo","codigomaterialerp"):
            code_o=c; break
    if code_o is None:
        # Se busca una columna cuyo contenido cruce mejor con los códigos de Stock.
        best=None; score=-1
        stock_codes=set(b.codigo)
        for c in salidas.columns:
            vals=clean_id(salidas[c])
            sc=vals.isin(stock_codes).sum()
            if sc>score:
                score=sc; best=c
        code_o=best if best is not None else salidas.columns[0]

    date_o=salidas.columns[7] if len(salidas.columns)>7 else None
    desc_o=salidas.columns[45] if len(salidas.columns)>45 else None

    qty_o=None
    for c in salidas.columns:
        if norm(c) in ("unidades","unidad","cantidad","cant","cantidadsalida"):
            qty_o=c; break

    val_o=None
    for c in salidas.columns:
        if norm(c) in ("totals","totals","total","totals","totals"):
            val_o=c; break
    if val_o is None:
        for c in salidas.columns:
            if "total" in norm(c) and ("s/" in str(c).lower() or "sol" in str(c).lower()):
                val_o=c; break

    s=pd.DataFrame({
        "codigo":clean_id(salidas[code_o]),
        "descripcion_salida":salidas[desc_o].fillna("").astype(str).str.strip() if desc_o else "",
        "fecha":dates(salidas[date_o]) if date_o else pd.NaT,
        "cantidad":to_num(salidas[qty_o]).fillna(0) if qty_o else 0.0
    })
    s["valor"]=to_num(salidas[val_o]).fillna(0) if val_o else np.nan
    s=s[s.codigo!=""]
    # No utilizar movimientos posteriores a la fecha actual.
    s=s[s.fecha.isna() | (s.fecha<=pd.Timestamp.today().normalize())]

    # ---------------- CONSUMO MENSUAL ----------------
    if s.fecha.notna().any():
        minm=s.loc[s.fecha.notna(),"fecha"].min().to_period("M")
        maxm=s.loc[s.fecha.notna(),"fecha"].max().to_period("M")
        periods=pd.period_range(minm,maxm,freq="M")
        p=s.dropna(subset=["fecha"]).assign(periodo=lambda x:x.fecha.dt.to_period("M")).pivot_table(
            index="codigo",columns="periodo",values="cantidad",aggfunc="sum",fill_value=0
        ).reindex(columns=periods,fill_value=0)
    else:
        periods=pd.PeriodIndex([],freq="M")
        p=pd.DataFrame()

    agg=s.groupby("codigo").agg(
        consumo_total=("cantidad","sum"),
        valor_salidas=("valor","sum"),
        ultimo_movimiento=("fecha","max")
    ).reset_index()

    o=b.merge(agg,on="codigo",how="left")
    o["consumo_total"]=o.consumo_total.fillna(0)
    o["valor_salidas"]=o.valor_salidas.fillna(0)
    o["ultimo_movimiento"]=pd.to_datetime(o.ultimo_movimiento,errors="coerce")

    month_cols=[]
    for per in periods:
        col=f"{per.month:02d}-{per.year}"
        month_cols.append(col)
        vals=p[per] if per in p.columns else pd.Series(dtype=float)
        o[col]=o.codigo.map(vals).fillna(0)

    n=len(periods)
    o["meses_con_consumo"]=(o[month_cols]>0).sum(axis=1) if month_cols else 0
    o["meses_sin_consumo"]=n-o["meses_con_consumo"]
    o["consumo_mensual_prom"]=o.consumo_total/n if n else 0.0

    if s.fecha.notna().any():
        first=s.fecha.min(); last=s.fecha.max()
        elapsed=max((last-first).days+1,1)
    else:
        elapsed=365
    o["consumo_diario"]=o.consumo_total/elapsed
    today=pd.Timestamp.today().normalize()
    o["dias_sin_movimiento"]=np.where(o.ultimo_movimiento.notna(),(today-o.ultimo_movimiento).dt.days,np.nan)
    o["cobertura_dias"]=np.where(o.consumo_diario>0,o.stock_actual/o.consumo_diario,np.nan)

    # ---------------- SITUACIÓN DE STOCK / ROTURA ----------------
    # La rotura no se determina solo por stock cero: se combina stock,
    # frecuencia de consumo y recencia del último movimiento.
    def situacion_stock(r):
        if r.stock_actual <= 0:
            if r.consumo_total <= 0:
                return "SIN STOCK – SIN CONSUMO"
            if r.meses_con_consumo >= 2 and (
                (pd.notna(r.dias_sin_movimiento) and r.dias_sin_movimiento <= 60)
                or r.tipo_consumo == "Frecuente"
            ):
                return "ROTURA DE STOCK"
            return "SIN STOCK – CONSUMO EVENTUAL"
        if pd.notna(r.cobertura_dias) and pd.notna(r.lead_time_dias) and r.lead_time_dias > 0 and r.cobertura_dias < r.lead_time_dias:
            return "RIESGO DE ROTURA"
        return "STOCK SUFICIENTE"

    # Se crea después de lead time; por ahora se recalcula más adelante.
    o["situacion_stock"]=""

    # ---------------- LEAD TIME ----------------
    o["lead_time_dias"]=np.nan
    if oc is not None and ingresos is not None:
        oc=oc.copy(); ingresos=ingresos.copy()
        oc.columns=[str(x).strip() for x in oc.columns]
        ingresos.columns=[str(x).strip() for x in ingresos.columns]

        # OC: F.Docum., P. Emis, Número, Material
        def col_by(names, frame):
            for c in frame.columns:
                if norm(c) in [norm(x) for x in names]: return c
            return None

        co=col_by(["Material","C. Mat.","Código","Codigo"],oc)
        fo=col_by(["F. Docum.","F.Docum","Fecha","Fecha documento"],oc)
        po=col_by(["P. Emis","P.Emis","P Emis"],oc)
        no=col_by(["Número","Numero","N°","Nro"],oc)

        ci=col_by(["Material","C. Mat.","Código","Codigo"],ingresos)
        fi=col_by(["F. Almacén","F. Almacen","Fecha ingreso","Fecha","F. Recepción","F. Recepcion"],ingresos)
        pi=col_by(["P.OC","P. OC","P OC"],ingresos)
        ni=col_by(["Número OC","Numero OC","N° OC","Nro OC"],ingresos)

        if all([co,fo,po,no,ci,fi,pi,ni]):
            q=pd.DataFrame({
                "codigo":clean_id(oc[co]),
                "p_emis":clean_id(oc[po]),
                "numero":clean_id(oc[no]),
                "fecha_oc":dates(oc[fo])
            })
            r=pd.DataFrame({
                "codigo":clean_id(ingresos[ci]),
                "p_oc":clean_id(ingresos[pi]),
                "numero_oc":clean_id(ingresos[ni]),
                "fecha_ingreso":dates(ingresos[fi])
            })
            z=q.merge(r,left_on=["codigo","p_emis","numero"],right_on=["codigo","p_oc","numero_oc"],how="inner")
            z=z.dropna(subset=["fecha_oc","fecha_ingreso"])
            z=z[z.fecha_ingreso>=z.fecha_oc]
            z["lt"]=(z.fecha_ingreso-z.fecha_oc).dt.days
            # Una OC/material puede tener varios ingresos: primer ingreso válido.
            z=z.sort_values(["codigo","p_emis","numero","fecha_ingreso"]).drop_duplicates(
                ["codigo","p_emis","numero"],keep="first"
            )
            med=z.groupby("codigo")["lt"].median()
            o=o.drop(columns="lead_time_dias").merge(med.rename("lead_time_dias"),on="codigo",how="left")

    o["lead_time_dias"]=o.lead_time_dias.round(2)

    def situacion_stock_final(r):
        if r.stock_actual <= 0:
            if r.consumo_total <= 0:
                return "SIN STOCK – SIN CONSUMO"
            if r.meses_con_consumo >= 2 and (
                (pd.notna(r.dias_sin_movimiento) and r.dias_sin_movimiento <= 60)
                or r.tipo_consumo == "Frecuente"
            ):
                return "ROTURA DE STOCK"
            return "SIN STOCK – CONSUMO EVENTUAL"
        if pd.notna(r.cobertura_dias) and pd.notna(r.lead_time_dias) and r.lead_time_dias > 0 and r.cobertura_dias < r.lead_time_dias:
            return "RIESGO DE ROTURA"
        return "STOCK SUFICIENTE"

    o["situacion_stock"]=o.apply(situacion_stock_final,axis=1)

    # ---------------- DEMANDA ----------------
    def tipo(r):
        n=int(r.meses_con_consumo)
        if n==0:return "Sin consumo"
        if n==1:return "Eventual"
        if n<=5:return "Intermitente"
        return "Frecuente"
    o["tipo_consumo"]=o.apply(tipo,axis=1)

    def trend(r):
        if not month_cols:return "No concluyente"
        y=np.array([r[c] for c in month_cols],float)
        if np.count_nonzero(y)<4:return "No concluyente"
        if np.std(y)==0:return "Estable"
        slope=np.polyfit(np.arange(len(y)),y,1)[0]
        base=np.mean(y[y>0]) if np.any(y>0) else 1
        rel=abs(slope)/base
        if rel<.03:return "Estable"
        return "Creciente" if slope>0 else "Decreciente"
    o["tendencia"]=o.apply(trend,axis=1)

    def cv(r):
        y=np.array([r[c] for c in month_cols],float); y=y[y>0]
        if len(y)<2:return np.nan
        return np.std(y,ddof=1)/np.mean(y)
    o["cv_consumo"]=o.apply(cv,axis=1)
    o["variabilidad"]=pd.cut(o.cv_consumo,[-np.inf,.25,.60,np.inf],labels=["Baja","Media","Alta"]).astype(str)

    def anomaly(r):
        y=np.array([r[c] for c in month_cols],float); y=y[y>0]
        if len(y)<4:return "No concluyente"
        med=np.median(y); mad=np.median(np.abs(y-med))
        if mad==0:return "Pico anormal" if np.max(y)>=2*med else "No"
        score=np.max(np.abs(y-med)/(mad+1e-9))
        return "Pico anormal" if score>6 else "No"
    o["anomalia"]=o.apply(anomaly,axis=1)

    # ---------------- ABC / XYZ ----------------
    o=o.sort_values("valor_salidas",ascending=False).reset_index(drop=True)
    total=o.valor_salidas.sum()
    o["abc_acum_pct"]=o.valor_salidas.cumsum()/total*100 if total else 0
    o["abc"]=np.select([o.abc_acum_pct<=80,o.abc_acum_pct<=95],["A","B"],default="C")
    o["xyz"]=np.select([o.cv_consumo<=.25,o.cv_consumo<=.60],["X","Y"],default="Z")

    # ---------------- ABASTECIMIENTO ----------------
    # Cálculo del abastecimiento:
    # 1) Lead Time real = mediana del tiempo OC -> ingreso, por material.
    # 2) Si no hay Lead Time real cruzable, se usa un horizonte operativo
    #    de 30 días únicamente para poder calcular los parámetros; se informa
    #    claramente en el diagnóstico.
    # 3) Stock de seguridad = 1.65 * desviación mensual/30 * sqrt(Lead Time).
    # 4) Punto de pedido = consumo diario * Lead Time + stock de seguridad.
    # 5) Stock objetivo = punto de pedido + consumo de 30 días.
    # 6) Cantidad a abastecer = techo(stock objetivo - stock actual).
    #
    # Esto evita que Stock de Seguridad y Punto de Pedido queden vacíos
    # solamente porque no pudo cruzarse una OC con un ingreso.

    if month_cols:
        monthly_arr=o[month_cols].astype(float)
        monthly_sd=monthly_arr.std(axis=1,ddof=1).fillna(0)
    else:
        monthly_sd=pd.Series(0.0,index=o.index)

    lt_real=o["lead_time_dias"].copy()
    tiene_lt=lt_real.notna() & (lt_real>0)
    lt_modelo=lt_real.where(tiene_lt,30.0)

    sd_diaria=monthly_sd/30.0

    o["stock_seguridad"]=(1.65*sd_diaria*np.sqrt(lt_modelo)).fillna(0).clip(lower=0)
    o["punto_pedido"]=(o["consumo_diario"]*lt_modelo+o["stock_seguridad"]).fillna(0).clip(lower=0)
    o["stock_objetivo"]=(o["punto_pedido"]+o["consumo_diario"]*30).fillna(0).clip(lower=0)

    o["cantidad_a_comprar"]=np.ceil(
        np.maximum(o["stock_objetivo"]-o["stock_actual"],0)
    ).astype(int)

    # No forzar compras cuando no existe demanda suficiente para justificarla.
    o.loc[o["tipo_consumo"].isin(["Sin consumo","Eventual"]),"cantidad_a_comprar"]=0

    def metodo_abastecimiento(r):
        if r.tipo_consumo=="Sin consumo":
            return "Sin demanda histórica"
        if r.tipo_consumo=="Eventual":
            return "Demanda eventual: validar antes de comprar"
        if r.tendencia in ["Creciente","Decreciente"]:
            return "Demanda histórica + tendencia (regresión lineal) + stock de seguridad"
        if r.variabilidad=="Alta":
            return "Demanda histórica + stock de seguridad por variabilidad"
        return "Demanda histórica + stock de seguridad"

    o["metodologia"]=o.apply(metodo_abastecimiento,axis=1)

    def diagnostico_abastecimiento(r):
        p=[]
        if not pd.notna(r.lead_time_dias) or r.lead_time_dias<=0:
            p.append("Lead Time no calculable por cruce OC-Ingreso; se usa horizonte de 30 días para calcular el modelo")
        if r.stock_actual<=0 and r.consumo_total>0:
            p.append("stock cero con salidas")
        if r.tendencia!="No concluyente":
            p.append("tendencia "+r.tendencia.lower())
        if r.anomalia=="Pico anormal":
            p.append("pico mensual anormal")
        if pd.notna(r.dias_sin_movimiento) and r.dias_sin_movimiento>90:
            p.append("más de 90 días sin movimiento")
        return "; ".join(p) if p else "Sin anomalías relevantes detectadas."

    o["diagnostico"]=o.apply(diagnostico_abastecimiento,axis=1)

    def priority(r):
        if r.situacion_stock=="ROTURA DE STOCK":return "CRÍTICO"
        if r.stock_actual<=0 and r.consumo_total>0:return "CRÍTICO"
        if pd.notna(r.cobertura_dias) and pd.notna(r.lead_time_dias) and r.cobertura_dias<r.lead_time_dias:return "URGENTE"
        if r.cantidad_a_comprar>0:return "REVISAR"
        if r.tipo_consumo=="Sin consumo":return "SIN CONSUMO"
        if r.tipo_consumo=="Eventual":return "EVENTUAL"
        return "NORMAL"
    o["prioridad"]=o.apply(priority,axis=1)

    def method(r):
        if r.tipo_consumo=="Sin consumo":return "Sin demanda histórica"
        if r.tipo_consumo in ["Eventual","Intermitente"]:return "Demanda intermitente"
        if r.tendencia in ["Creciente","Decreciente"]:return "Regresión lineal evaluada"
        return "Promedio histórico + stock de seguridad"
    o["metodologia"]=o.apply(method,axis=1)

    def rec(r):
        q=int(r.cantidad_a_comprar)
        if r.situacion_stock=="ROTURA DE STOCK":
            return f"ROTURA DE STOCK: {r.meses_con_consumo} meses con consumo y stock actual 0.00. Priorizar abastecimiento de {q} {r.unidad_medida}."
        if r.prioridad=="CRÍTICO":
            return "Stock cero con salidas históricas: priorizar abastecimiento." if q==0 else f"Stock cero con consumo: abastecer {q} {r.unidad_medida}."
        if r.prioridad=="URGENTE":return f"Cobertura inferior al Lead Time: revisar/abastecer {q} {r.unidad_medida}."
        if r.tipo_consumo=="Eventual":return "Un solo mes con consumo: validar necesidad antes de comprar."
        if r.tipo_consumo=="Sin consumo":return "Sin consumo histórico: no comprar solo por stock cero."
        return "Stock suficiente según el modelo." if q==0 else f"Abastecer {q} {r.unidad_medida}."
    o["recomendacion"]=o.apply(rec,axis=1)

    return o,month_cols
