import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from your environment

SYSTEM = """Extract information from meeting notes.
Return ONLY valid JSON, no other text, in this shape:
{"date": string or null, "attendees": [string],
 "action_items": [{"task": string, "owner": string or null, "due": string or null}]}

Rules:
- Use null for anything not stated. Do not invent details.
- Copy dates exactly as written. Never convert relative dates ("Friday", "next Tuesday") to calendar dates, and never guess a year.
- Include tasks that are clearly assigned or clearly required. If no one is named, owner is null.
- Skip hedged items ("might", "maybe", "at some point") and general discussion."""

EXAMPLES = [
    (
        "Budget sync - June 4\nPresent: Ana, Raj\n"
        "Raj will send the forecast by Friday. Ana might look at vendor options if time allows. "
        "Someone needs to book the room for next Tuesday.",
        {
            "date": "June 4",
            "attendees": ["Ana", "Raj"],
            "action_items": [
                {"task": "send the forecast", "owner": "Raj", "due": "Friday"},
                {"task": "book the room", "owner": None, "due": "next Tuesday"},
            ],
        },
    ),
    (
        "standup (5/8?)\nomar and jess here\nroadmap looks fine, no changes.",
        {"date": "5/8", "attendees": ["omar", "jess"], "action_items": []},
    ),
]

def build_messages(notes: str) -> list[dict]:
    messages = []
    for ex_notes, ex_output in EXAMPLES:
        messages.append({"role": "user", "content": ex_notes})
        messages.append({"role": "assistant", "content": json.dumps(ex_output)})
    messages.append({"role": "user", "content": notes})
    return messages

def extract(notes: str) -> dict:
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM,
        messages=build_messages(notes),
    )
    text = resp.content[0].text.strip()
    text = text.removeprefix("```json").removesuffix("```").strip()
    return json.loads(text)

TEST_NOTES = {
    "clean": """Project Kickoff - March 3, 2026
Attendees: Priya, Marcus, Elena
- Priya will draft the project brief by March 10.
- Marcus to set up the shared repo by Friday.
- Elena will email the client to confirm the budget. No deadline set.""",

    "messy": """standup notes tues (3/17?)
priya + marcus here, elena out sick
marcus said hes blocked on the API keys, someone needs to ask IT. priya says shell do it today.
we should probably look at the onboarding flow at some point
elena's report is due eow but she's out so maybe pushed?""",

    "no_actions": """Weekly Sync - April 2, 2026
Attendees: Sam, Dana
Reviewed last week's metrics. Traffic is up 12%. No blockers.
Next meeting same time next week.""",

    "ambiguous_owners": """Design Review
Attended: Lee, Kim, Jordan, Alex
The team agreed the homepage needs a redesign. Someone should send the mockups to the client by next Wednesday.
Kim mentioned she might look into accessibility issues if she has time.
Action: update the style guide (Jordan, end of month).""",
}

for name, notes in TEST_NOTES.items():
    print(f"\n=== {name} ===")
    try:
        result = extract(notes)
        print(json.dumps(result, indent=2))
    except json.JSONDecodeError as e:
        print(f"FAILED to parse JSON: {e}")