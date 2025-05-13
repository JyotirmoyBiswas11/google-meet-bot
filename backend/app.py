from flask import Flask, jsonify, request,redirect
from flask_cors import CORS
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
import json
import re
import datetime
import requests as http_requests
from google.auth.transport import requests as google_requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.apps import meet_v2 as meet
from google.cloud import pubsub_v1
from googleapiclient.discovery import build
from cryptography.fernet import Fernet
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage
import threading
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
import pdfkit

app = Flask(__name__)
cors = CORS(app, origins="*")
meet_summary = None  # Global variable to store the summary
summary_status = "loading"  # Global variable to store the status of summary generation
USER_CREDENTIALS=None
load_dotenv()
encryption_key = os.getenv('ENCRYPTION_KEY')
if encryption_key is None:
    raise ValueError("No encryption key found. Please set the ENCRYPTION_KEY environment variable.")
cipher_suite = Fernet(encryption_key.encode())

client_secret_json_str = os.getenv('CLIENT_SECRET') 
if client_secret_json_str is None: 
    raise ValueError("No CLIENT_SECRET environment variable set.")

service_cred=os.getenv('ADMIN_KEY')
if service_cred is None:
    raise ValueError("NO ADMIN KEY found")

service_account_info = json.loads(service_cred)
CLIENT_SECRET_FILE = json.loads(client_secret_json_str) 
cred = credentials.Certificate(service_account_info)
scopes = [ 'https://www.googleapis.com/auth/documents.readonly', 'https://www.googleapis.com/auth/meetings.space.readonly', 'https://www.googleapis.com/auth/userinfo.email','https://www.googleapis.com/auth/meetings.space.created', 'openid', 'https://www.googleapis.com/auth/userinfo.profile']
firebase_admin.initialize_app(cred)
db = firestore.client()

def create_html_content(summary):
    if isinstance(summary, str):
        return f'<p class="text-black">{summary}</p>'

    if summary.get('error'):
        return f'<p class="text-red-500">{summary["error"]}</p>'

    html_content = '<div>'

    if 'agenda' in summary:
        html_content += '<h2 class="text-xl font-semibold mb-2 text-black">Agenda</h2>'
        html_content += '<ul class="list-disc pl-5 text-black">'
        for point in summary['agenda']:
            html_content += f'<li>{point}</li>'
        html_content += '</ul>'

    if 'key_decisions' in summary:
        html_content += '<h2 class="text-xl font-semibold mt-4 mb-2 text-black">Key Decisions</h2>'
        for key, decisions in summary['key_decisions'].items():
            html_content += f'<div><h3 class="font-semibold text-black">{key.capitalize()}</h3><ul class="list-disc pl-5 text-black">'
            for decision in decisions:
                html_content += f'<li>{decision}</li>'
            html_content += '</ul></div>'

    if 'action_items' in summary:
        html_content += '<h2 class="text-xl font-semibold mt-4 mb-2 text-black">Action Items</h2>'
        for item in summary['action_items']:
            html_content += '<div class="mb-2 text-black">'
            html_content += f'<p><strong>Owner:</strong> {item["owner"]}</p>'
            html_content += f'<p><strong>Task:</strong> {item["task"]}</p>'
            html_content += f'<p><strong>Dependencies:</strong> {item["dependencies"]}</p>'
            html_content += '</div>'

    if 'major_discussion_points' in summary:
        html_content += '<h2 class="text-xl font-semibold mt-4 mb-2 text-black">Major Discussion Points</h2>'
        for point in summary['major_discussion_points']:
            html_content += '<div class="mb-2 text-black">'
            html_content += f'<p><strong>Topic:</strong> {point["topic"]}</p>'
            html_content += f'<p><strong>Context:</strong> {point["context"]}</p>'
            html_content += f'<p><strong>Resolution:</strong> {point["resolution"]}</p>'
            html_content += '</div>'

    if 'next_steps' in summary:
        html_content += '<h2 class="text-xl font-semibold mt-4 mb-2 text-black">Next Steps</h2>'
        for step in summary['next_steps']:
            html_content += '<div class="mb-2 text-black">'
            html_content += f'<p><strong>Priority:</strong> {step["priority"]}</p>'
            html_content += f'<p><strong>Timeline:</strong> {step["timeline"]}</p>'
            html_content += f'<p><strong>Dependencies:</strong> {step["dependencies"]}</p>'
            html_content += '</div>'

    if 'additional_notes' in summary:
        html_content += '<h2 class="text-xl font-semibold mt-4 mb-2 text-black">Additional Notes</h2>'
        html_content += '<ul class="list-disc pl-5 text-black">'
        for note in summary['additional_notes']:
            html_content += f'<li>{note}</li>'
        html_content += '</ul>'

    html_content += '</div>'

    return html_content


pdfkit_config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')

