# from langgraph.graph import StateGraph, START, END
# from typing import TypedDict, NotRequired
# from pydantic import BaseModel, Field
# from langchain.chat_models import init_chat_model

# llm = init_chat_model("openai:gpt-4.1-mini")

# class SecurityReview(BaseModel):
#     vulnerabilities: list[str] = Field(description="The vulnerabilities in the code", default=None)
#     riskLevel: str = Field(description="The risk level of the vulnerabilities", default=None)
#     suggestions: list[str] = Field(description="The suggestions for fixing the vulnerabilities", default=None)


# class MaintainabilityReview(BaseModel):
#     concerns: list[str] = Field(description="The concerns about the code", default=None)
#     qualityScore: int = Field(description="The quality score of the code from 1 to 10", default=None, ge=1, le=10)
#     recommendations: list[str] = Field(description="The recommendations for improving the code", default=None)


# class State(TypedDict):
#     code: str
#     security_review: SecurityReview
#     maintainability_review: MaintainabilityReview
#     final_review: str

# def security_review(state: State):
#     code = state['code']
#     messages = [
#         ("system", "You are an expert in code security. Focus on identifying security vulnerabilities, injection risks, and authentication issues."),
#         ("user", f"Review this code: {code}")
#     ]
#     llm_with_structured_output = llm.with_structured_output(SecurityReview)
#     schema = llm_with_structured_output.invoke(messages)
#     return {
#         'security_review': schema
#     }


# def maintainability_review(state: State):
#     code = state['code']
#     messages = [
#         ("system", "You are an expert in code quality. Focus on code structure, readability, and adherence to best practices."),
#         ("user", f"Review this code: {code}")
#     ]
#     llm_with_structured_output = llm.with_structured_output(MaintainabilityReview)
#     schema = llm_with_structured_output.invoke(messages)
#     return {
#         'maintainability_review': schema
#     }


# def aggregator(state: State):
#     security_review = state['security_review']
#     maintainability_review = state['maintainability_review']
#     messages = [
#         ("system", "You are a technical lead summarizing multiple code reviews"),
#         ("user", f"Synthesize these code review results into a concise summary with key actions: Security review: {security_review} and Maintainability review: {maintainability_review}")
#     ]
#     response = llm.invoke(messages)
#     return {
#         'final_review': response.text
#     }


# builder = StateGraph(State)

# builder.add_node('security_review', security_review)
# builder.add_node('maintainability_review', maintainability_review)
# builder.add_node('aggregator', aggregator)

# builder.add_edge(START, 'security_review')
# builder.add_edge(START, 'maintainability_review')
# builder.add_edge("security_review", "aggregator")
# builder.add_edge("maintainability_review", "aggregator")
# builder.add_edge('aggregator', END)
# agent = builder.compile()









































# from langgraph.graph import StateGraph, START, END
# from typing import TypedDict, NotRequired
# from pydantic import BaseModel, Field
# from langchain.chat_models import init_chat_model

# llm = init_chat_model("openai:gpt-4.1-mini")

# # =========================
# # Models
# # =========================

# class SecurityReview(BaseModel):
#     vulnerabilities: list[str] = Field(
#         description=(
#             "Concrete and specific security issues found in the code. "
#             "Each item should mention the vulnerable component, why it is risky, "
#             "and the type of vulnerability (e.g., injection, auth, exposure)."
#         )
#     )

#     riskLevel: str = Field(
#         description=(
#             "Overall security risk assessment using one of the following values only: "
#             "'Low', 'Medium', or 'High'."
#         )
#     )

#     suggestions: list[str] = Field(
#         description=(
#             "Actionable remediation steps that directly mitigate the identified vulnerabilities. "
#             "Suggestions must be technically specific and implementation-oriented."
#         )
#     )


# class MaintainabilityReview(BaseModel):
#     concerns: list[str] = Field(
#         description=(
#             "Specific maintainability problems in the code such as complexity, "
#             "poor naming, tight coupling, lack of modularity, or unclear responsibilities."
#         )
#     )

