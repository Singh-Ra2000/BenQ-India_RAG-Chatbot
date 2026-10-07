"""
=====================================================
  RAG CHATBOT — STEP 4 & 5: Chatbot + Web Interface
  Your BenQ Projector FAQ Chatbot!
=====================================================
WHAT THIS DOES:
  - Opens a chat window in your browser
  - Customer types a question
  - Searches your ChromaDB for relevant chunks
  - Sends chunks + question to OpenAI
  - Returns an accurate answer from YOUR documents

HOW TO USE:
  1. Open this file in Notepad
  2. Paste your OpenAI API key below
  3. Save and close
  4. Run: python chatbot.py
  5. Open your browser and go to: http://localhost:5000
"""

from flask import Flask, request, jsonify, render_template_string
import chromadb
from openai import OpenAI
import json
from pathlib import Path

# ══════════════════════════════════════════════════
#   ✏️  PASTE YOUR OPENAI API KEY HERE
# ══════════════════════════════════════════════════

import os
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "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")

# ══════════════════════════════════════════════════
#   SETTINGS
# ══════════════════════════════════════════════════

DB_FOLDER      = "output/chroma_db"
COLLECTION     = "projector_faq"
RESULTS_COUNT  = 5       # how many chunks to retrieve per question
MODEL          = "gpt-4o-mini"   # cheap, fast, very capable

# ══════════════════════════════════════════════════
#   CHAT PAGE HTML — the interface customers see
# ══════════════════════════════════════════════════

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BenQ Projector Support</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f0f2f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .chat-container {
            width: 100%;
            max-width: 780px;
            height: 92vh;
            background: white;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.12);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .chat-header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: white;
            padding: 18px 24px;
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .logo {
            width: 42px; height: 42px;
            background: #6c63ff;
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 20px;
        }
        .header-text h2 { font-size: 17px; font-weight: 600; }
        .header-text p  { font-size: 12px; opacity: 0.7; margin-top: 2px; }
        .status-dot {
            width: 8px; height: 8px;
            background: #4ade80;
            border-radius: 50%;
            display: inline-block;
            margin-right: 5px;
        }
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .message {
            max-width: 80%;
            padding: 12px 16px;
            border-radius: 16px;
            font-size: 14px;
            line-height: 1.6;
        }
        .bot-message {
            background: #f1f5f9;
            border-radius: 4px 16px 16px 16px;
            align-self: flex-start;
            color: #1e293b;
        }
        .user-message {
            background: linear-gradient(135deg, #6c63ff, #4f46e5);
            color: white;
            border-radius: 16px 4px 16px 16px;
            align-self: flex-end;
        }
        .sources {
            font-size: 11px;
            margin-top: 8px;
            opacity: 0.6;
            border-top: 1px solid #e2e8f0;
            padding-top: 6px;
        }
        .typing {
            display: flex; gap: 4px; padding: 14px 16px;
            background: #f1f5f9;
            border-radius: 4px 16px 16px 16px;
            align-self: flex-start;
            width: fit-content;
        }
        .typing span {
            width: 8px; height: 8px;
            background: #94a3b8;
            border-radius: 50%;
            animation: bounce 1.2s infinite;
        }
        .typing span:nth-child(2) { animation-delay: 0.2s; }
        .typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-8px); }
        }
        .input-area {
            padding: 16px 20px;
            border-top: 1px solid #e2e8f0;
            display: flex;
            gap: 10px;
            background: white;
        }
        .input-area input {
            flex: 1;
            padding: 12px 16px;
            border: 1.5px solid #e2e8f0;
            border-radius: 24px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }
        .input-area input:focus { border-color: #6c63ff; }
        .send-btn {
            width: 46px; height: 46px;
            background: linear-gradient(135deg, #6c63ff, #4f46e5);
            color: white;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            font-size: 18px;
            display: flex; align-items: center; justify-content: center;
            transition: transform 0.1s;
        }
        .send-btn:hover { transform: scale(1.05); }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .suggestions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding: 0 24px 16px;
        }
        .suggestion-btn {
            background: #f1f5f9;
            border: 1px solid #e2e8f0;
            border-radius: 20px;
            padding: 6px 14px;
            font-size: 12px;
            cursor: pointer;
            color: #475569;
            transition: all 0.2s;
        }
        .suggestion-btn:hover {
            background: #6c63ff;
            color: white;
            border-color: #6c63ff;
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
    </style>
</head>
<body>
<div class="chat-container">
    <div class="chat-header">
        <div class="logo">📽️</div>
        <div class="header-text">
            <h2>BenQ Projector Support</h2>
            <p><span class="status-dot"></span>Online — Ask me anything about your projector</p>
        </div>
    </div>

    <div class="messages" id="messages">
        <div class="message bot-message">
            👋 Hi! I'm your BenQ Projector assistant.<br><br>
            I can help you with:<br>
            • <strong>Product specs</strong> (brightness, resolution, connectivity)<br>
            • <strong>Troubleshooting</strong> (setup, display, audio issues)<br>
            • <strong>How-to guides</strong> (Bluetooth, AirPlay, screen mirroring)<br><br>
            What would you like to know?
        </div>
    </div>

    <div class="suggestions" id="suggestions">
        <button class="suggestion-btn" onclick="ask(this.innerText)">What is the brightness of GV50?</button>
        <button class="suggestion-btn" onclick="ask(this.innerText)">How to connect Bluetooth?</button>
        <button class="suggestion-btn" onclick="ask(this.innerText)">Why is my image blurry?</button>
        <button class="suggestion-btn" onclick="ask(this.innerText)">Does GV32 support Netflix?</button>
    </div>

    <div class="input-area">
        <input type="text" id="userInput" placeholder="Type your question here..."
               onkeypress="if(event.key==='Enter') sendMessage()">
        <button class="send-btn" id="sendBtn" onclick="sendMessage()">➤</button>
    </div>
</div>

<script>
    function addMessage(text, isUser, sources) {
        const messages = document.getElementById('messages');
        const div = document.createElement('div');
        div.className = 'message ' + (isUser ? 'user-message' : 'bot-message');
        div.innerHTML = text.replace(/\\n/g, '<br>');
        if (sources && sources.length > 0) {
            const srcDiv = document.createElement('div');
            srcDiv.className = 'sources';
            srcDiv.innerHTML = '📄 Sources: ' + sources.join(', ');
            div.appendChild(srcDiv);
        }
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    function showTyping() {
        const messages = document.getElementById('messages');
        const div = document.createElement('div');
        div.className = 'typing'; div.id = 'typing';
        div.innerHTML = '<span></span><span></span><span></span>';
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    function hideTyping() {
        const t = document.getElementById('typing');
        if (t) t.remove();
    }

    function ask(question) {
        document.getElementById('userInput').value = question;
        sendMessage();
    }

    async function sendMessage() {
        const input = document.getElementById('userInput');
        const btn   = document.getElementById('sendBtn');
        const text  = input.value.trim();
        if (!text) return;

        // Hide suggestions after first message
        document.getElementById('suggestions').style.display = 'none';

        addMessage(text, true);
        input.value = '';
        btn.disabled = true;
        showTyping();

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: text })
            });
            const data = await response.json();
            hideTyping();
            if (data.error) {
                addMessage('Sorry, something went wrong. Please try again.', false);
            } else {
                addMessage(data.answer, false, data.sources);
            }
        } catch (e) {
            hideTyping();
            addMessage('Connection error. Is the server running?', false);
        }

        btn.disabled = false;
        input.focus();
    }
