# LLM coding agent

A small coding agent: a loop that sends a prompt to a model over an
OpenAI-compatible API, executes whatever tools the model asks for, feeds the
results back, and repeats until the model answers without requesting a tool.

Built from the CodeCrafters "Build your own Claude Code" challenge, then
extended past the challenge stages with the failure handling a loop like this
needs before it can be run unattended.

## Running it

```bash
export OPENROUTER_API_KEY=...
uv run app/main.py -p "Count the Python files in this repo and summarise what each one does"
```

| Variable | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | — | required |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | any OpenAI-compatible endpoint |
| `LOCAL` | `false` | `true` selects a free model instead of the paid one |

`--max-iterations N` bounds the number of model turns (default 25).

Tool calls are logged to stderr as they execute; the model's final answer goes
to stdout, so the agent composes with pipes.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `read_file` | `file_path` | file contents |
| `write_file` | `file_path`, `content` | number of characters written |
| `bash_cmd` | `command` | `exit_code=N` followed by combined stdout and stderr |

Each is declared to the model as a JSON-Schema function specification.

## How the loop handles failure

The interesting part of an agent loop is not the happy path. Four things
decide whether a run survives contact with a model that makes mistakes:

**Every tool call in a turn is executed, not just the first.** Models
routinely emit several tool calls in one message. The API rejects the next
request unless every `tool_call_id` has a matching `tool` message, so
executing only the first both loses work and breaks the conversation.

**Tool failures are returned to the model, not raised.** Malformed JSON
arguments, a missing required field, a file that is not there, an unknown tool
name — each comes back as a string the model can read and react to. Raising
would end the run on the model's first mistake, which is the opposite of what
the loop is for.

**`bash_cmd` reports its exit code and times out.** Without the exit code the
model sees the stderr of a failed command with no reliable way to know it
failed. Without the timeout, one command that never returns hangs the run.

**Output is bounded on both axes.** Tool results are truncated at 20,000
characters so a single large file cannot fill the context window, and the loop
stops after a fixed number of turns rather than trusting the model to decide
it is finished.

## Scope

`bash_cmd` runs arbitrary shell commands as the invoking user, with no
sandbox. That is fine for a local tool run against a repo you own and is not
fine for anything else; isolating it would mean a container or a seccomp
profile, which this does not have.

There is no evaluation harness here — no task set, no scoring, no reward. The
agent is the thing that would be evaluated, not the evaluator.
