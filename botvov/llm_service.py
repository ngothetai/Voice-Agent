import json
from typing import Callable, Dict, Any
import os
from burr.core import State, action, when
from burr.core.application import ApplicationBuilder
from burr.core.graph import GraphBuilder
import inspect
from botvov.tool_calling.VOV_channel import VOVChannelProvider
from botvov.tool_calling.Weather import WeatherProvider
from botvov.utils import _get_llm_client, _get_instructor_client, user_query_format, read_channel_list
import datetime
import requests
from botvov.models import ResponseRouter


# Read configurations from environment variables
MODEL_NAME = os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-3B-Instruct')
PROMPT_SYSTEM = os.getenv('PROMPT_SYSTEM', 'You are a helpful assistant. Please answer the following questions to the best of your ability proper Vietnamese.')
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.5'))
ATTEMPTS = int(os.getenv('ATTEMPTS', '10'))


@action(reads=[], writes=["query", "lat", "long"])
def process_input(state: State, user_query:str, lat: str, long: str) -> State:
    """Processes input from user and updates state with the input."""
    return state.append(
        query=user_query_format(user_query)
    ).update(
        lat=lat,
        long=long
    )


@action(reads=["query", "response_agent"], writes=["response_agent", "command"])
def channel_list(state: State) -> State:
    user_query = state["query"]
    channel_respone = VOVChannelProvider.extract_channel_id(user_query)
    channel_list, mapped_channel_list_and_id = read_channel_list()
    
    response_agent = state.get("response_agent", dict({}))
    response_agent["channel_list"] = f"System is playing {mapped_channel_list_and_id[channel_respone.channel_id]} channel for you."
        
    return state.update(
        response_agent=response_agent,
        command={
            "type": "VOV",
            "message_id": channel_respone.channel_id,
            "message": mapped_channel_list_and_id[channel_respone.channel_id]
        }
    )


@action(reads=["query", "response_agent"], writes=["response_agent", "command"])
def broadcast_schedule(state: State) -> State:
    channel_response = VOVChannelProvider.extract_channel_id(state['query'].copy())
    _, mapped_channel_list_and_id = read_channel_list()
    date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%d-%m-%Y")

    response = requests.get(VOVChannelProvider.broadcast_schedule_url.format(channel_id=channel_response.channel_id, start_date=date, end_date=date))
    
    if response.status_code == 200:
        res = VOVChannelProvider._preprocess_broadcast_json(response.json())
        if res:
            response_agent = state.get('response_agent', dict({}))
            response_agent["broadcast_schedule"] = json.dumps({
                f"{mapped_channel_list_and_id[channel_response.channel_id]} broadcast schedule": res
            })
            return state.update(
                response_agent=response_agent,
                command={
                    "type": "broadcast_schedule",
                    "message_id": str(channel_response.channel_id),
                    "message": response.json()['data']
                }
            )
    response_agent = state.get('response_agent', dict({}))
    response_agent["broadcast_schedule"] = "Error while fetching data from VOV provider"
    return state.update(
        response_agent=response_agent,
        command={
            "type": "broadcast_schedule",
            "message_id": None,
            "message": None
        }
    )


