from app.llm.tools import _drive_search, _web_search

TOOL_FUNCTIONS = {
    "drive_search": _drive_search,
    "web_search": _web_search
}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "drive_search",
            "description": """
            Search internal Google Drive documents.
            Use for users personal information retrieval,
            like user background, reports, projects, personal documents, and others related to user.
            """,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string"
                    },
                    "k": {
                        "type": "integer",
                        "description": "define the number of document chunks return",
                        "default": 10
                    }
                },
                "required": ["query", "k"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": """
            Search the internet.
            Use for external information.
            """,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "set the maximum search result that return.",
                        "default": 8
                    }
                },
                "required": ["query"]
            }
        }
    }
]