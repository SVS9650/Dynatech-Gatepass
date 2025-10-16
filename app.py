# --- Imports ---
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- Configuration ---
# 1. Determine the current directory robustly for cloud deployment
current_dir = Path(__file__).parent
DATA_FILE = "gatepass_data.json"
DATA_PATH = current_dir / DATA_FILE

# 2. Get secure credentials from environment variables set on Render
# These MUST be set correctly in the Render dashboard for the app to start!
EMAIL_USERNAME = os.environ.get("EMAIL_USERNAME", "YOUR_USERNAME_HERE")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "YOUR_PASSWORD_HERE")
SENDER_EMAIL = EMAIL_USERNAME

# 3. Define the email recipients for CC (e.g., security, manager)
CC_RECIPIENTS = [
    "manager@dynatechcontrols.in", 
    "security@dynatechcontrols.in"
]

# --- App Initialization ---
app = Flask(__name__)
CORS(app) # Enable CORS for front-end access

# --- Utility Functions ---

def load_data():
    """Loads existing gate pass data from the JSON file."""
    if not DATA_PATH.exists():
        return []
    try:
        with open(DATA_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: {DATA_FILE} is corrupted. Starting with empty data.")
        return []
    except Exception as e:
        print(f"Error loading data: {e}")
        return []

def save_data(data):
    """Saves the gate pass data back to the JSON file."""
    try:
        with open(DATA_PATH, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

def get_next_gatepass_id(data):
    """Calculates the next Gate Pass ID based on existing data."""
    if not data:
        return 1
    # Assuming the last item in the list has the highest ID
    return data[-1].get('id', 0) + 1

def send_gatepass_email(recipient_email, gatepass_data):
    """Sends the formatted Gate Pass email."""
    try:
        # 1. Email Content
        gatepass_id = gatepass_data['id']
        subject = f"Gate Pass Request #{gatepass_id} - {gatepass_data['name']}"
        
        # HTML body for better formatting
        body = f"""
        <html>
        <body>
            <p><strong>New Gate Pass Request Submitted</strong></p>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr><td><strong>Gate Pass ID:</strong></td><td>#{gatepass_id}</td></tr>
                <tr><td><strong>Name:</strong></td><td>{gatepass_data['name']}</td></tr>
                <tr><td><strong>Department:</strong></td><td>{gatepass_data['department']}</td></tr>
                <tr><td><strong>Requester Email:</strong></td><td>{gatepass_data['user_email']}</td></tr>
                <tr><td><strong>Timestamp:</strong></td><td>{gatepass_data['timestamp']}</td></tr>
                <tr><td colspan="2"><strong>Reason for Pass:</strong></td></tr>
                <tr><td colspan="2"><pre>{gatepass_data['reason']}</pre></td></tr>
            </table>
            <p><strong>Status: PENDING APPROVAL.</strong></p>
            <p>This is an automated notification. Please review the details.</p>
        </body>
        </html>
        """

        # 2. Construct Message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Cc'] = ", ".join(CC_RECIPIENTS)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        # 3. Connect and Send
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            # Send to the primary recipient AND all CCs
            recipients = [recipient_email] + CC_RECIPIENTS
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
        
        print(f"Gate Pass #{gatepass_id} Email sent successfully to {recipient_email} and CCs.")
        return True

    except Exception as e:
        print(f"Gate Pass #{gatepass_data.get('id', 'N/A')} Email sending failed: {e}")
        return False

# --- API Routes ---

@app.route('/api/gatepass', methods=['POST'])
def submit_gatepass():
    """Handles POST requests to submit a new gate pass."""
    try:
        data = request.get_json()
    except Exception:
        return jsonify({"status": "error", "message": "Invalid JSON format in request body."}), 400

    required_fields = ['name', 'department', 'reason', 'user_email']
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields."}), 400

    # Load existing data, calculate new ID, and create record
    gatepass_records = load_data()
    new_id = get_next_gatepass_id(gatepass_records)
    
    # CRITICAL FIX: Use datetime.now().isoformat() for robust timestamp generation
    gatepass_record = {
        "id": new_id,
        "name": data['name'],
        "department": data['department'],
        "user_email": data['user_email'],
        "reason": data['reason'],
        "timestamp": datetime.now().isoformat(), # Corrected for cloud environment
        "status": "pending"
    }

    # Add new record and save to file
    gatepass_records.append(gatepass_record)
    save_data(gatepass_records)
    
    # Attempt to send email
    email_success = send_gatepass_email(data['user_email'], gatepass_record)

    if email_success:
        return jsonify({
            "status": "success", 
            "message": f"Gate Pass #{new_id} submitted and email sent successfully.",
            "gatepass_id": new_id
        }), 200
    else:
        # Log the failure but still confirm data was saved
        return jsonify({
            "status": "warning", 
            "message": f"Gate Pass #{new_id} submitted and saved, but email notification failed. Check server logs.",
            "gatepass_id": new_id
        }), 200 # Still return 200 (OK) because data storage succeeded

# --- App Runner (For local testing) ---

if __name__ == '__main__':
    print("Gatepass server starting. Loading data from gatepass_data.json")
    # This line runs the app using Flask's built-in server for local development.
    # In a production environment (like Render), Gunicorn runs the app using the Procfile.
    app.run(debug=True, host='0.0.0.0', port=5000)
