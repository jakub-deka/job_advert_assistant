from cProfile import label
import hashlib
from platform import system
import streamlit as st
from Job import *
from LLM import LLMwithKnowledge
from Utilities import PromptTemplater
import stutils
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


def init_config():
    with open("./default.yml", "r") as f:
        config = yaml.safe_load(f.read())

    for key, value in config.items():
        st.session_state[key] = value


def get_llm_config(config_name: str):
    config_name = Path(f"./llm_configurations/{config_name}.yml")
    with open(config_name, "r") as f:
        config = yaml.safe_load(f.read())
    return config


def create_llm_based_on_config(
    session_state_name: str,
    config_name: str,
    prompt_template_name: str,
    knowledge: dict[str, str] = {},
    return_json: bool = False,
    log_file_path: str | None = None,
    reset_knowledge: bool = False,
    system_prompt: str | None = None,
):
    config = get_llm_config(config_name)
    if st.session_state.log_llm_prompts_to_file:
        log_file_path = Path(f"./logs/{session_state_name}.log")
    else:
        log_file_path = None

    pt = PromptTemplater("./prompts")

    if session_state_name in st.session_state and not reset_knowledge:
        old_knowledge = st.session_state[session_state_name].knowledge
        old_messages = st.session_state[session_state_name].messages
    else:
        old_knowledge = {}
        old_messages = None

    if system_prompt is None:
        system_prompt = config["system_prompt"]

    res = LLMwithKnowledge(
        model_name=config["model_name"],
        url=config["url"],
        system_prompt=system_prompt,
        prompt_template=pt.get_prompt(prompt_template_name),
        knowledge=old_knowledge,
        return_json=return_json,
        log_file_path=log_file_path,
        messages=old_messages,
    )

    for k, v in knowledge.items():
        res.add_to_knowledge({k: v})

    st.session_state[session_state_name] = res


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

    # Initialise writing agent
    create_llm_based_on_config(
        "writing_agent",
        current_llm_config,
        "writing_help_write",
        system_prompt="You are an expert cover letter writer that using a job description and context provided will write engaging, interesting, and concise cover letters that will increase chances of a candidate to get a job.",
        knowledge=default_knowledge,
    )


def change_llm():
    # This will cause a rerun of the application
    init_llms()
    run_job_desc_formatter()
    run_job_recon(force_rerun=True)


def run_job_recon(force_rerun: bool = False):
    if force_rerun:
        del st.session_state["job_recon"]

    if st.session_state.job_recon_style in ["json", "verbose", "verbose_bulk"]:
        if (
            "job_recon" in st.session_state
            and st.session_state.job_recon["style"] == st.session_state.job_recon_style
        ):
            # Don't have to do anything as a job recon object is there already and it is the correct style.
            pass
        else:
            # Actually have to run job recon now

            if st.session_state.job_recon_style == "json":
                # Provision the job recon LLM object
                create_llm_based_on_config(
                    "llm_job_recon",
                    st.session_state.current_llm_config,
                    "job_recon_json",
                    return_json=True,
                    reset_knowledge=True,
                )
                llm_reply = st.session_state.llm_job_recon.generate(
                    job_description=st.session_state.job.job_description
                )
                job_recon_body = llm_reply["response"]
                st.session_state.job_recon = {
                    "style": "json",
                    "job_recon_body": job_recon_body,
                }
            elif st.session_state.job_recon_style == "verbose_bulk":
                create_llm_based_on_config(
                    "llm_job_recon",
                    st.session_state.current_llm_config,
                    "job_recon_bulk",
                )
                with open("./prompts/job_recon.yml", "r") as f:
                    job_recon_questions = yaml.safe_load(f.read())["questions"]
                llm_reply = st.session_state.llm_job_recon.generate(
                    job_description=st.session_state.job.job_description,
                    number_of_words=20,
                    questions=job_recon_questions,
                )
                job_recon_body = llm_reply["response"]
                st.session_state.job_recon = {
                    "style": "verbose_bulk",
                    "job_recon_body": job_recon_body,
                }
            else:
                # Provision the job recon LLM object
                create_llm_based_on_config(
                    "llm_job_recon", st.session_state.current_llm_config, "job_recon"
                )
                with open("./prompts/job_recon.yml", "r") as f:
                    job_recon_questions = yaml.safe_load(f.read())
                responses = []
                for q in job_recon_questions["questions"]:
                    llm_reply = st.session_state.llm_job_recon.generate(
                        number_of_words=20,
                        job_description=st.session_state.job.job_description,
                        question=q,
                    )
                    responses.append({"question": q, "answer": llm_reply["response"]})
                st.session_state.job_recon = {
                    "style": "verbose",
                    "job_recon_body": responses,
                }

    else:
        # As job_recon is off we need to delete the job recon object in the session state
        del st.session_state["job_recon"]


