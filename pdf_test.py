import streamlit as st
from LinkedInProfile import *
from haystack.dataclasses import ByteStream

uploaded_file = st.file_uploader("LinkedIn profile pdf", type=["pdf"])
if uploaded_file is not None:
    st.session_state["profile"] = LinkedInProfile(uploaded_file.getvalue())
    st.write(st.session_state.profile)
    st.write(st.session_state.profile.p)
