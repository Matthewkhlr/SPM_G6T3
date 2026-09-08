def send_email(to: str, subject: str, body: str) -> dict:
    print(f"[email] to={to} subject={subject} body={body}")
    return {"channel": "email", "to": to, "status": "queued"}
