import asyncio
import os
import sys
sys.path.append(os.path.dirname(__file__))

from core.gemini_agent import GeminiAgent

async def main():
    agent = GeminiAgent({})
    res = await agent.run("Should I reroute this shipment?", {"cargo_type": "fmcg", "priority": "safety"})
    print(res)

if __name__ == "__main__":
    asyncio.run(main())