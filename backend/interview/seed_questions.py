"""
Seed the question_bank table with 25 mock MCQ questions.
Topics: Python, SQL, Machine Learning, Data Structures.
Run: python -m interview.seed_questions
"""

import json
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "interview.db"

QUESTIONS = [
    # --- Python (7 questions) ---
    {"topic": "Python", "difficulty": "easy",
     "question": "What is the output of len([1, 2, 3])?",
     "options": ["2", "3", "4", "Error"], "correct_answer": "B"},
    {"topic": "Python", "difficulty": "easy",
     "question": "Which keyword is used to define a function in Python?",
     "options": ["func", "define", "def", "function"], "correct_answer": "C"},
    {"topic": "Python", "difficulty": "medium",
     "question": "What does `list(range(0, 10, 3))` return?",
     "options": ["[0,3,6,9]", "[0,3,6]", "[3,6,9]", "[0,1,2,3]"], "correct_answer": "A"},
    {"topic": "Python", "difficulty": "medium",
     "question": "Which of these is a mutable data type?",
     "options": ["tuple", "str", "list", "frozenset"], "correct_answer": "C"},
    {"topic": "Python", "difficulty": "hard",
     "question": "What is the time complexity of `in` for a Python set?",
     "options": ["O(n)", "O(1) average", "O(log n)", "O(n log n)"], "correct_answer": "B"},
    {"topic": "Python", "difficulty": "hard",
     "question": "What does `__slots__` do in a class?",
     "options": ["Limits methods", "Prevents dynamic attributes", "Adds type checking", "Enables async"],
     "correct_answer": "B"},
    {"topic": "Python", "difficulty": "medium",
     "question": "What is a generator in Python?",
     "options": ["A class factory", "A function using yield", "A decorator", "A metaclass"],
     "correct_answer": "B"},

    # --- SQL (7 questions) ---
    {"topic": "SQL", "difficulty": "easy",
     "question": "Which clause is used to filter rows in SQL?",
     "options": ["GROUP BY", "ORDER BY", "WHERE", "HAVING"], "correct_answer": "C"},
    {"topic": "SQL", "difficulty": "easy",
     "question": "What does SELECT DISTINCT do?",
     "options": ["Selects first row", "Removes duplicates", "Sorts results", "Limits output"],
     "correct_answer": "B"},
    {"topic": "SQL", "difficulty": "medium",
     "question": "Which JOIN returns rows even if there is no match in the right table?",
     "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "SELF JOIN"], "correct_answer": "B"},
    {"topic": "SQL", "difficulty": "medium",
     "question": "What is a CTE (Common Table Expression)?",
     "options": ["A stored procedure", "A temporary named result set", "An index type", "A trigger"],
     "correct_answer": "B"},
    {"topic": "SQL", "difficulty": "hard",
     "question": "Which window function returns the previous row's value?",
     "options": ["LEAD()", "LAG()", "RANK()", "NTILE()"], "correct_answer": "B"},
    {"topic": "SQL", "difficulty": "hard",
     "question": "What does HAVING clause filter on?",
     "options": ["Individual rows", "Aggregated groups", "Columns", "Subqueries"],
     "correct_answer": "B"},
    {"topic": "SQL", "difficulty": "medium",
     "question": "What does GROUP BY do?",
     "options": ["Sorts data", "Groups rows for aggregation", "Joins tables", "Filters nulls"],
     "correct_answer": "B"},

    # --- Machine Learning (6 questions) ---
    {"topic": "Machine Learning", "difficulty": "easy",
     "question": "What type of learning uses labeled data?",
     "options": ["Unsupervised", "Reinforcement", "Supervised", "Transfer"], "correct_answer": "C"},
    {"topic": "Machine Learning", "difficulty": "easy",
     "question": "Which metric is used for classification accuracy?",
     "options": ["RMSE", "MAE", "F1-Score", "R-squared"], "correct_answer": "C"},
    {"topic": "Machine Learning", "difficulty": "medium",
     "question": "What is overfitting?",
     "options": ["Model is too simple", "Model memorizes training data",
      "Model underfits test data", "Model has low variance"], "correct_answer": "B"},
    {"topic": "Machine Learning", "difficulty": "medium",
     "question": "Which algorithm is used for both classification and regression?",
     "options": ["Logistic Regression", "K-Means", "Random Forest", "Apriori"],
     "correct_answer": "C"},
    {"topic": "Machine Learning", "difficulty": "hard",
     "question": "What does the bias-variance tradeoff mean?",
     "options": ["More data = less error", "Reducing bias increases variance",
      "More features = better model", "Regularization increases bias and variance"],
     "correct_answer": "B"},
    {"topic": "Machine Learning", "difficulty": "hard",
     "question": "What is the purpose of cross-validation?",
     "options": ["Speed up training", "Estimate generalization error",
      "Reduce dataset size", "Select features"], "correct_answer": "B"},

    # --- Data Structures (5 questions) ---
    {"topic": "Data Structures", "difficulty": "easy",
     "question": "Which data structure uses FIFO ordering?",
     "options": ["Stack", "Queue", "Tree", "Graph"], "correct_answer": "B"},
    {"topic": "Data Structures", "difficulty": "easy",
     "question": "What is the time complexity of accessing an array element by index?",
     "options": ["O(n)", "O(1)", "O(log n)", "O(n^2)"], "correct_answer": "B"},
    {"topic": "Data Structures", "difficulty": "medium",
     "question": "Which traversal visits the root node first?",
     "options": ["Inorder", "Preorder", "Postorder", "Level-order"], "correct_answer": "B"},
    {"topic": "Data Structures", "difficulty": "medium",
     "question": "What is the worst-case time complexity of a hash table lookup?",
     "options": ["O(1)", "O(n)", "O(log n)", "O(n log n)"], "correct_answer": "B"},
    {"topic": "Data Structures", "difficulty": "hard",
     "question": "Which data structure is best for implementing a priority queue?",
     "options": ["Array", "Linked List", "Heap", "Stack"], "correct_answer": "C"},
]


def seed():
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    # Create table if not exists (idempotent)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS question_bank (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic       TEXT NOT NULL,
            difficulty  TEXT NOT NULL CHECK(difficulty IN ('easy','medium','hard')),
            question    TEXT NOT NULL,
            options     TEXT NOT NULL,
            correct_answer TEXT NOT NULL
        )
    """)

    # Only seed if empty (idempotent)
    count = conn.execute("SELECT COUNT(*) FROM question_bank").fetchone()[0]
    if count > 0:
        print(f"question_bank already has {count} rows — skipping seed.")
        conn.close()
        return

    for q in QUESTIONS:
        conn.execute(
            "INSERT INTO question_bank (topic, difficulty, question, options, correct_answer) VALUES (?, ?, ?, ?, ?)",
            (q["topic"], q["difficulty"], q["question"], json.dumps(q["options"]), q["correct_answer"]),
        )
    conn.commit()
    print(f"Seeded {len(QUESTIONS)} questions into question_bank.")
    conn.close()


if __name__ == "__main__":
    seed()
