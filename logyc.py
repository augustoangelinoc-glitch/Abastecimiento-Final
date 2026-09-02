
import math, re
import numpy as np
import pandas as pd

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())

def find_col(df, candidates):
    exact = {norm(c): c for c in df.columns}
    for x in candidates:
        if norm(x) in exact:
            return exact[norm(x)]
    for c in df.columns:
        nc = norm(c)
        if any(norm(x) in nc for x in candidates):
            return c
    return None

def to_num(s):
    def f(v):
        if pd.isna(v): return np.nan
        x=str(v).strip().replace("S/","").replace("$","").replace(" ","")
        if not x or x.lower() in ("nan","none","null"): return np.nan
        if "," in x and "." in x:
            x = x.replace(".","").replace(",",".") if x.rfind(",")>x.rfind(".") else x.replace(",","")
        elif "," in x:
            p=x.split(",")
            x="".join(p[:-1])+"."+p[-1] if len(p[-1])<=2 else "".join(p)
        try: return float(x)
        except: return np.nan
    return s.map(f)

def dates(s):
    return pd.to_datetime(s, errors="coerce", dayfirst=True)

def clean_code(s):
    return s.astype(str).str.strip().str.replace(r"\.0$","",regex=True).replace({"nan":"","None":""})

def calculate(stock, salidas, oc=None, ingresos=None):
    # ===== STOCK ACTUAL =====
    stock=stock.copy(); salidas=salidas.copy()
    stock.columns=[str(x).strip() for x in stock.columns]
    salidas.columns=[str(x).strip() for x in salidas.columns]

    code_s=stock.columns[0]
    # ACUERDO: descripción = columna B de Stock Actual
    desc_s=stock.columns[1]
    fam_s=find_col(stock,["familia","grupo","categoria","categoría"])
    um_s=find_col(stock,["unidadmedida","unidad","um"])
    st_s=find_col(stock,["stockactual","stock","existencia","saldo"])
    cost_s=find_col(stock,["costounitario","costounitarioactual","costo","precio"])
    val_s=find_col(stock,["valorinventario","valorizado","valorstock"])

    b=pd.DataFrame({
        "codigo":clean_code(stock[code_s]),
        "descripcion":stock[desc_s].fillna("").astype(str).str.strip(),
        "familia":stock[fam_s].fillna("").astype(str).str.strip() if fam_s else "",
        "unidad_medida":stock[um_s].fillna("").astype(str).str.strip() if um_s else "",
        "stock_actual":to_num(stock[st_s]).fillna(0) if st_s else 0.0,
        "costo_unitario":to_num(stock[cost_s]) if cost_s else np.nan
    })
    if val_s: b["valor_inventario"]=to_num(stock[val_s])
    else: b["valor_inventario"]=b.stock_actual*b.costo_unitario
    b=b[b.codigo!=""].drop_duplicates("codigo")

    # ===== SALIDAS =====
    code_o=find_col(salidas,["codigo","códigomaterial","material","item","articulo","artículo"]) or salidas.columns[0]
    # ACUERDO: descripción de Salidas = columna AT
    desc_o=salidas.columns[45] if len(salidas.columns)>45 else find_col(salidas,["descripcion","descripción"])
    date_o=find_col(salidas,["fecha","fechasalida","fechadocumento","fechaemision"])
    qty_o=find_col(salidas,["cantidad","cant","cantidadsalida","salida"])
    val_o=find_col(salidas,["valorsalida","valortotal","importe","valor"])
    cst_o=find_col(salidas,["costounitario","costo","precio"])

    s=pd.DataFrame({
        "codigo":clean_code(salidas[code_o]),
        "descripcion_salida":salidas[desc_o].fillna("").astype(str).str.strip() if desc_o else "",
        "fecha":dates(salidas[date_o]) if date_o else pd.NaT,
        "cantidad":to_num(salidas[qty_o]).fillna(0) if qty_o else 0.0
    })
    s["valor"]=to_num(salidas[val_o]) if val_o else (s.cantidad*to_num(salidas[cst_o]) if cst_o else np.nan)
    s=s[s.codigo!=""]

    # ===== MESES =====
    if s.fecha.notna().any():
        minm=s.fecha.min().to_period("M"); maxm=s.fecha.max().to_period("M")
        periods=pd.period_range(minm,maxm,freq="M")
        p=s.dropna(subset=["fecha"]).assign(periodo=lambda x:x.fecha.dt.to_period("M")).pivot_table(
            index="codigo",columns="periodo",values="cantidad",aggfunc="sum",fill_value=0)
        p=p.reindex(columns=periods,fill_value=0)
    else:
        periods=pd.PeriodIndex([],freq="M"); p=pd.DataFrame()

    agg=s.groupby("codigo").agg(consumo_total=("cantidad","sum"),valor_salidas=("valor","sum"),ultimo_movimiento=("fecha","max")).reset_index()
    o=b.merge(agg,on="codigo",how="left")
    o["consumo_total"]=o.consumo_total.fillna(0)
    o["valor_salidas"]=o.valor_salidas.fillna(0)
    o["ultimo_movimiento"]=pd.to_datetime(o.ultimo_movimiento,errors="coerce")

    month_cols=[]
    for per in periods:
        col=f"{per.month:02d}-{per.year}"
        month_cols.append(col)
        o[col]=o.codigo.map(p[per] if per in p.columns else pd.Series(dtype=float)).fillna(0)

    n=len(periods)
    o["meses_con_consumo"]=(o[month_cols]>0).sum(axis=1) if month_cols else 0
    o["meses_sin_consumo"]=n-o["meses_con_consumo"]
    o["consumo_mensual_prom"]=o.consumo_total/n if n else 0.0

    days=(s.fecha.max()-s.fecha.min()).days+1 if s.fecha.notna().any() else 365
    o["consumo_diario"]=o.consumo_total/days
    today=pd.Timestamp.today().normalize()
    o["dias_sin_movimiento"]=np.where(o.ultimo_movimiento.notna(),(today-o.ultimo_movimiento).dt.days,np.nan)
    o["cobertura_dias"]=np.where(o.consumo_diario>0,o.stock_actual/o.consumo_diario,np.nan)

    # ===== LEAD TIME REAL: OC -> INGRESO =====
    o["lead_time_dias"]=np.nan
    if oc is not None and ingresos is not None:
        oc=oc.copy(); ingresos=ingresos.copy()
        co=find_col(oc,["codigo","material","item","articulo","artículo"]) or oc.columns[0]
        fo=find_col(oc,["fechaoc","fecha","fechaemision","fechaemisión"])
        no=find_col(oc,["numerooc","nrooc","nroorden","ordencompra","oc","numero"])
        ci=find_col(ingresos,["codigo","material","item","articulo","artículo"]) or ingresos.columns[0]
        fi=find_col(ingresos,["fechaingreso","fecharecepcion","fecharecepción","fecha","fecharecepcion"])
        ni=find_col(ingresos,["numerooc","nrooc","nroorden","ordencompra","oc","numero"])
        if fo and no and fi and ni:
            q=pd.DataFrame({"codigo":clean_code(oc[co]),"oc":oc[no].astype(str).str.strip(),"fecha_oc":dates(oc[fo])})
            r=pd.DataFrame({"codigo":clean_code(ingresos[ci]),"oc":ingresos[ni].astype(str).str.strip(),"fecha_ingreso":dates(ingresos[fi])})
            z=q.merge(r,on=["codigo","oc"],how="inner").dropna()
            z=z[z.fecha_ingreso>=z.fecha_oc].sort_values(["codigo","oc","fecha_ingreso"])
            # primera recepción de cada OC/material
            z=z.drop_duplicates(["codigo","oc"],keep="first")
            med=z.assign(lt=(z.fecha_ingreso-z.fecha_oc).dt.days).groupby("codigo")["lt"].median()
            o=o.drop(columns="lead_time_dias").merge(med.rename("lead_time_dias"),on="codigo",how="left")
    o["lead_time_dias"]=o.lead_time_dias.round(2)

    # ===== DEMANDA =====
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
        if rel<0.03:return "Estable"
        return "Creciente" if slope>0 else "Decreciente"

    o["tendencia"]=o.apply(trend,axis=1)

    def cv(r):
        y=np.array([r[c] for c in month_cols],float)
        y=y[y>0]
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

    # ===== ABC / XYZ =====
    o=o.sort_values("valor_salidas",ascending=False).reset_index(drop=True)
    total=o.valor_salidas.sum()
    o["abc_acum_pct"]=o.valor_salidas.cumsum()/total*100 if total else 0
    o["abc"]=np.select([o.abc_acum_pct<=80,o.abc_acum_pct<=95],["A","B"],default="C")
    o["xyz"]=np.select([o.cv_consumo<=.25,o.cv_consumo<=.60],["X","Y"],default="Z")

    # ===== ABASTECIMIENTO =====
    # Para materiales con demanda regular: demanda durante LT + SS.
    # SS = z * desviación estándar mensual transformada a LT.
    def ss(r):
        y=np.array([r[c] for c in month_cols],float)
        if len(y)<2 or not pd.notna(r.lead_time_dias) or r.lead_time_dias<=0:return 0.0
        sd=np.std(y,ddof=1)
        return max(0,1.65*(sd/math.sqrt(30))*math.sqrt(r.lead_time_dias))
    o["stock_seguridad"]=o.apply(ss,axis=1)
    o["punto_pedido"]=o.consumo_diario*o.lead_time_dias.fillna(0)+o.stock_seguridad
    o["stock_objetivo"]=o.punto_pedido+o.consumo_diario*30
    o["cantidad_a_comprar"]=np.ceil(np.maximum(o.stock_objetivo-o.stock_actual,0)).astype(int)

    # No extrapolar automáticamente un único consumo o ausencia total de demanda.
    o.loc[o.tipo_consumo.isin(["Sin consumo","Eventual"]),"cantidad_a_comprar"]=0

    def priority(r):
        if r.stock_actual<=0 and r.consumo_total>0:return "CRÍTICO"
        if pd.notna(r.cobertura_dias) and pd.notna(r.lead_time_dias) and r.cobertura_dias<r.lead_time_dias:return "URGENTE"
        if r.cantidad_a_comprar>0:return "REVISAR"
        if r.tipo_consumo=="Sin consumo":return "SIN CONSUMO"
        if r.tipo_consumo=="Eventual":return "EVENTUAL"
        return "NORMAL"
    o["prioridad"]=o.apply(priority,axis=1)

    def method(r):
        if r.tipo_consumo=="Sin consumo":return "Sin demanda"
        if r.tipo_consumo in ["Eventual","Intermitente"]:return "Demanda intermitente"
        if r.tendencia in ["Creciente","Decreciente"]:return "Regresión lineal evaluada"
        return "Promedio histórico + stock de seguridad"
    o["metodologia"]=o.apply(method,axis=1)

    def rec(r):
        q=int(r.cantidad_a_comprar)
        if r.prioridad=="CRÍTICO":
            return "Stock cero con salidas históricas: priorizar abastecimiento." if q==0 else f"Stock cero con consumo: abastecer {q} {r.unidad_medida}."
        if r.prioridad=="URGENTE":
            return f"Cobertura inferior al Lead Time: revisar/abastecer {q} {r.unidad_medida}."
        if r.tipo_consumo=="Eventual":return "Un solo mes con consumo: validar necesidad antes de comprar."
        if r.tipo_consumo=="Sin consumo":return "Sin consumo histórico: no comprar solo por stock cero."
        return "Stock suficiente según el modelo." if q==0 else f"Abastecer {q} {r.unidad_medida}."
    o["recomendacion"]=o.apply(rec,axis=1)

    def diag(r):
        p=[]
        if r.stock_actual<=0 and r.consumo_total>0:p.append("stock cero con salidas")
        if r.tendencia!="No concluyente":p.append("tendencia "+r.tendencia.lower())
        if r.anomalia=="Pico anormal":p.append("pico mensual anormal")
        if pd.notna(r.dias_sin_movimiento) and r.dias_sin_movimiento>90:p.append("más de 90 días sin movimiento")
        return "; ".join(p) if p else "Sin anomalías relevantes detectadas."
    o["diagnostico"]=o.apply(diag,axis=1)

    return o, month_cols
