import json
from qwen_agent.llm import get_chat_model
from utils.load_settings import load_settings
from functions.weather import Weather
from functions.timer import Timer
from typing import Dict, List


SETTINGS: Dict = load_settings("./settings.yml")


# Example dummy function hard coded to return the same weather
# In production, this could be your backend API or an external API

def main():
    # Initialize the chat model
    llm_settings: Dict = SETTINGS['llm']
    llm = get_chat_model(llm_settings)

    # Given request of user1
    messages: list = [{
        'role': 'user',
        'content': "Thời tiết ở San Francisco, Paris thế nào? Vậy thì thời tiết ở Asian/Tokyo là mấy giờ?",
    }]

    # Init the function calling
    selected_functions: List[Dict] = [
        Weather.function,
        Timer.function,
    ]

    print('# Assistant Response 1:')
    latest_response = None
    for responses in llm.chat(
            messages=messages,
            functions=selected_functions,
            stream=True,
            extra_generate_cfg=dict(
                # Note: set parallel_function_calls=True to enable parallel function calling
                parallel_function_calls=True,  # Default: False
                # Note: set function_choice='auto' to let the model decide whether to call a function or not
                # function_choice='auto',  # 'auto' is the default if function_choice is not set
                # Note: set function_choice='get_current_weather' to force the model to call this function
                # function_choice='get_current_weather',
            ),
    ):
        latest_response = responses
    print(latest_response)

    messages.extend(latest_response)  # extend conversation with assistant's reply

    # Step 2: check if the model wanted to call a function
    fncall_msgs = [rsp for rsp in responses if rsp.get('function_call', None)]
    if fncall_msgs:
        # Note: the JSON response may not always be valid; be sure to handle errors
        available_functions = {
            'get_current_weather': Weather.get_current_weather,
            'get_current_time_by_timezone': Timer.get_current_time_by_timezone,
        }  # only one function in this example, but you can have multiple

        for msg in fncall_msgs:
            # Step 3: call the function
            print('# Function Call:')
            function_name = msg['function_call']['name']
            if function_name == 'get_current_weather':
                function_to_call = available_functions[function_name]
                function_args = json.loads(msg['function_call']['arguments'])
                function_response = function_to_call(
                    location=function_args.get('location'),
                    unit=function_args.get('unit'),
                )
                print('# Function Response:')
                print(function_response)
                # Step 4: send the info for each function call and function response to the model
                # Note: please put the function results in the same order as the function calls
                messages.append({
                    'role': 'function',
                    'name': function_name,
                    'content': function_response,
                })  # extend conversation with function response
            elif function_name == 'get_current_time_by_timezone':
                function_to_call = available_functions[function_name]
                function_args = json.loads(msg['function_call']['arguments'])
                function_response = function_to_call(
                    timezone_str=function_args.get('timezone'),
                )
                print('# Function Response:')
                print(function_response)
                messages.append({
                    'role': 'function',
                    'name': function_name,
                    'content': function_response,
                })

        print('# Assistant Response 2:')
        for responses in llm.chat(
                messages=messages,
                functions=selected_functions,
                extra_generate_cfg={'parallel_function_calls': True},
                stream=True,
        ):  # get a new response from the model where it can see the function response
            latest_response = responses
        print(latest_response[0]['content'])


if __name__ == '__main__':
    main()
