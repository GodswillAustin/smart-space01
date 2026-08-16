from pathlib import Path
import sqlite3
import random
import secrets
import string
import hashlib
import bcrypt
from mailer import ResendMail
import json
import uuid

from smart_devices import LookupDevice


DB_DIR = Path("database")
DB_DIR.mkdir(exist_ok=True)

class PasswordHasher:
    
    @staticmethod
    def hash_password(password: str) -> bytes:
        password_bytes = password.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        return hashed
    
    @staticmethod
    def verify_password(password: str, hashed_password: bytes) -> bool:
        password_bytes = password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_password)
    
class DatabaseArchitecture:

    @staticmethod
    def accounts_db():
        conn = sqlite3.connect(DB_DIR / "accounts.db", timeout=10)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @staticmethod
    def charts_db():
        conn = sqlite3.connect(DB_DIR / "charts.db", timeout=10)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @staticmethod
    def create_all():
        databases = [
            DatabaseArchitecture.accounts_db,
            DatabaseArchitecture.charts_db
        ]

        for db in databases:
            conn = db()
            conn.close()

class Tables:

    @staticmethod
    def space_table():
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS spaces (
                username TEXT PRIMARY KEY,
                password TEXT,
                space_name TEXT,
                space_type TEXT,
                email TEXT,
                address TEXT,
                owner_id INTEGER,
                authorized_users TEXT,
                registered_devices TEXT,
                scheduled_recurring_actions TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

    @staticmethod
    def user_table():
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                phone_number INTEGER,
                address TEXT,
                persistent_memory TEXT,
                default_space TEXT,
                accessable_spaces TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # ,
            #     FOREIGN KEY (space_id)
            #         REFERENCES spaces(space_id)
            #         ON DELETE CASCADE
            # )

    @staticmethod
    def chat_table(chat_id):
        with DatabaseArchitecture.charts_db() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS chat_{chat_id} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                message_type TEXT,
                content TEXT,
                role TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

class Validator:

    def __init__(self, user_id):
        self.user_id = user_id

    generate_id = staticmethod(
        lambda user_id: hashlib.sha256(str(user_id).encode()).hexdigest()
    )

    @staticmethod
    def verify_username(username):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM spaces WHERE username = ? LIMIT 1",
                (username,)
            )
            return cursor.fetchone() is not None

    def verify_user(self):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM users WHERE user_id = ? LIMIT 1",
                (self.user_id,)
            )
            return cursor.fetchone() is not None

    def fetch_space(self):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    default_space,
                    accessable_spaces
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))
            
            return cursor.fetchone()

    def smart_spaces(self):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    default_space,
                    accessable_spaces
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))
            
            space_records = cursor.fetchone()

            cursor.execute("""
                SELECT
                    username,
                    space_name,
                    space_type,
                    owner_id,
                    authorized_users,
                    registered_devices,
                    scheduled_recurring_actions
                FROM spaces
                WHERE owner_id = ?
                    OR EXISTS (
                        SELECT 1
                        FROM json_each(authorized_users)
                        WHERE key = ?
                )
            """, (self.user_id, str(self.user_id)))

            verification = cursor.fetchall()

            if not verification:
                return None, None
            
            default_space = {}
            other_spaces = []
            
            for verified in verification:
                if space_records[0] == verified[0]:
                    default_space = {
                        "username": verified[0],
                        "space_name": verified[1],
                        "space_type": verified[2],
                        "role": "owner" if self.user_id == verified[3] else "member",
                        "authorized_users": verified[4],
                        "registered_devices": verified[5],
                        "scheduled_recurring_actions": verified[6]
                    }
                        
                else:
                    other_spaces.append(
                        {
                            "username": verified[0],
                            "space_name": verified[1],
                            "space_type": verified[2],
                            "role": "owner" if self.user_id == verified[3] else "member",
                            "authorized_users": verified[4]
                        }
                    )
            return default_space, other_spaces


    def authenticate(self, owner_id, username, password, stored_hash):
        if self.user_id != owner_id:
            return {
                "status": "error",
                "error": {
                    "message": (
                        f"The user is not authorised to access the smart space with the username '{username}'."
                    )
                }
            }

        verified_password = PasswordHasher.verify_password(password, stored_hash)
        if not verified_password:
            return {
                "status": "error",
                "error": {
                    "message": f"The password provided for the smart space '{username}' is incorrect."
                }
            }

