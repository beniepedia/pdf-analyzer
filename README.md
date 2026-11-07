# PDF Analyzer API

API untuk mengecek halaman berwarna dan hitam-putih pada PDF via Upload File, URL, atau Base64. Mendukung file **PDF, DOC, dan DOCX** (DOC/DOCX dikonversi ke PDF via LibreOffice headless sebelum diproses).

---

## 📋 Fitur

- Cek halaman berwarna vs hitam-putih pada PDF
- Support input: file upload (multipart), URL, Base64
- Support format: **PDF, DOC, DOCX**
- Autentikasi API Key (header `X-API-Key`)
- Rate limiting (10 request/menit per IP)
- SSRF protection (blokir localhost + private IP)
- Health check endpoint (`GET /health`)
- Docker multi-stage build + CI/CD (GitHub Actions → Docker Hub)

---

## 🚀 Quick Start

### 1. Clone repository

```bash
git clone https://github.com/namauseranda/pdf-analyzer.git
cd pdf-analyzer
```

### 2. Salin dan konfigurasi `.env`

```bash
cp .env.example .env
```

Edit file `.env` dengan API Key dan konfigurasi Anda:

```env
API_KEY_1=rahasia-api-key-1
API_KEY_2=rahasia-api-key-2
MAX_FILE_SIZE_MB=15
ALLOWED_ORIGINS=https://backend-perusahaan.com
LIBREOFFICE_TIMEOUT=120
```

### 3. Install dependency

```bash
pip install -r requirements.txt
```

### 4. Jalankan server

```bash
uvicorn app.main:app --reload
```

Akses dokumentasi otomatis di: `http://localhost:8000/docs`

---

## 🐳 Docker

### Build dan jalankan dengan Docker Compose (development)

```bash
docker-compose up --build
```

### Jalankan di produksi

```bash
docker pull namauseranda/pdf-analyzer:latest
docker run -d --name pdf-analyzer \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  namauseranda/pdf-analyzer:latest
```

---

## 📡 Endpoint

| Endpoint | Metode | Deskripsi | Format |
|----------|--------|-----------|--------|
| `/check/upload` | POST | Upload file | PDF, DOC, DOCX |
| `/check/url` | POST | Download dari URL | PDF, DOC, DOCX |
| `/check/base64` | POST | Decode Base64 | PDF, DOC, DOCX |
| `/health` | GET | Health check | — |

Semua endpoint memerlukan header `X-API-Key`.

### Contoh response

```json
{
  "source": "dokumen.pdf",
  "total_pages": 2,
  "color_pages": 1,
  "bw_pages": 1,
  "paper_size_mm": "210.0 × 297.0",
  "paper_size_inch": "8.27 × 11.69",
  "paper_size_standard": "Mixed",
  "details": [
    {
      "page": 1,
      "type": "CL",
      "paper_size_mm": "210.0 × 297.0",
      "paper_size_inch": "8.27 × 11.69",
      "paper_size_standard": "A4"
    },
    {
      "page": 2,
      "type": "BW",
      "paper_size_mm": "215.9 × 279.4",
      "paper_size_inch": "8.50 × 11.00",
      "paper_size_standard": "Letter"
    }
  ]
}
```

```bash
curl -X POST http://localhost:8000/check/upload \
  -H "X-API-Key: rahasia-api-key-1" \
  -F "file=@dokumen.pdf"
```

```bash
curl -X POST http://localhost:8000/check/url \
  -H "X-API-Key: rahasia-api-key-1" \
  -H "Content-Type: application/json" \
  -d '{"pdf_url": "https://contoh.com/dokumen.pdf"}'
```

```bash
curl -X POST http://localhost:8000/check/base64 \
  -H "X-API-Key: rahasia-api-key-1" \
  -H "Content-Type: application/json" \
  -d '{"base64_data": "JVBERi0xLjQKJa..."}'
```

---

## 🔐 Konfigurasi Keamanan

| Variabel | Deskripsi |
|----------|-----------|
| `API_KEY_1` | API Key utama |
| `API_KEY_2` | API Key cadangan |
| `MAX_FILE_SIZE_MB` | Maksimal ukuran file (default: 15) |
| `ALLOWED_ORIGINS` | Domain yang diizinkan CORS (pisahkan koma) |
| `LIBREOFFICE_TIMEOUT` | Batas waktu konversi DOC/DOCX (detik, default: 120) |

---

## 🔄 CI/CD (GitHub Actions → Docker Hub)

Setiap push ke branch `main` atau `master` akan otomatis:
1. Build Docker image
2. Push ke Docker Hub (`namauseranda/pdf-analyzer:latest`)

### Secrets yang diperlukan di GitHub

Masuk ke **Settings → Secrets and variables → Actions**:

| Secret | Contoh |
|--------|--------|
| `DOCKERHUB_USERNAME` | `namauseranda` |
| `DOCKERHUB_TOKEN` | `ghp_xxxx...` |

### Deploy di server

```bash
./deploy.sh
```

Pastikan file `.env` sudah ada di server sebelum menjalankan `deploy.sh`.

---

## 🧪 Struktur Project

```
pdf-analyzer/
├── app/
│   ├── main.py           # Entry point FastAPI
│   ├── config.py         # Konfigurasi env
│   ├── security.py       # API Key + SSRF protection
│   ├── schemas.py        # Pydantic models
│   ├── utils.py          # Helper (temp file, detect type, cleanup)
│   ├── services.py       # PDF processing + LibreOffice conversion
│   └── routers/
│       ├── upload.py     # POST /check/upload
│       ├── url.py        # POST /check/url
│       └── base64.py     # POST /check/base64
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── deploy.sh
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 📄 Lisensi

MIT