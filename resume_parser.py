from pdfminer.high_level import extract_text
import docx

def extract_resume_text(path):
    """
    Takes the file path of an uploaded resume and extracts all the text from it.
    Supports both .pdf and .docx file formats.
    """
    
    # If it's a PDF, use the pdfminer library to extract text
    if path.endswith(".pdf"):
        return extract_text(path)

    # If it's a Word Document, use the python-docx library to extract text paragraph by paragraph
    elif path.endswith(".docx"):
        doc = docx.Document(path)
        # Join all the paragraphs together with line breaks
        return "\n".join([p.text for p in doc.paragraphs])

    # If the file format is unsupported, return an empty string
    return ""