def encrypt_token(token):
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(token):
    return cipher_suite.decrypt(token.encode()).decode()

def store_token(user_id, credentials):
    encrypted_token = encrypt_token(credentials.token)
    encrypted_refresh_token = encrypt_token(credentials.refresh_token)

    db.collection('tokens').document(user_id).set({
        'token': encrypted_token,
        'refresh_token': encrypted_refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    })

def get_token(user_id):
    doc_ref = db.collection('tokens').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        decrypted_token = decrypt_token(data['token'])
        decrypted_refresh_token = decrypt_token(data['refresh_token'])
        credentials = Credentials(
            token=decrypted_token,
            refresh_token=decrypted_refresh_token,
            token_uri=data['token_uri'],
            client_id=data['client_id'],
            client_secret=data['client_secret'],
            scopes=data['scopes']
        )
        if credentials.expired:
            credentials.refresh(google_requests())
            store_token(user_id, credentials)  
        return credentials
    else:
        return None
    
def get_user_info(credentials):
    # Fetch the user's info from the Google OAuth2 API
    response = http_requests.get('https://www.googleapis.com/oauth2/v3/userinfo', headers={
        'Authorization': f'Bearer {credentials.token}'
    })
    if response.status_code == 200:
        user_info = response.json()
        return user_info['email']
    else:
        raise Exception('Failed to fetch user info')
    
@app.route('/authorize')
def authorize():
    flow = InstalledAppFlow.from_client_config(CLIENT_SECRET_FILE, scopes)
    flow.redirect_uri = 'http://localhost:5000/callback'
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return redirect(authorization_url)

@app.route('/test')
def test():
    return {"message":"Hi ! this is a test route thanks for checking in! have a great day"}

@app.route('/callback')
def callback():
    flow = InstalledAppFlow.from_client_config(CLIENT_SECRET_FILE, scopes)
    flow.redirect_uri = 'http://localhost:5000/callback'  
    flow.fetch_token(authorization_response=request.url)
    global USER_CREDENTIALS
    credentials = flow.credentials
    USER_CREDENTIALS = credentials

    user_email = get_user_info(credentials)
    existing_credentials = get_token(user_email)
    
    if existing_credentials:
        if existing_credentials.expired or should_refresh_token(existing_credentials):
            existing_credentials.refresh(google_requests.Request())
            store_token(user_email, existing_credentials)
    else:
        store_token(user_email, credentials)
    print( jsonify({'message': 'Authorization successful'}))
    return  redirect('http://localhost:3000/home')

def should_refresh_token(credentials):
    """Determine if a token should be refreshed."""
    # Consider refreshing the token if it expires within the next 5 minutes (300 seconds)
    return credentials.expiry and (credentials.expiry - datetime.datetime.utcnow()).total_seconds() < 300



def get_space_details(meeting_code):
    """Get details of a meeting space using a meeting code."""
    client = meet.SpacesServiceClient(credentials=USER_CREDENTIALS)
    request = meet.GetSpaceRequest(name=f"spaces/{meeting_code}")
    response = client.get_space(request=request)
    print(response)
    return response

def subscribe_to_space(space_name: str = None, topic_name: str = None):
    """Subscribe to events for a meeting space."""
    session = google_requests.AuthorizedSession(USER_CREDENTIALS)
    body = {
        'targetResource': f"//meet.googleapis.com/{space_name}",
        "eventTypes": [
            "google.workspace.meet.conference.v2.started",
            "google.workspace.meet.conference.v2.ended",
            "google.workspace.meet.participant.v2.joined",
            "google.workspace.meet.participant.v2.left",
            "google.workspace.meet.recording.v2.fileGenerated",
            "google.workspace.meet.transcript.v2.fileGenerated",
        ],
        "payloadOptions": {"includeResource": False},
        "notificationEndpoint": {"pubsubTopic": topic_name},
        "ttl": "86400s",
    }
    response = session.post("https://workspaceevents.googleapis.com/v1/subscriptions", json=body)
    return response