def run_job_desc_formatter():
    if st.session_state.use_llm_job_description_formatter:
        if "unformatted_job" in st.session_state:
            # This should NEVER happen
            raise Exception("Unfromatted job present in session state")
            st.session_state.job = copy.deepcopy(st.session_state.unformatted_job)
            del st.session_state["unformatted_job"]

        create_llm_based_on_config(
            "llm_job_desc_formatter",
            st.session_state.current_llm_config,
            "format_job_description",
        )
        formatted_job_desc = st.session_state.llm_job_desc_formatter.generate(
            text_to_format=st.session_state.job.job_description
        )
        st.session_state.unformatted_job = copy.deepcopy(st.session_state.job)
        st.session_state.job = Job(job_description=formatted_job_desc["response"])

        # As the job description changed we need to rerun job_recon
        run_job_recon(force_rerun=True)
    elif (
        not st.session_state.use_llm_job_description_formatter
        and "unformatted_job" in st.session_state
    ):
        # Switching back to raw job description
        st.session_state.job = copy.deepcopy(st.session_state.unformatted_job)
        del st.session_state["unformatted_job"]
        run_job_recon(force_rerun=True)


# region Render
def render_config():
    st.markdown("### Configuration options")
    st.markdown(" ")

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

    st.toggle(
        label="Reset LLM chat history between questions?",
        key="reset_llm_memory_between_questions",
    )


def render_job_recon():
    if "job_recon" in st.session_state:
        st.divider()
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
    st.session_state.llm_knowledge_display = st.expander(
        label="LLM knowledge", icon="🧠"
    )
    with st.session_state.llm_knowledge_display:
        st.write("")
        for key, value in st.session_state.llm_chat.knowledge.items():
            st.write({key: value[:40]})


def add_message_to_chat_history(message: dict[str, str]):
    with st.session_state.chat_container:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_sidebar():
    with st.sidebar:
        render_job_recon()
        render_llm_knowledge()
        render_config()


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

    with st.form(key="writing_help"):
        st.text_area(label="Writing prompt", key="writing_prompt")
        st.form_submit_button(
            on_click=process_writing_prompt,
        )

    st.session_state.writing_help_output = st.container()


def process_writing_prompt():
    writing_prompt = st.session_state.writing_prompt
    reply = st.session_state.writing_agent.answer_question(question=writing_prompt)
    with st.session_state.writing_help_output:
        st.markdown("# Writing prompt")
        st.write(writing_prompt)
        st.markdown("# LLM reply")
        st.write(reply["response"])


def render_chat_ui():

    col1, col2, col3 = st.columns([1, 3, 2])

    with col1:
        render_faq()

    with col2:
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

st.set_page_config(layout="wide", initial_sidebar_state="expanded")
stutils.add_custom_css()
if "first_chat_run" not in st.session_state:
    st.session_state.first_chat_run = False
    init_config()
    fake_home_entry()
    init_llms()

    # Execute set pieces if needed
    run_job_desc_formatter()
    run_job_recon()


render_sidebar()
render_chat_ui()
st.write("This is a change4")
# endregion
