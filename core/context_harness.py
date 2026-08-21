import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Banned keywords for basic guardrails
BANNED_KEYWORDS = [
    r"\bhack\b",
    r"\bexploit\b",
    r"\bddos\b",
    r"\bxóa\s+database\b",
    r"\bdrop\s+table\b",
    r"\bđánh\s+cắp\s+dữ\s+liệu\b",
    r"\blấy\s+trộm\s+thông\s+tin\b",
    r"\blàm\s+sao\s+để\s+tấn\s+công\b",
    r"\bhướng\s+dẫn\s+tấn\s+công\b",
    r"\bđịt\b", r"\blồn\b", r"\bcặc\b", # Basic profanity filter
]

def check_guardrails(query: str) -> bool:
    """
    Checks if the user's query violates any safety or policy constraints.
    Returns False if safe, True if violation found.
    """
    query_lower = query.lower()
    for pattern in BANNED_KEYWORDS:
        if re.search(pattern, query_lower):
            return True
    return False

def compress_context(query: str, documents: list[str], max_sentences: int = 5) -> str:
    """
    Compresses long documents into a concise summary by extracting 
    the most relevant sentences based on TF-IDF cosine similarity to the query.
    """
    if not documents:
        return ""
        
    # Split all documents into individual sentences
    all_sentences = []
    for doc in documents:
        # Simple sentence splitting (can be improved with NLTK/Spacy if needed)
        sentences = [s.strip() for s in re.split(r'[.!?\n]+', doc) if len(s.strip()) > 10]
        all_sentences.extend(sentences)
        
    if not all_sentences:
        return ""
        
    if len(all_sentences) <= max_sentences:
        return " ".join(all_sentences)
        
    # Use TF-IDF to find the most relevant sentences
    vectorizer = TfidfVectorizer()
    try:
        tfidf_matrix = vectorizer.fit_transform([query] + all_sentences)
        # Calculate similarity between query (index 0) and all sentences (index 1 onwards)
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        
        # Get top 'max_sentences' indices
        top_indices = similarities.argsort()[-max_sentences:][::-1]
        
        # Sort indices to maintain chronological order from original documents
        top_indices.sort()
        
        compressed = " ".join([all_sentences[i] for i in top_indices])
        return compressed
    except Exception as e:
        # Fallback to simple truncation if TF-IDF fails
        return " ".join(all_sentences[:max_sentences])
