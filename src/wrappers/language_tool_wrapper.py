import logging
from dataclasses import dataclass
from typing import Any

import requests

PORT = 8010
logger = logging.getLogger(__name__)


def set_language_tool_port(language_tool_port):
    global PORT
    PORT = language_tool_port


@dataclass
class Replacement:
    value: str


@dataclass
class Rule:
    id: str
    description: str | None = None
    issueType: str | None = None
    category: dict[str, Any] | None = None


@dataclass
class Match:
    offset: int
    length: int
    message: str
    rule: Rule
    replacements: list[Replacement]
    context: dict[str, Any] | None = None
    sentence: str | None = None


@dataclass
class LanguageToolResponse:
    matches: list[Match]
    software: dict[str, Any] | None = None
    language: dict[str, Any] | None = None
    warnings: dict[str, Any] | None = None


def check_text_with_language_tool(text, language):
    url = f"http://localhost:{PORT}/v2/check"
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    data = {"text": text, "language": language, "enabledOnly": "false"}
    logger.debug("languagetool: %s", data)
    response = requests.post(url, headers=headers, data=data)
    try:
        response_dict = response.json()
        return response.json()
    except Exception:
        logger.debug("languagetool error: %s", response.text)
        return {}


def wrap_with_b_tag(text, errors, white_list_rules=None, black_list_rules=None):
    errors = sorted(errors, key=lambda x: x[0])
    result = []
    last_index = 0
    if not white_list_rules:
        white_list_rules = []
    if not black_list_rules:
        black_list_rules = []
    rules = white_list_rules + ["Two_PREP", "WORD_REPEAT_RULE", "ENGLISH_WORD_REPEAT_RULE"]
    for offset, length, error_message, rule, replacements in errors:  # replacements.value
        if rule["id"] in rules:
            logger.debug("%s %s %s", rule["id"], error_message, rule)
            new_text = replacements[0]["value"]
        else:
            new_text = text[offset : offset + length]
        result.append(text[last_index:offset])
        result.append(new_text)
        # if rule['id'] in black_list_rules or rule['id'] in white_list_rules:
        #     result.append(new_text)
        # else:
        #     result.append(f"<b style=\"color:{color};\">{new_text}</b>")
        last_index = offset + length
    result.append(text[last_index:])
    return "".join(result)


def fix_errors(text, errors, types_to_fix):
    errors = sorted(errors, key=lambda x: x[0])
    result = []
    last_index = 0
    for offset, length, error_message, rule, replacements in errors:
        if (
            rule["id"] in types_to_fix
            and len(replacements) > 0
            and (rule["id"] != "MORFOLOGIK_RULE_RU_RU" or "-" in text[offset : offset + length])
        ):
            new_text = replacements[0]["value"]
        else:
            new_text = text[offset : offset + length]
        result.append(text[last_index:offset])
        result.append(new_text)
        last_index = offset + length
    result.append(text[last_index:])
    return "".join(result)


def apply_and_count_errors_for_text(b, language):
    lang_dict = {"en": "en-US", "ru": "ru-RU"}
    language_for_checking = lang_dict[language] if language in lang_dict else language
    errors_dict = check_text_with_language_tool(b[2], language_for_checking)
    errors = list(
        filter(
            lambda e: e["rule"]["id"] not in ["MORFOLOGIK_RULE_RU_RU", "Many_PNN", "OPREDELENIA"],
            errors_dict["matches"],
        )
    )
    err_messages = [e["message"] for e in errors]
    errors_tuples = [
        (e["offset"], e["length"], e["message"], e["rule"], e["replacements"]) for e in errors
    ]
    return err_messages, errors_tuples


def check_text_with_language_tool_structured(text, language):
    """
    Check text with LanguageTool and return a structured LanguageToolResponse object.

    Args:
        text (str): The text to check
        language (str): The language code (e.g., 'en-US', 'ru-RU', 'en', 'ru')

    Returns:
        LanguageToolResponse: A structured response object
    """
    # Use the existing function to get the JSON response
    response_dict = check_text_with_language_tool(text, language)

    # Convert matches to structured objects
    matches = []
    for match_dict in response_dict.get("matches", []):
        # Create Rule object
        rule = Rule(
            id=match_dict["rule"]["id"],
            description=match_dict["rule"].get("description"),
            issueType=match_dict["rule"].get("issueType"),
            category=match_dict["rule"].get("category"),
        )

        # Create Replacement objects
        replacements = [Replacement(value=r["value"]) for r in match_dict.get("replacements", [])]

        # Create Match object
        match = Match(
            offset=match_dict["offset"],
            length=match_dict["length"],
            message=match_dict["message"],
            rule=rule,
            replacements=replacements,
            context=match_dict.get("context"),
            sentence=match_dict.get("sentence"),
        )

        matches.append(match)

    # Create and return LanguageToolResponse object
    return LanguageToolResponse(
        matches=matches,
        software=response_dict.get("software"),
        language=response_dict.get("language"),
        warnings=response_dict.get("warnings"),
    )
