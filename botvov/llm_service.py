from ast import List
import instructor
from openai import OpenAI
import json
from typing import Callable, Dict, Tuple, Any
import base64
import os
import functools

from burr.core import State, action, when
from burr.core.application import ApplicationBuilder
from burr.core.graph import GraphBuilder
import inspect
import requests
from botvov.tool_calling.VOV import VOVChannelProvider
from botvov.tool_calling.Timer import TimeProvider
from botvov.tool_calling.Weather import WeatherProvider
from botvov.tool_calling.Broadcast import VOVChannelBroadcastSchedule


# Read configurations from environment variables
MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-3B-Instruct')
PROMPT_SYSTEM = os.getenv('PROMPT_SYSTEM', 'You are a helpful assistant. Please answer the following questions to the best of your ability proper Vietnamese.')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.5'))
ATTEMPTS = int(os.getenv('ATTEMPTS', '10'))

# Init some tool calling
vov_channel_provider = VOVChannelProvider()
time_provider = TimeProvider()
weather_provider = WeatherProvider()
broadcast_schedule_provider = VOVChannelBroadcastSchedule()


def encode_audio_to_base64(file_bytes: bytes) -> str:
    encoded_string = base64.b64encode(file_bytes).decode('utf-8')
    return encoded_string


def user_query_format(user_query: str):
    return {
        "role": "user",
        "content": user_query
    }
    
def assistant_response_format(assistant_response: str):
    return {
        "role": "assistant",
        "content": assistant_response
    }


@functools.lru_cache
def _get_llm_client():
    assistant = OpenAI(
        api_key="cant-be-empty",
        base_url="http://llm_serve:8000/v1",
    )
    return assistant


@functools.lru_cache
def _get_instructor_client():
    assistant = _get_llm_client()
    return instructor.from_openai(assistant)


@action(reads=["query"], writes=["query", "lat", "long"])
def process_input(state: State, user_query, lat, long) -> State:
    """Processes input from user and updates state with the input."""
    return state.append(
        query=user_query_format(user_query)
    ).update(
        lat=lat,
        long=long
    )


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
        "query_channels": vov_channel_provider._get_channel_list,
        "query_time": time_provider._get_current_time,
        "query_weather": weather_provider._query_weather,
        "query_broadcast_schedule": broadcast_schedule_provider._get_broadcast_schedule,
        "fallback_tool": _fallback_tool,
    }.items()
]

@action(reads=["query", "lat", "long"], writes=["tool_parameters", "tool"])
def select_tool(state: State) -> State:
    """Selects the tool + assigns the parameters. Uses the tool-calling API."""
    
    query = state["query"]
    
    messages = [
        {
            "role": "system",
            "content": (f"""
                You are a helpful assistant. Use the supplied tools to assist the user, if they apply in any way. Remember to use the tools! They can do stuff you can't.
                If you can't use only the tools provided to answer the question but know the answer, please provide the answer
                If you cannot use the tools provided to answer the question, use the fallback tool and provide a reason.
                Again, if you can't use one tool provided to answer the question, use the fallback tool and provide a reason.
                You must select exactly one tool no matter what, filling in every parameters with your best guess. Do not skip out on parameters!
                
                <location>
                    "latitute": {state['lat']}, "longitute": {state['long']}
                </location>
            """),
        }
    ] + query
    
    response = _get_llm_client().chat.completions.create(
        model=MODEL_NAME, 
        messages=messages,
        tools=ASSISTANT_TOOLS,
        temperature=TEMPERATURE,
    )
    
    # Extract the tool name and parameters from OpenAI's response
    if len(response.choices[0].message.tool_calls) == 0:
        return state.update(
            tool="fallback_tool",
            tool_parameters={
                "response": f"No tool was selected, instead response was: {response.choices[0].message}."
            },
        )
    fn = response.choices[0].message.tool_calls[0].function

    return state.update(tool=fn.name, tool_parameters=json.loads(fn.arguments))

@action(reads=["tool_parameters"], writes=["tool_response"])
def call_tool(state: State, tool_function: Callable) -> State:
    """Action to call the tool. This will be bound to the tool function."""
    response = tool_function(**state["tool_parameters"])
    return state.update(tool_response=response)


def _fallback_action(response: str) -> Dict[str, Any]:
    """Tells the user that the assistant can't do any action -- this should be a fallback"""
    return {
        "action response": response,
        "command": {
            "name": "open_channel",
            "content": None
        }
    }

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
        "open_channel": vov_channel_provider._open_channel,
        "show_time": time_provider._show_time,
        "show_weather": weather_provider._show_weather,
        "show_broadcast_schedule": broadcast_schedule_provider._show_broadcast_schedule,
        "fallback_action": _fallback_action,
    }.items()
]

