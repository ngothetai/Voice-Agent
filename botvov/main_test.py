import instructor
from openai import OpenAI
import json
from typing import Callable, Dict
import base64
import os
import functools

from burr.core import State, action, when
from burr.core.application import ApplicationBuilder
import inspect



# Read configurations from environment variables
MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-3B-Instruct')
PROMPT_SYSTEM = os.getenv('PROMPT_SYSTEM', 'You are a helpful assistant. Please answer the following questions to the best of your ability proper Vietnamese.')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.5'))
ATTEMPTS = int(os.getenv('ATTEMPTS', '10'))


def encode_audio_to_base64(file_bytes: bytes) -> str:
    encoded_string = base64.b64encode(file_bytes).decode('utf-8')
    return encoded_string


@functools.lru_cache
def _get_llm_client():
    assistant = OpenAI(
        api_key="cant-be-empty",
        base_url="http://localhost:8000/v1",
    )
    return assistant


@functools.lru_cache
def _get_instructor_client():
    assistant = _get_llm_client()
    return instructor.from_openai(assistant)

### Define the calling tools for the assistant

@action(reads=[], writes=["query"])
def process_input(state: State, user_query) -> State:
    """Processes input from user and updates state with the input."""
    return state.update(
        query=user_query
    )

def _get_channel_list(provider: str) -> Dict[str, Dict[str, str]]:
    """
    Get the list of channel from provider.
    There are two available providers: vov and vtv
    """
    #@TODO: Change to get from API with vov or vtv provider
    json_channels = json.load(open("./chanels_vov.json", "r"))
    # mapped_channel_list_and_id: Dict[str, str] = dict()
    # for it in json_channels.values():
    #     for channel in it:
    #         mapped_channel_list_and_id[channel['id']] = channel['name']
    return {
        "channels": json_channels,
        # "mapped_channel_list_and_id": mapped_channel_list_and_id
    }

def _fallback_tool(response: str) -> Dict[str, str]:
    """Tells the user that the assistant can't do that -- this should be a fallback"""
    return {"response": response}


TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


ASSISTANT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": fn_name,
            "description": fn.__doc__ or fn_name,
            "parameters": {
                "type": "object",
                "properties": {
                    param.name: {
                        "type": TYPE_MAP.get(param.annotation)
                        or "string",  # TODO -- add error cases
                        "description": param.name,
                    }
                    for param in inspect.signature(fn).parameters.values()
                },
                "required": [param.name for param in inspect.signature(fn).parameters.values()],
            },
        },
    }
    for fn_name, fn in {
        "query_channels": _get_channel_list,
        "fallback_tool": _fallback_tool,
    }.items()
]

@action(reads=["query"], writes=["tool_parameters", "tool"])
def select_tool(state: State) -> State:
    """Selects the tool + assigns the parameters. Uses the tool-calling API."""
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Use the supplied tools to assist the user, if they apply in any way. Remember to use the tools! They can do stuff you can't."
                "If you can't use only the tools provided to answer the question but know the answer, please provide the answer"
                "If you cannot use the tools provided to answer the question, use the fallback tool and provide a reason. "
                "Again, if you can't use one tool provided to answer the question, use the fallback tool and provide a reason. "
                "You must select exactly one tool no matter what, filling in every parameters with your best guess. Do not skip out on parameters!"
            ),
        },
        {
            "role": "user",
            "content": state["query"]
        }
    ]
    
    response = _get_llm_client().chat.completions.create(
        model=MODEL_NAME, 
        messages=messages,
        tools=ASSISTANT_TOOLS,
    )
    
    # Extract the tool name and parameters from OpenAI's response
    if response.choices[0].message.tool_calls is None:
        return state.update(
            tool="fallback_tool",
            tool_parameters={
                "response": "No tool was selected, instead response was: {response.choices[0].message}."
            },
        )
    fn = response.choices[0].message.tool_calls[0].function

    return state.update(tool=fn.name, tool_parameters=json.loads(fn.arguments))

@action(reads=["tool_parameters"], writes=["tool_response"])
def call_tool(state: State, tool_function: Callable) -> State:
    """Action to call the tool. This will be bound to the tool function."""
    response = tool_function(**state["tool_parameters"])
    return state.update(tool_response=response)


### Define the actions for the assistant

def _open_channel(channel_id: str) -> Dict[str, str]:
    """
    Open the channel with the given id.
    """
    #@TODO: Implement: Change to open the channel with the given id
    return {"Application response": f"Radio is opening the channel with the id: {channel_id}. Wait for a moment."}

