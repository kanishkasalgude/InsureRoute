import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
print("Available models:", models)
