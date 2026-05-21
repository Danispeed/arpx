import streamlit as st
from agents.supervisor import analyze_paper, explain_paper, generate_message_response
from rag.utils import find_num_references
from rag.weaviate_db import clear
import streamlit_mermaid as stmd
from utils.mermaid_sanitizer import sanitize as sanitize_mermaid
from db.history_db import init_db, save_explanation, load_history, update_explanation, save_message
from utils.tts import synthesize as tts_synthesize
import json
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

# Only for testing. Clear weaviate database for each run
if "weaviate_db_cleared" not in st.session_state:
    clear()
    st.session_state.weaviate_db_cleared = True

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
                "mermaid_code": mermaid,
                "image_prompt": item.get("image_prompt", ""),
                "analogy_image": item.get("analogy_image", ""),
                "planner_brief": item.get("planner_brief", ""),
                "quiz": item.get("quiz_json", ""),
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
            topics = analyze_paper(uploaded_file, st.session_state.chat_id, selected_references)
            
            st.session_state.topics = topics
            st.session_state.analyzed = True
            st.session_state.explanation_id = save_explanation(st.session_state.chat_id, topics)
            st.rerun()

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
        import base64 as _b64
        analogy_image = result.get("analogy_image", "")
        text = result.get("text_explanation", "")

        # Render explanation with inline image at [ANALOGY_IMAGE] marker
        if analogy_image and "[ANALOGY_IMAGE]" in text:
            before, after = text.split("[ANALOGY_IMAGE]", 1)
            st.markdown(before)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(_b64.b64decode(analogy_image), use_container_width=True)
            st.markdown(after)
        else:
            st.markdown(text.replace("[ANALOGY_IMAGE]", ""))
            if analogy_image:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.image(_b64.b64decode(analogy_image), use_container_width=True)

        # Audio narration
        tts_key = f"tts_audio_{st.session_state.explanation_id}"
        if st.button("Read aloud"):
            with st.spinner("Generating narration..."):
                st.session_state[tts_key] = tts_synthesize(text)
        audio_bytes = st.session_state.get(tts_key)
        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
        elif tts_key in st.session_state:
            st.warning("Narration is unavailable - the Piper voice model could not be loaded.")

        # Show diagram
        st.subheader("Diagram")

        mermaid_code = result.get("mermaid_code", "")
        if mermaid_code:
            clean_code, diagram_type = sanitize_mermaid(mermaid_code)
            stmd.st_mermaid(clean_code, height=400)
            st.caption(f"Diagram type: {diagram_type}")

        # Comprehension quiz
        quiz_raw = result.get("quiz", "") or ""
        quiz = None
        start, end = quiz_raw.find("{"), quiz_raw.rfind("}")
        if start != -1 and end > start:
            try:
                quiz = json.loads(quiz_raw[start:end + 1])
            except (ValueError, TypeError):
                quiz = None

        questions = (quiz or {}).get("questions") or []
        if questions:
            st.subheader("Test your understanding")
            eid = st.session_state.explanation_id

            with st.form(f"quiz_form_{eid}"):
                for i, q in enumerate(questions):
                    st.markdown(f"**{i + 1}. {q.get('question', '')}**")
                    st.radio(
                        f"q{i}",
                        options=list(range(len(q.get("options", [])))),
                        format_func=lambda idx, opts=q.get("options", []): opts[idx],
                        index=None,
                        key=f"quiz_{eid}_{i}",
                        label_visibility="collapsed",
                    )
                submitted = st.form_submit_button("Submit answers")

            if submitted:
                correct = 0
                for i, q in enumerate(questions):
                    chosen = st.session_state.get(f"quiz_{eid}_{i}")
                    options = q.get("options", [])
                    try:
                        answer = int(q.get("answer_index"))
                    except (TypeError, ValueError):
                        answer = None
                    answer_text = (
                        options[answer]
                        if answer is not None and 0 <= answer < len(options)
                        else "?"
                    )
                    rationale = q.get("rationale", "")
                    if chosen is None:
                        st.warning(f"Q{i + 1}: not answered. Correct answer: {answer_text}. {rationale}")
                    elif chosen == answer:
                        correct += 1
                        st.success(f"Q{i + 1}: correct. {rationale}")
                    else:
                        st.error(f"Q{i + 1}: incorrect. Correct answer: {answer_text}. {rationale}")
                st.info(f"You scored {correct} / {len(questions)}.")

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
            
