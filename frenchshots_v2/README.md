# FrenchShots

A TikTok-style vertical feed for French video clips.  
Every shot has a **"Reveal vocabulary"** button — press it and Gemini AI analyses
the video's topic and returns every key word with its English translation,
pronunciation guide, and example sentences.

## Stack

| Layer | Tech |
|---|---|
| Backend | Flask + SQLAlchemy (SQLite) |
| Auth | Google OAuth2 via Authlib |
| AI | Gemini 2.0 Flash (google-genai SDK) |
| Frontend | Vanilla HTML / CSS / JS — zero frameworks |

## Setup

### 1. Clone & install

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
#   SECRET_KEY
#   GOOGLE_CLIENT_ID
#   GOOGLE_CLIENT_SECRET
#   GEMINI_API_KEY
```

Load the `.env` file before running:

```bash
export $(grep -v '^#' .env | xargs)   # Linux/Mac
# or use python-dotenv (pip install python-dotenv)
```

### 3. Google OAuth setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → **APIs & Services → Credentials → OAuth 2.0 Client ID**
3. Application type: **Web application**
4. Authorised redirect URIs: `http://localhost:5000/auth/callback`
5. Copy the Client ID and Secret into `.env`

> The first user to sign in is automatically made admin.

### 4. Run

```bash
python app.py
# → http://localhost:5000
```

## Project structure

```
frenchshots/
├── app.py                  # All routes & business logic
├── models.py               # SQLAlchemy models (User, Video, Like)
├── requirements.txt
├── .env.example
├── static/
│   ├── css/style.css       # Full dark editorial theme
│   ├── js/main.js          # Feed, vocab drawer, upload modal, likes
│   └── uploads/videos/     # User-uploaded MP4s (auto-created)
└── templates/
    ├── index.html          # Main feed
    ├── 404.html
    └── 500.html
```

## How the vocabulary feature works

1. User uploads a video with a title and description.
2. On upload, `app.py` calls Gemini 1.5 Flash with the title/description and a structured prompt.
3. Gemini returns a JSON array of 8–14 vocabulary items, each with:
   - French word
   - Part of speech
   - English translation
   - Pronunciation guide
   - French example sentence + English translation
4. The JSON is stored in the `videos.vocab_json` column.
5. When a viewer presses **Reveal vocabulary**, the frontend calls `/api/vocab/<id>` which returns the cached JSON instantly.
6. If no vocab is cached yet (e.g. legacy rows), it is generated on demand.
