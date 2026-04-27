import streamlit as st
from agents.supervisor import analyze_paper, explain_paper, generate_message_response
import streamlit_mermaid as stmd
from db.history_db import init_db, save_explanation, load_history, update_explanation, save_message
import uuid

# State (since every user interaction reruns the entire script from top to bottom)
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

if "topics" not in st.session_state:
    st.session_state.topics = None

if "level" not in st.session_state:
    st.session_state.level = 5

if "explained" not in st.session_state:
    st.session_state.explained = False

if "explanation" not in st.session_state:
    st.session_state.explanation = None

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())
    
if "explanation_id" not in st.session_state:
    st.session_state.explanation_id = None

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


init_db()

st.title("ARPX - Adaptive Research Paper Explainer")
st.write("Upload a research paper and get a tailored explanation!")

st.sidebar.title("History")

history = load_history()

for item in history:
    explanation_id = item["id"]
    chat_id = item["chat_id"]
    title = item["title"]
    topics = item["topics"]
    level = item["level"]
    text = item["text_explanation"]
    mermaid = item["mermaid_code"]
    messages = item["messages"]
    
    if st.sidebar.button(f"{title}", key=f"history_{explanation_id}"):
        st.session_state.explanation_id = explanation_id
        if chat_id:
            st.session_state.chat_id = chat_id
        if topics:
            st.session_state.analyzed = True
            st.session_state.topics = topics  # Since topics are sored as a list of strings in db
        
        if level:
            st.session_state.level = level
        
        if text and not text.startswith("Error"):
            st.session_state.explanation = {
                "text_explanation": text,
                "mermaid_code": mermaid
            }
            st.session_state.explained = True
            st.session_state.chat_messages = messages    
        
        else:
            st.session_state.explanation = None
            st.session_state.explained = False
            st.session_state.chat_messages = []

if st.sidebar.button("New Chat"):
    st.session_state.analyzed = False
    st.session_state.topics = None
    st.session_state.level = 5
    st.session_state.explained = False
    st.session_state.explanation = None
    st.session_state.uploader_key += 1 
    
    st.session_state.chat_id = str(uuid.uuid4())
    st.session_state.explanation_id = None
    st.session_state.chat_messages = []
    
    st.rerun()
        
uploaded_file = None

# File upload
if not st.session_state.analyzed:
    uploaded_file = st.file_uploader("Upload a research paper of your choice as a PDF", type="pdf", key=f"file_uploader_{st.session_state.uploader_key}")

# Only show analyze button when a PDF is uploaded
if uploaded_file is not None and not st.session_state.analyzed:
    if st.button("Analyze Paper"):
        topics = analyze_paper(uploaded_file, st.session_state.chat_id)
        st.session_state.topics = topics
        st.session_state.analyzed = True
        st.session_state.explanation_id = save_explanation(st.session_state.chat_id, topics)

# Show topics + slider
if st.session_state.analyzed:
    st.subheader("Detected Topics")
    
    st.write(st.session_state.topics)
    
    st.subheader("Choose explanation level")
    
    level = st.slider(
        "Level (1 = very simple, 10 = very technical)",
        min_value=1,
        max_value=10,
        value=st.session_state.level
    )
    
    update_explanation(st.session_state.explanation_id, level, None)
    st.session_state.level = level
    
    if st.button("Explain Paper"):
        with st.spinner("Generating explanation (this may take up to 2 minutes for large papers)..."):
            result = explain_paper(level, st.session_state.topics, st.session_state.chat_id)
            
            text = result.get("text_explanation")
            
            if text and not text.startswith("Error"):
                st.session_state.explanation = result
                st.session_state.explained = True
            
            else:
                st.session_state.explanation = None
                st.session_state.explained = False
                st.session_state.chat_messages = []
                st.markdown(text)

            
            update_explanation(st.session_state.explanation_id, None, result)
    
if st.session_state.explained:
    st.subheader("Explanation")
    
    result = st.session_state.explanation
    
    if result:
        # Show text
        st.markdown(result.get("text_explanation", ""))
        
        # Show diagram
        st.subheader("Diagram")
        
        mermaid_code = result.get("mermaid_code", "")
        if mermaid_code:
            stmd.st_mermaid(mermaid_code)
            
        st.subheader("Ask follow-up questions")
        
        # Show previous messages
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        user_input = st.chat_input("Ask something about the paper and/or the explanation...")
        
        if user_input:
            # First: save the user message
            save_message(st.session_state.explanation_id, user_input, "user")
            
            result = generate_message_response(
                user_input,
                st.session_state.level,
                st.session_state.chat_id,
                st.session_state.chat_messages
            )
            
            response_text = result.get("text_explanation")
            
            # Save assistant message
            save_message(st.session_state.explanation_id, response_text, "assistant")
            
            # Update local state
            st.session_state.chat_messages.append({
                "role": "user",
                "content": user_input
            })
            
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": response_text
            })
            
            st.rerun()
            
