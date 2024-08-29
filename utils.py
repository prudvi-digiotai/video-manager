from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
import base64
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.multipart import MIMEMultipart

SCOPES_DRIVE = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'
PARENT_FOLDER_ID = "1REXfwxk9dcPdpZXJOFZSur3880soVN9y"


def authenticate_drive():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES_DRIVE)
    return credentials

def upload_file(filepath, filename, parent_folder_id):
    creds = authenticate_drive()
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': filename,
        'parents': [parent_folder_id]
    }

    media = MediaFileUpload(filepath, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f'File ID: {file.get("id")}')
    return file.get('id')

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def authenticate_gmail():
    """Authenticate and return the Gmail service."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    service = build("gmail", "v1", credentials=creds)
    return service

def send_email(to_email, subject, body):
    """Tool to send email"""
    try:
        msg = MIMEMultipart('alternative')
        msg['to'] = to_email
        msg['subject'] = subject

        part2 = MIMEText(body, 'html')
        msg.attach(part2)

        raw_string = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        service = authenticate_gmail()
        sent_message = service.users().messages().send(userId='me', body={'raw': raw_string}).execute()

        print(sent_message)
        print('Email sent successfully!')
        return 'Email sent successfully!'
    except Exception as e:
        print(f'Error sending email: {str(e)}')
        return f'Error sending email: {str(e)}'
