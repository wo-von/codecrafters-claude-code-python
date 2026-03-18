import argparse
import json
import os
import sys
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
IS_LOCAL = os.getenv("LOCAL", "false").lower() in {"1", "true", "yes"}


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)

def read_tool_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "read_file",
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


def write_tool_spec() -> dict[str, any]: # type: ignore
    return {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "required": ["file_path", "content"],
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path of the file to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
            },
        },
    }


def get_model_name() -> str:
    return "z-ai/glm-4.5-air:free" if IS_LOCAL else "anthropic/claude-haiku-4.5"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one-shot chat + tool call.")
    parser.add_argument("-p", required=True, help="Prompt to send to the model.")
    return parser.parse_args()


def run_loop(client: OpenAI, message_lst: list[ChatCompletionMessageParam]) -> None:
    while True:
        completion = client.chat.completions.create(
            model=get_model_name(),
            messages=message_lst,
            tools=[read_tool_spec(), write_tool_spec()], # type: ignore
        )

        if not completion.choices:
            raise RuntimeError("No choices in response")
        message = completion.choices[0].message
        message_lst.append(message)

        if message.tool_calls:
            tool_call = message.tool_calls[0]
            function_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            if function_name == "read_file":
                content = read_file(args["file_path"])
            elif function_name == "write_file":
                write_file(args["file_path"], args["content"])
                content = "File written successfully"
            else:
                raise RuntimeError(f"Unknown tool function: {function_name}")
            message_lst.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": content,
                } # type: ignore
            )
            continue

        # Final model output
        print(message.content)
        break


def main() -> None:
    args = parse_args()
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": args.p}]
    print(f"Using model: {get_model_name()}", file=sys.stderr)
    run_loop(client, messages)


if __name__ == "__main__":
    main()
