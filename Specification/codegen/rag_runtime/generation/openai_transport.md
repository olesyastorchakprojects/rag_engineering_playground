# OpenAI-Compatible Chat Completions API

## Endpoint

- method: `POST`
- url: `<OPENAI_COMPATIBLE_URL>` + `/v1/chat/completions`
- headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <TOGETHER_API_KEY>`
- body: JSON object

## Request Shape

```json
{
  "model": "<model_name>",
  "messages": [
    { "role": "system", "content": "<system_prompt>" },
    { "role": "user",   "content": "<user_prompt>" }
  ],
  "temperature": <temperature>
}
```

Field rules:

- `model` — non-empty string
- `messages` — non-empty array; each item is an object with `role` (non-empty string) and `content` (string)
- `temperature` — floating-point number

## Response Shape

Successful response:

- HTTP status `2xx`
- body parses as a JSON object
- `choices` — present, non-empty array
- `choices[0].message` — present, JSON object
- `choices[0].message.content` — present, string
- `usage` — present, JSON object
- `usage.prompt_tokens` — present, non-negative integer
- `usage.completion_tokens` — present, non-negative integer

## Invalid Response

- HTTP status not `2xx`
- body does not parse as a JSON object
- `choices` missing, not an array, or empty
- `choices[0].message.content` missing or not a string
- `usage` missing
- `usage.prompt_tokens` or `usage.completion_tokens` missing or not an integer
