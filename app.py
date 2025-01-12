import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import numpy as np
from sklearn.preprocessing import LabelEncoder
import speech_recognition as sr
import google.generativeai as genai
import json
from pydub import AudioSegment
import io
import os

# Configure Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY1')
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS

# Load the saved mental health model
model = joblib.load('mental_health_model.pkl')

# Define the order of columns as used in training
columns_order = ['gender', 'Occupation', 'Mood_Swings', 'Changes_Habits', 'Work_Interest', 'Social_Weakness']

# Function to encode input for mental health prediction
def encode_input(user_input):
    encoded_input = []
    for column in columns_order:
        le = LabelEncoder()
        le.fit(['Male', 'Female'] if column == 'gender' else
               ['Corporate', 'Student', 'Business', 'Housewife', 'Others'] if column == 'Occupation' else
               ['Medium', 'Low', 'High'] if column == 'Mood_Swings' else
               ['No', 'Yes', 'Maybe'])  # Adjust categories as per each column
        encoded_input.append(le.transform([user_input[column]])[0])
    return np.array(encoded_input).reshape(1, -1)

# Route for mental health prediction
@app.route('/predict', methods=['POST'])
def predict():
    user_input = request.json  # Expecting JSON input
    X_test = encode_input(user_input)
    probabilities = model.predict_proba(X_test)
    prob_yes = probabilities[0][1]
    return jsonify({"mental_fitness_score": int(round(prob_yes * 100))})

# Function to record audio
def record_audio():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Speak now...")
        audio = recognizer.listen(source)
    return audio

# Function to convert speech to text
def convert_speech_to_text(audio):
    recognizer = sr.Recognizer()
    try:
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        return "Speech not understood"
    except sr.RequestError:
        return "Error in speech recognition service"

# Route for voice analysis
@app.route('/voice_analysis', methods=['POST'])
def voice_analysis():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    
    try:
        # Read the audio file data
        audio_data = audio_file.read()
        
        # Convert to base64 for Gemini
        file_data = {
            "mime_type": "audio/webm",  # Update this based on the actual mime type
            "data": base64.b64encode(audio_data).decode('utf-8')
        }

        # Perform voice analysis using Gemini
        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt_template = """
        Analyze the following audio file and provide a voice analysis in JSON format.
        
        Provide the analysis in exactly this JSON format:
        {
            "Smoothness": "<percentage out of 100> %",
            "Control": "<percentage out of 100> %",
            "Liveliness": "<number between 0-1 with 2 decimal places>",
            "Energy_range": "<number> dB",
            "Clarity": "<number> ms",
            "Crispness": "<number between 0-1 with 2 decimal places>",
            "Speech": "<Normal/Emotional/Monotone>",
            "Pause": "<Regular/Fluent/Filled Pauses>"
        }
        """

        response = model.generate_content([file_data, prompt_template])
        json_str = response.text.strip()
        if '```json' in json_str:
            json_str = json_str.split('```json')[1].split('```')[0].strip()
        analysis = json.loads(json_str)
    except json.JSONDecodeError:
        analysis = {"error": "Failed to parse JSON response"}
    except Exception as e:
        analysis = {"error": f"An error occurred: {str(e)}"}

    return jsonify({"voice_analysis": analysis})

if __name__ == '__main__':
    app.run(debug=True)
