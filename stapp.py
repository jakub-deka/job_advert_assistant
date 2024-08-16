# TODO add readme and bookmarklet
# TODO add ability to provide job description as text
# TODO make a favicon
# TODO Fix the issue with adding information to context. The form needs to clear after it is submitted.
from math import exp
from re import L
from click import prompt
import streamlit as st
import yaml
from Job import *
from LLM import *
from Utilities import *
import base64


# region Utilities
def get_page_content(content_name: str):
    with open(f"./content/{content_name}.md", "r") as f:
        return f.read()


def load_config(path: str):
    with open(path, "r") as f:
        res = yaml.safe_load(f.read())
    return res


def set_bg_hack(main_bg):
    """
    A function to unpack an image from root folder and set as bg.

    Returns
    -------
    The background.
    """
    # set bg name
    main_bg_ext = "png"

    st.markdown(
        f"""
         <style>
         .stApp {{
             background: url(data:image/{main_bg_ext};base64,{base64.b64encode(open(main_bg, "rb").read()).decode()});
             background-repeat: no-repeat;
             background-attachment: fixed;
             background-position: bottom right; 
         }}
         </style>
         """,
        unsafe_allow_html=True,
    )


# endregion
def check_for_job_url_in_query():
    if "job_url" in st.query_params:
        st.session_state.job_url = st.query_params.job_url
        initialise_job()
        st.session_state.job_url_input_expanded = False


def first_run():
    st.set_page_config(layout="wide", initial_sidebar_state="expanded")
    st.session_state.first_run = False
    st.session_state.use_llm_job_formatter = True
    st.session_state.job_url_input_expanded = True

    st.session_state.pt = PromptTemplater("./prompts")

    # Load the config
    st.session_state.config = load_config("./llm_configurations/llama3.1-8b-free.yml")
    initialise_llm("llm", "rag")
    if st.session_state.use_llm_job_formatter:
        initialise_llm("job_desc_formatter", "format_job_description")

    # Initialise the key objects and session variables
    check_for_job_url_in_query()

    st.session_state.message_log = []


def initialise_llm(llm_name: str, prompt_template_name: str):
    if llm_name in st.session_state:
        old_knowledge = st.session_state[llm_name].knowledge
    else:
        old_knowledge = {}

    st.session_state[llm_name] = LLMwithKnowledge(
        model_name=st.session_state.config["model_name"],
        url=st.session_state.config["url"],
        system_prompt=st.session_state.config["system_prompt"],
        prompt_template=st.session_state.pt.get_prompt(prompt_template_name),
        knowledge=old_knowledge,
    )


def initialise_job():
    st.session_state.job = Job(st.session_state.job_url)
    if st.session_state.job.success:
        if st.session_state.use_llm_job_formatter:
            st.session_state.unformatted_job_description = (
                st.session_state.job.job_description
            )
            llm_reply = st.session_state["job_desc_formatter"].generate(
                text_to_format=st.session_state.unformatted_job_description
            )
            st.session_state.job.job_description = llm_reply["response"]
        st.session_state.llm.add_to_knowledge(
            {"job description": st.session_state.job.job_description}
        )


def draw_config_buttons():
    config_path = Path("./llm_configurations")
    configs = [str(c) for c in config_path.glob("*.yml")]
    with st.expander(label="Chose LLM configuration", icon="⚙️"):
        for c in configs:
            if st.button(c):
                st.session_state.config = load_config(c)
                initialise_llm("llm", "rag")
                if st.session_state.use_llm_job_formatter:
                    initialise_llm("job_desc_formatter", "format_job_description")


def draw_page():
    with open("style.css", "r") as f:
        css = f"<style>{f.read()}</style>"

    st.markdown(css, unsafe_allow_html=True)

    with st.sidebar:
        st.image("logo3.png", use_column_width="never")

        st.checkbox(
            label="Format job description using LLM",
            key="use_llm_job_formatter",
        )
        if st.session_state.use_llm_job_formatter:
            initialise_llm("job_desc_formatter", "format_job_description")

        draw_config_buttons()
        with st.expander(label="Current LLM config", icon="🛠️"):
            st.markdown("# Current config")
            st.write(st.session_state.config)

        st.session_state.llm_knowledge_display = st.expander(
            label="LLM knowledge", icon="🧠"
        )

        with st.session_state.llm_knowledge_display:
            st.write("")
            for key, value in st.session_state.llm.knowledge.items():
                st.write({key: value[:40]})

    # set_bg_hack("logo.png")
    st.markdown(get_page_content("home_introduction"))

    c1, c2, c3 = st.columns(3)

    with c1:
        with st.popover(label="Instructions", use_container_width=True):
            st.markdown(get_page_content("home_instructions"))

    # with st.expander(label="Job URL input", expanded=st.session_state.job_url_input_expanded):
    with c2:
        with st.popover(label="Job URL input", use_container_width=True):
            with st.form("joburl", border=False):
                job_url = (
                    st.session_state.job_url if "job_url" in st.session_state else ""
                )
                st.text_input(label="Job URL", key="job_url", value=job_url)
                st.form_submit_button(on_click=initialise_job)

    with c3:
        with st.popover(label="Add information to context", use_container_width=True):
            with st.form("addcontext", border=False, clear_on_submit=True):
                additional_info_label = st.text_input("Label")
                additional_info = st.text_area(
                    label="Information to add to LLM context", height=200
                )
                submit = st.form_submit_button()
                if submit:
                    add_to_llm_context({additional_info_label: additional_info})
                    with st.session_state.llm_knowledge_display:
                        st.write({additional_info_label: additional_info[:40]})

    if "job" in st.session_state and st.session_state.job.success:
        draw_chat_ui()
    elif "job" in st.session_state and not st.session_state.job.success:
        st.write("Error occured when retrieving the job details.")
        st.write(st.session_state.job.job_description)
    else:
        st.write("Provide job url and hit submit to begin.")


def add_to_llm_context(info: dict[str:str]):
    st.session_state.llm.add_to_knowledge(info)


def draw_side_questions():
    st.markdown("### Quick questions")

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

    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        if st.button(label="Reset LLM context"):
            st.session_state.llm.reset_knowledge()
            st.rerun()
    with c2:
        if st.button(label="Reset chat history"):
            st.session_state.message_log = []
            redraw_chat_history()
    with c3:
        st.empty()

    c2, c3 = st.columns([5, 2])

    with c2:
        st.session_state.chat_container = st.container(height=600)
        redraw_chat_history()

        prompt = st.chat_input(" > ")
        if prompt:
            ask_llm(prompt)

    with c3:
        draw_side_questions()

    st.columns(1)
    with st.expander(label="Job description", icon="💼"):
        st.markdown(st.session_state.job.job_description)


if not "first_run" in st.session_state:
    first_run()

draw_page()
