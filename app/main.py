import argparse
import os
import sys
import json
from pprint import pprint
from openai.types.chat import ChatCompletionMessageParam
from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
IS_LOCAL = os.getenv("LOCAL", default="false").lower() in ("1", "true", "yes")


def Read(path):
    with open(path) as f:
        return f.read()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-p", required=True)
    args = p.parse_args()
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    message_lst: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": args.p}
    ]

    model = "z-ai/glm-4.5-air:free" if IS_LOCAL else "anthropic/claude-haiku-4.5"
    print(f"Using model: {model}", file=sys.stderr)

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    while True:

        chat = client.chat.completions.create(
            model=model,
            messages=message_lst,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "Read",
                        "description": "Read and return the contents of a file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "The path to the file to read",
                                }
                            },
                            "required": ["file_path"],
                        },
                    },
                }
            ],
        )

        if not chat.choices or len(chat.choices) == 0:
            raise RuntimeError("no choices in response")

        message = chat.choices[0].message
        # You can use print statements as follows for debugging, they'll be visible when running tests.
        print("Logs from your program will appear here!", file=sys.stderr)
        if message.tool_calls:
            function_name = message.tool_calls[0].function.name
            args = json.loads(message.tool_calls[0].function.arguments)
            path = args["file_path"]
            result = globals()[function_name](path)
            print(result)
        else:
            print(message.content)


if __name__ == "__main__":
    main()
