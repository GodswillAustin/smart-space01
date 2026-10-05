from pathlib import Path
import sqlite3
import aiosqlite
import asyncio
import hashlib
import bcrypt
import json
import uuid
from zoneinfo import ZoneInfo
from datetime import datetime
import secrets

from email_service import ResendMail
from email_messages import create_space, update_space, delete_space
from timer import scheduler
from notifier import notification

DB_DIR = Path("database")
DB_DIR.mkdir(exist_ok=True)

class PasswordHasher:
    
    @staticmethod
    async def hash_password(password: str) -> bytes:
        password_bytes = password.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        return hashed
    
    @staticmethod
    async def verify_password(password: str, hashed_password: bytes) -> bool:
        password_bytes = password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_password)
    
class DatabaseArchitecture:

    @staticmethod
    def accounts_db():
        return aiosqlite.connect(
        DB_DIR / "accounts.db",
        timeout=10
    )

    @staticmethod
    def charts_db():
        return aiosqlite.connect(
        DB_DIR / "spaces.db",
        timeout=10
    )

    @staticmethod
    def charts_db():
        return aiosqlite.connect(
        DB_DIR / "charts.db",
        timeout=10
    )

    @staticmethod
    async def create_all():
        await Tables.user_table()
        await Tables.space_table()

class Tables:

  @staticmethod
  async def space_table():
    async with DatabaseArchitecture.accounts_db() as conn:

      await conn.execute("PRAGMA foreign_keys = ON;")

      await conn.execute("""
        CREATE TABLE IF NOT EXISTS spaces (
          username TEXT PRIMARY KEY,
          password TEXT,
          space_name TEXT,
          space_type TEXT,
          email TEXT,
          address TEXT,
          owner_id INTEGER,
          authorised_users_telegram_id TEXT,
          registered_devices TEXT,
          scheduled_loop_actions TEXT,
          pairing_token INTEGER,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
      """)

      await conn.commit()

  @staticmethod
  async def user_table():
    async with DatabaseArchitecture.accounts_db() as conn:

      await conn.execute("PRAGMA foreign_keys = ON;")

      await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
          user_id INTEGER PRIMARY KEY,
          full_name TEXT NOT NULL,
          gender TEXT,
          phone_number INTEGER,
          address TEXT,
          time_zone,
          persistent_memory TEXT,
          default_space TEXT,
          available_spaces TEXT,
          AI_voice_id TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
      """)

      await conn.commit()

  @staticmethod
  async def chat_table(chat_id):
    async with DatabaseArchitecture.charts_db() as conn:

      await conn.execute("PRAGMA foreign_keys = ON;")

      await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS chat_{chat_id} (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          message_id TEXT UNIQUE,
          message_type TEXT,
          role TEXT,
          reasoning TEXT,
          content TEXT,
          tool TEXT,
          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
      """)

      await conn.commit()

