import sys
import os
sys.path.append(os.path.dirname(__file__))
from pipeline import answer, classify_query

print("=" * 50)
print("  Football Fan Q&A Bot")
print("  Type 'quit' to exit")
print("=" * 50)

history = []

FOLLOWUP_KEYWORDS = ["what about", "and what", "how about", "same for", "what else", "tell me more", "who else", "which one"]

def is_followup(question: str) -> bool:
    q = question.lower().strip()
    # Short questions are likely follow-ups
    if len(q.split()) <= 4:
        return True
    return any(kw in q for kw in FOLLOWUP_KEYWORDS)

while True:
    question = input("\nYou: ").strip()
    if question.lower() in ["quit", "exit", "q"]:
        print("Goodbye!")
        break
    if not question:
        continue

    # Only inject history for follow-up questions
    if history and is_followup(question):
        last_q, last_a = history[-1]
        context_question = f"Previous question: {last_q}\nPrevious answer summary: {last_a[:150]}\n\nFollow-up question: {question}"
    else:
        context_question = question

    query_type = classify_query(question)
    print(f"[{query_type.upper()}]")
    response = answer(context_question)
    print(f"Bot: {response}")

    history.append((question, response))
    if len(history) > 3:
        history.pop(0)
