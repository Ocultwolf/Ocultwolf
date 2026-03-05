from langchain_core.prompts import PromptTemplate

template = """\
Your are a helpful that responds to the user's 

{% if name %}
The user's name is {{ name }} and you can call them by that name
{% endif -%}
"""

prompt_template = PromptTemplate.from_template(template, template_format="jinja2")