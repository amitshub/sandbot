import os
import json
import redis
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

redis_url = os.getenv("REDIS_URL")
r = redis.from_url(redis_url, decode_responses=True)

keys = r.keys("business_bot:chat_history:*")

questions = []

for key in keys:
    try:
        raw = r.get(key)
        if not raw:
            continue

        data = json.loads(raw)

        if isinstance(data, list):
            for item in data:
                if item.get("role") == "user":
                    questions.append(item.get("content", ""))

    except Exception as e:
        print("ERROR:", key, e)

pdf_file = "/tmp/all_questions.pdf"

doc = SimpleDocTemplate(pdf_file, pagesize=A4)
styles = getSampleStyleSheet()

story = []

story.append(Paragraph("All User Questions", styles["Title"]))
story.append(Spacer(1, 12))

for i, q in enumerate(questions, start=1):
    story.append(Paragraph(f"{i}. {q}", styles["Normal"]))
    story.append(Spacer(1, 6))

doc.build(story)

print("PDF CREATED:", pdf_file)