import os
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
from PyPDF2 import PdfFileReader  # For PyPDF2==1.26.0

app = Flask(__name__)

# Define the upload directory
UPLOAD_FOLDER = 'uploaded_files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf'}

# Function to check if the file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET", "POST"])
def index():
    extracted_texts = None
    if request.method == "POST":
        if 'uploaded_folder' not in request.files:
            return "No folder part in the request", 400
        uploaded_folder = request.files.getlist("uploaded_folder")  # Get list of uploaded files
        extracted_texts = {}

        for uploaded_file in uploaded_folder:
            # Check if the uploaded file is allowed (only accept PDFs)
            if uploaded_file and allowed_file(uploaded_file.filename):
                filename = secure_filename(uploaded_file.filename)
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                uploaded_file.save(save_path)  # Save the uploaded file

                try:
                    # Extract text from the PDF file using PdfFileReader (for PyPDF2==1.26.0)
                    with open(save_path, 'rb') as f:
                        reader = PdfFileReader(f)
                        text = ""
                        for page_num in range(reader.getNumPages()):
                            page = reader.getPage(page_num)
                            page_text = page.extractText()
                            if page_text:
                                text += page_text

                    # Store the extracted text in the dictionary
                    if text:
                        extracted_texts[filename] = text
                    else:
                        extracted_texts[filename] = "No text could be extracted from the PDF."
                except Exception as e:
                    extracted_texts[filename] = f"Error reading file: {str(e)}"
            else:
                extracted_texts[uploaded_file.filename] = "Not a PDF file."

    return render_template("index.html", extracted_texts=extracted_texts)

if __name__ == "__main__":
    app.run(debug=True)
