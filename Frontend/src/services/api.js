const API_BASE = "http://raspy.local:8000";

export async function analyze(mode, prompt = "") {
  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      mode,
      prompt,
    }),
  });

  if (!response.ok) {
    throw new Error("Backend request failed");
  }

  return response.json();
}
