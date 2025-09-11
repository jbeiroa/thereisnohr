---
language:
- en
license: apache-2.0
tags:
- mlx
- mlx
datasets:
- cerebras/SlimPajama-627B
- bigcode/starcoderdata
- HuggingFaceH4/ultrachat_200k
- HuggingFaceH4/ultrafeedback_binarized
widget:
- text: '<|system|>

    You are a chatbot who can help code!</s>

    <|user|>

    Write me a function to calculate the first 10 digits of the fibonacci sequence
    in Python and print it out to the CLI.</s>

    <|assistant|>

    '
base_model: mlx-community/TinyLlama-1.1B-Chat-v1.0-mlx
---

# jbeiroa/tinyllama-mlx-ft

The Model [jbeiroa/tinyllama-mlx-ft](https://huggingface.co/jbeiroa/tinyllama-mlx-ft) was
converted to MLX format from [mlx-community/TinyLlama-1.1B-Chat-v1.0-mlx](https://huggingface.co/mlx-community/TinyLlama-1.1B-Chat-v1.0-mlx)
using mlx-lm version **0.20.4**.

## Use with mlx

```bash
pip install mlx-lm
```

```python
from mlx_lm import load, generate

model, tokenizer = load("jbeiroa/tinyllama-mlx-ft")

prompt="hello"

if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template is not None:
    messages = [{"role": "user", "content": prompt}]
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

response = generate(model, tokenizer, prompt=prompt, verbose=True)
```
