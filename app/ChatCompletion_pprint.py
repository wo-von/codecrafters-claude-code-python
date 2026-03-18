ChatCompletion(
    id="gen-1773834241-qLVc2qeW59QalBHVSH1E",
    choices=[
        Choice(
            finish_reason="tool_calls",
            index=0,
            logprobs=None,
            message=ChatCompletionMessage(
                content=None,
                refusal=None,
                role="assistant",
                annotations=None,
                audio=None,
                function_call=None,
                tool_calls=[
                    ChatCompletionMessageFunctionToolCall(
                        id="call_866995824aba4aadb09eee0b",
                        function=Function(
                            arguments='{"file_path":"apple.py"}', name="Read"
                        ),
                        type="function",
                        index=0,
                    )
                ],
                reasoning='\nThe user is asking me to open a file called "apple.py". I need to use the Read function to read the contents of this file. The file_path parameter should be "apple.py".',
                reasoning_details=[
                    {
                        "type": "reasoning.text",
                        "text": '\nThe user is asking me to open a file called "apple.py". I need to use the Read function to read the contents of this file. The file_path parameter should be "apple.py".',
                        "format": "unknown",
                        "index": 0,
                    }
                ],
            ),
            native_finish_reason="tool_calls",
        )
    ],
    created=1773834241,
    model="z-ai/glm-4.5-air:free",
    object="chat.completion",
    service_tier=None,
    system_fingerprint=None,
    usage=CompletionUsage(
        completion_tokens=58,
        prompt_tokens=175,
        total_tokens=233,
        completion_tokens_details=CompletionTokensDetails(
            accepted_prediction_tokens=None,
            audio_tokens=0,
            reasoning_tokens=40,
            rejected_prediction_tokens=None,
            image_tokens=0,
        ),
        prompt_tokens_details=PromptTokensDetails(
            audio_tokens=0, cached_tokens=44, cache_write_tokens=0, video_tokens=0
        ),
        cost=0,
        is_byok=False,
        cost_details={
            "upstream_inference_cost": 0,
            "upstream_inference_prompt_cost": 0,
            "upstream_inference_completions_cost": 0,
        },
    ),
    provider="Z.AI",
)
