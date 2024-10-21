from cProfile import label
import hashlib
from platform import system
import streamlit as st
from Job import *
from LLM import LLMwithKnowledge
from Utilities import PromptTemplater
from stutils import *
from pathlib import Path
import yaml
import json
import pandas as pd
import copy


def fake_home_entry():
    from Job import Job
    from Utilities import ContentProvider
    from LinkedInProfile import LinkedInProfile

    st.session_state.first_run = False

    with open("./testing/example_job.txt", "r") as f:
        example_job = f.read()
    st.session_state.job = Job(job_description=example_job)
    st.session_state.content = ContentProvider("./content")
    st.session_state.profile = LinkedInProfile("./testing/Profile-2.pdf")


def init_llms(keep_chat_history: bool = False):
    current_llm_config = st.session_state.current_llm_config

    # Initialise llm chat agent
    default_knowledge = {
        **st.session_state.profile.profile,
        **{"job_description": st.session_state.job.job_description},
    }
    create_llm_based_on_config(
        "llm_chat", current_llm_config, "rag", knowledge=default_knowledge
    )

    if not keep_chat_history or "chat" not in st.session_state:
        st.session_state.chat = []

    # Initialise writing agent and helper agents
    create_llm_based_on_config(
        "writing_agent",
        current_llm_config,
        "writing_help_write",
        system_prompt="You are an expert cover letter writer that using a job description and context provided will write engaging, interesting, and concise cover letters that will increase chances of a candidate to get a job.",
        knowledge=default_knowledge,
    )

    create_llm_based_on_config(
        "accuracy_agent",
        current_llm_config,
        "writing_check_for_completness",
        system_prompt="You are an accuracy expert that never misses anythiong. Follow instructions provided to the letter.",
        knowledge=default_knowledge,
    )

    create_llm_based_on_config(
        "llm_check_agent",
        current_llm_config,
        "writing_check_for_llm",
        system_prompt="You are very good at detecting the difference between text written by a person and text written by LLM. Follow instructions provided to the letter.",
    )


def change_llm():
    # This will cause a rerun of the application
    init_llms()
    run_job_desc_formatter()
    run_job_recon(force_rerun=True)


# region Render
def render_config():
    st.markdown("### Configuration options")
    st.markdown(
        "If the output of the LLM is not to your satisfaction, please try different model that is already configured."
    )

    with st.container(border=True):
        llm_configs_path = Path("./llm_configurations")
        configs = [str(c.stem) for c in llm_configs_path.glob("*")]
        st.radio(
            label="LLM config",
            options=configs,
            on_change=change_llm,
            key="current_llm_config",
        )
        st.markdown(" ")
        st.toggle(
            label="Keep chat history when switching LLMs",
            key="keep_chat_history_when_changing_llms",
        )

    with st.container(border=True):
        st.toggle(
            label="Format job description using LLM",
            key="use_llm_job_description_formatter",
            on_change=run_job_desc_formatter,
        )
        st.markdown(
            "_Caution: it is not possible to guarantee that the LLM will not remove or modify some parts of the job description._"
        )
        st.markdown(" ")

    with st.container(border=True):
        options = ["off", "verbose", "verbose_bulk", "json"]
        st.radio(
            label="Job recon",
            options=options,
            on_change=run_job_recon,
            key="job_recon_style",
            horizontal=True,
        )

    st.markdown(
        "To ensure that context windows are kept to minimum please reset chat history before each prompt. This is the default behaviour."
    )
    st.toggle(
        label="Reset LLM chat history between questions?",
        key="reset_llm_memory_between_questions",
    )


def render_job_recon():
    if "job_recon" in st.session_state:
        st.markdown("### Job recon")
        if st.session_state.job_recon["style"] == "json":
            df = json.loads(st.session_state.job_recon["job_recon_body"])
            df = (
                pd.DataFrame(df, index=[0])
                .T.rename(columns={0: "extracted output"})
                .reset_index()
                .assign(index=lambda x: x["index"].str.replace("_", " "))
                .set_index("index")
            )
            st.table(df)
        elif st.session_state.job_recon["style"] == "verbose_bulk":
            st.markdown(st.session_state.job_recon["job_recon_body"])
        else:
            for r in st.session_state.job_recon["job_recon_body"]:
                st.markdown(f':orange[{r["question"]}] :blue[{r["answer"]}]')
        st.divider()


def render_llm_knowledge():
    st.markdown(
        "This information will be passed as part of the CONTEXT to the LLM together with your query/question."
    )
    st.session_state.llm_knowledge_display = st.expander(
        label="LLM knowledge", icon="🧠"
    )
    with st.session_state.llm_knowledge_display:
        st.write("")
        for key, value in st.session_state.llm_chat.knowledge.items():
            st.write({key: value})


def add_message_to_chat_history(message: dict[str, str]):
    with st.session_state.chat_container:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_sidebar():
    with st.sidebar:
        render_llm_knowledge()
        # render_config()


def render_faq():
    st.markdown("### FAQ")
    st.markdown(
        "Use buttons below to quickly ask questions about the job description provided."
    )
    for q in st.session_state.faqs:
        if st.button(q, use_container_width=True):
            ask_llm(q)


def render_writing_help():
    st.markdown("### Writing help")
    st.markdown(
        "Use these prompts or your own to ask LLM to help you write a cover letter etc."
    )

    for wp in st.session_state.writing_prompts:
        if st.button(wp):
            st.session_state.writing_prompt = wp

    with st.form(key="writing_help"):
        st.text_area(label="Writing prompt", key="writing_prompt")
        # st.toggle(label="Check accuracy", key="writing_check_accuracy")
        # st.toggle(label="Check for LLM traits", key="writing_check_llm")
        st.form_submit_button(
            on_click=process_writing_prompt,
        )

    st.session_state.writing_help_output = st.container()


def process_writing_prompt():
    response = st.session_state.writing_agent.answer_question(
        question=st.session_state.writing_prompt
    )["response"]

    with st.session_state.writing_help_output:
        # Write out the outp
        # ut
        st.markdown(response)


def render_chat_ui():

    col0, col1, col2, col3 = st.columns([1, 1, 3, 2])

    with col0:
        render_job_recon()

    with col1:
        render_faq()

    with col2:
        st.markdown("## Chat with the job description")
        st.session_state.chat_ui = st.container(height=800, border=False)
        with st.session_state.chat_ui:
            st.container(height=20, border=False)
            st.session_state.chat_display = st.container(height=700, border=False)
            for m in st.session_state.chat:
                render_message(m)
            prompt = st.chat_input(" > ")
            if prompt:
                ask_llm(prompt)

    with col3:
        render_writing_help()


def render_message(message):
    with st.session_state.chat_display:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def ask_llm(prompt: str):
    new_message = {"role": "user", "content": prompt}
    st.session_state.chat.append(new_message)
    render_message(new_message)
    if st.session_state.reset_llm_memory_between_questions:
        st.session_state.llm_chat.reset_memory()
    response = st.session_state.llm_chat.answer_question(prompt)
    response_dict = {"role": "assistant", "content": response["response"]}
    st.session_state.chat.append(response_dict)
    render_message(response_dict)


def render_messages():
    for m in st.session_state.chat:
        render_message(m)


# endregion


# region Main body

st.set_page_config(layout="wide", initial_sidebar_state="collapsed")
add_custom_css()
if "first_chat_run" not in st.session_state:
    st.session_state.first_chat_run = False
    init_config()
    # fake_home_entry()
    init_llms()

    # Execute set pieces if needed
    run_job_desc_formatter()
    run_job_recon()


render_sidebar()
render_chat_ui()
# endregion
