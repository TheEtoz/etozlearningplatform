"""
ETOZ Learning Platform — Streamlit Frontend Entry Point

This is the main file that starts the Streamlit web interface.
Streamlit turns Python scripts into interactive web apps — no HTML/CSS/JS needed.

Why this file exists:
    Students interact with the platform through a browser. Streamlit lets us
    build that interface using only Python. This file is the "home page"
    of the frontend.

How to run:
    From the project root (with venv activated):
        streamlit run frontend/app.py

    Then open: http://localhost:8501
"""

import streamlit as st

# Page configuration must be the first Streamlit command in the script.
st.set_page_config(
    page_title="ETOZ Learning Platform",
    page_icon="🐍",
    layout="wide",
)

st.title("🐍 ETOZ Learning Platform")
st.subheader("Learn Python through practice")

st.markdown(
    """
    Welcome to **ETOZ** — your beginner-friendly programming learning platform.

    ### What you'll be able to do here:
    - 📝 Answer **MCQ** (multiple choice) questions
    - 💻 Solve **Python coding** exercises
    - 📊 Track your **learning progress**
    - 🎯 See your **strengths and weaknesses**

    ---
    *Step 1 complete — Hello World is running! More features coming soon.*
    """
)

st.info("Backend API should be running at http://localhost:8000")
