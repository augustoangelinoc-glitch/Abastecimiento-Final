import io, re, unicodedata
import numpy as np
import pandas as pd

def norm(x):
    s = unicodedata.normalize("NFKD", str(x)).encode("ascii","ignore").decode().lower().strip()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def find_col(df, aliases, required=False):
    mp = {norm(c): c for c in df.columns}
    for a in aliases:
        if norm(a) in mp: return mp[norm(a)]
    for a in aliases:
        na=norm(a)
        for n,c in mp.items():
            if na and (na in n or n in na): return c
    if required: raise ValueError(f"No se encontró columna requerida: {aliases}")
    return None

def read(file):
    return pd.read_excel(file)

def codes(s):
    return s.astype(str).str.strip().replace({"nan":np.nan,"None":np.nan})

def load_stock(file):
    d=read(file)
    c=find_col(d,["Código","Codigo","Material","Item"],True)
    stock=find_col(d,["Stock Actual","Stock","Sistema","Existencia","Saldo"],True)
    desc=find_col(d,["Descripción","Descripcion","Nombre"],False)
    fam=find_col(d,["Familia","Grupo","Categoria"],False)
    um=find_col(d,["U.M.","UM","Unidad de Medida","Unidad"],False)
    ck=find_col(d,["C. Kardex","Costo Kardex","Kardex"],False)
    cc=find_col(d,["Costo Cierre Mes","Costo Cierre"],False)
    tipo=find_col(d,["Tipo"],False)
    out=pd.DataFrame({
        "codigo":codes(d[c]), "descripcion":d[desc] if desc else np.nan,
        "familia":d[fam] if fam else np.nan, "unidad":d[um] if um else np.nan,
        "stock_actual":pd.to_numeric(d[stock],errors="coerce"),
        "costo_kardex":pd.to_numeric(d[ck],errors="coerce") if ck else 0,
        "costo_cierre":pd.to_numeric(d[cc],errors="coerce") if cc else 0,
        "tipo":d[tipo] if tipo else np.nan
    })
    # Regla acordada: C. Kardex es la referencia principal; si falta, usar Cierre.
    out["costo_unitario"]=np.where(out["costo_kardex"]>0,out["costo_kardex"],
                                   np.where(out["costo_cierre"]>0,out["costo_cierre"],np.nan))
    out["tipo_costo"]=np.where(out["costo_unitario"].notna(),"VALORIZABLE","SIN COSTO / POSIBLE CONSIGNACION")
    return out

def load_salidas(file):
    d=read(file)
    c=find_col(d,["Código","Codigo","Material","Item"],True)
    f=find_col(d,["Fecha","Fecha Salida","Fecha de Salida"],True)
    q=find_col(d,["Cantidad Salida","Cantidad de Salida","Salida","Consumo","Unidades"],True)
    desc=find_col(d,["Descripción","Descripcion"],False)
    fam=find_col(d,["Familia","Grupo","Categoria"],False)
    um=find_col(d,["U.M.","UM","Unidad","Unidad de Medida"],False)
    return pd.DataFrame({"codigo":codes(d[c]),"descripcion":d[desc] if desc else np.nan,
        "familia":d[fam] if fam else np.nan,"unidad":d[um] if um else np.nan,
        "fecha":pd.to_datetime(d[f],errors="coerce",dayfirst=True),
        "cantidad":pd.to_numeric(d[q],errors="coerce")})

