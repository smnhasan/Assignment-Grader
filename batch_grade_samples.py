import os
import json
import logging
from pypdf import PdfReader
from src.grader import AssignmentGrader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("batch_grader")

def extract_pdf_text(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    reader = PdfReader(pdf_path)
    text = ""
    for idx, page in enumerate(reader.pages):
        text += page.extract_text() or ""
    return text

def main():
    grader = AssignmentGrader()
    
    assignments_dir = os.path.join(os.path.dirname(__file__), "assignments")
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    students = {
        "Student A": "student_A.pdf",
        "Student B": "student_B.pdf",
        "Student C": "student_C.pdf"
    }
    
    summary = []
    
    for name, filename in students.items():
        pdf_path = os.path.join(assignments_dir, filename)
        logger.info(f"Processing {name} ({filename})...")
        
        try:
            student_text = extract_pdf_text(pdf_path)
            
            # Grade
            report = grader.grade_assignment(name, student_text)
            
            # Save JSON report
            json_filename = f"{filename.replace('.pdf', '')}_report.json"
            json_path = os.path.join(reports_dir, json_filename)
            with open(json_path, "w") as f:
                json.dump(report, f, indent=2)
                
            # Save Markdown report
            md_filename = f"{filename.replace('.pdf', '')}_report.md"
            md_path = os.path.join(reports_dir, md_filename)
            md_content = grader.report_to_markdown(report)
            with open(md_path, "w") as f:
                f.write(md_content)
                
            logger.info(f"Saved reports for {name} to {reports_dir}")
            
            summary.append({
                "student": name,
                "score": report.get("total_score", 0),
                "correctness": report.get("criteria", {}).get("correctness", {}).get("score", 0),
                "completeness": report.get("criteria", {}).get("completeness", {}).get("score", 0),
                "evidence": report.get("criteria", {}).get("evidence", {}).get("score", 0),
                "clarity": report.get("criteria", {}).get("clarity", {}).get("score", 0),
                "flags_count": len(report.get("flags", [])),
                "has_injection": report.get("metadata", {}).get("has_injection", False)
            })
            
        except Exception as e:
            logger.error(f"Failed to grade {name}: {e}")
            
    # Write batch summary report
    summary_path = os.path.join(reports_dir, "batch_summary.md")
    with open(summary_path, "w") as f:
        f.write("# Batch Grading Summary\n\n")
        f.write("| Student | Total Score | Correctness (40) | Completeness (25) | Evidence (20) | Clarity (15) | Warning Flags | Injection Attempt |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|:---:|\n")
        for s in summary:
            f.write(f"| {s['student']} | **{s['score']}** | {s['correctness']} | {s['completeness']} | {s['evidence']} | {s['clarity']} | {s['flags_count']} | {'Yes ⚠️' if s['has_injection'] else 'No'} |\n")
        
        f.write("\n## Student Report Details\n")
        for name, filename in students.items():
            base = filename.replace('.pdf', '')
            f.write(f"- [{name} Report]({base}_report.md)\n")
            
    logger.info("Batch grading process completed successfully.")

if __name__ == "__main__":
    main()
