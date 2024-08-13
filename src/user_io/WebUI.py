from qwen_agent.gui import WebUI
from functions import init_agent_service


def app_gui():
    # Define the agent
    bot = init_agent_service()
    chatbot_config = {
        'prompt.suggestions': [
            'Thời gian ở Hồ Chí Minh bây giờ là bao nhiêu',
            'Thời tiết hiện tại ở Paris là bao nhiêu độ C',
        ]
    }
    WebUI(
        bot,
        chatbot_config=chatbot_config,
    ).run()