#     qualityScore: int = Field(
#         description=(
#             "Overall maintainability and code quality score from 1 (very poor) "
#             "to 10 (excellent), considering readability, structure, and best practices."
#         ),
#         ge=1,
#         le=10
#     )

#     recommendations: list[str] = Field(
#         description=(
#             "Concrete refactoring or design recommendations that improve readability, "
#             "testability, and long-term maintainability."
#         )
#     )



# class PerformanceReview(BaseModel):
#     bottlenecks: list[str] = Field(
#         description=(
#             "Specific code paths, operations, or patterns that negatively impact performance, "
#             "such as unnecessary loops, blocking I/O, excessive memory usage, or repeated computations."
#         )
#     )

#     efficiencyScore: int = Field(
#         description=(
#             "Overall performance efficiency score from 1 (inefficient) to 10 (highly optimized), "
#             "considering runtime cost, memory usage, and scalability."
#         ),
#         ge=1,
#         le=10
#     )

#     optimizationSuggestions: list[str] = Field(
#         description=(
#             "Concrete and implementable optimizations that improve performance or scalability "
#             "without changing the external behavior of the code."
#         )
#     )



# # =========================
# # State
# # =========================

# class State(TypedDict):
#     code: str
#     security_review: SecurityReview
#     maintainability_review: MaintainabilityReview
#     performance_review: PerformanceReview
#     final_review: str
#     refactored_code: str


# # =========================
# # Nodes
# # =========================

# def security_review(state: State):
#     llm_structured = llm.with_structured_output(SecurityReview)
#     return {
#         "security_review": llm_structured.invoke([
#             ("system", "You are an expert in code security."),
#             ("user", f"Review this code:\n{state['code']}")
#         ])
#     }


# def maintainability_review(state: State):
#     llm_structured = llm.with_structured_output(MaintainabilityReview)
#     return {
#         "maintainability_review": llm_structured.invoke([
#             ("system", "You are an expert in code maintainability and quality."),
#             ("user", f"Review this code:\n{state['code']}")
#         ])
#     }


# def performance_review(state: State):
#     llm_structured = llm.with_structured_output(PerformanceReview)
#     return {
#         "performance_review": llm_structured.invoke([
#             ("system", "You are an expert in performance optimization and scalability."),
#             ("user", f"Analyze the performance of this code:\n{state['code']}")
#         ])
#     }


# def aggregator(state: State):
#     response = llm.invoke([
#         ("system", "You are a senior technical lead synthesizing multiple code reviews."),
#         (
#             "user",
#             f"""
# Security Review:
# {state['security_review']}

# Maintainability Review:
# {state['maintainability_review']}

# Performance Review:
# {state['performance_review']}

# Produce a concise but actionable final review.
# """
#         )
#     ])
#     return {"final_review": response.text}


# def code_refactorer(state: State):
#     response = llm.invoke([
#         ("system", "You are a senior software engineer refactoring code based on reviews."),
#         (
#             "user",
#             f"""
# Original code:
# {state['code']}

# Final review:
# {state['final_review']}

# Tasks:
# 1. Suggest concrete refactoring strategies
# 2. Provide at least one improved code version
# 3. Ensure functionality is preserved
# 4. Explain why the changes improve security, maintainability, or performance
# """
#         )
#     ])
#     return {"refactored_code": response.text}


# # =========================
# # Graph
# # =========================

# builder = StateGraph(State)

# builder.add_node("security_review", security_review)
# builder.add_node("maintainability_review", maintainability_review)
# builder.add_node("performance_review", performance_review)
# builder.add_node("aggregator", aggregator)
# builder.add_node("code_refactorer", code_refactorer)

# builder.add_edge(START, "security_review")
# builder.add_edge(START, "maintainability_review")
# builder.add_edge(START, "performance_review")

# builder.add_edge("security_review", "aggregator")
# builder.add_edge("maintainability_review", "aggregator")
# builder.add_edge("performance_review", "aggregator")

# builder.add_edge("aggregator", "code_refactorer")
# builder.add_edge("code_refactorer", END)

