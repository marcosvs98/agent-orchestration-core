**GLM‑OCR** is a multimodal OCR model developed by zai‑org, designed to extract text, tables, formulas, and structured fields from documents in a contextualized manner. It combines a **visual encoder (CogViT)** with a **language decoder (GLM‑0.5B)**, allowing it not only to recognize characters but also to understand the structure and content of documents. Its purpose is to support corporate and production scenarios, such as data extraction from PDFs, scanned images, technical documents, preprocessing for RAG/NLP, and data automation workflows, providing structured and adaptable output.

---

## Prerequisites

* Python 3.9+
* pip
* GPU for efficient use (optional)
* Access to Hugging Face Hub (token required if the model is private)

---

## Installation

1. Install required libraries:

```bash
pip install transformers huggingface_hub
```

2. (Optional) Log in to Hugging Face:

```python
from huggingface_hub import login
login(token="YOUR_HUGGINGFACE_TOKEN")
```

3. Install vLLM or other multimodal servers if you plan to deploy on a server (optional):

```bash
pip install -U vllm --extra-index-url https://wheels.vllm.ai/nightly
```

---

## Download and Use via Hugging Face SDK

```python
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import torch

MODEL_ID = "zai-org/GLM-OCR"

# Download the model and processor
processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForImageTextToText.from_pretrained(MODEL_ID, torch_dtype="auto", device_map="auto")

# Load image
image = Image.open("document.png")

# Prepare message for OCR
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "url": "document.png"},
            {"type": "text", "text": "Text Recognition:"}  # Can also be "Table Recognition:" or "Formula Recognition:"
        ],
    }
]

# Preprocessing
inputs = processor.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt"
).to(model.device)

inputs.pop("token_type_ids", None)

# Generate output
generated_ids = model.generate(**inputs, max_new_tokens=8192)
output = processor.decode(generated_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

print(output)
```

This code automatically downloads the model, processes the image, and returns the recognized text. The same approach can be used for tables and formulas by changing the prompt from `"Text Recognition:"` to `"Table Recognition:"` or `"Formula Recognition:"`.

---

## Additional Execution Modes

1. **vLLM Server**

```bash
vllm serve zai-org/GLM-OCR --allowed-local-media-path / --port 8080
```

Allows HTTP calls for OCR from clients.

2. **SGLang (Inference Server)**

```bash
python -m sglang.launch_server --model zai-org/GLM-OCR --port 8080
```

3. **Ollama**

```bash
ollama run glm-ocr
```

Runs local OCR by dragging images into the terminal.

---

## Supported Scenarios

* **Document Parsing**: direct recognition of text, tables, and formulas.
* **Information Extraction**: structured JSON extraction, ideal for automation workflows or integration with downstream systems.
* **Preprocessing for RAG/NLP**: converts document images into text or structured data to feed analysis pipelines.

The model is suitable for corporate and production use, offering **deterministic output, support for multiple document types, and multimodal integration**, differentiating it from simple OCR.

If needed, a **complete guide for production pipeline integration** can also be created, including batch processing, local caching, GPU inference, and structured extraction ready for corporate systems.

Do you want me to create that as well?
