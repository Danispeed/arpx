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
                       image_prompt TEXT,
                       analogy_image TEXT,
                       planner_brief TEXT,
                       quiz_json TEXT,
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
    
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS RetrievedChunks (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       explanation_id INTEGER,
                       message_id INTEGER,
                       chunk_type TEXT,
                       source TEXT,
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
            SET text_explanation = ?, mermaid_code = ?,
                image_prompt = ?, analogy_image = ?, planner_brief = ?,
                quiz_json = ?
            WHERE id = ?
        """, (
            result.get("text_explanation"),
            result.get("mermaid_code"),
            result.get("image_prompt", ""),
            result.get("analogy_image", ""),
            result.get("planner_brief", ""),
            result.get("quiz", ""),
            explanation_id,
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
    
    message_id = cursor.lastrowid
    
    connection.commit()
    connection.close()
    
    return message_id

def save_chunks(explanation_id, chunks, chunk_type, message_id=None):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    for chunk in chunks:
        cursor.execute("""
                INSERT INTO RetrievedChunks (
                    explanation_id,
                    message_id,
                    chunk_type,
                    source,
                    content
                )
                VALUES (?, ?, ?, ?, ?)
                """, (
                    explanation_id,
                    message_id,
                    chunk_type,
                    chunk["source"],
                    chunk["text"]
                ))

    connection.commit()
    connection.close()
    

def load_history():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
                   SELECT id, chat_id, title, topics, level, text_explanation, mermaid_code,
                          created_at, image_prompt, analogy_image, planner_brief, quiz_json
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
            "image_prompt": row[8],
            "analogy_image": row[9],
            "planner_brief": row[10],
            "quiz_json": row[11],
            "messages": load_messages(explanation_id),
            "topic_chunks": load_chunks(explanation_id, "topics"),
            "explain_chunks": load_chunks(explanation_id, "explanation"),
            "message_chunks": load_message_chunks(explanation_id)
        })
    
    return history

def load_messages(explanation_id):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
                   SELECT id, role, content
                   FROM Messages
                   WHERE explanation_id = ?
                   ORDER BY created_at ASC
            """, (explanation_id,))
    
    rows = cursor.fetchall()
    connection.close()
    
    return [{"id": mid, "role": r, "content": c} for mid, r, c in rows]

def load_chunks(explanation_id, chunk_type=None, message_id=None):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    query = """
        SELECT source, content
        FROM RetrievedChunks
        WHERE explanation_id = ?
    """
    
    params = [explanation_id]
    
    if chunk_type is not None:
        query += " AND chunk_type = ?"
        params.append(chunk_type)
    
    if message_id is not None:
        query += " AND message_id = ?"
        params.append(message_id)
    
    cursor.execute(query, params)
    
    rows = cursor.fetchall()
    connection.close()
    
    return [
        {
            "source": source,
            "text": text
        }
        for source, text in rows
    ]

def load_message_chunks(explanation_id):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
        SELECT message_id, source, content
        FROM RetrievedChunks
        WHERE explanation_id = ?
        AND chunk_type = 'chat'
        ORDER BY message_id ASC
    """, (explanation_id,))
    
    rows = cursor.fetchall()
    connection.close()
    
    grouped = {}
    
    for message_id, source, content in rows:
        if message_id not in grouped:
            grouped[message_id] = []
        
        grouped[message_id].append({
            "source": source,
            "text": content
        })    
    
    return grouped
    
    
def generate_title(topics):
    print("Topics:", topics)
    
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