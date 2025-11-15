import enum 

def messages_dump(obj):
    """Recursively convert objects to a JSON-serializable format."""
    if isinstance(obj, dict):
        return {k: messages_dump(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [messages_dump(item) for item in obj]
    elif hasattr(obj, 'model_dump'):
        return messages_dump(obj.model_dump())
    # if it's an enum...
    elif isinstance(obj, enum.Enum):
        return messages_dump(obj.value)
    else:
        return obj