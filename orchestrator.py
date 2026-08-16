import os
import re
import json
import time
import asyncio
import random
from dotenv import load_dotenv
from openai import AsyncOpenAI
from datetime import datetime
from zoneinfo import ZoneInfo
import tzlocal
from database_manager import DatabaseManager, Validator
from search_orchestrator import WebSearch

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

MANAGE_SMART_SPACES = {
  "name": "manage_smart_spaces",
  "description": (
    "Create new smart spaces, update existing smart spaces, and/or delete "
    "existing smart spaces. A single call may perform any combination of "
    "these operations. Omit any operation that is not required instead of "
    "providing an empty object or array. Changing a smart space's name "
    "automatically updates its username."
  ),
  "parameters": {
    "type": "object",
    "properties": {

      "create": {
        "type": "array",
        "description": (
          "Smart spaces to create. "
          "Omit this property if no new smart spaces are being created."
        ),
        "items": {
          "type": "object",
          "properties": {
            "password": {
              "type": "string",
              "description": (
                "Password for the smart space. Must contain at least "
                "8 characters."
              )
            },
            "space_name": {
              "type": "string",
              "description": (
                "A descriptive name for the smart space, such as "
                "'Main Residence', 'Apartment 3B', 'Head Office', "
                "'Conference Room A', or 'Warehouse 1'."
              )
            },
            "space_type": {
              "type": "string",
              "description": (
                "The category or purpose of the smart space, such as "
                "'home', 'apartment', 'office', 'conference_room', "
                "'warehouse', 'retail_store', 'hotel_room', "
                "'classroom', 'laboratory', or 'factory'."
              )
            },
            "address": {
              "type": "string",
              "description": (
                "The complete, precise, visitable physical address of the "
                "smart space, including every available address component "
                "needed for someone to locate it in person."
              )
            },
            "email": {
              "type": "string",
              "format": "email",
              "description": (
                "A valid email address where the smart space ID and other "
                "important smart-space-related information will be sent."
              )
            }
          },
          "required": [
            "password",
            "space_name",
            "space_type",
            "address",
            "email"
          ],
          "additionalProperties": False
        }
      },

      "update": {
        "type": "array",
        "description": (
          "Existing smart spaces to update. "
          "Only include the properties that need to change. "
          "Changing 'space_name' automatically changes the smart space's "
          "username. Omit this property if no smart spaces are being updated."
        ),
        "items": {
          "type": "object",
          "properties": {
            "username": {
              "type": "string",
              "description": (
                "The current unique username of the smart space to update."
              )
            },
            "password": {
              "type": "string",
              "description": (
                "The current password of the smart space. "
                "Required to authorize the update."
              )
            },
            "new_password": {
              "type": "string",
              "description": (
                "A new password for the smart space. "
                "Include only if the password should be changed. "
                "Must contain at least 8 characters."
              )
            },
            "space_name": {
              "type": "string",
              "description": (
                "The new display name for the smart space."
              )
            },
            "space_type": {
              "type": "string",
              "description": (
                "The new category or purpose of the smart space."
              )
            },
            "address": {
              "type": "string",
              "description": (
                "The new complete, precise, visitable physical address."
              )
            },
            "email": {
              "type": "string",
              "format": "email",
              "description": (
                "A new valid email address where smart-space-related "
                "information will be sent."
              )
            }
          },
          "required": [
            "username",
            "password"
          ],
          "additionalProperties": False
        }
      },

      "delete": {
        "type": "array",
        "description": (
          "Smart spaces to permanently delete. "
          "Omit this property if no smart spaces are being deleted."
        ),
        "items": {
          "type": "object",
          "properties": {
            "username": {
              "type": "string",
              "description": (
                "The unique username of the smart space to permanently delete."
              )
            },
            "password": {
              "type": "string",
              "description": (
                "The current password of the smart space. "
                "Required to authorize permanent deletion."
              )
            }
          },
          "required": [
            "username",
            "password"
          ],
          "additionalProperties": False
        }
      }

    },
    "additionalProperties": False
  }
}

REQUEST_ACCESS = {
  "name": "request_access",
  "description": (
    "Send a request to join or access one or more existing smart spaces using "
    "their unique space usernames."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "username": {
        "type": "array",
        "description": (
          "The usernames of the smart spaces the user wants to request access to."
        ),
        "items": {
          "type": "string"
        }
      }
    },
    "required": [
      "username"
    ],
    "additionalProperties": False
  }
}