# agent = builder.compile()





















































# from langgraph.graph import StateGraph, START, END
# from typing import TypedDict
# from pydantic import BaseModel, Field
# from langchain.chat_models import init_chat_model
# import functools
# import hashlib

# llm = init_chat_model("openai:gpt-4.1-mini")


# # =========================
# # Models
# # =========================

# class SecurityReview(BaseModel):
#     vulnerabilities: list[str] = Field(
#         description=(
#             "Concrete and specific security issues found in the code. "
#             "Each item should mention the vulnerable component, why it is risky, "
#             "and the type of vulnerability (e.g., injection, auth, exposure)."
#         )
#     )
#     riskLevel: str = Field(
#         description=(
#             "Overall security risk assessment using one of the following values only: "
#             "'Low', 'Medium', or 'High'."
#         )
#     )
#     suggestions: list[str] = Field(
#         description=(
#             "Actionable remediation steps that directly mitigate the identified vulnerabilities. "
#             "Suggestions must be technically specific and implementation-oriented."
#         )
#     )


# class MaintainabilityReview(BaseModel):
#     concerns: list[str] = Field(
#         description=(
#             "Specific maintainability problems in the code such as complexity, "
#             "poor naming, tight coupling, lack of modularity, or unclear responsibilities."
#         )
#     )
#     qualityScore: int = Field(
#         description=(
#             "Overall maintainability and code quality score from 1 (very poor) "
#             "to 10 (excellent), considering readability, structure, and best practices."
#         ),
#         ge=1,
#         le=10
#     )
#     recommendations: list[str] = Field(
#         description=(
#             "Concrete refactoring or design recommendations that improve readability, "
#             "testability, and long-term maintainability."
#         )
#     )


# class PerformanceReview(BaseModel):
#     bottlenecks: list[str] = Field(
#         description=(
#             "Specific code paths, operations, or patterns that negatively impact performance, "
#             "such as unnecessary loops, blocking I/O, excessive memory usage, or repeated computations."
#         )
#     )
#     efficiencyScore: int = Field(
#         description=(
#             "Overall performance efficiency score from 1 (inefficient) to 10 (highly optimized), "
#             "considering runtime cost, memory usage, and scalability."
#         ),
#         ge=1,
#         le=10
#     )
#     optimizationSuggestions: list[str] = Field(
#         description=(
#             "Concrete and implementable optimizations that improve performance or scalability "
#             "without changing the external behavior of the code."
#         )
#     )


# # =========================
# # State
# # =========================

# class State(TypedDict):
#     code: str
#     security_review: SecurityReview
#     maintainability_review: MaintainabilityReview
#     performance_review: PerformanceReview
#     final_review: str
#     refactored_code: str


# # =========================
# # Constants for Node Names & Prompts
# # =========================

# SECURITY_NODE = "security_review"
# MAINTAINABILITY_NODE = "maintainability_review"
# PERFORMANCE_NODE = "performance_review"
# AGGREGATOR_NODE = "aggregator"
# REFACTORER_NODE = "code_refactorer"


# SECURITY_SYSTEM_PROMPT = (
#     "You are an expert in code security. Focus on identifying security vulnerabilities, "
#     "injection risks, and authentication issues."
# )

# MAINTAINABILITY_SYSTEM_PROMPT = (
#     "You are an expert in code maintainability and quality. Focus on code structure, "
#     "readability, and adherence to best practices."
# )

# PERFORMANCE_SYSTEM_PROMPT = (
#     "You are an expert in performance optimization and scalability. "
#     "Analyze runtime cost, memory usage, and scalability."
# )

# AGGREGATOR_SYSTEM_PROMPT = "You are a senior technical lead synthesizing multiple code reviews."

# REFACTORER_SYSTEM_PROMPT = "You are a senior software engineer refactoring code based on reviews."


# # =========================
# # Utility Functions
# # =========================

