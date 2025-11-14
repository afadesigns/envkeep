def my_validator(value: str) -> str:
    if value != "valid":
        raise ValueError("Value is not valid")
    return value
