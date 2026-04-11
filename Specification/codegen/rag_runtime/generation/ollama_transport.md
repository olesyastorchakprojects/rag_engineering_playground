# Ollama Chat API

## Endpoint

- method: `POST`
- url: `<OLLAMA_URL>` + `/api/chat`
- body: JSON object

## Request Shape

```json
{
  "model": "<model_name>",
  "messages": [
    { "role": "system", "content": "<system_prompt>" },
    { "role": "user",   "content": "<user_prompt>" }
  ],
  "stream": false,
  "options": {
    "temperature": <temperature>
  }
}
```

Field rules:

- `model` — non-empty string
- `messages` — non-empty array; each item is an object with `role` (non-empty string) and `content` (string)
- `stream` — boolean; must be `false`
- `options.temperature` — floating-point number

## Response Shape

Successful response:

- HTTP status `2xx`
- body parses as a JSON object
- `message` — present, JSON object
- `message.content` — present, string

## Invalid Response

- HTTP status not `2xx`
- body does not parse as a JSON object
- `message` missing or not a JSON object
- `message.content` missing or not a string
