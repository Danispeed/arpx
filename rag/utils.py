import fitz
import re

def extract_text_from_pdf(pdf_document):
    # Read the file as bytes (stream= tells PyMuPDF where in memory to read from)
    document = fitz.open(stream=pdf_document.read(), filetype="pdf")
    text = ""
    
    # Document is now a PyMuPDF Document object
    for page in document:
        # Extract the readable text from the current page
        text += page.get_text()
    
    return text

# Extract references from Reference section from paper text
def extract_references(text):
    # Find reference section
    parts = re.split(r"\n\s*(References|REFERENCES)\s*\n", text)
    
    # Why < 3:
    # The parts will look like:
    # [
    #    "everything before references",
    #    "References",
    #    "everything after references",
    # ]
    # If references is not found: ["entire document"]
    if len(parts) < 3:
        print("No references section found")
        return []
    
    references_text = parts[-1]
    
    # Split into lines
    lines = references_text.split("\n")
    
    references = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Skip very short lines (should be noise)
        if len(line) < 20:
            continue
        
        references.append(line)
    
    # Limit the number of references (can also be changed later, look at how 10 works first)
    return references[:3]