import streamlit as st
import pandas as pd
import numpy as np
import math
from datetime import timedelta

# --- Configuration and Constants ---
QUESTION_FILE = "active_practice_tests.xlsx"
NUM_QUESTIONS_OPTIONS = [5, 20, 40] 

CERT_NAME_MAPPING = {
    "IBM_DS_A": "IBM Data Science Professional (Courses 1-5)",
    # "PBI": "PowerBI",
    # "MAZ_FDM": "Microsoft Azure Fundamentals",
    # "MAZ_DVA": "Microsoft Azure Developer Associate",
    # "GCP_ADP": "Google Cloud Associate Data Practitioner",
    # "GCP_PML": "Google Cloud Professional Machine Learning Engineer",
}

DIFFICULTY_DISTRIBUTIONS = {
    "Easy": {"easy": 0.70, "medium": 0.25, "hard": 0.05},
    "Medium": {"easy": 0.50, "medium": 0.30, "hard": 0.20},
    "Hard": {"easy": 0.30, "medium": 0.35, "hard": 0.35},
}

# --- Page Configuration ---
# 2. Changed layout to centered (narrow) by removing the layout="wide" argument.
st.set_page_config(
    page_title="Exam Practice"
)

# --- Data Loading and Caching ---
@st.cache_data
def load_data(file_path):
    try:
        xls = pd.ExcelFile(file_path)
        all_sheets = {}
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            
            if 'difficulty' in df.columns:
                df['difficulty'] = df['difficulty'].str.lower()
            
            if 'correct_option(s)' in df.columns:
                df.rename(columns={'correct_option(s)': 'correct_options'}, inplace=True)
                df['correct_options'] = df['correct_options'].astype(str).str.strip().str.upper()
                df['correct_options'] = df['correct_options'].str.replace('A', '1').str.replace('B', '2').str.replace('C', '3').str.replace('D', '4')
                df['is_multiple'] = df['correct_options'].str.contains(',', na=False)

            all_sheets[sheet_name] = df
        return all_sheets
    except FileNotFoundError:
        st.error(f"Error: The file '{file_path}' was not found. Please ensure it is in the same directory as the script.")
        return None

# --- Helper Functions ---
def select_questions(df, num_questions, difficulty_level):
    selected_questions_list = []
    
    multi_choice_df = df[df['is_multiple'] == True]
    if not multi_choice_df.empty:
        selected_multi = multi_choice_df.sample(n=1)
        selected_questions_list.append(selected_multi)
        df = df.drop(selected_multi.index)
        num_questions_to_select = num_questions - 1
    else:
        num_questions_to_select = num_questions

    distribution = DIFFICULTY_DISTRIBUTIONS[difficulty_level]
    
    for diff, proportion in distribution.items():
        num_to_select = math.ceil(num_questions_to_select * proportion)
        diff_df = df[df['difficulty'] == diff]
        
        num_available = len(diff_df)
        actual_to_select = min(num_to_select, num_available)
        
        if actual_to_select > 0:
            selected_questions_list.append(diff_df.sample(n=actual_to_select, replace=False))
            
    final_questions = pd.concat(selected_questions_list)
    
    if len(final_questions) < num_questions:
        remaining_needed = num_questions - len(final_questions)
        remaining_pool = df.drop(final_questions.index.intersection(df.index))
        
        if len(remaining_pool) >= remaining_needed:
            final_questions = pd.concat([final_questions, remaining_pool.sample(n=remaining_needed, replace=False)])
    
    return final_questions.sample(frac=1).reset_index(drop=True).head(num_questions)

