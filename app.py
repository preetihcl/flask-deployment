import os
import openai
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for
from PyPDF2 import PdfFileReader
from werkzeug.utils import secure_filename

# Flask configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploaded_files')  # Outside static folder
ALLOWED_EXTENSIONS = {"pdf"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Define the allowed_file function
def allowed_file(filename):
    """Check if the file has an allowed extension (PDF)."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to extract text from PDFs
def extract_text_from_pdfs(folder_path):
    """Extract text from all PDF files in a folder."""
    data = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".pdf"):
            filepath = os.path.join(folder_path, filename)
            try:
                with open(filepath, "rb") as file:
                    reader = PdfFileReader(file)
                    text = ""
                    for page_num in range(reader.numPages):
                        text += reader.getPage(page_num).extract_text() + "\n"
                    data.append({"Filename": f"<strong>{filename}</strong>", "Content": text.strip()})
            except Exception as e:
                data.append({"Filename": f"<strong>{filename}</strong>", "Content": f"Error: {str(e)}"})
    return data

@app.route("/", methods=["GET", "POST"])
def index():
    data = None
    analyzed_data = []
    uploaded_files = []
    
    if request.method == "POST":
        # Read the OpenAI API key from the form input
        api_key = request.form.get("api_key")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            openai.api_key = api_key
        else:
            return "API Key is required", 400

        if "files" not in request.files:
            return redirect(request.url)

        files = request.files.getlist("files")
        if not files:
            print("No files uploaded.")
        
        saved_files = []
        for file in files:
            print(f"Uploaded file: {file.filename}")
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                print(f"Saving file to: {file_path}")
                file.save(file_path)  # Save the file in the uploaded_files folder
                saved_files.append(file_path)
                uploaded_files.append(filename)  # Keep track of uploaded filenames

        # Extract text from PDFs
        extracted_data = extract_text_from_pdfs(app.config["UPLOAD_FOLDER"])

        # Analyze each extracted text using GPT
        for pdf in extracted_data:
            filename = pdf["Filename"]
            content = pdf["Content"]
            if content:
                gpt_result = get_gpt_response(content)
                
                if isinstance(gpt_result, dict):  # Ensure it is a valid result
                    analyzed_data.append({
                        "Candidate Name": filename.replace("<strong>", "").replace("</strong>", ""), 
                        **gpt_result  # Add the skills and ratings as separate columns
                    })

        # Convert analyzed data to a DataFrame for display
        data = pd.DataFrame(analyzed_data)

        # Drop the 'Rating' column if it exists
        if "Rating" in data.columns:
            data = data.drop(columns=["Rating"])

    return render_template(
        "index.html",
        tables=[data.to_html(classes="table table-bordered", index=False, escape=False)] if data is not None else None,
        uploaded_files=uploaded_files,  # Pass uploaded filenames to the template
    )

# GPT response function
def get_gpt_response(resumetext):
    """Send text to OpenAI GPT-3.5 and get a formatted response."""
    try:
        prompt = (
            f"You are a helpful assistant. Analyze the provided resume text: {resumetext}. "
            "Generate the output as a Python dictionary with keys representing skills/technologies "
            "such as Python, Generative AI, AWS, Azure, NLP, Deep Learning, Database, Time Series, ML. "
            "For each key, rate the proficiency as 'Proficient', 'Intermediate', or 'Expert'. "
            "Additionally, add a key like 'overall rating' out of 5 in the final output. "
            "Do not include any explanations."
        )
        response = openai.Completion.create(
            engine="gpt-3.5-turbo-instruct",
            prompt=prompt,
            max_tokens=200,
            temperature=0,
            n=1,
        )
        
        if "choices" in response and len(response["choices"]) > 0:
            result = response["choices"][0].get("text", "").strip()
            
            if result:
                responselist = result.split("\n")
                str_list = list(filter(None, responselist))
                mydict = {}
                
                for item in str_list:
                    parts = item.split(":")
                    if len(parts) == 2:  # Ensure that each line contains a key-value pair
                        mydict[parts[0].strip()] = parts[1].strip()

                # Add overall rating calculation (based on proficiency)
                overall_rating = calculate_overall_rating(mydict)
                mydict['Rating'] = overall_rating
                return mydict
            else:
                return {"Error": "No text returned from GPT response."}
        else:
            return {"Error": "No valid choices found in GPT response."}
    
    except Exception as e:
        return {"Error": f"Error processing GPT response: {str(e)}"}

# Function to calculate the overall rating based on skill proficiency
def calculate_overall_rating(skill_dict):
    """Calculate an overall rating based on proficiency levels of skills."""
    proficiency_map = {
        "Expert": 5,
        "Proficient": 4,
        "Intermediate": 3
    }
    total_score = 0
    count = 0
    
    # Iterate over skills and calculate the total score
    for skill, proficiency in skill_dict.items():
        if proficiency in proficiency_map:
            total_score += proficiency_map[proficiency]
            count += 1
    
    # Calculate average score and scale it to out of 5
    if count > 0:
        average_score = total_score / count
        return round(average_score, 1)  # Rounded to 1 decimal place
    else:
        return 0  # Return 0 if no valid proficiency ratings were found

if __name__ == "__main__":
    app.run(debug=True)
