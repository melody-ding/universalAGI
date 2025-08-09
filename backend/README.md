# Chat Backend API

A FastAPI backend with Langchain agent integration for processing chat messages using OpenAI.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your OpenAI API key:
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

3. Run the server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Endpoints

- `GET /` - Health check
- `POST /send-message` - Send a message to the AI agent

### Send Message Request
```json
{
  "message": "Hello, how are you?",
  "conversation_history": [
    {
      "content": "Previous message",
      "role": "user"
    }
  ]
}
```

### Send Message Response
```json
{
  "response": "I'm doing well, thank you for asking!",
  "status": "success"
}
```

## Features

- FastAPI with CORS support for frontend integration
- Langchain agent with OpenAI integration
- Basic tools (weather, calculator)
- Conversation history support
- Error handling