# def validate_code_input(code: str):
#     """
#     Simple input validation for the source code.
#     Raises ValueError if invalid input detected.
#     """
#     if not isinstance(code, str):
#         raise ValueError("Code must be a string.")
#     if len(code.strip()) == 0:
#         raise ValueError("Code cannot be empty or whitespace only.")


# def get_code_hash(code: str) -> str:
#     """
#     Returns a SHA-256 hash hex digest for the given code string.
#     Useful for caching.
#     """
#     return hashlib.sha256(code.encode('utf-8')).hexdigest()


# # =========================
# # Pre-initialize structured output wrappers (performance optimization)
# # =========================

# # These are initialized once and reused to reduce overhead in node executions.
# llm_security = llm.with_structured_output(SecurityReview)
# llm_maintainability = llm.with_structured_output(MaintainabilityReview)
# llm_performance = llm.with_structured_output(PerformanceReview)


# # Simple in-memory cache dictionaries keyed by code hash to avoid redundant LLM calls
# _security_cache: dict[str, SecurityReview] = {}
# _maintainability_cache: dict[str, MaintainabilityReview] = {}
# _performance_cache: dict[str, PerformanceReview] = {}


# # =========================
# # Nodes
# # =========================

# def security_review(state: State):
#     code = state.get("code")
#     validate_code_input(code)
#     code_key = get_code_hash(code)
#     if code_key in _security_cache:
#         return {"security_review": _security_cache[code_key]}

#     result = llm_security.invoke([
#         ("system", SECURITY_SYSTEM_PROMPT),
#         ("user", f"Review this code:\n{code}")
#     ])
#     _security_cache[code_key] = result
#     return {"security_review": result}


# def maintainability_review(state: State):
#     code = state.get("code")
#     validate_code_input(code)
#     code_key = get_code_hash(code)
#     if code_key in _maintainability_cache:
#         return {"maintainability_review": _maintainability_cache[code_key]}

#     result = llm_maintainability.invoke([
#         ("system", MAINTAINABILITY_SYSTEM_PROMPT),
#         ("user", f"Review this code:\n{code}")
#     ])
#     _maintainability_cache[code_key] = result
#     return {"maintainability_review": result}


# def performance_review(state: State):
#     code = state.get("code")
#     validate_code_input(code)
#     code_key = get_code_hash(code)
#     if code_key in _performance_cache:
#         return {"performance_review": _performance_cache[code_key]}

#     result = llm_performance.invoke([
#         ("system", PERFORMANCE_SYSTEM_PROMPT),
#         ("user", f"Analyze the performance of this code:\n{code}")
#     ])
#     _performance_cache[code_key] = result
#     return {"performance_review": result}


# def aggregator(state: State):
#     # Defensive: ensure required reviews are present
#     sec_rev = state.get("security_review")
#     maint_rev = state.get("maintainability_review")
#     perf_rev = state.get("performance_review")
#     if not (sec_rev and maint_rev and perf_rev):
#         raise ValueError("Missing one or more review results in state.")

#     response = llm.invoke([
#         ("system", AGGREGATOR_SYSTEM_PROMPT),
#         ("user", f"""
# Security Review:
# {sec_rev}

# Maintainability Review:
# {maint_rev}

# Performance Review:
# {perf_rev}

# Produce a concise but actionable final review.
# """)
#     ])
#     return {"final_review": response.text}


# def code_refactorer(state: State):
#     code = state.get("code")
#     final_review = state.get("final_review")

#     validate_code_input(code)
#     if not final_review or not final_review.strip():
#         raise ValueError("Final review must be present and non-empty.")

#     response = llm.invoke([
#         ("system", REFACTORER_SYSTEM_PROMPT),
#         ("user", f"""
# Original code:
# {code}

# Final review:
# {final_review}

# Tasks:
# 1. Suggest concrete refactoring strategies
# 2. Provide at least one improved code version
# 3. Ensure functionality is preserved
# 4. Explain why the changes improve security, maintainability, or performance
# """)
#     ])
#     return {"refactored_code": response.text}


# # =========================
# # Graph construction
# # =========================

# builder = StateGraph(State)