class Authenticator:
    def __init__(self, user_id):
        self.user_id = user_id

    generate_id = staticmethod(
        lambda user_id: hashlib.sha256(str(user_id).encode()).hexdigest()
    )

    async def user_exists(self):
        async with DatabaseArchitecture.accounts_db() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM users WHERE user_id=?",
                (self.user_id,)
            )

            return await cursor.fetchone() is not None

    async def chat_exists(self):
        table_name = f"chat_{self.user_id}"

        async with DatabaseArchitecture.charts_db() as conn:
            cursor = await conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
            )

            return await cursor.fetchone() is not None

    @staticmethod
    async def username_exists(username):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute(
                "SELECT 1 FROM spaces WHERE username = ? LIMIT 1",
                (username,)
            )
            return await cursor.fetchone() is not None

    async def verify_user(self):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute(
                "SELECT 1 FROM users WHERE user_id = ? LIMIT 1",
                (self.user_id,)
            )
            return await cursor.fetchone() is not None

    async def fetch_space(self):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute("""
                SELECT
                    default_space,
                    available_spaces
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))
            default_space, available_spaces = await cursor.fetchone()
            
            return (
                json.loads(default_space or "{}"),
                json.loads(available_spaces or "[]")
            )

    async def space_data(self, username):
        async with DatabaseArchitecture.accounts_db() as conn:
            cursor = await conn.execute("""
                SELECT
                    password,
                    space_name,
                    space_type,
                    email,
                    address,
                    owner_id,
                    authorised_users_telegram_id,
                    registered_devices,
                    scheduled_recurring_actions
                FROM spaces
                WHERE username = ?
                """, (username,))
            return await cursor.fetchone()

    async def verifyPermission(self, username, password):
        data = await self.space_data(username)
        if all(x is None for x in data):
            tool_response = {
                "status": "error",
                "error": {
                    "code": "SMART_SPACE_NOT_FOUND",
                    "message": "No smart space was found with the specified username.",
                    "username": username
                }
            }
            return tool_response

        (
            stored_hash,
            space_name,
            space_type,
            email,
            address,
            owner_id,
            authorised_users_telegram_id,
            registered_devices,
            scheduled_recurring_actions
        ) = data

        if self.user_id != owner_id:
            tool_response =  {
                "status": "error",
                "error": {
                    "message": (
                        f"The user is not authorised to access the smart space with the username '{username}'."
                    )
                }
            }
            return tool_response

        verified_password = await PasswordHasher.verify_password(password, stored_hash)
        if not verified_password:
            tool_response = {
                "status": "error",
                "error": {
                    "message": f"The password provided for the smart space '{username}' is incorrect."
                }
            }
            return tool_response
        return (
            stored_hash, 
            space_name, 
            space_type, 
            email, 
            address, 
            owner_id, 
            authorised_users_telegram_id, 
            registered_devices, 
            scheduled_recurring_actions
        )

    async def verify_user_access(self):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute("""
                SELECT value
                FROM space, json_each(authorised_users_telegram_id)
                WHERE value = ?
                LIMIT 1
            """, (self.user_id,))

            result = await cursor.fetchone()

            return result[0]

class ManageUsers(Authenticator):
    def __init__(self, user_id):
        super().__init__(user_id)

    async def register_user(self, full_name):

        user_verifier = await super().verify_user()
        if user_verifier:
            return True
        
        async with DatabaseArchitecture.accounts_db() as conn:

            await conn.execute(f"""
                INSERT INTO users (
                    user_id,
                    full_name,
                    persistent_memory,
                    default_space,
                    available_spaces
                )
                VALUES (?, ?, ?, ?, ?)
                """, (
                    self.user_id,
                    full_name,
                    json.dumps({}),
                    json.dumps({}),
                    json.dumps([])
                ))
        
            await conn.commit()

    @staticmethod
    async def save_chat(
        user_id,
        message_id,
        message_type='text',
        role='assistant',
        reasoning=None,
        content=None,
        tool=None
    ):
        
        async with DatabaseArchitecture.charts_db() as conn:

            try:
                await conn.execute(f"""
                    INSERT INTO chat_{user_id} (
                        message_id,
                        message_type,
                        role,
                        reasoning,
                        content,
                        tool
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        message_id,
                        message_type,
                        role,
                        reasoning,
                        content,
                        tool
                ))
                await conn.commit()
            except sqlite3.OperationalError:
                validate = await Authenticator(user_id).ph_loc()

                if not await super().user_exists():
                    return (
                        "<b>Setup required</b>\n\n"
                        "Before you can access our services, please accept our "
                        "<b>Terms and Conditions</b> and provide the required information "
                        "to complete your setup."
                    )
                elif not validate[0] and not validate[1]:
                    return (
                        "<b>Contact information and location required</b>\n\n"
                        "To continue, please share your <b>contact information</b> and "
                        "<b>location</b>, as required when you accepted our Terms and Conditions."
                    )
                elif not validate[0]:
                    return (
                        "<b>Contact information required</b>\n\n"
                        "Please share your <b>contact information</b> to continue."
                    )
                elif not validate[1]:
                    return (
                        "<b>Location required</b>\n\n"
                        "To continue, please share your <b>location</b>."
                    )
                else:
                    return (
                        "<b>One last thing!</b>\n\n"
                        "Please provide your <b>gender</b> to continue."
                    )

    async def chat_history(self, limit=10):
        async with DatabaseArchitecture.charts_db() as conn:

            cursor = await conn.execute(f"""
                SELECT message_id, message_type, role, reasoning, content, tool, timestamp
                FROM chat_{self.user_id}
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))

            rows = await cursor.fetchall()

            return rows[::-1]

    async def del_history(self):
        async with DatabaseArchitecture.charts_db() as conn:

            cursor = await conn.execute(f"""
            SELECT message_id
            FROM chat_{self.user_id}
            """)

            rows = await cursor.fetchall()

            await conn.execute(f"""
                DELETE FROM chat_{self.user_id}
                """)

            await conn.commit()

            return [row[0] for row in rows]

    async def save_number(self, ph):
        async with DatabaseArchitecture.accounts_db() as conn:
            await conn.execute(f"""
                UPDATE users
                SET phone_number = ?
                WHERE user_id = ?
            """, (ph, self.user_id))
            await conn.commit()

    async def save_gender(self, gender):
        async with DatabaseArchitecture.accounts_db() as conn:
            await conn.execute(f"""
                UPDATE users
                SET gender = ?
                WHERE user_id = ?
            """, (gender, self.user_id))
            await conn.commit()

    async def save_location(self, loc):
        async with DatabaseArchitecture.accounts_db() as conn:
            await conn.execute(f"""
                UPDATE users
                SET address = ?
                WHERE user_id = ?
            """, (loc, self.user_id))
            await conn.commit()

    async def save_time_zone(self, time_zone):
        async with DatabaseArchitecture.accounts_db() as conn:
            await conn.execute(f"""
                UPDATE users
                SET time_zone = ?
                WHERE user_id = ?
            """, (time_zone, self.user_id))
            await conn.commit()

    async def get_time_zone(self):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute("""
                SELECT time_zone
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))

            time_zone = await cursor.fetchone()

            return time_zone[0]

    async def get_ph_loc(self):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute("""
                SELECT phone_number, address
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))

            return await cursor.fetchone()

    async def mamage_memory(self, arguments):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute("""
                SELECT persistent_memory
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))

            row = await cursor.fetchone()
            memory = json.loads(row[0]) if row and row[0] else {}

            memory.update(arguments.get("create", {}))
            memory.update(arguments.get("update", {}))

            for key in arguments.get("delete", []):
                memory.pop(key, None)

            memory = json.dumps(memory)

            await cursor.execute(f"""
                UPDATE users
                SET persistent_memory = ?
                WHERE user_id = ?
            """, (memory, self.user_id))
            await conn.commit()

    async def memory(self):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute("""
                SELECT persistent_memory
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))

            data =  await cursor.fetchone()

            return json.loads(data[0]) or "No memories stored."

    async def update_AI_voice_id(self, AI_voice_id):
        async with DatabaseArchitecture.accounts_db() as conn:
            await conn.execute("""
                UPDATE users
                SET AI_voice_id = ?
                WHERE user_id = ?
            """, (
                json.dumps(AI_voice_id),
                self.user_id
            ))
            await conn.commit()

    async def get_AI_voice_id(self):
        async with DatabaseArchitecture.accounts_db() as conn:
            cursor = await conn.execute("""
                SELECT AI_voice_id
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))

            AI_voice_id = await cursor.fetchone()
            return AI_voice_id[0] or "iv02"
    
