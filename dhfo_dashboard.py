#!/usr/bin/env python3
"""
DHFO Market Dashboard — auto-refreshing macro & markets board.
Rebuilt from "DHFO Dashboard - RP | V2 [ARCHIVED]".

Live data  : Yahoo Finance (indices, FX, commodities, US yields) via yfinance.
Manual data: India macro rates, valuations, FII/DII, a few global series that
             have no free live feed -> read from manual_values.json (editable,
             each with an "as_of" date). Refresh these via search on schedule.

Output     : DHFO-Market-Dashboard.html  (premium, brand-styled, self-contained)

Run: python3 dhfo_dashboard.py
"""

import os, json, math, datetime as dt, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
MANUAL_JSON = os.path.join(HERE, "macro_values.json")
OUT_HTML    = os.path.join(HERE, "DHFO.html")
OUT_INDEX   = os.path.join(HERE, "index.html")   # for GitHub Pages hosting
RELOAD_SECS = int(os.environ.get("DHFO_RELOAD_SECS", "30"))  # 0 = no auto-reload
FETCH_DIAG = ""  # short live-fetch diagnostic, surfaced as a <meta> tag

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# ----------------------------------------------------------------------------
# INDICATOR REGISTRY  (order == render order; section headers via 'section')
# kind: yahoo | ratio | manual
# fmt : level | fx | pct | num2 | num0
# ----------------------------------------------------------------------------
LB_TO_TON = 2204.62

