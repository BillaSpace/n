import os
import yaml

languages = {}
languages_present = {}

langs_dir = os.path.join(os.path.dirname(__file__), "langs")

def load_yaml_file(path, lang_code):
    try:
        with open(path, encoding="utf8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ValueError("YAML content is not a dictionary.")
            return data
    except Exception as e:
        print(f"❌ Failed to load '{lang_code}.yml': {e}")
        return None


# Load English first (required)
en_path = os.path.join(langs_dir, "en.yml")
en_data = load_yaml_file(en_path, "en")

if not en_data:
    print("❌ Critical: Failed to load 'en.yml'. Cannot start the bot without it.")
    exit(1)

languages["en"] = en_data
languages_present["en"] = en_data.get("name", "English")


# Load all other languages
for filename in os.listdir(langs_dir):
    if not filename.endswith(".yml") or filename == "en.yml":
        continue

    lang_code = filename[:-4]
    lang_path = os.path.join(langs_dir, filename)
    lang_data = load_yaml_file(lang_path, lang_code)

    if not lang_data:
        continue  # Skip broken file

    # Fill missing keys from English
    for key in languages["en"]:
        if key not in lang_data:
            lang_data[key] = languages["en"][key]

    languages[lang_code] = lang_data

    try:
        languages_present[lang_code] = lang_data["name"]
    except KeyError:
        print(f"❌ '{filename}' missing required key: 'name'. Skipping.")
        continue
