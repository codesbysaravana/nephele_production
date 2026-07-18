Phase 3: The Intelligence Layer (Agentic AI)
You have successfully built the fastest Voice Pipeline possible. Nephele can hear, think, and speak in real-time. But right now, she is amnesiac—she doesn't remember past conversations, and she has no access to external data.

It is time to execute Phase 3: Transforming Nephele into a Full Agent with Machine Learning (RAG), SQL Data Warehousing, and Long-Term Memory.

User Review Required
IMPORTANT

The Latency Tradeoff: Giving an AI "Agency" (the ability to use tools and search databases) naturally adds latency to the conversation. If Nephele has to search a database before speaking, she cannot reply in <1 second. To mitigate this, we will build a custom Asynchronous Tool-Calling Loop rather than using slow, bloated frameworks like LangChain.

Open Questions
TIP

SQL Database: For the structured Data Warehousing (user data, logs, facts), do you want to start with a lightweight local SQLite database, or do you want me to wire up a production PostgreSQL instance?
RAG / Unstructured Data: We planned to use ChromaDB for semantic search (PDFs, text files). Do you want to implement this locally, or use a cloud vector database like Pinecone?
Proposed Architecture (The Agent Loop)
We will upgrade backend/ai_services/openai.py to support OpenAI Function Calling (Tools).

1. Short-Term & Long-Term Memory
Short-Term: We will implement a rolling memory window (saving the last 10 messages) so she remembers the context of the current conversation.
Long-Term: We will create a save_memory SQL tool. If you tell her an important fact ("My dog's name is Max"), she will autonomously choose to save it to the SQL database.
2. SQL / Data Warehousing Tool
We will provide Nephele with a query_database tool.
If you ask her for metrics or past records, she will write SQL, execute it against your database, read the results, and speak the answer back to you.
3. RAG / Vector Database Tool (Machine Learning)
We will integrate ChromaDB.
We will provide Nephele with a semantic_search tool. If you ask her a complex question requiring domain knowledge, she will search ChromaDB, retrieve the embedded context, and synthesize an answer.
Workflow
When you speak to Nephele:

Deepgram transcribes your voice.
The transcript goes to the LLM.
The LLM decides: Can I answer this immediately, or do I need to search my SQL/Chroma database?
If she needs to search, she executes the Python tool, retrieves the data, and then streams her audio response.
Verification Plan
Install chromadb, sqlalchemy, and pydantic.
Restructure openai.py to handle the tool_calls finish reason.
Test by telling Nephele a fact, letting her save it to SQL, and then asking her about it later.