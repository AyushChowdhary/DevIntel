import os

from google import genai
from google.genai import types

# ``gemini-2.0-flash`` was shut down in 2026. Keep the model configurable while
# using Google's maintained Flash alias as the no-configuration default.
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
MAX_OUTPUT_TOKENS = 500
SYSTEM_INSTRUCTION = (
    "You are DevIntel, a concise codebase assistant. Answer only from the supplied "
    "repository context. Cite relevant file paths, distinguish facts from assumptions, "
    "and say when the context is insufficient."
)


def generate_answer(task: str, context: str, api_key: str) -> str:
    """Generate one answer with a client created for this request only.

    The caller owns ``api_key`` and must not retain or log it. Creating the client here
    prevents one user's key from becoming shared application state.
    """
    client = genai.Client(api_key=api_key)
    prompt = f"Repository context:\n{context}\n\nTask:\n{task}"
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        ),
    )
    return response.text or "No response was generated."
