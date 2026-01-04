import re

from src.wrappers import language_tool_wrapper as language_tool_wrapper
from src.wrappers import ollama_wrapper as ollama_wrapper


def fix_grammar_with_llm(text, language):
    """
    Fix grammar in text using LanguageTool and LLM (Ollama).

    Args:
        text (str): The text to fix
        language (str): The language code (e.g., 'en-US')

    Returns:
        str: The fixed text
    """
    # Normalize spaces in text
    text = re.sub(r"\s+", " ", text)

    # Get LanguageTool results
    structured_response = language_tool_wrapper.check_text_with_language_tool_structured(
        text, language
    )

    # Sort matches by offset to process them in order
    matches = sorted(structured_response.matches, key=lambda m: m.offset)

    # Track offset adjustments as we apply fixes
    offset_adjustment = 0
    fixed_text = text

    for match in matches:
        if len(match.replacements) > 0:
            # Adjust the offset based on previous fixes
            adjusted_offset = match.offset + offset_adjustment
            adjusted_end = adjusted_offset + match.length

            # Create options dictionary
            options = {}

            # Add current text as first option
            current_text = fixed_text[adjusted_offset:adjusted_end]
            options["a"] = current_text
            best_option = "a"
            if current_text.lower() == current_text:  # ignore names
                for i, replacement in enumerate(
                    match.replacements[:4]
                ):  # Limit to 4 additional options
                    option_key = chr(98 + i)  # b, c, d, e
                    options[option_key] = replacement.value
                llm_options = {}
                for key in options:
                    llm_options[key] = (
                        fixed_text[max(0, adjusted_offset - 40) : adjusted_offset]
                        + options[key]
                        + fixed_text[adjusted_end : min(adjusted_end + 40, len(fixed_text))]
                    )
                best_option = ollama_wrapper.choose_best_option(
                    fixed_text, match.message, llm_options
                )

            chosen_replacement = options.get(best_option, current_text)

            # Apply the fix to the text
            fixed_text = (
                fixed_text[:adjusted_offset] + chosen_replacement + fixed_text[adjusted_end:]
            )

            # Update offset adjustment for subsequent matches
            old_length = match.length
            new_length = len(chosen_replacement)
            offset_adjustment += new_length - old_length
    return fixed_text
