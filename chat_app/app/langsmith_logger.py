from langsmith import traceable

@traceable(name="chat-session")
def log_with_langsmith(steps):
    for step in steps:
        print("LangSmith log:", step)
from langsmith import traceable

