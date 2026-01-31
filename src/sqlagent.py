"""
Sequel2SQL Agent

A Pydantic AI agent using Google Gemma 3 27B for PostgreSQL query assistance.
This is the foundational agent before adding RAG and AST components.
"""

from pydantic_ai import Agent

# Optional: Configure LogFire for monitoring and debugging
# Uncomment the lines below after running: uv run logfire auth
# import logfire
# logfire.configure()
# logfire.instrument_pydantic_ai()

# Initialize agent with Gemma 3 27B via Gemini API
agent = Agent(
	'google-gla:gemma-3-27b-it',
	system_prompt=(
		'You are a SQL assistant specialized in PostgreSQL. '
		'You help users write, understand, debug, and optimize PostgreSQL queries. '
		'Provide clear explanations and correct SQL syntax. '
		'When fixing errors, explain what was wrong and why your solution works.'
	)
)
