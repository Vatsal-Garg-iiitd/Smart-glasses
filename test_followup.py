from main import analyze, AnalyzeRequest
import json

print("--- Test 1: Initial Question ---")
req1 = AnalyzeRequest(mode="ask", prompt="Who is the president of the United States?")
res1 = analyze(req1)
print("Response 1:", res1.get("analysis", "Error"))

print("\n--- Test 2: Follow-up Question ---")
req2 = AnalyzeRequest(mode="ask", prompt="How old is he?")
res2 = analyze(req2)
print("Response 2:", res2.get("analysis", "Error"))

print("\n--- Context Verification ---")
print("Image captured on follow-up?", res2.get("image") is not None)
