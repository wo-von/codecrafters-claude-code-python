import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
IS_LOCAL = os.getenv("LOCAL", "false").lower() in {"1", "true", "yes"}

# A single tool result is capped before it enters the conversation. Reading a
# large file would otherwise fill the context window in one turn, and the run
# would die on a token limit rather than on anything interesting.
MAX_TOOL_OUTPUT_CHARS = 20_000

# A shell command that never returns would hang the loop forever.
BASH_TIMEOUT_SECONDS = 120

# The model decides when it is done. This bounds how wrong that can go.
DEFAULT_MAX_ITERATIONS = 25


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
# Every tool returns a string. Failures are returned as strings too, not
# raised: the model is the one that has to recover from them, so it has to be
# able to see them. See execute_tool_call.


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote {len(content)} characters to {path}"


def bash_cmd(cmd: str) -> str:
    # The exit code is part of the result. Without it the model sees the
    # stderr of a failed command with no reliable way to tell that it failed.
    try:
        completed = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=BASH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {BASH_TIMEOUT_SECONDS}s: {cmd}"
    return f"exit_code={completed.returncode}\n{completed.stdout}"


def truncate(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return f"{text[:limit]}\n\n[truncated: {dropped} more characters]"


# --------------------------------------------------------------------------
# Tool specifications
# --------------------------------------------------------------------------


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


TOOLS = [read_tool_spec(), write_tool_spec(), bash_tool_spec()]


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------


def dispatch(name: str, args: Dict[str, Any]) -> str:
    if name == "read_file":
        return read_file(args["file_path"])
    if name == "write_file":
        return write_file(args["file_path"], args["content"])
    if name == "bash_cmd":
        return bash_cmd(args["command"])
    raise RuntimeError(f"Unknown tool function: {name}")


def execute_tool_call(tool_call: Any) -> str:
    """Run one tool call and return its result as a string.

    Never raises. A tool that fails -- bad JSON in the arguments, a missing
    required field, a file that is not there, an unknown tool name -- returns
    the failure as its result so the model can read it and try something else.
    Raising here would end the run on the first mistake the model makes, which
    is the opposite of what an agent loop is for.
    """
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as exc:
        return f"Error: could not parse arguments for {name} as JSON: {exc}"

    if not isinstance(args, dict):
        return f"Error: arguments for {name} must be a JSON object"

    try:
        return truncate(dispatch(name, args))
    except KeyError as exc:
        return f"Error: missing required argument {exc} for {name}"
    except Exception as exc:  # noqa: BLE001 - surfaced to the model, not swallowed
        return f"Error: {name} failed: {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------
# Agent loop
# --------------------------------------------------------------------------


def get_model_name() -> str:
    return "z-ai/glm-4.5-air:free" if IS_LOCAL else "anthropic/claude-haiku-4.5"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an LLM agent loop with tools.")
    parser.add_argument("-p", required=True, help="Prompt to send to the model.")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum model turns before giving up (default {DEFAULT_MAX_ITERATIONS}).",
    )
    return parser.parse_args()


def run_loop(
    client: OpenAI,
    message_lst: List[ChatCompletionMessageParam],
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> None:
    for iteration in range(1, max_iterations + 1):
        completion = client.chat.completions.create(
            model=get_model_name(),
            messages=message_lst,
            tools=TOOLS,
        )

        if not completion.choices:
            raise RuntimeError("No choices in response")

        message = completion.choices[0].message
        # Normalise to a plain dict. Appending the SDK object works, but it
        # mixes two shapes in one list and carries null fields back to the API.
        message_lst.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            print(message.content)
            return

        # Every tool call in the turn, not just the first. Models routinely
        # emit several in one message, and the API rejects the next request
        # unless every tool_call_id has a matching tool message.
        for tool_call in message.tool_calls:
            print(
                f"[{iteration}] {tool_call.function.name}"
                f"({tool_call.function.arguments})",
                file=sys.stderr,
            )
            message_lst.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": execute_tool_call(tool_call),
                }
            )

    print(
        f"Stopped: reached the {max_iterations}-turn limit without a final answer.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    args = parse_args()
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    messages: List[ChatCompletionMessageParam] = [{"role": "user", "content": args.p}]
    print(f"Using model: {get_model_name()}", file=sys.stderr)
    run_loop(client, messages, max_iterations=args.max_iterations)


if __name__ == "__main__":
    main()
