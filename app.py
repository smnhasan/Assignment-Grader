import os
import json
import logging
import pandas as pd
import gradio as gr
from pypdf import PdfReader
from src.grader import AssignmentGrader
from src.indexer import BookIndexer

# Setup logging
logger = logging.getLogger("app")

# Initialize grader and indexer
grader = AssignmentGrader()
indexer = BookIndexer()

def extract_pdf_text(pdf_path):
    if not os.path.exists(pdf_path):
        return ""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
        return f"Error reading PDF: {e}"

def load_student_data(student_name):
    """Loads student PDF text to populate the input box."""
    if student_name == "Student A":
        return extract_pdf_text("assignments/student_A.pdf")
    elif student_name == "Student B":
        return extract_pdf_text("assignments/student_B.pdf")
    elif student_name == "Student C":
        return extract_pdf_text("assignments/student_C.pdf")
    else:
        return ""

def grade_handler(student_name, student_text):
    """Grades the student assignment and returns HTML score card, markdown report, and warning list."""
    if not student_text.strip():
        return (
            "<div style='color: red;'>Please enter the student's answer or select a sample student first.</div>",
            "### No report generated.",
            "Please select a student and click Grade."
        )
    
    logger.info(f"UI triggered grading for: {student_name}")
    try:
        # Run grader
        report = grader.grade_assignment(student_name, student_text)
        
        # Save results locally to reports folder
        os.makedirs("reports", exist_ok=True)
        safe_name = student_name.replace(" ", "_")
        
        with open(f"reports/{safe_name}_report.json", "w") as f:
            json.dump(report, f, indent=2)
            
        md_content = grader.report_to_markdown(report)
        with open(f"reports/{safe_name}_report.md", "w") as f:
            f.write(md_content)
        
        # Build HTML score card
        score = report.get("total_score", 0)
        
        if score >= 80:
            color1, color2 = "#15803d", "#22c55e" # green
            status = "Excellent / Pass"
        elif score >= 60:
            color1, color2 = "#b45309", "#f59e0b" # yellow/orange
            status = "Pass with feedback"
        else:
            color1, color2 = "#b91c1c", "#ef4444" # red
            status = "Needs Improvement"
            
        score_card_html = f"""
        <div style="background: linear-gradient(135deg, {color1}, {color2}); color: white; padding: 25px; border-radius: 16px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3); margin-bottom: 20px;">
            <h3 style="margin: 0; font-size: 1.2em; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.05em;">Grading Complete</h3>
            <h1 style="margin: 10px 0; font-size: 3.5em; font-weight: 800; line-height: 1;">{score} <span style="font-size: 0.4em; font-weight: 400; opacity: 0.8;">/ 100</span></h1>
            <p style="margin: 0; font-size: 1.1em; font-weight: 600; letter-spacing: 0.02em;">{status}</p>
        </div>
        """
        
        # Build individual criteria bars
        criteria = report.get("criteria", {})
        score_card_html += "<div style='background: rgba(30, 41, 59, 0.5); padding: 15px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.1);'>"
        score_card_html += "<h4 style='margin: 0 0 10px 0; color: #94a3b8; font-size: 0.9em; text-transform: uppercase;'>Criterion Breakdown</h4>"
        
        for key, data in criteria.items():
            c_score = data.get("score", 0)
            c_max = data.get("max_score", 100)
            pct = (c_score / c_max) * 100 if c_max > 0 else 0
            display_name = key.replace("_", " ").title()
            
            score_card_html += f"""
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 4px;">
                    <span style="font-weight: 500; color: #e2e8f0;">{display_name}</span>
                    <span style="font-weight: bold; color: #e2e8f0;">{c_score}/{c_max}</span>
                </div>
                <div style="background: #334155; height: 8px; border-radius: 4px; overflow: hidden;">
                    <div style="background: #3b82f6; width: {pct}%; height: 100%; border-radius: 4px;"></div>
                </div>
            </div>
            """
        score_card_html += "</div>"
        
        # Build Warning Flags Section
        flags = report.get("flags", [])
        flags_html = ""
        if flags:
            flags_html += "<div style='margin-top: 20px;'>"
            flags_html += "<h4 style='color: #ef4444; font-weight: bold; font-size: 1.1em; margin-bottom: 10px;'>⚠️ Warning Flags / Auditing Alerts</h4>"
            for f in flags:
                is_crit = "Critical" in f or "injection" in f.lower()
                border_col = "#ef4444" if is_crit else "#f97316"
                bg_col = "rgba(239, 68, 68, 0.1)" if is_crit else "rgba(249, 115, 22, 0.1)"
                txt_col = "#fca5a5" if is_crit else "#fed7aa"
                
                flags_html += f"""
                <div style="border-left: 4px solid {border_col}; background: {bg_col}; padding: 12px; border-radius: 0 8px 8px 0; margin-bottom: 10px; font-size: 0.9em; color: {txt_col};">
                    {f}
                </div>
                """
            flags_html += "</div>"
        else:
            flags_html += """
            <div style="margin-top: 20px; border-left: 4px solid #10b981; background: rgba(16, 185, 129, 0.1); padding: 12px; border-radius: 0 8px 8px 0; font-size: 0.9em; color: #a7f3d0;">
                All claims factually align with textbook content. No warnings flagged.
            </div>
            """
            
        return score_card_html, md_content, flags_html
        
    except Exception as e:
        logger.error(f"Grading error: {e}")
        return (
            f"<div style='color: red;'>Error during grading: {e}</div>",
            "### Grading failed due to an error.",
            f"Error details: {e}"
        )