@action(reads=[], writes=["response_agent", "command"])
def current_time(state: State) -> State:
    ai = _get_llm_client()
    res = ai.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": f"""
                You are a professional clock, use the information extracted from computer data and provide the current time for the audience to know.
                
                <current_time>
                    {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%d-%m-%Y %H:%M:%S")}
                </current_time>
                """
            }
        ],
    )
    response_agent = state.get('response_agent', dict({}))
    response_agent["current_time"] = res.choices[0].message.content
    return state.update(
        response_agent=response_agent,
        command={
            "type": "time",
            "message_id": None,
            "message": None
        }
    )


@action(reads=["lat", "long", "response_agent"], writes=["response_agent", "command"])
def weather(state: State) -> State:
    lat = str(round(float(state['lat']), 2))
    long = str(round(float(state['long']), 2))
    response = requests.get(WeatherProvider.open_weather_url.format(lat=lat, lon=long, API_key=WeatherProvider.API_key))
    if response.status_code == 200:
        response_agent: Dict = state.get('response_agent', dict({}))
        response_agent["weather"] = WeatherProvider._summary_weather(response.json())
        return state.update(
            response_agent=response_agent,
            command={
                "type": "weather",
                "message_id": None,
                "message": response.json()
            }
        )
    else:
        response_agent = state.get('response_agent', dict({}))
        response_agent["weather"] = "Error while fetching data from OpenWeather"
        return state.update(
            response_agent=response_agent,
            command={
                "type": "weather",
                "message_id": None,
                "message": None
            }
        )
        

@action(reads=["query", "command"], writes=["next_agent"])
def router(state: State) -> State:
    """Selects the tool + assigns the parameters. Uses the tool-calling API."""
    query = state["query"].copy()
    
    messages = [
        {
            "role": "system",
            "content": ("""
                You are a world-class router. Your task is to route the user query to the correct next agent in a list agents below.
                The agents can handle the related task that user asked or provide the information that user asked.
                But if the user query is not actually related to any agents, you must return fallback.
                Choose carefully because if the question is not related to any agent and you still call that agent, something bad will happen.
                
                You can access agents: 
                [
                    {
                        "agent_name": "channel_list",
                        "description": "Agent can access the list of VOV channels, play/open the channel. It can handle tasks like: 'Play VOV1 channel', 'Open VOV2 channel', 'List all VOV channels',..." 
                    },
                    {
                        "agent_name": "current_time",
                        "description": "Agent can provide the current time. It can handle tasks like: 'What time is it now?', 'What is the current time?',..."
                    },
                    {
                        "agent_name": "broadcast_schedule",
                        "description": "Agent can provide the broadcast schedule of VOV channels. It can handle tasks like: 'What is the broadcast schedule of VOV1 channel?', 'What is the schedule of VOV2 channel?',..."
                    },
                    {
                        "agent_name": "weather",
                        "description": "Agent can provide the weather information of the location. It can handle tasks like: 'What is the weather?'."
                    },
                    {
                        "agent_name": "fallback",
                        "description": "You can handle yourself the user query that is not related to any agent."
                    }
                ]
                Please route the user query to the correct agent by agent name.
                Example:
                - user_query: "What is the weather like?"
                - next_agent: "weather"
                
                - user_query: "What is the broadcast schedule of VOV1 channel?"
                - next_agent: "broadcast_schedule"
                
                - user_query: "Open VOV1"
                - next_agent: "channel_list"
                
                - user_query: "What time is it now?"
                - next_agent: "current_time"
                
                - user_query: "Show me the food population in Hanoi?"
                - next_agent: "fallback"
            """),
        }
    ] + query
    
    choice = _get_instructor_client().chat.completions.create(
        model=MODEL_NAME, 
        messages=messages,
        temperature=TEMPERATURE,
        top_p=0.8,
        response_model=ResponseRouter
    )

    return state.update(
        next_agent=choice.choice
    )


@action(reads=["query", "response_agent"], writes=["final_output", "query"])
def format_results(state: State) -> State:
    response_agent = state.get("response_agent", {})
    query = state["query"].copy()
    
    content = """
You are a world-class assistant.
Your task is to write final answer for user query accurately and only in Vietnamese.
Extract the context below, and answer the final information as detailed as possible, eliminate all redundant information and unnecessary context.
Please answer naturaly, clearly and shorty in Vietnamese, providing only the final information that user should be know. If the user query is not enough information, you can ask for more information.
And you must answer like a human speak. Example: if now clock is 2022-12-15 22:16:41, you must answer "Bây giờ là 10 giờ 30 phút sáng ngày 20 tháng 10 năm 2022".
    """
    
    # Add the response agent to the query
    for key, value in response_agent.items():
        content += f"""\n
        <{key}>
            {value}
        </{key}>
        """
    
    messages = [
            {
                "role": "system",
                "content": content
            }
        ] + query
    
    response = _get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE,
    )
    
    final_output = response.choices[0].message.content
    
    # rewrite the final output
    rewrite = _get_llm_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": """
                You are a professional content editor in Vietnamese, use a text and rewrite it in a more professional and shorten way, and make sure all words are in Vietnamese.
                If any paragraph in the text contains a long list, replace it with a summary of the main idea of ​​that paragraph or provide general information.
                """
            },
            {
                "role": "user",
                "content": final_output
            }
        ],
    ).choices[0].message.content

    # detele the response agent of the channel_list
    if "channel_list" in response_agent:
        state["response_agent"].pop("channel_list")
    
    return state.update(
        final_output=rewrite
    ).append(
        query={
            "role": "assistant",
            "content": rewrite
        }
    )


def build_graph():
    """Builds the application."""
    return (
        GraphBuilder()
        .with_actions(
            process_input,
            router,
            format_results,
            channel_list,
            broadcast_schedule,
            current_time,
            weather,
        )
        .with_transitions(
            ("process_input", "router"),
            ("router", "channel_list", when(next_agent="channel_list")),
            ("router", "broadcast_schedule", when(next_agent="broadcast_schedule")),
            ("router", "current_time", when(next_agent="current_time")),
            ("router", "weather", when(next_agent= "weather")),
            ("router", "format_results", when(next_agent= "fallback")),
            (["channel_list", "broadcast_schedule", "current_time", "weather"],  "format_results"),
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