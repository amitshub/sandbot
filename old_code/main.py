# from fastapi import FastAPI, Form
# from fastapi.responses import HTMLResponse
# from pydantic import BaseModel
# import os
# from groq import Groq
# from dotenv import load_dotenv
# from rag import retrieve

# load_dotenv()

# app = FastAPI()
# client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# class ChatRequest(BaseModel):
#     message: str
#     history: list = []


# def generate_ai_reply(user_message: str, history: list = []):
#     docs = retrieve(user_message)

#     context = "\n\n".join([
#         f"Source: {doc['url']}\nContent: {doc['text']}"
#         for doc in docs
#     ])
#     conversation = "\n".join(history[-5:])

#     prompt = f"""
# You are a helpful business assistant.

# Answer ONLY using provided context.
# If answer is not found, say: "I will connect you with our team."

# Context:
# {context}

# Conversation:
# {conversation}

# User:
# {user_message}
# """

#     completion = client.chat.completions.create(
#         model="llama-3.1-8b-instant",
#         messages=[
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0.2,
#     )

#     return completion.choices[0].message.content

# @app.post("/ai-reply")
# def ai_reply(req: ChatRequest):

#     user_message = req.message
#     history = req.history

#     # 🔍 DEBUG: check retrieval
#     docs = retrieve(user_message)
#     print("\n🔎 Retrieved Docs:\n", docs)   # 👈 ADD HERE

#     # Build context
#     context = "\n\n".join([
#         f"Source: {doc['url']}\nContent: {doc['text']}"
#         for doc in docs
#     ])

#     conversation = "\n".join(history[-5:])

#     prompt = f"""
# Answer ONLY using context.

# Context:
# {context}

# Conversation:
# {conversation}

# User:
# {user_message}
# """

#     completion = client.chat.completions.create(
#         model="llama-3.1-8b-instant",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.2,
#     )

#     reply = completion.choices[0].message.content

#     return {"reply": reply}




# @app.get("/", response_class=HTMLResponse)
# def home():
#     return """
#     <html>
#       <head>
#         <title>RAG Test Chat</title>
#       </head>
#       <body style="font-family:Arial;max-width:700px;margin:40px auto;">
#         <h2>RAG Test Chat</h2>

#         <form method="post" action="/ask">
#           <textarea name="message" rows="5" style="width:100%;padding:10px;" placeholder="Enter your question..."></textarea>
#           <br><br>
#           <button type="submit" style="padding:10px 20px;">Ask AI</button>
#         </form>
#       </body>
#     </html>
#     """


# @app.post("/ask", response_class=HTMLResponse)
# def ask(message: str = Form(...)):
#     reply = generate_ai_reply(message)

#     return f"""
#     <html>
#       <body style="font-family:Arial;max-width:700px;margin:40px auto;">
#         <h2>RAG Test Chat</h2>

#         <p><b>Your question:</b></p>
#         <div style="background:#f5f5f5;padding:12px;border-radius:8px;">
#           {message}
#         </div>

#         <p><b>AI answer:</b></p>
#         <div style="background:#e8fff0;padding:12px;border-radius:8px;">
#           {reply}
#         </div>

#         <br>
#         <a href="/">Ask another question</a>
#       </body>
#     </html>
#     """ 

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import os
import uuid
from html import escape

from groq import Groq
from dotenv import load_dotenv
from backend.rag import retrieve


load_dotenv()

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Temporary local memory for testing UI
# Note: this resets when server restarts
chat_sessions = {}


class ChatRequest(BaseModel):
    message: str
    history: list = []


def generate_ai_reply(user_message: str, history: list = []):
    docs = retrieve(user_message)

    context = "\n\n".join([
        f"Source: {doc['url']}\nContent: {doc['text']}"
        for doc in docs
    ])

    conversation = "\n".join(history[-8:])

    prompt = f"""
You are a helpful business assistant for Sandlus Info Solutions.

Answer ONLY using the provided context.
Use conversation history only to understand follow-up questions.
If the answer is not found in the context, say:
"I will connect you with our team."

Keep replies short, natural, and suitable for WhatsApp.

Context:
{context}

Conversation history:
{conversation}

User:
{user_message}
"""

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content