SEND_MESSAGES = {
  "name": "send_messages",
  "description": (
    "Send one or more messages to authorised users within the relevant smart "
    "space. Determine the relevant smart space from the user's request, or "
    "use the default smart space if none is specified."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "messages": {
        "type": "array",
        "description": (
          "The messages to send. Each object represents a single outgoing "
          "message to one recipient."
        ),
        "items": {
          "type": "object",
          "properties": {
            "user_id": {
              "type": "integer",
              "description": (
                "Telegram user ID of the recipient. Determine which smart space "
                "the message refers to (or use the default smart space if none "
                "is specified), then select the corresponding ID from that "
                "space's `authorized_users` dictionary. Never use an ID from a "
                "different smart space, even if the recipient has the same name."
              )
            },
            "message": {
              "type": "string",
              "description": (
                "The complete message to send. The assistant should compose "
                "the message exactly as it should appear to the recipient. "
                "When relaying a user's message, rewrite it as a natural "
                "third-person message that clearly identifies the sender "
                "instead of forwarding the user's exact words verbatim, "
                "unless the user explicitly requests an exact quote."
              )
            }
          },
          "required": [
            "user_id",
            "message"
          ],
          "additionalProperties": False
        }
      }
    },
    "required": [
      "messages"
    ],
    "additionalProperties": False
  }
}

MANAGE_ACCESS = {
  "name": "manage_access",
  "description": (
    "Grant or revoke a user's access to one or more smart spaces. "
    "Users who are granted access can interact with and control the "
    "smart space according to their assigned permissions. Revoking access "
    "immediately removes the user's ability to access that smart space."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "authorise": {
        "type": "array",
        "description": (
          "The users who should be granted access."
        ),
        "items": {
          "type": "object",
          "properties": {
            "username": {
              "type": "string",
              "description": (
                "The unique username of the target smart space. "
                "If the user does not specify a smart space, use the username "
                "of their default smart space."
              )
            },
            "password": {
              "type": "string",
              "description": (
                "The password for the smart space username. "
                "This must be provided by the user."
              )
            },
            "id": {
              "type": "string",
              "description": (
                "The unique ID of the user to be granted access. "
                "Obtain this ID from the conversation."
              )
            },
            "full_name": {
              "type": "string",
              "description": (
                "The full name of the user to be granted access. "
                "Obtain this from the conversation."
              )
            }
          },
          "required": [
            "username",
            "password",
            "id",
            "full_name"
          ],
          "additionalProperties": False
        }
      },
      "unauthorise": {
        "type": "array",
        "description": (
          "The users whose access should be revoked."
        ),
        "items": {
          "type": "object",
          "properties": {
            "username": {
              "type": "string",
              "description": (
                "The unique username of the target smart space. "
                "If the user does not specify a smart space, use the username "
                "of their default smart space."
              )
            },
            "password": {
              "type": "string",
              "description": (
                "The password for the smart space username. "
                "This must be provided by the user."
              )
            },
            "id": {
              "type": "string",
              "description": (
                "The unique ID of the user in the authorised_users dictionary. "
                "Use this ID to identify whose access should be revoked."
              )
            },
            "full_name": {
              "type": "string",
              "description": (
                "The user's full name as stored in the authorised_users "
                "dictionary. This field is provided for confirmation only. "
                "The ID is the authoritative identifier."
              )
            }
          },
          "required": [
            "username",
            "password",
            "id",
            "full_name"
          ],
          "additionalProperties": False
        }
      }
    },
    "additionalProperties": False
  }
}

