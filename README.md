# 📄 Chat with PDF

An AI study assistant for your documents. Upload a PDF, ask questions in plain language, and get answers that **explain** the material like a teacher, grounded in the PDF itself and aware of everything you asked before.

Built with **Django**, **LangChain**, **FAISS**, **FastEmbed** and **Groq (LLaMA 3.3 70B)** using a conversational RAG (Retrieval-Augmented Generation) pipeline.

---

## 📚 Table of Contents

- [Features](#-features)
- [Tech Stack](#️-tech-stack)
- [Architecture](#️-architecture)
- [Detailed Workflow](#-detailed-workflow)
  - [1. Authentication](#1-authentication)
  - [2. PDF Upload and Indexing](#2-pdf-upload-and-indexing)
  - [3. Asking a Question](#3-asking-a-question)
  - [4. History-Aware Retrieval](#4-history-aware-retrieval)
  - [5. Answer Generation](#5-answer-generation)
  - [6. Persistence and Restart Recovery](#6-persistence-and-restart-recovery)
  - [7. Deleting a PDF](#7-deleting-a-pdf)
- [The Assistant's Behavior Rules](#-the-assistants-behavior-rules)
- [Advantages](#-advantages)
- [Data Model](#️-data-model)
- [URL Routes](#️-url-routes)
- [Project Structure](#-project-structure)
- [Local Setup](#️-local-setup)
- [Environment Variables](#-environment-variables)
- [Deployment on Render](#-deployment-on-render)
- [Known Limitations and Future Improvements](#-known-limitations-and-future-improvements)
- [Author](#-author)
- [License](#-license)

---

## 🚀 Features

- 🔐 **User accounts**: register, log in and log out with Django's built-in authentication.
- 📤 **PDF upload**: give each PDF a name and upload it; it is indexed automatically.
- 💬 **Conversational Q&A**: ask questions and get answers in an AJAX chat UI, with no page reload.
- 🧠 **Memory across turns**: follow-ups like *"explain that more"* or *"give me a quiz on it"* work, because the chat history is used both for searching and for answering.
- 🗂️ **Saved conversations**: every question and answer is stored in PostgreSQL, so a chat is still there when you come back.
- ⚡ **Index once, reuse forever**: each PDF's FAISS index is saved to disk and reloaded instead of re-embedding.
- 🗑️ **Delete PDFs**: remove documents you no longer need, along with their chat history.
- 🔒 **Per-user privacy**: users only see, chat with, and delete their own PDFs (others get `403 Forbidden`).
- ☁️ **Deploy-ready**: Gunicorn, WhiteNoise static files, `DATABASE_URL` config and a `render.yaml` blueprint.

---

## 🛠️ Tech Stack

| Layer | Technology | Role in the project |
|-------|-----------|---------------------|
| Language | Python 3.11 | Runtime (`runtime.txt`) |
| Web framework | Django 6 | Views, ORM, auth, templates, admin |
| Frontend | Django templates, Tailwind CSS (CDN), vanilla JS `fetch` | Upload page, PDF library, chat UI |
| RAG orchestration | LangChain (`langchain-core`, `langchain-community`, `langchain-classic`) | History-aware retriever, stuff-documents chain, retrieval chain |
| PDF loading | `PyPDFLoader` (pypdf) | Extracts text page by page |
| Text splitting | `RecursiveCharacterTextSplitter` | 1000-character chunks with 200-character overlap |
| Embeddings | FastEmbed `BAAI/bge-small-en-v1.5` | Small, fast ONNX embedding model running locally on CPU |
| Vector store | FAISS (`faiss-cpu`) | Similarity search, index saved per PDF in `faiss_indexes/` |
| LLM | Groq `llama-3.3-70b-versatile` via `langchain-groq` | Query rewriting and answer generation |
| Database | PostgreSQL (`psycopg2`, `dj-database-url`) | Users, PDFs, chat messages |
| Config | `python-dotenv` | Loads secrets from `.env` |
| Static files | WhiteNoise | Serves compressed static files in production |
| App server | Gunicorn | Production WSGI server |
| Hosting | Render (`render.yaml`, `build.sh`) | One-click deployment |

---

## 🏗️ Architecture

```
                        ┌──────────────────────────────┐
                        │           Browser            │
                        │  Tailwind UI + fetch() chat  │
                        └──────────────┬───────────────┘
                                       │ HTTP (CSRF-protected)
                        ┌──────────────▼───────────────┐
                        │        Django (mysite)       │
                        │  users app  │   myapp app    │
                        │  register   │ index, upload  │
                        │  login      │ chat, delete   │
                        │  logout     │                │
                        └──────┬──────┴───────┬────────┘
                               │              │
              ┌────────────────▼──┐     ┌─────▼────────────────────────┐
              │    PostgreSQL     │     │   langchain_utils.py (RAG)   │
              │ User, Profile,    │     │                              │
              │ ChatMessage       │     │  PyPDFLoader → Splitter      │
              └───────────────────┘     │        → FastEmbed           │
                                        │        → FAISS (disk cache)  │
              ┌───────────────────┐     │                              │
              │  media/pdf/       │◄────│  History-aware retriever     │
              │  uploaded files   │     │        → Groq LLaMA 3.3 70B  │
              └───────────────────┘     └──────────────┬───────────────┘
                                                       │
                                        ┌──────────────▼───────────────┐
                                        │   faiss_indexes/<pdf_id>/    │
                                        └──────────────────────────────┘
```

The project has two Django apps:

- **`users`**: registration (`UserCreationForm` + email), login (Django `LoginView`) and logout.
- **`myapp`**: the PDF library, upload, chat and delete views, plus the whole RAG pipeline in `myapp/langchain_utils.py`.

---

## 🔄 Detailed Workflow

### 1. Authentication

1. A new user opens `/register/` and submits username, email and password (validated by Django's `UserCreationForm`).
2. They are redirected to `/login/` with a welcome message.
3. After logging in, Django redirects to `/` (`LOGIN_REDIRECT_URL`).
4. Every app view uses `@login_required`, so anonymous visitors are sent to `/login/` (`LOGIN_URL`).

### 2. PDF Upload and Indexing

```
Upload form (name + file)
        │
        ▼
Profile row created in PostgreSQL ──► file saved to media/pdf/
        │
        ▼
process_pdf(path, pdf_id)
        │
        ├── faiss_indexes/<pdf_id>/ exists? ── yes ──► load index from disk
        │
        └── no
             │
             ▼
     PyPDFLoader: read text, one Document per page (keeps page metadata)
             │
             ▼
     RecursiveCharacterTextSplitter: 1000-char chunks, 200-char overlap
             │
             ▼
     FastEmbed (BAAI/bge-small-en-v1.5): one vector per chunk
             │
             ▼
     FAISS.from_documents → save_local(faiss_indexes/<pdf_id>/)
             │
             ▼
     Retriever stored in the in-memory `retrievers` dict
        │
        ▼
Redirect to the PDF library (/)
```

Key details:

- **Chunk overlap** of 200 characters keeps sentences that cross a chunk boundary searchable from both sides.
- The **embedding model is loaded once** per process (`get_embeddings()` caches it in a module-level variable), so later uploads and queries do not pay the model-loading cost again.
- The FAISS index is **written to disk per PDF**, so a PDF is embedded only once in its lifetime.

### 3. Asking a Question

1. The user opens `/chat/<pdf_id>/`. Django checks that the PDF belongs to them, then renders the page with all previous messages from `ChatMessage`.
2. The user types a question. JavaScript sends it with `fetch()` as a `POST` to the same URL, with the CSRF token in the `X-CSRFToken` header.
3. The view looks up the PDF's retriever in memory. If it is missing (for example after a server restart), it calls `process_pdf` again, which just loads the saved index from disk.
4. `get_answer()` runs the RAG chain (steps 4 and 5 below).
5. The question and answer are saved as a new `ChatMessage` row.
6. The view returns `{"answer": "..."}` as JSON, and the page appends it to the conversation.

### 4. History-Aware Retrieval

A plain retriever fails on follow-ups: searching the PDF for *"what about the second one?"* finds nothing useful. This project fixes that with LangChain's `create_history_aware_retriever`:

```
chat history + latest question
        │
        ▼
Groq LLM with a "contextualize" prompt:
"Rewrite the latest question as a standalone question. Do not answer it."
        │
        ▼
Standalone question, e.g. "What is the second normal form in database design?"
        │
        ▼
FAISS similarity search → most relevant chunks
```

If the question is already standalone, it is used as-is.

### 5. Answer Generation

```
Retrieved chunks ──► injected into <context> of the QA system prompt
Chat history     ──► MessagesPlaceholder("chat_history")
User question    ──► human message
        │
        ▼
create_stuff_documents_chain (all chunks "stuffed" into one prompt)
        │
        ▼
Groq llama-3.3-70b-versatile
        │
        ▼
Answer written as a friendly teacher explanation
```

The two pieces are joined with `create_retrieval_chain(history_aware_retriever, doc_chain)`, so a single `invoke({"input", "chat_history"})` does rewriting, retrieval and answering.

### 6. Persistence and Restart Recovery

| What | Where | Survives a restart? |
|------|-------|---------------------|
| User accounts | PostgreSQL | ✅ |
| PDF metadata (`Profile`) | PostgreSQL | ✅ |
| Uploaded PDF files | `media/pdf/` | ✅ (on persistent disk) |
| Every question and answer (`ChatMessage`) | PostgreSQL | ✅ |
| FAISS vector index | `faiss_indexes/<pdf_id>/` | ✅ (on persistent disk) |
| Retriever objects | in-memory `retrievers` dict | ❌ rebuilt from disk on first use |
| LLM chat history | in-memory `chat_histories` dict, keyed by `(user_id, pdf_id)` | ❌ rebuilt from PostgreSQL on first use |

On the first question after a restart, the app reloads the last **20 messages (10 exchanges)** for that user and PDF from the database, so the assistant still remembers the conversation. History is capped at 20 messages to keep prompts small and fast.

### 7. Deleting a PDF

`/delete/<pdf_id>/` checks ownership, then deletes the `Profile` row. Because `ChatMessage` has `on_delete=CASCADE`, the PDF's whole chat history is removed with it.

---

## 🧑‍🏫 The Assistant's Behavior Rules

The QA system prompt in `langchain_utils.py` turns the LLM into a study assistant rather than a search box:

1. **PDF first**: the retrieved PDF context is the primary source; explain it rather than quoting it back.
2. **Teach, don't recite**: simple language, analogies and examples, in flowing paragraphs (no lists unless asked).
3. **Fill gaps honestly**: if the PDF is incomplete, it may add general knowledge but must say so (*"Beyond what the PDF covers..."*), so the student always knows the source.
4. **Use conversation history**: understands references like *"explain that more"* or *"what did you mean by point 2"* without asking you to repeat yourself.
5. **Out-of-scope questions**: politely says the question is unrelated in one sentence, then offers help with the PDF.
6. **Length matches the question**: 2-4 sentences for quick facts, full explanations for concepts, structured but conversational summaries.

---

## ✅ Advantages

- **Answers grounded in your document.** RAG retrieves the relevant passages first, so the model answers from your PDF instead of guessing, which greatly reduces hallucinations.
- **Real conversations, not one-off searches.** The history-aware retriever rewrites follow-up questions, so multi-turn study sessions work naturally.
- **Transparent about sources.** The prompt forces the assistant to flag anything that comes from outside the PDF.
- **Learning-focused answers.** Explanations are written like a tutor would give them, which makes it useful for students, not only for lookup.
- **Fast responses.** Groq's LPU inference serves a 70B model with very low latency, and FastEmbed's ONNX model embeds on CPU without a GPU or PyTorch at query time.
- **Low cost.** Embeddings and vector search run locally (FastEmbed + FAISS), so the only paid API call is the LLM, and indexes are built once per PDF.
- **No external vector database needed.** FAISS indexes are plain files on disk, which keeps the setup simple.
- **Survives restarts.** Chats are stored in PostgreSQL and indexes on disk; in-memory caches are rebuilt automatically.
- **Private by design.** Every PDF and chat is tied to a user, and ownership is checked on chat and delete.
- **Production-friendly.** Secrets come from environment variables, the database from `DATABASE_URL`, static files through WhiteNoise, and Gunicorn serves the app on Render.
- **Easy to extend.** The whole AI pipeline lives in one module (`langchain_utils.py`), so swapping the LLM, embedding model or vector store is a small change.

---

## 🗄️ Data Model

```
User (django.contrib.auth)
 │ 1
 │
 │ *
Profile                         ChatMessage
──────────────                  ──────────────────────
id                              id
user      → User   ◄─────────── user     → User
name      (max 50)      1   *   pdf      → Profile (CASCADE)
pdf       (FileField,  ◄─────── question (text)
           upload_to=pdf/)      answer   (text)
                                created_at (auto)
```

`Profile` represents one uploaded PDF (the name is historical; it is the PDF record).

---

## 🗺️ URL Routes

| Route | View | Method | Description |
|-------|------|--------|-------------|
| `/register/` | `users.views.register` | GET, POST | Create an account |
| `/login/` | Django `LoginView` | GET, POST | Log in |
| `/logout/` | `users.views.logout_view` | GET | Log out and go to login |
| `/` | `myapp.views.index` | GET | Your PDF library |
| `/upload/` | `myapp.views.upload_pdf` | GET, POST | Upload and index a PDF |
| `/chat/<pdf_id>/` | `myapp.views.chat_view` | GET | Chat page with saved history |
| `/chat/<pdf_id>/` | `myapp.views.chat_view` | POST | Ask a question, returns `{"answer": ...}` |
| `/delete/<pdf_id>/` | `myapp.views.delete_view` | GET | Delete a PDF and its chats |
| `/admin/` | Django admin | | Admin site |

---

## 📁 Project Structure

```
Chat_with_Pdf/
├── mysite/                     # Django project
│   ├── settings.py             # Env-based config, DATABASE_URL, WhiteNoise, media
│   ├── urls.py                 # Root routes (admin, myapp, users, media)
│   ├── wsgi.py / asgi.py
├── myapp/                      # PDF + chat app
│   ├── langchain_utils.py      # RAG pipeline: load, split, embed, FAISS, Groq chain
│   ├── views.py                # index, upload_pdf, chat_view, delete_view
│   ├── models.py               # Profile (PDF), ChatMessage
│   ├── forms.py                # UpLoadPdf form
│   ├── urls.py
│   ├── migrations/
│   └── templates/myapp/
│       ├── index.html          # PDF library
│       ├── upload.html         # Upload form
│       └── chat.html           # Chat UI (fetch + CSRF)
├── users/                      # Auth app
│   ├── views.py                # register, logout
│   ├── forms.py                # RegisterForm (adds email)
│   ├── urls.py
│   └── templates/users/        # login.html, register.html
├── staticfiles/                # collectstatic output
├── faiss_indexes/              # Saved FAISS indexes (auto-created, git-ignored)
├── media/                      # Uploaded PDFs (git-ignored)
├── build.sh                    # Render build: install, collectstatic, migrate
├── render.yaml                 # Render blueprint
├── runtime.txt                 # python-3.11.0
├── requirements.txt
└── manage.py
```

---

## ⚙️ Local Setup

### Prerequisites

- Python 3.11
- PostgreSQL running locally (or any PostgreSQL URL)
- A free [Groq API key](https://console.groq.com)

### 1. Clone the repository

```bash
git clone https://github.com/codinghub27/Chat_with_Pdf.git
cd Chat_with_Pdf
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the database

```bash
createdb chat_with_pdf
```

### 5. Create a `.env` file in the project root

```env
SECRET_KEY=your_django_secret_key
DEBUG=True
DATABASE_URL=postgres://your_user:your_password@localhost:5432/chat_with_pdf
GROQ_API_KEY=your_groq_api_key
# Optional, only needed for gated HuggingFace downloads
HF_TOKEN=your_huggingface_token
```

### 6. Run migrations and (optionally) create an admin user

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 7. Start the server

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000, register an account, upload a PDF and start chatting.

> The first upload downloads the `BAAI/bge-small-en-v1.5` embedding model. Later uploads reuse it.

---

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Django secret key |
| `DATABASE_URL` | ✅ | PostgreSQL connection URL, parsed by `dj-database-url` |
| `GROQ_API_KEY` | ✅ | Groq API key for LLaMA 3.3 70B |
| `DEBUG` | ➖ | `True` for development; defaults to `False` |
| `HF_TOKEN` | ➖ | HuggingFace token, only if a model download needs it |

Never commit `.env`; it is already in `.gitignore`.

---

## ☁️ Deployment on Render

The repo includes everything needed for [Render](https://render.com):

- **`render.yaml`** defines a Python web service named `chat-with-pdf`.
- **`build.sh`** runs `pip install`, `collectstatic` and `migrate`.
- **Start command**: `gunicorn mysite.wsgi:application`.

Steps:

1. Create a PostgreSQL database on Render and copy its internal URL.
2. Create a new Blueprint (or Web Service) from this repo.
3. Set `SECRET_KEY`, `DATABASE_URL` and `GROQ_API_KEY` in the service's environment.
4. Make `build.sh` executable if needed (`git update-index --chmod=+x build.sh`).
5. Attach a persistent disk for `media/` and `faiss_indexes/` if you want uploads and indexes to survive redeploys.

---

## 🚧 Known Limitations and Future Improvements

- **In-memory caches are per process.** With several Gunicorn workers each one builds its own retriever and history cache. This is correct (they rebuild from disk and the database) but uses more memory.
- **Delete does not clean files.** Deleting a PDF removes its database rows, but the file in `media/` and its folder in `faiss_indexes/` stay on disk.
- **No file-type or size validation** on upload yet; a PDF check (extension and MIME type) and a size limit would make it safer.
- **Ephemeral storage on free hosting.** Without a persistent disk, uploads and indexes are lost on redeploy.
- **`ALLOWED_HOSTS = ['*']`** should be narrowed to the real domain in production.
- **Ideas:** streaming answers, page-number citations from chunk metadata, multi-PDF chat, OCR for scanned PDFs, and background indexing for large files.

---

## 🙌 Author

**Sravan** ([@codinghub27](https://github.com/codinghub27)), B.Tech CSE (4th year)

Built as a portfolio project combining Django backend development with a LangChain RAG pipeline.

---

## 📜 License

This project is for educational and portfolio purposes.
