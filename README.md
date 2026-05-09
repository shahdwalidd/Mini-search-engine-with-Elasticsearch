# 🔍 NexSearch — Mini Search Engine

A full-featured search engine built with **Elasticsearch**, **FastAPI**, and a beautiful dark UI.

## Features

| Feature | Details |
|---|---|
| **Boolean search** | `AND`, `OR`, `NOT`, grouping `()` |
| **Phrase search** | `"information retrieval"` |
| **Fuzzy search** | `headphon~`, `retrival~2` |
| **Wildcard search** | `lap*`, `?hone` |
| **Date range filter** | Filter by file modification date |
| **File type filter** | Filter results by csv / txt / json / pdf / xlsx |
| **Highlighted snippets** | `<mark>` tags around matching terms |
| **Did you mean?** | Elasticsearch suggest on zero results |
| **Pagination** | 5 results per page with prev/next |
| **Stats** | Total docs, by type, by category, top 10 terms |
| **File formats** | CSV, TXT, JSON, PDF, XLSX |

## Quick Start

### Option A: Docker (easiest)
```bash
# Start Elasticsearch + API
docker-compose up -d

# Open the UI
open frontend/index.html
```

### Option B: Manual

**Step 1 — Start Elasticsearch**
```bash
# macOS
brew install elastic/tap/elasticsearch-full
brew services start elasticsearch-full

# Docker (just ES)
docker run -d -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  elasticsearch:8.13.0

# Windows: download from elastic.co, run bin\elasticsearch.bat
```

**Step 2 — Install & start the API**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

**Step 3 — Open the UI**
- Open `frontend/index.html` in your browser
- Go to the **Index Builder** tab
- Select file formats → click **Build Index**
- Search!

## Project Structure
```
mini_search_engine/
├── backend/
│   ├── main.py           # FastAPI app (all endpoints)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── index.html        # Complete single-file UI
├── datasets/
│   ├── products.csv      # 30 tech products with name/description/price/category
│   ├── tech_trends.txt   # Technology article
│   └── articles.json     # 4 JSON articles with tags
├── docker-compose.yml
├── start.sh              # Linux/Mac quick start
├── start.bat             # Windows quick start
└── README.md
```

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | GET | Health check |
| `GET /health` | GET | ES + API status |
| `POST /index` | POST | Build/rebuild index |
| `GET /search` | GET | Search with all features |
| `GET /stats` | GET | Index statistics |

### Search Parameters
- `q` — query string (supports all Elasticsearch query_string syntax)
- `page` — page number (default: 1)
- `size` — results per page (default: 5, max: 50)
- `file_type` — filter by type: `csv`, `txt`, `json`, `pdf`, `xlsx`
- `date_from` — modification date from (YYYY-MM-DD)
- `date_to` — modification date to (YYYY-MM-DD)

### Search Examples
```
# Boolean
iphone AND apple
phone OR tablet
laptop NOT gaming

# Phrase
"noise canceling headphones"
"Apple Silicon"

# Fuzzy (typo tolerance)
iphon~
headphon~2

# Wildcard
lap*
*phone
?amsung

# Combined
(iphone OR samsung) AND NOT refurbished
"gaming laptop" AND NOT apple
```

## CSV Schema
The included `products.csv` has 30 tech products:
- `id`, `name`, `description`, `price`, `category`
- Categories: phones, laptops, tablets, audio, wearables, tvs, cameras, drones, gaming

## JSON Schema
`articles.json` contains 4 tech articles:
- `id`, `title`, `content`, `tags`, `published`
- Each article becomes a separate indexed document

## Notes
- The search engine uses **English analyzer** — stemming is applied (e.g., "running" matches "run")
- Fuzzy matching has `AUTO` fuzziness — adapts to word length
- "Did you mean?" only appears when zero results are returned
- All timestamps use ISO 8601 format from `os.path.getmtime()`