IND = [
 # --- INDIA MACRO & RATES -------------------------------------------------
 dict(section="India Macro & Rates"),
 dict(name="Wholesale Price Index (INR)", label="WPI (Y-o-Y)",            kind="manual", fmt="pct"),
 dict(name="Consumer Price Index",         label="CPI (Y-o-Y)",           kind="manual", fmt="pct"),
 dict(name="Cash Reserve Ratio",           label="CRR",                   kind="manual", fmt="pct"),
 dict(name="Statutory Liquidity Ratio",    label="SLR",                   kind="manual", fmt="pct"),
 dict(name="Repo Rate",                    label="Repo Rate",             kind="manual", fmt="pct"),
 dict(name="Standing Deposit Facility",    label="SDF Rate",              kind="manual", fmt="pct"),
 dict(name="Bank Rate",                    label="Bank Rate",             kind="manual", fmt="pct"),
 dict(name="91 day T-bill",                label="91 day T-bill (YTM)",   kind="manual", fmt="pct"),
 dict(name="182 day T-bill",               label="182 day T-bill (YTM)",  kind="manual", fmt="pct"),
 dict(name="364 day T-bill",               label="364 day T-bill (YTM)",  kind="manual", fmt="pct"),
 dict(name="10-yr G-Sec Yield",            label="10-yr G-Sec Yield",     kind="manual", fmt="pct"),

 # --- INDIAN INDICES ------------------------------------------------------
 dict(section="Indian Indices"),
 dict(name="Sensex 30",          label="BSE SENSEX",         kind="yahoo", tk="^BSESN",              fmt="level"),
 dict(name="Nifty 50",           label="NIFTY 50",           kind="yahoo", tk="^NSEI",               fmt="level"),
 dict(name="Nifty Bank",         label="NIFTY BANK",         kind="yahoo", tk="^NSEBANK",            fmt="level"),
 dict(name="Nifty Next 50",      label="NIFTY NEXT 50",      kind="yahoo", tk="^NSMIDCP",           fmt="level"),
 dict(name="Nifty 100",          label="NIFTY 100",          kind="yahoo", tk="^CNX100",             fmt="level"),
 dict(name="Nifty 200",          label="NIFTY 200",          kind="yahoo", tk="^CNX200",             fmt="level"),
 dict(name="Nifty 500",          label="NIFTY 500",          kind="yahoo", tk="^CRSLDX",             fmt="level"),
 dict(name="Nifty Midcap 100",   label="NIFTY MIDCAP 100",   kind="yahoo", tk="NIFTY_MIDCAP_100.NS", fmt="level"),
 dict(name="Nifty Midcap 50",    label="NIFTY MIDCAP 50",    kind="yahoo", tk="^NSEMDCP50",          fmt="level"),
 dict(name="Nifty Smallcap 100", label="NIFTY SMALLCAP 100", kind="yahoo", tk="^CNXSC",              fmt="level"),
 dict(name="India VIX",          label="INDIA VIX",          kind="yahoo", tk="^INDIAVIX",           fmt="num2"),
 dict(name="USD / INR",          label="USDINR",             kind="yahoo", tk="INR=X",               fmt="fx"),
 dict(name="EUR / INR",          label="EURINR",             kind="yahoo", tk="EURINR=X",            fmt="fx"),
 dict(name="GBP / INR",          label="GBPINR",             kind="yahoo", tk="GBPINR=X",            fmt="fx"),
 dict(name="Nifty Smallcap / Nifty 50", label="Smallcap 100 / Nifty 50", kind="ratio", num="^CNXSC", den="^NSEI", fmt="num2"),
 dict(name="Gold / Silver ratio",       label="Gold / Silver",           kind="ratio", num="GC=F",  den="SI=F", fmt="num2"),

 # --- INDIA SECTORS -------------------------------------------------------
 dict(section="India Sectors"),
 dict(name="Nifty IT",                 label="NIFTY IT",            kind="yahoo", tk="^CNXIT",              fmt="level"),
 dict(name="Nifty Financial Services", label="NIFTY FIN SERVICES",  kind="yahoo", tk="NIFTY_FIN_SERVICE.NS",fmt="level"),
 dict(name="Nifty Auto",               label="NIFTY AUTO",          kind="yahoo", tk="^CNXAUTO",            fmt="level"),
 dict(name="Nifty Pharma",             label="NIFTY PHARMA",        kind="yahoo", tk="^CNXPHARMA",          fmt="level"),
 dict(name="Nifty FMCG",               label="NIFTY FMCG",          kind="yahoo", tk="^CNXFMCG",            fmt="level"),
 dict(name="Nifty Metal",              label="NIFTY METAL",         kind="yahoo", tk="^CNXMETAL",           fmt="level"),
 dict(name="Nifty Realty",             label="NIFTY REALTY",        kind="yahoo", tk="^CNXREALTY",          fmt="level"),

 # --- FLOWS & VALUATIONS --------------------------------------------------
 dict(section="Flows & Valuations"),
 dict(name="FII net (cash)",   label="FII Movement (Cr)",  kind="manual", fmt="num0"),
 dict(name="DII net (cash)",   label="DII Movement (Cr)",  kind="manual", fmt="num0"),
 dict(name="Nifty P/E",        label="Nifty P/E",          kind="manual", fmt="num2"),
 dict(name="Nifty P/B",        label="Nifty P/B",          kind="manual", fmt="num2"),
 dict(name="Nifty Div Yield",  label="Nifty Div Yield",    kind="manual", fmt="pct"),
 dict(name="Market Cap / GDP", label="India Mcap / GDP",   kind="manual", fmt="pct"),
 dict(name="Earnings Yield",   label="Earnings Yield",     kind="manual", fmt="pct"),

 # --- US & GLOBAL ---------------------------------------------------------
 dict(section="US & Global"),
 dict(name="Dow Jones",        label="DJIA",               kind="yahoo", tk="^DJI",       fmt="level"),
 dict(name="S&P 500",          label="S&P 500",            kind="yahoo", tk="^GSPC",      fmt="level"),
 dict(name="NASDAQ Composite", label="NASDAQ",             kind="yahoo", tk="^IXIC",      fmt="level"),
 dict(name="Dollar Index",     label="DXY",                kind="yahoo", tk="DX-Y.NYB",   fmt="num2"),
 dict(name="Nasdaq 100",       label="NASDAQ 100",         kind="yahoo", tk="^NDX",       fmt="level"),
 dict(name="CSI 300",          label="CSI 300",            kind="yahoo", tk="000300.SS",  fmt="level"),
 dict(name="Golden Dragon (PGJ proxy)", label="Golden Dragon", kind="yahoo", tk="PGJ",   fmt="num2"),
 dict(name="Nikkei 225",       label="NIKKEI 225",         kind="yahoo", tk="^N225",      fmt="level"),
 dict(name="Hang Seng",        label="HANG SENG",          kind="yahoo", tk="^HSI",       fmt="level"),
 dict(name="FTSE 100",         label="FTSE 100",           kind="yahoo", tk="^FTSE",      fmt="level"),
 dict(name="DAX",              label="DAX",                kind="yahoo", tk="^GDAXI",     fmt="level"),
 dict(name="Euro Stoxx 50",    label="EURO STOXX 50",      kind="yahoo", tk="^STOXX50E",  fmt="level"),
 dict(name="MSCI EM (EEM)",    label="MSCI EM",            kind="yahoo", tk="EEM",        fmt="num2"),
 dict(name="US CPI (Y-o-Y)",   label="US CPI (Y-o-Y)",     kind="manual", fmt="pct"),
 dict(name="US 2Y Treasury",   label="US 2Y",              kind="manual", fmt="pct"),
 dict(name="US 5Y Treasury",   label="US 5Y",              kind="yahoo", tk="^FVX",       fmt="pct"),
 dict(name="US 10Y Treasury",  label="US 10Y",             kind="yahoo", tk="^TNX",       fmt="pct"),
 dict(name="US 20Y Treasury",  label="US 20Y",             kind="manual", fmt="pct"),
 dict(name="US 30Y Treasury",  label="US 30Y",             kind="yahoo", tk="^TYX",       fmt="pct"),
 dict(name="US 13wk T-bill",   label="US 13wk",            kind="yahoo", tk="^IRX",       fmt="pct"),
 dict(name="10-yr TIPS breakeven", label="10Y Breakeven",  kind="manual", fmt="pct"),

 # --- COMMODITIES ---------------------------------------------------------
 dict(section="Commodities"),
 dict(name="Gold",     label="Gold ($/oz)",        kind="yahoo", tk="GC=F", fmt="num0"),
 dict(name="Gold INR", label="Gold (Rs/10g)",      kind="prod", a="GC=F", b="INR=X", scale=10.0/31.1035,   fmt="num0"),
 dict(name="Silver",   label="Silver ($/oz)",      kind="yahoo", tk="SI=F", fmt="num2"),
 dict(name="Silver INR",label="Silver (Rs/kg)",    kind="prod", a="SI=F", b="INR=X", scale=1000.0/31.1035, fmt="num0"),
 dict(name="WTI Crude",label="WTI ($/bbl)",        kind="yahoo", tk="CL=F", fmt="num2"),
 dict(name="Brent",    label="Brent ($/bbl)",      kind="yahoo", tk="BZ=F", fmt="num2"),
 dict(name="Copper",   label="Copper ($/ton)",     kind="yahoo", tk="HG=F", fmt="num0", mult=LB_TO_TON),
 dict(name="Aluminium",label="Aluminium ($/ton)",  kind="yahoo", tk="ALI=F",fmt="num0"),
 dict(name="Nickel",   label="Nickel ($/ton)",     kind="manual", fmt="num0"),
 dict(name="Zinc",     label="Zinc ($/ton)",       kind="manual", fmt="num0"),
 dict(name="Iron Ore", label="Iron Ore ($/ton)",   kind="manual", fmt="num0"),

 # --- LIQUIDITY, CREDIT & TRADE ------------------------------------------
 dict(section="Liquidity, Credit & Trade"),
 dict(name="US M2 Money Stock", label="US M2 ($bn)",         kind="manual", fmt="num0"),
 dict(name="India M3",          label="India M3 (Rs lac cr)",kind="manual", fmt="num2"),
 dict(name="ICE BofA HY OAS",   label="US HY OAS",           kind="manual", fmt="pct"),
 dict(name="Freightos Baltic",  label="FBX Freight Index",   kind="manual", fmt="num0"),
 dict(name="Asia Dollar Index", label="ADXY",                kind="manual", fmt="num2"),

 # --- ALTERNATIVES --------------------------------------------------------
 dict(section="Alternatives"),
 dict(name="Bitcoin",  label="BTC / USD",  kind="yahoo", tk="BTC-USD", fmt="num0"),
 dict(name="Ethereum", label="ETH / USD",  kind="yahoo", tk="ETH-USD", fmt="num0"),
]

