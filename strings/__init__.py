# Authored By Certified Coders © 2025

from pathlib import Path

import yaml

languages = {}
languages_present = {}


def get_string(lang: str):
    return languages[lang]


langs_dir = Path("./strings/langs")

with open(langs_dir / "en.yml", encoding="utf8") as f:
    languages["en"] = yaml.safe_load(f)
    languages_present["en"] = languages["en"]["name"]

for filepath in langs_dir.iterdir():
    if not filepath.suffix == ".yml":
        continue
    
    language_name = filepath.stem
    if language_name == "en":
        continue
    
    with open(filepath, encoding="utf8") as f:
        languages[language_name] = yaml.safe_load(f)
    
    for item in languages["en"]:
        if item not in languages[language_name]:
            languages[language_name][item] = languages["en"][item]
    
    try:
        languages_present[language_name] = languages[language_name]["name"]
    except KeyError:
        raise ValueError(f"Language file '{filepath.name}' is missing required 'name' field")
