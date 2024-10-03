from flask import Flask, render_template, request, jsonify, url_for
from flask_socketio import SocketIO, emit
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import translate_v2 as translate
from google.cloud import texttospeech
from gtts import gTTS
import os
import io

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

# Set Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"

# Google Cloud services clients
speech_client = speech.SpeechClient()
translate_client = translate.Client()
text_to_speech_client = texttospeech.TextToSpeechClient()

@app.route('/')
def index():
    return render_template('speaker.html')

@app.route('/listener')
def listener():
    return render_template('listener.html')

# Handle real-time speech from the speaker
@socketio.on('audio_data')
def handle_audio_data(audio_data, input_lang, listeners):
    # Transcribe the speaker's audio
    audio = speech.RecognitionAudio(content=audio_data)
    config = speech.RecognitionConfig(language_code=input_lang)
    response = speech_client.recognize(config=config, audio=audio)

    # Clear the output directory
    output_directory = 'static/output/'
    for filename in os.listdir(output_directory):
        file_path = os.path.join(output_directory, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)  # Delete each file in the output directory
                print(f'Deleted file: {file_path}')
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

    # Process transcription and translation
    for result in response.results:
        transcription = result.alternatives[0].transcript
        print(f"Transcribed Text: {transcription}")

        # Translate for each listener
        for listener in listeners:
            translated_text = translate_client.translate(transcription, target_language=listener['language'])['translatedText']
            print(f"Translated to {listener['language']}: {translated_text}")

            # Convert translated text to speech
            tts = gTTS(translated_text, lang=listener['language'])
            audio_path = f'static/output/{listener["id"]}_translated.mp3'
            tts.save(audio_path)

            # Log the emitted event to see if it's being triggered
            print(f"Emitting audio to listener {listener['id']} with audio URL {audio_path}")

            # Send the translated speech to the listener
            emit('translated_audio', {
                'listener_id': listener['id'],
                'audio_url': url_for('static', filename=f'output/{listener["id"]}_translated.mp3')
            }, broadcast=True)


@socketio.on('start_listening')
def handle_start_listening(data):
    listener_id = data['listener_id']  # This will be the same as the listenerId generated in the client
    language = data['language']
    print(f"Listener {listener_id} has started listening in {language}")

    # Emit translated audio back to this specific listener
    emit('translated_audio', {
        'listener_id': listener_id,  # This matches the client-side listenerId
        'audio_url': 'path/to/audio/file.mp3'
    })

if __name__ == "__main__":
    socketio.run(app, debug=True)
