import json
from typing import Any, Dict

from ai import client, SYSTEM_INSTRUCTION, ask_ai


# ============================================================
# PHARMA AI — SAFETY + INTENT ENGINE
# ============================================================
#
# IMPORTANT:
# This file DOES NOT create a second Gemini API connection.
# It imports the already-working Gemini client from ai.py.
#
# Flow:
#
# User message
#      ↓
# safety.py
#      ↓
# Understand intent / emotion / urgency
#      ↓
# Route the request
#      ↓
# ai.py → Gemini
#
# Future:
#      ↓
# medication tools
# game tools
# medical evidence
# memory
# WhatsApp
# ============================================================


# ============================================================
# CLASSIFICATION INSTRUCTIONS
# ============================================================

ANALYSIS_INSTRUCTION = """
You are the PHARMA AI message understanding engine.

Your job is NOT to answer the user's message.

Your job is to understand what the user is trying to communicate
and return a structured classification.

A user may write very short, emotional, vague, indirect, or complex
messages. Do not assume that every message is asking for medicine.

Understand the likely meaning from the complete message.

Classify these dimensions:

1. intent
2. emotional_state
3. urgency
4. response_mode
5. needs_clarification

INTENT OPTIONS
--------------
greeting
general_conversation
general_health
medication_information
medication_side_effect
medication_interaction
medication_dosage_question
symptom_question
emotional_support
mental_wellbeing
game_request
other

EMOTIONAL_STATE OPTIONS
-----------------------
neutral
happy
sad
anxious
frustrated
confused
lonely
overwhelmed
stressed
angry
grieving
mixed
unknown

URGENCY OPTIONS
---------------
normal
needs_attention
urgent

Use "urgent" only when the message reasonably suggests that the user
may need immediate professional or emergency assistance.

Do not invent details that the user did not provide.

RESPONSE_MODE OPTIONS
---------------------
normal_ai
supportive
medical_information
clarification
game
urgent_support

IMPORTANT SAFETY RULE
---------------------
When a user expresses sadness, depression, loneliness, stress,
frustration, grief, or another difficult emotion, do NOT automatically
classify the message as a medication request.

The appropriate route may simply be supportive conversation.

PHARMA AI should not prescribe drugs for emotional distress.

It may provide compassionate general support and encourage appropriate
professional help when warranted.

If the user appears to be in immediate danger or may need urgent help,
use "urgent_support" and "urgent" rather than treating the request as
a normal medication question.

Do not provide or invent instructions for self-harm or suicide.

GAME REQUESTS
-------------
If the user clearly asks to play a game, use:

intent = "game_request"
response_mode = "game"

A future game system will use this classification to launch an available
game.

Do not claim that a game has launched unless the application actually
has a connected game tool.

OUTPUT
------
Return ONLY valid JSON.

Required format:

{
  "intent": "...",
  "emotional_state": "...",
  "urgency": "...",
  "response_mode": "...",
  "needs_clarification": true,
  "reason": "short explanation"
}
"""


# ============================================================
# SAFE DEFAULT
# ============================================================

def default_analysis() -> Dict[str, Any]:
    """
    Safe fallback when the classification request fails.
    """

    return {
        "intent": "other",
        "emotional_state": "unknown",
        "urgency": "normal",
        "response_mode": "normal_ai",
        "needs_clarification": False,
        "reason": "Unable to classify the message reliably.",
    }


# ============================================================
# VALIDATE CLASSIFICATION
# ============================================================

VALID_INTENTS = {
    "greeting",
    "general_conversation",
    "general_health",
    "medication_information",
    "medication_side_effect",
    "medication_interaction",
    "medication_dosage_question",
    "symptom_question",
    "emotional_support",
    "mental_wellbeing",
    "game_request",
    "other",
}

VALID_EMOTIONS = {
    "neutral",
    "happy",
    "sad",
    "anxious",
    "frustrated",
    "confused",
    "lonely",
    "overwhelmed",
    "stressed",
    "angry",
    "grieving",
    "mixed",
    "unknown",
}

VALID_URGENCY = {
    "normal",
    "needs_attention",
    "urgent",
}

VALID_RESPONSE_MODES = {
    "normal_ai",
    "supportive",
    "medical_information",
    "clarification",
    "game",
    "urgent_support",
}


def validate_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make sure Gemini's classification follows our allowed structure.
    """

    result = default_analysis()

    if not isinstance(data, dict):
        return result

    intent = data.get("intent")
    emotional_state = data.get("emotional_state")
    urgency = data.get("urgency")
    response_mode = data.get("response_mode")
    needs_clarification = data.get("needs_clarification")
    reason = data.get("reason")

    if intent in VALID_INTENTS:
        result["intent"] = intent

    if emotional_state in VALID_EMOTIONS:
        result["emotional_state"] = emotional_state

    if urgency in VALID_URGENCY:
        result["urgency"] = urgency

    if response_mode in VALID_RESPONSE_MODES:
        result["response_mode"] = response_mode

    if isinstance(needs_clarification, bool):
        result["needs_clarification"] = needs_clarification

    if isinstance(reason, str):
        result["reason"] = reason[:500]

    return result


# ============================================================
# UNDERSTAND USER MESSAGE
# ============================================================

def analyze_message(user_message: str) -> Dict[str, Any]:
    """
    Understand the user's message using the existing Gemini client.

    This does NOT answer the user.
    It only classifies the message.
    """

    if not isinstance(user_message, str):
        raise TypeError("user_message must be a string.")

    user_message = user_message.strip()

    if not user_message:
        raise ValueError("user_message cannot be empty.")

    prompt = f"""
