import asyncio
import logging
import re
from typing import Optional

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError, constr
from twilio.rest.async_client import AsyncClient
from twilio.base.exceptions import TwilioRestException
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# Improved phone number validation regex:
WHATSAPP_E164_REGEX = re.compile(r"^\+?\d{10,15}$")


def validate_whatsapp_number(number: str) -> str:
    """
    Validate and normalize WhatsApp phone number in E.164 format with 'whatsapp:' prefix
    """
    if not number.startswith("whatsapp:"):
        raise ValueError(f"WhatsApp number must start with 'whatsapp:', got: {number}")

    phone = number[len("whatsapp:") :]
    if not WHATSAPP_E164_REGEX.match(phone):
        raise ValueError(f"Phone number {phone} must be in valid E.164 format (digits only, 10-15 digits)")
    return number


def get_env_variable(key: str, required: bool = True) -> Optional[str]:
    val = os.environ.get(key)
    if required and not val:
        raise EnvironmentError(f"Environment variable '{key}' is required but not set")
    return val


class ChainAnalysisReviewStrategy(BaseModel):
    review: str = Field(..., description="A detailed review of the on-chain data insights")
    strategy: str = Field(..., description="Recommended strategies based on on-chain data analysis")


class OnChainAnalysisTool(BaseTool):
    name = "OnChainAnalysisTool"
    description = "Analyzes blockchain data and returns insights for review and strategy generation."

    def _run(self, query: str) -> str:
        # TODO: Replace with actual blockchain data fetching and analysis
        # For demo, return a dummy insight string
        return (
            "On-chain data analysis indicates an increase in wallet activity and token "
            "velocity, suggesting growing market interest."
        )

    async def _arun(self, query: str) -> str:
        # Implement a non-blocking/async version if real data fetching is async
        # For now, delegate to sync method to keep compatibility
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run, query)


class WhatsAppSender:
    def __init__(self, account_sid: str, auth_token: str, from_whatsapp: str):
        self.client = AsyncClient(account_sid, auth_token)
        self.from_whatsapp = from_whatsapp

    async def send_message(self, to_whatsapp: str, message: str) -> str:
        try:
            msg = await self.client.messages.create(
                body=message, from_=self.from_whatsapp, to=to_whatsapp
            )
            return msg.sid
        except TwilioRestException as e:
            logger.error(f"Twilio error while sending WhatsApp message: {e}")
            raise RuntimeError("Failed to send WhatsApp message, please check the logs.") from e
        except Exception as e:
            logger.exception("Unexpected error sending WhatsApp message")
            raise RuntimeError("Failed to send WhatsApp message due to unexpected error.") from e


def create_chain_analysis_agent(
    model_name: str = "gpt-4o",
    temperature: float = 0.0,
    verbose: bool = False,
    system_prompt: Optional[str] = None,
    tool: Optional[BaseTool] = None,
):
    tool = tool or OnChainAnalysisTool()
    system_prompt = system_prompt or (
        "Eres un experto en análisis on-chain. "
        "Analiza los datos blockchain proporcionados, genera una reseña detallada y sugiere "
        "estrategias basadas en dichos datos. Devuelve la respuesta en un formato estructurado "
        "que incluya campos 'review' y 'strategy'."
    )
    model = ChatOpenAI(model=model_name, temperature=temperature)
    agent = create_agent(
        model=model,
        tools=[tool],
        response_format=ToolStrategy(ChainAnalysisReviewStrategy),
        system_prompt=system_prompt,
        verbose=verbose,
    )
    return agent


async def generate_and_send_analysis_async(
    user_query: str, to_whatsapp: str, agent=None
) -> str:
    """
    Async function to generate on-chain analysis, review, and strategy from user query,
    and send the result via WhatsApp.

    Args:
        user_query (str): User's input query for on-chain analysis.
        to_whatsapp (str): Recipient WhatsApp number in 'whatsapp:+{E.164}' format.
        agent: Optional pre-created agent instance.

    Returns:
        str: Twilio message SID.
    """
    # Validate user input length and sanitize if needed
    if not user_query.strip():
        raise ValueError("User query is empty or whitespace")

    # Validate and normalize WhatsApp number
    try:
        to_whatsapp_validated = validate_whatsapp_number(to_whatsapp)
    except ValueError as e:
        logger.error(f"Invalid WhatsApp number: {e}")
        raise

    # Lazy create agent if not provided
    if agent is None:
        agent = create_chain_analysis_agent(verbose=True)

    # Call agent asynchronously if possible
    response = await asyncio.to_thread(
        lambda: agent.invoke(messages=[HumanMessage(content=user_query)])
    )

    # Extract structured response with granular error handling
    try:
        structured = response.get("structured_response")
        if not structured:
            raise ValueError("Agent response did not contain 'structured_response'")
        # Validate with Pydantic model for security and structure
        parsed_response = ChainAnalysisReviewStrategy.parse_obj(structured)
        review = parsed_response.review
        strategy = parsed_response.strategy
    except (KeyError, ValidationError, ValueError) as e:
        logger.error(f"Failed to parse agent response: {e}")
        raise RuntimeError(f"Failed to parse agent response: {e}") from e

    whatsapp_message = (
        "🔍 *Análisis On-Chain*\n\n"
        "📝 *Reseña:*\n"
        f"{review}\n\n"
        "🎯 *Estrategias recomendadas:*\n"
        f"{strategy}"
    )

    # Load Twilio credentials once at runtime from env variables
    account_sid = get_env_variable("TWILIO_ACCOUNT_SID")
    auth_token = get_env_variable("TWILIO_AUTH_TOKEN")
    from_whatsapp = get_env_variable("TWILIO_WHATSAPP_FROM")

    # Validate from_whatsapp number format
    validate_whatsapp_number(from_whatsapp)

    sender = WhatsAppSender(account_sid, auth_token, from_whatsapp)

    message_sid = await sender.send_message(to_whatsapp_validated, whatsapp_message)
    logger.info(f"WhatsApp message sent with SID: {message_sid}")

    return message_sid


def generate_and_send_analysis(
    user_query: str, to_whatsapp: str, agent=None
) -> str:
    """
    Synchronous wrapper around async generate_and_send_analysis_async.
    """
    return asyncio.run(generate_and_send_analysis_async(user_query, to_whatsapp, agent))


if __name__ == "__main__":
    import sys

    # Example usage script with argument validation and minimal masking of sensitive info

    example_prompt = (
        "Analiza la situación actual on-chain de Ethereum y genera una reseña y estrategias "
        "para inversores basadas en los datos recientes."
    )
    example_recipient_number = "whatsapp:+521XXXXXXXXXX"  # Replace with actual E.164 number e.g. whatsapp:+5213456789012

    # Allow CLI override for prompt and recipient number for flexibility and security
    prompt = sys.argv[1] if len(sys.argv) > 1 else example_prompt
    recipient = sys.argv[2] if len(sys.argv) > 2 else example_recipient_number

    try:
        sid = generate_and_send_analysis(prompt, recipient)
        print(f"Mensaje enviado con SID: {sid}")
    except Exception as e:
        logger.error(f"Error in generating or sending analysis: {e}")
        # Avoid printing sensitive info; exit with non-zero
        sys.exit(1)