def run_batch_grading():
    """Reads saved reports or triggers grading and returns markdown summary table."""
    logger.info("UI triggered Batch Grading Dashboard view")
    reports_dir = "reports"
    summary_path = os.path.join(reports_dir, "batch_summary.md")
    
    if os.path.exists(summary_path):
        with open(summary_path, "r") as f:
            summary_content = f.read()
        return summary_content
    else:
        return "### No batch reports found. Run `python3 batch_grade_samples.py` first to pre-grade."

def search_textbook(query, k):
    """Searches textbook and formats results into clear table."""
    if not query.strip():
        return pd.DataFrame(columns=["Page", "Relevance Score", "Matching Textbook Context Excerpt"])
    
    logger.info(f"UI book search query: '{query}' (K={k})")
    try:
        results = indexer.search(query, k=int(k))
        data = []
        for r in results:
            data.append({
                "Page": f"Page {r['page']}",
                "Relevance Score": f"{r['score']:.4f}",
                "Matching Textbook Context Excerpt": r['text']
            })
        return pd.DataFrame(data)
    except Exception as e:
        logger.error(f"Book search error: {e}")
        return pd.DataFrame([{"Error": str(e)}])

def get_logs():
    """Reads system log file and returns it."""
    log_path = "logs/grader.log"
    if not os.path.exists(log_path):
        return "No logs found yet."
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        # Return last 150 lines
        return "".join(lines[-150:])
    except Exception as e:
        return f"Error reading logs: {e}"