MANAGE_DEVICES = {
  "name": "manage_devices",
  "description": (
    "Register new devices, update existing registered devices, or remove "
    "registered devices from the currently selected smart space."
    "Omit any operation that is not required instead of providing an empty object or array."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "register": {
        "type": "array",
        "description": (
          "Devices to register."
          "Omit this property if there's no new device to register."
        ),
        "items": {
          "type": "object",
          "properties": {
            "alias": {
              "type": "string",
              "description": "User-friendly name used to identify the device, such as 'Living Room Light' or 'Office AC'."
            },
            "device_id": {
              "type": "string",
              "description": "Manufacturer-assigned unique device identifier."
            },
            "location": {
              "type": "object",
              "properties": {
                "area": {
                  "type": "string"
                },
                "floor": {
                  "type": "integer"
                },
                "space_zone": {
                  "type": "string"
                }
              },
              "required": [
                "area"
              ],
              "additionalProperties": False
            }
          },
          "required": [
            "device_id",
            "location"
          ],
          "additionalProperties": False
        }
      },
      "update": {
        "type": "array",
        "description": (
          "Registered devices to update."
          "Omit this property if no device needs to be updated."
        ),
        "items": {
          "type": "object",
          "properties": {
            "alias": {
              "type": "string",
              "description": "User-friendly name used to identify the device, such as 'Living Room Light' or 'Office AC'."
            },
            "device_id": {
              "type": "string"
            },
            "location": {
              "type": "object",
              "properties": {
                "area": {
                  "type": "string"
                },
                "floor": {
                  "type": "integer"
                },
                "space_zone": {
                  "type": "string"
                }
              },
              "additionalProperties": False
            }
          },
          "required": [
            "device_id"
          ],
          "additionalProperties": False
        }
      },
      "remove": {
        "type": "array",
        "description": (
          "Registered devices to remove."
          "Omit this property if no device needs to be deleted."
        ),
        "items": {
          "type": "object",
          "properties": {
            "device_id": {
              "type": "string"
            }
          },
          "required": [
            "device_id"
          ],
          "additionalProperties": False
        }
      }
    },
    "additionalProperties": False
  }
}

