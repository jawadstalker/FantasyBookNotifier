import stanza

stanza.download('fa')

nlp = stanza.Pipeline('fa', processors='tokenize,ner')

text = "علی و سارا به مدرسه رفتند و با محمد و لیلا ملاقات کردند."
doc = nlp(text)

for ent in doc.ents:
    if ent.type == 'PER':  
        print(ent.text)
