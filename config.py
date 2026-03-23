import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Model Configurations
LLM_MODEL = "llama-3.3-70b-versatile"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Agent Thresholds
DEVIATION_THRESHOLD = 0.75

# File Constraints
MAX_FILE_SIZE_MB = 20
SCANNED_PAGE_THRESHOLD = 50  # characters