@action(reads=["query","tool_response"], writes=["action_parameters","action"])
def select_action(state: State) -> State:
    """Action to synthetic the results and do the needed action.
    """
    
    query = state["query"]
    
    response = _get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": f"""
                    You are a helpful assistant. Use the supplied actions to assist the user, if they apply in any way. Remember to use the actions!
                    They can perform some actions, control some devices, and specially show detail information to screen that you cannot do yourself.
                    If you can't use only the actions provided to help the user requirements but know how to do, please provide the answer
                    If you cannot use the actions provided to meet user requirements, use the fallback tool and provide a reason.
                    Again, if you can't use one action provided to answer the user requirements, use the fallback tool and provide a reason.
                    You must select exactly one action no matter what, filling in every parameters with your best guess. Do not skip out on parameters!
                
                <tool_response>
                    {state['tool_response']}
                </tool_response>
                """
                ,
            }
        ] + query,
        tools=ASSISTANT_ACTIONS,
        temperature=TEMPERATURE,
    )
    # Extract the tool name and parameters from OpenAI's response
    if len(response.choices[0].message.tool_calls) == 0:
        return state.update(
            action="fallback_action",
            action_parameters={
                "response": f"No action was selected, instead response was: {response.choices[0].message}."
            },
        )
    else:
        fn = response.choices[0].message.tool_calls[0].function
        return state.update(action=fn.name, action_parameters=json.loads(fn.arguments))

@action(reads=["action_parameters"], writes=["action_response","command"])
def call_action(state: State, action_function: Callable) -> State:
    """Action to call the tool. This will be bound to the tool function."""
    result = action_function(**state["action_parameters"])
    response = result.get("action response")
    command = result.get("data")
    return state.update(action_response=response).update(command=command)

@action(reads=["query", "action_response", "tool_response"], writes=["final_output"])
def format_results(state: State) -> State:
    """Action to format the results in a usable way. Note we're not cascading in context for the chat history.
    This is largely due to keeping it simple, but you'll likely want to pass IDs around or maintain the chat history yourself
    """
    
    query = state["query"]
    
    messages = [
            {
                "role": "system",
                "content": f"""
                    You are a helpful assistant.
                    Your task is to answer briefly, accurately and only in Vietnamese.
                    Extract and answer the final information as detailed as possible, eliminate all redundant information and unnecessary context.
                    Please answer briefly in Vietnamese, providing only the final information that directly answers the user's question.
                <tool_response>
                    {state['tool_response']}
                </tool_response>
                
                
                <action_response>
                    {state['action_response']}
                </action_response>
                """
                ,
            }
        ] + query
    response = _get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE,
    )
    final_output = response.choices[0].message.content
    
    # history_message = [
    #     messages[1],
        
    # ]

    return state.update(
        final_output=final_output
    ).append(
        query=messages[1]
    ).append(
        query={
            "role": "assistant",
            "content": f"""
                <tool_response>
                    {state['tool_response']}
                </tool_response>
                
                
                <action_response>
                    {state['action_response']}
                </action_response>
                
                {final_output}
            """
        }
    )


def build_graph():
    """Builds the application."""
    return (
        GraphBuilder()
        .with_actions(
            process_input,
            select_tool,
            select_action,
            format_results,
            query_channels=call_tool.bind(tool_function=vov_channel_provider._get_channel_list),
            query_time=call_tool.bind(tool_function=time_provider._get_current_time),
            query_weather=call_tool.bind(tool_function=weather_provider._query_weather),
            query_broadcast_schedule=call_tool.bind(tool_function=broadcast_schedule_provider._get_broadcast_schedule),
            fallback_tool=call_tool.bind(tool_function=_fallback_tool),
            open_channel=call_action.bind(action_function=vov_channel_provider._open_channel),
            show_time=call_action.bind(action_function=time_provider._show_time),
            show_weather=call_action.bind(action_function=weather_provider._show_weather),
            show_broadcast_schedule=call_action.bind(action_function=broadcast_schedule_provider._show_broadcast_schedule),
            fallback_action=call_action.bind(action_function=_fallback_action),
        )
        .with_transitions(
            ("process_input", "select_tool"),
            ("select_tool", "query_channels", when(tool="query_channels")),
            ("select_tool", "query_time", when(tool="query_time")),
            ("select_tool", "query_weather", when(tool="query_weather")),
            ("select_tool", "query_broadcast_schedule", when(tool="query_broadcast_schedule")),
            ("select_tool", "fallback_tool", when(tool="fallback_tool")),
            (["query_channels", "query_time", "query_weather", "query_broadcast_schedule", "fallback_tool"], "select_action"),
            ("select_action", "open_channel", when(action="open_channel")),
            ("select_action", "fallback_action", when(action="fallback_action")),
            ("select_action", "show_time", when(action="show_time")),
            ("select_action", "show_weather", when(action="show_weather")),
            ("select_action", "show_broadcast_schedule", when(action="show_broadcast_schedule")),
            (["open_channel", "show_time", "show_weather", "show_broadcast_schedule", "fallback_action"], "format_results"),
            ("format_results", "process_input"),
        )
        .build()
    )
    
if __name__ == "__main__":
    app = (ApplicationBuilder()
        .with_graph(build_graph())
        .with_entrypoint("process_input")
        .with_tracker(project="botvov", use_otel_tracing=True)
        ).build()
    app.visualize(output_file_path="./botvov.png")
    action, result, state = app.run(
        halt_after=["format_results"],
        inputs={
            "user_query": "Mở giúp tôi kênh v o v 3",
        },
    )
    print(state['final_output'])