def _fallback_action(response: str) -> Dict[str, str]:
    """Tells the user that the assistant can't do that -- this should be a fallback"""
    return {"response": response}

ASSISTANT_ACTIONS = [
    {
        "type": "function",
        "function": {
            "name": fn_name,
            "description": fn.__doc__ or fn_name,
            "parameters": {
                "type": "object",
                "properties": {
                    param.name: {
                        "type": TYPE_MAP.get(param.annotation)
                        or "string",  # TODO -- add error cases
                        "description": param.name,
                    }
                    for param in inspect.signature(fn).parameters.values()
                },
                "required": [param.name for param in inspect.signature(fn).parameters.values()],
            },
        },
    }
    for fn_name, fn in {
        "open_channel": _open_channel,
        "fallback_action": _fallback_action,
    }.items()
]

@action(reads=["query","tool_response"], writes=["action_parameters","action"])
def select_action(state: State) -> State:
    """Action to synthetic the results and do the needed action.
    """
    response = _get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                "You are a helpful assistant. Use the supplied actions to assist the user, if they apply in any way. Remember to use the actions!"
                "They can perform some actions, or control some devices that you cannot do yourself."
                "If you can't use only the actions provided to help the user requirements but know how to do, please provide the answer"
                "If you cannot use the actions provided to meet user requirements, use the fallback tool and provide a reason. "
                "Again, if you can't use one action provided to answer the user requirements, use the fallback tool and provide a reason. "
                "You must select exactly one action no matter what, filling in every parameters with your best guess. Do not skip out on parameters!"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"The original question was: {state['query']}."
                    f"The context data is: {state['tool_response']}."
                ),
            },
        ],
        tools=ASSISTANT_ACTIONS,
    )
    # Extract the tool name and parameters from OpenAI's response
    if response.choices[0].message.tool_calls is None:
        return state.update(
            action="fallback_action",
            action_parameters={
                "response": "No action was selected, instead response was: {response.choices[0].message}."
            },
        )
    fn = response.choices[0].message.tool_calls[0].function

    return state.update(action=fn.name, action_parameters=json.loads(fn.arguments))

@action(reads=["action_parameters"], writes=["action_response"])
def call_action(state: State, action_function: Callable) -> State:
    """Action to call the tool. This will be bound to the tool function."""
    response = action_function(**state["action_parameters"])
    return state.update(action_response=response)

@action(reads=["query", "action_response", "tool_response"], writes=["final_output"])
def format_results(state: State) -> State:
    """Action to format the results in a usable way. Note we're not cascading in context for the chat history.
    This is largely due to keeping it simple, but you'll likely want to pass IDs around or maintain the chat history yourself
    """
    response = _get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. You answer use question proper Vietnamese."
                    "Your goal is to take the"
                    "data presented and use it to answer the original question:"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"The original question was: {state['query']}."
                    f"The response from tool calling is: {state['tool_response']}."
                    f"The response from action calling is: {state['action_response']}."
                    "Please format the data and provide a response that responds to the original query."
                ),
            },
        ],
    )

    return state.update(final_output=response.choices[0].message.content)


def application():
    """Builds the application."""
    return (
        ApplicationBuilder()
        .with_actions(
            process_input,
            select_tool,
            select_action,
            format_results,
            query_channels=call_tool.bind(tool_function=_get_channel_list),
            fallback_tool=call_tool.bind(tool_function=_fallback_tool),
            open_channel=call_action.bind(action_function=_open_channel),
            fallback_action=call_action.bind(action_function=_fallback_action),
        )
        .with_transitions(
            ("process_input", "select_tool"),
            ("select_tool", "query_channels", when(tool="query_channels")),
            ("select_tool", "fallback_tool", when(tool="fallback_tool")),
            (["query_channels", "fallback_tool"], "select_action"),
            ("select_action", "open_channel", when(action="open_channel")),
            ("select_action", "fallback_action", when(action="fallback_action")),
            (["open_channel", "fallback_action"], "format_results"),
            ("format_results", "process_input"),
        )
        .with_entrypoint("process_input")
        .with_tracker(project="botvov", use_otel_tracing=True)
        .build()
    )
    
if __name__ == "__main__":
    app = application()
    app.visualize(output_file_path="./botvov.png")
    action, result, state = app.run(
        halt_after=["format_results"],
        inputs={
            "user_query": "bật giúp tôi kênh v o v một",
        },
    )
    print(state['final_output'])