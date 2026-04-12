import streamlit as st
from agents.supervisor import analyze_paper

st.title("ARPX - Adaptive Research Paper Explainer")
st.write("Upload a research paper and get a tailored explanation!")

# State (since every user interaction reruns the entire script from top to bottom)
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

if "topics" not in st.session_state:
    st.session_state.topics = None

if "debug_info" not in st.session_state:
    st.session_state.debug_info = ""

# File upload
uploaded_file = st.file_uploader("Upload a research paper of your choice as a PDF", type="pdf")

# Only show analyze button when a PDF is uploaded
if uploaded_file is not None and not st.session_state.analyzed:
    if st.button("Analyze Paper"):
        topics = analyze_paper(uploaded_file)
        st.session_state.analyzed = True

if st.session_state.analyzed:
    st.subheader("Detected Topics")
    
    for topic in st.session_state.topics:
        st.write(f"- {topic}")