# Build Gradio UI
with gr.Blocks(
    title="AI Assignment Grader"
) as demo:

    gr.HTML("""
    <div style="text-align: center; padding: 25px 0 15px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
        <h1 style="margin: 0; font-size: 2.8em; font-weight: 800; background: linear-gradient(to right, #3b82f6, #60a5fa); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">AI Assignment Grader</h1>
        <p style="margin: 5px 0 0 0; font-size: 1.1em; color: #94a3b8;">Automated retrieval-augmented assignment evaluation system with multi-agent critic</p>
    </div>
    """)
    
    with gr.Tabs():
        
        # TAB 1: GRADER
        with gr.Tab("Individual Grader"):
            gr.Markdown("### Submit and grade individual student answers")
            
            with gr.Row():
                with gr.Column(scale=4):
                    student_dropdown = gr.Dropdown(
                        choices=["Custom Input", "Student A", "Student B", "Student C"],
                        value="Custom Input",
                        label="Choose Student / Sample Answer"
                    )
                    
                    student_name_input = gr.Textbox(
                        value="Custom Student",
                        label="Student Name / Identifier",
                        placeholder="Enter student name..."
                    )
                    
                    student_text_input = gr.Textbox(
                        lines=15,
                        label="Student Submission Text",
                        placeholder="Paste student answers here...",
                        elem_id="student_text_area"
                    )
                    
                    # Dropdown handler to automatically populate text
                    def dropdown_handler(choice):
                        text = load_student_data(choice)
                        name = choice if choice != "Custom Input" else "Custom Student"
                        return text, name
                        
                    student_dropdown.change(
                        fn=dropdown_handler,
                        inputs=[student_dropdown],
                        outputs=[student_text_input, student_name_input]
                    )
                    
                    grade_btn = gr.Button("Grade Submission", variant="primary", elem_classes=["primary"])
                    
                with gr.Column(scale=5):
                    gr.Markdown("### Grading Result")
                    score_card = gr.HTML("<div style='text-align: center; color: #64748b; padding: 40px;'>Click 'Grade Submission' to view the evaluation results.</div>")
                    flags_card = gr.HTML("")
                    
                    with gr.Accordion("Full Markdown Report", open=False):
                        markdown_report = gr.Markdown("The report will appear here.")
                        
            grade_btn.click(
                fn=grade_handler,
                inputs=[student_name_input, student_text_input],
                outputs=[score_card, markdown_report, flags_card]
            )
            
        # TAB 2: BATCH DASHBOARD
        with gr.Tab("Batch Summary Dashboard"):
            gr.Markdown("### Grade all sample submissions at once and compare their results")
            
            batch_btn = gr.Button("Load Batch Summary", variant="primary")
            batch_markdown = gr.Markdown("Click 'Load Batch Summary' to load pre-calculated results for Student A, B, and C.")
            
            batch_btn.click(
                fn=run_batch_grading,
                outputs=[batch_markdown]
            )
            
        # TAB 3: BOOK SEARCH
        with gr.Tab("Textbook Vector Search"):
            gr.Markdown("### Query the vector index of the textbook directly")
            
            with gr.Row():
                search_query = gr.Textbox(
                    label="Search Query",
                    placeholder="Enter keywords or ML questions (e.g. RANSAC, L1 L2, ElasticNet)..."
                )
                k_slider = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=4,
                    step=1,
                    label="Number of Context Chunks (K)"
                )
                
            search_btn = gr.Button("Search Vector Database")
            search_results_df = gr.DataFrame(
                headers=["Page", "Relevance Score", "Matching Textbook Context Excerpt"],
                wrap=True
            )
            
            search_btn.click(
                fn=search_textbook,
                inputs=[search_query, k_slider],
                outputs=[search_results_df]
            )
            
        # TAB 4: SYSTEM LOGS
        with gr.Tab("System Logs"):
            gr.Markdown("### Real-time logs of text extraction, embedding, search queries, and AI critic checks")
            
            refresh_logs_btn = gr.Button("Refresh System Logs")
            logs_view = gr.Code(
                value=get_logs(),
                language="python",
                interactive=False,
                lines=25,
                label="grader.log content"
            )
            
            refresh_logs_btn.click(
                fn=get_logs,
                outputs=[logs_view]
            )

# Automatically load the batch summary on startup if it exists
if os.path.exists("reports/batch_summary.md"):
    logger.info("Pre-calculated batch summary found. Ready for UI loading.")

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=gr.themes.Default(
            primary_hue="blue",
            secondary_hue="slate"
        ),
        css="""
            .gradio-container {
                background-color: #0f172a !important;
                color: #f8fafc !important;
            }
            button.primary {
                background-color: #2563eb !important;
                color: white !important;
            }
            button.primary:hover {
                background-color: #1d4ed8 !important;
            }
            textarea, input, select {
                background-color: #1e293b !important;
                color: #f8fafc !important;
                border-color: #334155 !important;
            }
            .tab-nav {
                border-bottom-color: #334155 !important;
            }
            .tab-nav button {
                color: #94a3b8 !important;
            }
            .tab-nav button.selected {
                color: #3b82f6 !important;
                border-bottom-color: #3b82f6 !important;
            }
        """
    )
