# AI Assignment Grader

An automated, retrieval-augmented (RAG) agentic grader built to grade student assignments against a provided course textbook. The system incorporates **iterative retrieval**, **prompt-injection protection**, **auditor-based checking**, and a **polished Gradio web interface**.

---

## 🚀 Key Features

1. **Modular Configuration & Logging (`src/config.py`, `src/utils.py`)**
   * Config constants (API keys, models) are centralized in `src/config.py`.
   * Standard utilities like robust JSON parsing, dual console-file logger, and Jinja2 prompt rendering are isolated in `src/utils.py`.

2. **Jinja2 Prompt Templating (`src/prompts/`)**
   * All system prompts are separated from application code and stored as modular Jinja2 templates (`.j2`), allowing quick editing without restarting or modifying logic.

3. **Textbook Vector Indexing (`src/indexer.py`)**
   * Extracts page-by-page text from textbooks using `pypdf`.
   * Chunks text with overlap and indexes using **FAISS vector database** with cosine similarity.
   * Employs MD5-based textbook hashing to save/cache FAISS index directories dynamically.

4. **Agentic Grading Pipeline (`src/grader.py`)**
   * **Prompt Injection Checker**: Scans student answers using regex and an LLM guardrail classifier to prevent rubric overrides.
   * **Iterative Grading Agent**: Tailors semantic searches to retrieve specific textbook pages for each question.
   * **Auditor/Reviewer Critic**: Performs an agent-critic review to double-check score validity, find contradictions, deduct marks for injection attempts, and assign warning flags.

5. **Dynamic PDF Grading Tab & Web UI (`app.py`)**
   * **Tab 1: Upload & Grade PDFs** - Grade *any* student submission dynamically. Upload the textbook, questions/rubric, and the student's submission PDF.
   * **Tab 2: Individual Grader** - Grades individual static ML answers.
   * **Tab 3: Batch Summary Dashboard** - Compares all student grades in a side-by-side table.
   * **Tab 4: Textbook Vector Search** - Queries FAISS textbook index directly to see text matches.
   * **Tab 5: System Logs** - Views real-time logs (`logs/grader.log`).

---

## 📁 Project Structure

```
├── app.py                      # Gradio web application
├── batch_grade_samples.py      # Script to batch grade student A, B, C
├── run.sh                      # Shell script to auto-restart the server on port 7860
├── assignments/                # Sample student PDF submissions (A, B, C)
├── book/                       # Course textbook excerpt PDF
├── data/                       # FAISS index files and cache folders
├── logs/                       # System logs directory
├── reports/                    # Generated Markdown and JSON grade reports
├── src/                        # Codebase source folder
│   ├── __init__.py             # Package initializer
│   ├── config.py               # Consolidated environment and configuration settings
│   ├── utils.py                # Shared utilities (logging, JSON parser, Jinja2 renderer)
│   ├── indexer.py              # Textbook text extraction and FAISS vector indexing
│   ├── grader.py               # Agentic grading, critic, and injection protection
│   └── prompts/                # Separate folder for Jinja2 prompt templates
│       ├── detect_prompt_injection.j2
│       ├── draft_grading.j2
│       ├── checker_auditing.j2
│       ├── extract_questions_and_rubric.j2
│       ├── map_student_answers.j2
│       ├── dynamic_draft_grading.j2
│       └── dynamic_checker_auditing.j2
├── rubric.md                   # Static grading criteria & guidance
├── assignment.md               # Static assignment questions
├── .env.example                # Example environment file
└── README.md                   # Project documentation
```

---

## 📊 Summary of Student Grades

| Student | Total Score | Correctness (40) | Completeness (25) | Evidence (20) | Clarity (15) | Warning Flags | Injection Attempt |
|---|---:|---:|---:|---:|---:|---:|:---:|
| **Student A** | **93** | 36 | 25 | 19 | 13 | 1 | No |
| **Student B** | **74** | 34 | 16 | 13 | 13 | 1 | No |
| **Student C** | **41** | 14 | 10 | 7 | 10 | 6 | **Yes ⚠️** |

* **Student A:** High-quality answers corresponding to the book.
* **Student B:** Briefly correct, but incomplete answers lacking required details.
* **Student C:** Incorrect definitions along with a prompt injection attempt. The grader successfully bypassed the injection, penalized clarity/evidence, and flagged the errors.

---

## 🛠️ How to Run Locally

### 1. Set Up Environment
Configure your `.env` file based on `.env.example`:
```bash
OPENAI_API_KEY=your-api-key-here
MODEL=gpt-5.4-nano
EMBEDDING_MODEL=text-embedding-3-small
```

### 2. Run Batch Grading
Grade the three sample student files and write reports to disk:
```bash
/home/nahid/anaconda3/envs/assessment-env/bin/python3 batch_grade_samples.py
```

### 3. Run the Web App
Start or restart the Gradio web interface (this will stop any previous server running on port 7860):
```bash
./run.sh
```
Open your browser and navigate to `http://localhost:7860`.
