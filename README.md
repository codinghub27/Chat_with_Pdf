# 📄 Chat with PDF

An AI-powered web application that lets you upload PDF documents and have intelligent conversations with them. Built with Django, LangChain, and Groq — it acts as a smart study assistant that explains concepts from your PDFs like a teacher, not a search engine.

---

## 🚀 Features

- 🔐 **User Authentication** — Register, login, and logout securely
- 📤 **PDF Upload** — Upload and manage your own PDF documents
- 💬 **AI Chat** — Ask questions about your PDF and get intelligent, context-aware answers
- 🧠 **Conversation History** — Chat history is preserved per PDF per user
- 🗑️ **Delete PDFs** — Remove PDFs you no longer need
- 🔒 **Per-user Privacy** — Users can only access their own PDFs

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django |
| AI / RAG | LangChain |
| LLM | Groq API (LLaMA 3.3 70B) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector Store | FAISS |
| Database | PostgreSQL |
| Auth | Django built-in authentication |

---

## ⚙️ Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/chat-with-pdf.git
cd chat-with-pdf
```

### 2. Create and activate virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env` file

Create a `.env` file in the project root and add:

```env
GROQ_API_KEY=your_groq_api_key_here
HF_TOKEN=your_huggingface_token_here
SECRET_KEY=your_django_secret_key_here
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Start the development server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

---

## 📁 Project Structure

```
chat-with-pdf/
├── mysite/                  # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── myapp/                   # Main application
│   ├── models.py            # Profile, ChatMessage models
│   ├── views.py             # Upload, chat, delete views
│   ├── langchain_utils.py   # RAG pipeline (LangChain + FAISS + Groq)
│   ├── forms.py             # PDF upload form
│   └── templates/
│       └── myapp/
│           ├── index.html
│           ├── upload.html
│           └── chat.html
├── faiss_indexes/           # Saved FAISS vector indexes (auto-created)
├── media/                   # Uploaded PDF files
├── requirements.txt
├── .env                     # Environment variables (never commit this)
└── manage.py
```

---

## 🔑 Getting API Keys

- **Groq API Key** — Sign up at [console.groq.com](https://console.groq.com)
- **HuggingFace Token** — Sign up at [huggingface.co](https://huggingface.co/settings/tokens)

---

## 🧠 How It Works

```
User uploads PDF
      ↓
PDF is split into chunks (1000 chars, 200 overlap)
      ↓
Chunks are embedded using HuggingFace all-MiniLM-L6-v2
      ↓
Vectors saved locally using FAISS
      ↓
User asks a question
      ↓
Question + chat history → history-aware retriever
      ↓
Relevant chunks retrieved from FAISS
      ↓
Groq LLaMA 3.3 70B generates answer
      ↓
Answer + history saved to PostgreSQL
```

---

## 📌 Environment Variables Reference

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key for LLM access |
| `HF_TOKEN` | HuggingFace token for embeddings |
| `SECRET_KEY` | Django secret key |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | Database host (localhost for local) |
| `DB_PORT` | Database port (default: 5432) |

---

## 🙌 Author

**Sravan** — B.Tech CSE (4th Year)

Built as a flagship portfolio project combining Django backend development with LangChain RAG pipelines.

---

## 📜 License

This project is for educational and portfolio purposes.