YahooTickers = sorted({d["tk"] for d in IND if d.get("kind")=="yahoo"} |
                      {d["num"] for d in IND if d.get("kind")=="ratio"} |
                      {d["den"] for d in IND if d.get("kind")=="ratio"} |
                      {d["a"] for d in IND if d.get("kind")=="prod"} |
                      {d["b"] for d in IND if d.get("kind")=="prod"})

# ----------------------------------------------------------------------------
def fmt_val(v, fmt):
    if v is None or (isinstance(v,float) and math.isnan(v)): return "—"
    if fmt=="pct":   return f"{v:,.2f}%"
    if fmt=="fx":    return f"{v:,.2f}"
    if fmt=="num2":  return f"{v:,.2f}"
    if fmt=="num0":  return f"{v:,.0f}"
    if fmt=="level": return f"{v:,.0f}"
    return f"{v}"

def pct_change(cur, base):
    if cur is None or base is None or base==0: return None
    try:    return (cur/base - 1.0)*100.0
    except: return None

def cagr(cur, base, yrs):
    if cur is None or base is None or base<=0 or cur<=0: return None
    try:    return ((cur/base)**(1.0/yrs) - 1.0)*100.0
    except: return None

def asof(series, target):
    s = series[series.index <= target]
    return None if s.empty else float(s.iloc[-1])

