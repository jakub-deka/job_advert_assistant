# TODO add readme and bookmarklet
# TODO make a favicon
# TODO common tasks like writing a cover letter or motivation
# TODO fix issue where the dictionaries are not merged in llm knowledge
# TODO fix issue where profile seems to be added more than once to the knowledge
# TODO fix job recon running when profile is added without a job
# TODO split this into 2 pages - one for inputs and one to interacti with the chatbot
from math import exp
from re import L
from click import prompt
import streamlit as st
import yaml
from Job import *
from LLM import *
import LinkedInProfile
from Utilities import *
import base64
import json
import pandas as pd
import random
from LinkedInProfile import *

LOGGING_TO_FILES_ENABLED = False

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


def verify_job_recon(j: dict[str, str]):
    initialise_llm(
        "job_recon_verifier",
        "verify_job_recon_item",
        log_file_path="./logs/job_recon_verifier.log",
    )
    res = []
    llm = st.session_state["job_recon_verifier"]
    for key, value in j.items():
        response = llm.generate(
            job_description=st.session_state.job.job_description,
            key=key,
            value=value,
        )
        res.append({"key": key, "value": value, "response": response["response"]})

    return res


def run_job_recon_json():
    initialise_llm(
        "job_recon",
        "job_recon_json",
        return_json=True,
        log_file_path="./logs/job_recon_json.log",
    )
    llm_reply = st.session_state["job_recon"].generate(
        job_description=st.session_state.job.job_description
    )

    st.session_state.job_recon_json = json.loads(llm_reply["response"])


def run_job_recon():
    with open("./prompts/job_recon.yml", "r") as f:
        job_recon_questions = yaml.safe_load(f.read())
    initialise_llm(
        "job_recon", "job_recon", log_file_path="./logs/job_recon_verbose.log"
    )
    responses = []
    for q in job_recon_questions["questions"]:
        llm_reply = st.session_state["job_recon"].generate(
            number_of_words=20,
            job_description=st.session_state.job.job_description,
            question=q,
        )
        responses.append({"question": q, "answer": llm_reply["response"]})

    st.session_state.job_recon_verbose = responses


def initialise_llm(
    llm_name: str,
    prompt_template_name: str,
    return_json: bool = False,
    log_file_path: str | None = None,
):
    if llm_name in st.session_state:
        old_knowledge = st.session_state[llm_name].knowledge
    else:
        old_knowledge = {}

    if not st.session_state.log_llm_to_file:
        log_file_path = None
    elif not LOGGING_TO_FILES_ENABLED:
        log_file_path = None

    st.session_state[llm_name] = LLMwithKnowledge(
        model_name=st.session_state.config["model_name"],
        url=st.session_state.config["url"],
        system_prompt=st.session_state.config["system_prompt"],
        prompt_template=st.session_state.pt.get_prompt(prompt_template_name),
        knowledge=old_knowledge,
        return_json=return_json,
        log_file_path=log_file_path,
    )


def initialise_job_if_present():
    if "job_url" in st.session_state or "input_job_description" in st.session_state:
        if (
            st.session_state.job_url is not None
            or st.session_state.input_job_description is not None
        ):
            initialise_job()
    else:
        pass


def initialise_job():
    st.session_state.job = Job(
        st.session_state.job_url, st.session_state.input_job_description
    )
    if st.session_state.job.success:
        if (
            st.session_state.use_llm_job_formatter
            and st.session_state.job_url is not None
        ):
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
        
        # Clear the chat history
        st.session_state.message_log = []
        redraw_chat_history()
    else:
        raise Exception("Something went wrong when creating a job object")

    if st.session_state.perform_job_recon:
        if st.session_state.job_recon_type == "JSON":
            run_job_recon_json()
        else:
            run_job_recon()


def add_to_llm_context(info: dict[str:str]):
    st.session_state.llm.add_to_knowledge(info)
    with st.session_state.llm_knowledge_display:
        st.write(info)


def add_message_to_chat_history(message: dict[str, str]):
    with st.session_state.chat_container:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def ask_llm(prompt: str):
    prompt_dict = {"role": "user", "content": prompt}
    st.session_state.message_log.append(prompt_dict)
    add_message_to_chat_history(prompt_dict)

    st.session_state.llm.reset_memory()
    response = st.session_state.llm.answer_question(prompt)
    response_dict = {"role": "assistant", "content": response["response"]}
    st.session_state.message_log.append(response_dict)
    add_message_to_chat_history(response_dict)


def check_for_job_url_in_query():
    if "job_url" in st.query_params:
        st.session_state.job_url = st.query_params.job_url
        initialise_job()


# endregion




def first_run():
    st.set_page_config(layout="wide", initial_sidebar_state="expanded")
    st.session_state.first_run = False
    st.session_state.use_llm_job_formatter = False
    st.session_state.job_url = None
    st.session_state.input_job_description = None
    st.session_state.perform_job_recon = True
    st.session_state.job_recon_type = "Verbose"
    st.session_state.log_llm_to_file = True
    st.session_state.llm_knowledge_display = st.empty()
    
    logos = list(Path("./logo").glob("*"))
    st.session_state.logo_path = str(random.choice(logos))

    st.session_state.pt = PromptTemplater("./prompts")

    # Load the config
    st.session_state.config = load_config("./llm_configurations/llama3.1-8b-free.yml")
    initialise_llm("llm", "rag", log_file_path="./logs/main_llm.log")
    if st.session_state.use_llm_job_formatter:
        initialise_llm(
            "job_desc_formatter",
            "format_job_description",
            log_file_path="./logs/job_desc_formatter.log",
        )

    # Initialise the key objects and session variables
    check_for_job_url_in_query()

    st.session_state.message_log = []



