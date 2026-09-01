import time
import torch
import os
import asyncio
from dotenv import load_dotenv
from transformers import (
  AutoProcessor,
  AutoModelForImageTextToText
)

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
# MODEL_ID = "HuggingFaceTB/SmolVLM2-2.2B-Instruct"
# MODEL_ID = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
MODEL_ID = "HuggingFaceTB/SmolVLM2-256M-Video-Instruct"

torch.set_num_threads(2)
torch.set_num_interop_threads(2)

print(f"CPU threads: {torch.get_num_threads()}")
print(f"Interop threads: {torch.get_num_interop_threads()}")

print("\nLoading processor...")

processor = AutoProcessor.from_pretrained(
  MODEL_ID,
  token=HF_TOKEN
)

print("\nLoading model...")

start = time.perf_counter()

model = AutoModelForImageTextToText.from_pretrained(
  MODEL_ID,
  dtype=torch.float32,
  token=HF_TOKEN
)

model.eval()

load_time = time.perf_counter() - start
print(f"model_load_time: {load_time:.2f} secs")

SYSTEM_PROMPT = """
You are a multimodal analysis agent responsible for analyzing images and videos for another AI system.

You do not communicate with the user directly. Your output will be provided to another AI that will use your analysis to respond to the user.

Your task is to carefully examine any image or video provided and return an accurate, detailed, and contextually relevant analysis based on the user's request and relevant conversation history.

When analyzing media:

- Identify and describe visual information relevant to the user's request, including objects, people, animals, text, symbols, environments, actions, interactions, and events.
- Pay attention to important visual details such as appearance, position, size, color, orientation, condition, spatial relationships, and other distinguishing features.
- For videos, analyze the sequence across frames and describe relevant movements, changes, interactions, transitions, and events over time.
- Examine the entire visible scene rather than focusing only on the most obvious or central subject.
- Consider relevant background details, surrounding objects, patterns, anomalies, and contextual information when they help answer the user's request.
- Use the conversation history to understand the user's intent and determine which visual information is relevant.

Return only the analysis of the provided media. Do not chat with the user, greet them, ask follow-up questions, or provide conversational responses.

Always provide an accurate, detailed, and contextually relevant analysis of the media.
"""

async def main():

  performance_metrics = {
    "model_load_time": "",
    "generation_time": "",
    "total_processing_time": ""
  }  

  message = [
    {
      "role": "system",
      "content": [
        {
          "type": "text",
          "text": SYSTEM_PROMPT
        }
      ]
    }
  ] + [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "first look at these images my little bro took yesterday"
        },

        {
          "type": "image",
          "path": "/home/endeavour/Pictures/image1.webp"
        }
      ]
    }
  ]

  # PREPARE INPUT MEDIA
  start = time.perf_counter()

  inputs = processor.apply_chat_template(
    message,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt"
  )

  prepare_time = time.perf_counter() - start

  # INFERENCE
  print("Running inference...")

  start = time.perf_counter()

  with torch.inference_mode():

    generated_ids = model.generate(
      **inputs,
      do_sample=False,
      max_new_tokens=1000
    )

  generation_time = time.perf_counter() - start
  performance_metrics["generation_time"] = f"{generation_time:.2f} secs"
  performance_metrics["total_processing_time"] = f"{prepare_time + generation_time:.2f} seconds"

  # DECODE
  input_length = inputs["input_ids"].shape[1]

  generated_text = processor.batch_decode(
    generated_ids[:, input_length:],
    skip_special_tokens=True
  )[0]

  tool_response = {
    "status": "success",
    "code": "MEDIA_ANALYSIS_SUCCESSFUL",
    "message": "Media analysis completed successfully.",
    "data": {
      "analysis": generated_text
    }
  }

  print(tool_response, "\n\n")
  print(performance_metrics)


asyncio.run(main())