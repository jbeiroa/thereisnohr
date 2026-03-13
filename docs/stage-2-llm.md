# Stage 2 LLM Layer (Completed)

This document explains the current Stage 2 implementation: model/provider agnostic LLM access via LiteLLM.

## What was added

- `src/llm/client.py`
  - `LLMClient` abstract interface.
  - `LiteLLMClient` concrete implementation.
  - Async methods and metadata-returning variants.
- `src/llm/registry.py`
  - Loads model aliases from YAML and validates shape.
- `src/llm/types.py`
  - Typed model alias structure.
- `src/llm/factory.py`
  - Constructs a default LiteLLM client from runtime settings.
- `config/model_aliases.yaml`
  - Alias map for summarizer/extractor/explainer/embedding models.

## Why this design

1. Provider decoupling
- Application code should call a stable interface (`LLMClient`) instead of provider SDKs directly.

2. Alias-based routing
- Feature code references aliases like `summarizer_default`, while environment/config controls real model/provider targets.

3. Structured outputs as contract
- Candidate extraction/summarization steps need predictable JSON schemas.
- `generate_structured` validates response payloads using Pydantic models and retries on malformed output.

4. Retry-first reliability
- LLM output can be malformed; a bounded retry budget improves robustness without creating infinite loops.

## Configuration

`Settings` additions in `src/core/config.py`:

- `model_aliases_path`
- `extractor_model_alias`
- `explainer_model_alias`
- `llm_timeout_seconds`
- `llm_max_retries`

Environment variables in `.env`:

```env
MODEL_ALIASES_PATH=./config/model_aliases.yaml
EXTRACTOR_MODEL_ALIAS=extractor_default
EXPLAINER_MODEL_ALIAS=explainer_default
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
OPENAI_API_KEY=your-openai-api-key
```

## Alias file format

`config/model_aliases.yaml` example:

```yaml
summarizer_default:
  default_model: ollama/llama3.2:3b
  default_litellm_params:
    temperature: 0.2
    max_tokens: 900
  fallbacks:
    - model: openai/gpt-4o-mini
      litellm_params:
        temperature: 0.2
        max_tokens: 900
  fallback_policy:
    num_retries: 2
embedding_default:
  default_model: ollama/embeddinggemma
  default_litellm_params: {}
  fallbacks:
    - model: openai/text-embedding-3-small
      litellm_params: {}
  fallback_policy:
    num_retries: 1
```

`default_model` is required. `default_litellm_params`, `fallbacks`, and `fallback_policy` are optional.

## Usage examples

### Structured generation

```python
from pydantic import BaseModel
from src.llm.factory import build_default_llm_client


class Summary(BaseModel):
    name: str
    score: float


client = build_default_llm_client()
summary = client.generate_structured(
    prompt="Return JSON with fields name and score",
    schema=Summary,
    model_alias="summarizer_default",
)
```

### Embeddings

```python
from src.llm.factory import build_default_llm_client

client = build_default_llm_client()
vectors = client.embed(["candidate A", "candidate B"], "embedding_default")
```