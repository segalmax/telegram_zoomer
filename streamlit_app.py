"""Minimal, fail-fast Streamlit UI for Telegram-Zoomer.

Assumptions
-----------
• All configuration lives in Supabase and is accessed via ConfigLoader (fail-fast).
• Anthropic translation and vector-store helpers already exist and raise on error.
• No fall-backs, no defaults – caller must export SUPABASE_ENV (dev/prod).
• On every translation we write the (src, tgt) pair to Supabase.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import os
import httpx

# bootstrap Django ORM so we can reuse model.save() and change-log
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config_admin.settings")
django.setup()

from bot_config import models as m
import streamlit as st

from app.config_loader import get_config_loader, ConfigurationError
from app.autogen_translation import translate_and_link
from app.vector_store import save_pair

cfg = get_config_loader()  # will fail fast if env vars missing

def save_and_notify(obj, success_msg: str) -> None:
    """Save Django model object and show success message."""
    obj.save()
    st.success(success_msg)
    st.rerun()  # Force UI refresh to show updated values

st.set_page_config(page_title="Telegram Zoomer – Live Translate", layout="wide")

st.sidebar.markdown("## Environment")
supabase_env = os.getenv("SUPABASE_ENV", "prod")
st.sidebar.write(f"`SUPABASE_ENV={supabase_env}`")
st.sidebar.write(f"DB → {cfg.supabase_url}")

# ---------------------------------------------------------------------
# UI INPUT
# ---------------------------------------------------------------------

st.title("🔄 Live Translation")

# ---------------------------- SETTINGS PANEL ----------------------------
with st.sidebar.expander("⚙️ Update Settings", expanded=False):
    section = st.selectbox("Choose config table", [
        "AI Model",
        "Processing Limits",
        "Translation Memory",
        "Translator Prompt",
        "Article Extraction",
        "Environment Config",
        "Message Template",
        "Generic JSON Editor"
    ])

    if section == "AI Model":
        model = cfg.get_ai_model_config()
        with st.form("ai_model_form"):
            model_id = st.text_input("model_id", model["model_id"])
            max_tokens = st.number_input("max_tokens", value=int(model["max_tokens"]), step=1, format="%d")
            temperature = st.number_input("temperature", value=float(model["temperature"]), step=0.1, format="%f")
            submitted = st.form_submit_button("Save")
        if submitted:
            obj = m.AIModelConfig.objects.filter(is_default=True).first()
            obj.model_id = model_id
            obj.max_tokens = max_tokens
            obj.temperature = temperature
            obj.is_default = True
            save_and_notify(obj, "AI model config updated ✔️")

    elif section == "Processing Limits":
        limits = cfg.get_processing_limits()
        with st.form("proc_limits_form"):
            new_vals = {}
            for k, v in limits.items():
                new_vals[k] = st.number_input(k, value=v, step=1)
            submitted = st.form_submit_button("Save")
        if submitted:
            obj = m.ProcessingLimits.objects.filter(environment=supabase_env).first()
            for k, v in new_vals.items():
                setattr(obj, k, v)
            save_and_notify(obj, "Processing limits updated")

    elif section == "Translation Memory":
        tm = cfg.get_translation_memory_config()
        with st.form("tm_form"):
            new_vals = {}
            for k, v in tm.items():
                new_vals[k] = st.text_input(k, value=str(v))
            submitted = st.form_submit_button("Save")
        if submitted:
            obj = m.TranslationMemoryConfig.objects.filter(is_active=True).first()
            for k, v in new_vals.items():
                setattr(obj, k, v if k != "recency_weight" else float(v))
            save_and_notify(obj, "Translation memory config updated")

    elif section == "Article Extraction":
        domain = st.text_input("Domain", "example.com")
        try:
            art_cfg = cfg.get_article_extraction_config(domain)
            with st.form("article_form"):
                language_code = st.text_input("language_code", art_cfg["language_code"])
                min_len = st.number_input("min_article_length", value=int(art_cfg["min_article_length"]), step=10)
                timeout = st.number_input("timeout_seconds", value=int(art_cfg["timeout_seconds"]), step=1)
                submitted = st.form_submit_button("Save")
            if submitted:
                obj = m.ArticleExtractionConfig.objects.get(domain=domain)
                obj.language_code = language_code
                obj.min_article_length = min_len
                obj.timeout_seconds = timeout
                save_and_notify(obj, "Article extraction config updated")
        except ConfigurationError as e:
            st.error(str(e))

    elif section == "Environment Config":
        env_cfg = cfg.get_environment_config()
        with st.form("env_form"):
            name_pattern = st.text_input("session_name_pattern", env_cfg["session_name_pattern"])
            log_level = st.text_input("log_level", env_cfg["log_level"])
            log_format = st.text_input("log_format", env_cfg["log_format"])
            submitted = st.form_submit_button("Save")
        if submitted:
            obj = m.EnvironmentConfig.objects.get(environment=supabase_env)
            obj.session_name_pattern = name_pattern
            obj.log_level = log_level
            obj.log_format = log_format
            save_and_notify(obj, "Environment config updated")

    elif section == "Message Template":
        name = st.text_input("Template name", "default")
        try:
            template = cfg.get_message_template(name)
            with st.form("tmpl_form"):
                content = st.text_area("Template", template, height=200)
                submitted = st.form_submit_button("Save")
            if submitted:
                obj = m.MessageTemplate.objects.get(name=name)
                obj.template = content
                save_and_notify(obj, "Message template updated")
        except ConfigurationError as e:
            st.error(str(e))

    elif section == "Translator Prompt":
        prompt = cfg.get_prompt("translator_prompt")
        with st.form("prompt_form"):
            content = st.text_area("Prompt Content", prompt, height=300)
            submitted = st.form_submit_button("Save")
        if submitted:
            obj = m.TranslationPrompt.objects.get(name="translator_prompt")
            obj.content = content
            save_and_notify(obj, "Prompt updated")
source_text = st.text_area("Source message", height=200)
use_memory = st.checkbox("Use translation memory (experimental)", value=True)

if st.button("Translate", disabled=not source_text.strip()):
    with st.spinner("Translating …"):
        try:
            # Fetch minimal runtime settings
            translator_prompt = cfg.get_prompt("translator_prompt")
            memories: list[dict] = []  # memory retrieval removed – TODO optional

            # Run translation (autogen helper handles Anthropic call + linking)
            translation, conversation_log = asyncio.run(translate_and_link(source_text, memories))

            st.success("Translation complete ✔️")
            st.subheader("Result")
            st.text_area("Modern Lurkmore Style", translation, height=200)

            # Save pair (no defensive checks – save_pair already asserts)
            save_pair(
                source_message_text=source_text,
                tgt=translation,
                conversation_log="\n".join(conversation_log),
            )

            # Persist analytics row (simple REST insert) – will raise if 401
            httpx.post(
                f"{cfg.supabase_url}/rest/v1/streamlit_conversations",
                headers={
                    "apikey": cfg.supabase_key,
                    "Authorization": f"Bearer {cfg.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={
                    "id": str(_dt.datetime.utcnow().timestamp()),
                    "source_text": source_text,
                    "translation_text": translation,
                    "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                },
                timeout=10,
            ).raise_for_status()

        except ConfigurationError as e:
            st.error(f"Configuration error – {e}")
            st.stop()
        except Exception as e:  # noqa: BLE001
            st.error(f"🚨 Translation failed – {e}")
            st.stop()
