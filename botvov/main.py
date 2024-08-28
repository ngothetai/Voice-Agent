from flask import Flask, request, jsonify
from botvov.assistant import QwenAssistant

app = Flask(__name__)
assistant = QwenAssistant()

@app.route('/chat', methods=['POST'])
def chat():
    message = request.json.get('message')
    if not message:
        return jsonify({"error": "No message provided"}), 400

    response = assistant.chat(message)
    print(response)
    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
