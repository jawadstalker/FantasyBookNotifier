# save as merged_ner_extractor.py
import stanza
import spacy
import keyboard
import pyperclip
from langdetect import detect
from collections import Counter

# ---------------------------
# Load Models
# ---------------------------
print("Loading Persian Stanza model...")
fa_nlp = stanza.Pipeline('fa')

print("Loading English spaCy model...")
en_nlp = spacy.load("en_core_web_sm")

# ---------------------------
# Persian NER (Stanza)
# ---------------------------
def extract_persian_names(text):
    doc = fa_nlp(text)
    names = set()

    for ent in doc.ents:
        if ent.type == 'pers':
            # If name has surname, we keep only first part to avoid duplication
            name = ent.text.split()[0]
            names.add(name)

    return list(names)

# ---------------------------
# English NER (spaCy)
# ---------------------------
def extract_english_names(text):
    doc = en_nlp(text)
    persons = [ent.text.strip() for ent in doc.ents if ent.label_ == "PERSON"]
    counted = Counter(persons)
    return [name for name, _ in counted.most_common()]

# ---------------------------
# Language Router
# ---------------------------
def extract_names(text):
    try:
        lang = detect(text)
    except:
        lang = "unknown"

    if lang == "fa":
        print("Detected: Persian (FA)")
        return extract_persian_names(text)

    elif lang == "en":
        print("Detected: English (EN)")
        return extract_english_names(text)

    else:
        print("Language Unknown.")
        return []

# ---------------------------
# Hotkey Action
# ---------------------------
def on_hotkey():
    text = pyperclip.paste()

    if not text:
        print("Clipboard خالی است.")
        return

    print("\n--- Processing Text ---")
    names = extract_names(text)

    if names:
        print("Found Names:")
        for n in names:
            print("-", n)

        pyperclip.copy("\n".join(names))
        print("\n(Names copied to clipboard.)")
    else:
        print("No characters found.")

# ---------------------------
# Main Listener
# ---------------------------
if __name__ == "__main__":
    print("Press Ctrl+Shift+V to extract names (Persian or English).")
    print("Press Ctrl+C to exit.")
    
    keyboard.add_hotkey("ctrl+shift+v", on_hotkey)
    keyboard.wait()
