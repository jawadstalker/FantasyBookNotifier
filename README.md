# FantasyBookNotifier

<img src="logo.png" alt="FantasyBookNotifier Banner" width="200"/>

## 📚 Overview

**FantasyBookNotifier** is a Python automation tool that scrapes the latest fantasy books from multiple publishers, downloads their cover images, saves book data as JSON, and sends a visually rich email notification with embedded images. This project is ideal for book enthusiasts, reviewers, or anyone eager to stay updated with new fantasy releases.

---

## 🚀 Features

* Scrapes books from multiple publishers:

  * **Baazh Book**
  * **Porteghaal**
  * **Tandis Pub**
  * **Tor Books**
  * **DAW Books**
  * **Fantasy Literature**
* Extracts:

  * Book title
  * Author (if available)
  * Price
  * Cover image
  * Link to the book
* Downloads cover images automatically.
* Saves all book data to `all_books.json`.
* Sends an HTML email with:

  * Embedded book images
  * Book title, publisher, and price
  * Clickable links to the book pages
* Limits the number of books per publisher to avoid spam.
* Handles dynamically loaded websites using **Playwright**.
* Supports automatic image resizing in the email for consistent display.

---

## 💻 Requirements

* Python 3.10+
* Packages:

  ```bash
  pip install playwright aiohttp
  playwright install
  ```
* A Gmail account (or any SMTP-enabled email) for sending notifications.

---

## ⚡ How It Works

1. **Web Scraping:**
   The script uses **Playwright** to open each publisher's website and extract the latest books. It intelligently selects the best quality image from `srcset` attributes if available.

2. **Data Processing:**
   Book information is organized into a list of dictionaries and saved as JSON (`all_books.json`). Each publisher is limited to a configurable number of books.

3. **Image Downloading:**
   All book cover images are downloaded into the `book_images` folder. Images are named safely for file systems.

4. **Email Generation:**

   * The script generates an HTML email with embedded images (`cid`) and styled layout for readability.
   * Images are resized for consistent display in email clients.

5. **Email Sending:**

   * Uses SMTP to send the email to the designated recipient.
   * Email includes book title, publisher, price, and a clickable link for each book.

---

## 🛠️ Configuration

Set your email credentials at the top of the script:

```python
SENDER_EMAIL = "your_email@gmail.com"
APP_PASSWORD = "your_app_password"
RECEIVER_EMAIL = "recipient_email@gmail.com"
```

> **Note:** Use an App Password for Gmail for enhanced security.

---

## 📂 Folder Structure

```
FantasyBookNotifier/
│
├─ book_images/        # Downloaded book covers
├─ all_books.json      # JSON file containing all scraped books
├─ main.py             # Main Python script
└─ README.md
```

---

## 🔧 How to Run

```bash
python main.py
```

* The script will scrape all configured sites.
* Download book cover images.
* Save JSON data.
* Send an HTML email notification.

---

## 📬 Example Email Layout

* Embedded book cover images
* Book title & publisher
* Price information
* Direct link to the book

All images are automatically resized to display properly in most email clients.

---

## 📝 License

This project is released under the **MIT License**. You are free to use and modify it for personal or educational purposes.

---

## 💡 Future Enhancements

* Support additional publishers
* Add filtering by genre or author
* Schedule automatic daily/weekly email updates
* Improve error handling and logging
* Store historical book data for trend analysis
