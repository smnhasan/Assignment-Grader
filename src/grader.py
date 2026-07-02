import os
import re
import json
from openai import OpenAI

from src.indexer import BookIndexer
from src.config import OPENAI_API_KEY, MODEL
from src.utils import setup_logger, render_prompt, parse_json_markdown

logger = setup_logger("src.grader")


class AssignmentGrader:
    def __init__(self):
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = MODEL
        self.indexer = BookIndexer()
        self.indexer.get_or_create_index()

    def detect_prompt_injection(self, text):
        """Detects prompt injection attempts using regex and LLM checking."""
        logger.info("Running prompt injection check...")
        
        # 1. Quick regex check for common injection keywords
        injection_keywords = [
            r"ignore\s+(any|previous)?\s*instruction",
            r"ignore\s+(the)?\s*rubric",
            r"award\s+full\s+marks",
            r"give\s+full\s+marks",
            r"system\s*-\s*",
            r"write\s+only\s+positive\s+feedback",
            r"100/100"
        ]
        regex_match = False
        for pattern in injection_keywords:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Regex flagged prompt injection with pattern: {pattern}")
                regex_match = True
                break

        # 2. LLM validation check using Jinja template
        try:
            guard_prompt = render_prompt("detect_prompt_injection.j2", student_text=text)
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": guard_prompt}],
                max_completion_tokens=1000
            )
            raw_content = response.choices[0].message.content.strip()
            result = parse_json_markdown(raw_content)
            
            # Combine regex and LLM checks
            has_injection = regex_match or result.get("has_injection", False)
            reason = result.get("reason", "Regex pattern detected injection keywords.") if regex_match else result.get("reason", "")
            
            logger.info(f"Prompt injection result: has_injection={has_injection}, reason={reason}")
            return has_injection, reason
        except Exception as e:
            logger.error(f"Error in LLM prompt injection check: {e}")
            # Fallback to regex check
            return regex_match, "Regex check flagged keywords. LLM check failed."

    def split_questions(self, text):
        """Splits the student answer text into answers for Q1, Q2, Q3, Q4, and Q5."""
        logger.info("Splitting student text into Q1-Q5...")
        q_dict = {"Q1": "", "Q2": "", "Q3": "", "Q4": "", "Q5": ""}
        
        patterns = [
            r"(?:Q1|Question\s*1)[:\.\s-]",
            r"(?:Q2|Question\s*2)[:\.\s-]",
            r"(?:Q3|Question\s*3)[:\.\s-]",
            r"(?:Q4|Question\s*4)[:\.\s-]",
            r"(?:Q5|Question\s*5)[:\.\s-]"
        ]
        
        indices = []
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                indices.append((match.start(), match.end()))
            else:
                indices.append((-1, -1))
                
        valid_indices = [idx for idx in indices if idx[0] != -1]
        
        if len(valid_indices) >= 3:
            found_questions = []
            for i, idx in enumerate(indices):
                if idx[0] != -1:
                    found_questions.append((i+1, idx[0], idx[1]))
            
            found_questions.sort(key=lambda x: x[1])
            
            for idx in range(len(found_questions)):
                q_num, start_idx, end_idx = found_questions[idx]
                next_start = len(text)
                if idx + 1 < len(found_questions):
                    next_start = found_questions[idx + 1][1]
                
                q_text = text[end_idx:next_start].strip()
                q_dict[f"Q{q_num}"] = q_text
        else:
            logger.info("Text is not structured with clear Q1-Q5 headers. Treating as single block.")
            q_dict["Q1"] = text
            
        return q_dict

    def grade_assignment(self, student_name, student_text):
        """Grades a student assignment by searching the book, analyzing answers, and checking the draft."""
        logger.info(f"Starting grading for {student_name}...")
        
        # 1. Check for prompt injection
        has_injection, injection_reason = self.detect_prompt_injection(student_text)
        
        # 2. Split student text
        q_answers = self.split_questions(student_text)
        
        # 3. Retrieve context for each question
        queries = {
            "Q1": "coefficient of determination R2 score meaning negative close to 0 1",
            "Q2": "Ridge Lasso ElasticNet regularization penalty norm L1 L2 weight shrink sparsity",
            "Q3": "RANSAC linear regression outliers inliers random sample consensus",
            "Q4": "logistic regression classification sigmoid function probability mapping",
            "Q5": "scikit-learn LogisticRegression parameter C inverse regularization strength larger smaller"
        }
        
        retrieved_context = {}
        for q_key, query in queries.items():
            logger.info(f"Retrieving book context for {q_key}...")
            search_results = self.indexer.search(query, k=4)
            retrieved_context[q_key] = search_results

        # Format context for prompt
        formatted_context = ""
        for q_key, chunks in retrieved_context.items():
            formatted_context += f"=== TEXTBOOK CONTEXT FOR {q_key} ===\n"
            for c in chunks:
                formatted_context += f"[Page {c['page']}] (Score: {c['score']:.3f}): {c['text']}\n\n"

        # 4. Draft grading stage (Agent) using Jinja template
        logger.info("Running draft grading agent...")
        try:
            draft_prompt = render_prompt(
                "draft_grading.j2",
                student_name=student_name,
                q_answers=q_answers,
                formatted_context=formatted_context
            )
            draft_response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": draft_prompt}],
                max_completion_tokens=4000
            )
            raw_draft = draft_response.choices[0].message.content.strip()
            draft_report = parse_json_markdown(raw_draft)
        except Exception as e:
            logger.error(f"Error in draft grading: {e}")
            draft_report = {
                "criteria": {},
                "total_score": 0,
                "feedback": f"Error generating draft grade: {e}",
                "flags": ["ERROR in drafting"]
            }

        # 5. Checker / Reviewer stage (Critic) using Jinja template
        logger.info("Running checker/critic stage...")
        try:
            checker_prompt = render_prompt(
                "checker_auditing.j2",
                student_name=student_name,
                q_answers=q_answers,
                formatted_context=formatted_context,
                draft_report_json=json.dumps(draft_report, indent=2),
                has_injection=has_injection,
                injection_reason=injection_reason
            )
            checker_response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": checker_prompt}],
                max_completion_tokens=4000
            )
            raw_final = checker_response.choices[0].message.content.strip()
            final_report = parse_json_markdown(raw_final)
            logger.info(f"Grading completed successfully for {student_name}. Total Score: {final_report.get('total_score')}")
            return final_report
        except Exception as e:
            logger.error(f"Error in checker stage: {e}")
            draft_report["metadata"] = {
                "student_name": student_name,
                "has_injection": has_injection,
                "injection_reason": injection_reason
            }
            draft_report["flags"].append(f"Auditor warning: Checker step failed to execute ({e}).")
            return draft_report

    def report_to_markdown(self, report):
        """Converts the JSON report structure into a clean, human-readable Markdown format."""
        meta = report.get("metadata", {})
        student = meta.get("student_name", "Student")
        total = report.get("total_score", 0)
        feedback = report.get("feedback", "")
        flags = report.get("flags", [])
        
        # Calculate total max score from criteria
        criteria = report.get("criteria", {})
        total_max = sum(data.get("max_score", 0) for data in criteria.values())
        if total_max == 0:
            total_max = 100
            
        md = f"# Grading Report - {student}\n\n"
        md += f"**Overall Score:** `{total}/{total_max}`\n\n"
        
        md += "## Criterion Breakdown\n\n"
        for name, data in criteria.items():
            display_name = name.replace("_", " ").title()
            score = data.get("score", 0)
            max_score = data.get("max_score", 0)
            justification = data.get("justification", "No justification provided.")
            refs = ", ".join(data.get("references", []))
            
            md += f"### {display_name} ({score}/{max_score})\n"
            md += f"**Justification:** {justification}\n"
            if refs:
                md += f"**Book References:** {refs}\n"
            md += "\n"
            
        md += "## Overall Feedback\n"
        md += f"{feedback}\n\n"
        
        if flags:
            md += "## ⚠️ Warning Flags / Flags\n"
            for f in flags:
                md += f"- {f}\n"
            md += "\n"
        else:
            md += "## ⚠️ Warning Flags\n*No warning flags detected. Answers align with the textbook.*\n"
            
        return md

    def extract_questions_and_rubric(self, questions_text):
        """Analyzes questions/rubric text and identifies individual questions and grading criteria/rubric."""
        logger.info("Extracting questions and rubric dynamically using LLM...")
        try:
            prompt = render_prompt("extract_questions_and_rubric.j2", questions_text=questions_text)
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=2000
            )
            raw_content = response.choices[0].message.content.strip()
            return parse_json_markdown(raw_content)
        except Exception as e:
            logger.error(f"Error extracting questions and rubric: {e}")
            return {
                "rubric": {
                    "correctness": { "max_score": 40, "description": "Answers are factually correct according to the book." },
                    "completeness": { "max_score": 25, "description": "All questions are answered." },
                    "evidence": { "max_score": 20, "description": "Answers use evidence/references from the book." },
                    "clarity": { "max_score": 15, "description": "Clear and well-structured response." }
                },
                "questions": [
                    { "id": "Q1", "text": "Q1", "search_query": "question keywords" }
                ]
            }

    def map_student_answers(self, student_text, questions):
        """Maps the student's submission text to the extracted questions using LLM."""
        logger.info("Mapping student answers to questions dynamically using LLM...")
        questions_formatted = ""
        for q in questions:
            questions_formatted += f"- {q['id']}: {q['text']}\n"
            
        try:
            prompt = render_prompt(
                "map_student_answers.j2",
                questions_formatted=questions_formatted,
                student_text=student_text
            )
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=2000
            )
            raw_content = response.choices[0].message.content.strip()
            result = parse_json_markdown(raw_content)
            return result.get("answers", {})
        except Exception as e:
            logger.error(f"Error mapping student answers: {e}")
            return {}

    def grade_assignment_dynamic(self, student_name, student_text, book_path, questions_text):
        """Grades a student assignment dynamically by indexing the uploaded book and parsing the questions."""
        logger.info(f"Starting dynamic grading for {student_name}...")
        
        # 1. Compute book hash and get or create index
        import hashlib
        hasher = hashlib.md5()
        with open(book_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()
        
        dynamic_save_dir = f"data/faiss_index_{file_hash}"
        logger.info(f"Using dynamic index directory: {dynamic_save_dir} (file hash: {file_hash})")
        
        dynamic_indexer = BookIndexer(book_path=book_path, save_dir=dynamic_save_dir)
        dynamic_indexer.get_or_create_index()
        
        # 2. Extract questions and rubric
        questions_data = self.extract_questions_and_rubric(questions_text)
        questions = questions_data.get("questions", [])
        rubric = questions_data.get("rubric", {
            "correctness": { "max_score": 40, "description": "Answers are factually correct according to the book." },
            "completeness": { "max_score": 25, "description": "All questions are answered." },
            "evidence": { "max_score": 20, "description": "Answers use evidence/references from the book." },
            "clarity": { "max_score": 15, "description": "Clear and well-structured response." }
        })
        
        # 3. Check for prompt injection
        has_injection, injection_reason = self.detect_prompt_injection(student_text)
        
        # 4. Map student answers
        student_answers = self.map_student_answers(student_text, questions)
        
        # 5. Retrieve textbook context for each question
        retrieved_context = {}
        for q in questions:
            q_id = q["id"]
            query = q["search_query"]
            logger.info(f"Retrieving book context for {q_id} using query: '{query}'...")
            search_results = dynamic_indexer.search(query, k=4)
            retrieved_context[q_id] = search_results

        # Format context for prompt
        formatted_context = ""
        for q in questions:
            q_id = q["id"]
            chunks = retrieved_context.get(q_id, [])
            formatted_context += f"=== TEXTBOOK CONTEXT FOR {q_id} ===\n"
            for c in chunks:
                formatted_context += f"[Page {c['page']}] (Score: {c['score']:.3f}): {c['text']}\n\n"

        # Format student answers for prompt
        formatted_answers = ""
        for q in questions:
            q_id = q["id"]
            q_text = q["text"]
            ans_text = student_answers.get(q_id, "Not answered.")
            formatted_answers += f"Question {q_id}: {q_text}\nStudent Answer: {ans_text}\n\n"

        # Construct rubric description and keys
        rubric_description = ""
        total_marks = 0
        for criterion, data in rubric.items():
            max_score = data.get("max_score", 0)
            desc = data.get("description", "")
            rubric_description += f"- {criterion.replace('_', ' ').title()} ({max_score} marks): {desc}\n"
            total_marks += max_score

        # 6. Draft grading stage (Agent) using Jinja template
        logger.info("Running draft grading agent...")
        try:
            criteria_keys = list(rubric.keys())
            draft_prompt = render_prompt(
                "dynamic_draft_grading.j2",
                student_name=student_name,
                formatted_answers=formatted_answers,
                formatted_context=formatted_context,
                total_marks=total_marks,
                rubric_description=rubric_description,
                criteria_keys=criteria_keys,
                rubric=rubric
            )
            
            draft_response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": draft_prompt}],
                max_completion_tokens=4000
            )
            raw_draft = draft_response.choices[0].message.content.strip()
            draft_report = parse_json_markdown(raw_draft)
        except Exception as e:
            logger.error(f"Error in draft grading: {e}")
            draft_report = {
                "criteria": {},
                "total_score": 0,
                "feedback": f"Error generating draft grade: {e}",
                "flags": ["ERROR in drafting"]
            }

        # 7. Checker / Reviewer stage (Critic) using Jinja template
        logger.info("Running checker/critic stage...")
        try:
            checker_prompt = render_prompt(
                "dynamic_checker_auditing.j2",
                formatted_answers=formatted_answers,
                formatted_context=formatted_context,
                draft_report_json=json.dumps(draft_report, indent=2),
                has_injection=has_injection,
                injection_reason=injection_reason,
                student_name=student_name,
                rubric=rubric
            )
            
            checker_response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": checker_prompt}],
                max_completion_tokens=4000
            )
            raw_final = checker_response.choices[0].message.content.strip()
            final_report = parse_json_markdown(raw_final)
            logger.info(f"Grading completed successfully for {student_name}. Total Score: {final_report.get('total_score')}")
            return final_report
        except Exception as e:
            logger.error(f"Error in checker stage: {e}")
            draft_report["metadata"] = {
                "student_name": student_name,
                "has_injection": has_injection,
                "injection_reason": injection_reason
            }
            draft_report["flags"].append(f"Auditor warning: Checker step failed to execute ({e}).")
            return draft_report