def load_oc(file):
    d=read(file)
    pe=find_col(d,["P. Emis","P Emis"],True); no=find_col(d,["Número","Numero","N°"],True)
    mat=find_col(d,["Material","Código","Codigo","Item"],True)
    fecha=find_col(d,["Fecha Creacion","Fecha Creación","Fecha OC"],False)
    prov=find_col(d,["Razon Social","Razón Social","Proveedor"],False)
    qty=find_col(d,["Unidades","Cantidad","Qty"],False)
    saldo=find_col(d,["Saldo","Saldo Item","Cantidad Pendiente"],False)
    precio=find_col(d,["Precio","Valor Unitario","Costo"],False)
    estado=find_col(d,["Estado Item","Estado"],False)
    return pd.DataFrame({
        "oc_tipo":codes(d[pe]),"numero_oc":codes(d[no]),
        "oc_id":codes(d[pe])+"-"+codes(d[no]),
        "codigo":codes(d[mat]),"fecha_oc":pd.to_datetime(d[fecha],errors="coerce",dayfirst=True) if fecha else pd.NaT,
        "proveedor":d[prov] if prov else np.nan,"cantidad_oc":pd.to_numeric(d[qty],errors="coerce") if qty else np.nan,
        "saldo_oc":pd.to_numeric(d[saldo],errors="coerce") if saldo else np.nan,
        "precio_oc":pd.to_numeric(d[precio],errors="coerce") if precio else np.nan,
        "estado_oc":d[estado] if estado else np.nan})

def load_ingresos(file):
    d=read(file)
    pe=find_col(d,["P. Emis","P Emis"],True); no=find_col(d,["Número","Numero","N°"],True)
    po=find_col(d,["P.OC","P OC","P. O.C."],True); noc=find_col(d,["Número OC","Numero OC","N OC"],True)
    mat=find_col(d,["Material","Código","Codigo","Item"],True)
    fi=find_col(d,["F.Contab","F Contab","Fecha Contable"],False)
    fo=find_col(d,["Fecha OC","F.OC","F OC"],False)
    qty=find_col(d,["Unidades","Cantidad","Qty"],False)
    prov=find_col(d,["Razon Social","Razón Social","Proveedor"],False)
    obs=find_col(d,["Observación","Observacion","Comentario"],False)
    return pd.DataFrame({
        "ingreso_id":codes(d[pe])+"-"+codes(d[no]),
        "oc_tipo":codes(d[po]),"numero_oc":codes(d[noc]),
        "oc_id":codes(d[po])+"-"+codes(d[noc]),"codigo":codes(d[mat]),
        "fecha_ingreso":pd.to_datetime(d[fi],errors="coerce",dayfirst=True) if fi else pd.NaT,
        "fecha_oc":pd.to_datetime(d[fo],errors="coerce",dayfirst=True) if fo else pd.NaT,
        "cantidad_ingresada":pd.to_numeric(d[qty],errors="coerce") if qty else np.nan,
        "proveedor":d[prov] if prov else np.nan,
        "observacion":d[obs] if obs else np.nan})

def demand_metrics(s):
    valid=s.dropna(subset=["fecha","cantidad"]).copy()
    valid=valid[valid["cantidad"]>=0]
    if valid.empty:
        return pd.DataFrame(columns=["codigo","consumo_mensual","consumo_reciente","cv","tendencia"])
    lo,hi=valid.fecha.min(),valid.fecha.max()
    periods=pd.period_range(lo.to_period("M"),hi.to_period("M"),freq="M")
    p=valid.assign(periodo=valid.fecha.dt.to_period("M")).groupby(["codigo","periodo"])["cantidad"].sum().unstack(fill_value=0)
    p=p.reindex(columns=periods,fill_value=0)
    rows=[]
    for code,row in p.iterrows():
        vals=row.astype(float).values
        mean=float(vals.mean())
        std=float(vals.std(ddof=0))
        cv=std/mean if mean>0 else np.nan
        recent=float(vals[-min(3,len(vals)):].mean()) if len(vals) else 0
        if len(vals)>=3:
            x=np.arange(len(vals)); slope=float(np.polyfit(x,vals,1)[0])
            trend="CRECIENTE" if slope>0.05*max(mean,1) else ("DECRECIENTE" if slope<-0.05*max(mean,1) else "ESTABLE")
        else: trend="INSUFICIENTE"
        rows.append([code,mean,recent,cv,trend])
    return pd.DataFrame(rows,columns=["codigo","consumo_mensual","consumo_reciente","cv","tendencia"])

def abc_class(a):
    a=a.sort_values("valor_consumo",ascending=False).copy()
    total=a["valor_consumo"].sum()
    if total<=0:
        a["abc"]="SIN ABC"; return a
    a["cum"]=a["valor_consumo"].cumsum()/total
    a["abc"]=np.select([a["cum"]<=.80,a["cum"]<=.95],["A","B"],default="C")
    return a