# builder.add_node(SECURITY_NODE, security_review)
# builder.add_node(MAINTAINABILITY_NODE, maintainability_review)
# builder.add_node(PERFORMANCE_NODE, performance_review)
# builder.add_node(AGGREGATOR_NODE, aggregator)
# builder.add_node(REFACTORER_NODE, code_refactorer)

# builder.add_edge(START, SECURITY_NODE)
# builder.add_edge(START, MAINTAINABILITY_NODE)
# builder.add_edge(START, PERFORMANCE_NODE)

# builder.add_edge(SECURITY_NODE, AGGREGATOR_NODE)
# builder.add_edge(MAINTAINABILITY_NODE, AGGREGATOR_NODE)
# builder.add_edge(PERFORMANCE_NODE, AGGREGATOR_NODE)

# builder.add_edge(AGGREGATOR_NODE, REFACTORER_NODE)
# builder.add_edge(REFACTORER_NODE, END)

# agent = builder.compile()


from langgraph.graph import StateGraph, START, END
from typing import TypedDict, NotRequired
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from agents.executor_subgraph import build_executor_subgraph


import hashlib
import os

# =========================
# LLM
# =========================

llm = init_chat_model("openai:gpt-4.1-mini")

# =========================
# RAG (GLOBAL, SHARED)
# =========================

VECTORSTORE_DIR = "/home/ocultwolf/.openclaw/workspace/python/MongoIA/clon/platzilang/curso-agentes-langgraph/src/agents/vectorstore_langchain_langgraph/"
_embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
_vectorstore = FAISS.load_local(
    VECTORSTORE_DIR,
    _embeddings,
    allow_dangerous_deserialization=True
)
retriever = _vectorstore.as_retriever(search_kwargs={"k": 5})


def get_rag_context(query: str) -> str:
    docs = retriever.invoke(query)
    return "\n\n".join(d.page_content for d in docs)


# =========================
# Models
# =========================

class SecurityReview(BaseModel):
    vulnerabilities: list[str]
    riskLevel: str
    suggestions: list[str]


class MaintainabilityReview(BaseModel):
    concerns: list[str]
    qualityScore: int = Field(ge=1, le=10)
    recommendations: list[str]


class PerformanceReview(BaseModel):
    bottlenecks: list[str]
    efficiencyScore: int = Field(ge=1, le=10)
    optimizationSuggestions: list[str]


# =========================
# State
# =========================

class State(TypedDict):
    user_prompt: str
    code: str
    rag_context: str
    security_review: SecurityReview
    maintainability_review: MaintainabilityReview
    performance_review: PerformanceReview
    final_review: str
    refactored_code: str
    execution_success: NotRequired[bool]
    execution_error: NotRequired[str | None]
    execution_stdout: NotRequired[str | None]


# =========================
# Node names
# =========================

CODE_GENERATOR_NODE = "code_generator"
SECURITY_NODE = "security_review"
MAINTAINABILITY_NODE = "maintainability_review"
PERFORMANCE_NODE = "performance_review"
AGGREGATOR_NODE = "aggregator"
REFACTORER_NODE = "code_refactorer"
EXECUTOR_VALIDATE_NODE = "executor_validate"
EXECUTOR_FINAL_NODE = "executor_final"

executor_validate_graph = build_executor_subgraph()
executor_final_graph = build_executor_subgraph()




# =========================
# Utils
# =========================

def validate_code_input(code: str):
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Invalid code input")


def get_code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# =========================
# Structured outputs
# =========================

llm_security = llm.with_structured_output(SecurityReview)
llm_maintainability = llm.with_structured_output(MaintainabilityReview)
llm_performance = llm.with_structured_output(PerformanceReview)


# =========================
# Nodes
# =========================

