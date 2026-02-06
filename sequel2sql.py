"""
Sequel2SQL - Main Application Entry Point

Runs a web-based chat interface for the SQL agent using Pydantic AI's built-in web UI.
"""

# Load environment variables BEFORE importing agent
# (agent initialization needs GOOGLE_API_KEY to be set)
from agent.sqlagent import agent

# Create web application from agent
app = agent.to_web()

if __name__ == "__main__":
	import uvicorn

	print("Starting Sequel2SQL web interface...")
	print("Open http://localhost:8000 in your browser")
	print("Press Ctrl+C to stop")

	uvicorn.run(app, host="0.0.0.0", port=8000)
