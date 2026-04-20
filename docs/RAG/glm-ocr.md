# GLM-OCR (external)

**GLM-OCR** is a multimodal OCR model developed by zai-org. It extracts text, tables, formulas, and structured fields from documents. It combines a **visual encoder (CogViT)** with a **language decoder (GLM-0.5B)**. Use cases include PDFs, scanned images, technical documents, and **preprocessing text before RAG ingest**—this repository does **not** embed GLM-OCR as a first-party service; treat this page as a **technical reference** for optional upstream pipelines.

## Prerequisites

- Python 3.9+
- pip
- GPU optional
- Hugging Face Hub access (token if the model is gated)

## Installation

1. Install libraries:

```bash
pip install transformers huggingface_hub
```

2. (Optional) Log in to Hugging Face:

```python
from huggingface_hub import login
login(token="YOUR_HUGGINGFACE_TOKEN")
```

3. (Optional) vLLM or other multimodal servers for deployment:

```bash
pip install -U vllm --extra-index-url https://wheels.vllm.ai/nightly
```

## Hugging Face SDK example

```python
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import torch

MODEL_ID = "zai-org/GLM-OCR"

processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, torch_dtype="auto", device_map="auto")

image = Image.open("document.png")

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "url": "document.png"},
            {"type": "text", "text": "Text Recognition:"}
        ],
    }
]

inputs = processor.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt"
).to(model.device)

inputs.pop("token_type_ids", None)

generated_ids = model.generate(**inputs, max_new_tokens=8192)
output = processor.decode(generated_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

print(output)
```

Use `"Table Recognition:"` or `"Formula Recognition:"` instead of the text prompt when targeting tables or formulas.

## Other runtimes

**vLLM**

```bash
vllm serve zai-org/GLM-OCR --allowed-local-media-path / --port 8080
```

**SGLang**

```bash
python -m sglang.launch_server --model zai-org/GLM-OCR --port 8080
```

**Ollama**

```bash
ollama run glm-ocr
```

## Related

- [RAG overview](index.md)
- [Runtime and integration](runtime-and-integration.md) — ingest path for text after OCR
