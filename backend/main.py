"""
Mini Search Engine — Backend
Boolean · Phrase · Fuzzy · Wildcard · Highlights · Did you mean? · Paging · Stats
"""

import os
import json
import csv
import time
from math import ceil
from datetime import datetime
from collections import Counter

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from elasticsearch import Elasticsearch

try:
    import pandas as pd
    PANDAS_OK = True
except Exception:
    PANDAS_OK = False

try:
    import pdfplumber
    PDF_OK = True
except Exception:
    PDF_OK = False

# ── Setup ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Mini Search Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
es = Elasticsearch(ES_HOST)
INDEX = "mini_search_engine"

# ── Elasticsearch ──────────────────────────────────────────────────────────────

def wait_for_es(retries=15, delay=2):
    for i in range(retries):
        try:
            if es.ping():
                print("Elasticsearch ready!")
                return True
        except Exception:
            pass
        print(f"[{i+1}/{retries}] Waiting for Elasticsearch...")
        time.sleep(delay)
    return False


def create_index():
    body = {
        "settings": {"number_of_replicas": 0},
        "mappings": {
            "properties": {
                "filename":  {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "content":   {"type": "text", "analyzer": "english"},
                "file_type": {"type": "keyword"},
                "mod_date":  {"type": "date"},
                "price":     {"type": "float"},
                "category":  {"type": "keyword"},
                "title":     {"type": "text"},
                "tags":      {"type": "keyword"},
            }
        },
    }
    if not es.indices.exists(index=INDEX):
        es.indices.create(index=INDEX, body=body)
        print(f"Index '{INDEX}' created.")
    else:
        print(f"Index '{INDEX}' already exists.")


def drop_index():
    if es.indices.exists(index=INDEX):
        es.indices.delete(index=INDEX)
        print(f"Index '{INDEX}' deleted.")


# ── Extractors ─────────────────────────────────────────────────────────────────

def _mod_date(path):
    return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()


def index_txt(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    es.index(index=INDEX, document={
        "filename": os.path.basename(path),
        "content": content,
        "file_type": "txt",
        "mod_date": _mod_date(path),
    })
    return 1


def index_pdf(path):
    if not PDF_OK:
        print(f"pdfplumber not installed - skipping {path}")
        return 0
    with pdfplumber.open(path) as pdf:
        content = " ".join(p.extract_text() for p in pdf.pages if p.extract_text())
    es.index(index=INDEX, document={
        "filename": os.path.basename(path),
        "content": content,
        "file_type": "pdf",
        "mod_date": _mod_date(path),
    })
    return 1


def index_xlsx(path):
    if not PANDAS_OK:
        print(f"pandas not installed - skipping {path}")
        return 0
    df = pd.read_excel(path)
    content = " | ".join(df.astype(str).apply(" ".join, axis=1))
    es.index(index=INDEX, document={
        "filename": os.path.basename(path),
        "content": content,
        "file_type": "xlsx",
        "mod_date": _mod_date(path),
    })
    return 1


def index_csv(path):
    mod = _mod_date(path)
    count = 0
    if PANDAS_OK:
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            name = ""
            for col in ["name", "title"]:
                if col in df.columns and str(row.get(col, "")) not in ("", "nan"):
                    name = str(row[col])
                    break
            desc = ""
            for col in ["description", "content", "text", "body"]:
                if col in df.columns and str(row.get(col, "")) not in ("", "nan"):
                    desc = str(row[col])
                    break
            extras = " ".join(str(v) for v in row.values if str(v) != "nan")
            doc = {
                "filename": name or os.path.basename(path),
                "content": (desc + " " + extras).strip(),
                "file_type": "csv",
                "mod_date": mod,
            }
            if "category" in df.columns and str(row.get("category", "")) not in ("", "nan"):
                doc["category"] = str(row["category"])
            if "price" in df.columns:
                try:
                    doc["price"] = float(row["price"])
                except Exception:
                    pass
            es.index(index=INDEX, document=doc)
            count += 1
    else:
        with open(path, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name") or row.get("title") or os.path.basename(path)
                desc = row.get("description") or row.get("content") or ""
                extras = " ".join(str(v) for v in row.values())
                doc = {
                    "filename": name,
                    "content": (desc + " " + extras).strip(),
                    "file_type": "csv",
                    "mod_date": mod,
                }
                if row.get("category"):
                    doc["category"] = row["category"]
                if row.get("price"):
                    try:
                        doc["price"] = float(row["price"])
                    except Exception:
                        pass
                es.index(index=INDEX, document=doc)
                count += 1
    return count


def index_json(path):
    mod = _mod_date(path)
    with open(path, encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    count = 0
    for obj in data:
        all_text = " ".join(str(v) for v in obj.values())
        doc = {
            "filename": obj.get("title") or obj.get("name") or os.path.basename(path),
            "content": obj.get("content") or obj.get("description") or all_text,
            "file_type": "json",
            "mod_date": mod,
        }
        if "tags" in obj:
            doc["tags"] = obj["tags"]
        if "title" in obj:
            doc["title"] = obj["title"]
        es.index(index=INDEX, document=doc)
        count += 1
    return count


# ── Indexer ────────────────────────────────────────────────────────────────────

HANDLERS = {
    ".txt":  index_txt,
    ".pdf":  index_pdf,
    ".xlsx": index_xlsx,
    ".csv":  index_csv,
    ".json": index_json,
}


def run_indexer(folder: str, allowed_exts: list) -> dict:
    wait_for_es()
    drop_index()
    create_index()
    allowed = set()
    for e in allowed_exts:
        e = e.strip()
        allowed.add(e if e.startswith(".") else f".{e}")
    summary = {"total": 0, "by_type": {}}
    for fname in os.listdir(folder):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in allowed:
            continue
        path = os.path.join(folder, fname)
        handler = HANDLERS.get(ext)
        if not handler:
            continue
        try:
            n = handler(path)
            summary["total"] += n
            key = ext.lstrip(".")
            summary["by_type"][key] = summary["by_type"].get(key, 0) + n
            print(f"Indexed {n} doc(s) from: {fname}")
        except Exception as err:
            print(f"Error indexing {fname}: {err}")
    es.indices.refresh(index=INDEX)
    return summary


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Mini Search Engine API", "status": "running"}


@app.get("/health")
def health():
    try:
        ok = es.ping()
    except Exception:
        ok = False
    return {"api": "ok", "elasticsearch": "ok" if ok else "unreachable"}


@app.post("/index")
def build_index(
    folder: str = Query(default="../datasets"),
    formats: str = Query(default="csv,txt,json,pdf,xlsx"),
):
    if not os.path.isabs(folder):
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.normpath(os.path.join(here, folder))
        if os.path.exists(candidate):
            folder = candidate
    if not os.path.exists(folder):
        return JSONResponse(
            status_code=404,
            content={"error": f"Folder not found: '{folder}'. Make sure 'datasets' folder exists next to 'backend'."}
        )
    allowed = [f.strip() for f in formats.split(",")]
    result = run_indexer(folder, allowed)
    return {
        "success": True,
        "indexed": result["total"],
        "by_type": result["by_type"],
        "message": f"Indexed {result['total']} documents successfully",
    }


@app.get("/search")
def search(
    q: str = Query(...),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=5, ge=1, le=50),
    file_type: str = Query(default=None),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    if not es.indices.exists(index=INDEX):
        return JSONResponse(
            status_code=404,
            content={"error": "Index not built yet. Go to Index Builder tab first."}
        )
    filters = []
    if file_type:
        filters.append({"term": {"file_type": file_type}})
    if date_from or date_to:
        dr = {}
        if date_from:
            dr["gte"] = date_from
        if date_to:
            dr["lte"] = date_to
        filters.append({"range": {"mod_date": dr}})

    main_q = {
        "query_string": {
            "query": q,
            "fields": ["filename^3", "title^3", "content^2", "tags^2", "category"],
            "default_operator": "OR",
            "fuzziness": "AUTO",
            "allow_leading_wildcard": True,
        }
    }
    es_query = {"bool": {"must": [main_q], "filter": filters}} if filters else main_q

    body = {
        "from": (page - 1) * size,
        "size": size,
        "query": es_query,
        "highlight": {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fields": {
                "content":  {"fragment_size": 150, "number_of_fragments": 2},
                "filename": {},
                "title":    {},
            },
        },
    }

    try:
        res = es.search(index=INDEX, body=body)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    total = res["hits"]["total"]["value"]
    results = []
    for h in res["hits"]["hits"]:
        src = h["_source"]
        hl = h.get("highlight", {})
        snippet = (hl.get("content") or hl.get("title") or [""])[0] or src.get("content", "")[:200]
        results.append({
            "id":        h["_id"],
            "score":     round(h["_score"] or 0, 3),
            "filename":  src.get("filename") or src.get("title") or "Unknown",
            "file_type": src.get("file_type", ""),
            "mod_date":  src.get("mod_date", ""),
            "content":   src.get("content", "")[:300],
            "snippet":   snippet,
            "price":     src.get("price"),
            "category":  src.get("category"),
            "tags":      src.get("tags", []),
        })

    suggestion = None
    if total == 0:
        try:
            sug = es.search(index=INDEX, body={
                "suggest": {
                    "hint": {"text": q, "term": {"field": "content", "suggest_mode": "missing"}}
                }
            })
            words = []
            for item in sug.get("suggest", {}).get("hint", []):
                if item.get("options"):
                    words.append(item["options"][0]["text"])
            if words:
                suggestion = " ".join(words)
        except Exception:
            pass

    return {
        "total":       total,
        "page":        page,
        "total_pages": max(1, ceil(total / size)),
        "size":        size,
        "results":     results,
        "suggestion":  suggestion,
    }


@app.get("/stats")
def stats():
    if not es.indices.exists(index=INDEX):
        return {"total_documents": 0, "by_type": {}, "by_category": {}, "top_terms": []}
    try:
        total = es.count(index=INDEX)["count"]
        agg_res = es.search(index=INDEX, body={
            "size": 0,
            "aggs": {
                "by_type":     {"terms": {"field": "file_type", "size": 20}},
                "by_category": {"terms": {"field": "category",  "size": 20}},
            },
        })
        by_type = {b["key"]: b["doc_count"] for b in agg_res["aggregations"]["by_type"]["buckets"]}
        by_cat  = {b["key"]: b["doc_count"] for b in agg_res["aggregations"]["by_category"]["buckets"]}
        sample = es.search(index=INDEX, body={"size": 200, "_source": ["content"], "query": {"match_all": {}}})
        stops = {
            "the","a","an","and","or","not","is","in","of","to","for","with",
            "this","that","it","as","on","at","by","from","be","are","was",
            "were","has","have","had","will","can","its","nan","none","true","false",
        }
        counter = Counter()
        for h in sample["hits"]["hits"]:
            text = h["_source"].get("content", "")
            words = [w.lower().strip(".,!?\"'()[]{}") for w in text.split()]
            counter.update(w for w in words if len(w) > 3 and w not in stops and w.isalpha())
        top_terms = [{"term": t, "count": c} for t, c in counter.most_common(10)]
        return {
            "total_documents": total,
            "by_type":         by_type,
            "by_category":     by_cat,
            "top_terms":       top_terms,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    