from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain,create_history_aware_retriever
from langchain_core.messages import HumanMessage,AIMessage
from .models import ChatMessage
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

load_dotenv()
os.environ["USER_AGENT"] = "langchain-rag-app"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

groq_key = os.getenv("GROQ_API_KEY")
hf_token = os.getenv("HF_TOKEN")
if groq_key:
    os.environ["GROQ_API_KEY"] = groq_key
if hf_token:
    os.environ["HF_TOKEN"] = hf_token

# Load embedding model ONCE at module level
_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    return _embeddings
# In-memory retriever cache
retrievers = {}

chat_histories={}
FAISS_INDEX_DIR="faiss_indexes"
os.makedirs(FAISS_INDEX_DIR,exist_ok=True)


def process_pdf(pdf_path,pdf_id):
    index_path=os.path.join(FAISS_INDEX_DIR,str(pdf_id))

    # ✅ If already saved on disk, just load it
    if os.path.exists(index_path):
        db=FAISS.load_local(index_path,get_embeddings(),allow_dangerous_deserialization=True)
        return db.as_retriever()





    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    documents = splitter.split_documents(docs)

    db = FAISS.from_documents(
        documents,
        get_embeddings()
    )
    db.save_local(index_path)

    return db.as_retriever()






def get_answer(retriever, question, user_id, pdf_id):

    llm = ChatGroq(model="llama-3.3-70b-versatile")

    # ── 1. History-aware retriever ──────────────────────────────────────────
    # Rewrites the user's question using chat history before searching the PDF.
    # Example: "What about the next chapter?" becomes a standalone question.

    contextualize_prompt=ChatPromptTemplate.from_messages([
        ("system",
        """Given the chat history and the latest user question,
        rewrite it as a standalone question that makes sense without the history.
        Do not answer it - just rewrite it. If it's already standalone, return it as-is."""),
        MessagesPlaceholder("chat_history"),
        ("human","{input}"),
    ])
    history_aware_retriever=create_history_aware_retriever(
        llm,retriever,contextualize_prompt
    )

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system",
         """You are a smart, friendly study assistant helping a student understand an uploaded PDF document.

    BEHAVIOR RULES:

    1. PDF first, always
       Use the provided context from the PDF as your primary source.
       If the answer is clearly in the PDF, explain it — do not just quote it back.

    2. Teach, don't recite
       Explain like a teacher talking to a student, not like a search engine returning results.
       Use simple language, analogies, and examples where helpful.
       Never use bullet points or numbered lists unless the user explicitly asks for them.
       Write in flowing, connected paragraphs.

    3. Fill gaps honestly
       If the PDF context is incomplete or unclear on the topic, expand using your general knowledge.
       When you do this, say something like "Beyond what the PDF covers..." or
       "To add some context the PDF doesn't include..." — so the student knows the source.

    4. Use conversation history
       If the student's question refers to something discussed earlier (e.g. "explain that more",
       "give me a quiz on that", "what did you mean by point 2"), use the prior conversation
       to understand what they mean. Do not ask them to repeat themselves.

    5. Out of scope questions
       If the question is completely unrelated to the PDF topic, politely say so in one sentence,
       then offer to help with something from the PDF instead.

    6. Length matches the question
       Short factual question → concise answer (2-4 sentences).
       Conceptual question → full explanation (as long as needed).
       "Summarize" or "explain everything" → structured but still conversational response.

    <context>
    {context}
    </context>"""),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # document_chain = create_stuff_documents_chain(llm, prompt)
    # retriever_chain = create_retrieval_chain(retriever, document_chain)
    # response = retriever_chain.invoke({'input': question})
    # return response['answer']

    doc_chain=create_stuff_documents_chain(llm,qa_prompt)
    rag_chain=create_retrieval_chain(history_aware_retriever,doc_chain)
    # ── 3. Retrieve or create history for this (user, pdf) pair ─────────────

    history_key=(user_id,pdf_id)
    if history_key not in chat_histories:
        # rebuild from db on restart
        past_msgs=ChatMessage.objects.filter(user_id=user_id,pdf_id=pdf_id).order_by('created_at').values_list('question','answer')
        rebuilt=[]
        for q,a in past_msgs:
            rebuilt.append(HumanMessage(content=q))
            rebuilt.append(AIMessage(content=a))
        chat_histories[history_key]=rebuilt[-20:]
    history=chat_histories[history_key]

    # ── 4. Run the chain ────────────────────────────────────────────────────
    response=rag_chain.invoke({
        "input":question,
        "chat_history":history,
    })
    answer=response["answer"]
    # ── 5. Append to history ─────────────────────────────────────────────────
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))

    # Optional: cap history to last 10 exchanges (20 messages) to avoid token bloat
    if len(history) > 20:
        chat_histories[history_key] = history[-20:]
    print(history)

    return answer



