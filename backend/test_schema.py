import google.generativeai as genai
from google.ai.generativelanguage import Type, Schema, FunctionDeclaration, Tool

try:
    tool = Tool(
        function_declarations=[
            FunctionDeclaration(
                name="test",
                description="test",
                parameters=Schema(
                    type=Type.OBJECT,
                    properties={
                        "checkpoint_ids": Schema(
                            type=Type.ARRAY,
                            items=Schema(type=Type.STRING)
                        )
                    }
                )
            )
        ]
    )
    print("Success with google.ai.generativelanguage objects")
except Exception as e:
    import traceback
    traceback.print_exc()

try:
    # Testing dict definition exactly like we have but with ints instead of strings for types
    schema = {
        "name": "test",
        "description": "test",
        "parameters": {
            "type": Type.OBJECT,
            "properties": {
                "checkpoint_ids": {
                    "type": Type.ARRAY,
                    "items": {"type": Type.STRING}
                }
            }
        }
    }
    model = genai.GenerativeModel("gemini-1.5-flash", tools=[schema])
    print("Success with dict using Type enum")
except Exception as e:
    import traceback
    traceback.print_exc()
