import streamlit as st
from agents.supervisor import analyze_paper, explain_paper, generate_message_response
from rag.utils import find_num_references
from rag.weaviate_db import clear
import streamlit_mermaid as stmd
from db.history_db import init_db, save_explanation, load_history, update_explanation, save_message, save_chunks
import uuid
from rag.rag_types import retrieve_chunks_naive, retrieve_chunks_llm_query, retrieve_chunks_fusion

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

if "topic_chunks" not in st.session_state:
    st.session_state.topic_chunks = []

if "explain_chunks" not in st.session_state:
    st.session_state.explain_chunks = []

if "message_chunks" not in st.session_state:
    st.session_state.message_chunks = {}
    
init_db()

st.title("ARPX - Adaptive Research Paper Explainer")
st.write("Upload a research paper and get a tailored explanation!")

col1, col2 = st.sidebar.columns([5, 1])

with col1:
    st.markdown(
        """
        <div style="
            font-size: 1.5rem;
            font-weight: 600;
            line-height: 38px;
        ">
            History
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    if st.button("+", help="New Chat", use_container_width=True):
        st.session_state.analyzed = False
        st.session_state.topics = None
        st.session_state.level = 5
        st.session_state.explained = False
        st.session_state.explanation = None
        st.session_state.uploader_key += 1 
        
        st.session_state.chat_id = str(uuid.uuid4())
        st.session_state.explanation_id = None
        st.session_state.chat_messages = []
        
        st.session_state.topic_chunks = []
        st.session_state.explain_chunks = []
        st.session_state.message_chunks = {}
        st.rerun()

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
    
    is_active = (st.session_state.explanation_id == explanation_id)
    
    button_type = "primary" if is_active else "secondary"
    
    if st.sidebar.button(f"{title}", key=f"history_{explanation_id}", use_container_width=True, type=button_type):
        st.session_state.explanation_id = explanation_id
        if chat_id:
            st.session_state.chat_id = chat_id
        if topics:
            st.session_state.analyzed = True
            st.session_state.topics = topics  # Since topics are sored as a list of strings in db
            st.session_state.topic_chunks = item["topic_chunks"]
        
        if level:
            st.session_state.level = level
        
        if text and not text.startswith("Error"):
            st.session_state.explanation = {
                "text_explanation": text,
                "mermaid_code": mermaid
            }
            st.session_state.explain_chunks = item["explain_chunks"]
            st.session_state.explained = True
            st.session_state.chat_messages = messages  
            st.session_state.message_chunks = item["message_chunks"]  
        
        else:
            st.session_state.explanation = None
            st.session_state.explained = False
            st.session_state.chat_messages = []
            st.session_state.explain_chunks = []
            st.session_state.message_chunks = {}
        
        st.rerun()
        
uploaded_file = None

# File upload
if not st.session_state.analyzed:
    uploaded_file = st.file_uploader("Upload a research paper of your choice as a PDF", type="pdf", key=f"file_uploader_{st.session_state.uploader_key}")

# Only show analyze button when a PDF is uploaded
if uploaded_file is not None and not st.session_state.analyzed:
    num_references = find_num_references(uploaded_file)
    
    st.write(f"Found {num_references} references")
    
    selected_references = st.number_input(
        "Select number of references to index",
        min_value=0,
        max_value=num_references,
        value=min(5, num_references)
    )
        
    if st.button("Analyze Paper"):
        with st.spinner("Analyzing paper, extracting topics, and indexing references..."):
            uploaded_file.seek(0)   # Reset pointer
            topics, topic_chunks = analyze_paper(uploaded_file, st.session_state.chat_id, selected_references)
            
            st.session_state.topics = topics
            st.session_state.topic_chunks = topic_chunks
            st.session_state.analyzed = True
            st.session_state.explanation_id = save_explanation(st.session_state.chat_id, topics)
            save_chunks(st.session_state.explanation_id, topic_chunks, "topics")
            st.rerun()

# Show topics + slider
if st.session_state.analyzed:
    st.subheader("Detected Topics")
    
    st.write(st.session_state.topics)
    
    with st.expander("Retrieved chunks used for topics extraction"):
        for i, chunk in enumerate(st.session_state.topic_chunks, 1):
            st.markdown(f"### Chunk {i}")
            st.write(f"Source: {chunk['source']}")
            st.write(chunk["text"])
    
    
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
            result, explain_chunks = explain_paper(level, st.session_state.topics, st.session_state.chat_id)

            text = result.get("text_explanation", "")
            
            if text and explain_chunks and not text.startswith("Error"):
                st.session_state.explanation = result
                st.session_state.explain_chunks = explain_chunks
                st.session_state.explained = True
            
            else:
                st.session_state.explanation = None
                st.session_state.explained = False
                st.session_state.chat_messages = []
                st.markdown(text)

            
            update_explanation(st.session_state.explanation_id, None, result)
            save_chunks(st.session_state.explanation_id, explain_chunks, "explanation")
    
if st.session_state.explained:
    st.subheader("Explanation")
    
    result = st.session_state.explanation
    
    if result:
        # Show text
        st.markdown(result.get("text_explanation", ""))
        
        with st.expander("Retrieved chunks for explanation"):
            for i, chunk in enumerate(st.session_state.explain_chunks, 1):
                st.markdown(f"### Chunk {i}")
                st.write(f"Source: {chunk['source']}")
                st.write(chunk["text"])
        
        # Show diagram
        st.subheader("Diagram")
        
        mermaid_code = result.get("mermaid_code", "")
        if mermaid_code:
            line_count = len(mermaid_code.splitlines())
            
            dynamic_height = min(max(400, line_count * 35), 900)
            
            # Inline view
            stmd.st_mermaid(mermaid_code, height=dynamic_height)
            
            with st.expander("Fullscreen diagram"):
                stmd.st_mermaid(mermaid_code, height=1600)
            
        st.subheader("Ask follow-up questions")
        
        # Show previous messages
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                
                if message["role"] == "assistant":
                    chunks = st.session_state.message_chunks.get(message["id"], [])
                    
                    if chunks:
                        with st.expander("Retrieved chunks"):
                            for i, chunk in enumerate(chunks, 1):
                                st.markdown(f"### Chunk {i}")
                                st.write(f"Source: {chunk['source']}")
                                st.write(chunk["text"])
        
        user_input = st.chat_input("Ask something about the paper and/or the explanation...")
        
        if user_input:       
            # First: save the user message
            user_message_id = save_message(st.session_state.explanation_id, user_input, "user")
            
            result, relevant_chunks = generate_message_response(
                user_input,
                st.session_state.level,
                st.session_state.chat_id,
                st.session_state.chat_messages,
                retrieve_chunks_fusion,
                4,
                1
            )
            response_text = result.get("text_explanation")
            
            # Save assistant message
            assistant_message_id = save_message(st.session_state.explanation_id, response_text, "assistant")
            
            save_chunks(st.session_state.explanation_id, relevant_chunks, "chat", assistant_message_id)
            st.session_state.message_chunks[assistant_message_id] = relevant_chunks
            
            # Update local state
            st.session_state.chat_messages.append({
                "id": user_message_id,
                "role": "user",
                "content": user_input
            })
            
            st.session_state.chat_messages.append({
                "id": assistant_message_id,
                "role": "assistant",
                "content": response_text
            })
            
            st.rerun()
            
