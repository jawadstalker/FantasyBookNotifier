# save as extract_names_spacy.py
import pyperclip
import keyboard
import spacy
from collections import Counter
import re

nlp = spacy.load("en_core_web_sm")

def extract_persons_spacy(text):
    doc = nlp(text)
    persons = [ent.text.strip() for ent in doc.ents if ent.label_ == "PERSON"]
    counted = Counter(persons)
    return [name for name, _ in counted.most_common()]

def on_hotkey():
    text = pyperclip.paste()
    if not text:
        print("Clipboard خالیه.")
        return
    names = extract_persons_spacy(text)
    if names:
        print("Found PERSONs:")
        for n in names:
            print("-", n)
        pyperclip.copy("\n".join(names))
        print("\n(Names copied to clipboard.)")
    else:
        print("no charcters have been found")

if __name__ == "__main__":
    print("Press Ctrl+Shift+V to extract character names from clipboard. Ctrl+C to exit.")
    keyboard.add_hotkey('ctrl+shift+v', on_hotkey)
    keyboard.wait()  