def draw_config_buttons():
    config_path = Path("./llm_configurations")
    configs = [str(c) for c in config_path.glob("*.yml")]
    with st.expander(label="Chose LLM configuration", icon="⚙️"):
        for c in configs:
            if st.button(c):
                st.session_state.config = load_config(c)
                initialise_llm("llm", "rag", log_file_path="./logs/main_llm.log")
                if st.session_state.use_llm_job_formatter:
                    initialise_llm(
                        "job_desc_formatter",
                        "format_job_description",
                        log_file_path="./logs/job_desc_formatter.log",
                    )


def draw_page():
    with open("style.css", "r") as f:
        css = f"<style>{f.read()}</style>"

    st.markdown(css, unsafe_allow_html=True)

    with st.sidebar:
        st.image(st.session_state.logo_path)

        st.checkbox(
            label="Format job description using LLM",
            key="use_llm_job_formatter",
        )
        if st.session_state.use_llm_job_formatter:
            initialise_llm("job_desc_formatter", "format_job_description")

        st.checkbox(label="Perform job description recon", key="perform_job_recon")

        st.radio(
            label="Job recon type (full refresh required)",
            options=["JSON", "Verbose"],
            key="job_recon_type",
            horizontal=True,
            # on_change=initialise_job_if_present(),
        )

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

        if "job_recon_json" in st.session_state and st.session_state.perform_job_recon:
            st.markdown("## Job recon")
            st.markdown(
                "This information is extracted from the job description, however in some rare cases it may not match fully the provided job description and should be verified."
            )
            df = (
                pd.DataFrame(st.session_state.job_recon_json, index=[0])
                .T.rename(columns={0: "extracted output"})
                .reset_index()
                .assign(index=lambda x: x["index"].str.replace("_", " "))
                .set_index("index")
            )
            st.table(df)

        if (
            "job_recon_verbose" in st.session_state
            and st.session_state.perform_job_recon
        ):
            for r in st.session_state.job_recon_verbose:
                st.markdown(f":orange[{r["question"]}] :blue[{r["answer"]}]")

    st.markdown(get_page_content("home_introduction"))

    c1, c2, c2b, c2c, c3 = st.columns(5)

    with c1:
        with st.popover(label="Instructions", use_container_width=True):
            st.markdown(get_page_content("home_instructions"))

    with c2:
        with st.popover(label="Job URL input", use_container_width=True):
            with st.form("joburl", border=False):
                job_url = (
                    st.session_state.job_url if "job_url" in st.session_state else ""
                )
                st.text_input(label="Job URL", key="job_url", value=job_url)
                st.form_submit_button(on_click=initialise_job)

    with c2b:
        with st.popover(label="Add job description", use_container_width=True):
            with st.form("jobdescription", border=False):
                st.text_area(label="Job description", key="input_job_description")
                st.form_submit_button(on_click=initialise_job)
                
    with c2c:
        with st.popover(label="Upload your LinkedIn profile", use_container_width=True):
            st.markdown("Simply head over to LinkedIn and download your profile as pdf.")
            st.image("./assets/down_as_pdf.png")
            uploaded_file = st.file_uploader("LinkedIn profile pdf", type=["pdf"])
            if uploaded_file is not None:
                my_profile = LinkedInProfile(uploaded_file.getvalue()).profile
                add_to_llm_context(my_profile)
                

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
                    # with st.session_state.llm_knowledge_display:
                        # st.write({additional_info_label: additional_info[:40]})

    if "job description" in st.session_state.llm.knowledge:
        draw_chat_ui()
    # if "job" in st.session_state and st.session_state.job.success: draw_chat_ui()
    elif "job" in st.session_state and not st.session_state.job.success:
        st.write("Error occured when retrieving the job details.")
        st.write(st.session_state.job.job_description)
    else:
        st.write("Provide job url and hit submit to begin.")




def draw_side_questions():

    def draw_question(question: str):
        if st.button(label=question, use_container_width=True):
            ask_llm(question)

    st.markdown("### Quick questions")

    qs = [
        "Considering my profile and skills, am I a good fit for this role? Be brief.",
        "What is the company name and the role title?",
        "What country and city is this role based in?",
        "What is the salary for this role?",
        "Is this role office based, remote or hybrid?",
        "Summarise key responsibilities in a short list.",
        "Summarise requirements specified for this role.",
    ]

    for q in qs:
        draw_question(q)


def redraw_chat_history():
    if "chat_container" in st.session_state:
        with st.session_state.chat_container:
            for m in st.session_state.message_log:
                add_message_to_chat_history(m)


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

    if "unformatted_job_description" in st.session_state:
        with st.expander(label="UNFORMATTED job description"):
            st.write(st.session_state.unformatted_job_description)

    with st.expander(label="Raw message history"):
        for m in st.session_state.llm.messages:
            if m.role == ChatRole.SYSTEM:
                col = "red"
            elif m.role == ChatRole.ASSISTANT:
                col = "blue"
            else:
                col = "orange"
            st.markdown(f":{col}-background[{m.role}]")
            for l in m.content.split("\n"):
                st.write(f""":{col}[{l}]""")


if not "first_run" in st.session_state:
    first_run()

draw_page()
