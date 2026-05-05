from openai import OpenAI

client = OpenAI(
    api_key="sk-6ae4842ab0dc4d57a60323a4a0147f7b",
    base_url="https://api.deepseek.com/v1"
)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "请用一句话介绍自己"}],
    max_tokens=100
)
print(response.choices[0].message.content)