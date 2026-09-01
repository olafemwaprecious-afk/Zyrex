import os
from dotenv import load_dotenv
from google import genai

# Load .env
load_dotenv()

# Get API key
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is missing from your .env file.")

# Create Gemini client
client = genai.Client(api_key=API_KEY)

# Your AI's initial role
SYSTEM_INSTRUCTION = """
You are a helpful, intelligent AI assistant.

Your job is to understand the user's request carefully,
reason about it, and provide accurate and useful answers.

Be clear, honest, respectful, and concise.

Do not pretend to know something you do not know.
If you are uncertain, say so.

This is the initial version of the AI.
Its role, knowledge, memory, tools, and behavior will
be expanded and improved over time.
"""


def ask_ai(user_message: str) -> str:
    """Send a message to Gemini using the Interactions API."""

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=user_message,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    return interaction.output_text


if __name__ == "__main__":
    while True:
        user_message = input("You: ")

        if user_message.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        try:
            response = ask_ai(user_message)
            print("AI:", response)
        except Exception as e:
            print("Error:", e)