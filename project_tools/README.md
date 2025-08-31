# Project Tools

This directory contains project-specific tools that are automatically loaded and registered by the agent.

## How to Create Custom Tools

1. Create a new Python file in this directory (e.g., `my_tool.py`)
2. Define a class that inherits from `dbrheo.tools.base.Tool`
3. Implement the required methods
4. The tool will be automatically discovered and registered when the agent starts

## Example Tool

See `example_tool.py` for a simple example that shows:
- How to define tool parameters
- How to implement validation
- How to execute the tool logic
- How to return results

## Required Methods

Your tool class must implement:
- `validate_tool_params(params)` - Validate input parameters
- `get_description(params)` - Return a description of what the tool will do
- `should_confirm_execute(params, signal)` - Whether to ask for user confirmation
- `execute(params, signal, update_output)` - The actual tool logic

## Auto-Registration

All tools in this directory are automatically:
- Discovered at startup
- Registered with the tool registry
- Available to the agent
- Tagged as "project" and "custom" tools

No additional configuration needed!