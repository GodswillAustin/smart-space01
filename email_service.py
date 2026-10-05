import resend
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
RESEND_API = os.getenv("RESEND_API")

resend.api_key = RESEND_API

class ResendMail:
  def __init__(self, email, subject, mail_content):
    self.email = email
    self.subject = subject
    self.mail_content = mail_content


  def resendmail(self):
    response = resend.Emails.send(
      {
        "from": "onboarding@resend.dev",
        "reply_to": ["godswillment@gmail.com", "godswillaustin5@gmail.com"],
        "to": self.email,
        "subject": self.subject,
        "html": self.mail_content
      }
    )
    return response

  async def MAIL(self):
    await asyncio.to_thread(self.resendmail)