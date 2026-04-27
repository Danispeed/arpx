import sqlite3
from dotenv import load_dotenv
from openai import AzureOpenAI
import os

DB_PATH = "arpx.db"

load_dotenv()

_AZURE_API_VERSION = (os.getenv("AZURE_OPENAI_API_VERSION") or "").strip() or "2024-10-21"
_AZURE_ENDPOINT = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip().rstrip("/")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=_AZURE_API_VERSION,
    azure_endpoint=_AZURE_ENDPOINT or None,
)

def init_db():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Explanations (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       chat_id TEXT,
                       title TEXT,
                       topics TEXT,
                       level INTEGER,
                       text_explanation TEXT,
                       mermaid_code TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
    
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Messages (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       explanation_id INTEGER,
                       role TEXT,
                       content TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )
                   """)

    connection.commit()
    connection.close()


def save_explanation(chat_id, topics):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    title = generate_title(topics)
    
    cursor.execute("""
                   INSERT INTO Explanations (chat_id, title, topics)
                   VALUES(?, ?, ?)
                   """, (
                       chat_id,
                       title,
                       str(topics),
                   ))
    
    explanation_id = cursor.lastrowid
    
    connection.commit()
    connection.close()
    
    return explanation_id

def update_explanation(explanation_id, level=None, result=None):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    if level is not None:
        cursor.execute("""
            UPDATE Explanations
            SET level = ?
            WHERE id = ?
        """, (level, explanation_id))
    
    if result is not None:
        cursor.execute("""
            UPDATE Explanations
            SET text_explanation = ?, mermaid_code = ?
            WHERE id = ?
        """, (
            result.get("text_explanation"),
            result.get("mermaid_code"),
            explanation_id
        ))
    
    connection.commit()
    connection.close()
    
def save_message(explanation_id, message_content, role):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
                   INSERT INTO Messages (explanation_id, role, content)
                   VALUES(?, ?, ?)
                """, (explanation_id, role, message_content))
    
    connection.commit()
    connection.close()
    

def load_history():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
                   SELECT id, chat_id, title, topics, level, text_explanation, mermaid_code, created_at
                   FROM Explanations
                   ORDER BY created_at DESC
                """)
    
    rows = cursor.fetchall()
    connection.close()
    
    history = []
    
    for row in rows:
        explanation_id = row[0]
        
        history.append({
            "id": explanation_id,
            "chat_id": row[1],
            "title": row[2],
            "topics": row[3],
            "level": row[4],
            "text_explanation": row[5],
            "mermaid_code": row[6],
            "created_at": row[7],
            "messages": load_messages(explanation_id)
        })
    
    return history

def load_messages(explanation_id):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
                   SELECT role, content
                   FROM Messages
                   WHERE explanation_id = ?
                   ORDER BY created_at ASC
            """, (explanation_id,))
    
    rows = cursor.fetchall()
    connection.close()
    
    return [{"role": r, "content": c} for r, c in rows]
    
def generate_title(topics):
    print("Topics:", topics)
    
    # HERE: could also just send the paper to the llm (I dont think that would be too much to send)
    prompt = f"""
    Generate a short, clear title (max 3 words) for a research paper explanation.
    
    Use the topics as the main signal.
    
    Topics: {topics}
    
    Rules:
    - Max 6 words
    - No punctuation except spaces
    - No quotes
    - Make it human readable
    
    Example:
    "Distributed Consensus Overview"
    """
    
    response = client.chat.completions.create(
        model=(os.getenv("AZURE_OPENAI_DEPLOYMENT") or "").strip(),
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    title = response.choices[0].message.content.strip()
    return title