import streamlit as st
import yaml


def add_custom_css():
    with open("style.css", "r") as f:
        css = f"<style>{f.read()}</style>"
    st.markdown(css, unsafe_allow_html=True)