def metrics_from_series(s):
    """s: pandas Series indexed by tz-naive dates, NaN dropped."""
    s = s.dropna()
    if s.empty: return None
    cur = float(s.iloc[-1]); d = s.index[-1]
    prev = float(s.iloc[-2]) if len(s)>1 else None
    y0   = dt.datetime(d.year,1,1)
    base_ytd = asof(s, y0 - dt.timedelta(days=1))
    return dict(
        value=cur, asof=d.strftime("%d %b %Y"),
        d1 = pct_change(cur, prev),
        w1 = pct_change(cur, asof(s, d - dt.timedelta(days=7))),
        m1 = pct_change(cur, asof(s, d - dt.timedelta(days=30))),
        ytd= pct_change(cur, base_ytd),
        y1 = pct_change(cur, asof(s, d - dt.timedelta(days=365))),
        c5 = cagr(cur, asof(s, d - dt.timedelta(days=365*5)), 5),
        c10= cagr(cur, asof(s, d - dt.timedelta(days=365*10)),10),
    )

def load_manual():
    if os.path.exists(MANUAL_JSON):
        try:
            with open(MANUAL_JSON) as f: return json.load(f)
        except: pass
    return {}

# ----------------------------------------------------------------------------
# Live macro fetch (runs at build time). Works where the runner has open
# internet (e.g. GitHub Actions); falls back silently to macro_values.json
# for any source that is blocked or slow (e.g. a restricted sandbox).
# ----------------------------------------------------------------------------
def _http_get(url, headers=None, timeout=8, opener=None):
    import urllib.request
    req=urllib.request.Request(url, headers=headers or {"User-Agent":"Mozilla/5.0"})
    if opener is not None:                       # OpenerDirector uses .open(), not .urlopen()
        return opener.open(req, timeout=timeout).read().decode("utf-8","replace")
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8","replace")

def _fmt_date(s):
    try:
        return dt.datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except: return s

def _fred(series):
    txt=_http_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", timeout=25)
    rows=[l.split(",") for l in txt.strip().splitlines()[1:] if l]
    return [(d, float(v)) for d,v in rows if v not in ("",".","NA")]

def _fred_latest(series):
    v=_fred(series);  return (v[-1][0], v[-1][1]) if v else None

def _fred_yoy(series):
    v=_fred(series)
    if len(v)<13: return None
    return (v[-1][0], (v[-1][1]/v[-13][1]-1)*100.0)

