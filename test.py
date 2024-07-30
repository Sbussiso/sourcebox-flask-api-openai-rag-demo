import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Define the base URL, defaulting to 'http://127.0.0.1:5000' if not present in .env
base_url = os.getenv('BASE_URL', 'http://127.0.0.1:5000')

# Print the base URL for debugging purposes
print(f"Base URL: {base_url}")

# Ensure the base URL is valid
if not base_url.startswith(('http://', 'https://')):
    base_url = 'http://127.0.0.1:5000'

# Initialize the session
session = requests.Session()

try:
    # 1. Upload the file
    upload_url = f'{base_url}/upload'
    file_path = '/workspaces/python-8/test/example.csv'

    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = session.post(upload_url, files=files)
        print("Upload response:", response.json())

    # 2. Retrieve the list of uploaded files
    retrieve_files_url = f'{base_url}/retrieve-files'
    response = session.get(retrieve_files_url)
    print("Retrieve files response:", response.json())

    # 3. Get GPT-3 response
    gpt_response_url = f'{base_url}/gpt-response'
    data = {'user_message': 'Explain the content of the uploaded file'}
    response = session.post(gpt_response_url, json=data)
    print("GPT response:", response.json())

    # 4. Get GPT-3 pack response (assuming you have implemented the relevant logic in the endpoint)
    gpt_pack_response_url = f'{base_url}/gpt-pack-response'
    pack_data = {
        'user_message': 'Explain the pack content',
        'pack_id': 'example_pack_id',  # You will need to replace this with a valid pack ID
        'history': 'previous conversation history'
    }
    response = session.post(gpt_pack_response_url, json=pack_data)
    print("GPT pack response:", response.json())

    # 5. Delete the session and all associated files
    delete_session_url = f'{base_url}/delete-session'
    response = session.delete(delete_session_url)
    print("Delete session response:", response.json())

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