@app.post("/ai-reply")
def ai_reply(req: ChatRequest):
    reply = generate_ai_reply(req.message, req.history)
    return {"reply": reply}


@app.get("/", response_class=HTMLResponse)
def home(session_id: str = None):
    if not session_id:
        session_id = str(uuid.uuid4())
        chat_sessions[session_id] = []

    if session_id not in chat_sessions:
        chat_sessions[session_id] = []

    history = chat_sessions[session_id]

    chat_html = ""

    if not history:
        chat_html = """
        <div style="text-align:center;color:#999;margin-top:120px;">
            Start testing your RAG chatbot here...
        </div>
        """

    for msg in history:
        role = msg["role"]
        text = escape(msg["content"]).replace("\n", "<br>")

        if role == "user":
            align = "right"
            bg = "#d9fdd3"
            label = "You"
        else:
            align = "left"
            bg = "#f1f1f1"
            label = "Bot"

        chat_html += f"""
        <div style="text-align:{align}; margin:12px 0;">
            <div style="font-size:12px;color:#777;margin-bottom:3px;">{label}</div>
            <div style="
                display:inline-block;
                background:{bg};
                padding:10px 14px;
                border-radius:12px;
                max-width:80%;
                line-height:1.5;
                text-align:left;
            ">
                {text}
            </div>
        </div>
        """

    return f"""
    <html>
      <head>
        <title>RAG Test Chat</title>
      </head>

      <body style="
        font-family:Arial, sans-serif;
        background:#f5f6f7;
        margin:0;
        padding:30px;
      ">

        <div style="
            max-width:850px;
            margin:auto;
            background:#fff;
            border-radius:14px;
            box-shadow:0 4px 20px rgba(0,0,0,0.08);
            overflow:hidden;
        ">

          <div style="
            background:#075e54;
            color:white;
            padding:16px 20px;
            font-size:18px;
            font-weight:bold;
          ">
            Sandlus RAG Test Chat
          </div>

          <div id="chatBox" style="
            padding:20px;
            min-height:420px;
            max-height:520px;
            overflow-y:auto;
            background:#efeae2;
          ">
            {chat_html}
          </div>

          <form method="post" action="/ask" style="
            display:flex;
            gap:10px;
            padding:15px;
            background:#fff;
            border-top:1px solid #ddd;
          ">
            <input type="hidden" name="session_id" value="{session_id}" />

            <textarea
              name="message"
              rows="2"
              required
              placeholder="Type your message..."
              style="
                flex:1;
                resize:none;
                padding:12px;
                border:1px solid #ccc;
                border-radius:10px;
                font-size:14px;
                outline:none;
              "
            ></textarea>

            <button type="submit" style="
              background:#25d366;
              color:white;
              border:none;
              border-radius:10px;
              padding:0 22px;
              font-weight:bold;
              cursor:pointer;
            ">
              Send
            </button>
          </form>

          <div style="
            padding:10px 15px;
            background:#fafafa;
            border-top:1px solid #eee;
            font-size:13px;
          ">
            <a href="/" style="color:#075e54;text-decoration:none;font-weight:bold;">
              Start New Chat
            </a>
          </div>

        </div>

        <script>
          var chatBox = document.getElementById("chatBox");
          chatBox.scrollTop = chatBox.scrollHeight;
        </script>

      </body>
    </html>
    """


@app.post("/ask")
def ask(session_id: str = Form(...), message: str = Form(...)):
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []

    history = chat_sessions[session_id]

    formatted_history = [
        f"{m['role'].capitalize()}: {m['content']}"
        for m in history[-8:]
    ]

    reply = generate_ai_reply(message, formatted_history)

    history.append({
        "role": "user",
        "content": message
    })

    history.append({
        "role": "assistant",
        "content": reply
    })

    return RedirectResponse(
        url=f"/?session_id={session_id}",
        status_code=303
    )