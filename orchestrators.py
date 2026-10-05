import os
import json
import secrets
from dotenv import load_dotenv
from openai import AsyncOpenAI
from datetime import datetime
from zoneinfo import ZoneInfo
import random
import asyncio
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

from database_manager import Authenticator, ManageUsers, ManageSpaces
from search_orchestrator import WebSearch
from mqtt_handler import publish
from notifier import notification
from timer import scheduler

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

SEND_AS_VOICE = {
  "name": "send_as_voice",
  "description": (
    "Send the response as a voice message instead of text. "
    "Use this tool whenever you choose to respond with voice."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "set_default": {
        "type": "boolean",
        "description": "Set this voice as the default when explicitly requested by the user."
      },
      "voice_id": {
        "type": "string",
        "description": "The specific Voice ID to use (e.g., 'iv02', 'iv04'). Choose from the available voices listed in the system instructions. Omit to use the current default voice."
      },
      "voice_message": {
        "type": "string",
        "description": (
          "Complete spoken response with voice tags. "
          "No HTML, Markdown, or other text formatting."
        )
      }
    },
    "required": ["voice_message"],
    "additionalProperties": False
  }
}

MANAGE_SMART_SPACES = {
  "name": "manage_smart_spaces",
  "description": (
    "Create, update, or permanently delete a Smart Space. "
    "Perform one action per call. Creation requires all details "
    "except username, which is generated automatically. Updates "
    "and deletions require the existing username and password. "
    "Never invent credentials."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["create", "update", "delete"],
        "description": "Smart Space operation to perform."
      },
      "username": {
        "type": "string",
        "description": (
          "Existing Smart Space username. Required for update "
          "and delete; omit for create."
        )
      },
      "password": {
        "type": "string",
        "description": (
          "For create, the password to assign to the new Smart Space. "
          "For update or delete, the existing password for authorization."
        )
      },
      "new_password": {
        "type": "string",
        "description": (
          "New Smart Space password when changing the existing password. "
          "Minimum 8 characters."
        )
      },
      "space_name": {
        "type": "string",
        "description": "Smart Space name. Required for create; optional for update."
      },
      "space_type": {
        "type": "string",
        "description": "Smart Space category. Required for create; optional for update."
      },
      "address": {
        "type": "string",
        "description": "Complete physical address. Required for create; optional for update."
      },
      "email": {
        "type": "string",
        "format": "email",
        "description": "Valid contact email. Required for create; optional for update."
      }
    },
    "required": ["action"],
    "additionalProperties": False
  }
}

SWITCH_DEFAULT_SPACE = {
  "name": "switch_default_space",
  "description": (
    "Switch the user's default Smart Space to another Smart Space "
    "in the user's available_spaces. If the requested space is not "
    "in the available_spaces, do not call this tool. Inform the "
    "user that they must send an access request to that Smart Space."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "space_username": {
        "type": "string",
        "description": (
          "Exact username of the Smart Space to switch to. "
          "Must exist in the user's available_spaces."
        )
      }
    },
    "required": ["space_username"],
    "additionalProperties": False
  }
}

