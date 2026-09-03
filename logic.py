
import re, unicodedata, numpy as np, pandas as pd

def norm(x):
    s = unicodedata.normalize("NFKD", str(x)).encode("ascii","ignore").decode()
    return re.sub(r"[^a-z0-9]+"," ",s.lower()).strip()

def find_col(df, names):
    m={norm(c):c for c in df.columns}
    for n in names:
        if norm(n) in m: return m[norm(n)]
    for n in names:
        nn=norm(n)
        for k,v in m.items():
            if nn and (nn in k or k in nn): return v
    return None

def read(file): file.seek(0); return pd.read_excel(file)

def codes_from_excel(file, col):
    try:
        import openpyxl
        file.seek(0); wb=openpyxl.load_workbook(file,data_only=True,read_only=True)
        ws=wb.active; heads=[str(c.value).strip() if c.value is not None else "" for c in next(ws.iter_rows())]
        if col not in heads: return None
        j=heads.index(col); out=[]
        for row in ws.iter_rows(min_row=2):
            c=row[j]; v=c.value
            if v is None: out.append(None); continue
            if isinstance(v,(int,float)) and not isinstance(v,bool):
                fmt=c.number_format or ""; z=re.search(r"0{2,}",fmt)
                out.append(str(int(v)).zfill(len(z.group(0))) if z else (str(int(v)) if float(v).is_integer() else str(v)))
            else: out.append(str(v).strip())
        return out
    except Exception: return None

def load_stock(file):
    d=read(file); d.columns=[str(c).strip() for c in d.columns]
    code=find_col(d,["codigo","código","cod","sku","item","material"])
    raw=codes_from_excel(file,code) if code else None
    d["codigo"]=raw if raw and len(raw)==len(d) else d[code]
    sc=find_col(d,["stock actual","stock","existencia","saldo"])
    cost=find_col(d,["costo unitario","coste unitario","costo","coste","precio unitario"])
    if sc is None and len(d.columns)>=4: sc=d.columns[3]
    if cost is None and len(d.columns)>=20: cost=d.columns[19]
    for x in ["descripcion","familia","unidad"]:
        c=find_col(d,[x,{"descripcion":"descripción","unidad":"unidad de medida"}.get(x,"")])
        d[x]=d[c] if c else np.nan
    d["stock_actual"]=pd.to_numeric(d[sc],errors="coerce").fillna(0)
    d["costo_unitario"]=pd.to_numeric(d[cost],errors="coerce").fillna(0)
    return d[["codigo","descripcion","familia","unidad","stock_actual","costo_unitario"]].drop_duplicates("codigo")

def load_salidas(file):
    d=read(file); d.columns=[str(c).strip() for c in d.columns]
    code=find_col(d,["codigo","código","cod","sku","item","material"])
    raw=codes_from_excel(file,code) if code else None
    d["codigo"]=raw if raw and len(raw)==len(d) else d[code]
    fc=find_col(d,["fecha","fecha salida","fecha de salida","fecha movimiento"])
    qc=find_col(d,["cantidad salida","cantidad de salida","salida","cantidad","qty","consumo"])
    vc=find_col(d,["valor salida","valor de salida","importe","monto"])
    if fc is None and len(d.columns)>=8: fc=d.columns[7]
    if qc is None: raise ValueError("No se encontró la columna de cantidad de salida.")
    d["fecha"]=pd.to_datetime(d[fc],errors="coerce",dayfirst=True)
    d["cantidad"]=pd.to_numeric(d[qc],errors="coerce")
    d["valor_salida"]=pd.to_numeric(d[vc],errors="coerce") if vc else np.nan
    for x in ["descripcion","familia","unidad"]:
        c=find_col(d,[x,{"descripcion":"descripción","unidad":"unidad de medida"}.get(x,"")])
        d[x]=d[c] if c else np.nan
    return d[["codigo","descripcion","familia","unidad","fecha","cantidad","valor_salida"]]

