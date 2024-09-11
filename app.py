import json
import os
from pprint import pprint

private_key_id = os.getenv('private_key_id')
private_key = os.getenv('private_key')
client_email = os.getenv('client_email')
client_id = os.getenv('client_id')
auth_uri = os.getenv('auth_uri')
token_uri = os.getenv('token_uri')
auth_provider_x509_cert_url = os.getenv('auth_provider_x509_cert_url')
client_x509_cert_url = os.getenv('client_x509_cert_url')
universe_domain =  os.getenv("universe_domain")

service_account_info = {
    "type": "service_account",
    "project_id": os.getenv('project_id'),
    "private_key_id": private_key_id,
    "private_key": private_key,
    "client_email": client_email,
    "client_id": client_id,
    "auth_uri": auth_uri,
    "token_uri": token_uri,
    "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
    "client_x509_cert_url": client_x509_cert_url,
    "universe_domain": universe_domain
}
# pprint(service_account_info)

with open('service_account.json', 'w') as f:
    json.dump(service_account_info, f, indent=2)

token = os.getenv('token')
refresh_token = os.getenv('refresh_token')
token_uri = os.getenv('token_uri')
client_id_mail = os.getenv('client_id_mail')
client_secret = os.getenv('client_secret')
scopes = os.getenv('scopes')
universe_domain = os.getenv('universe_domain')
account = os.getenv('account')
expiry = os.getenv('expiry')

token_info = {
    "token": token,
    "refresh_token": refresh_token,
    "token_uri": token_uri,
    "client_id": client_id_mail,
    "client_secret": client_secret,
    "scopes": ["https://www.googleapis.com/auth/gmail.send"],
    "universe_domain": universe_domain,
    "account": account,
    "expiry": expiry
}
# pprint(token_info)

with open('token.json', 'w') as f:
    json.dump(token_info, f)


import streamlit as st
from agents import ResearchAgent, VideoAgent, EmailAgent
from langchain_openai import ChatOpenAI
# from dotenv import load_dotenv
# load_dotenv()

st.title("Video Manager")

topic = st.text_input("Enter the topic")
url = st.text_input("Enter the URL")
to_mail = st.text_input("Enter your Email")

if st.button("Submit"):
    if topic and url and to_mail:
        llm = ChatOpenAI(model='gpt-4o-mini')
        research_agent = ResearchAgent(llm, url, topic)

        with st.spinner("Researching content..."):
            summarized_content = research_agent.research()
            st.write("Research complete ✅")

        with st.spinner("Creating Video..."):
            video_agent = VideoAgent(llm, topic, summarized_content)
            video_status = video_agent.create_video()
            st.write("Video created ✅")

        with st.spinner("Sending email..."):
            email_agent = EmailAgent(llm, to_mail)
            mail = email_agent.send_email(to_mail, video_status)
            st.write("Email sent ✅")

    else:
        st.warning("Please enter a topic, URL, and select at least one option.")
