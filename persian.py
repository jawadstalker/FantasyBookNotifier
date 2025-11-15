import stanza

# دانلود مدل فارسی (فقط یک بار)
stanza.download('fa')

# بارگذاری مدل
nlp = stanza.Pipeline('fa', processors='tokenize,ner')

text = "علی و سارا به مدرسه رفتند و با محمد و لیلا ملاقات کردند."
doc = nlp(text)

for ent in doc.ents:
    if ent.type == 'PER':  # PER = شخص
        print(ent.text)
