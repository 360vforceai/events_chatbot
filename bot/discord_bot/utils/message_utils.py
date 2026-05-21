def split_message(content: str, limit: int = 2000) -> list[str]:
    if not content:
        return []
    return [content[i:i+limit] for i in range(0, len(content), limit)]
