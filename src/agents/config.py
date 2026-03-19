"""
Central model configuration.
- Tier 1 (free, local): Ollama @ 172.17.0.1:11434
- Tier 2 (cheap API):   claude-haiku-3-5
- Tier 3 (complex):     claude-sonnet-4-5
Only Anthropic API is funded. OpenAI is disabled.
"""

OLLAMA_BASE_URL = "http://172.17.0.1:11434"

# Tier 1 - local, free
INTENT_MODEL = "deepseek-r1:14b"          # intent classification (fast, no API cost)
SIMPLE_MODEL  = "deepseek-r1:14b"         # simple Q&A, summaries

# Tier 2 - cheap Anthropic
CHEAP_MODEL   = "anthropic:claude-haiku-3-5-20241022"  # structured extraction, medium tasks

# Tier 3 - full Anthropic
SMART_MODEL   = "anthropic:claude-sonnet-4-5-20250514"  # complex reasoning

# Anti-loop safety
MAX_ITERATIONS = 3
