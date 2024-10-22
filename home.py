import streamlit as st
from Job import *
from Utilities import *
from LinkedInProfile import *
from stutils import *


def first_run():
    st.session_state.first_run = False
    st.session_state.content = ContentProvider("./content")
    init_config()


def initialise_job_from_url():
    st.session_state.job_checked = False
    print("initialise job from url")
    print(st.session_state.input_job_url)
    st.session_state.job = Job(url=st.session_state.input_job_url)


def initialise_job_from_desc():
    st.session_state.job = Job(job_description=st.session_state.input_job_desc)


def initialise_job(job_url: str, job_description: str):
    if len(job_url) >= 6:
        job_description = Job(url=job_url).job_description
    elif len(job_description) >= 20:
        pass
    else:
        print("Reloading app as no job information is provided.")
        st.rerun()

    if st.session_state.use_llm_job_description_formatter:
        st.session_state.job_description = format_job_description(job_description)
        st.session_state.job = Job(
            job_description=st.session_state.job_description["checked"]
        )
        st.session_state.job_checked = False
    else:
        st.session_state.job_description = {"unformatted": job_description}
        st.session_state.job = Job(
            job_description=st.session_state.job_description["unformatted"]
        )
        st.session_state.job_checked = False


# region Render


def render_introduction():
    st.markdown("# Job advert assistant")

    c1, c2, c3 = st.columns([0.5, 0.1, 0.4])

    with c1:
        st.session_state.content.write_content("home_introduction")

    with c3:
        st.session_state.content.write_content("home_motivation")


def render_upload_linkedin_profile():
    st.session_state.content.write_content("home_1_upload_profile")
    st.image("./assets/down_as_pdf.png")
    uploaded_file = st.file_uploader("LinkedIn profile pdf", type=["pdf"])
    if uploaded_file is not None:
        st.session_state.profile = LinkedInProfile()
        st.session_state.profile.build_profile_from_pdf(uploaded_file.getvalue())
        uploaded_file = None
        st.rerun()


def render_build_profile(submit_text: str = "Submit"):
    if "profile" in st.session_state:
        p = st.session_state.profile.profile
    else:
        p = LinkedInProfile()
        p.build_profile_from_parts("", "", "", "")
        p = p.profile

    with st.form(key="build_profile_from_parts"):
        headline = st.text_area(
            label="Profile headline", value=p["my profile headline"], height=20
        )
        summary = st.text_area(label="Profile summary", value=p["my profile summary"])
        skills = st.text_area(label="Skills (list)", value=p["my top skills"])
        experience = st.text_area(
            label="Job experience", height=300, value=p["my experience"]
        )

        if st.form_submit_button(submit_text):
            st.session_state.profile = LinkedInProfile()
            st.session_state.profile.build_profile_from_parts(
                skills, headline, summary, experience
            )
            st.session_state.bypass_profile_check = True
            st.rerun()


def render_upload_profile_from_text():
    st.session_state.content.write_content("home_1_profile_from_text")
    st.image("./assets/profile_example.png")

    f = st.file_uploader("Your profile as text file", type=["txt", "json"])
    if f is not None:
        st.session_state.profile = LinkedInProfile()
        st.session_state.profile.build_profile_from_string(f.getvalue().decode("utf-8"))
        f = None
        st.session_state.bypass_profile_check = True
        st.rerun()


def build_profile_from_parts(skills: str):
    st.session_state.skills = skills
    st.session_state.profile = LinkedInProfile()
    st.session_state.profile.build_profile_from_parts(
        skills=skills, headline="", summary="", experience=""
    )
    st.session_state.bypass_profile_check = True


def render_pull_job():
    st.session_state.content.write_content("home_2_get_job")

    with st.container():
        print(f"Use llm formatter {st.session_state.use_llm_job_description_formatter}")
        st.toggle(
            label="Format job description using LLM",
            key="use_llm_job_description_formatter",
            value=st.session_state.use_llm_job_description_formatter,
        )
        st.markdown(
            "_Caution: it is not possible to guarantee that the LLM will not remove or modify some parts of the job description._"
        )
        st.markdown(" ")

    with st.form("get_job", clear_on_submit=True):
        st.markdown("### Get job description using URL")
        st.markdown(
            "_Caution: this may not work for all websites. Job description returned may contain errors and bits of HTML code._"
        )
        job_url = st.text_input(label="Job advert URL")

        st.divider()

        st.markdown("### Input job description directly")
        job_description = st.text_area(label="Job description", height=300)

        if st.form_submit_button():
            initialise_job(job_url, job_description)
            st.rerun()


def render_job_check():

    labels = {
        "unformatted": "Original, unmodified job description",
        "formatted": "Formatting first pass",
        "checked": "Formatted and checked (2nd pass)",
    }

    st.session_state.content.write_content("home_3_check")
    st.write(" ")

    cols = st.columns(len(st.session_state.job_description.keys()))

    for index, (key, value) in enumerate(st.session_state.job_description.items()):
        with cols[index]:
            human_redable_label = labels[key] if key in labels.keys() else key

            st.text_area(label=human_redable_label, value=value, height=500)
            if st.button("Use this job description", key=f"check_job_{key}"):
                st.session_state.job = Job(job_description=value)
                st.session_state.job_checked = True
                st.switch_page("./pages/chat.py")

    st.write(
        "If the job description does not look right please fall back to pasting in job description."
    )
    if st.button("Something went wrong. Go back."):
        del st.session_state["job"]
        st.rerun()


def render_profile_check():
    st.write(" ")
    st.write("Please check your profile. You can edit it below.")

    render_build_profile("Use this profile")


# endregion


# region Main body
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
add_custom_css()

if "first_run" not in st.session_state:
    first_run()
    render_introduction()

if "profile" not in st.session_state:
    st.session_state.content.write_content("home_1_profile")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_upload_linkedin_profile()

    with c2:
        st.session_state.content.write_content("home_1_build_profile")
        render_build_profile()

    with c3:
        render_upload_profile_from_text()
elif not st.session_state.bypass_profile_check:
    render_profile_check()
elif "job" not in st.session_state:
    render_pull_job()
elif not st.session_state.job_checked:
    render_job_check()
else:
    st.switch_page("./pages/chat.py")
# endregion