def fetch_live_macro():
    """Return ({indicator_name: {'value':x,'as_of':'..'}}, [errors])."""
    ov={}; errs=[]
    def put(name, res, nd=2):
        if res:
            d,val=res; ov[name]={"value":round(val,nd),"as_of":_fmt_date(d)}
    # ---- FRED (open, no key) ----
    fred_jobs=[
        ("US 2Y Treasury",     lambda:_fred_latest("DGS2"), 2),
        ("US 20Y Treasury",    lambda:_fred_latest("DGS20"),2),
        ("10-yr TIPS breakeven",lambda:_fred_latest("T10YIE"),2),
        ("ICE BofA HY OAS",    lambda:_fred_latest("BAMLH0A0HYM2"),2),
        ("US M2 Money Stock",  lambda:_fred_latest("M2SL"),0),
        ("US CPI (Y-o-Y)",     lambda:_fred_yoy("CPIAUCSL"),2),
        ("Consumer Price Index",lambda:_fred_yoy("INDCPIALLMINMEI"),2),  # India CPI YoY
        ("10-yr G-Sec Yield",  lambda:_fred_latest("IRLTLT01INM156N"),2),# India 10Y
    ]
    fred_alive=True
    for name,fn,nd in fred_jobs:
        if not fred_alive: break          # source unreachable -> stop probing
        try: put(name, fn(), nd)
        except Exception as e:
            errs.append(f"FRED({name}):{type(e).__name__}:{str(e)[:70]}"); fred_alive=False
    # ---- NSE (needs cookie handshake; may be blocked on some hosts) ----
    try:
        import urllib.request, http.cookiejar
        cj=http.cookiejar.CookieJar()
        op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        h={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Accept":"application/json,text/html","Accept-Language":"en-US,en;q=0.9",
           "Referer":"https://www.nseindia.com/"}
        _http_get("https://www.nseindia.com/", headers=h, opener=op, timeout=8)
        today=dt.datetime.now(IST).strftime("%d %b %Y")
        idx=json.loads(_http_get("https://www.nseindia.com/api/allIndices", headers=h, opener=op, timeout=8))
        for row in idx.get("data",[]):
            if (row.get("index") or row.get("indexSymbol"))=="NIFTY 50":
                for nm,key in [("Nifty P/E","pe"),("Nifty P/B","pb"),("Nifty Div Yield","dy")]:
                    try: ov[nm]={"value":round(float(row[key]),2),"as_of":today}
                    except Exception: pass
                break
        fd=json.loads(_http_get("https://www.nseindia.com/api/fiidiiTradeReact", headers=h, opener=op, timeout=8))
        for row in fd:
            cat=(row.get("category") or "").upper()
            try: net=round(float(row.get("netValue")))
            except Exception: continue
            d=_fmt_date_nse(row.get("date"))
            if "FII" in cat or "FPI" in cat: ov["FII net (cash)"]={"value":net,"as_of":d}
            elif "DII" in cat:               ov["DII net (cash)"]={"value":net,"as_of":d}
    except Exception as e:
        errs.append(f"NSE:{type(e).__name__}:{str(e)[:70]}")
    return ov, errs

def _fmt_date_nse(s):
    for f in ("%d-%b-%Y","%d %b %Y","%Y-%m-%d"):
        try: return dt.datetime.strptime((s or "").strip(), f).strftime("%d %b %Y")
        except Exception: pass
    return (s or "").strip() or dt.datetime.now(IST).strftime("%d %b %Y")

# ----------------------------------------------------------------------------
def gather():
    import yfinance as yf
    hist = {}
    try:
        raw = yf.download(YahooTickers, period="11y", interval="1d",
                          progress=False, threads=True)["Close"]
        for tk in YahooTickers:
            try:
                s = raw[tk].copy(); s.index = raw.index
                hist[tk] = s
            except Exception:
                hist[tk] = None
    except Exception as e:
        print("yahoo download error:", e)

    manual = load_manual()
    global FETCH_DIAG
    ferrs=[]
    try:
        overrides, ferrs = fetch_live_macro()
    except Exception as e:
        overrides = {}; ferrs=[f"outer:{type(e).__name__}:{str(e)[:70]}"]
    FETCH_DIAG = (f"overrides={len(overrides)} " + (" | ".join(ferrs) if ferrs else "ok")).replace('"',"'")
    print("FETCH_DIAG:", FETCH_DIAG)
    rows = []
    for d in IND:
        if "section" in d:
            rows.append(dict(section=d["section"])); continue
        r = dict(name=d["name"], label=d["label"], fmt=d["fmt"], source="")
        if d["kind"]=="yahoo":
            s = hist.get(d["tk"])
            m = metrics_from_series(s) if s is not None else None
            if m:
                mult = d.get("mult",1.0)
                m["value"] = m["value"]*mult
                r.update(m); r["source"]="live"
                r["spark"]=[float(x) for x in s.dropna().iloc[-30:].tolist()]
            else:
                r["value"]=None; r["source"]="na"
        elif d["kind"]=="ratio":
            sn, sd = hist.get(d["num"]), hist.get(d["den"])
            if sn is not None and sd is not None:
                import pandas as pd
                df = pd.concat([sn.rename("n"), sd.rename("d")], axis=1).dropna()
                ratio = (df["n"]/df["d"])
                m = metrics_from_series(ratio)
                if m:
                    r.update(m); r["source"]="live"
                    r["spark"]=[float(x) for x in ratio.dropna().iloc[-30:].tolist()]
                else: r["value"]=None; r["source"]="na"
            else:
                r["value"]=None; r["source"]="na"
        elif d["kind"]=="prod":
            sa, sb = hist.get(d["a"]), hist.get(d["b"])
            if sa is not None and sb is not None:
                import pandas as pd
                df = pd.concat([sa.rename("a"), sb.rename("b")], axis=1).dropna()
                ser = (df["a"]*df["b"]*d.get("scale",1.0))
                m = metrics_from_series(ser)
                if m:
                    r.update(m); r["source"]="live"
                    r["spark"]=[float(x) for x in ser.dropna().iloc[-30:].tolist()]
                else: r["value"]=None; r["source"]="na"
            else:
                r["value"]=None; r["source"]="na"
        else:  # manual — prefer freshly-fetched value, fall back to stored JSON
            mv = overrides.get(d["name"]) or manual.get(d["name"])
            if mv and mv.get("value") is not None:
                r["value"]=mv["value"]; r["asof"]=mv.get("as_of","")
                r["source"]="manual"
            else:
                r["value"]=None; r["source"]="manual"; r["asof"]=""
        rows.append(r)
    return rows