class ManageSpaces(ManageUsers):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.user_id = user_id

    async def update_available_space(self, available_spaces):
        async with DatabaseArchitecture.accounts_db() as conn:
            await conn.execute("""
                UPDATE users
                SET available_spaces = ?
                WHERE user_id = ?
            """, (
                json.dumps(available_spaces),
                self.user_id
            ))
            await conn.commit()

    async def update_default_space(self, default_space):
        async with DatabaseArchitecture.accounts_db() as conn:
            await conn.execute("""
                UPDATE users
                SET default_space = ?
                WHERE user_id = ?
            """, (
                json.dumps(default_space),
                self.user_id
            ))
            await conn.commit()

    async def manage_smart_spaces(self, tool_id, arguments):

        tool_response = []
        async with DatabaseArchitecture.accounts_db() as conn:

            generate_username = lambda name: f"@{''.join(name.split())}_{uuid.uuid4().hex[:4]}".lower()

            for register in arguments.get("create", ""):
                space_type = register.get('space_type', 'apartment')
                email = register.get('email')
                address = register.get('address')
                password = register.get('password')
                if len(password) < 8:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "code": "PASSWORD_TOO_SHORT",
                                "message": "The password must be at least 8 characters long."
                            }
                        }
                    )
                    continue
                hashed_password = await PasswordHasher.hash_password(password)

                for _ in range(5):
                    username = generate_username(register.get("space_name"))
                    _username_exists_ = await super().username_exists(username)
                    if not _username_exists_:
                        break

                if _username_exists_:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "message": f"Failed to register the {space_type}. Please try again or change the space name."
                            }
                        }
                    )
                    continue
                
                space_name = register.get('space_name')
                default_space, available_spaces = await super().fetch_space()

                if (space_name == default_space.get("space_name") or any(
                        space.get("space_name") == space_name
                        for space in available_spaces
                    )
                ):
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "code": "SMART_SPACE_NAME_EXISTS",
                                "message": (
                                    "A smart space with this name already exists in your accessible "
                                    "smart spaces. Duplicate smart space names are not allowed."
                                ),
                                "space_type": space_type,
                                "space_name": space_name,
                                "resolution": (
                                    "Choose a different name or remove the existing smart space "
                                    "before trying again."
                                )
                            }
                        }
                    )
                    continue

                content = create_space(
                    space_name, 
                    username, 
                    space_type, 
                    address, 
                    email
                )
                subject = "Welcome to Will Smart Spaces"
                try:
                    mail = ResendMail(email, subject, content)
                    await mail.MAIL()
                except Exception:
                    tool_response.append(
                        {
                            "status": "error",
                            "error_message": f"The email address '{email}' is invalid."
                        }
                    )
                    continue

                cursor = await conn.execute(f"""
                INSERT INTO spaces (
                    username,
                    password,
                    space_name,
                    space_type,
                    email,
                    address,
                    owner_id,
                    authorised_users_telegram_id,
                    registered_devices,
                    scheduled_recurring_actions
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    username,
                    hashed_password,
                    space_name,
                    space_type,
                    email,
                    address,
                    self.user_id,
                    json.dumps({}),
                    json.dumps([]),
                    json.dumps([])
                ))
                await conn.commit()

                space_info = {
                        "space_name": space_name,
                        "username": username,
                        "space_type": space_type,
                        "space_address": address,
                        "user_role": "owner",
                        "authorised_users_telegram_id": [],
                        "registered_devices": [],
                        "scheduled_recurring_actions": []
                    }

                if default_space:
                    available_spaces.extend([default_space])
                    await self.update_available_spaces(available_spaces, self.user_id)

                await self.update_default_space(space_info, self.user_id)
                
                tool_response.append(
                    {
                        "status": "success",
                        "data": {
                            "message": (
                                f"Smart {space_type} registered successfully."
                                "Use this username to grant temporary or permanent access "
                                "to the smart space and to manage access permissions."
                            ),
                            "space_type": space_type,
                            "space_name": space_name,
                            "username": username
                        }
                    }
                )

            for update in arguments.get("update", ""):

                old_username = update.get("username")
                password = update.get("password")

                auth = await super().verifyPermission(old_username, password)
                if len(auth) <= 1:
                    tool_response.append(auth)
                    continue

                old_hashed = auth[0]
                old_space_name = auth[1]
                old_space_type = auth[2]
                old_email = auth[3]
                old_address = auth[4]
                owner_id = auth[5]
                authorised_users_telegram_id = auth[6]

                new_space_name = update.get("space_name")

                if new_space_name:
                    for _ in range(5):
                        candidate = generate_username(new_space_name)
                        username_exists = await super().username_exists(candidate)
                        if not username_exists:
                            new_username = candidate
                            break

                    if new_username is None:
                        tool_response.append(
                            {
                                "status": "error",
                                "error": {
                                    "message": (
                                        f"Unable to update the smart space "
                                        f"'{old_username}'. Please try again."
                                    )
                                }
                            }
                        )
                        continue
                else:
                    new_username = old_username
               
                new_space_name = new_space_name or old_space_name
                new_space_type = update.get("space_type", old_space_type)
                email = update.get("email", old_email)
                new_address = update.get("address", old_address)

                new_password = update.get("new_password")
                hashed_password = await PasswordHasher.hash_password(new_password) if new_password else old_hashed

                changes = [
                    '<b>Smart space updated</b>\n'
                    f'Your smart space "<b>{old_space_name}</b>" has been updated.\n'
                    '<blockquote expandable>'
                ]

                if old_space_name != new_space_name:
                    changes.append(
                        f"<b>• Name:</b> {old_space_name} → {new_space_name}\n"
                    )

                    changes.append(
                        f"<b>• Username:</b> {old_username} → {new_username}\n"
                    )

                if old_space_type != new_space_type:
                    changes.append(
                        f"<b>• Type:</b> {old_space_type} → {new_space_type}\n"
                    )

                if old_address != new_address:
                    changes.append(
                        f"<b>• Address:</b> {new_address}\n"
                    )

                if old_email != email:
                    changes.append(
                        f"<b>• Email:</b> {old_email} → {email}\n"
                    )

                if new_password:
                    changes.append(
                        "<b>• Password:</b> Changed"
                    )

                msg = "\n".join(changes) + "</blockquote>"


                cursor = await conn.execute("""
                    UPDATE spaces
                    SET
                        username = ?,
                        password = ?,
                        space_name = ?,
                        space_type = ?,
                        email = ?,
                        address = ?
                    WHERE username = ?
                """, (
                    new_username,
                    hashed_password,
                    new_space_name,
                    new_space_type,
                    email,
                    new_address,
                    old_username
                ))
                await conn.commit()

                authorised_users_telegram_id = json.loads(authorised_users_telegram_id)

                for user_id in [*authorised_users_telegram_id]:
                    default_space, available_spaces = await super().fetch_space()

                    if default_space.get("space_name") == old_space_name:
                        default_space["space_name"] = new_space_name
                        default_space["username"] = new_username
                        default_space["space_type"] = new_space_type
                        default_space["address"] = address

                        await self.update_default_space(default_space, user_id)
                        await notification(user_id, msg)

                    else:
                        for space in available_spaces:
                            if space.get("space_name") == old_space_name:
                                space["space_name"] = new_space_name
                                space["username"] = new_username
                                space["space_type"] = new_space_type
                                default_space["address"] = address

                                await self.update_available_space(available_spaces, user_id)
                                await notification(user_id, msg)
                                break
                tool_msg = {
                    "status": "success",
                    "message": msg
                }

                content = update_space(msg.replace("\n", "<br>").replace("<blockquote>", "").replace("</blockquote>", ""))
                subject = f'Smart space "{new_space_name}" has been updated'

                try:
                    mail = ResendMail(email, subject, content)
                    await mail.MAIL()
                except Exception:
                    tool_msg["status"] = "warning"
                    tool_msg["email_error"] = (
                        f"The smart space was successfully updated, but the notification "
                        f"could not be sent to '{email}'. The email address may be invalid "
                        f"or unreachable. Please update the smart space with the correct "
                        f"email address."
                    )
                tool_response.append(tool_msg)

            for delete in arguments.get("delete", ""):
                username = delete["username"]
                password = delete["password"]

                auth = await super().verifyPermission(old_username, password)
                if len(auth) <= 1:
                    tool_response.append(auth)
                    continue

                old_hashed = auth[0]
                old_space_name = auth[1]
                old_space_type = auth[2]
                old_email = auth[3]
                old_address = auth[4]
                owner_id = auth[5]
                authorised_users_telegram_id = auth[6]

                await cursor.execute("DELETE FROM spaces WHERE username = ?", (username,))
                await conn.commit()

                tool_msg = {
                        "status": "success",
                        "message": f"{space_name} smart {space_type} has been deleted successfully"
                    }

                msg = f"The smart {space_type} <b>{space_name}</b> have been deleted."

                authorised_users_telegram_id = json.loads(authorised_users_telegram_id)
                for user_id in [*authorised_users_telegram_id]:
                    default_space, available_spaces = await super().fetch_space()

                    if space_name == default_space["space_name"]:
                        await self.update_default_space(None, user_id)
                        await notification(user_id, msg)
                    else:
                        for space in available_spaces:
                            if space_name in space["space_name"]:
                                available_spaces.remove(space)
                                await self.update_available_space(available_spaces, user_id)
                                await notification(user_id, msg)
                                break

                content = delete_space(space_name, username, space_type, address)
                subject = "Security Notice: A smart space was deleted"
                try:
                    mail = ResendMail(email, subject, content)
                    await mail.MAIL()
                except Exception:
                    tool_msg["status"] = "warning"
                    tool_msg["warning_message"] = (
                        f"The smart {space_type} was deleted successfully, but the email address "
                        f"'{email}' is invalid, so the deletion notification could not be sent."
                    )
                tool_response.append(tool_msg)

        await super().save_chat(
            user_id=self.user_id, 
            message_id=tool_id, 
            message_type='tool_response',
            role='tool',
            tool=json.dumps(tool_response)
        )

    async def manage_space_access(self, tool_id, arguments):
        async with DatabaseArchitecture.accounts_db() as conn:

            username = arguments.get("space_username")
            password = arguments.get("password")

            auth = await super().verifyPermission(username, password)
            if len(auth) <= 1:
                await super().save_chat(
                    user_id=self.user_id, 
                    message_id=tool_id, 
                    message_type='tool_response',
                    role='tool',
                    tool=json.dumps(auth)
                )
                return

            (
                hashed,
                space_name, 
                space_type, 
                email, 
                address,
                owner_id,
                authorised_users_telegram_id
            ) = auth

            space_name = auth[1]
            space_type = auth[2]
            email = auth[3]
            address = auth[4]
            owner_id = auth[5]
            authorised_users_telegram_id = auth[6]
            registered_devices = auth[7]
            scheduled_recurring_actions = auth[8]

            target_id = arguments.get("target_id")
            access_validity = arguments.get("access_validity")
            starts_at = access_validity.get("starts_at")
            expires_at = access_validity.get("expires_at")

            access_level = arguments.get("access_level")

            user_timezone = await super().get_time_zone()
            tz = ZoneInfo(user_timezone)
            now = datetime.now(tz)
            system_time = now.isoformat(timespec='seconds')

            default_space, available_spaces = await super().fetch_space()
            async def grant_access():
                space_info = {
                    "space_name": space_name,
                    "username": username,
                    "space_type": space_type,
                    "space_address": address,
                    "user_role": "member" if owner_id != target_id else "owner",
                    "authorised_users_telegram_id": [authorised_users_telegram_id],
                    "registered_devices": [registered_devices],
                    "scheduled_recurring_actions": [scheduled_recurring_actions]
                }
                if default_space:
                    await self.update_available_space(
                        available_spaces.extend([default_space]),
                        target_id
                    )
                await self.update_default_space(space_info, target_id)

            async def revoke_access():
                if default_space.get("username") == username:
                    await self.update_default_space({}, target_id)
                    return
                for space in available_spaces:
                    if space.get("username") == username:
                        available_spaces.remove(space)
                        await self.update_available_space(
                            available_spaces,
                            target_id
                        )
                        return

            async def task_timer():
                schedule =  scheduler(starts_at, expires_at, system_time)
                if starts_at:
                    task = asyncio.create_task(schedule.Start_at())
                    await task
                    msg_id = secrets.token_urlsafe(16)
                    await notification(target_id, target_start_msg)
                    msg = owner_start_msg.replace("<backend_notification>").replace("</backend_notification>")
                    await notification(self.user_id, msg)
                    await super().save_chat(
                        user_id=self.user_id, 
                        message_id=msg_id, 
                        role='user',
                        content=owner_start_msg
                    )
                if access_level == "denied":
                    await revoke_access()
                else:
                    await grant_access()
                    
                if expires_at:
                    task = asyncio.create_task(schedule.End_at()) 
                    await task
                    msg_id = secrets.token_urlsafe(16)
                    await notification(target_id, target_end_msg)
                    msg = owner_end_msg.replace("<backend_notification>").replace("</backend_notification>")
                    await notification(self.user_id, msg)
                    await super().save_chat(
                        user_id=self.user_id, 
                        message_id=msg_id, 
                        role='user',
                        content=owner_end_msg
                    )
                    if access_level != "denied":
                        await revoke_access()
                if access_level == "denied" and expires_at:
                    await grant_access()

            cursor = await conn.execute("""
                SELECT full_name
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))
            fullname = await cursor.fetchone()[0]

            if access_level == "unrestricted":
                tool_response = {
                    "status": "success",
                    "message": (
                        f"Unrestricted access for {fullname} to the smart {space_type} "
                        f"{space_name} has been successfully {'scheduled' if starts_at else 'granted'}.\n"
                        f"Access Initiate at: {starts_at}"
                    )
                }
                owner_start_msg = (
                    "<backend_notification>"
                    f"<b>Scheduled Unrestricted Access Activated</b>\n"
                    f"Unrestricted access has been successfully granted to "
                    f"<b>{fullname}</b> and is now active. "
                    f"Access will remain active until it is revoked or denied.\n"
                    f"<b>Access Started At:</b> {starts_at}"
                    "</backend_notification>"
                )
                target_start_msg = (
                    f"<b>Smart Space Access Granted</b>\n\n"
                    f"The admin of the smart {space_type} <b>{space_name}</b> "
                    f"has granted you unrestricted access.\n\n"
                    f"Your access is now active and will remain active "
                    f"until it is revoked or denied.\n\n"
                )
                asyncio.create_task(task_timer())   

            elif access_level == "restricted":
                tool_response = {
                    "status": "success",
                    "message": (
                        f"restricted access for {fullname} to the smart {space_type} "
                        f"{space_name} has been successfully {'scheduled' if starts_at else 'granted'}.\n"
                        f"Access will begin at: {starts_at}"
                        f"Access will expire at: {expires_at}"
                    )
                }
                owner_start_msg = (
                    "<backend_notification>"
                    f"{'Scheduled restricted' if starts_at else 'Restricted'} access activated.\n\n"
                    f"Access has been granted to {fullname} and will remain active until the scheduled end time.\n"
                    f"Access will end at: {expires_at}"
                    "</backend_notification>"
                )
                owner_end_msg = (
                    "<backend_notification>"
                    f"Scheduled restricted access for {fullname} has expired. "
                    f"Access has been revoked and {fullname} no longer has access to the smart space.\n"
                    f"Access expired at: {starts_at}\n"
                    f"Scheduled end time: {expires_at}"
                    "</backend_notification>"
                )

                target_start_msg = (
                    "<b>Scheduled Smart Space Access Activated</b>\n\n"
                    f"The admin of the smart {space_type} <b>{space_name}</b> "
                    f"has granted you restricted access to the smart {space_type}\n\n"
                    f"Your access is now active and will remain available "
                    f"until the scheduled expiration time.\n\n"
                    f"<b>Access Expires At:</b> {expires_at}"
                )
                target_end_msg = (
                    "<b>Scheduled Smart Space Access Expired</b>\n\n"
                    f"Your scheduled restricted access to the smart "
                    f"<b>{space_type} {space_name}</b> has expired.\n\n"
                    f"Your access has been automatically revoked, and you "
                    f"can no longer access this smart space."
                )
                asyncio.create_task(task_timer()) 

            elif access_level == "revoke":
                if starts_at:
                    tool_response = {
                        "status": "success",
                        "message": (
                            f"revoke access for {fullname} to the smart {space_type} "
                            f"{space_name} has been successfully scheduled.\n"
                            f"revoke will begin at: {starts_at}"
                        )
                    }
                    owner_start_msg = (
                        "<backend_notification>"
                        f"<b>Scheduled Access Revocation Activated</b>\n"
                        f"Access to the smart space has been revoked for <b>{fullname}</b> "
                        f"and will remain restricted until the scheduled expiration time.\n"
                        f"<b>Access Revoked At:</b> {starts_at}\n"
                        "</backend_notification>"
                    )

                    owner_end_msg = (
                        "<backend_notification>"
                        f"<b>Scheduled Access Revocation Expired</b>\n"
                        f"Access to the smart space has been automatically restored. "
                        f"<b>{fullname}</b> is now authorized to access the smart space.\n"
                        f"<b>Access Restored At:</b> {expires_at}\n"
                        "</backend_notification>"
                    )

                    target_start_msg = (
                        f"<b>Smart Space Access Revoked</b>\n\n"
                        f"Your access to the <b>smart {space_type} {space_name}</b> "
                        f"has been temporarily revoked as scheduled by the owner"
                        f"<b>{fullname}</b>.\n\n"
                        f"You will regain access automatically when the "
                        f"restriction expires.\n\n"
                        f"<b>Access Revoked At:</b> {starts_at}\n"
                        f"<b>Scheduled Restoration:</b> {expires_at}"
                    )

                    target_end_msg = (
                        f"<b>Smart Space Access Restored</b>\n\n"
                        f"Your access to the <b>smart {space_type} {space_name}</b> "
                        f"has been automatically restored following the expiration "
                        f"of the scheduled restriction.\n\n"
                        f"You can now access the smart space as usual.\n\n"
                        f"<b>Access Restored At:</b> {expires_at}"
                    )
                await task_timer()

            else:
                username = arguments.get('username')
                space = await super().space_data(username)

                (
                    hashed,
                    space_name, 
                    space_type, 
                    email, 
                    address,
                    owner_id,
                    authorised_users_telegram_id
                ) = space

                content = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; max-width: 600px; margin: auto; padding: 32px; color: #333;">

        <h2 style="margin-top: 0;">
            🔐 Smart Space Access Request
        </h2>

        <p>
            <strong>{fullname}</strong> is requesting access to your smart {space_type.lower()} <strong>"{space_name.title()}"</strong>.
        </p>

        <p>
            Review this request and decide the level of access you'd like to grant.
        </p>

        <h3 style="margin-bottom: 12px;">
            Available Access Options
        </h3>

        <ul style="line-height: 1.8; padding-left: 22px;">
            <li>⏳ <strong>Temporary Access</strong> — Grant access for a custom duration. Access will automatically expire at the time you choose.</li>
            <li>♾️ <strong>Permanent Access</strong> — Grant ongoing access with no expiration date.</li>
        </ul>

        <p>
            To approve this request, simply tell <strong>Will</strong> that you'd like to grant access and specify whether it should be <strong>temporary</strong> or <strong>permanent</strong>. If you choose temporary access, Will will ask you for the expiration time before granting access.
        </p>

        <p>
            You remain in complete control of your smart space. You can modify permissions, revoke access, or cancel this request at any time, regardless of the access level you choose.
        </p>

        <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 32px 0;">

        <p style="font-size: 13px; color: #777;">
            This is an automated email from <strong>Will</strong>. Please do not reply to this message.
        </p>

    </div>
    """
                subject = "Smart Space Access Request"
                await ResendMail(email, subject, content)

                message = (
                    f"<b>{fullname}</b> is requesting access to your smart {space_type.lower()}, "
                    f"<b>'{space_name.title()}'</b>.\n\n"
                    "Review this request and choose the level of access you'd like to grant:\n"
                    "• <b>Temporary access</b> with a custom expiration time.\n"
                    "• <b>Permanent access</b> with no expiration.\n\n"
                    "You can modify, revoke, or cancel access at any time, "
                    "regardless of the permissions you grant."
                )

                await notification(owner_id, message)

                tool_response = {
                    "status": "success",
                    "message": f"Access request submitted successfully to the smart {space_type.lower()} '{space_name}'.",
                    "username": username,
                    "request_status": "pending",
                    "status_message": "Access will be granted once the owner/admin approves."
                }

            await super().save_chat(
                user_id=self.user_id, 
                message_id=tool_id, 
                message_type="tool_response",
                role='tool',
                tool=json.dumps(tool_response)
            )

    async def update_pairing_token(self, username, pairing_token):
        async with DatabaseArchitecture.accounts_db() as conn:
            cursor = await conn.execute("""
                UPDATE spaces
                SET pairing_token = ?
                WHERE username = ? AND owner_id = ?
            """, (pairing_token, username, self.user_id))

            await conn.commit()

            if cursor.rowcount == 0:
                return False
            return True

    async def get_pairing_token(self, username):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute("""
                SELECT pairing_token
                FROM spaces
                WHERE username = ? AND owner_id = ?
            """, (username, self.user_id,))

            pairing_token = await cursor.fetchone()
            return pairing_token[0]

    async def manage_device(self, tool_id, arguments):
        async with DatabaseArchitecture.accounts_db() as conn:

            cursor = await conn.execute("""
                SELECT registered_devices
                FROM spaces
                WHERE owner_id = ?
            """, (self.user_id,))

            registered_devices = json.loads(await cursor.fetchone())

            if not isinstance(registered_devices, list):
                status = {
                    "status": "error",
                    "code": "NO_SMART_SPACE_FOUND",
                    "message": "No smart spaces found where the user has owner privileges."
                }
                await super().save_chat(
                    user_id=self.user_id, 
                    message_id=tool_id, 
                    message_type="tool_response",
                    role='tool',
                    tool=json.dumps(status)
                )
                return

            tool_response = []

            # Create a lookup table using device_id
            devices = {
                item["device"]["device_id"]: item
                for item in registered_devices
            }


            # UPDATE DEVICES
            for operation in arguments.get("update", []):

                device_id = operation.get("device_id")

                device = devices.get(device_id)

                if not device:
                    continue

                if "alias" in operation:
                    device["alias"] = operation["alias"]

                if "location" in operation:
                    device["location"] = operation["location"]

                tool_response.append(
                    {
                        "status": "success",
                        "message": "Device updated successfully.",
                        "id": device_id,
                    }
                )

            # DELETE DEVICES
            for operation in arguments.get("delete", []):

                device_id = operation.get("device_id")

                devices.pop(device_id, None)
                tool_response.append(
                    {
                        "status": "success",
                        "message": "Device removed successfully.",
                        "id": device_id
                    }
                )

            # Convert lookup dictionary back to a list
            registered_devices = list(devices.values())
            
            await conn.execute(f"""
                UPDATE spaces
                SET registered_devices = ?
                WHERE owner_id = ?
            """, (json.dumps(registered_devices), self.user_id))
            await conn.commit()

            await super().save_chat(
                user_id=self.user_id, 
                message_id=tool_id, 
                message_type="tool_response",
                role='tool',
                tool=json.dumps(tool_response)
            )

    @staticmethod
    async def register_device(device):
        username = device.get("username")
        device_type = device.get("device").get("device_type")
        pairing_token = device.get("pairing_token")

        async with DatabaseArchitecture.accounts_db() as conn:
        
            cursor = await conn.execute("""
                SELECT
                    space_name,
                    space_type,
                    email,
                    owner_id,
                    authorised_users_telegram_id,
                    registered_devices, 
                    pairing_token
                FROM spaces
                WHERE username = ?
            """, (username,))
            space_info = json.loads(await cursor.fetchone())

            if not space_info:
                return {"code": 70604}
            elif pairing_token != space_info[6]:
                return {"code": 70604}

            (
                space_name,
                space_type,
                email,
                owner_id,
                authorised_users_telegram_id,
                registered_devices, 
                stored_token
            ) = space_info

            registered_devices.append(
                {
                    "alias": None,
                    "location": None,
                    "device": device.get("device")
                }
            )

            await conn.execute("""
                UPDATE spaces
                SET 
                    registered_devices = ?,
                    pairing_token = ? 
                WHERE username = ?
            """, (json.dumps(registered_devices), None, username))
            await conn.commit()

            owner_msg = f"""
