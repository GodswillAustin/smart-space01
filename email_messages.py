create_space = lambda space_name, username, space_type, address, email: f"""
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
    background:#ededed;
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

update_space = lambda msg: f"""
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
    background:#ededed;
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

delete_space = lambda space_name, username, space_type, address: f"""
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
