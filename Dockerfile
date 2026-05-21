FROM python:3.11

WORKDIR /arpx

# Copy files
COPY . . 

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download the Piper TTS voice model outside /arpx so the compose bind mount
# does not shadow it at runtime.
ENV PIPER_VOICE_DIR=/opt/piper
RUN mkdir -p /opt/piper \
    && curl -fsSL -o /tmp/voice.tar.gz \
       "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-lessac-medium.tar.gz" \
    && tar -xzf /tmp/voice.tar.gz -C /opt/piper \
    && rm /tmp/voice.tar.gz

# Expose Streamlit port
EXPOSE 8051

# Run app
CMD ["streamlit", "run", "app.py", "--server.port=8051", "--server.address=0.0.0.0"]