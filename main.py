# -*- coding: utf-8 -*-

from __future__ import unicode_literals


# -----------------
# Built-in modules
# -----------------
import os
import sys
import json
import re
import dateutil.parser as dparser

import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.message import MIMEMessage

# 3rd party modules
sys.path.insert(0, "lib")

# E-mail Notifications
import boto.ses
import requests


# -----------
# Get Config
# -----------
config = {}

config_file = "config/production.json" \
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME")\
    else "config/development.json"

with open(config_file, 'r') as f:
    config = json.loads(f.read())
# END


# ------------------
# Setup S3 Instance
# ------------------
from boto.s3.connection import S3Connection
from boto.s3.key import Key

# Production Bucket
AWS_ACCESS_KEY_ID = config.get("AWS_S3_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = config.get("AWS_S3_SECRET_ACCESS_KEY")
AWS_S3_BUCKET = config.get("AWS_S3_BUCKET")
AWS_S3_FOLDER = config.get("AWS_S3_BUCKET_FOLDER")

if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    conn = S3Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

    # Check if bucket exits
    nonexistent = conn.lookup(AWS_S3_BUCKET)
    if nonexistent is None:
        bucket = conn.create_bucket(AWS_S3_BUCKET)
    else:
        bucket = conn.get_bucket(AWS_S3_BUCKET)
else:
    raise Exception(
        'Missing Keys', 'Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY\
         enviroment variables')


# ----------------------
# Nutritionix API Setup
# ----------------------
API_VERSION = "v2"
BASE_URL = os.path.join("https://trackapi.nutritionix.com", API_VERSION)

NIX_APP_ID = config.get("NIX_APP_ID")
NIX_APP_KEY = config.get("NIX_APP_KEY")
# End


# --------------
# AWS SES Setup
# --------------
email_client = boto.ses.connect_to_region(
    config.get("AWS_SES_REGION", "us-east-1"),
    aws_access_key_id=config.get("AWS_SES_ACCESS_KEY_ID"),
    aws_secret_access_key=config.get("AWS_SES_SECRET_ACCESS_KEY")
)

recip = []

from_email = config.get("EMAIL_FROM")
from_name = config.get("EMAIL_FROM_NAME")
# End


def nix_natural(text):
    """ Hit Nutritionix API Natural Endpoint and return the response"""
    headers = {
        "x-app-id": NIX_APP_ID,
        "x-app-key": NIX_APP_KEY
    }

    return requests.post(
        os.path.join(BASE_URL, "natural/nutrients"),
        data={"query": text},
        headers=headers
    )


def nix_log_food(text, email):
    """ Hit Nutritionix API Natural Endpoint and return the response"""
    headers = {
        "x-app-id": NIX_APP_ID,
        "x-app-key": NIX_APP_KEY
    }

    return requests.post(
        os.path.join(BASE_URL, "natural/sse"),
        data={
            "query": text,
        },
        headers=headers,
        params={
            "code": config.get("NIX_API_CODE"),
            "email": email
        }
    )


def get_raw_email(_key):
    """ Get raw e-mail from AWS S3 Bucket """
    key = Key(bucket)
    key.key = _key
    content = key.get_contents_as_string()

    return content


def generate_raw_reply(raw_email, text_body="", html_body=""):
    """
    Generates a reply for an incoming raw e-mail.

    :param raw_email: incoming e-mail in raw format
    :param text_body: plain text message for e-mail response
    :param html_body: html message for e-mail response
    :type raw_email: str
    :type text_body: str
    :type html_body: str
    """

    # Replace all the attachments in the original message
    # with text/plain placeholders
    original = email.message_from_string(raw_email)
    for part in original.walk():
        if (part.get('Content-Disposition') and
                part.get('Content-Disposition').startswith("attachment")):

            part.set_type("text/plain")
            part.set_payload("Attachment removed: %s (%s, %d bytes)"
                             % (part.get_filename(),
                                part.get_content_type(),
                                len(part.get_payload(decode=True))))
            del part["Content-Disposition"]
            del part["Content-Transfer-Encoding"]

    # Create a reply message
    new_msg = email.mime.multipart.MIMEMultipart()
    body = MIMEMultipart("alternative")

    if text_body:
        body.attach(MIMEText(text_body, "plain"))

    if html_body:
        body.attach(MIMEText(html_body, "html"))

    new_msg.attach(body)

    new_msg["Message-ID"] = email.utils.make_msgid()
    new_msg["In-Reply-To"] = original["Message-ID"]
    new_msg["References"] = original["Message-ID"]
    new_msg["Subject"] = "Re: " + original["Subject"]
    new_msg["To"] = original["Reply-To"] or original["From"]
    new_msg["From"] = "{from_name}<{from_email}>".format(
        from_email=from_email,
        from_name=from_name,
    )

    # Attach the original MIME message object
    new_msg.attach(MIMEMessage(original))

    return new_msg


def extract_reply_text(text):
    re_words = re.compile(r"[0-9a-zA-Z\s\[\]\(\)\{\}\.,\/]+")
    new_text = text.split('\n')

    new_text = map(lambda x: x.replace('\r', ''), new_text)

    for index, line in enumerate(new_text):
        if config.get("EMAIL_FROM_NAME") in line or config.get("EMAIL_FROM") in line:
            new_text = new_text[:index]
            break

    regex_matches = re_words.findall(new_text[-1])
    if not regex_matches:
        new_text.pop()

    new_text = ("\n".join(new_text[:index])).strip()

    return new_text


def handler(event, context):
    records = event.get("Records")

    if records and records[0].get("eventSource") == "aws:ses":
        for record in records:
            user_email = record\
                .get("ses")\
                .get("mail")\
                .get("commonHeaders")\
                .get("returnPath")

            # timestamp = record\
            #     .get("ses")\
            #     .get("mail")\
            #     .get("timestamp")

            subject = record\
                .get("ses")\
                .get("mail")\
                .get("commonHeaders")\
                .get("subject")

            message_id = record\
                .get("ses")\
                .get("mail")\
                .get("messageId")

            # Extract Date from e-mail subject
            parsed_date = dparser.parse(
                subject,
                fuzzy=True
            )

            long_string_date = parsed_date.strftime("%A, %d-%m-%y")
            short_string_date = parsed_date.strftime("%d-%m-%y")

            # Get raw e-mail from AWS S3 Bucket
            raw_email = get_raw_email(os.path.join(AWS_S3_FOLDER, message_id))

            # Get message from raw e-mail
            message = email.message_from_string(raw_email)

            email_text = ""
            for part in message.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload()
                    email_text = extract_reply_text(payload)
                    break

            # Add a date add the end of the e-mail text query
            email_text = "%s on %s" % (email_text, long_string_date)

            # Log food and store API response
            api_response_json = json.loads(
                nix_log_food(email_text,
                user_email
                ).text
            )

            # Get total calories
            calories = 0
            for food in api_response_json.get("foods"):
                calories += food.get("nf_calories")

            reply_text_body = """\
                Thanks! I just logged {calories} calories to your food log for {long_date}.
                You can view them on your dashboard here: https://www.nutritionix.com/dashboard/{short_date}
                """.format(
                long_date=long_string_date,
                short_date=short_string_date,
                calories=calories
            )

            reply_msg = generate_raw_reply(
                raw_email, text_body=reply_text_body
            )

            # Send e-mail reply
            response = email_client.send_raw_email(reply_msg.as_string())
