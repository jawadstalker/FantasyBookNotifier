import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -------------------------------------------------------
# STEP 1 — Load the dataset from your local files
# -------------------------------------------------------
books_path = "Books.csv"   # <-- change this

books = pd.read_csv(books_path, on_bad_lines="skip", encoding="latin-1")

# Only keep needed fields
books = books[["Book-Title", "Book-Author", "Publisher"]]
books = books.dropna()

# Create a description field for NLP
books["description"] = (
    books["Book-Title"].astype(str) + " " +
    books["Book-Author"].astype(str) + " " +
    books["Publisher"].astype(str)
)

# -------------------------------------------------------
# STEP 2 — Build TF-IDF model
# -------------------------------------------------------
tfidf = TfidfVectorizer(stop_words="english")
tfidf_matrix = tfidf.fit_transform(books["description"])

print("TF-IDF model created. Matrix size:", tfidf_matrix.shape)

# -------------------------------------------------------
# STEP 3 — Ask user for keywords
# -------------------------------------------------------
keywords = input("Enter five keywords (space-separated): ")

keywords_vec = tfidf.transform([keywords])
similarities = cosine_similarity(keywords_vec, tfidf_matrix).flatten()

# -------------------------------------------------------
# STEP 4 — Get top 3 recommendations
# -------------------------------------------------------
top_indices = similarities.argsort()[-3:][::-1]

print("\n📚 Top 3 Book Recommendations:\n")

for idx in top_indices:
    print("Title:", books.iloc[idx]["Book-Title"])
    print("Author:", books.iloc[idx]["Book-Author"])
    print("Publisher:", books.iloc[idx]["Publisher"])
    print("Score:", round(similarities[idx], 3))
    print("-" * 40)
