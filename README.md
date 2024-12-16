# BOTVOV

An AI assistant that supports answering questions and performing tasks from users, with speech-to-text and text-to-speech capabilities.

## Features

- Speech-to-Text conversion using Whisper models
- Text-to-Speech synthesis 
- LLM-based conversational AI
- RESTful API interface
- WebSocket support for real-time communication

## Prerequisites

- Python 3.10 or higher
- pip
- poetry
- Docker

## Deployment

```bash
sudo make run
```

## Configuration
The project can be configured through:

* llm.yaml - LLM settings
* models.yaml - Model configurations
* params.yaml - General paramters
* text2speech - TTS settings


## API Endpoints

* /botvov/


## Project Structure

```
BOTVOV/
├── botvov/                    # Source code của dự án
│   ├── main.py             # Tệp chính chạy ứng dụng
│   ├── utils.py            # Các hàm tiện ích
│   └── models/             # Thư mục chứa các định nghĩa mô hình
│       ├── user_model.py   # Mô hình dữ liệu người dùng
│       └── product_model.py # Mô hình dữ liệu sản phẩm
├── docs/                   # Tài liệu dự án
│   └── README.md           # README cho tài liệu
├── .gitignore              # Tệp để bỏ qua các tệp/thư mục không cần commit vào Git
├── requirements.txt        # Danh sách các thư viện cần thiết
├── Dockerfile              # Dockerfile để đóng gói ứng dụng
└── README.md               # Tệp hướng dẫn sử dụng dự án
```