def code_generator(state: State):
    user_prompt = state.get("user_prompt")
    if not user_prompt:
        raise ValueError("user_prompt is required")

    rag_context = get_rag_context(user_prompt)

    response = llm.invoke([
        ("system",
         "You are an expert LangChain and LangGraph engineer. "
         "Generate clean, idiomatic, production-ready Python code "
         "following LangChain and LangGraph best practices."),
        ("user", f"""
User request:
{user_prompt}

Relevant documentation:
{rag_context}

Generate the code.
""")
    ])

    return {
        "code": response.text,
        "rag_context": rag_context
    }


def security_review(state: State):
    code = state["code"]
    rag = state["rag_context"]

    result = llm_security.invoke([
        ("system", "You are a security expert reviewing code."),
        ("user", f"""
Code:
{code}

Relevant documentation:
{rag}
""")
    ])
    return {"security_review": result}


def maintainability_review(state: State):
    code = state["code"]
    rag = state["rag_context"]

    result = llm_maintainability.invoke([
        ("system", "You are a maintainability expert."),
        ("user", f"""
Code:
{code}

Relevant documentation:
{rag}
""")
    ])
    return {"maintainability_review": result}


def performance_review(state: State):
    code = state["code"]
    rag = state["rag_context"]

    result = llm_performance.invoke([
        ("system", "You are a performance optimization expert."),
        ("user", f"""
Code:
{code}

Relevant documentation:
{rag}
""")
    ])
    return {"performance_review": result}


def aggregator(state: State):
    stdout = state.get("execution_stdout") or "(no stdout captured)"
    stderr = state.get("execution_error") or "(no stderr captured)"
    response = llm.invoke([
        ("system", "You are a senior technical lead."),
        ("user", f"""
Security Review:
{state["security_review"]}

Maintainability Review:
{state["maintainability_review"]}

Performance Review:
{state["performance_review"]}

Latest execution stdout:
{stdout}

Latest execution stderr:
{stderr}

Synthesize a final review and highlight any runtime issues to address.
""")
    ])
    return {"final_review": response.text}


def code_refactorer(state: State):
    stdout = state.get("execution_stdout") or "(no stdout captured)"
    stderr = state.get("execution_error") or "(no stderr captured)"
    response = llm.invoke([
        ("system", "You are a senior software engineer."),
        ("user", f"""
Original code:
{state["code"]}

Final review:
{state["final_review"]}

Documentation:
{state["rag_context"]}

Latest execution stdout:
{stdout}

Latest execution stderr:
{stderr}

Refactor and improve the code, addressing any runtime failures.
""")
    ])
    return {"refactored_code": response.text}


# =========================
# Graph
# =========================

builder = StateGraph(State)

builder.add_node(CODE_GENERATOR_NODE, code_generator)
builder.add_node(SECURITY_NODE, security_review)
builder.add_node(MAINTAINABILITY_NODE, maintainability_review)
builder.add_node(PERFORMANCE_NODE, performance_review)
builder.add_node(AGGREGATOR_NODE, aggregator)
builder.add_node(REFACTORER_NODE, code_refactorer)
builder.add_node(EXECUTOR_VALIDATE_NODE, executor_validate_graph)
builder.add_node(EXECUTOR_FINAL_NODE, executor_final_graph)


builder.add_edge(START, CODE_GENERATOR_NODE)
builder.add_edge(CODE_GENERATOR_NODE, EXECUTOR_VALIDATE_NODE)

builder.add_edge(EXECUTOR_VALIDATE_NODE, SECURITY_NODE)
builder.add_edge(EXECUTOR_VALIDATE_NODE, MAINTAINABILITY_NODE)
builder.add_edge(EXECUTOR_VALIDATE_NODE, PERFORMANCE_NODE)

builder.add_edge(SECURITY_NODE, AGGREGATOR_NODE)
builder.add_edge(MAINTAINABILITY_NODE, AGGREGATOR_NODE)
builder.add_edge(PERFORMANCE_NODE, AGGREGATOR_NODE)

builder.add_edge(AGGREGATOR_NODE, REFACTORER_NODE)
builder.add_edge(REFACTORER_NODE, EXECUTOR_FINAL_NODE)

builder.add_edge(EXECUTOR_FINAL_NODE, END)

agent = builder.compile()