</script>
</body>
</html>
"""

# ══════════════════════════════════════════════════
#   CHATBOT ENGINE
# ══════════════════════════════════════════════════

app    = Flask(__name__)
client = None
collection = None


def setup():
    """Load ChromaDB and connect to OpenAI on startup."""
    global client, collection

    # Check API key
    if not OPENAI_API_KEY or OPENAI_API_KEY.strip() == "":
        print("\n❌  No API key! Open chatbot.py in Notepad and paste your key.")
        exit()

    # Connect to OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY.strip())
    print("✅  Connected to OpenAI")

    # Load ChromaDB
    if not Path(DB_FOLDER).exists():
        print(f"\n❌  Database not found at {DB_FOLDER}")
        print("    Run build_db.py first!")
        exit()

    db = chromadb.PersistentClient(path=DB_FOLDER)
    collection = db.get_collection(name=COLLECTION)
    count = collection.count()
    print(f"✅  Loaded ChromaDB — {count} chunks ready")


def get_embedding(text):
    """Convert a question into a vector using OpenAI."""
    response = client.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


def search_db(question, n=RESULTS_COUNT):
    """Find the most relevant chunks for the question."""
    embedding = get_embedding(question)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=n,
        include=["documents", "metadatas", "distances"]
    )
    chunks    = results["documents"][0]
    metadatas = results["metadatas"][0]
    return chunks, metadatas


def build_answer(question, chunks, metadatas):
    """Send question + relevant chunks to OpenAI and get an answer."""

    # Build context from retrieved chunks
    context = ""
    for i, (chunk, meta) in enumerate(zip(chunks, metadatas)):
        source = meta.get("source", "unknown")
        context += f"\n[Source {i+1}: {source}]\n{chunk}\n"

    # The system prompt tells the AI how to behave
    system_prompt = """You are a helpful customer support assistant for BenQ portable projectors.

Your job is to answer questions about BenQ projectors accurately and helpfully.

Rules:
- Answer ONLY based on the context provided below
- If the answer is not in the context, say "I don't have that information, please contact BenQ support at support.benq.com"
- Be friendly, clear and concise
- For technical issues, give step-by-step instructions
- If someone asks about a specific model, focus on that model's information
- Don't make up specifications or features"""

    user_message = f"""Context from BenQ documents:
{context}

Customer question: {question}

Please answer the customer's question based on the context above."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message}
        ],
        temperature=0.3,   # lower = more factual, less creative
        max_tokens=600
    )

    return response.choices[0].message.content


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/chat", methods=["POST"])
def chat():
    try:
        question = request.json.get("question", "").strip()
        if not question:
            return jsonify({"error": "Empty question"})

        # Search the database
        chunks, metadatas = search_db(question)

        # Get unique source file names
        sources = list(set(
            m.get("source", "").replace(".txt", "").replace("_", " ")
            for m in metadatas
            if m.get("source")
        ))[:3]

        # Generate answer
        answer = build_answer(question, chunks, metadatas)

        return jsonify({
            "answer":  answer,
            "sources": sources
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)})


# ══════════════════════════════════════════════════
#   START
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═"*55)
    print("  📽️   BenQ Projector FAQ Chatbot")
    print("  Powered by RAG + ChromaDB + OpenAI")
    print("═"*55)

    setup()

    print(f"\n  🌐  Starting web server...")
    print(f"  ✅  Chatbot is LIVE!")
    print(f"\n  👉  Open your browser and go to:")
    print(f"      http://localhost:5000")
    print(f"\n  Press Ctrl+C to stop the chatbot\n")

    app.run(debug=False, port=5000)