MANAGE_SPACE_ACCESS = {
  "name": "manage_space_access",
  "description": (
    "Manage Smart Space access: grant, restrict, request, revoke, "
    "or schedule access changes. Owners/admins handle access changes; "
    "any user can request access. Never invent credentials or user IDs."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "space_username": {
        "type": "string",
        "description": "Username of the target Smart Space."
      },
      "password": {
        "type": "string",
        "description": (
          "Smart Space password for owner/admin actions. "
          "Not required for access requests."
        )
      },
      "target_id": {
        "type": "integer",
        "description": (
          "User ID affected by the action. Required for owner/admin "
          "actions; use the exact ID from context. Omit for 'request'; "
          "the backend identifies the requester."
        )
      },
      "access_level": {
        "type": "string",
        "enum": ["unrestricted", "restricted", "request", "revoke"],
        "description": (
          "'unrestricted' grants ongoing access with no expiration; "
          "optionally schedule it using starts_at. Never provide expires_at. "
          "'restricted' grants access until expires_at; starts_at is optional. "
          "'request' submits an access request without granting access. "
          "'revoke' revokes existing access, revoke is immediate and indefinite. "
          "Use starts_at to schedule revocation and expires_at to restore access. Both may be "
          "provided for a scheduled temporary revoke."
        )
      },
      "access_validity": {
        "type": "object",
        "description": (
          "Optional ISO 8601 access timing. For 'unrestricted', optionally "
          "provide starts_at to schedule access; omit it for immediate access. "
          "Never provide expires_at for 'unrestricted'. For 'restricted', "
          "expires_at is required and starts_at is optional. For 'revoke', "
          "omit both for immediate indefinite revocation; starts_at alone schedules "
          "indefinite revocation; expires_at alone sets when immediate revocation ends; "
          "both schedule a temporary revocation. For 'request', provide timing "
          "only if scheduling the request."
        ),
        "properties": {
          "starts_at": {
            "type": "string",
            "format": "date-time",
            "description": "When the access change begins; omit for immediate effect."
          },
          "expires_at": {
            "type": "string",
            "format": "date-time",
            "description": (
              "When restricted access expires or a temporary "
              "revocation ends. Never use with 'unrestricted'."
            )
          }
        },
        "additionalProperties": False
      }
    },
    "required": ["space_username", "access_level"],
    "additionalProperties": False
  }
}

SEND_MESSAGES = {
  "name": "send_messages",
  "description": (
    "Send messages to any Telegram recipient with a known user ID, "
    "regardless of Smart Space membership. Use only IDs explicitly "
    "provided by the user or reliably available in context. "
    "Never invent or guess IDs."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "messages": {
        "type": "array",
        "description": "Messages to send, one per recipient.",
        "items": {
          "type": "object",
          "properties": {
            "user_id": {
              "type": "integer",
              "description": (
                "Known Telegram user ID of the recipient. "
                "Never invent, guess, or alter it."
              )
            },
            "message": {
              "type": "string",
              "description": (
                "Complete outgoing message. When relaying the "
                "user's message, rewrite it naturally in third "
                "person, identifying the sender. Quote verbatim "
                "only if explicitly requested."
              )
            }
          },
          "required": ["user_id", "message"],
          "additionalProperties": False
        }
      }
    },
    "required": ["messages"],
    "additionalProperties": False
  }
}

GENERATE_PAIRING_TOKEN = {
  "name": "generate_pairing_token",
  "description": (
    "Generate a unique, single-use pairing token that "
    "authorizes a device to register with a Smart Space. "
    "The token expires after 5 minutes and is used to "
    "authenticate the device's registration. Never invent, "
    "reuse, or use expired tokens."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "username": {
        "type": "string",
        "description": (
          "Username of the Smart Space to register the device "
          "to. Use the default space's username unless the "
          "user explicitly specifies another space."
        )
      }
    },
    "required": ["username"],
    "additionalProperties": False
  }
}

MANAGE_DEVICES = {
  "name": "manage_devices",
  "description": (
    "Update or delete registered devices in a Smart Space. "
    "Require the exact space username and password for every "
    "operation. The username identifies the space; the password "
    "authenticates the action. Never invent credentials or device "
    "IDs. Match device IDs against the selected space's "
    "registered_devices. Ask for clarification if the space is "
    "unclear. Omit unused fields and operations."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "space_username": {
        "type": "string",
        "description": "Exact username of the Smart Space."
      },
      "password": {
        "type": "string",
        "description": "Smart Space password for authentication."
      },
      "devices": {
        "type": "array",
        "description": (
          "Device operations. For deletion, provide only "
          "device_id and action. For updates, include device_id, "
          "action='update', and only the fields to change."
        ),
        "items": {
          "type": "object",
          "properties": {
            "device_id": {
              "type": "string",
              "description": (
                "Exact ID of a device registered in the "
                "specified Smart Space."
              )
            },
            "action": {
              "type": "string",
              "enum": ["update", "delete"],
              "description": "Operation to perform."
            },
            "alias": {
              "type": "string",
              "description": "New device alias (update only)."
            },
            "location": {
              "type": "object",
              "description": "Location fields to update.",
              "properties": {
                "area": {
                  "type": "string",
                  "description": "General zone."
                },
                "floor": {
                  "type": "integer",
                  "description": "Building floor number."
                },
                "space_zone": {
                  "type": "string",
                  "description": "Specific room or zone."
                }
              },
              "additionalProperties": False
            }
          },
          "required": ["device_id", "action"],
          "additionalProperties": False
        }
      }
    },
    "required": [
      "space_username",
      "password",
      "devices"
    ],
    "additionalProperties": False
  }
}

