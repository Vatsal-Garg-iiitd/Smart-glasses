#!/usr/bin/env python3
"""
Wake Word Listener ("Hey Lens")
===============================
This script listens continuously using the connected microphone.
When it hears the wake word "hey lens", it triggers the backend API.
"""

import time
import requests
import speech_recognition as sr

# Configuration
BACKEND_URL = "http://raspy.local:8000/trigger-wake-word"
WAKE_WORDS = ["hey lens", "hey lance", "hay lens", "hey lense", "halen", "helen"]

def trigger_backend():
    try:
        response = requests.post(BACKEND_URL, timeout=2)
        if response.status_code == 200:
            print("Successfully triggered frontend 'Ask AI' mode.")
        else:
            print(f"Failed to trigger backend. Status: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to backend: {e}")

def callback(recognizer, audio):
    """This is called from the background thread when audio is captured."""
    try:
        # Use Google's free web speech API
        text = recognizer.recognize_google(audio).lower()
        print(f"Heard: '{text}'")
        
        if any(wake_word in text for wake_word in WAKE_WORDS):
            print(">>> WAKE WORD DETECTED! <<<")
            trigger_backend()
            # Sleep a bit to prevent multiple triggers
            time.sleep(2)
            
    except sr.UnknownValueError:
        # Unintelligible speech
        pass
    except sr.RequestError as e:
        print(f"Speech Recognition service error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

def main():
    r = sr.Recognizer()
    m = sr.Microphone()
    
    with m as source:
        print("Adjusting for ambient noise... Please wait.")
        r.adjust_for_ambient_noise(source, duration=2)
        print("Ready! Listening in the background for 'Hey Lens'...")
    
    # Start listening in the background
    # phrase_time_limit ensures it processes chunks quickly
    stop_listening = r.listen_in_background(m, callback, phrase_time_limit=3)
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping wake word listener.")
        stop_listening(wait_for_stop=False)

if __name__ == "__main__":
    main()
