import os
import re
import json
import logging
from jinja2 import Environment, FileSystemLoader

# Set up logging directories
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Set up Jinja2 template environment
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "prompts")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def setup_logger(name, log_file="logs/grader.log"):
    """Sets up a logger that outputs to both a file and stream console."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        # Stream handler
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger

logger = setup_logger("src.utils")

def render_prompt(template_name, **kwargs):
    """Loads and renders a Jinja2 template from the prompts folder."""
    try:
        template = jinja_env.get_template(template_name)
        return template.render(**kwargs)
    except Exception as e:
        logger.error(f"Error rendering template {template_name}: {e}")
        raise e

def parse_json_markdown(text):
    """Robustly extracts and parses a JSON object from text, ignoring think blocks and markdown formatting."""
    # Remove any thinking block from reasoning models
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    
    # Strip whitespace
    text_clean = text.strip()
    
    # Try normal JSON load first
    try:
        return json.loads(text_clean)
    except Exception:
        pass
        
    # Find first '{' and last '}'
    start_idx = text_clean.find('{')
    end_idx = text_clean.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_candidate = text_clean[start_idx:end_idx+1]
        try:
            return json.loads(json_candidate)
        except Exception as e:
            logger.error(f"Failed to parse extracted JSON block. Error: {e}\nCandidate string:\n{json_candidate}")
            
    logger.error(f"Could not find or parse JSON block in text:\n{text}")
    raise ValueError("Valid JSON not found in LLM output.")
