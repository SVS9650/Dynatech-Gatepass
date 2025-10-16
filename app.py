from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# ---------------- Settings (Your original settings, kept local to the server) ----------------
# NOTE: In a real deployment, these settings should be stored in environment variables, not hardcoded.
DATA_FILE = "gatepass_data.json"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USERNAME = "gatepassDC@gmail.com"
EMAIL_PASSWORD = "xurh olou naqc tgwy"  # 16 digit app password
TO_EMAIL = "Shubhankar.singh@dynatechcontrols.in"
CC_EMAILS = ["hr@dynatechcontrols.in", "shardulvikramsingh6@gmail.com"]

# ---------------- Helper Functions ----------------
def load_data():
    """Loads existing gate pass data."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            # Handle empty file case
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_data(data):
    """Saves gate pass data."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def clean_old_entries():
    """Removes entries older than 45 days."""
    data = load_data()
    cutoff_date = datetime.now() - timedelta(days=45)
    
    # We must handle the case where 'date' might be missing, although it shouldn't be
    cleaned_data = []
    for entry in data:
        try:
            if datetime.strptime(entry.get("date", "1970-01-01"), "%Y-%m-%d") >= cutoff_date:
                cleaned_data.append(entry)
        except ValueError:
            # Skip entries with invalid date format
            continue
            
    save_data(cleaned_data)
    return cleaned_data

def send_email(user_name, user_email, department, reason, s_no):
    """Sends the gate pass request email."""
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USERNAME
    msg["To"] = TO_EMAIL
    msg["Cc"] = ", ".join(CC_EMAILS)
    msg["Reply-To"] = user_email
    msg["Subject"] = f"Gate Pass Request #{s_no} from {user_name}"

    body = f"""
Gate Pass Request Details:

S.No: {s_no}
Name: {user_name}
Department: {department}
Reason: {reason}
Date: {datetime.now().strftime('%Y-%m-%d')}

Please reply to this email with 'Approved' or 'Denied'.
"""
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USERNAME, [TO_EMAIL] + CC_EMAILS, msg.as_string())
        server.quit()
        print(f"Gate Pass #{s_no} Email sent successfully to {TO_EMAIL} and CCs.")
        return True, "Email sent successfully."
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False, f"Failed to send email. Check SMTP settings or app password. Error: {e}"

# --- Flask Server Setup ---
app = Flask(__name__)
# Crucial for cross-origin requests from the browser
CORS(app) 

# Initial data cleaning and load on server startup
CURRENT_DATA = clean_old_entries()

@app.route('/api/gatepass', methods=['POST'])
def add_gate_pass_endpoint():
    """
    Handles POST requests from the web front-end to submit a new gate pass.
    """
    try:
        # 1. Get JSON data from the browser
        data = request.get_json()
        
        # 2. Input Validation (Checking for all required fields)
        required_fields = ["name", "department", "reason", "user_email"]
        if not all(field in data and data[field] for field in required_fields):
            return jsonify({
                "status": "error", 
                "message": "Missing one or more required fields (name, department, reason, email)."
            }), 400

        name = data["name"]
        department = data["department"]
        reason = data["reason"]
        user_email = data["user_email"]
        
        # 3. Process and Save Entry (Replacing the Tkinter data logic)
        global CURRENT_DATA
        
        # Find the next serial number based on the current data length
        s_no = len(CURRENT_DATA) + 1
        date_str = datetime.now().strftime("%Y-%m-%d")

        entry = {
            "s_no": s_no,
            "date": date_str,
            "name": name,
            "department": department,
            "reason": reason,
            "user_email": user_email
        }
        
        CURRENT_DATA.append(entry)
        save_data(CURRENT_DATA)

        # 4. Send Email
        email_success, email_message = send_email(name, user_email, department, reason, s_no)

        if not email_success:
             # Log the entry but return a failure to the user about the email
             return jsonify({
                 "status": "warning", 
                 "message": f"Gate pass submitted successfully, but email failed to send: {email_message}"
             }), 200 # Still return 200 because the core task (data entry) succeeded.

        # 5. Return Success
        return jsonify({
            "status": "success",
            "message": "Gate pass submitted and email notification sent!",
            "entry": entry
        }), 200

    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({
            "status": "error", 
            "message": f"An unexpected server error occurred. {str(e)}"
        }), 500

if __name__ == '__main__':
    # Run the server. Use debug=True for development.
    # When deploying, ensure debug is False and use a production WSGI server.
    print(f"Gatepass server starting. Loading data from {DATA_FILE}")
    app.run(debug=True, host='0.0.0.0')
