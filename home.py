import streamlit as st
from Job import *
from Utilities import *
from LinkedInProfile import *
import stutils


def first_run():
    st.session_state.first_run = False
    st.session_state.content = ContentProvider("./content")


def initialise_job_from_url():
    print("initialise job from url")
    print(st.session_state.input_job_url)
    st.session_state.job = Job(url=st.session_state.input_job_url)


def initialise_job_from_desc():
    st.session_state.job = Job(job_description=st.session_state.input_job_desc)


# region Render


def render_introduction():
    st.markdown("# Job advert assistant")

    c1, c2, c3 = st.columns([0.5, 0.2, 0.3])

    with c1:
        st.session_state.content.write_content("home_introduction")

    with c3:
        st.session_state.content.write_content("home_motivation")


def render_upload_linkedin_profile():
    st.session_state.content.write_content("home_1_upload_profile")
    st.image("./assets/down_as_pdf.png")
    uploaded_file = st.file_uploader("LinkedIn profile pdf", type=["pdf"])
    if uploaded_file is not None:
        st.session_state.profile = LinkedInProfile(uploaded_file.getvalue())
        uploaded_file = None
        st.rerun()


def render_pull_job():
    st.session_state.content.write_content("home_2_get_job")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("## Get job description from URL.")
        with st.form("job_url", clear_on_submit=True):
            st.text_input(label="Job URL", key="input_job_url")
            st.form_submit_button(on_click=initialise_job_from_url)

    with c2:
        st.markdown("## Paste job description.")
        st.markdown(
            "In some cases the automated retrieval of the job description from url may not work (due to obfuscation). In these cases paste the job descripiton directly below."
        )
        with st.form("job_desc", clear_on_submit=True):
            st.text_area(label="Job description", height=300, key="input_job_desc")
            st.form_submit_button(on_click=initialise_job_from_desc)


# endregion

# region Main body
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
stutils.add_custom_css()

if "first_run" not in st.session_state:
    first_run()
    render_introduction()


if "profile" not in st.session_state:
    render_upload_linkedin_profile()
elif "job" not in st.session_state:
    render_pull_job()
else:
    st.switch_page("./pages/chat.py")


st.write(st.session_state)
# endregion