def xyz_class(df):
    x=df["cv"]
    df["xyz"]=np.select([x.isna(),x<=0.50,x<=1.00],["Z","X","Y"],default="Z")
    df.loc[df["consumo_mensual"]<=0,"xyz"]="Z"
    return df

def build_oc_tracking(oc, ing):
    o=oc.groupby(["oc_id","codigo"],dropna=False).agg(
        fecha_oc=("fecha_oc","min"),proveedor=("proveedor","first"),
        cantidad_oc=("cantidad_oc","sum"),saldo_oc=("saldo_oc","sum")
    ).reset_index()
    i=ing.groupby(["oc_id","codigo"],dropna=False).agg(
        primera_recepcion=("fecha_ingreso","min"),ultima_recepcion=("fecha_ingreso","max"),
        cantidad_ingresada=("cantidad_ingresada","sum"),ingresos=("ingreso_id","nunique")
    ).reset_index()
    t=o.merge(i,on=["oc_id","codigo"],how="left")
    t["cantidad_ingresada"]=t["cantidad_ingresada"].fillna(0)
    t["pendiente_calculado"]=(t["cantidad_oc"].fillna(0)-t["cantidad_ingresada"]).clip(lower=0)
    t["lead_time_dias"]=(t["primera_recepcion"]-t["fecha_oc"]).dt.days
    t["lead_time_completo_dias"]=(t["ultima_recepcion"]-t["fecha_oc"]).dt.days
    t["entrega_parcial"]=t["cantidad_ingresada"]+1e-9<t["cantidad_oc"]
    return t

def build_analysis(stock,sal,oc,ing):
    dm=demand_metrics(sal)
    tr=build_oc_tracking(oc,ing)
    lt=tr.groupby("codigo")["lead_time_dias"].median().rename("lead_time_mediano")
    pend=tr.groupby("codigo")["pendiente_calculado"].sum().rename("oc_pendiente")
    out=stock.merge(dm,on="codigo",how="left").merge(lt,on="codigo",how="left").merge(pend,on="codigo",how="left")
    for c in ["consumo_mensual","consumo_reciente","cv"]:
        out[c]=out[c].fillna(0 if c!="cv" else np.nan)
    out["valor_inventario"]=np.where(out["costo_unitario"].notna(),out["stock_actual"].fillna(0)*out["costo_unitario"],np.nan)
    out["valor_consumo"]=np.where(out["costo_unitario"].notna(),out["consumo_mensual"]*out["costo_unitario"],0)
    out=abc_class(out)
    out=xyz_class(out)
    daily=out["consumo_mensual"]/30
    out["cobertura_dias"]=np.where(daily>0,out["stock_actual"]/daily,np.inf)
    # Protección basada en variabilidad observada; sin porcentaje fijo global.
    out["stock_seguridad"]=np.where(
        out["consumo_mensual"]>0,
        out["cv"].fillna(0).clip(lower=0)*out["consumo_mensual"]*0.5,
        0
    )
    lt=out["lead_time_mediano"].fillna(0).clip(lower=0)
    out["punto_pedido"]=daily*lt+out["stock_seguridad"]
    # Objetivo = demanda durante LT + un ciclo de 30 días + seguridad.
    out["stock_objetivo"]=daily*(lt+30)+out["stock_seguridad"]
    out["cantidad_recomendada"]=(out["stock_objetivo"]-out["stock_actual"]-out["oc_pendiente"].fillna(0)).clip(lower=0)
    # Sin demanda
    out["situacion"]="NORMAL"
    out.loc[(out["stock_actual"]<=0)&(out["consumo_mensual"]>0)&(out["oc_pendiente"]<=0),"situacion"]="RIESGO DE QUIEBRE"
    out.loc[(out["consumo_mensual"]<=0)&(out["stock_actual"]>0),"situacion"]="SIN MOVIMIENTO"
    out.loc[(out["consumo_mensual"]>0)&(out["stock_actual"]<out["punto_pedido"])&(out["oc_pendiente"]>0),"situacion"]="ESPERAR OC / REVISAR"
    out.loc[(out["consumo_mensual"]>0)&(out["stock_actual"]<out["punto_pedido"])&(out["oc_pendiente"]<=0),"situacion"]="PLANIFICAR COMPRA"
    out.loc[(out["consumo_mensual"]>0)&(out["cobertura_dias"]>365),"situacion"]="EXCESO"
    out.loc[(out["consumo_mensual"]<=0)&(out["stock_actual"]<=0),"situacion"]="SIN STOCK Y SIN DEMANDA"
    out["riesgo"]="BAJO"
    out.loc[out["situacion"].isin(["RIESGO DE QUIEBRE"]),"riesgo"]="ALTO"
    out.loc[out["situacion"].isin(["PLANIFICAR COMPRA","ESPERAR OC / REVISAR"]),"riesgo"]="MEDIO"
    out["prioridad"]=4
    out.loc[out["riesgo"]=="ALTO","prioridad"]=1
    out.loc[(out["riesgo"]=="MEDIO")&(out["situacion"]=="PLANIFICAR COMPRA"),"prioridad"]=2
    out.loc[(out["riesgo"]=="MEDIO")&(out["situacion"]=="ESPERAR OC / REVISAR"),"prioridad"]=3
    out["explicacion"]="Situación normal según demanda, stock y abastecimiento pendiente."
    out.loc[out["situacion"]=="RIESGO DE QUIEBRE","explicacion"]="Stock insuficiente/no disponible frente a demanda observada y no hay OC pendiente suficiente."
    out.loc[out["situacion"]=="PLANIFICAR COMPRA","explicacion"]="La posición de inventario queda por debajo del nivel de reposición estimado y no existe OC pendiente suficiente."
    out.loc[out["situacion"]=="ESPERAR OC / REVISAR","explicacion"]="Existe una necesidad, pero ya hay abastecimiento pendiente; revisar fecha y cumplimiento antes de comprar nuevamente."
    out.loc[out["situacion"]=="SIN MOVIMIENTO","explicacion"]="Existe stock pero no se observa consumo en el periodo analizado."
    out.loc[out["situacion"]=="EXCESO","explicacion"]="La cobertura estimada supera un año; requiere revisión antes de generar nuevas compras."
    out.loc[out["tipo_costo"].str.contains("SIN COSTO",na=False),"explicacion"] += " El material no tiene costo valorizable; participa en demanda y riesgo, pero no en valor económico."
    return out