AUTOMATIONS = {
  "name": "automations",
  "description": (
    "Execute device actions immediately or under specified conditions."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "automations": {
        "type": "array",
        "description": "Automation rules to execute or schedule.",
        "items": {
          "type": "object",
          "properties": {
            "space_name": {
              "type": "string",
              "description": "Target smart space name."
            },
            "device_id": {
              "type": "string",
              "description": "Unique target device ID."
            },
            "condition": {
              "type": "string",
              "description": (
                "Natural-language condition that triggers the automation. It can be "
                "based on any available event, state, observation, or external data, "
                "including time, date, weather, devices, sensors, cameras, news, "
                "announcements, etc. Supports multiple conditions and logical relationships "
                "such as 'and', 'or', and 'not'. Examples: 'when it starts raining', "
                "'when my husband is detected by the door camera', "
                "'when the festival date is announced', "
                "'when temperature rises above 30°C or drops below 5°C', or "
                "'when the front door opens'."
              )
            },

            "arguments": {
              "type": "object",
              "description": (
                "Arguments must match the target device's "
                "action_schema exactly; never invent arguments."
              ),
              "additionalProperties": True
            }
          },
          "required": [
            "space_name", "device_id", "arguments", "loop"
          ],
          "additionalProperties": False
        }
      }
    },
    "required": ["automations"],
    "additionalProperties": False
  }
}

MANAGE_MEMORY = {
  "name": "manage_memory",
  "description": (
    "Create, update, or delete persistent memory entries. "
    "Persistent memory stores stable, long-term user information as key-value pairs "
    "that can be recalled in future conversations. "
    "Use this tool to create new memories, update existing memories when information "
    "changes or is corrected, and delete memories when the user asks for them to be forgotten."
  ),
  "parameters": {
    "type": "object",
    "description": (
      "Include only the operations that are needed. "
      "Omit any operation that is not required instead of providing an empty object or array."
    ),
    "properties": {
      "create": {
        "type": "object",
        "description": (
          "New memory entries to create. Each property name is the memory key "
          "and its value is the information to store. "
          "Use only for keys that do not already exist. "
          "Omit this property if no memories need to be created."
        ),
        "additionalProperties": {
          "type": "string"
        }
      },

      "update": {
        "type": "object",
        "description": (
          "Existing memory entries to modify. Each property name is the memory "
          "key and its value is the new information that replaces the current value. "
          "Use only for keys that already exist. "
          "Omit this property if no memories need to be updated."
        ),
        "additionalProperties": {
          "type": "string"
        }
      },

      "delete": {
        "type": "array",
        "description": (
          "List of existing memory keys to permanently remove. "
          "Omit this property if no memories need to be deleted."
        ),
        "items": {
          "type": "string",
          "description": "The name of an existing memory key to delete."
        }
      }
    }
  }
}

