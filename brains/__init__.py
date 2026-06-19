"""
brains: swappable brain implementations.

The core ships a rule-based `StubBrain` (in `sim/brain.py`). This package holds
heavier alternatives that depend on extras -- `llm_brain_template.py` needs the
`anthropic` SDK. Imports here stay lazy so the package loads without those
extras installed.
"""
