import os
import io
import pymongo
import pandas as pd
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------
LOCAL_MONGO_URI = os.getenv("MONGO_URI")
LOCAL_DB = "domain_expires"
COLLECTIONS_TO_CHECK = [
    "apexfocusgroup_expires",
    # "newearnhaus_expires",
    "levelsurveys_expires"
]

# Email Settings
SMTP_SENDER = "your-email@example.com"
SMTP_RECEIVER = "your-email@example.com"
SMTP_CC = "dev-team@example.com"
SMTP_APP_PASSWORD = os.getenv("SMTP_PASS")  # Gmail App Password
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Query Settings
DAYS_AGO = 10
LIMIT = 2000

def main():
    print("\n========== IN-MEMORY EXPORT & EMAIL SCRIPT STARTING ==========\n")

    # 0. Validate Environment Variables
    if not LOCAL_MONGO_URI:
        raise ValueError("LOCAL_MONGO_URI not found in environment variables")
    if not SMTP_APP_PASSWORD:
        raise ValueError("SMTP_APP_PASSWORD not found in environment variables")

    # 1. Calculate Target Date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_AGO)
    print(f"Target Cutoff Date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # 2. Connect to Local MongoDB
    try:
        client = pymongo.MongoClient(LOCAL_MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')  
        db = client[LOCAL_DB]
        print("Connected to MongoDB successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to connect to MongoDB: {e}")
        return

    sheets_data = {}

    # 3. Fetch Data
    for coll_name in COLLECTIONS_TO_CHECK:
        print(f"Querying {coll_name}...")
        try:
            # Look for records newer than the cutoff date (matches Studio 3T output)
            pipeline = {"gpost_date": {"$gt": cutoff_date}}
            
            cursor = db[coll_name].find(pipeline).limit(LIMIT)
            docs = list(cursor)

            if not docs:
                print(f"   -> No records found newer than {DAYS_AGO} days in '{coll_name}'. Skipping sheet.")
                continue

            print(f"   -> Found {len(docs)} records for '{coll_name}'.")

            df = pd.DataFrame(docs)

            if '_id' in df.columns:
                df['_id'] = df['_id'].astype(str)

            for col in df.select_dtypes(include=['datetimetz']).columns:
                df[col] = df[col].dt.tz_localize(None)

            sheet_name = coll_name.replace("_expires", "")
            sheets_data[sheet_name] = df

        except Exception as e:
            print(f"   -> ERROR processing collection '{coll_name}': {e}")
            continue

    # 4. Generate Excel File in Memory
    if not sheets_data:
        print("\nNo data found across any collections matching the criteria. Exiting without sending email.")
        client.close()
        return

    now = datetime.now()
    excel_filename = f"DC_Expires_{now.strftime('%b')}_{now.strftime('%d')}.xlsx"
    print(f"\nWriting data to in-memory buffer for {excel_filename}...")

    excel_buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            for sheet_name, df in sheets_data.items():
                df.to_excel(writer, index=False, sheet_name=sheet_name)
        print("In-memory Excel file generated successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to generate Excel file: {e}")
        client.close()
        return

    # 5. Prepare and Send Email
    print("\nPreparing to send email...")

    msg = MIMEMultipart()
    msg['From'] = SMTP_SENDER
    msg['To'] = SMTP_RECEIVER
    msg['Cc'] = SMTP_CC
    msg['Subject'] = f"Automated Expired Jobs Report - {now.strftime('%Y-%m-%d')}"

    body = (
        f"Hi Team,\n\n"
        f"Please find attached the jobs report for {now.strftime('%Y-%m-%d')}.\n\n"
        f"Criteria applied:\n"
        f"- gpost_date > {cutoff_date.strftime('%Y-%m-%d')}\n"
        f"- Limit: {LIMIT} records per client\n\n"
        f"Clients included in this attachment:\n"
    )
    
    for sheet in sheets_data.keys():
        body += f"- {sheet}\n"

    body += "\nBest regards,\nAutomated System"
    msg.attach(MIMEText(body, 'plain'))

    try:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(excel_buffer.getvalue())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename={excel_filename}")
        msg.attach(part)
    except Exception as e:
        print(f"ERROR attaching file to email: {e}")
        excel_buffer.close()
        client.close()
        return

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls() 
            server.login(SMTP_SENDER, SMTP_APP_PASSWORD)
            
            recipients = [SMTP_RECEIVER, SMTP_CC]
            server.send_message(msg, from_addr=SMTP_SENDER, to_addrs=recipients)
            
        print("Email sent successfully!")
    except smtplib.SMTPAuthenticationError:
        print("CRITICAL ERROR: SMTP Authentication failed. Check your App Password.")
    except Exception as e:
        print(f"CRITICAL ERROR sending email: {e}")
    finally:
        excel_buffer.close()
        client.close()

    print("\n========== SCRIPT COMPLETE ==========\n")


if __name__ == "__main__":
    main()