class DatabaseManager:

    def __init__(self, user_id):
        self.user_id = user_id

    def register_user(self, full_name):

        user_verifier = Validator(self.user_id).verify_user()
        if user_verifier:
            return True
        
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
            INSERT INTO users (
                user_id,
                full_name,
                accessable_spaces
            )
            VALUES (?, ?, ?)
            """, (
                self.user_id,
                full_name,
                json.dumps([])
            ))
        
        Tables.chat_table(self.user_id)


    @staticmethod
    def save_chat(
        user_id,
        message_id,
        content,
        role='assistant',
        message_type = 'text'
    ):
        
        with DatabaseArchitecture.charts_db() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
            INSERT INTO chat_{user_id} (
                message_id,
                message_type,
                content,
                role
            )
            VALUES (?, ?, ?, ?)
            """, (
                message_id,
                message_type,
                content,
                role
            ))

    def update_phone(self, ph):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE users
                SET phone_number = ?
                WHERE user_id = ?
            """, (ph, self.user_id))

    def update_location(self, loc):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE users
                SET address = ?
                WHERE user_id = ?
            """, (loc, self.user_id))

    def ph_loc(self):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT phone_number, address
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))

            return cursor.fetchone()
        
    def mamage_memory(self, arguments):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT persistent_memory
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))

            row = cursor.fetchone()
            memory = json.loads(row[0]) if row[0] else {}

            for data in arguments:
                if data in ['create', 'update']:
                    for key, value in arguments[data].items():
                        if key in memory.keys() or key not in memory.keys():
                            memory[key] = value
                elif data == 'delete':
                    for key in arguments[data]:
                        if key in memory.keys():
                            del memory[key]

            memory = json.dumps(memory)

            cursor.execute(f"""
                UPDATE users
                SET persistent_memory = ?
                WHERE user_id = ?
            """, (memory, self.user_id))

    def memory(self):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT persistent_memory
                FROM users
                WHERE user_id = ?
            """, (self.user_id,))

            data =  cursor.fetchone()

            return json.loads(data[0])

    def manage_smart_spaces(self, tool_id, arguments):

        tool_response = []
        messages = []

        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            generate_username = lambda name: f"@{''.join(name.split())}_{uuid.uuid4().hex[:8]}".lower()

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
                                "message": "The password must be at least 8 characters long."
                            }
                        }
                    )
                    continue
                hashed_password = PasswordHasher.hash_password(password)

                for _ in range(5):
                    username = generate_username(register.get("space_name"))
                    username_verifier = Validator.verify_username(username)
                    if not username_verifier:
                        break

                if username_verifier:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "message": f"Failed to register the {space_type}. Please try again."
                            }
                        }
                    )
                    continue
                
                space_name = register.get('space_name')
                validator = Validator(self.user_id).fetch_space()

                if space_name == validator[0] or space_name in validator[-1]:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "code": "SMART_SPACE_NAME_EXISTS",
                                "message": "A smart space with this name already exists.",
                                "space_type": space_type,
                                "space_name": space_name,
                                "resolution": (
                                "Choose a different name or remove the existing smart space before trying again."
                                )
                            }
                        }
                    )
                    continue

                content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Welcome to Will Smart Spaces</title>
</head>

<body style="
    margin:0;
    padding:40px 20px;
    background:#f1f5f9;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
    color:#0f172a;
">

<table role="presentation" width="100%" cellspacing="0" cellpadding="0">
<tr>
<td align="center">

<table role="presentation"
width="680"
cellpadding="0"
cellspacing="0"
style="
max-width:680px;
background:#ffffff;
border-radius:20px;
overflow:hidden;
box-shadow:0 20px 60px rgba(15,23,42,.08);
">

<!-- HEADER -->

<tr>
<td style="
padding:48px;
background:linear-gradient(135deg,#2563eb,#1d4ed8);
color:#ffffff;
">

<div style="font-size:38px;line-height:1;">
🏠
</div>

<h1 style="
margin:18px 0 8px;
font-size:32px;
font-weight:700;
">
Welcome to Will Smart Spaces
</h1>

<p style="
margin:0;
font-size:16px;
opacity:.92;
line-height:1.8;
">
Your smart space has been created successfully.
</p>

</td>
</tr>

<!-- INTRO -->

<tr>
<td style="padding:44px 48px 20px;">

<h2 style="
margin:0;
font-size:30px;
font-weight:700;
color:#111827;
">
You're all set 🎉
</h2>

<p style="
margin:18px 0 0;
font-size:17px;
line-height:1.9;
color:#475569;
">

Your smart space has been successfully created and is now ready to use.

We've included its details below for your records.

</p>

</td>
</tr>

<!-- DETAILS -->

<tr>
<td style="padding:0 48px;">

<div style="
background:#f8fafc;
border:1px solid #e2e8f0;
border-radius:16px;
padding:28px;
">

<h3 style="
margin:0 0 22px;
font-size:19px;
color:#111827;
">
Smart Space Details
</h3>

<table width="100%" cellspacing="0" cellpadding="0">

<tr>
<td style="padding:12px 0;color:#64748b;width:170px;">
Space Name
</td>

<td align="right"
style="padding:12px 0;font-weight:600;color:#111827;">
{space_name}
</td>
</tr>

<tr>
<td style="padding:12px 0;color:#64748b;">
Username
</td>

<td align="right">

<span style="
display:inline-block;
padding:7px 12px;
background:#eef2ff;
border:1px solid #c7d2fe;
border-radius:8px;
font-family:Consolas,Monaco,'Courier New',monospace;
font-size:14px;
font-weight:700;
color:#3730a3;
">
{username}
</span>

</td>
</tr>

<tr>
<td style="padding:12px 0;color:#64748b;">
Password
</td>

<td align="right">

<span style="
display:inline-block;
padding:7px 12px;
background:#fef3c7;
border:1px solid #fcd34d;
border-radius:8px;
font-family:Consolas,Monaco,'Courier New',monospace;
font-size:14px;
font-weight:700;
color:#92400e;
">
********
</span>

</td>
</tr>

<tr>
<td style="padding:12px 0;color:#64748b;">
Space Type
</td>

<td align="right"
style="padding:12px 0;font-weight:600;color:#111827;">
{space_type.title()}
</td>
</tr>

<tr>
<td style="
padding:12px 0;
vertical-align:top;
color:#64748b;
">
Address
</td>

<td align="right"
style="
padding:12px 0;
line-height:1.8;
font-weight:500;
color:#111827;
">
{address}
</td>
</tr>

<tr>
<td style="padding:12px 0;color:#64748b;">
Notification Email
</td>

<td align="right"
style="padding:12px 0;font-weight:500;color:#111827;">
{email}
</td>
</tr>

</table>

</div>

</td>
</tr>

<!-- SECURITY -->

<tr>
<td style="padding:36px 48px 0;">

<div style="
background:#eff6ff;
border:1px solid #bfdbfe;
border-radius:16px;
padding:24px;
">

<h3 style="
margin:0 0 16px;
font-size:20px;
color:#1d4ed8;
">
🔒 Keep these credentials safe
</h3>

<p style="
margin:0;
font-size:15px;
line-height:1.9;
color:#1e3a8a;
">

Your smart space username and password are required whenever someone wants to register or access this smart space.

Store them somewhere safe and only share them with people you trust.

</p>

</div>

</td>
</tr>

<!-- SECURITY ALERT -->

<tr>
<td style="padding:30px 48px 0;">

<div style="
background:#fffbeb;
border:1px solid #fde68a;
border-radius:16px;
padding:24px;
">

<h3 style="
margin:0 0 16px;
font-size:20px;
color:#92400e;
">
⚠ Didn't create this smart space?
</h3>

<p style="
margin:0;
font-size:15px;
line-height:1.9;
color:#78350f;
">

If you don't recognise this activity, please reply to this email immediately.

A member of our support team will investigate and help secure your account.

</p>

</div>

</td>
</tr>

<!-- FOOTER -->

<tr>
<td style="
padding:40px 48px;
">

<hr style="
border:none;
border-top:1px solid #e5e7eb;
margin:0 0 28px;
">

<p style="
margin:0;
font-size:15px;
line-height:1.9;
color:#475569;
">

Need help?

<br><br>

Simply reply to this email.
Every reply is delivered directly to our support team.

</p>

<p style="
margin:34px 0 0;
font-size:12px;
text-align:center;
line-height:1.8;
color:#94a3b8;
">

© 2026 <strong>Will Smart Spaces</strong><br>

Building smarter spaces, securely.

</p>

</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>
"""
                subject = "Welcome to Will Smart Spaces"
                try:
                    ResendMail(email, subject, content)
                except Exception:
                    tool_response.append(
                        {
                            "status": "error",
                            "error_message": f"The email address '{email}' is invalid."
                        }
                    )
                    continue

                tool_response.append(
                    {
                        "status": "success",
                        "data": {
                            "message": f"Smart {space_type} registered successfully.",
                            "space_type": space_type,
                            "space_name": space_name,
                            "username": username,
                            "access_management": {
                                "username_required": True,
                                "purpose": (
                                    "Use this username to grant temporary or permanent access "
                                    "to the smart space and to manage access permissions."
                                )
                            }
                        }
                    }
                )

                cursor.execute(f"""
                INSERT INTO spaces (
                    username,
                    password,
                    space_name,
                    space_type,
                    email,
                    address,
                    owner_id,
                    authorized_users,
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

            for update in arguments.get("update", ""):

                username = update.get("username")

                cursor.execute("""
                SELECT
                    password,
                    space_name,
                    space_type,
                    email,
                    address,
                    owner_id
                FROM spaces
                WHERE username = ?
                """, (username,))
                data = cursor.fetchone()

                if data is None:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "message": (
                                    f"There's no smart space with the username {username}."
                                )
                            }
                        }
                    )
                    continue

                if self.user_id != data[5]:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "message": (
                                    f"The user is not authorised to access the smart space with the username '{username}'."
                                )
                            }
                        }
                    )
                    continue

                password = update.get("password")
                stored_hash = data[0]
                verified_password = PasswordHasher.verify_password(password, stored_hash)
                if not verified_password:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "message": f"The password provided for the smart space '{username}' is incorrect."
                            }
                        }
                    )
                    continue

                space_name = update.get("space_name")
                if space_name:
                    for _ in range(5):
                        new_username = generate_username(space_name)
                        username_verifier = Validator.verify_username(new_username)
                        if not username_verifier:
                            break

                    if username_verifier:
                        tool_response.append(
                            {
                                "status": "error",
                                "error": {
                                    "message": f"Unable to update the smart space '{username}'. Please try again."
                                }
                            }
                        )
                        continue
                else:
                    new_username = username

                space_name = space_name or data[1]
                space_type = update.get("space_type", data[2])
                email = update.get("email", data[3])
                address = update.get("address", data[4])
                new_password = update.get("new_password", password)
                hashed_password = PasswordHasher.hash_password(new_password) if new_password else password

                cursor.execute("""
                    SELECT authorized_users
                    FROM spaces
                    WHERE username = ?
                """, (username,))

                users = cursor.fetchone()

                if users:

                    changes = [f'The smart space "{username}" has been updated.\n']

                    if data[1] != space_name:
                        changes.append(f"• Space name: {data[1]} → {space_name}")
                        changes.append(f"• Username: {username} → {new_username}")

                    if data[2] != space_type:
                        changes.append(f"• Space type: {data[2]} → {space_type}")

                    if data[4] != address:
                        changes.append(f"• New address: {address}")

                    msg = "\n".join(changes)
                    messages.append(
                        {
                            "authorized_users": users,
                            "message": msg
                        }
                    )
                    msg = msg.replace("\n", "<br>")

                content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Security Notice</title>
</head>

<body style="
    margin:0;
    padding:40px 20px;
    background:#eef2f7;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
    color:#1f2937;
">

<table role="presentation" width="100%" cellspacing="0" cellpadding="0">
<tr>
<td align="center">

<table role="presentation"
width="650"
cellpadding="0"
cellspacing="0"
style="
background:#ffffff;
border-radius:18px;
overflow:hidden;
box-shadow:0 12px 40px rgba(0,0,0,.08);
">

<!-- HEADER -->

<tr>
<td style="
background:linear-gradient(135deg,#2563eb,#1d4ed8);
padding:42px;
color:#ffffff;
">

<h1 style="margin:0;font-size:30px;font-weight:700;">
🏠 Will Smart Spaces
</h1>

<p style="
margin:12px 0 0;
font-size:16px;
opacity:.9;
line-height:1.6;
">
Security Notification
</p>

</td>
</tr>

<!-- TITLE -->

<tr>
<td style="padding:42px 42px 20px;">

<h2 style="
margin:0;
font-size:32px;
color:#111827;
">
Your smart space has been updated
</h2>

<p style="
margin-top:18px;
font-size:17px;
line-height:1.8;
color:#4b5563;
">
We're letting you know that changes have been made to your smart space.

If you made these changes, you don't need to do anything else.
</p>

</td>
</tr>

<!-- CHANGES -->

<tr>
<td style="padding:0 42px;">

<div style="
background:#f8fafc;
border-left:5px solid #2563eb;
padding:24px;
border-radius:12px;
font-size:15px;
line-height:1.9;
color:#111827;
">

{msg}

</div>

</td>
</tr>

<!-- WARNING -->

<tr>
<td style="padding:36px 42px 0;">

<div style="
background:#fff8e6;
border:1px solid #f6c453;
border-radius:14px;
padding:24px;
">

<h3 style="
margin:0 0 14px;
font-size:21px;
color:#92400e;
">
⚠ Didn't make these changes?
</h3>

<p style="
margin:0;
font-size:15px;
line-height:1.8;
color:#78350f;
">
If you don't recognise these changes, someone else may have accessed your smart space,
or this notification may have been sent unexpectedly.

<b>Please reply to this email as soon as possible.</b>
A member of our support team will personally review your message and investigate.
</p>

</div>

</td>
</tr>

<!-- HELP -->

<tr>
<td style="padding:40px 42px;">

<hr style="
border:none;
border-top:1px solid #e5e7eb;
margin:0 0 28px;
">

<h3 style="
margin:0;
font-size:18px;
color:#111827;
">
Need help?
</h3>

<p style="
margin-top:12px;
font-size:15px;
line-height:1.8;
color:#4b5563;
">
Simply click <b>Reply</b> in your email app if:

• You didn't make these changes.<br>
• You think someone accessed your account.<br>
• You believe this notification was sent by mistake.<br>
• You found a bug or something doesn't look right.
</p>

<p style="
margin-top:18px;
font-size:15px;
line-height:1.8;
color:#4b5563;
">
Every reply is monitored by our support team, and we'll get back to you as quickly as possible.
</p>

</td>
</tr>

<!-- FOOTER -->

<tr>
<td style="
background:#f9fafb;
padding:28px;
text-align:center;
">

<p style="
margin:0;
font-size:13px;
line-height:1.8;
color:#6b7280;
">
This email was sent to help keep your smart spaces secure.
</p>

<p style="
margin:8px 0 0;
font-size:12px;
color:#9ca3af;
">
© 2026 Will Smart Spaces. All rights reserved.
</p>

</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>
"""
                subject = "Your smart space has been updated"
                try:
                    ResendMail(email, subject, content)
                except Exception:
                    tool_response.append(
                        {
                            "status": "error",
                            "error_message": f"The email address '{email}' is invalid."
                        }
                    )
                    continue

                cursor.execute("""
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
                    space_name,
                    space_type,
                    email,
                    address,
                    username
                ))

                tool_response.append(
                    {
                        "status": "success",
                        "message": messages
                    }
                )

            for delete in arguments.get("delete", ""):
                username = delete["username"]
                password = delete["password"]

                cursor.execute("""
                    SELECT 
                        password,
                        space_name,
                        space_type,
                        email, 
                        address,
                        owner_id
                    FROM spaces
                    WHERE username = ?
                """, (username,))
    
                data = cursor.fetchone()

                if data is None:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "message": (
                                    f"There's no smart space with the username {username}."
                                )
                            }
                        }
                    )
                    continue

                if self.user_id != data[5]:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "message": (
                                    f"The user is not authorised to access the smart space with the username '{username}'."
                                )
                            }
                        }
                    )
                    continue

                stored_hash = data[0]
                verified_password = PasswordHasher.verify_password(password, stored_hash)
                if not verified_password:
                    tool_response.append(
                        {
                            "status": "error",
                            "error": {
                                "message": f"The password provided for the smart space '{username}' is incorrect."
                            }
                        }
                    )
                    continue
                space_name = data[1]
                space_type = data[2]
                address = data[4]
                content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Security Notice</title>
</head>

<body style="
    margin:0;
    padding:40px 20px;
    background:#f1f5f9;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
    color:#0f172a;
">

<table role="presentation" width="100%" cellspacing="0" cellpadding="0">
<tr>
<td align="center">

<table role="presentation"
width="680"
cellpadding="0"
cellspacing="0"
style="
max-width:680px;
background:#ffffff;
border-radius:20px;
overflow:hidden;
box-shadow:0 20px 60px rgba(15,23,42,.08);
">

<!-- HEADER -->

<tr>
<td style="
padding:48px;
background:linear-gradient(135deg,#dc2626,#991b1b);
color:#ffffff;
">

<div style="font-size:38px;line-height:1;">
🏠
</div>

<h1 style="
margin:18px 0 8px;
font-size:32px;
font-weight:700;
">
Will Smart Spaces
</h1>

<p style="
margin:0;
font-size:16px;
opacity:.9;
line-height:1.7;
">
Security Notification
</p>

</td>
</tr>

<!-- TITLE -->

<tr>
<td style="padding:44px 48px 20px;">

<h2 style="
margin:0;
font-size:30px;
font-weight:700;
color:#111827;
">
A smart space has been deleted
</h2>

<p style="
margin:18px 0 0;
font-size:17px;
line-height:1.9;
color:#475569;
">

This email confirms that one of your smart spaces has been permanently removed from your account.

If you made this change, there's nothing else you need to do.

</p>

</td>
</tr>

<!-- DETAILS CARD -->

<tr>
<td style="padding:0 48px;">

<div style="
background:#f8fafc;
border:1px solid #e2e8f0;
border-radius:16px;
padding:28px;
">

<h3 style="
margin:0 0 22px;
font-size:19px;
color:#111827;
">
Deleted Smart Space
</h3>

<table width="100%" cellspacing="0" cellpadding="0">

<tr>
<td style="
padding:12px 0;
color:#64748b;
width:160px;
">
Space Name
</td>

<td style="
padding:12px 0;
font-weight:600;
color:#111827;
text-align:right;
">
{space_name.title()}
</td>
</tr>

<tr>
<td style="
padding:12px 0;
color:#64748b;
">
Username
</td>

<td align="right">

<span style="
display:inline-block;
padding:7px 12px;
background:#eef2ff;
border:1px solid #c7d2fe;
border-radius:8px;
font-family:Consolas,Monaco,'Courier New',monospace;
font-size:14px;
font-weight:700;
color:#3730a3;
">
{username}
</span>

</td>
</tr>

<tr>
<td style="
padding:12px 0;
color:#64748b;
">
Space Type
</td>

<td style="
padding:12px 0;
font-weight:600;
color:#111827;
text-align:right;
">
{space_type.title()}
</td>
</tr>

<tr>
<td style="
padding:12px 0;
vertical-align:top;
color:#64748b;
">
Address
</td>

<td style="
padding:12px 0;
font-weight:500;
line-height:1.8;
color:#111827;
text-align:right;
">

{address.title()}

</td>
</tr>

<tr>
<td style="
padding:12px 0;
color:#64748b;
">
Status
</td>

<td align="right">

<span style="
display:inline-block;
padding:7px 14px;
background:#fee2e2;
color:#b91c1c;
border-radius:999px;
font-size:13px;
font-weight:700;
">
Removed from Account
</span>

</td>
</tr>

</table>

</div>

</td>
</tr>

<!-- WARNING -->

<tr>
<td style="padding:36px 48px 0;">

<div style="
background:#fff8e6;
border:1px solid #fcd34d;
border-radius:16px;
padding:26px;
">

<h3 style="
margin:0 0 16px;
font-size:21px;
color:#92400e;
">
⚠ Didn't make this change?
</h3>

<p style="
margin:0;
font-size:15px;
line-height:1.9;
color:#78350f;
">

If you don't recognise this deletion, someone may have accessed your account without your permission.

<b>Please reply to this email as soon as possible.</b>

A member of our support team will personally review your message and investigate the issue.

</p>

</div>

</td>
</tr>

<!-- WHY -->

<tr>
<td style="padding:40px 48px;">

<h3 style="
margin:0;
font-size:20px;
color:#111827;
">
Why did you receive this email?
</h3>

<p style="
margin:16px 0 0;
font-size:15px;
line-height:1.9;
color:#475569;
">

We send a security notification whenever important changes are made to one of your smart spaces.

These notifications help you quickly detect unauthorised activity and keep your account secure.

</p>

</td>
</tr>

<!-- SUPPORT -->

<tr>
<td style="
padding:0 48px 42px;
">

<div style="
background:#eff6ff;
border:1px solid #bfdbfe;
border-radius:16px;
padding:22px;
">

<h3 style="
margin:0 0 12px;
font-size:18px;
color:#1d4ed8;
">
💬 Need help?
</h3>

<p style="
margin:0;
font-size:15px;
line-height:1.9;
color:#1e3a8a;
">

Simply click <b>Reply</b> in your email app if:

<br><br>

• You didn't delete this smart space.<br>
• You believe your account has been compromised.<br>
• You think this notification was sent by mistake.<br>
• You found a bug or have any questions.

<br><br>

Every reply is delivered directly to our support team.

</p>

</div>

</td>
</tr>

<!-- FOOTER -->

<tr>
<td style="
background:#f8fafc;
border-top:1px solid #e5e7eb;
padding:30px;
text-align:center;
">

<p style="
margin:0;
font-size:13px;
line-height:1.9;
color:#64748b;
">

This security notification was sent automatically to help protect your account.

</p>

<p style="
margin:14px 0 0;
font-size:12px;
color:#94a3b8;
">

© 2026 <strong>Will Smart Spaces</strong><br>

Keeping your smart spaces secure.

</p>

</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>
"""

                email = data[3]
                subject = "Security Notice: A smart space was deleted"
                try:
                    ResendMail(email, subject, content)
                except Exception:
                    tool_response.append(
                        {
                            "status": "error",
                            "error_message": f"The email address '{email}' is invalid."
                        }
                    )
                    continue

                cursor.execute("DELETE FROM spaces WHERE username = ?", (username,))

                tool_response.append(
                    {
                        "status": "success",
                        "message": f"{space_name} smart {space_type} has been deleted successfully"
                    }
                )

        self.save_chat(self.user_id, tool_id, json.dumps(tool_response), 'tool')
        return messages

    def request_aceess(self, tool_id, arguments):

        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()
            tool_response, transmit = [], []

            usernames = arguments.get('username')
            for username in usernames:

                cursor.execute("""
                    SELECT 
                        space_name,
                        space_type, 
                        email, 
                        owner_id
                    FROM spaces
                    WHERE username = ?
                """, (username,))

                data = cursor.fetchone()

                if not data:
                    status = {
                        "status": "error",
                        "error": {
                            "code": "SMART_SPACE_NOT_FOUND",
                            "message": "No smart space was found with the specified username.",
                            "username": username
                        }
                    }
                    tool_response.append(status)
                    continue

                cursor.execute("""
                    SELECT full_name
                    FROM users
                    WHERE user_id = ?
                """, (self.user_id,))

                fullname = cursor.fetchone()

                content = f"""
<div style="font-family: Arial, Helvetica, sans-serif; max-width: 600px; margin: auto; padding: 32px; color: #333;">

    <h2 style="margin-top: 0;">
        🔐 Smart Space Access Request
    </h2>

    <p>
        <strong>{fullname}</strong> is requesting access to your
        <strong>{data[1].lower()}</strong>,
        <strong>"{data[0].title()}"</strong>.
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
                ResendMail(data[2], subject, content)

                message = (
                    f"<b>{fullname}</b> is requesting access to your smart <b>{data[1].lower()}</b>, "
                    f"<i>'{data[0].title()}'</i>.\n\n"
                    "Review this request and choose the level of access you'd like to grant:\n"
                    "• <b>Temporary access</b> with a custom expiration time.\n"
                    "• <b>Permanent access</b> with no expiration.\n\n"
                    "You can modify, revoke, or cancel access at any time, "
                    "regardless of the permissions you grant."
                )

                transmit.append(
                    {
                       data[-1]: message
                    }
                )

                status = {
                    "status": "success",
                    "data": {
                        "message": (
                        f"Access request submitted successfully to the smart {data[1].lower()} "
                        f"'{data[0]}'."
                        ),
                        "username": username,
                        "request_status": "pending"
                    }
                }

            tool_response.append(status)
            self.save_chat(self.user_id, tool_id, json.dumps(tool_response), 'tool')

            return transmit

    def verify_user_access(self):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT value
                FROM space, json_each(authorized_users)
                WHERE value = ?
                LIMIT 1
            """, (self.user_id,))

            result = cursor.fetchone()

            return result[0]

    def manage_device(self, tool_id, arguments):

        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT registered_devices
                FROM space
                WHERE owner_id = ?
            """, (self.user_id,))

            registered_devices = json.loads(cursor.fetchone())

            if not isinstance(registered_devices, list):
                status = {
                    "status": "error",
                    "code": "NO_SMART_SPACE_FOUND",
                    "message": "No smart spaces found where the user has owner privileges."
                }
                self.save_chat(self.user_id, tool_id, json.dumps(status), 'tool')
                return
            
            tool_response = []

            for task in arguments.get('update'):
                device_id = task['device_id']
                for device, coordinate in zip(registered_devices, range(len(registered_devices))) or zip(range(1), range(1)):
                    new_device = {}
                    if device_id == device['device']['device_id']:
                        metadata = LookupDevice()
                        device_metadata = metadata.find_device()
                        new_device.update(
                            {
                                'alias': task.get('alias') or device.get('alias'),
                                'location': task.get('location') or device.get('location'),
                                'device': {
                                    'device_id': device_id,
                                    'action_schema': device_metadata['device']
                                }
                            }
                        )
                        if registered_devices:
                            registered_devices[coordinate] = new_device
                        else:
                            registered_devices.append(new_device)
                        tool_response.append(
                            {
                                "status": "success",
                                "message": "Device updated successfully.",
                                "device": {
                                    "id": device_id,
                                    "name": task.get('alias') or device.get('alias')
                                }
                            }
                        )
            for device in arguments.get('register'):
                metadata = LookupDevice()
                device_metadata = metadata.find_device()
                new_device.update(
                    {
                        'alias': device['alias'],
                        'location': device['location'],
                        'device': {
                            'device_id': device_id,
                            'action_schema': device_metadata['device']
                        }
                    }
                )
                registered_devices.append(new_device)
                tool_response.append(
                    {
                        "status": "success",
                        "message": "Device registered successfully.",
                        "device": {
                            "id": device_id,
                            "name": device["device_name"]
                        }
                    }
                )

            for device_id in arguments.get('delete'):
                for devices, coordinate in zip(registered_devices, range(len(registered_devices))):
                    if device_id in devices:
                        del devices
                        # del registered_devices[coordinate]
                        tool_response.append(
                            {
                                "status": "success",
                                "message": "Device removed successfully.",
                                "device": {
                                    "id": device_id
                                }
                            }
                        )

            cursor.execute(f"""
                UPDATE spaces
                SET registered_devices = ?
                WHERE owner_id = ?
            """, (registered_devices, self.user_id))

            self.save_chat(self.user_id, tool_id, json.dumps(tool_response), 'tool')

    def manage_access(self, tool_id, arguments):

        tool_response = []
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            for actions in arguments:
                for action in actions:
                    username = action.get("username")

                    cursor.execute("""
                        SELECT 
                            password,
                            space_name,
                            space_type,
                            owner_id, 
                            authorized_users
                        FROM spaces
                        WHERE username = ?
                    """, (username,))

                    data = cursor.fetchone()

                    if data is None:
                        tool_response.append(
                            {
                                "status": "error",
                                "error": {
                                    "message": (
                                        f"There's no smart space with the username {username}."
                                    )
                                }
                            }
                        )
                        continue

                    password = action.get("password")
                    stored_hash = data[0]
                    auth = Validator.authenticate(data[3], username, password, stored_hash)
                    if isinstance(auth, dict):
                        tool_response.append(auth)
                        continue

                    space_name = data[1]
                    space_type = data[2]
                    authorized_users = json.loads(data[4])

                    if action["id"] not in authorized_users:
                        if actions.get("authorise"):
                            authorized_users.update(
                                {action["id"]: action["full_name"]}
                            )

                            tool_response.append(
                                {
                                    "status": "success",
                                    "message": (
                                        f"{action['full_name']} (user ID: {action['id']}) has been "
                                        f"successfully authorised to access your smart {space_type} {space_name}."
                                    )
                                }
                            )
                        else:
                            tool_response.append(
                                {
                                    "status": "error",
                                    "message": (
                                        f"{action['full_name']} (user ID: {action['id']}) is not an "
                                        f"authorised user of your smart {space_type} {space_name}."
                                    )
                                }
                            )
                    else:
                        if actions.get("unauthorise"):
                            del authorized_users[action["id"]]
                            tool_response.append(
                                {
                                    "status": "error",
                                    "message": (
                                        f"{action['full_name']} (user ID: {action['id']}) no longer has authorised "
                                        f"access to your smart {space_type} {space_name}."
                                    )
                                }
                            )

                        else:
                            tool_response.append(
                                {
                                    "status": "error",
                                    "message": (
                                        f"{action['full_name']} (user ID: {action['id']}) is already an authorised "
                                        f"user of your smart {space_type} {space_name}."
                                    )
                                }
                            )

                    cursor.execute(f"""
                        UPDATE spaces
                        SET authorized_users = ?
                        WHERE username = ?
                    """, (json.dumps(authorized_users), username))

                    self.save_chat(self.user_id, tool_id, json.dumps(tool_response), 'tool')

    # unfinished
    def fetch_authorized_users(self):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT value
                FROM spaces, json_each(authorized_users)
                WHERE owner_id = ?
            """, (self.user_id,))

            return cursor.fetchall()

    # unfinished
    def automations(self):
        with DatabaseArchitecture.accounts_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT scheduled_recurring_actions
                FROM spaces
                WHERE EXISTS (
                    SELECT 1
                    FROM json_each(authorized_users)
                    WHERE value = ?
                )
            """, (self.user_id,))

            result = cursor.fetchall()
        return result or None

    # unfinished
    def chat_history(self, limit=10):
        with DatabaseArchitecture.charts_db() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT message_id, content, role, timestamp
                FROM chat_{self.user_id}
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()

            return rows[::-1]

DatabaseArchitecture.create_all()
Tables.user_table()
Tables.space_table()