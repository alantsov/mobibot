"""
Helper functions for LaTeX and mathematical notation processing.
"""

import logging
import re
import traceback

from bs4 import BeautifulSoup
from latex2mathml.converter import convert
from pylatexenc.latex2text import LatexNodes2Text

logger = logging.getLogger(__name__)


def latex_to_mathml(latex):
    """Convert LaTeX string to MathML string with alttext attribute."""
    latex = latex.replace("mathrm", "text")
    latex = latex.replace("mathbf", "text")
    latex = latex.replace("mathbb", "text")
    try:
        rendered_mathml = convert(latex)
        rendered_mathml = rendered_mathml.replace("<math ", f'<math alttext="{latex}" ')
        return rendered_mathml
    except Exception as e:
        logger.debug(f"Error converting latex to mathml: {latex}, error: {e}")
        return None


def render_latex_in_text(text):
    r"""Find \( ... \) and replace with MathML."""
    pattern = r"\\\((.*?)\\\)"

    def replace_match(match):
        latex = match.group(1)
        mathml = latex_to_mathml(latex)
        return mathml if mathml else match.group(0)

    return re.sub(pattern, replace_match, text)


def mathml_to_span(mathml_str):
    """
    Convert MathML string to simple HTML span element.
    will raise Exception if input is not valid MathML or a block math element."""
    soup = BeautifulSoup(mathml_str, "html.parser")
    math_tag = soup.find("math")
    if math_tag is None:
        raise Exception("Invalid MathML input")
    container = soup.new_tag("span")
    process_inline_math(math_tag, container, soup)
    return str(container)


def process_inline_math(element, parent_html, soup):
    if element.name is None:
        if element.string and element.string.strip():
            parent_html.append(element.string)
        return
    if element.name in ["math", "mrow"]:
        for child in element.children:
            process_inline_math(child, parent_html, soup)
    elif element.name == "semantics":
        first_child = list(element.children)[0]
        process_inline_math(first_child, parent_html, soup)
    elif element.name == "annotation":
        logger.debug(f"Skipping annotation element {element.string}")
    elif element.name == "msub":
        children = list(filter(lambda x: x.name is not None, element.children))
        if len(children) >= 2:
            base = children[0]
            sub = children[1]
            container = soup.new_tag("span")
            parent_html.append(container)
            process_inline_math(base, container, soup)
            sub_span = soup.new_tag("sub")
            container.append(sub_span)
            process_inline_math(sub, sub_span, soup)
        else:
            raise Exception("Invalid msub element")
    elif element.name == "msup":
        children = list(filter(lambda x: x.name is not None, element.children))
        if len(children) >= 2:
            base = children[0]
            sub = children[1]
            container = soup.new_tag("span")
            parent_html.append(container)
            process_inline_math(base, container, soup)
            sub_span = soup.new_tag("sup")
            container.append(sub_span)
            process_inline_math(sub, sub_span, soup)
        else:
            raise Exception("Invalid msub element")
    elif element.name == "msqrt":
        children = list(filter(lambda x: x.name is not None, element.children))
        if len(children) >= 1:
            container = soup.new_tag("span")
            container.append("sqrt(")
            parent_html.append(container)
            process_inline_math(children[0], container, soup)
            container.append(")")
        else:
            raise Exception("Invalid msqrt element")
    elif element.name == "msubsup":
        children = list(filter(lambda x: x.name is not None, element.children))
        if len(children) >= 3:
            base = children[0]
            sub = children[1]
            sup = children[2]
            container = soup.new_tag("span")
            parent_html.append(container)
            process_inline_math(base, container, soup)
            sub_span = soup.new_tag("sub")
            container.append(sub_span)
            process_inline_math(sub, sub_span, soup)
            sup_span = soup.new_tag("sup")
            container.append(sup_span)
            process_inline_math(sup, sup_span, soup)
    elif element.name == "mfrac":
        children = list(filter(lambda x: x.name is not None, element.children))
        if len(children) >= 2:
            numerator = children[0]
            denominator = children[1]
            container = soup.new_tag("span")
            parent_html.append(container)
            numerator_span = soup.new_tag("span")
            numerator_span.append("(")
            container.append(numerator_span)
            process_inline_math(numerator, numerator_span, soup)
            numerator_span.append(")")
            denominator_span = soup.new_tag("span")
            container.append("/")
            container.append(denominator_span)
            denominator_span.append("(")
            process_inline_math(denominator, denominator_span, soup)
            denominator_span.append(")")
    elif element.name == "mspace":
        parent_html.append("\u00a0")  # Non-breaking space
    elif element.name in ["mi", "mo", "mn", "mtext"]:
        span = soup.new_tag("span")
        span.string = element.get_text().strip()
        parent_html.append(span)
    else:
        raise Exception(f"Unsupported inline MathML element {element.name}")


def latex_to_utf_8(latex):
    try:
        converter = LatexNodes2Text()
        text_formula = converter.latex_to_text(latex)
    except Exception:
        logger.debug(f"Failed to convert LaTeX to text using service: {latex}")
        logger.debug(traceback.format_exc())
        # Fall back to the raw LaTeX string if the service is unavailable;
        # downstream pipeline will still work, just with less pretty math rendering.
        text_formula = latex
    # 120120 𝔸
    # 120146 𝕒
    # 119834 𝐚
    # 119808 𝐀
    # 97 a
    # 65 A
    letter_a_in_utf_8 = {120120: 65, 119834: 97, 120146: 97, 119808: 65}
    all_letters = dict([])
    for a, b in letter_a_in_utf_8.items():
        for i in range(26):  # iterate english alphabet, contains 26 letters
            all_letters[chr(a + i)] = chr(b + i)
    text_formula = "".join([all_letters[c] if c in all_letters else c for c in text_formula])
    return text_formula


def process_math(soup):
    logger.debug("process_math_start")

    # Convert raw LaTeX to MathML first
    for text_node in soup.find_all(string=True):
        if r"\(" in text_node:
            new_text = render_latex_in_text(text_node)
            if new_text != text_node:
                new_soup = BeautifulSoup(new_text, "html.parser")
                text_node.replace_with(new_soup)

    for math_tag in soup.find_all("math"):
        if "alttext" not in math_tag.attrs:
            continue
        latex = math_tag["alttext"]
        text_formula = latex_to_utf_8(latex)

        # Handle simple formulas (single chars or plain text)
        if len(latex) == 1:
            # If it's a single char, just wrap in span
            if len(latex) == 1:
                span_string = f"<span>{latex}</span>"
                span_tag = BeautifulSoup(span_string, "html.parser")
                math_tag.replace_with(span_tag)
                continue

        # For everything else, try mathml_to_span
        logger.debug("complicated latex:")
        logger.debug("latex: %s", latex)
        logger.debug("utf8: %s", text_formula)
        mathml_str = str(math_tag)
        try:
            html_str = mathml_to_span(mathml_str)
        except Exception:
            logger.debug("Failed to convert MathML to span:")
            logger.debug(traceback.format_exc())
            html_str = f"<span>{text_formula}</span>"
        new_tag = BeautifulSoup(html_str, "html.parser")
        math_tag.replace_with(new_tag)
    return soup