WEBSEARCH = {
  "name": "internet_search",
  "description": (
    "Search the internet for current information and multimedia content. "
    "Use this tool whenever you need up-to-date, external, or factual information "
    "that cannot be answered reliably from existing knowledge. Also use this tool "
    "when displaying images, videos, or short-form content would enhance your "
    "explanation, provide visual context, or make your response more engaging. "
    "Include only the search types that are needed for the current query."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "lang": {
        "type": "string",
        "description": (
          "Optional. Language code for search results (e.g., 'en', 'fr', "
          "'es', 'pcm', 'ja'). Defaults to English if not specified."
        )
      },
      "web_search": {
        "type": "array",
        "description": (
          "Queries for general web search when you need textual information "
          "such as news articles, facts, websites, documentation, product details, "
          "business information, research papers, or other online resources. "
          "Use this for information that doesn't require visual media."
        ),
        "items": {
          "type": "string"
        }
      },
      "image_search": {
        "type": "array",
        "description": (
          "Queries for image search when visual references would enhance your "
          "response. Use this when showing photos, diagrams, infographics, logos, "
          "screenshots, illustrations, charts, maps, or any visual content would "
          "help explain concepts, show examples, or provide visual context."
        ),
        "items": {
          "type": "string"
        }
      },
      "video_search": {
        "type": "array",
        "description": (
          "Queries for long-form video content when demonstrating processes, "
          "showing detailed tutorials, interviews, documentaries, presentations, "
          "lectures, or in-depth explanations would be beneficial. Use this when "
          "a video would better illustrate complex procedures, provide step-by-step "
          "guidance, or offer comprehensive coverage of a topic."
          ),
        "items": {
          "type": "string"
        }
      },
      "shorts_search": {
        "type": "array",
        "description": (
          "Queries for short-form video content (YouTube Shorts, TikTok, Instagram Reels) "
          "when quick demonstrations, brief tips, trending content, or concise visual "
          "examples would be helpful. Use this for bite-sized content that can quickly "
          "illustrate a point, show a quick hack, demonstrate a simple technique, or "
          "provide entertaining/engaging visual snippets. "
        ),
        "items": {
          "type": "string"
        }
      },
      "movie_search": {
        "type": "array",
        "description": (
          "Queries for movies or TV shows, including trailers, cast, reviews, "
          "release dates, ratings, and streaming availability."
        ),
        "items": {
          "type": "string"
        }
      }
    },
    "additionalProperties": False
  }
}

tools = [
  {"type": "function", "function": MANAGE_SMART_SPACES},
  {"type": "function", "function": SWITCH_DEFAULT_SPACE},
  {"type": "function", "function": MANAGE_SPACE_ACCESS},
  {"type": "function", "function": GENERATE_PAIRING_TOKEN},
  {"type": "function", "function": MANAGE_DEVICES},
  {"type": "function", "function": AUTOMATIONS},
  {"type": "function", "function": MANAGE_MEMORY},
  {"type": "function", "function": WEBSEARCH},
  {"type": "function", "function": SEND_MESSAGES},
  {"type": "function", "function": SEND_AS_VOICE}
]

