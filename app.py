import os
import re
import streamlit as st
from streamlit_option_menu import option_menu

# --- BULLETPROOF PATCH FOR CREWAI GROQ CACHE BUG ---
try:
    import litellm
    old_completion = litellm.completion
    def patched_completion(*args, **kwargs):
        if "messages" in kwargs:
            for msg in kwargs["messages"]:
                if isinstance(msg, dict):
                    msg.pop("cache_breakpoint", None)
        return old_completion(*args, **kwargs)
    litellm.completion = patched_completion
except Exception:
    pass
# ----------------------------------------------------
import base64

def play_browser_audio(file_path):
    """Plays an MP3 file directly in the user's browser using HTML5 audio."""
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        audio_html = f"""
            <audio autoplay="true">
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    except Exception:
        # Fails silently if the mp3 file is missing from the repo
        pass

from crewai import Agent, Task, Crew, Process, LLM

# Page Configuration
st.set_page_config(
    page_title="AI Interactive Quiz Generator",
    page_icon="🎮",
    layout="wide"
)

# Horizontal Navigation Bar
selected = option_menu(
    menu_title=None,
    options=["create", "play"],
    icons=["building-add", "controller"],
    orientation="horizontal",
    default_index=0,
)

# Direct API Key Configuration
groq_api_key = "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"
os.environ["GROQ_API_KEY"] = groq_api_key

# Model definition
groq_llm = LLM(
    model="groq/openai/gpt-oss-120b",
    api_key=groq_api_key
)

# Parser function
def parse_quiz_questions(raw_text):
    questions_list = []
    
    raw_text = re.sub(r'```json', '', raw_text, flags=re.IGNORECASE)
    raw_text = re.sub(r'```', '', raw_text)

    blocks = re.split(r'(?:###\s*)?(?:Question\s*)?\b\d+[\.\)]\s*', raw_text)
    
    for block in blocks:
        if not block.strip() or len(block.strip()) < 10:
            continue
        
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        q_text_lines = []
        options = {}
        correct_answer = None
        
        for line in lines:
            opt_match = re.match(r'^([A-Da-d])[\)\.\:]\s*(.*)', line)
            ans_match = re.search(r'(?:correct\s*answer|answer)[:\s]*([A-Da-d])', line, re.IGNORECASE)
            
            if ans_match:
                correct_answer = ans_match.group(1).upper()
            elif opt_match:
                opt_letter = opt_match.group(1).upper()
                options[opt_letter] = opt_match.group(2)
            else:
                if not options:
                    q_text_lines.append(line)
        
        q_text = " ".join(q_text_lines).strip()
        q_text = re.sub(r'^(?:Question\s*\d+[:\-]?\s*)', '', q_text, flags=re.IGNORECASE).strip()
        
        if q_text and len(options) >= 2:
            if not correct_answer:
                correct_answer = "A"
            
            questions_list.append({
                "question": q_text,
                "options": options,
                "answer": correct_answer
            })
            
    return questions_list[:10]

# ---------------- CREATE TAB ----------------
if selected == "create":
    st.title("🏗️ Create Quiz")
    st.write("Generate a batch of 10 interactive quiz questions instantly using Groq!")

    ques_type = st.text_input("Enter question type (e.g., Science Trivia, History):", value="Science Trivia")
    std_level = st.text_input("Which class/standard?", value="High School")

    if st.button("🚀 Generate 10-Question Quiz", use_container_width=True):
        if not ques_type or not std_level:
            st.warning("Please fill in both fields!")
        else:
            with st.spinner("Groq is building your 10 interactive questions..."):
                try:
                    quiz_agent = Agent(
                        role=f"Expert Quiz Master for Class {std_level}",
                        goal=f"Create a list of exactly 10 engaging quiz questions about {ques_type} with 4 options each (A, B, C, D) and clear answer keys.",
                        backstory="An expert educator who designs structured exam questions.",
                        allow_delegation=False,
                        verbose=True,
                        llm=groq_llm
                    )

                    task_create_question = Task(
                        description=(
                            f"Generate exactly 10 distinct quiz questions about {ques_type} tailored for {std_level} students. "
                            "Follow this exact format for each question:\n\n"
                            "1. What is the question text here?\n"
                            "A) First option\n"
                            "B) Second option\n"
                            "C) Third option\n"
                            "D) Fourth option\n"
                            "Correct Answer: A\n\n"
                            "Output all 10 questions numbered 1 through 10."
                        ),
                        expected_output="A list of 10 numbered quiz questions with options and answer keys.",
                        agent=quiz_agent
                    )

                    quiz_crew = Crew(
                        agents=[quiz_agent],
                        tasks=[task_create_question],
                        process=Process.sequential
                    )

                    result = quiz_crew.kickoff()
                    parsed_qs = parse_quiz_questions(str(result))
                    
                    if len(parsed_qs) > 0:
                        if "quiz_batches" not in st.session_state:
                            st.session_state["quiz_batches"] = []
                        st.session_state["quiz_batches"].append(parsed_qs)
                        st.balloons()
                        st.success(f"Successfully generated {len(parsed_qs)} questions! Switch to 'Play' tab to test.")
                    else:
                        st.error("Could not parse questions. Try clicking generate again.")

                except Exception as e:
                    st.error(f"Error: {e}")

    if "quiz_batches" in st.session_state and st.session_state["quiz_batches"]:
        st.markdown("---")
        st.subheader("📋 Generated Quiz Summary")
        st.info(f"Total batches generated: {len(st.session_state['quiz_batches'])}. Switch to the **Play** tab to start playing!")

# ---------------- PLAY TAB ----------------
elif selected == "play":
    st.title("🎮 Play Quiz")
    
    if "quiz_batches" not in st.session_state or not st.session_state["quiz_batches"]:
        st.warning("No quiz questions generated yet! Go to the **Create** tab and generate some questions first.")
    else:
        with st.sidebar:
            batch_idx = st.selectbox(
                "Select Quiz Batch:", 
                options=range(len(st.session_state["quiz_batches"])),
                format_func=lambda x: f"Batch {x + 1}"
            )

        current_batch = st.session_state["quiz_batches"][batch_idx]
        
        st.write("Test your knowledge!")
        st.markdown("---")

        for i, q_data in enumerate(current_batch):
            st.markdown(f"### Question {i + 1}")
            st.markdown(q_data["question"])
            
            opt_keys = sorted(q_data["options"].keys())
            opt_labels = [f"{k}) {q_data['options'][k]}" for k in opt_keys]
            
            user_choice_label = st.radio(
                f"Select your answer for Q{i+1}:",
                options=opt_labels,
                key=f"batch_{batch_idx}_q_{i}",
                index=None
            )
            
            chosen_letter = user_choice_label.split(")")[0].strip() if user_choice_label else None
            
            if st.button(f"Submit Answer for Q{i+1}", key=f"sub_{batch_idx}_{i}"):
                if not chosen_letter:
                    st.warning("Please select an option first!")
                elif chosen_letter == q_data["answer"]:
                    st.success(f"🎉 Correct! Option {chosen_letter} is right.")
                    st.balloons()
                    play_browser_audio("ttsmaker-file-2026-10-15-8-50-2.mp3")
                else:
                    st.error(f"❌ Incorrect. The correct answer was option {q_data['answer']}.")
                    play_browser_audio("ttsmaker-file-2026-10-15-9-2-15.mp3")
            
            st.markdown("---")
