"""
CadenceWorks — Config Helper
Reads credentials from environment variables (Railway / production)
with a transparent fallback to config.ini for local development.

Environment variables take precedence over config.ini values.
"""

import os
import configparser
from pathlib import Path

BASE_DIR    = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.ini"


def load_config() -> configparser.ConfigParser:
    """
    Return a ConfigParser populated from config.ini (if present)
    then overridden by any matching environment variables.

    Env vars recognised:
        TWILIO_ACCOUNT_SID    -> [twilio] account_sid
        TWILIO_AUTH_TOKEN     -> [twilio] auth_token
        TWILIO_FROM_NUMBER    -> [twilio] from_number
        PRACTICE_NAME         -> [practice] name
        PRACTICE_CURRENCY     -> [practice] currency
        PRACTICE_COUNTRY_CODE -> [practice] country_code
        ANTHROPIC_API_KEY     -> [anthropic] api_key
    """
    cfg = configparser.ConfigParser()

    # 1. Load file (works locally, silently skipped in production)
    if CONFIG_PATH.exists():
        cfg.read(CONFIG_PATH)

    # 2. Ensure sections exist so .set() never raises NoSectionError
    for section in ("twilio", "practice", "reminder_agent", "templates", "anthropic"):
        if not cfg.has_section(section):
            cfg.add_section(section)

    # 3. Override with environment variables
    _env_overrides = {
        "twilio": {
            "account_sid": "TWILIO_ACCOUNT_SID",
            "auth_token":  "TWILIO_AUTH_TOKEN",
            "from_number": "TWILIO_FROM_NUMBER",
        },
        "practice": {
            "name":         "PRACTICE_NAME",
            "currency":     "PRACTICE_CURRENCY",
            "country_code": "PRACTICE_COUNTRY_CODE",
        },
        "anthropic": {
            "api_key": "ANTHROPIC_API_KEY",
        },
    }

    for section, mappings in _env_overrides.items():
        for key, env_var in mappings.items():
            value = os.environ.get(env_var)
            if value:
                cfg.set(section, key, value)

    return cfg