def extract_document_id(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    else:
        return None

def get_document_content(auth, document_id):
    service = build('docs', 'v1', credentials=auth)
    doc = service.documents().get(documentId=document_id).execute()
    content = doc.get('body').get('content', [])
    text = ""
    for element in content:
        if 'paragraph' in element:
            for elem in element.get('paragraph').get('elements', []):
                if 'textRun' in elem:
                    text += elem.get('textRun').get('content', '')
    print("Document Content:", text)
    return text

api_url = "https://ai-meeting-notetaker-api-357644217967.us-central1.run.app/analyze/sentiment"
summary_api_url = "https://ai-meeting-notetaker-api-357644217967.us-central1.run.app/generate/summary"

def convert_transcript_to_string(raw_transcript):
    lines = raw_transcript.split("\n")
    try:
        transcript_index = lines.index("Transcript") + 1
        meeting_end_index = lines.index("Meeting ended")
    except ValueError:
        meeting_end_index = len(lines)
    transcript_lines = lines[transcript_index:meeting_end_index]
    formatted_transcript = "\n".join(transcript_lines)
    return formatted_transcript

def generate_summary(transcript):
    try:
        response = http_requests.post(summary_api_url, json={'transcript': transcript})
        response.raise_for_status()
        print("Generated Summary:", response.json())
        
        global meet_summary
        global summary_status
        meet_summary = response.json()
        summary_status = "completed"
        html_content = create_html_content(response.json())
        
        full_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; color: black; }}
        .text-red-500 {{ color: red; }}
        .text-xl {{ font-size: 1.25rem; }}
        .font-semibold {{ font-weight: 600; }}
        .mb-2 {{ margin-bottom: 0.5rem; }}
        .mt-4 {{ margin-top: 1rem; }}
        .list-disc {{ list-style-type: disc; }}
        .pl-5 {{ padding-left: 1.25rem; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""
        pdfkit.from_string(full_html, 'summary.pdf', configuration=pdfkit_config)
        
        sender_email = "mail1test1jb@gmail.com"
        receiver_email = get_user_info(USER_CREDENTIALS)
        subject = "Summary Report"
        body = "Please find the attached summary report."
        password = "chvg qyhg ktgu xmkg"  
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with open('summary.pdf', 'rb') as attachment:
            part = MIMEApplication(attachment.read(), Name='summary.pdf')
            part['Content-Disposition'] = 'attachment; filename="summary.pdf"'
            msg.attach(part)
    
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
    
    except http_requests.exceptions.RequestException as error:
        print("Error generating summary:", error)

def analyze_sentiment(transcript):
    try:
        response = http_requests.post(api_url, json={'transcript': transcript})
        response.raise_for_status()
        overall_sentiment = response.json().get('overall_sentiment')
        print("Overall Sentiment:", overall_sentiment)
    except http_requests.exceptions.RequestException as error:
        print("Error analyzing sentiment:", error)

def process_document(auth, document_id):
    document_content = get_document_content(auth, document_id)
    transcript = convert_transcript_to_string(document_content)
    generate_summary(transcript)
    analyze_sentiment(transcript)



def on_transcript_ready(message: pubsub_v1.subscriber.message.Message):
    """Display information about a meeting transcript when artifact is ready."""
    payload = json.loads(message.data)
    resource_name = payload.get("transcript").get("name")
    client = meet.ConferenceRecordsServiceClient(credentials=USER_CREDENTIALS)
    transcript = client.get_transcript(name=resource_name)
    print(f"Transcript available at {transcript.docs_destination.export_uri, transcript}")
    docID = extract_document_id(transcript.docs_destination.export_uri)
    process_document(USER_CREDENTIALS, docID)

def on_message(message: pubsub_v1.subscriber.message.Message) -> None:
    """Handles an incoming event from the Google Cloud Pub/Sub API."""
    event_type = message.attributes.get("ce-type")
    handler = {
        "google.workspace.meet.conference.v2.started": lambda x: print("Conference Started"),
        "google.workspace.meet.participant.v2.joined": lambda x: print("Participant Joined"),
        "google.workspace.meet.transcript.v2.fileGenerated": on_transcript_ready,
    }.get(event_type)
    try:
        if handler is not None:
            handler(message)
        message.ack()
    except Exception as error:
        print("Unable to process event")
        print(error)

def listen_for_events(subscription_name: str = None):
    """Subscribe to events on the subscription."""
    subscriber = pubsub_v1.SubscriberClient()
    with subscriber:
        future = subscriber.subscribe(subscription_name, callback=on_message)
        print("Listening for events")
        try:
            future.result()
        except KeyboardInterrupt:
            future.cancel()
    print("Done")

def start_listening(meeting_code):
    space = get_space_details(meeting_code)
    print("space", space)
    print(f"Join the meeting at {space.meeting_uri}")
    TOPIC_NAME = "projects/note-taker-440718/topics/workspace-event"
    SUBSCRIPTION_NAME = "projects/note-taker-440718/subscriptions/workspace-event-sub"
    subscribe_to_space(topic_name=TOPIC_NAME, space_name=space.name)
    listen_for_events(subscription_name=SUBSCRIPTION_NAME)

@app.route("/summary/<mid>")
def summary(mid):
    global summary_status
    summary_status = "loading"  # Reset status to loading
    listener_thread = threading.Thread(target=start_listening, args=(mid,), daemon=True)
    listener_thread.start()
    return jsonify({"message": summary_status})

@app.route("/summary_status", methods=["GET"])
def summary_status():
    global meet_summary
    global summary_status
    if summary_status == "completed":
        return jsonify(meet_summary)
    else:
        return jsonify({"message": summary_status})

if __name__ == "__main__":
    app.run(debug=True)
