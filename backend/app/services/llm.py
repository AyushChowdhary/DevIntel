
from dotenv import load_dotenv
import os
from google import genai

# Load env variables
load_dotenv()

# Create client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_answer(query, context):
    prompt = f"""
You are an expert software engineer.

Context:
{context}

Question:
{query}

Instructions:
- Identify programming language
- Mention file names
- Be precise
- If unsure, say so

Answer:
"""

    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        contents=prompt,
    )

    return response.text or "No response"

    