def quality_report(stock,sal,oc,ing):
    q={}
    q["Materiales en stock"]=int(stock.codigo.nunique())
    q["Materiales con salidas"]=int(sal.codigo.nunique())
    q["Materiales con OC"]=int(oc.codigo.nunique())
    q["Materiales con ingresos"]=int(ing.codigo.nunique())
    q["Salidas sin código"]=int(sal.codigo.isna().sum())
    q["Salidas con fecha inválida"]=int(sal.fecha.isna().sum())
    q["Salidas con cantidad inválida"]=int(sal.cantidad.isna().sum()+ (sal.cantidad<0).sum())
    q["OC sin código"]=int(oc.codigo.isna().sum())
    q["Ingresos sin OC identificable"]=int(ing.oc_id.isna().sum())
    q["Materiales sin costo"]=int(stock.costo_unitario.isna().sum())
    q["Stock sin salidas"]=int(len(set(stock.codigo.dropna())-set(sal.codigo.dropna())))
    q["Salidas sin stock"]=int(len(set(sal.codigo.dropna())-set(stock.codigo.dropna())))
    return q

def export_results(analysis,tracking,q):
    b=io.BytesIO()
    with pd.ExcelWriter(b,engine="openpyxl") as w:
        analysis.to_excel(w,index=False,sheet_name="Analisis")
        tracking.to_excel(w,index=False,sheet_name="OC_Ingresos")
        pd.DataFrame({"Indicador":list(q.keys()),"Valor":list(q.values())}).to_excel(w,index=False,sheet_name="Calidad")
        analysis[analysis["cantidad_recomendada"]>0].sort_values(["prioridad","cantidad_recomendada"],ascending=[True,False]).to_excel(w,index=False,sheet_name="Compras")
    return b.getvalue()
