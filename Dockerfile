FROM python:3.11

WORKDIR /arpx

# Copy files
COPY . . 

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Streamlit port
EXPOSE 8051

# Run app
CMD ["streamlit", "run", "app.py", "--server.port=8051", "--server.address=0.0.0.0"]