def display_results():
    st.subheader("Test Complete!")
    
    correct_count = st.session_state.results.count("Correct")
    total_questions = len(st.session_state.questions)
    score = (correct_count / total_questions) * 100 if total_questions > 0 else 0
    
    if 'start_time' in st.session_state:
        total_duration = pd.Timestamp.now() - st.session_state.start_time
        minutes, seconds = divmod(int(total_duration.total_seconds()), 60)
        duration_str = f"{minutes}m {seconds}s"
    else:
        duration_str = "N/A"

    col1, col2 = st.columns(2)
    col1.metric("Your Score", f"{score:.2f}%", f"{correct_count} out of {total_questions} correct")
    col2.metric("Total Time Taken", duration_str)

    st.subheader("Review Your Answers")
    
    review_data = []
    for i, row in st.session_state.questions.iterrows():
        review_data.append({
            "Question": row['question'],
            "Your Answer": st.session_state.user_answers[i],
            "Correct Answer": ", ".join([row[f"option_{opt.strip()}"] for opt in row['correct_options'].split(',')]),
            "Result": st.session_state.results[i]
        })
        
    review_df = pd.DataFrame(review_data)
    st.dataframe(review_df, use_container_width=True)
    
    if st.button("Start New Test"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- Initialise Session State ---
if 'test_started' not in st.session_state:
    st.session_state.test_started = False
if 'questions' not in st.session_state:
    st.session_state.questions = pd.DataFrame()
if 'current_question_index' not in st.session_state:
    st.session_state.current_question_index = 0
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = []
if 'results' not in st.session_state:
    st.session_state.results = []
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None

# --- UI Rendering ---
st.title("Certification Exam Practice Tool")

question_data = load_data(QUESTION_FILE)

if not question_data:
    st.stop()

# --- SCREEN 1: Test Setup ---
if not st.session_state.test_started:
    st.header("Setup Your Practice Test")
    
    cert_keys = list(CERT_NAME_MAPPING.keys())
    
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_cert = st.selectbox(
            "1. Select Certification", 
            options=cert_keys,
            format_func=lambda key: f"{CERT_NAME_MAPPING.get(key, key)} ({key})"
        )
    with col2:
        num_questions = st.selectbox("2. Select Number of Questions", options=NUM_QUESTIONS_OPTIONS)
    with col3:
        difficulty = st.selectbox("3. Select Test Difficulty", options=["Easy", "Medium", "Hard"])
        
    if st.button("Start Test", type="primary"):
        if selected_cert in question_data:
            df = question_data[selected_cert]
            st.session_state.questions = select_questions(df, num_questions, difficulty)
            
            if len(st.session_state.questions) < num_questions:
                st.warning(f"Warning: Only found {len(st.session_state.questions)} questions. The test will proceed with this number.")
            
            st.session_state.test_started = True
            st.session_state.current_question_index = 0
            st.session_state.user_answers = [None] * len(st.session_state.questions)
            st.session_state.results = [None] * len(st.session_state.questions)
            st.session_state.answer_submitted = False
            st.session_state.start_time = pd.Timestamp.now()
            st.rerun()
        else:
            st.error(f"No questions found for the selected certification: {selected_cert}")

# --- SCREEN 2: Quiz in Progress ---
elif st.session_state.current_question_index < len(st.session_state.questions):
    
    total_q = len(st.session_state.questions)
    current_q_num = st.session_state.current_question_index + 1
    
    if st.session_state.start_time:
        elapsed_time = pd.Timestamp.now() - st.session_state.start_time
        minutes, seconds = divmod(int(elapsed_time.total_seconds()), 60)
        timer_str = f"Time Elapsed: {minutes}m {seconds}s"
        st.caption(timer_str)

    st.header(f"Question {current_q_num} of {total_q}")
    st.progress((current_q_num) / total_q)
    
    question_row = st.session_state.questions.iloc[st.session_state.current_question_index]
    
    options = [question_row[f'option_{i}'] for i in range(1, 5)]
    correct_options_list = sorted([opt.strip() for opt in question_row['correct_options'].split(',')])
    is_multiple_choice = question_row['is_multiple']

    # --- This block shows the question BEFORE submission ---
    if not st.session_state.answer_submitted:
        st.subheader(question_row['question'])
        user_selection = None
        if is_multiple_choice:
            st.info("This question may have multiple correct answers.")
            user_selection = st.multiselect("Select your answer(s):", options=options, key=f"q_{current_q_num}")
        else:
            user_selection = st.radio("Select your answer:", options=options, key=f"q_{current_q_num}")

        if st.button("Submit Answer"):
            selection_list = user_selection if isinstance(user_selection, list) else ([user_selection] if user_selection else [])
            selected_indices = sorted([str(options.index(opt) + 1) for opt in selection_list])
            
            st.session_state.user_answers[st.session_state.current_question_index] = ", ".join(selection_list) if selection_list else "No Answer"
            
            if selected_indices == correct_options_list:
                st.session_state.results[st.session_state.current_question_index] = "Correct"
            else:
                st.session_state.results[st.session_state.current_question_index] = "Incorrect"
                
            st.session_state.answer_submitted = True
            st.rerun()

    # --- This block shows the feedback AFTER submission ---
    if st.session_state.answer_submitted:
        # 1. UPDATED: Show the question, options, and your answer for full context.
        with st.container(border=True):
            st.markdown(f"**Question:** {question_row['question']}")
            st.markdown("**Options:**")
            for i, opt in enumerate(options):
                st.markdown(f"    {i+1}. {opt}")
            st.divider()
            
            user_answer_text = st.session_state.user_answers[st.session_state.current_question_index]
            st.markdown(f"**Your Answer:** {user_answer_text if user_answer_text != 'No Answer' else '_Not answered_'}")

        st.write("") # Add some vertical space

        result = st.session_state.results[st.session_state.current_question_index]
        
        if result == "Correct":
            st.success("Correct! Well done.")
        else:
            st.error("Incorrect.")
            correct_answer_text = [options[int(i)-1] for i in correct_options_list]
            st.info(f"**The correct answer(s) are:** {', '.join(correct_answer_text)}")
            
        if st.button("Next Question"):
            st.session_state.current_question_index += 1
            st.session_state.answer_submitted = False
            st.rerun()

# --- SCREEN 3: Test Results ---
else:
    display_results()