import argparse
import json
import os
import sys
from typing import Any, Dict, List
import subprocess

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
IS_LOCAL = os.getenv("LOCAL", "false").lower() in {"1", "true", "yes"}


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return "File written successfully"

def bash_cmd(cmd:str) -> str:
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout


def read_tool_spec() -> Dict[str, Any]:
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


def write_tool_spec() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path of the file"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["file_path", "content"],
            },
        },
    }

def bash_tool_spec() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "bash_cmd",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute",
                    }
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


def execute_tool_call(tool_call: Any) -> str:
    args = json.loads(tool_call.function.arguments)
    if tool_call.function.name == "read_file":
        return read_file(args["file_path"])
    if tool_call.function.name == "write_file":
        return write_file(args["file_path"], args["content"])
    if tool_call.function.name == "bash_cmd":
        return bash_cmd(args["command"])
    raise RuntimeError(f"Unknown tool function: {tool_call.function.name}")


def run_loop(client: OpenAI, message_lst: List[ChatCompletionMessageParam]) -> None:
    tools = [read_tool_spec(), write_tool_spec(), bash_tool_spec()]
    while True:
        completion = client.chat.completions.create(
            model=get_model_name(),
            messages=message_lst,
            tools=tools,
        )

        if not completion.choices:
            raise RuntimeError("No choices in response")

        message = completion.choices[0].message
        message_lst.append(message)

        if not message.tool_calls:
            print(message.content)
            break

        tool_response = execute_tool_call(message.tool_calls[0])
        message_lst.append(
            {"role": "tool", "tool_call_id": message.tool_calls[0].id, "content": tool_response}
        )


def main() -> None:
    args = parse_args()
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    messages: List[ChatCompletionMessageParam] = [{"role": "user", "content": args.p}]
    print(f"Using model: {get_model_name()}", file=sys.stderr)
    run_loop(client, messages)


if __name__ == "__main__":
    main()
