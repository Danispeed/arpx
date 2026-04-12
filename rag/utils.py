import fitz

def extract_text_from_pdf(pdf_document):
    # Read the file as bytes (stream= tells PyMuPDF where in memory to read from)
    document = fitz.open(stream=pdf_document.read(), filetype="pdf")
    text = ""
    
    # Document is now a PyMuPDF Document object
    for page in document:
        # Extract the readable text from the current page
        text += page.get_text()
    
    return text