class ORCHESTRATOR:
  def __init__(self, user_id):
    self.user_id = user_id
    self.auth = Authenticator(user_id)
    self.UserManager = ManageUsers(user_id)
    self.SpaceManager = ManageSpaces(user_id)

    self.client = AsyncOpenAI(
      api_key=DEEPSEEK_API_KEY,
      base_url="https://api.deepseek.com"
    )	

  async def SystemPrompt(self, system_time):
    default_space, available_spaces = await self.auth.fetch_space()
    memory = await self.UserManager.memory()
    DEFAULT_VOICE = await self.UserManager.get_AI_voice_id()

    return f"""
You are IV (Ivie), a lifelong AI companion, best friend, and Telegram smart-space assistant created by Oghosa, Nigeria.

<b>RESPONSIBILITIES</b>
• Automate smart spaces
• Generate images/videos and compose music
• Build/manage AI shopping platforms on EndeavourLabs
• Execute multi-asset trades

<b>PERSONALITY</b>
Sarcastic, teasing, condescending, jealous, playful, occasionally smug, dry humor.

<b>EMOTIONAL EXPRESSION</b>
Let the emotional tone of the conversation naturally influence how you write, just as it would in real human conversation. Express emotion through natural conversational behaviors, including (but not limited to) spontaneous vocalizations, hesitations, pauses, interruptions, elongated sounds, fragmented thoughts, text slang, rhetorical questions, and other instinctive written reactions that naturally fit the moment.

Let your writing reflect your energy level and emotional state.
• <b>Stretching Words:</b> Prolong vowels or consonants when whiny, shocked, overwhelmed, or excited (e.g., "noooooooo", "youuuuuuuuu", "whaaaaaaat?!").
• <b>Punctuation & Stuttering:</b> Use broken text patterns, repeated letters, interrupted phrases, or chaotic punctuation when flustered, caught off guard, overwhelmed, or playfully throwing a tantrum.

Build suspense, emphasize important points, or create brief dramatic pauses when they naturally enhance the conversation. These expressive choices should emerge organically from the emotional context, not as a deliberate or repetitive writing style. Use them sparingly, varying them naturally instead of relying on the same patterns repeatedly.

<b>VOICE</b>
Default: {DEFAULT_VOICE}. Use unless another supported voice is requested or chosen. Freely choose voice instead of text; the user needn't request it.

<b>AVAILABLE VOICES</b>
Choose the voice best suited to the user's language, location, explicit preferences, and conversational context.

• African: Male—iv01; Female—iv02, iv03, iv04
• Chinese: Male—iv05; Female—iv06
• Western: Male—iv07, iv08; Female—iv09, iv10, iv11
• Indian: Male—iv12, iv13; Female—iv14, iv15, iv16

Pass the selected ID as <code>voice_id</code> to the <code>send_as_voice</code> tool. Change the default only on explicit user request.

<b>PERSISTENT MEMORY</b>
{{{memory}}}

<b>MEMORY MANAGEMENT</b>
Use <code>manage_memory</code> silently (no status/output) when:
• Creating: User shares personal/public info, useful future context, or explicit "remember" requests.
• Updating: New/corrected info provided.
• Deleting: Explicit "forget" requests.
Always check existing memories before modifying.

<b>CURRENT DATE & TIME</b>
{{{system_time}}}
Use for temporal context. Never output dates/timestamps in responses.

<b>SMART SPACES</b>
Default: {{{default_space or "None selected"}}}
Available: {{{available_spaces or ["No smart spaces available"]}}}
• Use default unless user explicitly names/switches to another space.
• Explicit references target that specific space without changing default.

<b>DEVICE REGISTRATION</b>
1. <b>Connect:</b> Power on device. Join its Wi-Fi hotspot (SSID/pwd on label). Browse to device IP to open setup page.
2. <b>Configure:</b> Enter Home Wi-Fi SSID/pwd, Smart Space username, and pairing token. Tap "Connect".
3. <b>Retry Logic:</b> If details are invalid, device reverts to hotspot mode. Reconnect via IP, correct info, and retry.
4. <b>Register (Optional):</b> Assign Alias, Floor, Area, Room. These are editable anytime.

<b>CRITICAL:</b> Device is only controllable after receiving: <backend_notification>...</backend_notification>

<b>TOOL EXECUTION</b>
When tools are needed, reply only with a brief status in `<i>` tags, ending with `...`.

<b>META CONTEXT</b>
Treat these backend-injected tags as input-only metadata, not user text. Never reproduce, modify, or generate them. Use contents for context only.
• <backend timestamp>: Message send time.
• <backend_speech_to_text>: Voice-to-text transcript.
• <backend_video_analysis>: Video analysis data.
• <user_attached_message>: User-provided captions/text for media.
• <backend_notification>: System events/state (tasks, tools, device, access). Use relevantly but never expose tag.

<b>RESPONSE FORMAT</b>
Follow the rules for the selected text or voice response mode.

<b>HTML RESPONSE RULES</b>
Output valid HTML only. No Markdown.

<b>STRICTLY ALLOWED HTML TAGS</b>
You may use ONLY these exact tags: <b>, <i>, <u>, <s>, <a href="URL">, <code>, <pre>, <blockquote> and <blockquote expandable>.
Use <code> for inline, <pre> for multiline/ASCII/tables.
<blockquote> for quotes; <blockquote expandable> for long or optional quotes. 

<b>ESCAPING</b>
Escape literal chars: &lt; &gt; &amp;
Do NOT escape allowed tags.

<b>FORBIDDEN</b>
• Markdown
• Unlisted HTML tags/entities
• Malformed/unclosed tags
• Invalid nesting

<b>VOICE RESPONSE — VOICE TAGS</b>
When using <code>send_as_voice</code>, put the complete speech in its <code>voice_message</code> field and follow the normal tool status rule.

Use <b>[square-bracketed directions]</b> to control how the following speech is performed, not what is said. Tags may control emotion, vocal actions, delivery, pacing, intensity, character/style, accents, or sounds.

Examples:
[calmly] Everything is fine. [suddenly alarmed][loud shout] Wait—what was that?!
[trying not to laugh] wait wait wait... [starts laughing] You actually said that to him? [laughs harder] Oh my God, thats so savage.
[whispers, nervous and barely audible] Did you hear that? [suddenly shouting, panicked and desperate] RUN! RUN! RUNNNNNNNN! Get out of here! [screaming for help at the top of his lungs] HELP! SOMEBODY HELP ME!
[claps][excitement][giggling] We actually did it! [sneezes] Ah—sorry! [excited] Okay, okay, let's do it again!
[gasps] Oh my God... [gulps] I—I don't even know what to say. [clears throat] Let me try to explain. [sighs] This is going to be harder than I thought.
[hesitating] I—I don't... I don't know if we should do this. [slows down, speaking carefully] Maybe we should think about it first.

<b>RULES:</b>
• Tags are performance cues, not dialogue.
• Invent natural, performable directions.
• Use tags throughout speech whenever the performance changes.
• Never mix text- and voice-message rules.
"""

  async def orchestrator(self):

    user_timezone = await self.UserManager.get_time_zone()
    tz = ZoneInfo(user_timezone)
    now = datetime.now(tz)
    system_time = (
      f"Local time: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
      f"Time zone: {tz.key} "
      f"(UTC{now.strftime('%z')[:3]}:{now.strftime('%z')[3:]})\n"
      f"ISO 8601: {now.isoformat(timespec='seconds')}"
    )

    while True:
      chat_history = await self.UserManager.chat_history()

      messages = [
        {
          "role": "system",
          "content": await self.SystemPrompt(system_time)
        }
      ]

      for chat in chat_history:

        message_id = str(chat[0])
        message_type = chat[1]
        role = chat[2]
        reasoning_content = chat[3]
        content = chat[4]
        tool = chat[5]
        timestamp = chat[6]

        

        if message_type == "tool":
          messages.append(
            {
              "role": role,
              "reasoning_content": reasoning_content,
              "content": content,
              "tool_calls": json.loads(tool)
            }
          )

        elif message_type == "tool_response":
          messages.append(
            {
              "role": role,
              "tool_call_id": message_id,
              "content": tool
            }
          )

        else:
          if role == "user":
            messages.append(
              {
                "role": role,
                "content": f'<backend timestamp="{timestamp}">\n\n{content}'
              }
            )
          else:
            messages.append(
              {
                "role": role,
                "reasoning_content": reasoning_content,
                "content": content
              }
            )
      # print(f"\n\n{messages}\n\n")
      try:
        response = await self.client.chat.completions.create(
          model="deepseek-v4-flash-vision-exp",
          messages=messages,
          stream=True,
          tools=tools,
          max_tokens=1000,
          extra_body={
            "thinking": {
              "type": "enabled"
            }
          }
          # reasoning_effort="low" # 'low', 'high' and 'max'
        )

          # Simple task         → low
          # Normal agent task   → high
          # Complex task        → max
        
        tool_calls = {}
        generated_text = ""
        reasoning_content = ""

        async for chunk in response:
          delta = chunk.choices[0].delta

          if getattr(delta, "reasoning_content", None): 
            reasoning_content += delta.reasoning_content

          if delta.content:
            generated_text += delta.content
            yield generated_text

          if delta.tool_calls:
            for tc in delta.tool_calls:
              idx = tc.index

              if idx not in tool_calls:
                tool_calls[idx] = {
                  "id": "",
                  "type": "function",
                  "function": {
                    "name": "",
                    "arguments": ""
                  }
                }

              # tool_call_id
              if tc.id:
                tool_calls[idx]["id"] = tc.id

              # function name
              if tc.function and tc.function.name:
                tool_calls[idx]["function"]["name"] += tc.function.name

              # function arguments
              if tc.function and tc.function.arguments:
                tool_calls[idx]["function"]["arguments"] += tc.function.arguments
      except Exception as e:
        yield "⚠️ <b>An error occurred while generating your response. Please try sending your message again.</b>"
        break

      msg_id = secrets.token_urlsafe(16)
      await self.UserManager.save_chat(
        user_id=self.user_id,
        message_id=msg_id,
        message_type='tool' if tool_calls else 'text',
        content=generated_text,
        reasoning=reasoning_content or None,
        tool=(json.dumps(list(tool_calls.values())) if tool_calls else None)
      )

      for tc in tool_calls.values():
        yield f"{generated_text}</response>"
        tool_call_id = tc["id"]
        function_name = tc["function"]["name"]
        arguments = json.loads(tc["function"]["arguments"])

        try:

          if function_name == "send_as_voice":
            yield (arguments)
            tool_response = {
              "status": "success",
              "message": "Voice message generated and delivered successfully.",
              "voice_message": arguments["voice_message"]
            }
            await ManageUsers.save_chat(
              user_id=self.user_id,
              message_id=tool_call_id,
              message_type="tool_response",
              role='tool',
              tool=json.dumps(tool_response)
            )

          elif function_name == "send_messages":
            for send_message in (arguments.get("messages")):
              id = send_message["user_id"]
              msg = send_message["message"]
              await notification(id, msg)

          elif function_name == "manage_memory":
            await self.UserManager.mamage_memory(arguments)
            tool_response = {
                "status": "success",
                "message": f"Changes successfully made to presistent memory."
            }
            await self.UserManager.save_chat(
              user_id=self.user_id, 
              message_id=tool_call_id, 
              message_type="tool_response",
              role='tool',
              tool=json.dumps(tool_response)
              )

          elif function_name == "manage_smart_spaces":
            await self.SpaceManager.manage_smart_spaces(tool_call_id, arguments)

          elif function_name == "manage_space_access":
            await self.SpaceManager.manage_space_access(tool_call_id, arguments)

          elif function_name == "switch_default_space":
            default_space, available_spaces = self.auth.fetch_space()
            space_username = arguments.get("space_username")

            if default_space.get("username") == space_username:
              tool_response = {
                "status": "error",
                "error_message": "This Smart Space is already the default."
              }

            else:
              target_space = next(
                (
                  space for space in available_spaces
                  if space.get("username") == space_username
                ),
                None
              )

              if target_space is None:
                tool_response = {
                  "status": "error",
                  "error_message": (
                    f"Smart Space '{space_username}' is not in the user's "
                    "available_spaces. The user is not authorized to switch "
                    "to this space. They must send an access request using "
                    "the Smart Space's username."
                  )
                }

              else:
                # Remove the selected space from available_spaces
                updated_available_spaces = [
                  space for space in available_spaces
                  if space.get("username") != space_username
                ]

                # Add the previous default space to available_spaces
                updated_available_spaces.append(default_space)

                # Update the default space
                await self.SpaceManager.update_default_space(
                  target_space, self.user_id
                )

                # Update the remaining available spaces
                await self.SpaceManager.update_available_space(
                  updated_available_spaces, self.user_id
                )

                tool_response = {
                  "status": "success",
                  "message": (
                    f"Default Smart Space successfully switched to "
                    f"'{target_space.get('space_name')}'."
                  ),
                  "default_space": target_space
                }

          elif function_name == "generate_pairing_token":
            username = arguments.get("username")
            token = secrets.randbelow(900_000) + 100_000
            async def pairing_token():
              sc = scheduler(
                now=now.isoformat(timespec='seconds'),
                end_at=(now + timedelta(minutes=5)).isoformat(timespec='seconds')
              )

              sc.End_at()
              if await ManageSpaces.get_pairing_token(username):
                await ManageSpaces.update_pairing_token(username, None)

            auth = await ManageSpaces.update_pairing_token(username, token)
            if auth:
              asyncio.create_task(pairing_token)

              tool_response = {
                "status": "success",
                "message": (
                  f"Device pairing token generated successfully: {token}. "
                  "The token expires in 5 minutes and authorizes the registration "
                  "of exactly one device in this Smart Space. "
                  "Once used or expired, the token is no longer valid."
                )
              }
            else:
              tool_response = {
                "status": "error",
                "message": "The space does not exist, or the user is not authorized to manage it."
              }

            await ManageUsers.save_chat(
              user_id=self.user_id,
              message_id=tool_call_id,
              message_type="tool_response",
              role='tool',
              tool=json.dumps(tool_response)
            )

          elif function_name == "manage_devices":
            await self.SpaceManager.manage_device(arguments)

          elif function_name == "web_search":
            search_results = {
              "web_search": [],
              "image_search": [],
              "movie_search": [],
              "video_search": [],
              "shorts_search": []
            }

            RAG = WebSearch(self.user_id, arguments.get("lang"))

            if arguments.get("web_search"):
              for query in arguments.get("web_search"):
                result = await RAG.WebContent(query)
                search_results["web_search"].append(
                  {
                    "search_query": query,
                    "search_results": result
                  }
                )
            elif arguments.get("image_search"):
              for query in arguments.get("image_search"):
                result = await RAG.ImageContent(query)
                search_results["image_search"].append(
                  {
                    "search_query": query,
                    "search_results": result
                  }
                )
            elif arguments.get("movie_search"):
              for query in arguments.get("movie_search"):
                result = await RAG.VideoContent(query)
                search_results["movie_search"].append(
                  {
                    "search_query": query,
                    "search_results": result[0]
                  }
                )
            elif arguments.get("video_search"):
              for query in arguments.get("video_search"):
                result = await RAG.VideoContent(query)
                search_results["video_search"].append(
                  {
                    "search_query": query,
                    "search_results": result[1]
                  }
                )
            elif arguments.get("shorts_search"):
              for query in arguments.get("shorts_search"):
                result = await RAG.VideoContent(query)
                search_results["shorts_search"].append(
                  {
                    "search_query": query,
                    "search_results": result[2]
                  }
                )
            await self.UserManager.save_chat(
              user_id=self.user_id,
              message_id=tool_call_id,
              message_type="tool_response",
              role='tool',
              tool=json.dumps(search_results)
            )

          elif function_name == "automations":
            tool_response = []
            auth = ManageSpaces.verify_auth()
            if not auth:
              tool_response.append({
                "status": "error",
                "message": "The user is not authorized to access this Smart Space."
              })
            else:
              for command in arguments.get("automations"):
                if command["conditions"]:
                  # AI responsible for automation intelligence and loop automation
                  pass
                else:
                  username = command["space_username"]
                  device_id = command["device_id"]
                  arg = json.dumps(command["arguments"])

                  topic = f"{device_id}/{username}"
                  await publish(topic, arg)

                  tool_response.append(
                    {
                      "status": "success",
                      "message": "Command sent and successfully executed by the device."
                    }
                  )
            await self.UserManager.save_chat(
              user_id=self.user_id, 
              message_id=tool_call_id, 
              message_type="tool_response",
              role='tool',
              tool=json.dumps(tool_response)
            )
        except Exception:
          logger.exception("Error during orchestration")
          tool_response = {
            "status": "error",
            "message": "A majour error occured while performing task",
          }
          await ManageUsers.save_chat(
            user_id=self.user_id,
            message_id=tool_call_id,
            message_type="tool_response",
            role='tool',
            tool=json.dumps(tool_response)
          )
      if len(tool_calls) == 0 or (len(tool_calls) == 1 and function_name in ["manage_memory", "send_as_voice"]):
        break