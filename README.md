# FantasyBookNotifier

<img src="logo.png" alt="FantasyBookNotifier Banner" width="200"/>


This project allows you to **summarize long story chapters** (English or Persian) completely **offline** using Python and HuggingFace models.

The program:
- Accepts **plain text (TXT)** or **PDF files**
- Uses local **Transformer** models to generate summaries
- Supports both **English** and **Persian**
- Automatically splits long texts into smaller chunks (hierarchical summarization)

---

## 🚀 Features
- Summarize very long chapters (5k–50k words)
- Works offline after the first model download
- Supports both CPU and GPU
- PDF → Text extraction built-in
- Clean command-line interface

---

## 📦 Installation

Install all required libraries in **one command**:

```
pip install transformers torch sentencepiece pdfplumber PyPDF2
```

> ⚠️ Note:  
> - Installing `torch` may download 150MB–800MB depending on CPU/GPU version.  
> - Models will download on first run (BART ~1.6GB, mT5-small ~300MB).

---

## 📝 Usage

### **1. Summarize a TXT file**

```
python local_summarizer.py --input-file chapter.txt --lang en
```

### **2. Summarize a PDF**

```
python local_summarizer.py --input-file chapter.pdf --lang fa
```

### **3. Paste text manually**

```
python local_summarizer.py --lang en
```

Paste the text in terminal, then press:

- **Ctrl + D** (Linux / Mac)
- **Ctrl + Z + Enter** (Windows)

---

## ⚙️ Optional Arguments

| Argument | Description |
|---------|-------------|
| `--lang en/fa` | Input language |
| `--model <name>` | Custom HuggingFace model |
| `--device -1/0/1` | CPU or GPU selection |
| `--input-file file` | Text or PDF file |

---

## 📁 Example Directory Structure

```
project/
│
├── local_summarizer.py
├── README.md
└── chapter.pdf
```

---

## 🧠 Recommended Models

### English:
- `facebook/bart-large-cnn` (Best quality)
- `sshleifer/distilbart-cnn-12-6` (Lightweight)

### Persian:
- `google/mt5-small` (Multilingual)
- Any Persian summarization model from HuggingFace

---

## 🛠 How It Works

1. Detects if input is TXT or PDF  
2. If PDF → Extracts text using `pdfplumber`  
3. Splits text into manageable chunks  
4. Summarizes each chunk  
5. Summarizes all summaries → final summary  

This ensures stable performance even on extremely large texts.

---

## 🧑‍💻 Contributing

You can:
- Add GUI (Tkinter / PySide)
- Add FastAPI web interface
- Add support for more languages

---

## 📜 License
This project is free to use and modify.

---

Enjoy your fast, offline chapter summarizer!
