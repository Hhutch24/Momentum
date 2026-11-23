
import streamlit as st

# Configure the website
st.set_page_config(
    page_title="Momentum",
    page_icon="📅"
)

# Display the main heading
st.title("Momentum 📅")

st.write("Your personal planner and accountability assistant.")

# Create a temporary list of tasks
if "tasks" not in st.session_state:
    st.session_state.tasks = []

# Let the user enter a new task
st.subheader("What's on your mind?")

with st.form("task_form"):
    new_task = st.text_input("Add something to your list")
    add_button = st.form_submit_button("Add Task")

    if add_button and new_task.strip():
        st.session_state.tasks.append(new_task.strip())
        st.success("Task added!")

# Show all saved tasks for this session
st.subheader("Your Tasks")

if len(st.session_state.tasks) == 0:
    st.info("You haven't added any tasks yet.")

for index, task in enumerate(st.session_state.tasks):
    st.checkbox(task, key=f"task_{index}")
