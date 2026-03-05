from langchain_core.prompts import PromptTemplate

template = """\
You are a helpful assistant that can extract contact information from a given conversation.
"""

prompt_template = PromptTemplate.from_template(template)