Analyze this user message according to your instructions.

USER MESSAGE:
{user_message}
"""

    try:
        interaction = client.interactions.create(
            model="gemini-3.6-flash",
            input=prompt,
            system_instruction=ANALYSIS_INSTRUCTION,
        )

        raw_output = interaction.output_text

        if not raw_output:
            return default_analysis()

        # Remove accidental markdown code fences if Gemini adds them.
        cleaned = raw_output.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "", 1)
            cleaned = cleaned.replace("```", "", 1)
            cleaned = cleaned.strip()

        parsed = json.loads(cleaned)

        return validate_analysis(parsed)

    except (json.JSONDecodeError, TypeError, ValueError):
        return default_analysis()

    except Exception:
        return default_analysis()


# ============================================================
# ROUTING
# ============================================================

def route_message(user_message: str) -> Dict[str, Any]:
    """
    Analyze and decide what PHARMA AI should do with the message.
    """

    analysis = analyze_message(user_message)

    return {
        "user_message": user_message,
        "analysis": analysis,
    }


# ============================================================
# GENERATE PHARMA AI RESPONSE
# ============================================================

def process_message(user_message: str) -> Dict[str, Any]:
    """
    Main Phase 2 entry point.

    It understands the message first, then decides whether the message
    should go to normal Gemini conversation, supportive conversation,
    medical information, a future game tool, or urgent support.
    """

    routed = route_message(user_message)
    analysis = routed["analysis"]

    response_mode = analysis["response_mode"]

    # --------------------------------------------------------
    # GAME
    # --------------------------------------------------------
    #
    # We do not actually launch a game yet.
    # The future game engine will be connected here.
    #
    if response_mode == "game":
        return {
            "type": "game_request",
            "analysis": analysis,
            "message": (
                "The user wants to play a game. "
                "Game launching will be connected in a future phase."
            ),
            "game": {
                "available": False,
                "requested": True,
            },
        }

    # --------------------------------------------------------
    # URGENT SUPPORT
    # --------------------------------------------------------

    if response_mode == "urgent_support":
        response = ask_ai(
            f"""
The user may need urgent professional help.

User message:
{user_message}

Respond with calm, supportive language.

Do not diagnose the user.
Do not prescribe medication.
Do not provide dangerous instructions.
Encourage appropriate immediate professional or emergency help
when warranted.

Focus on the user's immediate wellbeing.
"""
        )

        return {
            "type": "urgent_support",
            "analysis": analysis,
            "response": response,
        }

    # --------------------------------------------------------
    # SUPPORTIVE CONVERSATION
    # --------------------------------------------------------

    if response_mode == "supportive":
        response = ask_ai(
            f"""
The user appears to need emotional support.

User message:
{user_message}

Respond as a compassionate healthcare information assistant.

Do not assume the user wants medication.
Do not prescribe medication for emotional distress.

Listen to what the user is saying, acknowledge their feelings,
and provide practical, gentle, general support.

You may suggest healthy next steps, talking with someone they trust,
taking a break, doing a simple enjoyable activity, or seeking
professional support when appropriate.

Do not claim to be a therapist or doctor.
"""
        )

        return {
            "type": "supportive",
            "analysis": analysis,
            "response": response,
        }

    # --------------------------------------------------------
    # CLARIFICATION
    # --------------------------------------------------------

    if response_mode == "clarification":
        response = ask_ai(
            f"""
The user's message is unclear.

User message:
{user_message}

Ask one or two useful follow-up questions that help understand
what the user actually needs.

Do not guess the missing medical information.
"""
        )

        return {
            "type": "clarification",
            "analysis": analysis,
            "response": response,
        }

    # --------------------------------------------------------
    # MEDICAL INFORMATION
    # --------------------------------------------------------

    if response_mode == "medical_information":
        response = ask_ai(
            f"""
Answer the user's health or medication question as PHARMA AI.

User message:
{user_message}

Provide general educational information.

Do not invent facts.
Do not prescribe.
Do not present uncertain information as certain.

Remember that authoritative medical evidence and medication databases
will be connected in a later phase.
"""
        )

        return {
            "type": "medical_information",
            "analysis": analysis,
            "response": response,
        }

    # --------------------------------------------------------
    # NORMAL AI CONVERSATION
    # --------------------------------------------------------

    response = ask_ai(user_message)

    return {
        "type": "normal",
        "analysis": analysis,
        "response": response,
    }


# ============================================================
# DIRECT TEST MODE
# ============================================================

if __name__ == "__main__":
    print("==========================================")
    print("PHARMA AI — Safety + Intent Engine")
    print("==========================================")
    print("Type 'exit' or 'quit' to stop.")
    print()

    while True:
        try:
            user_message = input("You: ").strip()

            if user_message.lower() in {"exit", "quit"}:
                print("PHARMA AI: Goodbye!")
                break

            if not user_message:
                print("PHARMA AI: Please enter a message.")
                continue

            result = process_message(user_message)

            print()
            print("Intent:", result["analysis"]["intent"])
            print("Emotion:", result["analysis"]["emotional_state"])
            print("Urgency:", result["analysis"]["urgency"])
            print("Mode:", result["analysis"]["response_mode"])

            if result["type"] == "game_request":
                print(
                    "PHARMA AI: I understand you want to play a game. "
                    "The game system will be connected later."
                )
            else:
                print("PHARMA AI:", result["response"])

            print()

        except KeyboardInterrupt:
            print("\nPHARMA AI: Goodbye!")
            break

        except Exception as exc:
            print(f"\nPHARMA AI ERROR: {exc}\n")