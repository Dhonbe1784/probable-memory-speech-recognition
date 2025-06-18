from flask import Flask, request, jsonify, render_template
import speech_recognition as sr
import os
import time
import threading
import wave
from datetime import datetime
import io
import numpy as np
from pydub import AudioSegment

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'recordings'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global state for recording management
class RecordingState:
    def __init__(self):
        self.active = False
        self.transcription = ""
        self.audio_buffer = []
        self.last_update = time.time()
        self.lock = threading.Lock()
        self.recognizer = sr.Recognizer()
        self.stop_event = threading.Event()

recording_state = RecordingState()

def convert_to_wav(audio_data):
    """Convert audio data to WAV format"""
    try:
        # Convert bytes to audio segment
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
        
        # Convert to WAV with the required parameters
        wav_io = io.BytesIO()
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(wav_io, format="wav")
        
        return wav_io.getvalue()
    except Exception as e:
        print(f"Audio conversion error: {e}")
        return None

def transcribe_audio(audio_data):
    """Transcribe audio data using Google Speech Recognition"""
    try:
        # Create AudioData object
        audio_data = sr.AudioData(audio_data, 16000, 2)
        
        # Transcribe using Google
        text = recording_state.recognizer.recognize_google(audio_data)
        return text
    except sr.UnknownValueError:
        return ""  # Return empty string when no speech detected
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""

def transcribe_stream():
    """Background thread for continuous transcription"""
    global recording_state
    
    while not recording_state.stop_event.is_set():
        if not recording_state.active or time.time() - recording_state.last_update < 1.0:
            time.sleep(0.1)
            continue
        
        with recording_state.lock:
            if not recording_state.audio_buffer:
                time.sleep(0.1)
                continue
            
            # Process audio buffer
            audio_chunk = b''.join(recording_state.audio_buffer)
            recording_state.audio_buffer = []
            
            # Convert to WAV format
            wav_data = convert_to_wav(audio_chunk)
            
            if wav_data:
                # Transcribe the audio chunk
                text = transcribe_audio(wav_data)
                if text:
                    recording_state.transcription += text + " "
                    print(f"Transcription: {text}")
                
                recording_state.last_update = time.time()

# Start transcription thread when server starts
transcription_thread = threading.Thread(target=transcribe_stream, daemon=True)
transcription_thread.start()

@app.route('/')
def index():
    """Serve the main interface"""
    return render_template('index.html')

@app.route('/start_recording', methods=['POST'])
def start_recording():
    """Start a new recording session"""
    global recording_state
    
    if recording_state.active:
        return jsonify({"status": "error", "message": "Recording already in progress"})
    
    # Reset state
    recording_state.active = True
    recording_state.transcription = ""
    recording_state.audio_buffer = []
    recording_state.last_update = time.time()
    recording_state.stop_event.clear()
    
    return jsonify({"status": "success", "message": "Recording started"})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    """Stop the current recording session"""
    global recording_state
    
    if not recording_state.active:
        return jsonify({"status": "error", "message": "No recording in progress"})
    
    recording_state.active = False
    recording_state.stop_event.set()
    
    # Save final transcription to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"transcript_{timestamp}.txt"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    with open(file_path, 'w') as f:
        f.write(recording_state.transcription)
    
    return jsonify({
        "status": "success", 
        "message": "Recording stopped",
        "transcription": recording_state.transcription
    })

@app.route('/audio_stream', methods=['POST'])
def audio_stream():
    """Endpoint for streaming audio chunks"""
    global recording_state
    
    if not recording_state.active:
        return jsonify({"status": "error"}), 400
    
    # Get audio data from request
    audio_data = request.data
    
    with recording_state.lock:
        recording_state.audio_buffer.append(audio_data)
        recording_state.last_update = time.time()
    
    return jsonify({"status": "success"})

@app.route('/get_transcription', methods=['GET'])
def get_transcription():
    """Get the current transcription"""
    return jsonify({"transcription": recording_state.transcription})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
