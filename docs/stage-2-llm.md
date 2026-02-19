# Stage 2 LLM Layer (Initial Implementation)

This document explains the first implementation slice of Stage 2: model/provider agnostic LLM access via LiteLLM.

## What was added

- `src/llm/client.py`
  - `LLMClient` abstract interface.
  - `LiteLLMClient` concrete implementation.
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
```

## Alias file format

`config/model_aliases.yaml` example:

```yaml
summarizer_default:
  model: openai/gpt-4o-mini
  params:
    temperature: 0.2
    max_tokens: 900
embedding_default:
  model: text-embedding-3-small
  params: {}
```

`model` is required. `params` is optional and passed to LiteLLM calls.

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

## Current limitations

- No async interface yet.
- No provider-specific structured output mode (JSON schema API) yet; currently prompt + parse + validate.
- No fallback provider chain yet.
- No token/cost telemetry yet.

These will be addressed in the next Stage 2 increments.
