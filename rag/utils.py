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

def find_num_references(pdf_document):
    text = extract_text_from_pdf(pdf_document)
    
    parts = re.split(r"\n\s*(References|REFERENCES)\s*\n", text)
    
    references_text = parts[-1]
    
    # Split into lines
    lines = references_text.split("\n")
    
    references = []
    current_reference = ""
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Line start with number (e.g., [1]). Thus it is a new reference
        if re.match(r"^\[\d+\]", line):
            if current_reference:
                # Save the old reference
                references.append(current_reference.strip())
            
            current_reference = line
        else:
            current_reference += " " + line
    
    if current_reference:
        references.append(current_reference.strip())
    
    filtered = []
    for reference in references:
        reference = clean_reference(reference)
        if is_likely_paper(reference):
            filtered.append(reference)
    
    return len(references)

# Extract references from Reference section from paper text
def extract_references(text, num_references):
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
    current_reference = ""
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Line start with number (e.g., [1]). Thus it is a new reference
        if re.match(r"^\[\d+\]", line):
            if current_reference:
                # Save the old reference
                references.append(current_reference.strip())
            
            current_reference = line
        else:
            current_reference += " " + line
    
    if current_reference:
        references.append(current_reference.strip())
    
    filtered = []
    for reference in references:
        reference = clean_reference(reference)
        if is_likely_paper(reference):
            filtered.append(reference)
            
    
    # Limit the number of references (can also be changed later, look at how 10 works first)
    return filtered[:num_references]

def split_into_sentences(text):
    # Split into sentences using regex
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return sentences

def is_likely_paper(reference: str) -> bool:
    ref = reference.lower()
    
    # Skip common non-paper sources
    skip_keywords = [
        "github",
        "wikipedia",
        "last accessed",
        "product",
        "documentation"
    ]
    
    if any(k in ref for k in skip_keywords):
        return False
    
    return True

def clean_reference(ref):
    ref = re.sub(r"\[.*?\]", "", ref)   # remove [1]
    ref = re.sub(r"http\S+", "", ref)   # remove URLs
    return ref.strip()