def load_oc(file):
    d=read(file); d.columns=[str(c).strip() for c in d.columns]
    code=find_col(d,["material","codigo","código","cod","sku","item"])
    fd=find_col(d,["f. docum.","f docum","fecha documento","fecha docum","fecha oc"])
    fg=find_col(d,["fecha guia","fecha guía","fecha recepcion","fecha recepción","fecha entrega"])
    est=find_col(d,["estado item","estado ítem","estado"])
    if not code or not fd or not fg: raise ValueError("Órdenes de compra debe tener Material, F. Docum. y Fecha Guía.")
    d["codigo"]=d[code].astype(str).str.strip()
    d["f_docum"]=pd.to_datetime(d[fd],errors="coerce",dayfirst=True)
    d["fecha_guia"]=pd.to_datetime(d[fg],errors="coerce",dayfirst=True)
    d["estado_item"]=d[est].astype(str).str.upper().str.strip() if est else "COMPRADO"
    return d[["codigo","f_docum","fecha_guia","estado_item"]]

def analyze(stock,sal,oc,horizon=1,z=1.65):
    sal=sal.dropna(subset=["codigo","fecha","cantidad"]).copy(); sal=sal[sal.cantidad>=0]
    if sal.empty: raise ValueError("No hay salidas válidas.")
    p0,p1=sal.fecha.min().to_period("M"),sal.fecha.max().to_period("M")
    periods=pd.period_range(p0,p1,freq="M")
    mon=sal.assign(periodo=sal.fecha.dt.to_period("M")).groupby(["codigo","periodo"],as_index=False).cantidad.sum().rename(columns={"cantidad":"consumo"})
    universe=pd.DataFrame({"codigo":sorted(set(stock.codigo.astype(str))|set(sal.codigo.astype(str)))})
    d=universe.merge(stock,on="codigo",how="left")
    ficha=sal.sort_values("fecha").groupby("codigo").agg(descripcion=("descripcion","last"),familia=("familia","last"),unidad=("unidad","last")).reset_index()
    d=d.merge(ficha,on="codigo",how="left",suffixes=("","_sal"))
    for c in ["descripcion","familia","unidad"]: d[c]=d[c].fillna(d[c+"_sal"]); d.drop(columns=[c+"_sal"],inplace=True)
    d.stock_actual=d.stock_actual.fillna(0); d.costo_unitario=d.costo_unitario.fillna(0)
    rows=[]
    for code,g in universe.merge(mon,on="codigo",how="left").groupby("codigo"):
        vals=[]
        for p in periods:
            q=g.loc[g.periodo==p,"consumo"].sum() if "periodo" in g else 0
            vals.append(float(q))
        a=np.array(vals); total=a.sum(); n=len(a); pos=int((a>0).sum()); mean=total/n
        std=float(np.std(a,ddof=1)) if n>1 else 0
        cv=std/mean if mean else 0
        if n>=2 and np.std(np.arange(n))>0:
            slope=float(np.polyfit(np.arange(n),a,1)[0])
            trend="Constante" if abs(slope)<max(mean*.01,1e-9) else ("Creciente" if slope>0 else "Decreciente")
            r2=float(np.corrcoef(np.arange(n),a)[0,1]**2) if np.std(a)>0 else 0
        else: trend="No concluyente"; r2=np.nan
        last=sal.loc[sal.codigo==code,"fecha"].max()
        anomaly="Pico anormal" if n>=3 and std>0 and a.max()>mean+2*std else "No"
        rows.append([code,total,pos,n-pos,mean,mean/30,std,cv,trend,r2,last, *vals])
    metric_cols=["codigo","consumo_total","meses_con_consumo","meses_sin_consumo","consumo_mensual_promedio","consumo_diario","desv_mensual","cv_consumo","tendencia","r2_regresion","ultimo_movimiento"]+[str(p) for p in periods]
    m=pd.DataFrame(rows,columns=metric_cols)
    d=d.merge(m,on="codigo",how="left")
    # valor de salidas
    s=sal.copy(); s["valor_calc"]=s.valor_salida.fillna(s.cantidad*d.set_index("codigo").costo_unitario.reindex(s.codigo).to_numpy())
    d=d.join(s.groupby("codigo").valor_calc.sum().rename("valor_salidas"),on="codigo"); d.valor_salidas=d.valor_salidas.fillna(0)
    d["valor_inventario"]=d.stock_actual*d.costo_unitario
    oc=oc.copy(); ok=oc[(oc.estado_item=="COMPRADO")&oc.f_docum.notna()&oc.fecha_guia.notna()].copy()
    ok["lt"]=(ok.fecha_guia-ok.f_docum).dt.days; ok=ok[(ok.lt>=0)&(ok.lt<=365)]
    lt=ok.groupby("codigo").lt.median().rename("lead_time") if not ok.empty else pd.Series(dtype=float)
    d=d.join(lt,on="codigo"); d["lead_time_estimado"]=d.lead_time.isna(); d["lead_time_utilizado"]=d.lead_time.fillna(12)
    d["stock_seguridad"]=z*d.desv_mensual*np.sqrt(d.lead_time_utilizado/30)
    fb=(d.stock_seguridad<=0)&(d.consumo_mensual_promedio>0); d.loc[fb,"stock_seguridad"]=d.loc[fb,"consumo_mensual_promedio"]*d.loc[fb,"lead_time_utilizado"]/30*.20
    d["punto_pedido"]=d.consumo_diario*d.lead_time_utilizado+d.stock_seguridad
    d["dias_cobertura"]=np.where(d.consumo_diario>0,d.stock_actual/d.consumo_diario,np.inf)
    for h in [1,2,3]:
        d[f"stock_objetivo_{h}m"]=d.consumo_mensual_promedio*h+d.stock_seguridad
        d[f"cantidad_abastecer_{h}m"]=np.ceil(np.maximum(0,d[f"stock_objetivo_{h}m"]-d.stock_actual))
        d[f"cobertura_post_{h}m"]=np.where(d.consumo_diario>0,(d.stock_actual+d[f"cantidad_abastecer_{h}m"])/d.consumo_diario,np.inf)
    d["stock_objetivo"]=d[f"stock_objetivo_{horizon}m"]; d["cantidad_abastecer"]=d[f"cantidad_abastecer_{horizon}m"]
    d["rotura_stock"]=(d.stock_actual<=0)&(d.consumo_total>0)
    d["situacion_stock"]=np.select([d.rotura_stock,d.stock_actual<=d.punto_pedido],["ROTURA DE STOCK","POR DEBAJO DEL PUNTO DE PEDIDO"],default="STOCK SUFICIENTE")
    d["momento_compra"]=np.where(d.stock_actual<=d.punto_pedido,"COMPRAR AHORA","NO COMPRAR AÚN")
    d["meses_analizados"]=len(periods); d["tipo_consumo"]=np.select([d.meses_con_consumo<=1,d.meses_con_consumo<=3,d.meses_con_consumo/d.meses_analizados>=.67],["Eventual","Intermitente","Frecuente"],default="Intermitente") if "meses_analizados" in d else "Intermitente"
    d["nivel_variabilidad"]=np.select([d.cv_consumo<=.5,d.cv_consumo<=1],["Baja","Media"],default="Alta")
    d["anomalía_de_consumo"]=d.get("anomalía_de_consumo","No")
    # ABC por valor de salidas; XYZ por CV
    totalv=d.valor_salidas.sum(); d["abc_acum_pct"]=np.nan
    if totalv>0:
        r=d.sort_values("valor_salidas",ascending=False).copy(); r["abc_acum_pct"]=r.valor_salidas.cumsum()/totalv*100
        r["clasificacion_abc"]=np.select([r.abc_acum_pct<=80,r.abc_acum_pct<=95],["A","B"],default="C")
        d=d.drop(columns=["abc_acum_pct","clasificacion_abc"],errors="ignore").merge(r[["codigo","abc_acum_pct","clasificacion_abc"]],on="codigo",how="left")
    else: d["clasificacion_abc"]="C"
    d["clasificacion_xyz"]=np.select([d.cv_consumo<=.5,d.cv_consumo<=1],["X","Y"],default="Z")
    d["prioridad"]=np.select([d.rotura_stock,(d.stock_actual<=d.punto_pedido)&(d.dias_cobertura<d.lead_time_utilizado)],["CRÍTICO","ALTO"],default="REVISAR")
    d["diagnostico"]=d.apply(lambda r: ("stock cero con salidas; rotura de stock" if r.rotura_stock else ("stock por debajo del punto de pedido" if r.stock_actual<=r.punto_pedido else "stock por encima del punto de pedido"))+f"; tendencia {r.tendencia.lower()}",axis=1)
    d["recomendacion"]=d.apply(lambda r:f"{'COMPRAR AHORA' if r.momento_compra=='COMPRAR AHORA' else 'NO COMPRAR AÚN'}: {r.cantidad_abastecer:.0f} {r.unidad or ''} para {horizon} mes(es). Cobertura proyectada {r[f'cobertura_post_{horizon}m']:.1f} días.",axis=1)
    return d,mon,periods