<b>Device Registered Successfully</b>
Your <b>{device_type}</b> has been successfully added to your Smart {space_type} <b>{space_name}</b>. You can now control and monitor it through IV.
"""
            members_msg = f""" 
<b>New Device Added</b> 
A new <b>{device_type}</b> has been successfully registered in this Smart {space_type} <b>{space_name}</b>. You can now access and control it through IV based on your assigned permissions.
"""
            await notification(owner_id, owner_msg)
            for user_id in [*authorised_users_telegram_id]:
                await notification(user_id, members_msg)

            return {"code": 70605}

    async def verify_auth(self, space_username):
        async with DatabaseArchitecture.accounts_db() as conn:
            cursor = await conn.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM json_each(authorised_users_telegram_id)
                    WHERE key = ?
                )
                FROM spaces
                WHERE username = ?
            """, (str(self.user_id), space_username))
            row = await cursor.fetchone()

            if row is None:
                return False
            return bool(row[0])

    @staticmethod
    async def notifier(username, message):
        async with DatabaseArchitecture.accounts_db() as conn:
            cursor = await conn.execute("""
                SELECT 
                    owner_id,
                    authorised_users_telegram_id
                FROM spaces
                WHERE username = ?
            """, (username,))

            ids = await cursor.fetchone()
            if not ids:
                return {"code": 70430}

            owner_id, authorised_users_telegram_id = ids
            authorised_users_telegram_id = json.loads(authorised_users_telegram_id)
            for user_id in [*authorised_users_telegram_id, owner_id]:
                await notification(user_id, message)

