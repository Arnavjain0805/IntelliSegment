"""
ai/assistant.py
Real Generative AI Assistant engine:
Directly interfaces with Google Gemini, OpenAI, or Groq to think, reason,
and generate authentic responses conditioned on real database facts.
"""

import os
import json
import urllib.request
import urllib.error
import re
import sys

# Ensure local modules can be resolved
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Attempt to load .env file
try:
    from dotenv import load_dotenv
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(env_file)
except Exception:
    pass

from ai.data_tools import (
    get_company_kpis,
    get_segments_context,
    get_customer_summary,
    get_all_customers_overview
)
from ai.prompts import (
    SYSTEM_PROMPT,
    CONCEPT_EXPLANATIONS,
    build_context_prompt
)

def get_active_api_key():
    """Retrieve active API key from server environment variables (.env)."""
    if os.environ.get("GEMINI_API_KEY") and os.environ.get("GEMINI_API_KEY").strip():
        return "gemini", os.environ.get("GEMINI_API_KEY").strip()
    if os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_API_KEY").strip():
        return "openai", os.environ.get("OPENAI_API_KEY").strip()
    if os.environ.get("GROQ_API_KEY") and os.environ.get("GROQ_API_KEY").strip():
        return "groq", os.environ.get("GROQ_API_KEY").strip()

    return "none", None


def call_gemini_api(api_key, prompt, system_instruction):
    """
    Calls Google Gemini API (gemini-2.5-flash / gemini-flash-lite-latest).
    Allows true generative thinking with zero hallucination constraints.
    """
    models = ["gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-2.5-pro"]
    last_error = None

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.95
            }
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=18) as response:
                result = json.loads(response.read().decode("utf-8"))
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return text, f"Google Gemini ({model})"
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            last_error = f"Gemini API ({model}) Error {e.code}: {err_body}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    raise Exception(last_error or "Unable to connect to Google Gemini API.")


def call_openai_api(api_key, prompt, system_instruction):
    """Calls OpenAI GPT-4o-mini / GPT-3.5-turbo."""
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    with urllib.request.urlopen(req, timeout=18) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"], "OpenAI (GPT-4o-mini)"


def call_groq_api(api_key, prompt, system_instruction):
    """Calls Groq Cloud (Llama 3.3)."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    with urllib.request.urlopen(req, timeout=18) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"], "Groq (Llama-3.3-70b)"


def process_chat_message(user_message):
    """
    Main entry point for handling natural language inquiries.
    Gathers factual data context, checks for configured LLM key,
    and runs genuine generative reasoning.
    """
    if not user_message or not user_message.strip():
        return "Please ask a question regarding your customers, segments, or business metrics.", "System"

    query = user_message.strip()

    # 1. Fetch live database facts to ground the AI
    kpis = get_company_kpis()
    segments_ctx = get_segments_context()

    # 2. Extract potential customer name reference from the message
    customer_ctx = None
    all_custs = get_all_customers_overview()
    for c in all_custs:
        if re.search(r'\b' + re.escape(c['name'].lower()) + r'\b', query.lower()):
            customer_ctx = get_customer_summary(c['name'])
            break

    # 3. Construct structured context prompt
    prompt = build_context_prompt(query, kpis, segments_ctx, customer_ctx, all_custs)

    # 4. Check for Real LLM Provider
    provider, api_key = get_active_api_key()

    if api_key:
        try:
            if provider == 'gemini':
                return call_gemini_api(api_key, prompt, SYSTEM_PROMPT)
            elif provider == 'openai':
                return call_openai_api(api_key, prompt, SYSTEM_PROMPT)
            elif provider == 'groq':
                return call_groq_api(api_key, prompt, SYSTEM_PROMPT)
        except Exception as e:
            return (
                f"⚠️ **AI Service Notice**: The generative AI service encountered an error:\n\n"
                f"> `{str(e)}`\n\n"
                f"Please ensure the server's `.env` configuration contains a valid API key."
            ), "API Error"

    # 5. If no API key is configured on the server
    return (
        f"🔒 **Server Configuration Required**\n\n"
        f"The AI Assistant operates with server-side authentication for maximum security. "
        f"To enable real-time generative reasoning, configure a `GEMINI_API_KEY` (or `OPENAI_API_KEY`) "
        f"in the server's `.env` file."
    ), "No Key Configured"
