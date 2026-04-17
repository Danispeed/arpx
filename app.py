import streamlit as st
from agents.supervisor import analyze_paper, explain_paper

st.title("ARPX - Adaptive Research Paper Explainer")
st.write("Upload a research paper and get a tailored explanation!")

# State (since every user interaction reruns the entire script from top to bottom)
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

if "topics" not in st.session_state:
    st.session_state.topics = None

if "explained" not in st.session_state:
    st.session_state.explained = False

if "explain" not in st.session_state:
    st.session_state.explanation = None
    
# File upload
uploaded_file = st.file_uploader("Upload a research paper of your choice as a PDF", type="pdf")

# Only show analyze button when a PDF is uploaded
if uploaded_file is not None and not st.session_state.analyzed:
    if st.button("Analyze Paper"):
        topics = analyze_paper(uploaded_file)
        st.session_state.topics = topics
        st.session_state.analyzed = True

# Show topics + slider
if st.session_state.analyzed:
    st.subheader("Detected Topics")
    
    st.write(st.session_state.topics)
    
    st.subheader("Choose explanation level")
    
    level = st.slider(
        "Level (1 = very simple, 10 = very technical)",
        min_value=1,
        max_value=10,
        value=5
    )
    
    if st.button("Explain Paper"):
        result = explain_paper(level, st.session_state.topics)
        
        # Just store the resukt for now
        st.session_state.explanation = result
        st.session_state.explained = True

# Display result (raw for now)
if st.session_state.explained:
    st.subheader("Explanation")
    st.write(st.session_state.explanation)
