import datetime
from main import conversation_history, analyze, AnalyzeRequest

conversation_history.clear()

analyze(AnalyzeRequest(mode="ask", prompt="Who is the president?"))
print("History length:", len(conversation_history))

analyze(AnalyzeRequest(mode="ask", prompt="How old is he?"))

print("History:", conversation_history)
