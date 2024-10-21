import streamlit as st
import yaml
from pathlib import Path
from Utilities import *
from LLM import *
from Job import *


def add_custom_css():
    with open("style.css", "r") as f:
        css = f"<style>{f.read()}</style>"
    st.markdown(css, unsafe_allow_html=True)


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


def format_job_description(job_description: str):
    create_llm_based_on_config(
        "llm_job_desc_formatter",
        st.session_state.current_llm_config,
        "format_job_description2",
    )
    create_llm_based_on_config(
        "llm_job_desc_checker",
        st.session_state.current_llm_config,
        "check_format_job_description",
    )

    formatted_job_description = st.session_state.llm_job_desc_formatter.generate(
        text_to_format=job_description
    )["response"]
    checked_job_description = st.session_state.llm_job_desc_checker.generate(
        text_to_format=job_description, formatted_job=formatted_job_description
    )["response"]

    res = {
        "unformatted": job_description,
        "formatted": formatted_job_description,
        "checked": checked_job_description,
    }

    return res


def run_job_desc_formatter():
    if st.session_state.use_llm_job_description_formatter:

        if "job_formatter_output" in st.session_state:
            text_to_format = st.session_state.job_formatter_output["unformatted"]
        else:
            text_to_format = st.session_state.job.job_description

        res = format_job_description(text_to_format)

        st.session_state.job_formatter_output = res
        st.session_state.job = Job(job_description=res["checked"])

        # As the job description changed we need to rerun job_recon
        run_job_recon(force_rerun=True)
    elif (
        not st.session_state.use_llm_job_description_formatter
        and "job_formatter_output" in st.session_state
    ):
        # Switching back to raw job description
        st.session_state.job = Job(
            job_description=st.session_state.job_formatter_output["unformatted"]
        )
        del st.session_state["job_formatter_output"]
        run_job_recon(force_rerun=True)


def safe_session_state_delete(key: str):
    if key in st.session_state:
        del st.session_state[key]


def run_job_recon(force_rerun: bool = False):
    if force_rerun:
        safe_session_state_delete("job_recon")

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
        safe_session_state_delete("job_recon")
