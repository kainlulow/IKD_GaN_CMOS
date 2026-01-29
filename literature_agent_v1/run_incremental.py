import datetime as dt
import json, re
import requests
import pandas as pd
import yaml
from rapidfuzz import fuzz

IKD_BASE = "IKD_GaN_CMOS"
MASTER_XLSX = f"{IKD_BASE}/01_literature/IKD_Literature_Master.xlsx"
REVIEW_XLSX = f"{IKD_BASE}/01_literature/IKD_ReviewQueue.xlsx"
RUNLOG_CSV  = f"{IKD_BASE}/01_literature/IKD_RunLog.csv"
TAXON_YAML  = f"{IKD_BASE}/00_taxonomy/IKD_Taxonomy.yaml"
QUERIES_JSON= f"{IKD_BASE}/03_queries/queries.json"
STATE_FILE  = "literature_agent_v1/state/last_run_timestamp.txt"

CROSSREF = "https://api.crossref.org/works"

def norm_title(t: str) -> str:
    t = (t or "").lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 \-:/]", "", t)
    return t

def read_last_run_date(default="2010-01-01"):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            s = f.read().strip()
            return s if s else default
    except FileNotFoundError:
        return default

def write_last_run_date(d):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(d)

def load_sheet(xlsx, sheet):
    return pd.read_excel(xlsx, sheet_name=sheet)

def save_sheet(xlsx, sheet, df):
    with pd.ExcelWriter(xlsx, engine="openpyxl", mode="w") as w:
        df.to_excel(w, index=False, sheet_name=sheet)

def log_run(time_window, sources, cand, acc, rev, notes=""):
    log = pd.read_csv(RUNLOG_CSV)
    log = pd.concat([log, pd.DataFrame([{
        "RunDateTime": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "TimeWindow": time_window,
        "SourcesQueried": sources,
        "NewCandidates": cand,
        "NewAccepted": acc,
        "NewReviewQueue": rev,
        "Notes": notes
    }])], ignore_index=True)
    log.to_csv(RUNLOG_CSV, index=False)

def crossref_search(query: str, from_date: str, rows=20):
    params = {
        "query.bibliographic": query,
        "filter": f"from-pub-date:{from_date}",
        "rows": rows
    }
    headers = {"User-Agent": "IKD-GaN-CMOS/1.0 (mailto:ikd-bot@users.noreply.github.com)"}
    r = requests.get(CROSSREF, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()["message"]["items"]

def deterministic_tag(title, abstract, tax):
    text = f"{title} {abstract}".lower()
    device = "Other"
    for k, kws in tax["keyword_rules"]["DeviceType"].items():
        if any(kw in text for kw in kws):
            device = k; break
    method = "Other"
    for k, kws in tax["keyword_rules"]["Method"].items():
        if any(kw in text for kw in kws):
            method = k; break
    enabler = "Other"
    for k, kws in tax["keyword_rules"]["EnablerCategory"].items():
        if any(kw in text for kw in kws):
            enabler = k; break
    return device, method, enabler

def is_dup(doi, title_norm, master_df):
    doi_norm = (doi or "").lower().strip()
    if doi_norm and (master_df["DOI"].fillna("").str.lower().str.strip() == doi_norm).any():
        return True
    # title similarity
    for t in master_df["Title"].fillna("").map(norm_title).values:
        if t and fuzz.ratio(title_norm, t) >= 95:
            return True
    return False

def main():
    tax = yaml.safe_load(open(TAXON_YAML, "r", encoding="utf-8"))
    queries = json.load(open(QUERIES_JSON, "r", encoding="utf-8"))

    last_run_date = read_last_run_date(default="2010-01-01")

    master = load_sheet(MASTER_XLSX, "Master")
    review = load_sheet(REVIEW_XLSX, "ReviewQueue")

    candidates = []
    for bucket, qlist in queries["buckets"].items():
        for q in qlist:
            candidates.extend(crossref_search(q, from_date=last_run_date, rows=20))

    new_candidates = len(candidates)
    accepted, review_rows = [], []

    for it in candidates:
        title = (it.get("title") or [""])[0]
        if not title:
            continue
        issued = it.get("issued", {}).get("date-parts", [])
        year = issued[0][0] if issued and issued[0] else None

        doi = it.get("DOI", "")
        url = it.get("URL", "")

        # verification gate: must have DOI or URL
        if not doi and not url:
            continue

        title_norm = norm_title(title)
        if is_dup(doi, title_norm, master):
            continue

        abstract = it.get("abstract", "") or ""
        publisher = it.get("publisher") or ""
        venue = ""
        ct = it.get("container-title")
        if isinstance(ct, list) and ct:
            venue = ct[0]
        elif isinstance(ct, str):
            venue = ct

        authors = []
        for a in it.get("author", [])[:12]:
            fam = a.get("family", "")
            giv = a.get("given", "")
            nm = (fam + (", " + giv if giv else "")).strip()
            if nm:
                authors.append(nm)

        device, method, enabler = deterministic_tag(title, abstract, tax)
        conf = "High" if (device!="Other" and method!="Other" and enabler!="Other") else "Low"

        row = {
            "RecordID": "",
            "Title": title,
            "Year": year,
            "Publisher": publisher,
            "Venue": venue,
            "Authors": "; ".join(authors),
            "Organizations": "",
            "DOI": doi,
            "URL": url,
            "DocType": "Journal",
            "DeviceType": device,
            "Method": method,
            "EnablerCategory": enabler,
            "MaterialSystem": "",
            "Node/Geometry": "",
            "KeyContribution": "",
            "EvidenceSnippet": title,
            "TagConfidence": conf,
            "AddedDate": dt.date.today().isoformat(),
            "Notes": ""
        }

        if conf == "Low":
            review_rows.append(row)
        else:
            accepted.append(row)

    if accepted:
        master = pd.concat([master, pd.DataFrame(accepted)], ignore_index=True)
        save_sheet(MASTER_XLSX, "Master", master)

    if review_rows:
        review = pd.concat([review, pd.DataFrame(review_rows)], ignore_index=True)
        save_sheet(REVIEW_XLSX, "ReviewQueue", review)

    log_run(
        time_window=f"since {last_run_date}",
        sources="Crossref API (metadata)",
        cand=new_candidates,
        acc=len(accepted),
        rev=len(review_rows),
        notes="Deterministic V1 run"
    )

    # update checkpoint
    write_last_run_date(dt.date.today().isoformat())

if __name__ == "__main__":
    main()
