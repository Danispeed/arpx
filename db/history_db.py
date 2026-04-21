import sqlite3

DB_PATH = "arpx.db"

def init_db():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS Explanations (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       title TEXT,
                       topics TEXT,
                       level INTEGER,
                       text_explanation TEXT,
                       mermaid_code TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

    connection.commit()
    connection.close()


def save_explanation(topics, level, result):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    title = " | ".join(topics[:2]) if topics else "Untitled"
    
    cursor.execute("""
                   INSERT INTO Explanations (title, topics, level, text_explanation, mermaid_code)
                   VALUES(?, ?, ?, ?, ?)
                   """, (
                       title,
                       str(topics),
                       level,
                       result.get("text_explanation"),
                       result.get("mermaid_code")
                   ))
    
    connection.commit()
    connection.close()


def load_history():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    
    cursor.execute("""
                   SELECT id, title, topics, level, text_explanation, mermaid_code, created_at
                   FROM Explanations
                   ORDER BY created_at DESC
                """)
    
    rows = cursor.fetchall()
    connection.close()
    
    return rows