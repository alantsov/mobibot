import re


def clean_title(title):
    if title is None:
        return ""
    return re.sub(r"[^\w\s\n]", "_", title)[:64].replace(" ", "_")


def parse_start_time(hh_mm_ss):
    if len(hh_mm_ss.split(":")) == 3:
        hh, mm, ss = hh_mm_ss.split(":")
    elif len(hh_mm_ss.split(":")) == 2:
        mm, ss = hh_mm_ss.split(":")
        hh = 0
    else:
        raise Exception("wrong hh_mm_ss format")
    return int(hh) * 3600 + int(mm) * 60 + int(ss)


def detect_language(text):
    language = "en"
    if len(re.findall("[а-яА-Я]", text)) > 5:
        language = "ru"
    if len(re.findall("[а-яА-Я]", text)) > len(re.findall("[a-zA-Z]", text)):
        language = "ru"
    return language


def extract_links(text):
    pattern = r"http[s]?://(?:[a-zA-Zа-яА-Я]|[1][2][3][4][5]|[$-_@.&+]|[!*$$$$,]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    links = re.findall(pattern, text)
    return links
