import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date, timedelta
import time
import bcrypt
import random
from io import BytesIO, StringIO
import base64
import json

# ------------------------------
# App Configuration
# ------------------------------
st.set_page_config(
    page_title="Student Council Management",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# Google Sheets Connection
# ------------------------------
@st.cache_resource
def connect_gsheets():
    """Establish connection to Google Sheets and verify required worksheets"""
    try:
        # Retrieve secrets from Streamlit configuration
        secrets = st.secrets["google_sheets"]
        
        # Create credentials dictionary
        creds_dict = {
            "type": "service_account",
            "client_email": secrets["service_account_email"],
            "private_key_id": secrets["private_key_id"],
            "private_key": secrets["private_key"].replace("\\n", "\n"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{secrets['service_account_email']}"
        }
        
        # Authenticate and connect to Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(credentials)
        
        # Open the specified Google Sheet
        sheet = client.open_by_url(secrets["sheet_url"])
        
        # Define all required worksheets
        required_worksheets = [
            "users", "attendance", "credit_data", "reward_data",
            "scheduled_events", "occasional_events", "money_data",
            "calendar_events", "announcements", "groups",
            "group_leaders", "group_earnings", "reimbursement_requests",
            "event_approval_requests", "system_config"
        ]
        
        # Create any missing worksheets
        existing_worksheets = [ws.title for ws in sheet.worksheets()]
        for ws_name in required_worksheets:
            if ws_name not in existing_worksheets:
                sheet.add_worksheet(title=ws_name, rows="2000", cols="50")
                with st.spinner(f"Creating required worksheet: {ws_name}"):
                    time.sleep(1)
        
        return sheet
    
    except Exception as e:
        st.error(f"Connection to Google Sheets failed: {str(e)}")
        return None

# ------------------------------
# Session State Initialization
# ------------------------------
def initialize_session_state():
    """Initialize all required session state variables with empty values"""
    # User session variables
    if "user" not in st.session_state:
        st.session_state.user = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0
    if "current_group" not in st.session_state:
        st.session_state.current_group = None
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()
    
    # UI state variables
    if "sidebar_expanded" not in st.session_state:
        st.session_state.sidebar_expanded = True
    if "show_help" not in st.session_state:
        st.session_state.show_help = False
    if "current_calendar_month" not in st.session_state:
        st.session_state.current_calendar_month = (date.today().year, date.today().month)
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Calendar"
    
    # Data storage variables - all initialized as empty
    if "users" not in st.session_state:
        st.session_state.users = {}
    if "attendance" not in st.session_state:
        st.session_state.attendance = pd.DataFrame(columns=["Name"])
    if "credit_data" not in st.session_state:
        st.session_state.credit_data = pd.DataFrame(columns=["Name", "Total_Credits", "RedeemedCredits"])
    if "reward_data" not in st.session_state:
        st.session_state.reward_data = pd.DataFrame(columns=["Reward", "Cost", "Stock"])
    if "scheduled_events" not in st.session_state:
        st.session_state.scheduled_events = pd.DataFrame(columns=[
            "Event Name", "Funds Per Event", "Frequency Per Month", "Total Funds", "Responsible Group"
        ])
    if "occasional_events" not in st.session_state:
        st.session_state.occasional_events = pd.DataFrame(columns=[
            "Event Name", "Total Funds Raised", "Cost", "Staff Required",
            "Preparation Time (Days)", "Rating", "Responsible Group"
        ])
    if "money_data" not in st.session_state:
        st.session_state.money_data = pd.DataFrame(columns=[
            "Amount", "Description", "Date", "Handled By", "Group"
        ])
    if "calendar_events" not in st.session_state:
        st.session_state.calendar_events = {}
    if "announcements" not in st.session_state:
        st.session_state.announcements = []
    if "meeting_names" not in st.session_state:
        st.session_state.meeting_names = []
    
    # Group management variables
    if "groups" not in st.session_state:
        st.session_state.groups = {
            "G1": [], "G2": [], "G3": [], "G4": [],
            "G5": [], "G6": [], "G7": [], "G8": []
        }
    if "group_leaders" not in st.session_state:
        st.session_state.group_leaders = {
            "G1": "", "G2": "", "G3": "", "G4": "",
            "G5": "", "G6": "", "G7": "", "G8": ""
        }
    if "group_codes" not in st.session_state:
        st.session_state.group_codes = {
            "G1": "", "G2": "", "G3": "", "G4": "",
            "G5": "", "G6": "", "G7": "", "G8": ""
        }
    if "group_earnings" not in st.session_state:
        st.session_state.group_earnings = pd.DataFrame(columns=[
            "Group", "Date", "Amount", "Description", "Verified"
        ])
    
    # Request system variables
    if "reimbursement_requests" not in st.session_state:
        st.session_state.reimbursement_requests = pd.DataFrame(columns=[
            "Request ID", "Group", "Requester", "Amount", "Purpose",
            "Date Submitted", "Status", "Admin Notes"
        ])
    if "event_approval_requests" not in st.session_state:
        st.session_state.event_approval_requests = pd.DataFrame(columns=[
            "Request ID", "Group", "Requester", "Event Name", "Description",
            "Proposed Date", "Budget", "File Reference", "Date Submitted",
            "Status", "Admin Notes"
        ])
    
    # Configuration variables
    if "system_config" not in st.session_state:
        st.session_state.system_config = {
            "allow_signups": True,
            "meeting_reminders": True,
            "require_admin_approval": True
        }

# ------------------------------
# Data Management Functions
# ------------------------------
def save_all_data(sheet):
    """Save all application data to Google Sheets"""
    if not sheet:
        return False, "No valid Google Sheet connection"
    
    try:
        # 1. Save user data
        users_ws = sheet.worksheet("users")
        users_data = [["username", "password_hash", "role", "group", "created_at", "last_login"]]
        for username, details in st.session_state.users.items():
            users_data.append([
                username,
                details["password_hash"],
                details["role"],
                details.get("group", ""),
                details["created_at"],
                details.get("last_login", "")
            ])
        users_ws.clear()
        users_ws.update(users_data)
        
        # 2. Save attendance records
        attendance_ws = sheet.worksheet("attendance")
        attendance_data = [st.session_state.attendance.columns.tolist()]
        for _, row in st.session_state.attendance.iterrows():
            attendance_data.append(row.tolist())
        attendance_ws.clear()
        attendance_ws.update(attendance_data)
        
        # 3. Save credit data
        credit_ws = sheet.worksheet("credit_data")
        credit_data = [st.session_state.credit_data.columns.tolist()]
        for _, row in st.session_state.credit_data.iterrows():
            credit_data.append(row.tolist())
        credit_ws.clear()
        credit_ws.update(credit_data)
        
        # 4. Save reward data
        reward_ws = sheet.worksheet("reward_data")
        reward_data = [st.session_state.reward_data.columns.tolist()]
        for _, row in st.session_state.reward_data.iterrows():
            reward_data.append(row.tolist())
        reward_ws.clear()
        reward_ws.update(reward_data)
        
        # 5. Save scheduled events
        scheduled_ws = sheet.worksheet("scheduled_events")
        scheduled_data = [st.session_state.scheduled_events.columns.tolist()]
        for _, row in st.session_state.scheduled_events.iterrows():
            scheduled_data.append(row.tolist())
        scheduled_ws.clear()
        scheduled_ws.update(scheduled_data)
        
        # 6. Save occasional events
        occasional_ws = sheet.worksheet("occasional_events")
        occasional_data = [st.session_state.occasional_events.columns.tolist()]
        for _, row in st.session_state.occasional_events.iterrows():
            occasional_data.append(row.tolist())
        occasional_ws.clear()
        occasional_ws.update(occasional_data)
        
        # 7. Save financial data
        money_ws = sheet.worksheet("money_data")
        money_data = [st.session_state.money_data.columns.tolist()]
        for _, row in st.session_state.money_data.iterrows():
            money_data.append(row.tolist())
        money_ws.clear()
        money_ws.update(money_data)
        
        # 8. Save calendar events
        calendar_ws = sheet.worksheet("calendar_events")
        calendar_data = [["date", "event", "group"]]
        for date_str, event_info in st.session_state.calendar_events.items():
            calendar_data.append([date_str, event_info["event"], event_info["group"]])
        calendar_ws.clear()
        calendar_ws.update(calendar_data)
        
        # 9. Save announcements
        announcements_ws = sheet.worksheet("announcements")
        announcements_data = [["title", "content", "date", "author", "group"]]
        for ann in st.session_state.announcements:
            announcements_data.append([
                ann["title"], ann["content"], ann["date"], ann["author"], ann.get("group", "")
            ])
        announcements_ws.clear()
        announcements_ws.update(announcements_data)
        
        # 10. Save group information
        groups_ws = sheet.worksheet("groups")
        groups_data = [["group_name", "members", "code"]]
        for group, members in st.session_state.groups.items():
            groups_data.append([
                group,
                ", ".join(members),
                st.session_state.group_codes.get(group, "")
            ])
        groups_ws.clear()
        groups_ws.update(groups_data)
        
        # 11. Save group leaders
        leaders_ws = sheet.worksheet("group_leaders")
        leaders_data = [["group", "leader"]]
        for group, leader in st.session_state.group_leaders.items():
            leaders_data.append([group, leader])
        leaders_ws.clear()
        leaders_ws.update(leaders_data)
        
        # 12. Save group earnings
        earnings_ws = sheet.worksheet("group_earnings")
        earnings_data = [st.session_state.group_earnings.columns.tolist()]
        for _, row in st.session_state.group_earnings.iterrows():
            earnings_data.append(row.tolist())
        earnings_ws.clear()
        earnings_ws.update(earnings_data)
        
        # 13. Save reimbursement requests
        reimburse_ws = sheet.worksheet("reimbursement_requests")
        reimburse_data = [st.session_state.reimbursement_requests.columns.tolist()]
        for _, row in st.session_state.reimbursement_requests.iterrows():
            reimburse_data.append(row.tolist())
        reimburse_ws.clear()
        reimburse_ws.update(reimburse_data)
        
        # 14. Save event approval requests
        event_ws = sheet.worksheet("event_approval_requests")
        event_data = [st.session_state.event_approval_requests.columns.tolist()]
        for _, row in st.session_state.event_approval_requests.iterrows():
            event_data.append(row.tolist())
        event_ws.clear()
        event_ws.update(event_data)
        
        # 15. Save system configuration
        config_ws = sheet.worksheet("system_config")
        config_data = [["setting", "value"]]
        for key, value in st.session_state.system_config.items():
            config_data.append([key, str(value)])
        config_ws.clear()
        config_ws.update(config_data)
        
        return True, "Data successfully saved to Google Sheets"
    
    except Exception as e:
        return False, f"Error saving data: {str(e)}"

def load_all_data(sheet):
    """Load all application data from Google Sheets"""
    if not sheet:
        return False, "No valid Google Sheet connection"
    
    try:
        # 1. Load user data
        users_ws = sheet.worksheet("users")
        users_records = users_ws.get_all_records()
        st.session_state.users = {}
        for record in users_records:
            if record["username"]:
                st.session_state.users[record["username"]] = {
                    "password_hash": record["password_hash"],
                    "role": record["role"],
                    "group": record["group"],
                    "created_at": record["created_at"],
                    "last_login": record["last_login"]
                }
        
        # 2. Load attendance records
        attendance_ws = sheet.worksheet("attendance")
        attendance_records = attendance_ws.get_all_records()
        st.session_state.attendance = pd.DataFrame(attendance_records)
        # Extract meeting names (all columns except "Name")
        st.session_state.meeting_names = [
            col for col in st.session_state.attendance.columns 
            if col != "Name" and st.session_state.attendance[col].dtype != 'object'
        ]
        
        # 3. Load credit data
        credit_ws = sheet.worksheet("credit_data")
        credit_records = credit_ws.get_all_records()
        st.session_state.credit_data = pd.DataFrame(credit_records)
        
        # 4. Load reward data
        reward_ws = sheet.worksheet("reward_data")
        reward_records = reward_ws.get_all_records()
        st.session_state.reward_data = pd.DataFrame(reward_records)
        
        # 5. Load scheduled events
        scheduled_ws = sheet.worksheet("scheduled_events")
        scheduled_records = scheduled_ws.get_all_records()
        st.session_state.scheduled_events = pd.DataFrame(scheduled_records)
        
        # 6. Load occasional events
        occasional_ws = sheet.worksheet("occasional_events")
        occasional_records = occasional_ws.get_all_records()
        st.session_state.occasional_events = pd.DataFrame(occasional_records)
        
        # 7. Load financial data
        money_ws = sheet.worksheet("money_data")
        money_records = money_ws.get_all_records()
        st.session_state.money_data = pd.DataFrame(money_records)
        
        # 8. Load calendar events
        calendar_ws = sheet.worksheet("calendar_events")
        calendar_records = calendar_ws.get_all_records()
        st.session_state.calendar_events = {}
        for record in calendar_records:
            if record["date"] and record["event"]:
                st.session_state.calendar_events[record["date"]] = {
                    "event": record["event"],
                    "group": record["group"]
                }
        
        # 9. Load announcements
        announcements_ws = sheet.worksheet("announcements")
        announcements_records = announcements_ws.get_all_records()
        st.session_state.announcements = []
        for record in announcements_records:
            if record["title"] and record["content"]:
                st.session_state.announcements.append({
                    "title": record["title"],
                    "content": record["content"],
                    "date": record["date"],
                    "author": record["author"],
                    "group": record["group"]
                })
        
        # 10. Load group information
        groups_ws = sheet.worksheet("groups")
        groups_records = groups_ws.get_all_records()
        groups = {f"G{i}": [] for i in range(1, 9)}
        group_codes = {f"G{i}": "" for i in range(1, 9)}
        
        for record in groups_records:
            if record["group_name"] in groups:
                groups[record["group_name"]] = record["members"].split(", ") if record["members"] else []
                group_codes[record["group_name"]] = record["code"] if record["code"] else ""
        
        st.session_state.groups = groups
        st.session_state.group_codes = group_codes
        
        # 11. Load group leaders
        leaders_ws = sheet.worksheet("group_leaders")
        leaders_records = leaders_ws.get_all_records()
        leaders = {f"G{i}": "" for i in range(1, 9)}
        for record in leaders_records:
            if record["group"] in leaders:
                leaders[record["group"]] = record["leader"]
        st.session_state.group_leaders = leaders
        
        # 12. Load group earnings
        earnings_ws = sheet.worksheet("group_earnings")
        earnings_records = earnings_ws.get_all_records()
        st.session_state.group_earnings = pd.DataFrame(earnings_records)
        
        # 13. Load reimbursement requests
        reimburse_ws = sheet.worksheet("reimbursement_requests")
        reimburse_records = reimburse_ws.get_all_records()
        st.session_state.reimbursement_requests = pd.DataFrame(reimburse_records)
        
        # 14. Load event approval requests
        event_ws = sheet.worksheet("event_approval_requests")
        event_records = event_ws.get_all_records()
        st.session_state.event_approval_requests = pd.DataFrame(event_records)
        
        # 15. Load system configuration
        config_ws = sheet.worksheet("system_config")
        config_records = config_ws.get_all_records()
        config = {}
        for record in config_records:
            if record["setting"]:
                value = record["value"]
                # Convert string values back to appropriate types
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.isdigit():
                    value = int(value)
                config[record["setting"]] = value
        st.session_state.system_config.update(config)
        
        return True, "Data successfully loaded from Google Sheets"
    
    except Exception as e:
        return False, f"Error loading data: {str(e)}"

# ------------------------------
# User Authentication Functions
# ------------------------------
def hash_password(password):
    """Hash a password using bcrypt for secure storage"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against its hashed version"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_new_user(username, password, group_code):
    """Create a new user account with group assignment via code"""
    # Validate group code
    user_group = None
    for group, code in st.session_state.group_codes.items():
        if code and group_code == code:
            user_group = group
            break
    
    if not user_group:
        return False, "Invalid group code. Please check and try again."
    
    # Check if username already exists
    if username in st.session_state.users:
        return False, "Username already exists. Please choose another."
    
    # Validate password strength
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    
    # Create new user record
    current_time = datetime.now().isoformat()
    st.session_state.users[username] = {
        "password_hash": hash_password(password),
        "role": "member",
        "group": user_group,
        "created_at": current_time,
        "last_login": ""
    }
    
    # Add user to their group
    if username not in st.session_state.groups[user_group]:
        st.session_state.groups[user_group].append(username)
    
    # Add user to attendance and credit records if not already present
    if username not in st.session_state.attendance["Name"].values:
        new_attendance_row = pd.DataFrame([[username] + [False]*len(st.session_state.meeting_names)],
                                         columns=["Name"] + st.session_state.meeting_names)
        st.session_state.attendance = pd.concat([st.session_state.attendance, new_attendance_row], ignore_index=True)
    
    if username not in st.session_state.credit_data["Name"].values:
        new_credit_row = pd.DataFrame([[username, 0, 0]],
                                     columns=["Name", "Total_Credits", "RedeemedCredits"])
        st.session_state.credit_data = pd.concat([st.session_state.credit_data, new_credit_row], ignore_index=True)
    
    return True, f"Account created successfully. You are assigned to {user_group}."

# ------------------------------
# Group Management Functions
# ------------------------------
def move_user_to_group(username, current_group, target_group):
    """Move a user from their current group to a different group"""
    # Validate input
    if username not in st.session_state.users:
        return False, f"User {username} not found."
    
    if current_group not in st.session_state.groups:
        return False, f"Current group {current_group} is invalid."
    
    if target_group not in st.session_state.groups:
        return False, f"Target group {target_group} is invalid."
    
    if username not in st.session_state.groups[current_group]:
        return False, f"User {username} is not in {current_group}."
    
    # Remove from current group
    st.session_state.groups[current_group].remove(username)
    
    # Add to target group
    if username not in st.session_state.groups[target_group]:
        st.session_state.groups[target_group].append(username)
    
    # Update user record
    st.session_state.users[username]["group"] = target_group
    
    return True, f"User {username} moved from {current_group} to {target_group}."

def assign_group_leader(group, username):
    """Assign a user as the leader of a group"""
    # Validate input
    if group not in st.session_state.groups:
        return False, f"Group {group} is invalid."
    
    if username not in st.session_state.users:
        return False, f"User {username} not found."
    
    if username not in st.session_state.groups[group]:
        return False, f"User {username} is not a member of {group}."
    
    # Update group leader
    st.session_state.group_leaders[group] = username
    
    return True, f"User {username} assigned as leader of {group}."

def record_group_earnings(group, amount, description):
    """Record earnings for a specific group"""
    # Validate input
    if group not in st.session_state.groups:
        return False, f"Group {group} is invalid."
    
    if amount <= 0:
        return False, "Earnings amount must be greater than zero."
    
    if not description:
        return False, "Please provide a description for the earnings."
    
    # Create new earnings record
    new_entry = pd.DataFrame([{
        "Group": group,
        "Date": date.today().strftime("%Y-%m-%d"),
        "Amount": amount,
        "Description": description,
        "Verified": "Pending"
    }])
    
    # Add to earnings data
    st.session_state.group_earnings = pd.concat(
        [st.session_state.group_earnings, new_entry], ignore_index=True
    )
    
    return True, "Earnings recorded successfully. Awaiting admin verification."

# ------------------------------
# Request Management Functions
# ------------------------------
def submit_reimbursement_request(group, requester, amount, purpose):
    """Submit a new reimbursement request"""
    # Validate input
    if group not in st.session_state.groups:
        return False, f"Group {group} is invalid."
    
    if requester not in st.session_state.users:
        return False, f"Requester {requester} not found."
    
    if amount <= 0:
        return False, "Reimbursement amount must be greater than zero."
    
    if not purpose:
        return False, "Please provide a purpose for the reimbursement."
    
    # Generate request ID
    request_id = f"REIMB-{random.randint(1000, 9999)}-{datetime.now().strftime('%m%d')}"
    
    # Create new request
    new_request = pd.DataFrame([{
        "Request ID": request_id,
        "Group": group,
        "Requester": requester,
        "Amount": amount,
        "Purpose": purpose,
        "Date Submitted": datetime.now().isoformat(),
        "Status": "Pending",
        "Admin Notes": ""
    }])
    
    # Add to requests
    st.session_state.reimbursement_requests = pd.concat(
        [st.session_state.reimbursement_requests, new_request], ignore_index=True
    )
    
    return True, f"Reimbursement request submitted. Request ID: {request_id}"

def submit_event_approval_request(group, requester, event_name, description, 
                                 proposed_date, budget, file_content):
    """Submit a new event approval request with file attachment"""
    # Validate input
    if group not in st.session_state.groups:
        return False, f"Group {group} is invalid."
    
    if requester not in st.session_state.users:
        return False, f"Requester {requester} not found."
    
    if not event_name:
        return False, "Please provide an event name."
    
    if not description:
        return False, "Please provide an event description."
    
    if budget < 0:
        return False, "Budget cannot be negative."
    
    if not file_content:
        return False, "Please upload a proposal document."
    
    # Generate request ID
    request_id = f"EVENT-{random.randint(1000, 9999)}-{datetime.now().strftime('%m%d')}"
    
    # Encode file content for storage
    encoded_file = base64.b64encode(file_content).decode('utf-8')
    
    # Create new request
    new_request = pd.DataFrame([{
        "Request ID": request_id,
        "Group": group,
        "Requester": requester,
        "Event Name": event_name,
        "Description": description,
        "Proposed Date": proposed_date.strftime("%Y-%m-%d"),
        "Budget": budget,
        "File Reference": encoded_file,
        "Date Submitted": datetime.now().isoformat(),
        "Status": "Pending",
        "Admin Notes": ""
    }])
    
    # Add to requests
    st.session_state.event_approval_requests = pd.concat(
        [st.session_state.event_approval_requests, new_request], ignore_index=True
    )
    
    return True, f"Event approval request submitted. Request ID: {request_id}"

def process_request(request_type, request_id, new_status, admin_notes=""):
    """Process a request by updating its status"""
    # Validate input
    valid_statuses = ["Pending", "Approved", "Denied"]
    if new_status not in valid_statuses:
        return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
    
    # Process reimbursement request
    if request_type == "reimbursement":
        request_index = st.session_state.reimbursement_requests.index[
            st.session_state.reimbursement_requests["Request ID"] == request_id
        ]
        
        if len(request_index) == 0:
            return False, f"Reimbursement request {request_id} not found."
        
        # Update request status
        st.session_state.reimbursement_requests.at[request_index[0], "Status"] = new_status
        st.session_state.reimbursement_requests.at[request_index[0], "Admin Notes"] = admin_notes
        
        # If approved, record the expense
        if new_status == "Approved":
            request_data = st.session_state.reimbursement_requests.iloc[request_index[0]]
            new_expense = pd.DataFrame([{
                "Amount": -float(request_data["Amount"]),  # Negative for expenses
                "Description": f"Reimbursement: {request_data['Purpose']}",
                "Date": date.today().strftime("%Y-%m-%d"),
                "Handled By": st.session_state.user,
                "Group": request_data["Group"]
            }])
            
            st.session_state.money_data = pd.concat(
                [st.session_state.money_data, new_expense], ignore_index=True
            )
    
    # Process event approval request
    elif request_type == "event":
        request_index = st.session_state.event_approval_requests.index[
            st.session_state.event_approval_requests["Request ID"] == request_id
        ]
        
        if len(request_index) == 0:
            return False, f"Event request {request_id} not found."
        
        # Update request status
        st.session_state.event_approval_requests.at[request_index[0], "Status"] = new_status
        st.session_state.event_approval_requests.at[request_index[0], "Admin Notes"] = admin_notes
        
        # If approved, add to calendar
        if new_status == "Approved":
            request_data = st.session_state.event_approval_requests.iloc[request_index[0]]
            st.session_state.calendar_events[request_data["Proposed Date"]] = {
                "event": request_data["Event Name"],
                "group": request_data["Group"]
            }
    
    else:
        return False, "Invalid request type. Must be 'reimbursement' or 'event'."
    
    return True, f"Request {request_id} updated to {new_status}."

# ------------------------------
# UI Rendering Functions
# ------------------------------
def render_login_signup():
    """Render login and signup forms for user authentication"""
    st.title("Student Council Management System")
    
    # Create tabs for login and signup
    login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
    
    with login_tab:
        st.subheader("Login to Your Account")
        
        # Show error for too many login attempts
        if st.session_state.login_attempts >= 3:
            st.error("Too many failed login attempts. Please try again later.")
            return False
        
        # Login form
        username = st.text_input("Username", key="login_username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
        
        # Login buttons
        col_login, col_clear = st.columns(2)
        with col_login:
            login_button = st.button("Login", use_container_width=True)
        
        with col_clear:
            if st.button("Clear", use_container_width=True):
                st.session_state.login_attempts = 0
                st.experimental_rerun()
        
        # Process login
        if login_button:
            if not username or not password:
                st.error("Please enter both username and password.")
                return False
            
            # Check creator credentials from secrets
            creator_creds = st.secrets.get("creator", {})
            if username == creator_creds.get("username") and password == creator_creds.get("password"):
                st.session_state.user = username
                st.session_state.role = "creator"
                st.session_state.current_group = ""
                st.success("Successfully logged in as Creator.")
                return True
            
            # Check admin credentials from secrets
            admin_creds = st.secrets.get("admins", {})
            if username in admin_creds and password == admin_creds[username]:
                # Create admin user if not exists
                if username not in st.session_state.users:
                    current_time = datetime.now().isoformat()
                    st.session_state.users[username] = {
                        "password_hash": hash_password(password),
                        "role": "admin",
                        "group": "",
                        "created_at": current_time,
                        "last_login": ""
                    }
                
                st.session_state.user = username
                st.session_state.role = "admin"
                st.session_state.current_group = ""
                st.success("Successfully logged in as Admin.")
                return True
            
            # Check regular users
            if username in st.session_state.users:
                user_data = st.session_state.users[username]
                if verify_password(password, user_data["password_hash"]):
                    # Update last login time
                    st.session_state.users[username]["last_login"] = datetime.now().isoformat()
                    
                    # Set session variables
                    st.session_state.user = username
                    st.session_state.role = user_data["role"]
                    st.session_state.current_group = user_data["group"]
                    
                    st.success(f"Welcome back, {username}!")
                    return True
                else:
                    st.session_state.login_attempts += 1
                    st.error("Incorrect password. Please try again.")
            else:
                st.session_state.login_attempts += 1
                st.error("Username not found. Please check your username or sign up for a new account.")
        
        return False
    
    with signup_tab:
        # Check if signups are allowed
        if not st.session_state.system_config.get("allow_signups", True):
            st.info("New account signups are currently disabled. Please contact an administrator.")
            return False
        
        st.subheader("Create a New Account")
        
        # Signup form
        new_username = st.text_input("Choose a Username", key="signup_username", placeholder="Enter your desired username")
        new_password = st.text_input("Create a Password", type="password", key="signup_password", placeholder="Create a password (min. 6 characters)")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password", placeholder="Re-enter your password")
        group_code = st.text_input("Group Code", key="group_code", placeholder="Enter your group code (G1-G8)")
        
        # Create account button
        if st.button("Create Account", key="create_account_button"):
            # Validate form
            if not new_username or not new_password or not confirm_password or not group_code:
                st.error("Please fill in all fields.")
                return False
            
            if new_password != confirm_password:
                st.error("Passwords do not match. Please try again.")
                return False
            
            # Create user
            success, message = create_new_user(new_username, new_password, group_code)
            if success:
                # Save new user to Google Sheets
                sheet = connect_gsheets()
                if sheet:
                    save_success, save_msg = save_all_data(sheet)
                    if not save_success:
                        st.warning(f"Account created but unable to save to server: {save_msg}")
                
                st.success(f"{message} You can now log in.")
            else:
                st.error(message)
    
    return False

def render_calendar_tab():
    """Render the Calendar tab content"""
    st.subheader("Event Calendar")
    
    # Get current month and year from session state
    current_year, current_month = st.session_state.current_calendar_month
    
    # Navigation controls
    col_prev, col_title, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Previous Month"):
            new_month = current_month - 1 if current_month > 1 else 12
            new_year = current_year - 1 if current_month == 1 else current_year
            st.session_state.current_calendar_month = (new_year, new_month)
            st.experimental_rerun()
    
    with col_title:
        st.write(f"**{datetime(current_year, current_month, 1).strftime('%B %Y')}**")
    
    with col_next:
        if st.button("Next Month ▶"):
            new_month = current_month + 1 if current_month < 12 else 1
            new_year = current_year + 1 if current_month == 12 else current_year
            st.session_state.current_calendar_month = (new_year, new_month)
            st.experimental_rerun()
    
    # Calculate calendar days
    first_day = date(current_year, current_month, 1)
    last_day = (date(current_year, current_month + 1, 1) - timedelta(days=1)) if current_month < 12 else date(current_year, 12, 31)
    days_in_month = (last_day - first_day).days + 1
    
    # Get first day of month as weekday (0=Monday)
    first_day_weekday = first_day.weekday()
    
    # Create list of dates for calendar
    calendar_dates = []
    
    # Add days from previous month
    for i in range(first_day_weekday):
        prev_date = first_day - timedelta(days=first_day_weekday - i)
        calendar_dates.append((prev_date, False))
    
    # Add days from current month
    for i in range(days_in_month):
        current_date = first_day + timedelta(days=i)
        calendar_dates.append((current_date, True))
    
    # Add days from next month to fill the week
    remaining_days = 7 - (len(calendar_dates) % 7)
    if remaining_days < 7:
        for i in range(remaining_days):
            next_date = last_day + timedelta(days=i + 1)
            calendar_dates.append((next_date, False))
    
    # Display calendar headers
    weekday_headers = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    header_cols = st.columns(7)
    for col, header in zip(header_cols, weekday_headers):
        col.write(f"**{header[:3]}**")  # Show first 3 letters
    
    # Display calendar grid
    for week_start in range(0, len(calendar_dates), 7):
        week_dates = calendar_dates[week_start:week_start + 7]
        day_cols = st.columns(7)
        
        for col, (current_date, is_current_month) in zip(day_cols, week_dates):
            date_str = current_date.strftime("%Y-%m-%d")
            day_number = current_date.day
            
            # Style for current month vs other months
            if not is_current_month:
                style = "color: #999; background-color: #f9f9f9;"
            else:
                style = "color: #000; background-color: #ffffff;"
            
            # Highlight today's date
            if current_date == date.today():
                style += "border: 2px solid #2196F3; font-weight: bold;"
            
            # Add event information if available
            event_text = ""
            if date_str in st.session_state.calendar_events:
                event_info = st.session_state.calendar_events[date_str]
                event_text = f"\n{event_info['event'][:15]}"
                if len(event_info['event']) > 15:
                    event_text += "..."
                if event_info['group']:
                    event_text += f" ({event_info['group']})"
            
            # Display the day with styling
            col.markdown(
                f'<div style="padding: 8px; border-radius: 4px; {style}">{day_number}{event_text}</div>',
                unsafe_allow_html=True
            )
    
    # Add new event form (admin and group leaders only)
    if is_admin() or is_group_leader(st.session_state.current_group):
        with st.expander("Add New Calendar Event", expanded=False):
            event_date = st.date_input("Event Date")
            event_name = st.text_input("Event Name")
            event_group = st.selectbox("Responsible Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
            
            if st.button("Save Event"):
                if not event_name:
                    st.error("Please enter an event name.")
                else:
                    date_str = event_date.strftime("%Y-%m-%d")
                    st.session_state.calendar_events[date_str] = {
                        "event": event_name,
                        "group": event_group
                    }
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    if sheet:
                        success, msg = save_all_data(sheet)
                        if success:
                            st.success("Event added to calendar.")
                        else:
                            st.error(f"Failed to save event: {msg}")

def render_attendance_tab():
    """Render the Attendance tab content"""
    st.subheader("Meeting Attendance Records")
    
    # Display attendance data
    if not st.session_state.attendance.empty:
        st.dataframe(st.session_state.attendance)
    else:
        st.info("No attendance records available yet. Add your first meeting to begin tracking attendance.")
    
    # Add new meeting form (admin only)
    if is_admin():
        with st.expander("Manage Meetings and Attendance", expanded=False):
            st.subheader("Add New Meeting")
            new_meeting_name = st.text_input("New Meeting Name")
            
            if st.button("Create Meeting Record"):
                if not new_meeting_name:
                    st.error("Please enter a meeting name.")
                elif new_meeting_name in st.session_state.meeting_names:
                    st.error("A meeting with this name already exists.")
                else:
                    # Add new column to attendance dataframe
                    st.session_state.attendance[new_meeting_name] = False
                    st.session_state.meeting_names.append(new_meeting_name)
                    
                    # Save changes
                    sheet = connect_gsheets()
                    if sheet:
                        success, msg = save_all_data(sheet)
                        if success:
                            st.success(f"Added new meeting: {new_meeting_name}")
                            st.experimental_rerun()
                        else:
                            st.error(f"Failed to save meeting: {msg}")
            
            # Update attendance for existing meeting
            if st.session_state.meeting_names:
                st.subheader("Update Attendance")
                selected_meeting = st.selectbox("Select Meeting", st.session_state.meeting_names)
                
                if selected_meeting:
                    st.write(f"Update attendance for: {selected_meeting}")
                    attendance_updated = False
                    
                    # Display checkboxes for each member
                    for idx, row in st.session_state.attendance.iterrows():
                        member_name = row["Name"]
                        current_status = row[selected_meeting]
                        
                        # Create unique key for each checkbox
                        checkbox_key = f"attendance_{selected_meeting}_{idx}"
                        new_status = st.checkbox(member_name, value=current_status, key=checkbox_key)
                        
                        # Update if status changed
                        if new_status != current_status:
                            st.session_state.attendance.at[idx, selected_meeting] = new_status
                            attendance_updated = True
                    
                    # Save changes button
                    if attendance_updated:
                        if st.button("Save Attendance Changes"):
                            sheet = connect_gsheets()
                            if sheet:
                                success, msg = save_all_data(sheet)
                                if success:
                                    st.success("Attendance records updated.")
                                else:
                                    st.error(f"Failed to save changes: {msg}")
    
    # Attendance statistics
    if st.session_state.meeting_names and not st.session_state.attendance.empty:
        with st.expander("View Attendance Statistics", expanded=False):
            st.subheader("Attendance Summary")
            
            # Calculate attendance rate for each member
            attendance_rates = []
            for _, row in st.session_state.attendance.iterrows():
                attended = sum(row[meeting] for meeting in st.session_state.meeting_names)
                total = len(st.session_state.meeting_names)
                rate = (attended / total) * 100 if total > 0 else 0
                attendance_rates.append({
                    "Name": row["Name"],
                    "Meetings Attended": attended,
                    "Total Meetings": total,
                    "Attendance Rate": f"{rate:.1f}%"
                })
            
            st.dataframe(pd.DataFrame(attendance_rates))

def render_credits_tab():
    """Render the Credits & Rewards tab content"""
    st.subheader("Student Credits and Rewards System")
    
    # Split into two columns
    col_credits, col_rewards = st.columns(2)
    
    with col_credits:
        st.subheader("Member Credits")
        
        if not st.session_state.credit_data.empty:
            st.dataframe(st.session_state.credit_data)
        else:
            st.info("No credit records available yet.")
        
        # Manage credits (admin only)
        if is_admin():
            with st.expander("Manage Credits", expanded=False):
                member = st.selectbox("Select Member", st.session_state.credit_data["Name"].tolist() if not st.session_state.credit_data.empty else [])
                credit_change = st.number_input("Credit Adjustment", value=0)
                reason = st.text_input("Reason for Adjustment")
                
                if st.button("Update Credits"):
                    if not member:
                        st.error("Please select a member.")
                    elif credit_change == 0:
                        st.error("Please enter a non-zero credit adjustment.")
                    else:
                        # Find member index
                        member_index = st.session_state.credit_data.index[
                            st.session_state.credit_data["Name"] == member
                        ].tolist()[0]
                        
                        # Update credits
                        st.session_state.credit_data.at[member_index, "Total_Credits"] += credit_change
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Updated {member}'s credits by {credit_change}")
                            else:
                                st.error(f"Failed to update credits: {msg}")
        
        # Redeem credits (all members)
        with st.expander("Redeem Credits for Rewards", expanded=False):
            member = st.selectbox("Your Name", st.session_state.credit_data["Name"].tolist() if not st.session_state.credit_data.empty else [], key="redeem_name")
            if member:
                # Get member's available credits
                member_data = st.session_state.credit_data[st.session_state.credit_data["Name"] == member].iloc[0]
                available_credits = member_data["Total_Credits"] - member_data["RedeemedCredits"]
                st.write(f"Your available credits: {available_credits}")
                
                # Show available rewards
                if not st.session_state.reward_data.empty:
                    available_rewards = st.session_state.reward_data[
                        (st.session_state.reward_data["Cost"] <= available_credits) &
                        (st.session_state.reward_data["Stock"] > 0)
                    ]
                    
                    if not available_rewards.empty:
                        selected_reward = st.selectbox("Select Reward", available_rewards["Reward"].tolist())
                        if selected_reward:
                            reward_cost = available_rewards[available_rewards["Reward"] == selected_reward]["Cost"].iloc[0]
                            reward_index = st.session_state.reward_data.index[
                                st.session_state.reward_data["Reward"] == selected_reward
                            ].tolist()[0]
                            
                            if st.button("Redeem Reward"):
                                # Update member's redeemed credits
                                member_index = st.session_state.credit_data.index[
                                    st.session_state.credit_data["Name"] == member
                                ].tolist()[0]
                                st.session_state.credit_data.at[member_index, "RedeemedCredits"] += reward_cost
                                
                                # Update reward stock
                                st.session_state.reward_data.at[reward_index, "Stock"] -= 1
                                
                                # Save changes
                                sheet = connect_gsheets()
                                if sheet:
                                    success, msg = save_all_data(sheet)
                                    if success:
                                        st.success(f"Successfully redeemed {selected_reward} for {reward_cost} credits!")
                                    else:
                                        st.error(f"Failed to process redemption: {msg}")
                    else:
                        st.info("No rewards available with your current credit balance.")
                else:
                    st.info("No rewards available in the catalog.")
    
    with col_rewards:
        st.subheader("Rewards Catalog")
        
        if not st.session_state.reward_data.empty:
            st.dataframe(st.session_state.reward_data)
        else:
            st.info("No rewards in catalog yet.")
        
        # Manage rewards (admin only)
        if is_admin():
            with st.expander("Manage Rewards Catalog", expanded=False):
                st.subheader("Add New Reward")
                reward_name = st.text_input("Reward Name")
                reward_cost = st.number_input("Credit Cost", min_value=10, step=5)
                reward_stock = st.number_input("Initial Stock", min_value=0, step=1)
                
                if st.button("Add Reward"):
                    if not reward_name:
                        st.error("Please enter a reward name.")
                    else:
                        new_reward = pd.DataFrame([{
                            "Reward": reward_name,
                            "Cost": reward_cost,
                            "Stock": reward_stock
                        }])
                        
                        st.session_state.reward_data = pd.concat(
                            [st.session_state.reward_data, new_reward], ignore_index=True
                        )
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Added new reward: {reward_name}")
                            else:
                                st.error(f"Failed to add reward: {msg}")
            
            with st.expander("Update Reward Stock", expanded=False):
                if not st.session_state.reward_data.empty:
                    reward_to_update = st.selectbox("Select Reward", st.session_state.reward_data["Reward"].tolist())
                    new_stock = st.number_input("New Stock Level", min_value=0, step=1)
                    
                    if st.button("Update Stock"):
                        reward_index = st.session_state.reward_data.index[
                            st.session_state.reward_data["Reward"] == reward_to_update
                        ].tolist()[0]
                        st.session_state.reward_data.at[reward_index, "Stock"] = new_stock
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Updated stock for {reward_to_update}")
                            else:
                                st.error(f"Failed to update stock: {msg}")

def render_events_tab():
    """Render the Events tab content"""
    st.subheader("Event Management")
    
    # Split into two columns
    col_scheduled, col_occasional = st.columns(2)
    
    with col_scheduled:
        st.subheader("Scheduled Events")
        
        if not st.session_state.scheduled_events.empty:
            st.dataframe(st.session_state.scheduled_events)
        else:
            st.info("No scheduled events yet.")
        
        # Add scheduled event form
        if is_admin() or is_group_leader(st.session_state.current_group):
            with st.expander("Add Scheduled Event", expanded=False):
                event_name = st.text_input("Event Name", key="sched_event_name")
                funds_per_event = st.number_input("Funds Per Event", min_value=0, key="sched_funds")
                frequency = st.number_input("Frequency Per Month", min_value=1, max_value=4, key="sched_freq")
                responsible_group = st.selectbox("Responsible Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"], key="sched_group")
                
                if st.button("Add Scheduled Event"):
                    if not event_name:
                        st.error("Please enter an event name.")
                    else:
                        total_funds = funds_per_event * frequency
                        new_event = pd.DataFrame([{
                            "Event Name": event_name,
                            "Funds Per Event": funds_per_event,
                            "Frequency Per Month": frequency,
                            "Total Funds": total_funds,
                            "Responsible Group": responsible_group
                        }])
                        
                        st.session_state.scheduled_events = pd.concat(
                            [st.session_state.scheduled_events, new_event], ignore_index=True
                        )
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Added scheduled event: {event_name}")
                            else:
                                st.error(f"Failed to add event: {msg}")
    
    with col_occasional:
        st.subheader("Occasional Events")
        
        if not st.session_state.occasional_events.empty:
            st.dataframe(st.session_state.occasional_events)
        else:
            st.info("No occasional events yet.")
        
        # Add occasional event form
        if is_admin() or is_group_leader(st.session_state.current_group):
            with st.expander("Add Occasional Event", expanded=False):
                event_name = st.text_input("Event Name", key="occ_event_name")
                funds_raised = st.number_input("Total Funds Raised", min_value=0, key="occ_funds")
                cost = st.number_input("Total Cost", min_value=0, key="occ_cost")
                staff_required = st.radio("Requires Many Staff?", ["Yes", "No"], key="occ_staff")
                prep_time = st.number_input("Preparation Time (Days)", min_value=1, key="occ_prep")
                rating = st.slider("Event Rating", 1, 5, 3, key="occ_rating")
                responsible_group = st.selectbox("Responsible Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"], key="occ_group")
                
                if st.button("Add Occasional Event"):
                    if not event_name:
                        st.error("Please enter an event name.")
                    else:
                        new_event = pd.DataFrame([{
                            "Event Name": event_name,
                            "Total Funds Raised": funds_raised,
                            "Cost": cost,
                            "Staff Required": staff_required,
                            "Preparation Time (Days)": prep_time,
                            "Rating": rating,
                            "Responsible Group": responsible_group
                        }])
                        
                        st.session_state.occasional_events = pd.concat(
                            [st.session_state.occasional_events, new_event], ignore_index=True
                        )
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Added occasional event: {event_name}")
                            else:
                                st.error(f"Failed to add event: {msg}")
    
    # Event statistics
    with st.expander("View Event Statistics", expanded=False):
        if not st.session_state.occasional_events.empty:
            st.subheader("Event Performance Summary")
            
            # Calculate profit for each event
            st.session_state.occasional_events["Profit"] = st.session_state.occasional_events[
                "Total Funds Raised"
            ] - st.session_state.occasional_events["Cost"]
            
            # Show profit summary
            st.dataframe(st.session_state.occasional_events[
                ["Event Name", "Total Funds Raised", "Cost", "Profit", "Rating", "Responsible Group"]
            ])
            
            # Group performance
            group_performance = st.session_state.occasional_events.groupby("Responsible Group").agg({
                "Event Name": "count",
                "Total Funds Raised": "sum",
                "Cost": "sum",
                "Profit": "sum",
                "Rating": "mean"
            }).reset_index()
            
            group_performance = group_performance.rename(columns={
                "Event Name": "Number of Events",
                "Rating": "Average Rating"
            })
            
            st.subheader("Group Performance")
            st.dataframe(group_performance)

def render_financials_tab():
    """Render the Financials tab content"""
    st.subheader("Financial Records")
    
    # Display financial data
    if not st.session_state.money_data.empty:
        st.dataframe(st.session_state.money_data)
    else:
        st.info("No financial records available yet.")
    
    # Add new transaction form (admin and group leaders)
    if is_admin() or is_group_leader(st.session_state.current_group):
        with st.expander("Record Financial Transaction", expanded=False):
            amount = st.number_input("Amount", key="finance_amount")
            description = st.text_input("Description", key="finance_desc")
            transaction_group = st.selectbox(
                "Group", 
                ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "General"],
                key="finance_group"
            )
            
            if st.button("Record Transaction"):
                if not description:
                    st.error("Please enter a description.")
                elif amount == 0:
                    st.error("Amount cannot be zero.")
                else:
                    new_transaction = pd.DataFrame([{
                        "Amount": amount,
                        "Description": description,
                        "Date": date.today().strftime("%Y-%m-%d"),
                        "Handled By": st.session_state.user,
                        "Group": transaction_group
                    }])
                    
                    st.session_state.money_data = pd.concat(
                        [st.session_state.money_data, new_transaction], ignore_index=True
                    )
                    
                    # Save changes
                    sheet = connect_gsheets()
                    if sheet:
                        success, msg = save_all_data(sheet)
                        if success:
                            st.success("Transaction recorded successfully.")
                        else:
                            st.error(f"Failed to record transaction: {msg}")
    
    # Financial summary
    if not st.session_state.money_data.empty:
        with st.expander("Financial Summary", expanded=False):
            # Calculate totals
            total_income = st.session_state.money_data[st.session_state.money_data["Amount"] > 0]["Amount"].sum()
            total_expenses = abs(st.session_state.money_data[st.session_state.money_data["Amount"] < 0]["Amount"].sum())
            current_balance = total_income - total_expenses
            
            # Display metrics
            col_income, col_expenses, col_balance = st.columns(3)
            with col_income:
                st.metric("Total Income", f"${total_income:,.2f}")
            with col_expenses:
                st.metric("Total Expenses", f"${total_expenses:,.2f}")
            with col_balance:
                st.metric("Current Balance", f"${current_balance:,.2f}")
            
            # Group financial summary
            st.subheader("Group Financial Summary")
            group_finance = st.session_state.money_data.groupby("Group")["Amount"].sum().reset_index()
            group_finance = group_finance.rename(columns={"Amount": "Net Balance"})
            st.dataframe(group_finance)
            
            # Monthly summary
            st.subheader("Monthly Financial Trend")
            st.session_state.money_data["Month"] = pd.to_datetime(st.session_state.money_data["Date"]).dt.to_period("M")
            monthly_summary = st.session_state.money_data.groupby("Month")["Amount"].sum().reset_index()
            monthly_summary["Month"] = monthly_summary["Month"].astype(str)
            
            # Create plot
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.bar(monthly_summary["Month"], monthly_summary["Amount"], color=np.where(monthly_summary["Amount"] > 0, 'green', 'red'))
            ax.set_xlabel("Month")
            ax.set_ylabel("Net Amount")
            ax.set_title("Monthly Financial Summary")
            plt.xticks(rotation=45)
            st.pyplot(fig)

def render_group_tab(group):
    """Render content for a specific group tab"""
    st.subheader(f"Group {group} Management")
    
    # Display group information
    col_info, col_stats = st.columns(2)
    
    with col_info:
        st.subheader("Group Information")
        
        # Group members
        st.write("**Members:**")
        members = st.session_state.groups.get(group, [])
        leader = st.session_state.group_leaders.get(group, "")
        
        for member in members:
            if member == leader:
                st.write(f"- {member} (Leader)")
            else:
                st.write(f"- {member}")
        
        # Group code (admin only)
        if is_admin():
            current_code = st.session_state.group_codes.get(group, "")
            new_code = st.text_input("Group Access Code", current_code, key=f"code_{group}")
            
            if st.button("Update Group Code", key=f"update_code_{group}"):
                if new_code:
                    st.session_state.group_codes[group] = new_code
                    sheet = connect_gsheets()
                    if sheet:
                        success, msg = save_all_data(sheet)
                        if success:
                            st.success("Group code updated successfully.")
                        else:
                            st.error(f"Failed to update code: {msg}")
        
        # Assign group leader (admin only)
        if is_admin():
            with st.expander("Assign Group Leader", expanded=False):
                if members:
                    new_leader = st.selectbox("Select New Leader", members, key=f"leader_{group}")
                    if st.button("Set as Leader", key=f"set_leader_{group}"):
                        success, msg = assign_group_leader(group, new_leader)
                        if success:
                            sheet = connect_gsheets()
                            if sheet:
                                save_success, save_msg = save_all_data(sheet)
                                if save_success:
                                    st.success(msg)
                                    st.experimental_rerun()
                                else:
                                    st.error(f"Leader assigned but failed to save: {save_msg}")
                        else:
                            st.error(msg)
                else:
                    st.info("No members in this group to assign as leader.")
    
    with col_stats:
        st.subheader("Group Statistics")
        
        # Number of members
        st.metric("Number of Members", len(members))
        
        # Meeting attendance rate
        if st.session_state.meeting_names and not st.session_state.attendance.empty:
            group_attendance = []
            for member in members:
                if member in st.session_state.attendance["Name"].values:
                    member_row = st.session_state.attendance[st.session_state.attendance["Name"] == member].iloc[0]
                    attended = sum(member_row[meeting] for meeting in st.session_state.meeting_names)
                    total = len(st.session_state.meeting_names)
                    rate = (attended / total) * 100 if total > 0 else 0
                    group_attendance.append(rate)
            
            if group_attendance:
                avg_attendance = sum(group_attendance) / len(group_attendance)
                st.metric("Average Attendance Rate", f"{avg_attendance:.1f}%")
        
        # Total earnings
        group_earnings = st.session_state.group_earnings[
            st.session_state.group_earnings["Group"] == group
        ]
        if not group_earnings.empty:
            total_earned = group_earnings["Amount"].sum()
            st.metric("Total Earnings", f"${total_earned:.2f}")
        
        # Pending requests
        pending_reimb = len(st.session_state.reimbursement_requests[
            (st.session_state.reimbursement_requests["Group"] == group) &
            (st.session_state.reimbursement_requests["Status"] == "Pending")
        ])
        
        pending_events = len(st.session_state.event_approval_requests[
            (st.session_state.event_approval_requests["Group"] == group) &
            (st.session_state.event_approval_requests["Status"] == "Pending")
        ])
        
        col_reimb, col_events = st.columns(2)
        with col_reimb:
            st.metric("Pending Reimbursements", pending_reimb)
        with col_events:
            st.metric("Pending Event Approvals", pending_events)
    
    # Group earnings
    st.subheader("Group Earnings")
    if not group_earnings.empty:
        st.dataframe(group_earnings)
    else:
        st.info("No earnings recorded for this group yet.")
    
    # Record earnings form (group members)
    if st.session_state.user in members:
        with st.expander("Record New Earnings", expanded=False):
            amount = st.number_input("Amount Earned", min_value=1, key=f"earn_amount_{group}")
            description = st.text_input("Description", key=f"earn_desc_{group}")
            
            if st.button("Record Earnings", key=f"record_earn_{group}"):
                if not description:
                    st.error("Please provide a description.")
                else:
                    success, msg = record_group_earnings(group, amount, description)
                    if success:
                        sheet = connect_gsheets()
                        if sheet:
                            save_success, save_msg = save_all_data(sheet)
                            if save_success:
                                st.success(msg)
                                st.experimental_rerun()
                            else:
                                st.error(f"Earnings recorded but failed to save: {save_msg}")
                    else:
                        st.error(msg)
    
    # Reimbursement requests
    st.subheader("Reimbursement Requests")
    group_reimb = st.session_state.reimbursement_requests[
        st.session_state.reimbursement_requests["Group"] == group
    ]
    if not group_reimb.empty:
        st.dataframe(group_reimb)
    else:
        st.info("No reimbursement requests for this group yet.")
    
    # Submit reimbursement request form (group members)
    if st.session_state.user in members:
        with st.expander("Request Reimbursement", expanded=False):
            amount = st.number_input("Reimbursement Amount", min_value=10, key=f"reimb_amount_{group}")
            purpose = st.text_area("Purpose for Reimbursement", key=f"reimb_purpose_{group}")
            
            if st.button("Submit Request", key=f"submit_reimb_{group}"):
                if not purpose:
                    st.error("Please provide a purpose for the reimbursement.")
                else:
                    success, msg = submit_reimbursement_request(
                        group, st.session_state.user, amount, purpose
                    )
                    if success:
                        sheet = connect_gsheets()
                        if sheet:
                            save_success, save_msg = save_all_data(sheet)
                            if save_success:
                                st.success(msg)
                            else:
                                st.error(f"Request submitted but failed to save: {save_msg}")
                    else:
                        st.error(msg)
    
    # Event approval requests
    st.subheader("Event Approval Requests")
    group_events = st.session_state.event_approval_requests[
        st.session_state.event_approval_requests["Group"] == group
    ]
    if not group_events.empty:
        st.dataframe(group_events[["Request ID", "Event Name", "Proposed Date", "Budget", "Status"]])
    else:
        st.info("No event approval requests for this group yet.")
    
    # Submit event approval request form (group members)
    if st.session_state.user in members:
        with st.expander("Request Event Approval", expanded=False):
            event_name = st.text_input("Event Name", key=f"event_name_{group}")
            description = st.text_area("Event Description", key=f"event_desc_{group}")
            proposed_date = st.date_input("Proposed Date", key=f"event_date_{group}")
            budget = st.number_input("Estimated Budget", min_value=0, key=f"event_budget_{group}")
            proposal_file = st.file_uploader("Upload Proposal Document", key=f"event_file_{group}")
            
            if st.button("Submit Event Request", key=f"submit_event_{group}"):
                if not event_name or not description:
                    st.error("Please provide event name and description.")
                elif not proposal_file:
                    st.error("Please upload a proposal document.")
                else:
                    # Read file content
                    file_content = proposal_file.read()
                    
                    success, msg = submit_event_approval_request(
                        group, st.session_state.user, event_name, description,
                        proposed_date, budget, file_content
                    )
                    if success:
                        sheet = connect_gsheets()
                        if sheet:
                            save_success, save_msg = save_all_data(sheet)
                            if save_success:
                                st.success(msg)
                            else:
                                st.error(f"Request submitted but failed to save: {save_msg}")
                    else:
                        st.error(msg)

def render_admin_tab():
    """Render the Admin Dashboard tab content"""
    st.subheader("Admin Dashboard")
    
    # User management section
    with st.expander("User Management", expanded=False):
        st.subheader("System Users")
        
        # Display user list
        user_list = []
        for username, details in st.session_state.users.items():
            user_list.append({
                "Username": username,
                "Role": details["role"],
                "Group": details["group"],
                "Created": details["created_at"].split("T")[0] if details["created_at"] else "",
                "Last Login": details["last_login"].split("T")[0] if details["last_login"] else "Never"
            })
        
        if user_list:
            st.dataframe(pd.DataFrame(user_list))
        else:
            st.info("No users in the system yet.")
        
        # Change user role
        if user_list:
            st.subheader("Modify User Role")
            user_to_modify = st.selectbox("Select User", [u["Username"] for u in user_list])
            new_role = st.selectbox("New Role", ["member", "admin"])
            
            if st.button("Update User Role"):
                if user_to_modify in st.session_state.users:
                    # Prevent changing creator role
                    if st.session_state.users[user_to_modify]["role"] == "creator":
                        st.error("Cannot modify creator role.")
                    else:
                        st.session_state.users[user_to_modify]["role"] = new_role
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Updated {user_to_modify}'s role to {new_role}")
                            else:
                                st.error(f"Failed to update role: {msg}")
        
        # Move user between groups
        if user_list:
            st.subheader("Move User Between Groups")
            user_to_move = st.selectbox("Select User to Move", [u["Username"] for u in user_list])
            
            if user_to_move in st.session_state.users:
                current_group = st.session_state.users[user_to_move]["group"]
                st.write(f"Current Group: {current_group}")
                
                target_groups = [g for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"] if g != current_group]
                target_group = st.selectbox("Move to Group", target_groups)
                
                if st.button("Move User"):
                    success, msg = move_user_to_group(user_to_move, current_group, target_group)
                    if success:
                        sheet = connect_gsheets()
                        if sheet:
                            save_success, save_msg = save_all_data(sheet)
                            if save_success:
                                st.success(msg)
                                st.experimental_rerun()
                            else:
                                st.error(f"User moved but failed to save: {save_msg}")
                    else:
                        st.error(msg)
    
    # Approve requests section
    with st.expander("Approve Requests", expanded=False):
        # Reimbursement requests
        st.subheader("Reimbursement Requests")
        pending_reimb = st.session_state.reimbursement_requests[
            st.session_state.reimbursement_requests["Status"] == "Pending"
        ]
        
        if not pending_reimb.empty:
            st.dataframe(pending_reimb)
            
            req_id = st.selectbox("Select Reimbursement Request", pending_reimb["Request ID"].tolist())
            action = st.radio("Action", ["Approve", "Denied"], key="reimb_action")
            notes = st.text_input("Administrator Notes", key="reimb_notes")
            
            if st.button("Process Reimbursement Request"):
                success, msg = process_request("reimbursement", req_id, action, notes)
                if success:
                    sheet = connect_gsheets()
                    if sheet:
                        save_success, save_msg = save_all_data(sheet)
                        if save_success:
                            st.success(msg)
                            st.experimental_rerun()
                        else:
                            st.error(f"Request processed but failed to save: {save_msg}")
                else:
                    st.error(msg)
        else:
            st.info("No pending reimbursement requests.")
        
        # Event approval requests
        st.subheader("Event Approval Requests")
        pending_events = st.session_state.event_approval_requests[
            st.session_state.event_approval_requests["Status"] == "Pending"
        ]
        
        if not pending_events.empty:
            st.dataframe(pending_events[["Request ID", "Group", "Event Name", "Proposed Date", "Budget"]])
            
            req_id = st.selectbox("Select Event Request", pending_events["Request ID"].tolist(), key="event_req_select")
            action = st.radio("Action", ["Approve", "Denied"], key="event_action")
            notes = st.text_input("Administrator Notes", key="event_notes")
            
            # Show selected request details
            if req_id:
                req_details = pending_events[pending_events["Request ID"] == req_id].iloc[0]
                with st.expander("View Request Details"):
                    st.write(f"**Event Name:** {req_details['Event Name']}")
                    st.write(f"**Description:** {req_details['Description']}")
                    st.write(f"**Proposed Date:** {req_details['Proposed Date']}")
                    st.write(f"**Budget:** ${req_details['Budget']}")
                    st.write(f"**Submitted By:** {req_details['Requester']} ({req_details['Group']})")
                    
                    # Show file if available
                    if req_details['File Reference']:
                        try:
                            file_content = base64.b64decode(req_details['File Reference'])
                            st.download_button(
                                "Download Proposal Document",
                                file_content,
                                file_name=f"{req_details['Event Name']}_proposal.pdf",
                                mime="application/pdf"
                            )
                        except:
                            st.warning("Unable to display attached file.")
            
            if st.button("Process Event Request"):
                success, msg = process_request("event", req_id, action, notes)
                if success:
                    sheet = connect_gsheets()
                    if sheet:
                        save_success, save_msg = save_all_data(sheet)
                        if save_success:
                            st.success(msg)
                            st.experimental_rerun()
                        else:
                            st.error(f"Request processed but failed to save: {save_msg}")
                else:
                    st.error(msg)
        else:
            st.info("No pending event approval requests.")
    
    # Verify group earnings
    with st.expander("Verify Group Earnings", expanded=False):
        st.subheader("Pending Earnings Verification")
        pending_earnings = st.session_state.group_earnings[
            st.session_state.group_earnings["Verified"] == "Pending"
        ]
        
        if not pending_earnings.empty:
            st.dataframe(pending_earnings)
            
            # Select earnings to verify
            earnings_index = st.selectbox(
                "Select Earnings to Verify",
                pending_earnings.index.tolist()
            )
            
            if st.button("Verify Earnings"):
                # Update verification status
                st.session_state.group_earnings.at[earnings_index, "Verified"] = "Approved"
                
                # Add to financial records
                earnings_data = st.session_state.group_earnings.iloc[earnings_index]
                new_income = pd.DataFrame([{
                    "Amount": float(earnings_data["Amount"]),
                    "Description": f"Earnings: {earnings_data['Description']}",
                    "Date": date.today().strftime("%Y-%m-%d"),
                    "Handled By": st.session_state.user,
                    "Group": earnings_data["Group"]
                }])
                
                st.session_state.money_data = pd.concat(
                    [st.session_state.money_data, new_income], ignore_index=True
                )
                
                # Save changes
                sheet = connect_gsheets()
                if sheet:
                    success, msg = save_all_data(sheet)
                    if success:
                        st.success("Earnings verified and added to financial records.")
                        st.experimental_rerun()
                    else:
                        st.error(f"Failed to verify earnings: {msg}")
        else:
            st.info("No pending earnings to verify.")
    
    # System configuration
    with st.expander("System Configuration", expanded=False):
        st.subheader("System Settings")
        
        # Signup setting
        allow_signups = st.checkbox(
            "Allow New User Signups",
            value=st.session_state.system_config.get("allow_signups", True)
        )
        
        # Meeting reminders
        meeting_reminders = st.checkbox(
            "Send Meeting Reminders",
            value=st.session_state.system_config.get("meeting_reminders", True)
        )
        
        # Approval requirements
        require_approval = st.checkbox(
            "Require Admin Approval for Events",
            value=st.session_state.system_config.get("require_admin_approval", True)
        )
        
        if st.button("Save Settings"):
            st.session_state.system_config["allow_signups"] = allow_signups
            st.session_state.system_config["meeting_reminders"] = meeting_reminders
            st.session_state.system_config["require_admin_approval"] = require_approval
            
            # Save changes
            sheet = connect_gsheets()
            if sheet:
                success, msg = save_all_data(sheet)
                if success:
                    st.success("System settings updated successfully.")
                else:
                    st.error(f"Failed to save settings: {msg}")

# ------------------------------
# Permission Check Functions
# ------------------------------
def is_admin():
    """Check if current user has admin or creator privileges"""
    return st.session_state.get("role") in ["admin", "creator"]

def is_group_leader(group):
    """Check if current user is the leader of the specified group"""
    if not group or not st.session_state.get("user"):
        return False
    return st.session_state.group_leaders.get(group, "") == st.session_state.user

# ------------------------------
# Main Application Function
# ------------------------------
def main():
    """Main application entry point"""
    # Initialize session state with empty values
    initialize_session_state()
    
    # Connect to Google Sheets
    sheet = connect_gsheets()
    
    # Load data from Google Sheets if connection is successful
    if sheet:
        with st.spinner("Loading data from Google Sheets..."):
            success, msg = load_all_data(sheet)
            if not success:
                st.warning(f"Using initial empty data: {msg}")
    
    # Handle user authentication
    if not st.session_state.user:
        if render_login_signup():
            # Save login time after successful login
            if st.session_state.user in st.session_state.users:
                st.session_state.users[st.session_state.user]["last_login"] = datetime.now().isoformat()
                if sheet:
                    save_all_data(sheet)
            st.experimental_rerun()
        return
    
    # Main application interface after login
    st.title("Student Council Management System")
    
    # Sidebar with user info and navigation
    with st.sidebar:
        st.write(f"**Logged in as:** {st.session_state.user}")
        st.write(f"**Role:** {st.session_state.role}")
        if st.session_state.current_group:
            st.write(f"**Group:** {st.session_state.current_group}")
        
        st.divider()
        
        # Quick links
        st.subheader("Quick Links")
        if st.button("View My Group", use_container_width=True):
            if st.session_state.current_group:
                st.session_state.active_tab = f"Group {st.session_state.current_group}"
                st.experimental_rerun()
        
        if is_admin() and st.button("Admin Dashboard", use_container_width=True):
            st.session_state.active_tab = "Admin Dashboard"
            st.experimental_rerun()
        
        st.divider()
        
        # Logout button
        if st.button("Logout", use_container_width=True, type="primary"):
            st.session_state.user = None
            st.session_state.role = None
            st.session_state.current_group = None
            st.experimental_rerun()
    
    # Display announcements
    if st.session_state.announcements:
        with st.expander("Announcements", expanded=True):
            # Show most recent announcements first
            for ann in sorted(st.session_state.announcements, key=lambda x: x["date"], reverse=True)[:3]:
                # Show group-specific announcements only to members of that group
                if not ann["group"] or ann["group"] == st.session_state.current_group or is_admin():
                    st.info(f"**{ann['title']}** ({ann['date']})\n\n{ann['content']}")
    
    # Create main tabs
    main_tabs = ["Calendar", "Attendance", "Credits & Rewards", "Events", "Financials"]
    if is_admin():
        main_tabs.append("Admin Dashboard")
    
    # Add group tabs (G1-G8) after main tabs
    group_tabs = [f"Group {g}" for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]]
    all_tabs = main_tabs + group_tabs
    
    # Create tabs in the interface
    tabs = st.tabs(all_tabs)
    
    # Render appropriate content for each tab
    for i, tab_name in enumerate(all_tabs):
        with tabs[i]:
            if tab_name == "Calendar":
                render_calendar_tab()
            elif tab_name == "Attendance":
                render_attendance_tab()
            elif tab_name == "Credits & Rewards":
                render_credits_tab()
            elif tab_name == "Events":
                render_events_tab()
            elif tab_name == "Financials":
                render_financials_tab()
            elif tab_name == "Admin Dashboard":
                render_admin_tab()
            elif tab_name.startswith("Group "):
                group = tab_name.split(" ")[1]
                render_group_tab(group)

if __name__ == "__main__":
    main()