# ----------------------------------------------------------------------------
GREEN="#223E3B"; GOLD="#F5B11B"; TEAL="#40ACA7"
POS="#1f8a55"; NEG="#c0392b"; INK="#2a2a28"; MUTE="#8a8a82"; LINE="#e7e4dc"; BG="#f6f3ec"

def spark(vals, w=118, h=30):
    if not vals or len(vals)<2: return "&mdash;"
    mn=min(vals); mx=max(vals); rng=(mx-mn) or 1; n=len(vals)
    pts=[(i/(n-1)*w, (h-3)-((v-mn)/rng)*(h-6)) for i,v in enumerate(vals)]
    line=" ".join(f"{x:.1f},{y:.1f}" for x,y in pts)
    col = POS if vals[-1]>=vals[0] else NEG
    area=f"0,{h} "+line+f" {w},{h}"
    return (f'<svg class="spk" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<polygon points="{area}" fill="{col}" opacity="0.09"/>'
            f'<polyline points="{line}" fill="none" stroke="{col}" stroke-width="1.6" '
            f'stroke-linejoin="round"/></svg>')

def chip(v):
    if v is None: return '<td class="c mute">&mdash;</td>'
    cls="pos" if v>=0 else "neg"; a="&#9650;" if v>=0 else "&#9660;"
    return f'<td class="c {cls}">{a}&nbsp;{abs(v):,.2f}%</td>'

def kpi(r):
    if not r or r.get("value") is None: return ""
    v=fmt_val(r["value"], r["fmt"]); d=r.get("d1")
    if d is None: chng='<span class="kc mute">&mdash;</span>'
    else:
        cls="pos" if d>=0 else "neg"; a="&#9650;" if d>=0 else "&#9660;"
        chng=f'<span class="kc {cls}">{a}&nbsp;{abs(d):,.2f}% <em>1D</em></span>'
    return (f'<div class="kpi"><div class="kl">{r["label"]}</div>'
            f'<div class="kv">{v}</div>{chng}'
            f'<div class="ksp">{spark(r.get("spark"),150,34)}</div></div>')

