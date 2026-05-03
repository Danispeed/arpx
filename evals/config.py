import os
from dotenv import load_dotenv

load_dotenv()

AZURE_ENDPOINT = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip().rstrip("/")
AZURE_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_API_VERSION = (os.getenv("AZURE_OPENAI_API_VERSION") or "").strip() or "2024-10-21"

GENERATOR_MODEL = os.getenv("ARPX_GENERATOR_MODEL", "gpt-5-chat")
JUDGE_MODEL = os.getenv("ARPX_JUDGE_MODEL", "DeepSeek-V3.2")
PROPOSER_MODEL = os.getenv("ARPX_PROPOSER_MODEL", "gpt-4.1-mini")

CONCURRENCY = int(os.getenv("ARPX_EVAL_CONCURRENCY", "3"))

PROMPTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "n8n_workflows", "prompts.yaml")
CASES_PATH = os.path.join(os.path.dirname(__file__), "cases.yaml")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
