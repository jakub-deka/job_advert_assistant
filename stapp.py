# TODO add ability to set the job url through url parameter
# TODO add readme and bookmarklet
# TODO add ability to provide job description as text
# TODO add switcher for models
# TODO make a favicon
# TODO add controls for more models
import streamlit as st
import yaml
from Job import *
from LLM import *
from Utilities import *


# region Utilities
def get_page_content(content_name: str):
    with open(f"./content/{content_name}.md", "r") as f:
        return f.read()


# endregion


def first_run():
    st.set_page_config(layout="wide", initial_sidebar_state="expanded")
    st.session_state.first_run = False

    st.session_state.pt = PromptTemplater("./prompts")

    # Load the config
    with open("./llm_configurations/llama3.1-8b-free.yml", "r") as f:
        st.session_state.config = yaml.safe_load(f.read())

    st.session_state.llm = LLMwithKnowledge(
        model_name=st.session_state.config["model_name"],
        url=st.session_state.config["url"],
        system_prompt=st.session_state.config["system_prompt"],
        prompt_template=st.session_state.pt.get_prompt("rag"),
        knowledge={},
    )

    # Initialise the key objects and session variables
    if "job_url" in st.query_params:
        st.session_state.job_url = st.query_params.job_url
        initialise_job()

    st.session_state.message_log = []


def initialise_job():
    st.session_state.job = Job(st.session_state.job_url)
    if st.session_state.job.success:
        st.session_state.llm.add_to_knowledge(
            {"job description": st.session_state.job.job_description}
        )


def draw_page():
    with open("style.css", "r") as f:
        css = f"<style>{f.read()}</style>"

    st.markdown(css, unsafe_allow_html=True)

    st.markdown(get_page_content("home_introduction"))

    with st.sidebar:
        with st.expander(label="Current LLM config", icon="🛠️"):
            st.markdown("# Current config")
            st.write(st.session_state.config)

        if "job" in st.session_state:
            st.markdown(st.session_state.job.url)

    with st.form("joburl"):
        job_url = st.session_state.job_url if "job_url" in st.session_state else ""
        st.text_input(label="Job URL", key="job_url", value=job_url)
        st.form_submit_button(on_click=initialise_job)

    if "job" in st.session_state and st.session_state.job.success:
        draw_chat_ui()
        st.columns(1)
        st.write(st.session_state.job.job_description)
    elif "job" in st.session_state and not st.session_state.job.success:
        st.write("Error occured when retrieving the job details.")
        st.write(st.session_state.job.job_description)
    else:
        st.write("Provide job url and hit submit to begin.")


def draw_side_questions():
    st.markdown("### Common questions")

    qs = [
        "What is the company name and the role title?",
        "What country and city is this role based in?",
        "What is the salary for this role?",
        "Is this role office based, remote or hybrid?",
        "Summarise key responsibilities in a short list.",
        "Summarise requirements specified for this role.",
    ]

    for q in qs:
        draw_question(q)


def draw_question(question: str):
    if st.button(label=question, use_container_width=True):
        ask_llm(question)


def redraw_chat_history():
    with st.session_state.chat_container:
        for m in st.session_state.message_log:
            add_message_to_chat_history(m)


def add_message_to_chat_history(message: dict[str, str]):
    with st.session_state.chat_container:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                st.markdown(
                    f'<p class="fixedwidth">{message["content"]}</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<p class="lato-bold">{message["content"]}</p>',
                    unsafe_allow_html=True,
                )


def ask_llm(prompt: str):
    prompt_dict = {"role": "user", "content": prompt}
    st.session_state.message_log.append(prompt_dict)
    add_message_to_chat_history(prompt_dict)

    st.session_state.llm.reset_memory()
    response = st.session_state.llm.answer_question(prompt)
    response_dict = {"role": "assistant", "content": response["response"]}
    st.session_state.message_log.append(response_dict)
    add_message_to_chat_history(response_dict)


def draw_chat_ui():
    c1, c2 = st.columns([3, 1])

    with c1:
        st.session_state.chat_container = st.container(height=500)
        redraw_chat_history()

        prompt = st.chat_input(" > ")
        if prompt:
            ask_llm(prompt)

    with c2:
        draw_side_questions()


if not "first_run" in st.session_state:
    first_run()

draw_page()
