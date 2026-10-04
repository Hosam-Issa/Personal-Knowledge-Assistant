import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()

def get_weather(city: str) -> dict:
    return {"city": city, "temp_c": 4, "conditions": "rainy"}

def get_time(city: str) -> dict:
    if city == "Tokyo":
        raise ValueError("City not found. Provide a city name, e.g. Toronto.")
    
    return {"city": city, "time": "1:43PM"}

# JSON Schema
TOOLS = [{
    "name": "get_weather",
    "description": "Get the current weather for a city.",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
},
{
    "name": "get_time",
    "description": "Get the current time for a city.",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    }
}]

TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "get_time": get_time,
}

def run_agent(question: str, max_steps: int = 5) -> str:
    messages = [{"role": "user", "content": question}]
    for _ in range(max_steps):
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )
        print("STOP REASON:", resp.stop_reason)
        print(resp.content)

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                func = TOOL_FUNCTIONS.get(block.name)
                if func is None:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Unknown tool: {block.name}",
                        "is_error": True,
                    })
                    continue
                try:
                    output = func(**block.input)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(output),
                    })
                except Exception as e:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {e}",
                        "is_error": True,
                    })
                
        messages.append({"role": "user", "content": results})
    return "Stopped: too many steps."

print(run_agent("What's the time in Tokyo?"))