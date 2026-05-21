from openai import OpenAI
from app.config import settings
import json

client = OpenAI(api_key=settings.openai_api_key)


def get_recommendations(profile: dict, clubs_context: list[dict]) -> list[dict]:
    """
    profile: {major, interests, goals, campus, time_commitment}
    clubs_context: list of abridged club dicts (top 50 by tag overlap)
    returns: [{club_id, match_score, reason}]
    """
    with open("app/prompts/recommend.txt") as f:
        system_prompt = f.read()
    user_message = (
        f"Profile: major={profile.get('major')}, "
        f"interests={profile.get('interests')}, "
        f"goals={profile.get('goals')}, "
        f"campus={profile.get('campus')}, "
        f"availability={profile.get('time_commitment')}. "
        f"Available clubs: {json.dumps(clubs_context[:50])}"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=1000,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    data = json.loads(response.choices[0].message.content)
    return data.get("recommendations", [])
