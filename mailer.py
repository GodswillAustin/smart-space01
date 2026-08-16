import resend
import os
from dotenv import load_dotenv

load_dotenv()
RESEND_API = os.getenv("RESEND_API")

resend.api_key = RESEND_API

def ResendMail(to_email, subject, mail_content):
    r = resend.Emails.send({
    "from": "onboarding@resend.dev",
    "reply_to": ["godswillment@gmail.com", "godswillaustin5@gmail.com"],
    "to": to_email,
    "subject": subject,
    "html": mail_content
    })