def render(rows):
    now = dt.datetime.now(IST)
    live = sum(1 for r in rows if r.get("source")=="live")
    man  = sum(1 for r in rows if r.get("source")=="manual" and r.get("value") is not None)
    byname={r["name"]:r for r in rows if "name" in r}

    hero_keys=["Nifty 50","Sensex 30","Nifty Bank","USD / INR","Gold INR","Dow Jones"]
    hero="".join(kpi(byname.get(k)) for k in hero_keys)

    # group rows into section cards
    sections=[]; cur=None
    for r in rows:
        if "section" in r:
            cur={"title":r["section"],"rows":[]}; sections.append(cur); continue
        if cur is None:
            cur={"title":"","rows":[]}; sections.append(cur)
        v=fmt_val(r.get("value"), r["fmt"])
        src=r.get("source")
        if src=="live":
            tag=""; note=f'<span class="asof">{r.get("asof","")}</span>'
            cells=(chip(r.get("d1"))+chip(r.get("w1"))+chip(r.get("m1"))+
                   chip(r.get("ytd"))+chip(r.get("y1"))+chip(r.get("c5"))+chip(r.get("c10")))
            trend=f'<td class="tr">{spark(r.get("spark"))}</td>'
        elif src=="manual" and r.get("value") is not None:
            tag='<span class="tag man">auto</span>'
            note=f'<span class="asof">{r.get("asof","")}</span>' if r.get("asof") else ""
            cells=chip(None)*7; trend='<td class="tr mute">&mdash;</td>'
        else:
            tag='<span class="tag na">pending</span>'; note=""
            cells=chip(None)*7; trend='<td class="tr mute">&mdash;</td>'
        cur["rows"].append(
            f'<tr><td class="nm">{r["label"]}{tag}<div class="sub">{r["name"]} {note}</div></td>'
            f'<td class="val">{v}</td>{cells}{trend}</tr>')

    head=('<thead><tr><th>Indicator</th><th>Value</th><th>1D</th><th>1W</th><th>1M</th>'
          '<th>YTD</th><th>1Y</th><th>5Y</th><th>10Y</th><th>Trend&middot;30d</th></tr></thead>')
    cards=[]
    for s in sections:
        if not s["rows"]: continue
        cards.append(f'<section class="card"><div class="ctt">{s["title"]}</div>'
                     f'<div class="tw"><table>{head}<tbody>'+"".join(s["rows"])+
                     '</tbody></table></div></section>')
    cards_html="\n".join(cards)

    reload_tag = f'<meta http-equiv="refresh" content="{RELOAD_SECS}">' if RELOAD_SECS else ""
    reload_note = (f'&#8635; auto-reloads every {RELOAD_SECS}s &middot; '
                   f'<span id="ago">updated just now</span>') if RELOAD_SECS else ""
    gen_epoch = int(now.timestamp())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{reload_tag}
