"""
Example project-specific tool
A simple demonstration of how to create custom tools for your project
This example shows a timestamp tool, but you can create any tool you need
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dbrheo.tools.base import Tool
from dbrheo.types.tool_types import ToolResult
from dbrheo.types.core_types import AbortSignal


class TimestampTool(Tool):
    """
    A simple tool to get current timestamp or format dates
    This is an example of a project-specific tool
    """
    
    def __init__(self, config, i18n=None):
        super().__init__(
            name="get_timestamp",
            display_name="Example Timestamp Tool",
            description="[TEST TOOL] Example project tool for demonstration and reference. Shows how to create custom tools. This tool gets current timestamp or formats dates.",
            parameter_schema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Output format: 'unix', 'iso', 'human', or custom strftime format",
                        "default": "iso"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Timezone (e.g., 'UTC', 'local')",
                        "default": "local"
                    }
                },
                "required": []
            },
            is_output_markdown=False,
            can_update_output=False
        )
        self.config = config
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate parameters"""
        format_type = params.get("format", "iso")
        valid_formats = ["unix", "iso", "human"]
        
        # Check if it's a valid preset or a custom strftime format
        if format_type not in valid_formats and "%" not in format_type:
            return f"Invalid format. Use 'unix', 'iso', 'human', or a strftime format string"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get execution description"""
        format_type = params.get("format", "iso")
        return f"Getting timestamp in {format_type} format"
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal
    ) -> bool:
        """No confirmation needed for reading timestamp"""
        return False
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """Execute the tool"""
        try:
            format_type = params.get("format", "iso")
            tz = params.get("timezone", "local")
            
            # Get current time
            if tz == "UTC":
                now = datetime.now(timezone.utc)
            else:
                now = datetime.now()
            
            # Format the timestamp
            if format_type == "unix":
                result = str(int(now.timestamp()))
            elif format_type == "iso":
                result = now.isoformat()
            elif format_type == "human":
                result = now.strftime("%Y-%m-%d %H:%M:%S")
            elif "%" in format_type:
                # Custom strftime format
                try:
                    result = now.strftime(format_type)
                except Exception as e:
                    return ToolResult(
                        summary=f"Invalid format: {str(e)}",
                        llm_content="",
                        return_display=f"Invalid strftime format: {str(e)}",
                        error=f"Format error: {str(e)}"
                    )
            else:
                result = now.isoformat()
            
            return ToolResult(
                summary=f"Got timestamp: {result}",
                llm_content=result,
                return_display=f"**Timestamp:** `{result}`\n\n*Format: {format_type}*",
                error=None
            )
            
        except Exception as e:
            return ToolResult(
                summary=f"Error: {str(e)}",
                llm_content="",
                return_display=f"Error getting timestamp: {str(e)}",
                error=str(e)
            )


# Export the tool class for auto-registration
__all__ = ['TimestampTool']