import json

class BaseModel:
    def __init__(self, **data):
        for k, v in data.items():
            setattr(self, k, v)

    def model_dump_json(self, indent=None):
        return json.dumps(self.__dict__, indent=indent)

    @classmethod
    def model_json_schema(cls):
        return {}

    @classmethod
    def model_validate_json(cls, text):
        data = json.loads(text)
        return cls(**data)