<meta name="dhfo-fetch" content="{FETCH_DIAG}">
<title>DHFO</title>
<style>
:root{{--green:{GREEN};--gold:{GOLD};--teal:{TEAL};--pos:{POS};--neg:{NEG};
--ink:{INK};--mute:{MUTE};--line:{LINE};--bg:{BG};}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
font-family:"Avenir Next","Avenir","Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;}}
.wrap{{max-width:1240px;margin:0 auto;padding:0 22px 64px;}}
.top{{background:var(--green);margin:0 -22px 26px;padding:26px 22px 22px;
border-bottom:3px solid var(--gold);}}
.top .inner{{max-width:1196px;margin:0 auto;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:14px}}
.brand{{font-size:12px;letter-spacing:.34em;color:var(--gold);font-weight:700;text-transform:uppercase}}
h1{{margin:7px 0 0;font-size:32px;font-weight:600;color:#fff;letter-spacing:.5px}}
.sub1{{color:#c9d6d1;font-size:12.5px;margin-top:4px}}
.meta{{text-align:right;font-size:12px;color:#bcccc6;line-height:1.7}}
.meta b{{color:#fff;font-weight:600}}
.reload{{color:var(--gold);font-size:11.5px;margin-top:4px}}
.hero{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin:0 0 22px}}
@media(max-width:1000px){{.hero{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:560px){{.hero{{grid-template-columns:repeat(2,1fr)}}}}
.kpi{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 14px 10px;
box-shadow:0 1px 3px rgba(34,62,59,.05)}}
.kl{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute);font-weight:700}}
.kv{{font-size:21px;font-weight:700;color:var(--green);margin:5px 0 4px;font-variant-numeric:tabular-nums;letter-spacing:.2px}}
.kc{{font-size:11.5px;font-weight:700;font-variant-numeric:tabular-nums}}
.kc em{{color:var(--mute);font-style:normal;font-weight:600;font-size:9.5px;letter-spacing:.05em}}
.ksp{{margin-top:7px;height:34px}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--mute);margin:0 0 18px;align-items:center}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:1px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:14px;margin:0 0 16px;overflow:hidden;
box-shadow:0 1px 3px rgba(34,62,59,.05)}}
.ctt{{font-size:12px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--green);
padding:14px 18px 10px;border-left:3px solid var(--gold);margin:12px 0 0 0;background:linear-gradient(90deg,#f4f1e9,#fff 60%)}}
.tw{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:13px;min-width:720px}}
thead th{{background:#fbfaf6;color:var(--mute);font-weight:700;font-size:10px;letter-spacing:.05em;
text-transform:uppercase;padding:9px 8px;text-align:right;border-bottom:1px solid var(--line)}}
thead th:first-child{{text-align:left;padding-left:18px}}
tbody td{{padding:9px 8px;border-bottom:1px solid #f0ede5;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
tbody tr:last-child td{{border-bottom:none}}
td.nm{{text-align:left;padding-left:18px;font-weight:600;color:var(--ink)}}
td.nm .sub{{font-weight:400;color:var(--mute);font-size:10.5px;margin-top:2px}}
td.val{{font-weight:700;color:var(--green)}}
td.c{{font-size:12px}}
.pos{{color:var(--pos)}} .neg{{color:var(--neg)}} .mute{{color:#c4c0b6}}
td.tr{{width:130px}} svg.spk{{width:118px;height:30px;display:inline-block;vertical-align:middle}}
.ksp svg.spk{{width:100%;height:34px}}
.tag{{font-size:8.5px;letter-spacing:.08em;text-transform:uppercase;padding:2px 6px;border-radius:10px;
margin-left:8px;vertical-align:1px;font-weight:700}}
.tag.man{{background:#fdf0d3;color:#9a7409}} .tag.na{{background:#eee;color:#999}}
.asof{{color:var(--mute);font-weight:400;font-size:10px;margin-left:6px}}
tbody tr:hover td{{background:#fbfaf5}}
footer{{margin-top:22px;font-size:11px;color:var(--mute);line-height:1.7;border-top:1px solid var(--line);padding-top:16px}}
</style></head><body>
<div class="top"><div class="inner">
 <div><div class="brand">Dinesh Hinduja Family Office</div><h1>DHFO</h1>
 <div class="sub1">Market &amp; Macro Dashboard</div></div>
 <div class="meta">Last refreshed<br><b>{now.strftime('%d %b %Y · %I:%M %p')} IST</b><br>
 {live} live &middot; {man} auto<div class="reload">{reload_note}</div></div>
</div></div>
<div class="wrap">
<div class="hero">{hero}</div>
<div class="legend">
 <span><span class="dot" style="background:var(--pos)"></span>gain</span>
 <span><span class="dot" style="background:var(--neg)"></span>loss</span>
 <span><span class="tag man" style="margin:0">auto</span> refreshed on schedule from public sources</span>
 <span><span class="tag na" style="margin:0">pending</span> awaiting next refresh</span>
</div>
{cards_html}
<footer>
<b>Live</b> rows stream from Yahoo Finance (indices, FX, commodities, US Treasury yields), computed intraday;
the 30-day trend line is the recent path. <b>Auto</b> rows (India policy rates, CPI/WPI, G-Sec &amp; T-bills,
Nifty valuations, FII/DII, US CPI, M2/M3, credit spreads, base-metal spot) have no free real-time API, so they
are refreshed on each scheduled run; the date beside each is its last print. Rebuilt from
“DHFO Dashboard - RP | V2 [ARCHIVED]”. Informational only; not investment advice.
</footer>
</div>
<script>
(function(){{
  var gen={gen_epoch}*1000, el=document.getElementById('ago');
  if(!el) return;
  function tick(){{
    var s=Math.max(0,Math.round((Date.now()-gen)/1000));
    el.textContent = s<60 ? ('updated '+s+'s ago') : ('updated '+Math.floor(s/60)+'m ago');
  }}
  tick(); setInterval(tick,1000);
}})();
</script>
</body></html>"""

# ----------------------------------------------------------------------------
if __name__=="__main__":
    rows = gather()
    html = render(rows)
    # index.html (for GitHub Pages) always carries the auto-reload tag.
    with open(OUT_INDEX,"w") as f: f.write(html)
    # DHFO.html (local copy) omits auto-reload so it doesn't flicker offline.
    local = html.replace(f'<meta http-equiv="refresh" content="{RELOAD_SECS}">', "") if RELOAD_SECS else html
    with open(OUT_HTML,"w") as f: f.write(local)
    live = sum(1 for r in rows if r.get("source")=="live")
    print(f"Wrote {OUT_INDEX} and {OUT_HTML}  ({live} live series)")