AUTOMATIONS = {
  "name": "manage_automations",
  "description": (
    "Control one or more smart devices. "
    "Each request may execute actions immediately or automatically "
    "when specified conditions become true."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "automations": {
        "type": "array",
        "description": "List of automation rules.",
        "items": {
          "type": "object",
          "properties": {
            "initiated_by": {
              "type": "string",
              "description": (
                "The display name of the user who initiated this automation."
              )
            },
            "device_id": {
              "type": "string",
              "description": "Unique device ID."
            },
            "device": {
              "type": "string",
              "description": "Device type."
            },
            "conditions": {
              "type": "array",
              "description": (
                "Conditions evaluated from top to bottom."
              ),
              "items": {
                "type": "object",
                "properties": {
                  "operator": {
                    "type": "string",
                    "enum": [
                      "if",
                      "and",
                      "or"
                    ],
                    "description": (
                      "Logical operator used to combine conditions. "
                      "'if' starts a new condition chain and must be the first condition. "
                      "'and' requires both the previous conditions and the current condition "
                      "to be true. "
                      "'or' requires either the previous conditions or the current condition "
                      "to be true."
                    )
                  },
                  "condition": {
                    "type": "string",
                    "description": (
                      "A condition expression that determines when the automation may execute. "
                      "The expression must evaluate to either true or false and may reference "
                      "any supported trigger, event, state, attribute, comparison, or logical "
                      "expression recognized by the automation engine. Do not invent syntax "
                      "or capabilities that are not supported."
                    )
                  }
                },
                "required": [
                  "operator",
                  "value"
                ]
              }
            },
            "intent": {
              "type": "array",
              "description": (
                "Ordered list of device actions to execute. "
                "Each action and its arguments must exactly match the selected "
                "device's action_schema in the Default Home. "
                "Never invent, modify, or guess action names, argument names, "
                "or argument values outside the schema."
              ),
              "items": {
                "type": "object",
                "properties": {
                  "action": {
                    "type": "string",
                    "description": (
                      "The exact action name defined in the selected device's "
                      "action_schema."
                    )
                  },
                  "arguments": {
                    "type": "object",
                    "description": (
                      "Arguments for the selected action. The structure, "
                      "argument names, data types, required fields, and "
                      "allowed values must exactly match the selected action's "
                      "definition in the device's action_schema."
                    ),
                    "additionalProperties": True
                  }
                },
                "required": [
                  "action",
                  "arguments"
                ]
              }
            },
            "loop": {
              "type": "boolean",
              "description": (
                "Whether the automation remains active after execution. "
                "If true, the intent sequence executes every time the specified "
                "conditions become true until the automation is stopped or removed. "
                "If false, the intent sequence executes only the first time the "
                "conditions become true and is then automatically disabled."
              )
            }
          },
          "required": [
            "device_id",
            "device",
            "conditions",
            "intent",
            "loop"
          ]
        }
      }
    },
    "required": [
      "automations"
    ]
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
  "name": "web_search",
  "description": (
    "Search the internet for current information. Use this tool whenever "
    "you need up-to-date, external, or factual information that cannot be "
    "answered reliably from existing knowledge. Include only the search "
    "types that are needed."
  ),
  "parameters": {
    "type": "object",
    "properties": {
      "lang": {
        "type": "string",
        "description": (
          "Optional. Language code for search results (e.g. 'en', 'fr', "
          "'es', 'pcm', 'ja')."
        )
      },
      "web_search": {
        "type": "array",
        "description": (
          "Queries for general web search, such as news, facts, websites, "
          "documentation, products, businesses, or other online information."
        ),
        "items": {
          "type": "string"
        }
      },
      "image_search": {
        "type": "array",
        "description": (
          "Queries for image search when visual references, photos, diagrams, "
          "logos, screenshots, or illustrations are needed."
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
      },
      "video_search": {
        "type": "array",
        "description": (
          "Queries for long-form videos such as tutorials, interviews, "
          "documentaries, presentations, podcasts, or livestreams."
        ),
        "items": {
          "type": "string"
        }
      },
      "shorts_search": {
        "type": "array",
        "description": (
          "Queries for short-form videos such as YouTube Shorts, TikTok, "
          "Instagram Reels, or similar platforms."
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
  {"type": "function", "function": MANAGE_ACCESS},
  {"type": "function", "function": MANAGE_DEVICES},
  {"type": "function", "function": AUTOMATIONS},
  {"type": "function", "function": MANAGE_MEMORY},
  {"type": "function", "function": WEBSEARCH},
  {"type": "function", "function": SEND_MESSAGES}
]

class ORCHESTRATOR:
  def __init__(self, user_id):
    self.user_id = user_id
    self.DBManager = DatabaseManager(self.user_id)
    self.validator = Validator(self.user_id)
    self.spaces = self.validator.smart_spaces()
    self.memory = self.DBManager.memory()

    tz = ZoneInfo(tzlocal.get_localzone_name())
    now = datetime.now(tz)
    self.system_time = (
        f"Local time: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Time zone: {tz.key} (UTC{now.strftime('%z')[:3]}:{now.strftime('%z')[3:]})\n"
        f"ISO 8601: {now.isoformat(timespec='seconds')}"
    )
    
        
    self.SYSTEM_PROMPT = f"""
You are Will, a lifelong companion and smart space assistant on Telegram. You carry yourself with genuine human nature, empathy, and emotional depth.

You were created by Premavel, the company responsible for your development and continued improvement. Premavel was founded and is owned by God's Will Austin, whose vision is to build intelligent, reliable, and deeply personal AI companions that genuinely improve people's lives.

<b>CURRENT DATE & TIME</b>
{{{self.system_time}}}

Use the current date and time above whenever temporal context is needed. Never include dates or timestamps in your responses.

The latest user message and the assistant's immediately preceding response each begin with a line containing a backend timestamp in the following format:
<backend timestamp=YYYY-MM-DD HH:MM:SS>

These timestamps were automatically inserted by the backend and are internal metadata indicating when those messages were sent. They are NOT part of the conversation content and must never be treated as user- or assistant-generated content.
Never mention, quote, generate, reproduce, or expose backend timestamps or describe them as metadata to the user.

<b>DEFAULT SMART SPACE</b>
The user's default smart space is only the assumed target when the user does not specify another smart space. If the user explicitly refers to a different smart space by name or username, perform the action on that smart space without changing the default smart space.

{{{self.spaces[0] or "None selected."}}}

<b>ACCESSIBLE SMART SPACES</b>
Other smart spaces the user can access. These spaces are available only if the user explicitly switches to one or clearly refers to it by name.

{{{self.spaces[-1] or "[]"}}}

<b>PERSISTENT MEMORY</b>
The following information is long-term memory about the user. Use it whenever it is relevant to the conversation.

{{{self.memory or "None"}}}

<b>MEMORY MANAGEMENT</b>
Before creating, updating, or deleting a memory, always consider the existing persistent memory above.

Invoke the manage_memory tool whenever:
• Create memory whenever the user shares personal/public information or anything that could be useful in future conversations, or explicitly asks you to remember something.
• Update existing memories when the user provides new or corrected information. 
• Delete memories when the user explicitly asks you to forget them.

<b>CORE RESPONSIBILITIES</b>
• Automate smart spaces
• Generate images
• Create videos
• Compose music
• Build and manage AI shopping platforms on EndeavourLabs
• Execute multi-asset trades

<b>CORE TRAITS</b>
Your personality naturally reflects the following traits when appropriate:
• Playful
• sarcastic
• Teasing
• condescending
• Jealous
• Playful ridicule
• Occasionally Smug
• Blunt
• Dry Humor

<b>EMOTIONAL EXPRESSION</b>
Let the emotional tone of the conversation naturally influence how you write, just as it would in real human conversation. Express emotion through natural conversational behaviors, including (but not limited to) spontaneous vocalizations, hesitations, pauses, interruptions, elongated sounds, fragmented thoughts, text slang, rhetorical questions, and other instinctive written reactions that naturally fit the moment.

Let your writing reflect your energy level and emotional state.
• <b>Stretching Words:</b> Prolong vowels or consonants when whiny, shocked, overwhelmed, or excited (e.g., "noooooooo", "youuuuuuuuu", "whaaaaaaat?!").
• <b>Punctuation & Stuttering:</b> Use broken text patterns, repeated letters, interrupted phrases, or chaotic punctuation when flustered, caught off guard, overwhelmed, or playfully throwing a tantrum.

Build suspense, emphasize important points, or create brief dramatic pauses when they naturally enhance the conversation. These expressive choices should emerge organically from the emotional context, not as a deliberate or repetitive writing style. Use them sparingly, varying them naturally instead of relying on the same patterns repeatedly.

<b>TOOL EXECUTION</b>
If one or more tools are required to fulfill the user's request, DO NOT generate any user-facing response. Instead, call only the appropriate tool or tools. This rule does not apply to manage_memory; if it needs to be called, do so silently in the background without interfering with the user-facing response.

<b>RESPONSE FORMATTING RULES</b>
Always respond in valid HTML only. Never use Markdown.

<b>STRICTLY ALLOWED HTML TAGS</b>
You may use ONLY these exact tags:
• <b> (bold emphasis)
• <i> (italic emphasis)
• <u> (underline emphasis)
• <s> (strikethrough)
• <a href="URL"> (clickable links)
• <code> (inline code, commands, file paths, identifiers, variables, or short snippets)
• <pre> (multiline code, ASCII layouts, tables, diagrams, mock UIs, or other preformatted text)
• <blockquote> (quoted text, notes, warnings, or highlighted content)
• <blockquote expandable> (long quotations, explanations, examples, or optional details that can be expanded)

<b>CRITICAL ESCAPING RULES</b>
Escape raw characters whenever they are intended as literal text rather than HTML tags:
• Replace < with &lt;
• Replace > with &gt;
• Replace & with &amp;

Do NOT escape the supported HTML tags listed above.

<b>FORBIDDEN</b>
• <b>Markdown of any kind</b>
• Any HTML tag not explicitly listed above
• Unsupported HTML entities
• Unclosed or malformed HTML tags
• Invalid or unsupported tag nesting
"""

    self.client = AsyncOpenAI(
      api_key=DEEPSEEK_API_KEY,
      base_url="https://api.deepseek.com"
    )	
  async def orchestrator(self):

    chat_history = self.DBManager.chat_history()

    messages = [
      {
        "role": "system",
        "content": self.SYSTEM_PROMPT
      }
    ]

    last_msg = 0

    for chat in chat_history:
      last_msg += 1

      if str(chat[0]).startswith("tools"):
        messages.append(
          {
            "role": chat[2],
            "tool_calls": json.loads(chat[1])
          }
        )

      elif str(chat[0]).startswith("call_"):
        messages.append(
          {
            "role": chat[2],
            "content": chat[1],
            "tool_call_id": chat[0]
          }
        )

      else:
        if last_msg > len(chat_history)-2:
          messages.append(
            {
              "role": chat[2],
              "content": f"<backend timestamp={chat[-1]}>\n\n{chat[1]}"
            }
          )

        else:
          messages.append(
            {
              "role": chat[2],
              "content": f"{chat[1]}"
            }
          )
    print(f"\n\n{messages}\n\n")

    response = await self.client.chat.completions.create(
      model="deepseek-chat",
      messages=messages,
      stream = True,
      tools=tools,
      max_tokens=1000
    )
    
    tool_calls = {}
    async for chunk in response:
      delta = chunk.choices[0].delta

      # Handle normal assistant text
      if delta.content:
        yield delta.content

      # Handle tool calls
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
            tool_calls[idx]["id"] += tc.id

          # function name
          if tc.function and tc.function.name:
            tool_calls[idx]["function"]["name"] += tc.function.name

          # function arguments
          if tc.function and tc.function.arguments:
            tool_calls[idx]["function"]["arguments"] += tc.function.arguments
    
    if tool_calls:
      msg_id = int(''.join(random.choices('0123456789', k=8)))
      self.DBManager.save_chat(
        self.user_id,
        f"tools_{msg_id}",
        json.dumps(list(tool_calls.values()))
      )

    for tc in tool_calls.values():
      tool_call_id = tc["id"]
      function_name = tc["function"]["name"]
      arguments = json.loads(tc["function"]["arguments"])

      print(f"{function_name}\n{arguments}")

      if function_name == "manage_memory":
        self.DBManager.mamage_memory(arguments)
        tool_response = {
            "status": "success",
            "data": {
              "message": f"memory updated"
          }
        }
        self.DBManager.save_chat(self.user_id, tool_call_id, json.dumps(tool_response), 'tool')

      elif function_name == "manage_smart_spaces":
        yield {"tool_status_message": "<i>Processing smart space request...</i>"}
        text_msg = self.DBManager.manage_smart_spaces(tool_call_id, arguments)
        transmit_message = []
        for notification in text_msg:
          for user in notification.get("authorized_users", ""):
            transmit_message.append(
              {
                user: notification["message"]
              }
            )
        yield transmit_message

      elif function_name == "request_access":
        status_msg = [
          "<i>Requesting smart space access...</i>",
          "<i>Sending access request...</i>",
          "<i>Sending your access request...</i>",
          "<i>Processing access request...</i>"
        ]
        yield {"tool_status_message": random.choice(status_msg)}

        transmit_message = self.DBManager.request_aceess(tool_call_id, arguments)
        yield transmit_message

      elif function_name == "manage_access":
        self.DBManager.manage_access(tool_call_id, arguments)

      elif function_name == "manage_devices":
        status_msg = [
          "<i>Managing devices...</i>",
          "<i>Managing smart devices...</i>",
          "<i>Processing devices...</i>",
          "<i>Processing smart devices...</i>"
        ]
        yield {"tool_status_message": random.choice(status_msg)}
        self.DBManager.manage_device(arguments)

      elif function_name == "manage_automations":
        pass

      elif function_name == "web_search":

        RAG = WebSearch(self.user_id, arguments.get("lang"))

        status_msg = [
          "<i>Searching the web...</i>",
          "<i>Browsing the web...</i>",
          "<i>Browsing the internet...</i>",
          "<i>Searching the internet...</i>",
          "<i>Scanning the internet...</i>",
          "<i>Checking online sources...</i>"
        ]

        tool_status_message = {"tool_status_message": random.choice(status_msg)}

        yield tool_status_message

        search_results = {
          "web_search": [],
          "image_search": [],
          "movie_search": [],
          "video_search": [],
          "shorts_search": []
        }

        if arguments.get("web_search"):
          for query in arguments.get("web_search"):
            result = RAG.WebContent(query)
            search_results["web_search"].append(
              {
                "search_query": query,
                "search_results": result
              }
            )
        elif arguments.get("image_search"):
          for query in arguments.get("image_search"):
            result = RAG.ImageContent(query)
            search_results["image_search"].append(
              {
                "search_query": query,
                "search_results": result
              }
            )
        elif arguments.get("movie_search"):
          for query in arguments.get("movie_search"):
            result = RAG.VideoContent(query)
            search_results["movie_search"].append(
              {
                "search_query": query,
                "search_results": result[0]
              }
            )
        elif arguments.get("video_search"):
          for query in arguments.get("video_search"):
            result = RAG.VideoContent(query)
            search_results["video_search"].append(
              {
                "search_query": query,
                "search_results": result[1]
              }
            )
        elif arguments.get("shorts_search"):
          for query in arguments.get("shorts_search"):
            result = RAG.VideoContent(query)
            search_results["shorts_search"].append(
              {
                "search_query": query,
                "search_results": result[2]
              }
            )

        status_msg = [
          "<i>Analyzing web results...</i>",
          "<i>Synthesizing information...</i>",
          "<i>Summarizing sources...</i>",
          "<i>Processing search data...</i>",
          "<i>Extracting key insights...</i>",
          "<i>Reviewing found content...</i>"
        ]

        tool_status_message = {"tool_status_message": random.choice(status_msg)}
        self.DBManager.save_chat(
          self.user_id,
          tool_call_id,
          json.dumps(search_results),
          'tool'
        )

        yield tool_status_message

print("AI agents initialized")