import os
import shutil
import openai
import openpyxl
import logging
from flask import Flask, request, jsonify, session
from flask_restful import Api, Resource
from dotenv import load_dotenv
from uuid import uuid4
import process_files as pf

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app and API
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')  # Replace with a real secret key
app.config['UPLOAD_FOLDER'] = 'uploads'
api = Api(app)

# Ensure the upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UploadFile(Resource):
    def post(self):
        logger.info("Received file upload request")
        if 'file' not in request.files:
            logger.error("No file part in the request")
            return {'message': 'No file part'}, 400
        
        file = request.files['file']
        if file.filename == '':
            logger.error("No selected file")
            return {'message': 'No selected file'}, 400
        
        try:
            if file:
                if 'session_id' not in session:
                    session['session_id'] = str(uuid4())
                    logger.info(f"New session created: {session['session_id']}")
                
                session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session['session_id'])
                os.makedirs(session_folder, exist_ok=True)
                logger.info(f"Session folder created: {session_folder}")
                
                filename = file.filename
                filepath = os.path.join(session_folder, filename)
                file.save(filepath)
                logger.info(f"File saved: {filepath}")
                
                # Process files and save embeddings
                pf.process_and_save_embeddings(session_folder)
                logger.info(f"Embeddings processed and saved in session folder: {session_folder}")
                
                return {'message': 'File uploaded successfully', 'filename': filename}, 201
        except Exception as e:
            logger.exception("An error occurred during file upload")
            return {'message': 'An error occurred during file upload'}, 500

class RetrieveFiles(Resource):
    def get(self):
        logger.info("Received request to retrieve files")
        if 'session_id' not in session:
            logger.error("No session started")
            return {'message': 'No session started'}, 400
        
        session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session['session_id'])
        if not os.path.exists(session_folder):
            logger.error("No files found for this session")
            return {'message': 'No files found for this session'}, 404
        
        try:
            files = os.listdir(session_folder)
            if not files:
                logger.error("No files found in the session folder")
                return {'message': 'No files found in the session folder'}, 404
            
            file_list = [{'filename': file} for file in files if file != 'embeddings.npy']
            logger.info(f"Files retrieved: {file_list}")
            return {'files': file_list}
        except Exception as e:
            logger.exception("An error occurred while retrieving files")
            return {'message': 'An error occurred while retrieving files'}, 500

class GPTResponse(Resource):
    def post(self):
        logger.info("Received GPT response request")
        data = request.json
        user_message = data.get('user_message')

        if 'session_id' not in session:
            logger.error("No session started")
            return {'message': 'No session started'}, 400
        
        session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session['session_id'])
        embeddings_file = os.path.join(session_folder, 'embeddings.npy')
        if not os.path.exists(embeddings_file):
            logger.error("No embeddings found for this session")
            return {'message': 'No embeddings found for this session'}, 404
        
        try:
            embeddings = pf.load_embeddings(embeddings_file)
            logger.info(f"Embeddings loaded from file: {embeddings_file}")
            relevant_files = pf.query_embeddings(embeddings, user_message)
            logger.info(f"Relevant files identified: {relevant_files}")

            # Get the content of the most relevant file
            if relevant_files:
                top_file = relevant_files[0]
                top_content = pf.read_file(top_file)
                logger.info(f"Top file content: {top_content}")
            else:
                top_content = "No relevant documents found."
                logger.info("No relevant documents found")

            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            chat_completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are to answer all Queries using the provided context"
                    },
                    {
                        "role": "user",
                        "content": f"Query: {user_message}\n Context: {top_content}",
                    }
                ]
            )

            assistant_message = chat_completion.choices[0].message.content
            logger.info(f"Assistant message: {assistant_message}")
            return {"message": assistant_message}
        except Exception as e:
            logger.exception("An error occurred while generating GPT response")
            return {'message': 'An error occurred while generating GPT response'}, 500

class DeleteSession(Resource):
    def delete(self):
        logger.info("Received request to delete session")
        if 'session_id' not in session:
            logger.error("No session started")
            return {'message': 'No session started'}, 400
        
        session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session['session_id'])
        if os.path.exists(session_folder):
            try:
                shutil.rmtree(session_folder)
                logger.info(f"Session folder deleted: {session_folder}")
                session.pop('session_id', None)
                logger.info("Session data cleared")
                return {'message': 'Session and all associated files deleted successfully'}, 200
            except Exception as e:
                logger.exception("An error occurred while deleting session files")
                return {'message': 'An error occurred while deleting session files'}, 500
        else:
            logger.error("No files found for this session")
            return {'message': 'No files found for this session'}, 404

class GPTPackResponse(Resource):
    def post(self):
        logger.info("Received GPT pack response request")
        data = request.json
        user_message = data.get('user_message')
        conversation_history = data.get('history', [])

        try:
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            # Prepare the user message with the conversation history
            history_content = " ".join([f"{entry['sender']}: {entry['message']}" for entry in conversation_history])
            full_user_message = f"Prompt: {user_message} History: {history_content}"

            messages = [
                {"role": "system", "content": "You are to answer all Queries using the provided context"},
                {"role": "user", "content": full_user_message}
            ]

            logger.info(f"Sending messages to OpenAI: {messages}")

            chat_completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages
            )

            assistant_message = chat_completion.choices[0].message.content
            logger.info(f"Assistant message: {assistant_message}")
            return {"message": assistant_message}
        except Exception as e:
            logger.exception("An error occurred while generating GPT pack response")
            return {'message': 'An error occurred while generating GPT pack response'}, 500



api.add_resource(UploadFile, '/upload')
api.add_resource(RetrieveFiles, '/retrieve-files')
api.add_resource(GPTResponse, '/gpt-response')
api.add_resource(DeleteSession, '/delete-session')
api.add_resource(GPTPackResponse, '/gpt-pack-response')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
