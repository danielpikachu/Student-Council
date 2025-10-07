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
import string
from io import BytesIO, StringIO
import base64
import re
from collections import defaultdict
import logging

# ------------------------------
# App Configuration & Setup
# ------------------------------
st.set_page_config(
    page_title="SCIS Student Council Management System",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ------------------------------
# Global Constants & Variables
# ------------------------------
APP_VERSION = "2.1.0"
MIN_PASSWORD_LENGTH = 8
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
VALID_FILE_EXTENSIONS = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.ppt', '.pptx', '.txt']
GROUP_NAMES = [f"G{i}" for i in range(1, 9)]  # G1 to G8
ROLES = ["user", "group_leader", "admin", "creator"]
REIMBURSEMENT_LIMIT = 500  # Maximum reimbursement amount without special approval
EVENT_BUDGET_LIMIT = 2000  # Maximum event budget without special approval

# ------------------------------
# Google Sheets Connection & Management
# ------------------------------
def connect_gsheets():
    """
    Establish connection to Google Sheets using service account credentials
    and ensure all required worksheets exist.
    
    Returns:
        gspread.Spreadsheet: Connected spreadsheet object or None if failed
    """
    try:
        # Get secrets from Streamlit configuration
        if "google_sheets" not in st.secrets:
            st.error("Google Sheets configuration not found in secrets")
            logging.error("Google Sheets configuration missing from secrets")
            return None
            
        secrets = st.secrets["google_sheets"]
        
        # Validate required secrets
        required_secrets = ["service_account_email", "private_key_id", "private_key", "sheet_url"]
        for secret in required_secrets:
            if secret not in secrets or not secrets[secret]:
                st.error(f"Missing required Google Sheets secret: {secret}")
                logging.error(f"Missing Google Sheets secret: {secret}")
                return None
        
        # Create credentials dictionary
        creds = {
            "type": "service_account",
            "client_email": secrets["service_account_email"],
            "private_key_id": secrets["private_key_id"],
            "client_id": "100000000000000000000",  # Placeholder
            "private_key": secrets["private_key"].replace("\\n", "\n"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{secrets['service_account_email']}"
        }
        
        # Authenticate
        try:
            client = gspread.service_account_from_dict(creds)
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            logging.error(f"Google Sheets authentication failed: {str(e)}")
            return None
        
        # Open the spreadsheet
        try:
            sheet = client.open_by_url(secrets["sheet_url"])
        except gspread.exceptions.SpreadsheetNotFound:
            st.error("Spreadsheet not found. Please check the URL in secrets.")
            logging.error("Spreadsheet not found at provided URL")
            return None
        except Exception as e:
            st.error(f"Failed to open spreadsheet: {str(e)}")
            logging.error(f"Failed to open spreadsheet: {str(e)}")
            return None
        
        # List of required worksheets
        required_worksheets = [
            "users", "attendance", "credit_data", "reward_data",
            "scheduled_events", "occasional_events", "money_data",
            "calendar_events", "announcements", "config",
            "groups", "group_leaders", "group_earnings",
            "reimbursement_requests", "event_approval_requests",
            "activity_log", "meeting_minutes", "user_notifications"
        ]
        
        # Get existing worksheets
        existing_sheets = [ws.title for ws in sheet.worksheets()]
        
        # Create any missing worksheets
        for ws_name in required_worksheets:
            if ws_name not in existing_sheets:
                try:
                    sheet.add_worksheet(title=ws_name, rows="2000", cols="50")
                    st.success(f"Created missing worksheet: {ws_name}")
                    logging.info(f"Created missing worksheet: {ws_name}")
                    
                    # Initialize headers for new worksheets
                    if ws_name == "activity_log":
                        ws = sheet.worksheet(ws_name)
                        ws.append_row(["Timestamp", "User", "Action", "Details", "IP Address"])
                    elif ws_name == "user_notifications":
                        ws = sheet.worksheet(ws_name)
                        ws.append_row(["Notification ID", "Username", "Title", "Message", "Timestamp", "Read Status"])
                except Exception as e:
                    st.warning(f"Could not create worksheet {ws_name}: {str(e)}")
                    logging.warning(f"Failed to create worksheet {ws_name}: {str(e)}")
        
        logging.info("Successfully connected to Google Sheets")
        return sheet
    
    except Exception as e:
        st.error(f"Google Sheets connection failed: {str(e)}")
        logging.error(f"Google Sheets connection error: {str(e)}", exc_info=True)
        return None

# ------------------------------
# Session State Initialization
# ------------------------------
def initialize_session_state():
    """Initialize all required session state variables with default values"""
    # Core user session variables
    user_session_vars = {
        "user": None,
        "role": None,
        "login_attempts": 0,
        "last_login_attempt": None,
        "current_group": None,
        "show_password_reset": False,
        "password_reset_token": None,
        "password_reset_username": None,
        "notification_count": 0,
        "unread_notifications": [],
        "active_tab": "Dashboard",
        "user_ip": "unknown",
        "session_id": ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    }
    
    # UI state variables
    ui_state_vars = {
        "spinning": False,
        "winner": None,
        "allocation_count": 0,
        "current_calendar_month": (date.today().year, date.today().month),
        "show_help": False,
        "show_about": False,
        "confirm_action": None,
        "filter_group": "All",
        "date_range_start": date.today() - timedelta(days=30),
        "date_range_end": date.today(),
        "search_query": ""
    }
    
    # Data storage variables
    data_storage_vars = {
        "users": {},
        "attendance": pd.DataFrame(),
        "credit_data": pd.DataFrame(),
        "reward_data": pd.DataFrame(),
        "scheduled_events": pd.DataFrame(),
        "occasional_events": pd.DataFrame(),
        "money_data": pd.DataFrame(),
        "calendar_events": {},
        "announcements": [],
        "config": {},
        "meeting_names": [],
        "groups": {g: [] for g in GROUP_NAMES},
        "group_leaders": {g: "" for g in GROUP_NAMES},
        "group_earnings": pd.DataFrame(),
        "reimbursement_requests": pd.DataFrame(),
        "event_approval_requests": pd.DataFrame(),
        "group_codes": {g: generate_group_code(g) for g in GROUP_NAMES},
        "activity_log": pd.DataFrame(),
        "meeting_minutes": pd.DataFrame(),
        "user_notifications": pd.DataFrame()
    }
    
    # Combine all variables and initialize if missing
    all_vars = {** user_session_vars, **ui_state_vars,** data_storage_vars}
    for key, default_value in all_vars.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def generate_group_code(group):
    """Generate a random group code for new groups"""
    prefix = group.replace("G", "GRP")
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{random_suffix}"

# ------------------------------
# Default Data Initialization
# ------------------------------
def initialize_default_data():
    """Set up default data for all system components when no existing data is found"""
    logging.info("Initializing default data set")
    
    # Default members
    members = [
        "Ahaan", "Bella", "Ella",  # Admins
        "Alice", "Bob", "Charlie", "Diana", "Evan",  # G1-G5 members
        "Frank", "Grace", "Henry", "Ivy", "Jack"     # G6-G8 members
    ]
    
    # Initialize attendance with multiple meetings
    st.session_state.meeting_names = [
        "First Semester Kickoff",
        "Event Planning Session",
        "Budget Review Meeting",
        "Monthly General Meeting"
    ]
    
    # Create attendance data with random presence
    att_data = {"Name": members}
    for meeting in st.session_state.meeting_names:
        att_data[meeting] = [random.choice([True, False]) for _ in range(len(members))]
    st.session_state.attendance = pd.DataFrame(att_data)
    
    # Initialize credit data with varying amounts
    st.session_state.credit_data = pd.DataFrame({
        "Name": members,
        "Total_Credits": [random.randint(100, 500) for _ in members],
        "RedeemedCredits": [random.randint(0, 100) for _ in members],
        "Last_Updated": [datetime.now().strftime("%Y-%m-%d") for _ in members]
    })
    
    # Initialize reward catalog
    st.session_state.reward_data = pd.DataFrame([
        {"Reward": "Bubble Tea", "Cost": 50, "Stock": 15, "Supplier": "Local Café"},
        {"Reward": "Chips & Soda", "Cost": 30, "Stock": 25, "Supplier": "School Store"},
        {"Reward": "Café Coupon", "Cost": 80, "Stock": 10, "Supplier": "Downtown Café"},
        {"Reward": "Movie Ticket", "Cost": 120, "Stock": 5, "Supplier": "Cinema Complex"},
        {"Reward": "Gift Card ($10)", "Cost": 200, "Stock": 8, "Supplier": "General Store"}
    ])
    
    # Initialize scheduled events
    st.session_state.scheduled_events = pd.DataFrame([
        {
            "Event Name": "Monthly Bake Sale",
            "Funds Per Event": 300,
            "Frequency Per Month": 1,
            "Total Funds": 300,
            "Responsible Group": "G1",
            "Last Held": (date.today() - timedelta(days=14)).strftime("%Y-%m-%d"),
            "Next Scheduled": (date.today() + timedelta(days=16)).strftime("%Y-%m-%d")
        },
        {
            "Event Name": "Tutoring Sessions",
            "Funds Per Event": 0,
            "Frequency Per Month": 4,
            "Total Funds": 0,
            "Responsible Group": "G3",
            "Last Held": (date.today() - timedelta(days=3)).strftime("%Y-%m-%d"),
            "Next Scheduled": (date.today() + timedelta(days=4)).strftime("%Y-%m-%d")
        }
    ])
    
    # Initialize occasional events
    st.session_state.occasional_events = pd.DataFrame([
        {
            "Event Name": "Back to School Fair",
            "Total Funds Raised": 1200,
            "Cost": 500,
            "Staff Many Or Not": "Yes",
            "Preparation Time": 14,
            "Rating": 4.5,
            "Responsible Group": "G2"
        },
        {
            "Event Name": "Charity Run",
            "Total Funds Raised": 3500,
            "Cost": 800,
            "Staff Many Or Not": "Yes",
            "Preparation Time": 30,
            "Rating": 4.8,
            "Responsible Group": "G4"
        }
    ])
    
    # Initialize financial data with sample transactions
    financial_entries = []
    today = date.today()
    
    # Add income entries
    for i in range(10):
        entry_date = today - timedelta(days=random.randint(1, 60))
        financial_entries.append({
            "Amount": random.randint(100, 1000),
            "Description": random.choice([
                "Bake sale proceeds", "Donation", "Fundraiser income", 
                "Sponsorship", "Ticket sales"
            ]),
            "Date": entry_date.strftime("%Y-%m-%d"),
            "Handled By": random.choice(members),
            "Group": random.choice(GROUP_NAMES),
            "Category": "Income"
        })
    
    # Add expense entries
    for i in range(8):
        entry_date = today - timedelta(days=random.randint(1, 60))
        financial_entries.append({
            "Amount": -random.randint(50, 500),  # Negative for expenses
            "Description": random.choice([
                "Event supplies", "Printing costs", "Food for meeting", 
                "Prizes", "Decoration materials"
            ]),
            "Date": entry_date.strftime("%Y-%m-%d"),
            "Handled By": random.choice(members),
            "Group": random.choice(GROUP_NAMES),
            "Category": "Expense"
        })
    
    st.session_state.money_data = pd.DataFrame(financial_entries)
    
    # Initialize groups with balanced membership
    group_members = {g: [] for g in GROUP_NAMES}
    for i, member in enumerate(members):
        group_index = i % len(GROUP_NAMES)
        group_members[GROUP_NAMES[group_index]].append(member)
    
    st.session_state.groups = group_members
    
    # Initialize group leaders (first member of each group)
    st.session_state.group_leaders = {
        g: members[i] for i, g in enumerate(GROUP_NAMES) if group_members[g]
    }
    
    # Initialize group earnings with sample data
    earnings_entries = []
    for _ in range(20):
        group = random.choice(GROUP_NAMES)
        earn_date = today - timedelta(days=random.randint(1, 90))
        earnings_entries.append({
            "Group": group,
            "Date": earn_date.strftime("%Y-%m-%d"),
            "Amount": random.randint(50, 800),
            "Description": random.choice([
                "Fundraiser", "Donation", "Event proceeds", "Sponsorship"
            ]),
            "Verified": random.choice(["Pending", "Verified", "Rejected"]),
            "Verified By": random.choice(members) if random.choice([True, False]) else ""
        })
    
    st.session_state.group_earnings = pd.DataFrame(earnings_entries)
    
    # Initialize reimbursement requests
    reimburse_requests = []
    for i in range(8):
        group = random.choice(GROUP_NAMES)
        req_date = today - timedelta(days=random.randint(1, 14))
        status = random.choice(["Pending", "Approved", "Denied"])
        
        reimburse_requests.append({
            "Request ID": f"REIMB-{1000 + i}",
            "Group": group,
            "Requester": random.choice(group_members[group]),
            "Amount": random.randint(50, 400),
            "Purpose": random.choice([
                "Event supplies", "Printing materials", "Food for volunteers",
                "Transportation costs", "Decoration items"
            ]),
            "Date Submitted": req_date.strftime("%Y-%m-%d %H:%M:%S"),
            "Status": status,
            "Admin Notes": "Approved - valid expenses" if status == "Approved" 
                          else "Denied - insufficient documentation" if status == "Denied"
                          else "",
            "Reviewed By": random.choice(["Ahaan", "Bella", "Ella"]) if status != "Pending" else ""
        })
    
    st.session_state.reimbursement_requests = pd.DataFrame(reimburse_requests)
    
    # Initialize event approval requests
    event_requests = []
    for i in range(6):
        group = random.choice(GROUP_NAMES)
        req_date = today - timedelta(days=random.randint(1, 21))
        status = random.choice(["Pending", "Approved", "Denied"])
        proposed_date = today + timedelta(days=random.randint(7, 45))
        
        event_requests.append({
            "Request ID": f"EVENT-{1000 + i}",
            "Group": group,
            "Requester": random.choice(group_members[group]),
            "Event Name": random.choice([
                "Winter Festival", "Charity Car Wash", "Talent Show",
                "Book Drive", "Community Cleanup"
            ]),
            "Description": "Organizing an event to raise funds and awareness",
            "Proposed Date": proposed_date.strftime("%Y-%m-%d"),
            "Budget": random.randint(300, 1800),
            "Expected Attendance": random.randint(30, 200),
            "Date Submitted": req_date.strftime("%Y-%m-%d %H:%M:%S"),
            "Status": status,
            "Admin Notes": "Approved - good planning" if status == "Approved" 
                          else "Denied - conflicting with school calendar" if status == "Denied"
                          else ""
        })
    
    st.session_state.event_approval_requests = pd.DataFrame(event_requests)
    
    # Initialize calendar events
    calendar_events = {}
    for i in range(15):
        event_date = today + timedelta(days=random.randint(-14, 30))
        date_str = event_date.strftime("%Y-%m-%d")
        calendar_events[date_str] = [
            random.choice([
                "Student Council Meeting", "Group Planning Session",
                "Fundraiser Event", "Community Outreach"
            ]),
            random.choice(GROUP_NAMES)
        ]
    
    st.session_state.calendar_events = calendar_events
    
    # Initialize announcements
    st.session_state.announcements = [
        {
            "title": "Upcoming General Meeting",
            "text": "The monthly general meeting will be held next Friday at 3pm in the auditorium. All members are required to attend.",
            "time": (today - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
            "author": "Ahaan",
            "group": ""  # All groups
        },
        {
            "title": "Bake Sale Success",
            "text": "Thank you to everyone who participated in the bake sale. We raised over $500 for the charity drive!",
            "time": (today - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "author": "Bella",
            "group": "G1"  # Specific to G1
        }
    ]
    
    # Initialize system configuration
    st.session_state.config = {
        "show_signup": True,
        "app_version": APP_VERSION,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "max_reimbursement": 500,
        "max_event_budget": 2000
    }
    
    # Initialize users with proper roles and hashed passwords
    st.session_state.users = {}
    
    # Add admins: Ahaan, Bella, Ella
    for admin in ["Ahaan", "Bella", "Ella"]:
        # Get password from secrets or use default
        admin_creds = st.secrets.get("admins", {})
        pwd = admin_creds.get(admin.lower(), f"{admin.lower()}@2023")
        
        # Assign to first three groups
        group_index = ["Ahaan", "Bella", "Ella"].index(admin)
        group = GROUP_NAMES[group_index] if group_index < len(GROUP_NAMES) else "G1"
        
        st.session_state.users[admin] = {
            "password_hash": bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode(),
            "role": "admin",
            "created_at": datetime.now().isoformat(),
            "last_login": (today - timedelta(days=random.randint(1, 7))).isoformat() if random.choice([True, False]) else None,
            "group": group,
            "email": f"{admin.lower()}@school.edu"
        }
    
    # Add regular users
    regular_users = [m for m in members if m not in ["Ahaan", "Bella", "Ella"]]
    for user in regular_users:
        # Find which group this user belongs to
        user_group = next(g for g, members in group_members.items() if user in members)
        
        # Determine role (some group leaders)
        role = "group_leader" if user == st.session_state.group_leaders.get(user_group, "") else "user"
        
        st.session_state.users[user] = {
            "password_hash": bcrypt.hashpw(f"{user.lower()}@2023".encode(), bcrypt.gensalt()).decode(),
            "role": role,
            "created_at": (today - timedelta(days=random.randint(30, 90))).isoformat(),
            "last_login": (today - timedelta(days=random.randint(1, 14))).isoformat() if random.choice([True, False]) else None,
            "group": user_group,
            "email": f"{user.lower()}@school.edu"
        }
    
    # Initialize creator if defined in secrets
    creator_creds = st.secrets.get("creator", {})
    if creator_creds.get("username") and creator_creds.get("password"):
        st.session_state.users[creator_creds["username"]] = {
            "password_hash": bcrypt.hashpw(creator_creds["password"].encode(), bcrypt.gensalt()).decode(),
            "role": "creator",
            "created_at": (today - timedelta(days=120)).isoformat(),
            "last_login": (today - timedelta(days=random.randint(1, 3))).isoformat(),
            "group": "",
            "email": "creator@school.edu"
        }
    
    # Initialize activity log
    st.session_state.activity_log = pd.DataFrame([
        {
            "Timestamp": (today - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "User": "Ahaan",
            "Action": "login",
            "Details": "Successful login",
            "IP Address": "192.168.1.100"
        },
        {
            "Timestamp": (today - timedelta(days=1)).strftime("%Y-%m-%d %14:%30:00"),
            "User": "Bella",
            "Action": "approve_request",
            "Details": "Approved reimbursement request REIMB-1002",
            "IP Address": "192.168.1.101"
        }
    ])
    
    # Initialize meeting minutes
    st.session_state.meeting_minutes = pd.DataFrame([
        {
            "Meeting Name": "First Semester Kickoff",
            "Date": (today - timedelta(days=45)).strftime("%Y-%m-%d"),
            "Location": "School Auditorium",
            "Facilitator": "Ahaan",
            "Attendees": "15 members",
            "Agenda": "Discuss semester goals, assign responsibilities",
            "Key Decisions": "Approved $5000 budget, scheduled monthly meetings",
            "Next Steps": "Form committees, draft event calendar"
        }
    ])
    
    # Initialize user notifications
    st.session_state.user_notifications = pd.DataFrame([
        {
            "Notification ID": f"NOTIF-{random.randint(1000, 9999)}",
            "Username": "Alice",
            "Title": "Reimbursement Approved",
            "Message": "Your reimbursement request has been approved",
            "Timestamp": (today - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "Read Status": "Unread"
        },
        {
            "Notification ID": f"NOTIF-{random.randint(1000, 9999)}",
            "Username": "Bob",
            "Title": "Event Proposal Feedback",
            "Message": "Your event proposal needs additional information",
            "Timestamp": (today - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "Read Status": "Read"
        }
    ])
    
    logging.info("Default data initialization complete")

# ------------------------------
# Data Management - Google Sheets Operations
# ------------------------------
@st.cache_data(ttl=30)  # Cache for 30 seconds to reduce API calls
def get_worksheet_data(sheet, worksheet_name):
    """
    Retrieve data from a specific worksheet with error handling.
    
    Args:
        sheet: Google Sheets connection
        worksheet_name: Name of worksheet to retrieve
        
    Returns:
        list: List of records from the worksheet
    """
    try:
        ws = sheet.worksheet(worksheet_name)
        return ws.get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        st.warning(f"Worksheet {worksheet_name} not found")
        logging.warning(f"Worksheet {worksheet_name} not found")
        return []
    except Exception as e:
        st.warning(f"Error retrieving data from {worksheet_name}: {str(e)}")
        logging.warning(f"Error retrieving {worksheet_name} data: {str(e)}")
        return []

def save_all_data(sheet):
    """
    Save ALL application data to Google Sheets with comprehensive error handling.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not sheet:
        return False, "No Google Sheets connection available"
    
    try:
        # Track which worksheets were updated successfully
        success_count = 0
        error_messages = []
        
        # 1. Save users
        try:
            users_ws = sheet.worksheet("users")
            users_data = [["username", "password_hash", "role", "created_at", "last_login", 
                          "group", "email"]]
            for username, user in st.session_state.users.items():
                users_data.append([
                    username,
                    user["password_hash"],
                    user["role"],
                    user["created_at"],
                    user.get("last_login", ""),
                    user.get("group", ""),
                    user.get("email", "")
                ])
            users_ws.clear()
            users_ws.update(users_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Users: {str(e)}")
            logging.error(f"Error saving users: {str(e)}")
        
        # 2. Save attendance
        try:
            att_ws = sheet.worksheet("attendance")
            att_data = [st.session_state.attendance.columns.tolist()] + st.session_state.attendance.values.tolist()
            att_ws.clear()
            att_ws.update(att_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Attendance: {str(e)}")
            logging.error(f"Error saving attendance: {str(e)}")
        
        # 3. Save credit data
        try:
            credit_ws = sheet.worksheet("credit_data")
            credit_data = [st.session_state.credit_data.columns.tolist()] + st.session_state.credit_data.values.tolist()
            credit_ws.clear()
            credit_ws.update(credit_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Credit data: {str(e)}")
            logging.error(f"Error saving credit data: {str(e)}")
        
        # 4. Save reward data
        try:
            reward_ws = sheet.worksheet("reward_data")
            reward_data = [st.session_state.reward_data.columns.tolist()] + st.session_state.reward_data.values.tolist()
            reward_ws.clear()
            reward_ws.update(reward_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Reward data: {str(e)}")
            logging.error(f"Error saving reward data: {str(e)}")
        
        # 5. Save scheduled events
        try:
            scheduled_ws = sheet.worksheet("scheduled_events")
            scheduled_data = [st.session_state.scheduled_events.columns.tolist()] + st.session_state.scheduled_events.values.tolist()
            scheduled_ws.clear()
            scheduled_ws.update(scheduled_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Scheduled events: {str(e)}")
            logging.error(f"Error saving scheduled events: {str(e)}")
        
        # 6. Save occasional events
        try:
            occasional_ws = sheet.worksheet("occasional_events")
            occasional_data = [st.session_state.occasional_events.columns.tolist()] + st.session_state.occasional_events.values.tolist()
            occasional_ws.clear()
            occasional_ws.update(occasional_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Occasional events: {str(e)}")
            logging.error(f"Error saving occasional events: {str(e)}")
        
        # 7. Save money transactions
        try:
            money_ws = sheet.worksheet("money_data")
            money_data = [st.session_state.money_data.columns.tolist()] + st.session_state.money_data.values.tolist()
            money_ws.clear()
            money_ws.update(money_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Money data: {str(e)}")
            logging.error(f"Error saving money data: {str(e)}")
        
        # 8. Save calendar events
        try:
            calendar_ws = sheet.worksheet("calendar_events")
            calendar_data = [["date", "event", "group"]]
            for date_str, event_data in st.session_state.calendar_events.items():
                calendar_data.append([date_str, event_data[0], event_data[1]])
            calendar_ws.clear()
            calendar_ws.update(calendar_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Calendar events: {str(e)}")
            logging.error(f"Error saving calendar events: {str(e)}")
        
        # 9. Save announcements
        try:
            announcements_ws = sheet.worksheet("announcements")
            announcements_data = [["title", "text", "time", "author", "group"]]
            for ann in st.session_state.announcements:
                announcements_data.append([
                    ann["title"], ann["text"], ann["time"], ann["author"], ann.get("group", "")
                ])
            announcements_ws.clear()
            announcements_ws.update(announcements_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Announcements: {str(e)}")
            logging.error(f"Error saving announcements: {str(e)}")
        
        # 10. Save configuration
        try:
            config_ws = sheet.worksheet("config")
            config_data = [["key", "value"]]
            for key, value in st.session_state.config.items():
                config_data.append([key, str(value)])
            config_ws.clear()
            config_ws.update(config_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Config: {str(e)}")
            logging.error(f"Error saving config: {str(e)}")
        
        # 11. Save groups
        try:
            groups_ws = sheet.worksheet("groups")
            groups_data = [["group", "members"]]
            for group, members in st.session_state.groups.items():
                groups_data.append([group, ", ".join(members)])
            # Add group codes as the last row
            groups_data.append(["group_codes", str(st.session_state.group_codes)])
            groups_ws.clear()
            groups_ws.update(groups_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Groups: {str(e)}")
            logging.error(f"Error saving groups: {str(e)}")
        
        # 12. Save group leaders
        try:
            leaders_ws = sheet.worksheet("group_leaders")
            leaders_data = [["group", "leader"]]
            for group, leader in st.session_state.group_leaders.items():
                leaders_data.append([group, leader])
            leaders_ws.clear()
            leaders_ws.update(leaders_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Group leaders: {str(e)}")
            logging.error(f"Error saving group leaders: {str(e)}")
        
        # 13. Save group earnings
        try:
            earnings_ws = sheet.worksheet("group_earnings")
            earnings_data = [st.session_state.group_earnings.columns.tolist()] + st.session_state.group_earnings.values.tolist()
            earnings_ws.clear()
            earnings_ws.update(earnings_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Group earnings: {str(e)}")
            logging.error(f"Error saving group earnings: {str(e)}")
        
        # 14. Save reimbursement requests
        try:
            reimburse_ws = sheet.worksheet("reimbursement_requests")
            reimburse_data = [st.session_state.reimbursement_requests.columns.tolist()] + st.session_state.reimbursement_requests.values.tolist()
            reimburse_ws.clear()
            reimburse_ws.update(reimburse_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Reimbursement requests: {str(e)}")
            logging.error(f"Error saving reimbursement requests: {str(e)}")
        
        # 15. Save event approval requests
        try:
            events_ws = sheet.worksheet("event_approval_requests")
            events_data = [st.session_state.event_approval_requests.columns.tolist()] + st.session_state.event_approval_requests.values.tolist()
            events_ws.clear()
            events_ws.update(events_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Event requests: {str(e)}")
            logging.error(f"Error saving event requests: {str(e)}")
        
        # 16. Save activity log
        try:
            activity_ws = sheet.worksheet("activity_log")
            activity_data = [st.session_state.activity_log.columns.tolist()] + st.session_state.activity_log.values.tolist()
            activity_ws.clear()
            activity_ws.update(activity_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Activity log: {str(e)}")
            logging.error(f"Error saving activity log: {str(e)}")
        
        # 17. Save meeting minutes
        try:
            minutes_ws = sheet.worksheet("meeting_minutes")
            minutes_data = [st.session_state.meeting_minutes.columns.tolist()] + st.session_state.meeting_minutes.values.tolist()
            minutes_ws.clear()
            minutes_ws.update(minutes_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Meeting minutes: {str(e)}")
            logging.error(f"Error saving meeting minutes: {str(e)}")
        
        # 18. Save user notifications
        try:
            notifications_ws = sheet.worksheet("user_notifications")
            notifications_data = [st.session_state.user_notifications.columns.tolist()] + st.session_state.user_notifications.values.tolist()
            notifications_ws.clear()
            notifications_ws.update(notifications_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"User notifications: {str(e)}")
            logging.error(f"Error saving user notifications: {str(e)}")
        
        # Log results
        total_worksheet = 18
        logging.info(f"Data save complete. Success: {success_count}/{total_worksheet}")
        
        if success_count == total_worksheet:
            return True, "All data saved successfully to Google Sheets"
        elif success_count > 0:
            return False, f"Partial save completed. {success_count}/{total_worksheet} worksheets updated. Errors: {', '.join(error_messages[:3])}{'...' if len(error_messages) > 3 else ''}"
        else:
            return False, f"Failed to save any data. Errors: {', '.join(error_messages[:3])}{'...' if len(error_messages) > 3 else ''}"
    
    except Exception as e:
        error_msg = f"Critical error during data save: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return False, error_msg

def load_all_data(sheet):
    """
    Load ALL application data from Google Sheets with comprehensive error handling.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not sheet:
        return False, "No Google Sheets connection available"
    
    try:
        # Track loading progress
        success_count = 0
        error_messages = []
        
        # 1. Load users
        try:
            users_data = get_worksheet_data(sheet, "users")
            st.session_state.users = {}
            for row in users_data:
                if row["username"]:  # Skip empty rows
                    st.session_state.users[row["username"]] = {
                        "password_hash": row["password_hash"],
                        "role": row["role"],
                        "created_at": row["created_at"],
                        "last_login": row["last_login"] if row["last_login"] else None,
                        "group": row.get("group", ""),
                        "email": row.get("email", "")
                    }
            success_count += 1
        except Exception as e:
            error_messages.append(f"Users: {str(e)}")
            logging.error(f"Error loading users: {str(e)}")
        
        # 2. Load attendance
        try:
            att_data = get_worksheet_data(sheet, "attendance")
            st.session_state.attendance = pd.DataFrame(att_data)
            st.session_state.meeting_names = [
                col for col in st.session_state.attendance.columns 
                if col != "Name"
            ]
            success_count += 1
        except Exception as e:
            error_messages.append(f"Attendance: {str(e)}")
            logging.error(f"Error loading attendance: {str(e)}")
        
        # 3. Load credit data
        try:
            credit_data = get_worksheet_data(sheet, "credit_data")
            st.session_state.credit_data = pd.DataFrame(credit_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Credit data: {str(e)}")
            logging.error(f"Error loading credit data: {str(e)}")
        
        # 4. Load reward data
        try:
            reward_data = get_worksheet_data(sheet, "reward_data")
            st.session_state.reward_data = pd.DataFrame(reward_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Reward data: {str(e)}")
            logging.error(f"Error loading reward data: {str(e)}")
        
        # 5. Load scheduled events
        try:
            scheduled_data = get_worksheet_data(sheet, "scheduled_events")
            st.session_state.scheduled_events = pd.DataFrame(scheduled_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Scheduled events: {str(e)}")
            logging.error(f"Error loading scheduled events: {str(e)}")
        
        # 6. Load occasional events
        try:
            occasional_data = get_worksheet_data(sheet, "occasional_events")
            st.session_state.occasional_events = pd.DataFrame(occasional_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Occasional events: {str(e)}")
            logging.error(f"Error loading occasional events: {str(e)}")
        
        # 7. Load money transactions
        try:
            money_data = get_worksheet_data(sheet, "money_data")
            st.session_state.money_data = pd.DataFrame(money_data)
            # Convert amount to numeric if possible
            if "Amount" in st.session_state.money_data.columns:
                st.session_state.money_data["Amount"] = pd.to_numeric(
                    st.session_state.money_data["Amount"], errors="coerce"
                )
            success_count += 1
        except Exception as e:
            error_messages.append(f"Money data: {str(e)}")
            logging.error(f"Error loading money data: {str(e)}")
        
        # 8. Load calendar events
        try:
            calendar_data = get_worksheet_data(sheet, "calendar_events")
            st.session_state.calendar_events = {}
            for row in calendar_data:
                if row["date"]:  # Skip empty rows
                    st.session_state.calendar_events[row["date"]] = [
                        row["event"], row.get("group", "")
                    ]
            success_count += 1
        except Exception as e:
            error_messages.append(f"Calendar events: {str(e)}")
            logging.error(f"Error loading calendar events: {str(e)}")
        
        # 9. Load announcements
        try:
            announcements_data = get_worksheet_data(sheet, "announcements")
            st.session_state.announcements = []
            for row in announcements_data:
                if row["title"]:  # Skip empty rows
                    st.session_state.announcements.append({
                        "title": row["title"],
                        "text": row["text"],
                        "time": row["time"],
                        "author": row["author"],
                        "group": row.get("group", "")
                    })
            # Sort announcements by time (newest first)
            st.session_state.announcements.sort(key=lambda x: x["time"], reverse=True)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Announcements: {str(e)}")
            logging.error(f"Error loading announcements: {str(e)}")
        
        # 10. Load configuration
        try:
            config_data = get_worksheet_data(sheet, "config")
            st.session_state.config = {"show_signup": True, "app_version": APP_VERSION}
            for row in config_data:
                if row["key"]:  # Skip empty rows
                    # Convert string back to appropriate type
                    value = row["value"]
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    elif re.match(r'^\d+\.\d+$', value):
                        value = float(value)
                    st.session_state.config[row["key"]] = value
            success_count += 1
        except Exception as e:
            error_messages.append(f"Config: {str(e)}")
            logging.error(f"Error loading config: {str(e)}")
        
        # 11. Load groups
        try:
            groups_data = get_worksheet_data(sheet, "groups")
            groups = {g: [] for g in GROUP_NAMES}
            group_codes = {g: generate_group_code(g) for g in GROUP_NAMES}
            
            for row in groups_data:
                if row["group"] and row["group"] != "group_codes":
                    groups[row["group"]] = row["members"].split(", ") if row["members"] else []
                elif row["group"] == "group_codes" and row["members"]:
                    # Parse group codes from string representation
                    try:
                        group_codes = eval(row["members"])
                    except:
                        logging.warning("Could not parse group codes, using defaults")
            
            st.session_state.groups = groups
            st.session_state.group_codes = group_codes
            success_count += 1
        except Exception as e:
            error_messages.append(f"Groups: {str(e)}")
            logging.error(f"Error loading groups: {str(e)}")
        
        # 12. Load group leaders
        try:
            leaders_data = get_worksheet_data(sheet, "group_leaders")
            leaders = {g: "" for g in GROUP_NAMES}
            for row in leaders_data:
                if row["group"] in leaders:
                    leaders[row["group"]] = row["leader"] if row["leader"] else ""
            st.session_state.group_leaders = leaders
            success_count += 1
        except Exception as e:
            error_messages.append(f"Group leaders: {str(e)}")
            logging.error(f"Error loading group leaders: {str(e)}")
        
        # 13. Load group earnings
        try:
            earnings_data = get_worksheet_data(sheet, "group_earnings")
            st.session_state.group_earnings = pd.DataFrame(earnings_data)
            # Convert amount to numeric if possible
            if "Amount" in st.session_state.group_earnings.columns:
                st.session_state.group_earnings["Amount"] = pd.to_numeric(
                    st.session_state.group_earnings["Amount"], errors="coerce"
                )
            success_count += 1
        except Exception as e:
            error_messages.append(f"Group earnings: {str(e)}")
            logging.error(f"Error loading group earnings: {str(e)}")
        
        # 14. Load reimbursement requests
        try:
            reimburse_data = get_worksheet_data(sheet, "reimbursement_requests")
            st.session_state.reimbursement_requests = pd.DataFrame(reimburse_data)
            # Convert amount to numeric if possible
            if "Amount" in st.session_state.reimbursement_requests.columns:
                st.session_state.reimbursement_requests["Amount"] = pd.to_numeric(
                    st.session_state.reimbursement_requests["Amount"], errors="coerce"
                )
            success_count += 1
        except Exception as e:
            error_messages.append(f"Reimbursement requests: {str(e)}")
            logging.error(f"Error loading reimbursement requests: {str(e)}")
        
        # 15. Load event approval requests
        try:
            events_data = get_worksheet_data(sheet, "event_approval_requests")
            st.session_state.event_approval_requests = pd.DataFrame(events_data)
            # Convert budget to numeric if possible
            if "Budget" in st.session_state.event_approval_requests.columns:
                st.session_state.event_approval_requests["Budget"] = pd.to_numeric(
                    st.session_state.event_approval_requests["Budget"], errors="coerce"
                )
            success_count += 1
        except Exception as e:
            error_messages.append(f"Event requests: {str(e)}")
            logging.error(f"Error loading event requests: {str(e)}")
        
        # 16. Load activity log
        try:
            activity_data = get_worksheet_data(sheet, "activity_log")
            st.session_state.activity_log = pd.DataFrame(activity_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Activity log: {str(e)}")
            logging.error(f"Error loading activity log: {str(e)}")
        
        # 17. Load meeting minutes
        try:
            minutes_data = get_worksheet_data(sheet, "meeting_minutes")
            st.session_state.meeting_minutes = pd.DataFrame(minutes_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Meeting minutes: {str(e)}")
            logging.error(f"Error loading meeting minutes: {str(e)}")
        
        # 18. Load user notifications
        try:
            notifications_data = get_worksheet_data(sheet, "user_notifications")
            st.session_state.user_notifications = pd.DataFrame(notifications_data)
            
            # Update current user's unread notifications
            if st.session_state.user:
                user_notifs = st.session_state.user_notifications[
                    (st.session_state.user_notifications["Username"] == st.session_state.user) &
                    (st.session_state.user_notifications["Read Status"] == "Unread")
                ]
                st.session_state.unread_notifications = user_notifs.to_dict("records")
                st.session_state.notification_count = len(st.session_state.unread_notifications)
                
            success_count += 1
        except Exception as e:
            error_messages.append(f"User notifications: {str(e)}")
            logging.error(f"Error loading user notifications: {str(e)}")
        
        # Check if we have critical data
        critical_data_missing = not st.session_state.users or st.session_state.attendance.empty
        
        # Log results
        total_worksheet = 18
        logging.info(f"Data load complete. Success: {success_count}/{total_worksheet}")
        
        if critical_data_missing:
            return False, "Critical data (users or attendance) is missing or corrupted"
        elif success_count == total_worksheet:
            return True, "All data loaded successfully from Google Sheets"
        elif success_count > 0:
            return True, f"Loaded most data. {success_count}/{total_worksheet} worksheets loaded. Some features may be limited. Errors: {', '.join(error_messages[:3])}{'...' if len(error_messages) > 3 else ''}"
        else:
            return False, f"Failed to load any data. Errors: {', '.join(error_messages[:3])}{'...' if len(error_messages) > 3 else ''}"
    
    except Exception as e:
        error_msg = f"Critical error during data load: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return False, error_msg

# ------------------------------
# User Authentication & Management
# ------------------------------
def hash_password(password):
    """
    Hash a password using bcrypt for secure storage.
    
    Args:
        password (str): Plain text password
        
    Returns:
        str: Hashed password
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """
    Verify a plain text password against a hashed password.
    
    Args:
        password (str): Plain text password to verify
        hashed_password (str): Stored hashed password
        
    Returns:
        bool: True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except:
        return False

def validate_password(password):
    """
    Validate password strength according to security policies.
    
    Args:
        password (str): Password to validate
        
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"

def create_user(username, password, group_code, email=None):
    """
    Create a new user with group assignment via code.
    
    Args:
        username (str): New username
        password (str): New password
        group_code (str): Group access code
        email (str, optional): User email
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # Validate username
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"
    
    # Validate password
    pass_valid, pass_msg = validate_password(password)
    if not pass_valid:
        return False, pass_msg
    
    # Verify group code
    group = None
    for g, code in st.session_state.group_codes.items():
        if group_code == code:
            group = g
            break
    
    if not group:
        return False, "Invalid group code. Please check and try again."
    
    # Check if user already exists
    if username in st.session_state.users:
        return False, "Username already exists. Please choose another."
    
    # Create user record
    current_time = datetime.now().isoformat()
    st.session_state.users[username] = {
        "password_hash": hash_password(password),
        "role": "user",  # New users start with basic role
        "created_at": current_time,
        "last_login": None,
        "group": group,
        "email": email or f"{username.lower()}@school.edu"
    }
    
    # Add user to group
    if username not in st.session_state.groups[group]:
        st.session_state.groups[group].append(username)
        # Sort group members alphabetically
        st.session_state.groups[group].sort()
    
    # Log activity
    log_activity(f"create_user", f"Created new user {username} in group {group}")
    
    return True, f"User {username} created successfully in {group}. You can now log in."

def update_user_password(username, current_password, new_password):
    """
    Update a user's password after verification.
    
    Args:
        username (str): Username
        current_password (str): Current password for verification
        new_password (str): New password
        
    Returns:
        tuple: (success: bool, message: str)
    """
    if username not in st.session_state.users:
        return False, "User not found"
    
    # Verify current password
    if not verify_password(current_password, st.session_state.users[username]["password_hash"]):
        return False, "Current password is incorrect"
    
    # Validate new password
    pass_valid, pass_msg = validate_password(new_password)
    if not pass_valid:
        return False, pass_msg
    
    # Check if new password is different from current
    if verify_password(new_password, st.session_state.users[username]["password_hash"]):
        return False, "New password must be different from current password"
    
    # Update password
    st.session_state.users[username]["password_hash"] = hash_password(new_password)
    
    # Log activity
    log_activity(f"update_password", f"Updated password for user {username}")
    
    return True, "Password updated successfully"

def reset_user_password(username, admin_password):
    """
    Admin function to reset a user's password.
    
    Args:
        username (str): Username to reset
        admin_password (str): Admin's password for verification
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # Verify admin credentials
    if not st.session_state.user or not is_admin():
        return False, "You must be an admin to reset passwords"
    
    admin_user = st.session_state.user
    if not verify_password(admin_password, st.session_state.users[admin_user]["password_hash"]):
        return False, "Admin password is incorrect"
    
    if username not in st.session_state.users:
        return False, "User not found"
    
    # Generate temporary password
    temp_password = ''.join(random.choices(
        string.ascii_uppercase + string.ascii_lowercase + string.digits + "!@#$%",
        k=10
    ))
    
    # Update password
    st.session_state.users[username]["password_hash"] = hash_password(temp_password)
    
    # Log activity
    log_activity(f"reset_password", f"Admin reset password for user {username}")
    
    # Send notification to user (in-app)
    send_notification(
        username,
        "Your password has been reset",
        f"Your password was reset by an administrator. Your temporary password is: {temp_password}\nPlease change it after logging in."
    )
    
    return True, f"Password for {username} has been reset. Temporary password: {temp_password}"

def render_login_signup():
    """
    Render login and signup forms with validation and error handling.
    
    Returns:
        bool: True if login successful, False otherwise
    """
    st.title("SCIS Student Council Management System")
    st.write(f"Version: {APP_VERSION}")
    
    # Check for login timeout
    if st.session_state.login_attempts >= 5:
        now = datetime.now()
        if not st.session_state.last_login_attempt or \
           (now - st.session_state.last_login_attempt).total_seconds() > 300:  # 5 minutes
            # Reset after 5 minutes
            st.session_state.login_attempts = 0
            st.session_state.last_login_attempt = None
        else:
            minutes_remaining = int(5 - (now - st.session_state.last_login_attempt).total_seconds() / 60)
            st.error(f"Too many failed login attempts. Please try again in {minutes_remaining} minutes.")
            return False
    
    # Create tabs for login and signup
    login_tab, signup_tab, forgot_tab = st.tabs(["Login", "Sign Up", "Forgot Password"])
    
    with login_tab:
        st.subheader("Account Login")
        
        username = st.text_input("Username", key="login_username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
        
        col_login, col_clear = st.columns(2)
        with col_login:
            login_btn = st.button("Login", key="login_btn", use_container_width=True)
        
        with col_clear:
            if st.button("Clear", key="clear_login", use_container_width=True, type="secondary"):
                st.session_state.login_attempts = 0
                st.rerun()
        
        if login_btn:
            if not username or not password:
                st.error("Please enter both username and password")
                return False
            
            # Record attempt time
            st.session_state.last_login_attempt = datetime.now()
            
            # Check creator credentials
            creator_creds = st.secrets.get("creator", {})
            if username == creator_creds.get("username") and password == creator_creds.get("password"):
                # Special case for creator
                st.session_state.user = username
                st.session_state.role = "creator"
                st.session_state.current_group = ""
                
                # Update last login if user exists in system
                if username in st.session_state.users:
                    st.session_state.users[username]["last_login"] = datetime.now().isoformat()
                    save_all_data(connect_gsheets())
                
                log_activity("login", "Creator login successful")
                st.success("Logged in as Creator!")
                return True
            
            # Check regular users
            if username in st.session_state.users:
                # Verify password
                if verify_password(password, st.session_state.users[username]["password_hash"]):
                    # Successful login
                    st.session_state.user = username
                    st.session_state.role = st.session_state.users[username]["role"]
                    st.session_state.current_group = st.session_state.users[username].get("group", "")
                    
                    # Update last login
                    st.session_state.users[username]["last_login"] = datetime.now().isoformat()
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    
                    # Reset login attempts
                    st.session_state.login_attempts = 0
                    
                    log_activity("login", f"User {username} logged in successfully")
                    st.success(f"Welcome back, {username}!")
                    return True
                else:
                    # Failed login - incorrect password
                    st.session_state.login_attempts += 1
                    remaining_attempts = 5 - st.session_state.login_attempts
                    st.error(f"Incorrect password. {remaining_attempts} attempt(s) remaining.")
                    log_activity("login_failure", f"Login failed for {username} - incorrect password")
            else:
                # Failed login - user not found
                st.session_state.login_attempts += 1
                remaining_attempts = 5 - st.session_state.login_attempts
                st.error(f"Username not found. {remaining_attempts} attempt(s) remaining.")
                log_activity("login_failure", f"Login failed for unknown user: {username}")
        
        return False
    
    with signup_tab:
        if not st.session_state.config.get("show_signup", True):
            st.info("Signup is currently closed. Please contact an administrator to create an account.")
            return False
            
        st.subheader("Create New Account")
        
        new_username = st.text_input("Choose Username", key="new_username", placeholder="3+ characters, letters/numbers/underscores")
        new_email = st.text_input("Email Address", key="new_email", placeholder="school email preferred")
        new_password = st.text_input("Create Password", type="password", key="new_password", 
                                    placeholder="At least 8 chars with uppercase, number and special char")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        group_code = st.text_input("Enter Group Code", key="group_code", placeholder="Provided by your group leader")
        
        # Password requirements info
        with st.expander("Password Requirements"):
            st.write(f"- At least {MIN_PASSWORD_LENGTH} characters")
            st.write("- At least one uppercase letter (A-Z)")
            st.write("- At least one lowercase letter (a-z)")
            st.write("- At least one number (0-9)")
            st.write("- At least one special character (!@#$%^&*(), etc.)")
        
        if st.button("Create Account", key="create_account"):
            # Validate inputs
            if not new_username or not new_password or not confirm_password or not group_code:
                st.error("Please fill in all required fields (username, password, confirm password, group code)")
                return False
            
            if new_password != confirm_password:
                st.error("Passwords do not match. Please try again.")
                return False
            
            # Validate email format if provided
            if new_email and not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', new_email):
                st.error("Please enter a valid email address")
                return False
            
            # Create user
            success, msg = create_user(new_username, new_password, group_code, new_email)
            if success:
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(f"{msg}")
                
                # Send welcome notification
                send_notification(
                    new_username,
                    "Welcome to the Student Council System",
                    "Your account has been created successfully. You can now log in and start using the system."
                )
            else:
                st.error(msg)
    
    with forgot_tab:
        st.subheader("Reset Password")
        st.write("Enter your username to receive a password reset link from an administrator.")
        
        username = st.text_input("Username", key="forgot_username")
        
        if st.button("Request Password Reset", key="request_reset"):
            if not username:
                st.error("Please enter your username")
                return False
                
            if username not in st.session_state.users:
                st.error("Username not found")
                return False
            
            # Record reset request
            log_activity("password_reset_request", f"Password reset requested for {username}")
            
            # Notify admins about reset request
            admin_users = [u for u, details in st.session_state.users.items() if details["role"] in ["admin", "creator"]]
            for admin in admin_users:
                send_notification(
                    admin,
                    "Password Reset Request",
                    f"User {username} has requested a password reset. Please review and process this request."
                )
            
            st.success("Password reset request submitted. An administrator will process your request.")
    
    return False

# ------------------------------
# Group Management Functions
# ------------------------------
def move_user_between_groups(username, from_group, to_group):
    """
    Move a user from one group to another with validation.
    
    Args:
        username (str): User to move
        from_group (str): Current group
        to_group (str): Target group
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # Validate groups
    if from_group not in GROUP_NAMES or to_group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    if from_group == to_group:
        return False, "Source and target groups must be different"
    
    # Validate user is in source group
    if username not in st.session_state.groups[from_group]:
        return False, f"User {username} is not in group {from_group}"
    
    # Remove from current group
    st.session_state.groups[from_group].remove(username)
    st.session_state.groups[from_group].sort()  # Keep sorted
    
    # Add to new group if not already present
    if username not in st.session_state.groups[to_group]:
        st.session_state.groups[to_group].append(username)
        st.session_state.groups[to_group].sort()  # Keep sorted
    
    # Update user's group in their profile
    if username in st.session_state.users:
        st.session_state.users[username]["group"] = to_group
        
        # If user was a leader of old group, remove them
        if st.session_state.group_leaders.get(from_group) == username:
            # Promote another member or clear
            if st.session_state.groups[from_group]:
                new_leader = st.session_state.groups[from_group][0]
                st.session_state.group_leaders[from_group] = new_leader
                send_notification(
                    new_leader,
                    "You are now group leader",
                    f"You have been automatically promoted to group leader of {from_group}."
                )
            else:
                st.session_state.group_leaders[from_group] = ""
    
    # Log activity
    log_activity(f"move_user_group", f"Moved {username} from {from_group} to {to_group}")
    
    # Send notification to user
    send_notification(
        username,
        "Group Assignment Updated",
        f"You have been moved from {from_group} to {to_group}."
    )
    
    return True, f"Moved {username} from {from_group} to {to_group} successfully"

def set_group_leader(group, username):
    """
    Set a user as group leader with validation.
    
    Args:
        group (str): Group to update
        username (str): User to set as leader
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # Validate group
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    # Validate user exists
    if username not in st.session_state.users:
        return False, f"User {username} not found"
    
    # Validate user is in group
    if username not in st.session_state.groups[group]:
        return False, f"User {username} is not a member of {group}"
    
    # Get previous leader
    prev_leader = st.session_state.group_leaders.get(group, "")
    
    # Update leader
    st.session_state.group_leaders[group] = username
    
    # Update user role
    st.session_state.users[username]["role"] = "group_leader"
    
    # Log activity
    log_activity(f"set_group_leader", f"Set {username} as leader of {group}")
    
    # Send notifications
    send_notification(
        username,
        "You are now Group Leader",
        f"You have been designated as the group leader of {group}."
    )
    
    if prev_leader and prev_leader != username and prev_leader in st.session_state.users:
        # Demote previous leader if they exist and are different
        if st.session_state.users[prev_leader]["role"] == "group_leader":
            st.session_state.users[prev_leader]["role"] = "user"
        
        send_notification(
            prev_leader,
            "Group Leader Change",
            f"You are no longer the group leader of {group}. {username} is now the group leader."
        )
    
    return True, f"Successfully set {username} as leader of {group}"

def regenerate_group_code(group):
    """
    Generate a new code for a group.
    
    Args:
        group (str): Group to regenerate code for
        
    Returns:
        tuple: (success: bool, message: str)
    """
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    # Generate new code
    new_code = generate_group_code(group)
    st.session_state.group_codes[group] = new_code
    
    # Log activity
    log_activity(f"regenerate_group_code", f"Regenerated code for {group}")
    
    # Notify group leader
    leader = st.session_state.group_leaders.get(group, "")
    if leader:
        send_notification(
            leader,
            "Group Code Updated",
            f"The access code for {group} has been regenerated. New code: {new_code}"
        )
    
    return True, f"New code for {group}: {new_code}"

def record_group_earning(group, amount, description):
    """
    Record earnings for a group with verification workflow.
    
    Args:
        group (str): Group earning the funds
        amount (float): Amount earned
        description (str): Description of earnings source
        
    Returns:
        tuple: (success: bool, message: str)
    """
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    if amount <= 0:
        return False, "Amount must be greater than zero"
    
    if not description or len(description) < 5:
        return False, "Please provide a meaningful description (at least 5 characters)"
    
    # Create new earning record
    new_entry = pd.DataFrame([{
        "Group": group,
        "Date": date.today().strftime("%Y-%m-%d"),
        "Amount": amount,
        "Description": description,
        "Verified": "Pending",
        "Verified By": "",
        "Submitted By": st.session_state.user
    }])
    
    # Add to earnings data
    st.session_state.group_earnings = pd.concat(
        [st.session_state.group_earnings, new_entry], ignore_index=True
    )
    
    # Log activity
    log_activity(f"record_group_earning", f"Recorded ${amount} earning for {group}: {description}")
    
    # Notify admins about pending verification
    admin_users = [u for u, details in st.session_state.users.items() if details["role"] in ["admin", "creator"]]
    for admin in admin_users:
        send_notification(
            admin,
            "New Earnings to Verify",
            f"{group} has submitted earnings of ${amount} for verification."
        )
    
    return True, "Earnings recorded successfully and are pending verification"

def verify_group_earning(earning_index, verify_status, notes=""):
    """
    Verify or reject a group's earnings submission.
    
    Args:
        earning_index (int): Index of earning record
        verify_status (str): "Verified" or "Rejected"
        notes (str, optional): Admin notes
        
    Returns:
        tuple: (success: bool, message: str)
    """
    if verify_status not in ["Verified", "Rejected"]:
        return False, "Status must be either Verified or Rejected"
    
    if earning_index < 0 or earning_index >= len(st.session_state.group_earnings):
        return False, "Invalid earning record specified"
    
    # Update the record
    earning = st.session_state.group_earnings.iloc[earning_index]
    st.session_state.group_earnings.at[earning_index, "Verified"] = verify_status
    st.session_state.group_earnings.at[earning_index, "Verified By"] = st.session_state.user
    st.session_state.group_earnings.at[earning_index, "Admin Notes"] = notes
    
    # If verified, add to financial records
    if verify_status == "Verified":
        group = earning["Group"]
        amount = earning["Amount"]
        description = f"Earnings from: {earning['Description']}"
        
        new_transaction = pd.DataFrame([{
            "Amount": amount,
            "Description": description,
            "Date": date.today().strftime("%Y-%m-%d"),
            "Handled By": st.session_state.user,
            "Group": group,
            "Category": "Income"
        }])
        
        st.session_state.money_data = pd.concat(
            [st.session_state.money_data, new_transaction], ignore_index=True
        )
    
    # Log activity
    log_activity(f"verify_earning", f"{verify_status} earning record {earning_index} for {earning['Group']}")
    
    # Notify submitter
    submitter = earning.get("Submitted By", "")
    if submitter:
        send_notification(
            submitter,
            f"Earnings {verify_status}",
            f"Your earnings submission for ${earning['Amount']} has been {verify_status.lower()}. {notes}"
        )
    
    return True, f"Earnings {verify_status.lower()} successfully"

# ------------------------------
# Request Management Functions
# ------------------------------
def submit_reimbursement_request(group, requester, amount, purpose):
    """
    Submit a new reimbursement request with validation.
    
    Args:
        group (str): Group requesting reimbursement
        requester (str): Username of requester
        amount (float): Amount to reimburse
        purpose (str): Purpose of expenditure
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # Validate inputs
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    if amount <= 0:
        return False, "Reimbursement amount must be greater than zero"
    
    max_amount = st.session_state.config.get("max_reimbursement", REIMBURSEMENT_LIMIT)
    if amount > max_amount:
        return False, f"Amount exceeds maximum reimbursement limit of ${max_amount}. Please contact an administrator for special approval."
    
    if not purpose or len(purpose) < 10:
        return False, "Please provide a detailed purpose (at least 10 characters)"
    
    # Generate request ID
    request_id = f"REIMB-{random.randint(1000, 9999)}"
    
    # Create new request
    new_request = pd.DataFrame([{
        "Request ID": request_id,
        "Group": group,
        "Requester": requester,
        "Amount": amount,
        "Purpose": purpose,
        "Date Submitted": datetime.now().isoformat(),
        "Status": "Pending",
        "Admin Notes": "",
        "Reviewed By": ""
    }])
    
    # Add to requests
    st.session_state.reimbursement_requests = pd.concat(
        [st.session_state.reimbursement_requests, new_request], ignore_index=True
    )
    
    # Log activity
    log_activity(f"submit_reimbursement", f"Submitted reimbursement {request_id} for ${amount}")
    
    # Notify admins
    admin_users = [u for u, details in st.session_state.users.items() if details["role"] in ["admin", "creator"]]
    for admin in admin_users:
        send_notification(
            admin,
            "New Reimbursement Request",
            f"{group} has requested ${amount} reimbursement. Request ID: {request_id}"
        )
    
    return True, f"Reimbursement request {request_id} submitted successfully"

def submit_event_approval_request(group, requester, event_name, description, 
                                 proposed_date, budget, expected_attendance):
    """
    Submit a new event approval request.
    
    Args:
        group (str): Group requesting event approval
        requester (str): Username of requester
        event_name (str): Name of event
        description (str): Event description
        proposed_date (str): Proposed date (YYYY-MM-DD)
        budget (float): Estimated budget
        expected_attendance (int): Expected number of attendees
        
    Returns:
        tuple: (success: bool, message: str)
    """
    # Validate inputs
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    if not event_name or len(event_name) < 3:
        return False, "Please provide a valid event name (at least 3 characters)"
    
    if not description or len(description) < 20:
        return False, "Please provide a detailed description (at least 20 characters)"
    
    # Validate date
    try:
        event_date = datetime.strptime(proposed_date, "%Y-%m-%d").date()
        if event_date < date.today():
            return False, "Proposed date cannot be in the past"
        if (event_date - date.today()).days > 90:
            return False, "Events cannot be scheduled more than 90 days in advance"
    except ValueError:
        return False, "Invalid date format. Please use YYYY-MM-DD"
    
    # Validate budget
    if budget < 0:
        return False, "Budget cannot be negative"
    
    max_budget = st.session_state.config.get("max_event_budget", EVENT_BUDGET_LIMIT)
    if budget > max_budget:
        st.warning(f"This budget exceeds the standard limit of ${max_budget}. Special approval will be required.")
    
    # Validate attendance
    if expected_attendance <= 0:
        return False, "Expected attendance must be greater than zero"
    
    # Generate request ID
    request_id = f"EVENT-{random.randint(1000, 9999)}"
    
    # Create new request
    new_request = pd.DataFrame([{
        "Request ID": request_id,
        "Group": group,
        "Requester": requester,
        "Event Name": event_name,
        "Description": description,
        "Proposed Date": proposed_date,
        "Budget": budget,
        "Expected Attendance": expected_attendance,
        "Date Submitted": datetime.now().isoformat(),
        "Status": "Pending",
        "Admin Notes": "",
        "Reviewed By": ""
    }])
    
    # Add to requests
    st.session_state.event_approval_requests = pd.concat(
        [st.session_state.event_approval_requests, new_request], ignore_index=True
    )
    
    # Log activity
    log_activity(f"submit_event_request", f"Submitted event request {request_id}: {event_name}")
    
    # Notify admins
    admin_users = [u for u, details in st.session_state.users.items() if details["role"] in ["admin", "creator"]]
    for admin in admin_users:
        send_notification(
            admin,
            "New Event Approval Request",
            f"{group} has requested approval for {event_name}. Request ID: {request_id}"
        )
    
    return True, f"Event approval request {request_id} submitted successfully"

def update_request_status(request_type, request_id, new_status, admin_notes=""):
    """
    Update status of a reimbursement or event request.
    
    Args:
        request_type (str): "reimbursement" or "event"
        request_id (str): ID of request to update
        new_status (str): New status (Approved, Denied, etc.)
        admin_notes (str, optional): Notes from administrator
        
    Returns:
        tuple: (success: bool, message: str)
    """
    valid_types = ["reimbursement", "event"]
    if request_type not in valid_types:
        return False, f"Invalid request type. Must be one of: {', '.join(valid_types)}"
    
    valid_statuses = ["Pending", "Approved", "Denied", "In Review", "Returned for Revision"]
    if new_status not in valid_statuses:
        return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
    
    # Get appropriate DataFrame
    if request_type == "reimbursement":
        df = st.session_state.reimbursement_requests
        id_column = "Request ID"
    else:
        df = st.session_state.event_approval_requests
        id_column = "Request ID"
    
    # Find the request
    mask = df[id_column] == request_id
    if not mask.any():
        return False, f"No {request_type} request found with ID: {request_id}"
    
    # Update the request
    index = df.index[mask].tolist()[0]
    current_status = df.at[index, "Status"]
    
    if current_status == new_status:
        return False, f"Request is already {new_status}"
    
    # Update status and metadata
    if request_type == "reimbursement":
        st.session_state.reimbursement_requests.at[index, "Status"] = new_status
        st.session_state.reimbursement_requests.at[index, "Admin Notes"] = admin_notes
        st.session_state.reimbursement_requests.at[index, "Reviewed By"] = st.session_state.user
    else:
        st.session_state.event_approval_requests.at[index, "Status"] = new_status
        st.session_state.event_approval_requests.at[index, "Admin Notes"] = admin_notes
        st.session_state.event_approval_requests.at[index, "Reviewed By"] = st.session_state.user
    
    # If approved, take additional actions
    request_data = df.iloc[index]
    requester = request_data["Requester"]
    group = request_data["Group"]
    
    if new_status == "Approved":
        if request_type == "reimbursement":
            # Record as expense
            amount = request_data["Amount"]
            description = f"Reimbursement: {request_data['Purpose']} (Request {request_id})"
            
            new_transaction = pd.DataFrame([{
                "Amount": -float(amount),  # Negative for expense
                "Description": description,
                "Date": date.today().strftime("%Y-%m-%d"),
                "Handled By": st.session_state.user,
                "Group": group,
                "Category": "Expense"
            }])
            
            st.session_state.money_data = pd.concat(
                [st.session_state.money_data, new_transaction], ignore_index=True
            )
        else:
            # Add event to calendar
            event_name = request_data["Event Name"]
            event_date = request_data["Proposed Date"]
            st.session_state.calendar_events[event_date] = [event_name, group]
            
            # Create scheduled event record
            new_event = pd.DataFrame([{
                "Event Name": event_name,
                "Funds Per Event": request_data["Budget"],
                "Frequency Per Month": 1,
                "Total Funds": request_data["Budget"],
                "Responsible Group": group,
                "Last Held": "",
                "Next Scheduled": event_date
            }])
            
            st.session_state.scheduled_events = pd.concat(
                [st.session_state.scheduled_events, new_event], ignore_index=True
            )
    
    # Log activity
    log_activity(f"update_{request_type}_status", f"Updated {request_type} request {request_id} to {new_status}")
    
    # Notify requester
    send_notification(
        requester,
        f"{request_type.capitalize()} Request {new_status}",
        f"Your {request_type} request ({request_id}) has been {new_status.lower()}.\n\nAdmin notes: {admin_notes}"
    )
    
    return True, f"Successfully updated {request_type} request {request_id} to {new_status}"

# ------------------------------
# Notification System
# ------------------------------
def send_notification(username, title, message):
    """
    Send an in-app notification to a user.
    
    Args:
        username (str): User to notify
        title (str): Notification title
        message (str): Notification content
    """
    if username not in st.session_state.users:
        logging.warning(f"Attempted to send notification to non-existent user: {username}")
        return
    
    # Generate notification ID
    notif_id = f"NOTIF-{random.randint(100000, 999999)}"
    
    # Create notification record
    new_notif = pd.DataFrame([{
        "Notification ID": notif_id,
        "Username": username,
        "Title": title,
        "Message": message,
        "Timestamp": datetime.now().isoformat(),
        "Read Status": "Unread"
    }])
    
    # Add to notifications
    st.session_state.user_notifications = pd.concat(
        [st.session_state.user_notifications, new_notif], ignore_index=True
    )
    
    # Update current user's unread count if applicable
    if st.session_state.user == username:
        st.session_state.unread_notifications.append({
            "Notification ID": notif_id,
            "Title": title,
            "Message": message,
            "Timestamp": datetime.now().isoformat()
        })
        st.session_state.notification_count = len(st.session_state.unread_notifications)
    
    logging.info(f"Sent notification {notif_id} to {username}")

def mark_notifications_as_read():
    """Mark all unread notifications for current user as read"""
    if not st.session_state.user:
        return
    
    # Update in session state
    st.session_state.unread_notifications = []
    st.session_state.notification_count = 0
    
    # Update in DataFrame
    mask = (st.session_state.user_notifications["Username"] == st.session_state.user) & \
           (st.session_state.user_notifications["Read Status"] == "Unread")
    
    st.session_state.user_notifications.loc[mask, "Read Status"] = "Read"
    
    # Log activity
    log_activity("mark_notifications_read", "Marked all notifications as read")

# ------------------------------
# Activity Logging
# ------------------------------
def log_activity(action, details):
    """
    Log user actions for audit purposes.
    
    Args:
        action (str): Action performed
        details (str): Details about the action
    """
    new_entry = pd.DataFrame([{
        "Timestamp": datetime.now().isoformat(),
        "User": st.session_state.user or "system",
        "Action": action,
        "Details": details,
        "IP Address": st.session_state.user_ip,
        "Session ID": st.session_state.session_id
    }])
    
    st.session_state.activity_log = pd.concat(
        [st.session_state.activity_log, new_entry], ignore_index=True
    )
    
    # Keep log size manageable by limiting to last 10,000 entries
    if len(st.session_state.activity_log) > 10000:
        st.session_state.activity_log = st.session_state.activity_log.tail(10000).reset_index(drop=True)
    
    logging.info(f"Activity logged - User: {st.session_state.user or 'system'}, Action: {action}, Details: {details}")

# ------------------------------
# Permission Checks
# ------------------------------
def is_admin():
    """Check if current user has admin or creator role"""
    return st.session_state.get("role") in ["admin", "creator"]

def is_creator():
    """Check if current user is the creator (highest privilege)"""
    return st.session_state.get("role") == "creator"

def is_group_leader(group=None):
    """
    Check if current user is a group leader.
    
    Args:
        group (str, optional): Specific group to check leadership for
        
    Returns:
        bool: True if user is a group leader (for specified group if provided)
    """
    if not st.session_state.user:
        return False
        
    if group:
        return st.session_state.group_leaders.get(group) == st.session_state.user
    else:
        # Check if user is leader of any group
        return st.session_state.user in st.session_state.group_leaders.values()

def can_access_group(group):
    """
    Check if current user can access a specific group's data.
    
    Args:
        group (str): Group to check
        
    Returns:
        bool: True if user has access
    """
    if is_admin():
        return True
        
    if not st.session_state.user or not st.session_state.current_group:
        return False
        
    # Users can access their own group
    if group == st.session_state.current_group:
        return True
        
    return False

# ------------------------------
# UI Components & Pages
# ------------------------------
def render_header():
    """Render application header with user info and notifications"""
    col_title, col_user, col_notifs = st.columns([3, 1, 1])
    
    with col_title:
        st.title("SCIS Student Council Management System")
    
    with col_user:
        if st.session_state.user:
            st.write(f"Logged in as: **{st.session_state.user}**")
            st.write(f"Role: **{st.session_state.role.title()}**")
            st.write(f"Group: **{st.session_state.current_group or 'N/A'}**")
    
    with col_notifs:
        if st.session_state.user and st.session_state.notification_count > 0:
            if st.button(f"🔔 Notifications ({st.session_state.notification_count})"):
                with st.expander("Your Notifications", expanded=True):
                    for idx, notif in enumerate(st.session_state.unread_notifications):
                        st.subheader(notif["Title"])
                        st.write(notif["Message"])
                        st.caption(f"Received: {datetime.fromisoformat(notif['Timestamp']).strftime('%Y-%m-%d %H:%M')}")
                        if idx < len(st.session_state.unread_notifications) - 1:
                            st.divider()
                
                if st.button("Mark all as read"):
                    mark_notifications_as_read()
                    st.success("All notifications marked as read")
                    st.rerun()
        elif st.session_state.user:
            st.write("No new notifications")

def render_sidebar():
    """Render sidebar navigation with role-based options"""
    with st.sidebar:
        st.subheader("Navigation")
        
        # Common navigation for all users
        nav_options = [
            "Dashboard", 
            "Calendar", 
            "Announcements",
            "Credits & Rewards",
            "My Group"
        ]
        
        # Add group leader options
        if is_group_leader():
            nav_options.extend([
                "Submit Earnings",
                "Request Reimbursement",
                "Request Event Approval"
            ])
        
        # Add admin options
        if is_admin():
            nav_options.extend([
                "Manage Groups",
                "Financial Overview",
                "Approve Requests",
                "Manage Users",
                "System Settings"
            ])
        
        # Add creator-only options
        if is_creator():
            nav_options.extend(["System Audit", "Data Management"])
        
        # Navigation selection
        selected_tab = st.radio("Go to", nav_options, key="nav_radio")
        
        # Logout button
        if st.button("Logout", use_container_width=True, type="secondary"):
            log_activity("logout", "User logged out")
            st.session_state.user = None
            st.session_state.role = None
            st.session_state.current_group = None
            st.success("Logged out successfully")
            st.rerun()
        
        # Display app info
        st.divider()
        st.caption(f"Version: {APP_VERSION}")
        st.caption("SCIS Student Council © 2023")
        
        return selected_tab

def render_dashboard():
    """Render main dashboard with role-based information"""
    st.header("Dashboard")
    
    # Welcome message
    st.subheader(f"Welcome, {st.session_state.user}!")
    
    # Display announcements
    st.subheader("Recent Announcements")
    announcements_to_show = []
    for ann in st.session_state.announcements[:5]:  # Show up to 5
        # Show announcements for all groups or user's specific group
        if not ann["group"] or ann["group"] == st.session_state.current_group:
            announcements_to_show.append(ann)
    
    if announcements_to_show:
        for ann in announcements_to_show:
            with st.expander(f"{ann['title']} - {ann['author']} ({ann['time'].split(' ')[0]})"):
                st.write(ann["text"])
    else:
        st.info("No announcements available")
    
    st.divider()
    
    # Display upcoming events
    st.subheader("Upcoming Events")
    today = date.today()
    upcoming_events = []
    
    # Get events from calendar
    for event_date_str, event_data in st.session_state.calendar_events.items():
        try:
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
            if event_date >= today:
                days_until = (event_date - today).days
                upcoming_events.append({
                    "date": event_date_str,
                    "event": event_data[0],
                    "group": event_data[1],
                    "days_until": days_until
                })
        except ValueError:
            continue  # Skip invalid dates
    
    # Get events from scheduled events
    for _, row in st.session_state.scheduled_events.iterrows():
        if pd.notna(row["Next Scheduled"]):
            try:
                event_date = datetime.strptime(row["Next Scheduled"], "%Y-%m-%d").date()
                if event_date >= today:
                    days_until = (event_date - today).days
                    upcoming_events.append({
                        "date": row["Next Scheduled"],
                        "event": row["Event Name"],
                        "group": row["Responsible Group"],
                        "days_until": days_until
                    })
            except ValueError:
                continue  # Skip invalid dates
    
    # Sort by days until event
    upcoming_events.sort(key=lambda x: x["days_until"])
    
    if upcoming_events:
        for event in upcoming_events[:5]:  # Show up to 5
            group_label = f" ({event['group']})" if event['group'] else ""
            st.write(f"**{event['date']}** - {event['event']}{group_label}")
            st.caption(f"In {event['days_until']} day(s)" if event['days_until'] > 0 else "Today")
    else:
        st.info("No upcoming events scheduled")
    
    st.divider()
    
    # Display user-specific information
    if st.session_state.user:
        # Find user's credit information
        user_credit = st.session_state.credit_data[
            st.session_state.credit_data["Name"] == st.session_state.user
        ]
        
        if not user_credit.empty:
            st.subheader("Your Credits")
            total_credits = user_credit.iloc[0]["Total_Credits"]
            redeemed_credits = user_credit.iloc[0]["RedeemedCredits"]
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Credits", total_credits)
            with col2:
                st.metric("Redeemed Credits", redeemed_credits)
            
            # Create a simple chart
            fig, ax = plt.subplots(figsize=(10, 3))
            ax.bar(["Total", "Redeemed"], [total_credits, redeemed_credits], color=['#4CAF50', '#FFC107'])
            ax.set_title("Your Credit Summary")
            st.pyplot(fig)
        else:
            st.info("No credit information available for your account")
    
    # Group leader dashboard elements
    if is_group_leader():
        st.divider()
        st.subheader("Group Leader Summary")
        
        # Get the group this leader is responsible for
        leader_group = next(
            (g for g, leader in st.session_state.group_leaders.items() if leader == st.session_state.user),
            None
        )
        
        if leader_group:
            # Show group members
            st.write(f"**{leader_group} Members:** {', '.join(st.session_state.groups[leader_group])}")
            
            # Show pending requests for this group
            pending_reimbursements = st.session_state.reimbursement_requests[
                (st.session_state.reimbursement_requests["Group"] == leader_group) &
                (st.session_state.reimbursement_requests["Status"] == "Pending")
            ]
            
            pending_events = st.session_state.event_approval_requests[
                (st.session_state.event_approval_requests["Group"] == leader_group) &
                (st.session_state.event_approval_requests["Status"] == "Pending")
            ]
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Pending Reimbursements", len(pending_reimbursements))
            with col2:
                st.metric("Pending Event Approvals", len(pending_events))
            
            # Show group earnings
            group_earnings = st.session_state.group_earnings[
                st.session_state.group_earnings["Group"] == leader_group
            ]
            
            if not group_earnings.empty:
                st.subheader(f"{leader_group} Earnings Summary")
                fig, ax = plt.subplots(figsize=(10, 4))
                
                # Group by verification status
                status_counts = group_earnings["Verified"].value_counts()
                ax.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', startangle=90)
                ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                ax.set_title("Earnings by Verification Status")
                st.pyplot(fig)
                
                # Total earnings
                total_earned = group_earnings["Amount"].sum()
                verified_earned = group_earnings[group_earnings["Verified"] == "Verified"]["Amount"].sum()
                
                st.write(f"Total reported earnings: **${total_earned:.2f}**")
                st.write(f"Verified earnings: **${verified_earned:.2f}**")
            else:
                st.info(f"No earnings recorded for {leader_group} yet")
    
    # Admin dashboard elements
    if is_admin():
        st.divider()
        st.subheader("Administrator Summary")
        
        # System overview metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Users", len(st.session_state.users))
        with col2:
            st.metric("Pending Reimbursements", 
                     len(st.session_state.reimbursement_requests[
                         st.session_state.reimbursement_requests["Status"] == "Pending"
                     ]))
        with col3:
            st.metric("Pending Event Approvals",
                     len(st.session_state.event_approval_requests[
                         st.session_state.event_approval_requests["Status"] == "Pending"
                     ]))
        
        # Financial summary
        st.subheader("Financial Overview")
        if not st.session_state.money_data.empty:
            # Calculate totals
            total_income = st.session_state.money_data[
                st.session_state.money_data["Category"] == "Income"
            ]["Amount"].sum()
            
            total_expenses = abs(st.session_state.money_data[
                st.session_state.money_data["Category"] == "Expense"
            ]["Amount"].sum())
            
            net_balance = total_income - total_expenses
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Income", f"${total_income:.2f}")
            with col2:
                st.metric("Total Expenses", f"${total_expenses:.2f}")
            with col3:
                st.metric("Net Balance", f"${net_balance:.2f}")
            
            # Chart for income vs expenses
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.bar(["Income", "Expenses"], [total_income, total_expenses], color=['#4CAF50', '#F44336'])
            ax.set_title("Total Income vs. Expenses")
            st.pyplot(fig)
        else:
            st.info("No financial data available")

def render_calendar():
    """Render interactive calendar view"""
    st.header("Calendar")
    
    # Get current month and year from session state
    current_year, current_month = st.session_state.current_calendar_month
    
    # Navigation buttons
    col_prev, col_current, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("◀ Previous Month"):
            current_month -= 1
            if current_month < 1:
                current_month = 12
                current_year -= 1
            st.session_state.current_calendar_month = (current_year, current_month)
            st.rerun()
    
    with col_current:
        st.subheader(f"{datetime(current_year, current_month, 1).strftime('%B %Y')}")
    
    with col_next:
        if st.button("Next Month ▶"):
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1
            st.session_state.current_calendar_month = (current_year, current_month)
            st.rerun()
    
    # Get first day of month and number of days
    first_day = date(current_year, current_month, 1)
    _, num_days = calendar.monthrange(current_year, current_month)
    
    # Get day of week for first day (0 = Monday, 6 = Sunday)
    first_day_weekday = first_day.weekday()
    
    # Create calendar grid
    calendar_grid = []
    
    # Add empty cells for days before first day of month
    week = [""] * first_day_weekday
    day = 1
    
    # Fill in days of month
    for _ in range(num_days):
        week.append(day)
        day += 1
        if len(week) == 7:
            calendar_grid.append(week)
            week = []
    
    # Add remaining days to complete the last week
    if week:
        week += [""] * (7 - len(week))
        calendar_grid.append(week)
    
    # Create day headers
    day_headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # Display calendar headers
    header_cols = st.columns(7)
    for i, header in enumerate(day_headers):
        with header_cols[i]:
            st.subheader(header)
    
    # Display calendar days
    for week in calendar_grid:
        day_cols = st.columns(7)
        for i, day in enumerate(week):
            with day_cols[i]:
                if day != "":
                    # Highlight today
                    is_today = (day == date.today().day and 
                               current_month == date.today().month and 
                               current_year == date.today().year)
                    
                    # Create a container for each day
                    with st.container(border=True):
                        if is_today:
                            st.markdown(f"**<span style='color: red;'>{day}</span>**", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{day}**")
                        
                        # Check for events on this day
                        event_date_str = f"{current_year}-{current_month:02d}-{day:02d}"
                        if event_date_str in st.session_state.calendar_events:
                            event_name, event_group = st.session_state.calendar_events[event_date_str]
                            st.write(f"📅 {event_name}")
                            st.caption(f"Group: {event_group}")

    # Add new event button (for admins and group leaders)
    st.subheader("\nAdd New Calendar Event")
    with st.form("new_calendar_event"):
        col1, col2 = st.columns(2)
        with col1:
            event_date = st.date_input("Event Date")
            event_group = st.selectbox("Responsible Group", GROUP_NAMES)
        
        with col2:
            event_name = st.text_input("Event Name")
            event_description = st.text_area("Event Description", max_chars=200)
        
        submit_event = st.form_submit_button("Add Event to Calendar")
        
        if submit_event:
            if not event_name or len(event_name) < 3:
                st.error("Please enter a valid event name (at least 3 characters)")
            else:
                event_date_str = event_date.strftime("%Y-%m-%d")
                st.session_state.calendar_events[event_date_str] = [event_name, event_group]
                
                # Log activity
                log_activity("add_calendar_event", f"Added event: {event_name} on {event_date_str}")
                
                # Notify group members
                for member in st.session_state.groups[event_group]:
                    send_notification(
                        member,
                        "New Calendar Event",
                        f"A new event has been scheduled: {event_name} on {event_date_str}"
                    )
                
                st.success(f"Event '{event_name}' added to calendar for {event_date_str}")
                st.rerun()

def render_announcements():
    """Render announcements page with creation capabilities for admins"""
    st.header("Announcements")
    
    # Show all relevant announcements
    for ann in st.session_state.announcements:
        # Show announcements for all groups or user's specific group
        if not ann["group"] or ann["group"] == st.session_state.current_group or is_admin():
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(ann["title"])
                with col2:
                    st.caption(f"Posted: {ann['time']}")
                
                st.write(ann["text"])
                st.caption(f"By: {ann['author']}" + (f" • Group: {ann['group']}" if ann["group"] else ""))
        
    # Admin can create new announcements
    if is_admin():
        st.divider()
        st.subheader("Create New Announcement")
        
        with st.form("new_announcement"):
            ann_title = st.text_input("Announcement Title")
            ann_group = st.selectbox(
                "Target Group (leave as All for system-wide)",
                ["All"] + GROUP_NAMES
            )
            ann_text = st.text_area("Announcement Text", height=150)
            submit_ann = st.form_submit_button("Post Announcement")
            
            if submit_ann:
                if not ann_title or not ann_text:
                    st.error("Please provide both a title and message for your announcement")
                else:
                    new_announcement = {
                        "title": ann_title,
                        "text": ann_text,
                        "time": datetime.now().isoformat(),
                        "author": st.session_state.user,
                        "group": ann_group if ann_group != "All" else ""
                    }
                    
                    st.session_state.announcements.insert(0, new_announcement)
                    
                    # Log activity
                    log_activity("create_announcement", f"Posted announcement: {ann_title}")
                    
                    # Notify relevant users
                    if ann_group == "All":
                        # Notify all users
                        for user in st.session_state.users:
                            send_notification(
                                user,
                                "New Announcement",
                                f"{ann_title}: {ann_text[:100]}..."
                            )
                    else:
                        # Notify only group members
                        for member in st.session_state.groups[ann_group]:
                            send_notification(
                                member,
                                "New Group Announcement",
                                f"{ann_title}: {ann_text[:100]}..."
                            )
                    
                    st.success("Announcement posted successfully!")
                    st.rerun()

def render_credits_rewards():
    """Render credits and rewards management page"""
    st.header("Credits & Rewards System")
    
    # User's own credit information
    st.subheader("Your Credit Balance")
    if st.session_state.user:
        user_credit = st.session_state.credit_data[
            st.session_state.credit_data["Name"] == st.session_state.user
        ]
        
        if not user_credit.empty:
            total_credits = user_credit.iloc[0]["Total_Credits"]
            redeemed_credits = user_credit.iloc[0]["RedeemedCredits"]
            
            st.metric("Available Credits", total_credits - redeemed_credits)
            
            # Reward catalog
            st.subheader("Reward Catalog")
            reward_df = st.session_state.reward_data.copy()
            
            # Add a column to check if user can afford the reward
            reward_df["Affordable"] = reward_df["Cost"] <= (total_credits - redeemed_credits)
            
            # Display rewards
            for _, reward in reward_df.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.subheader(reward["Reward"])
                        st.caption(f"Supplier: {reward['Supplier']}")
                    with col2:
                        st.metric("Cost", f"{reward['Cost']} credits")
                    with col3:
                        st.metric("In Stock", reward["Stock"])
                
                # Redemption button if affordable and in stock
                if reward["Affordable"] and reward["Stock"] > 0:
                    if st.button(f"Redeem {reward['Reward']}", key=f"redeem_{reward['Reward']}"):
                        # Update user's redeemed credits
                        new_redeemed = redeemed_credits + reward["Cost"]
                        user_index = st.session_state.credit_data.index[
                            st.session_state.credit_data["Name"] == st.session_state.user
                        ].tolist()[0]
                        
                        st.session_state.credit_data.at[user_index, "RedeemedCredits"] = new_redeemed
                        st.session_state.credit_data.at[user_index, "Last_Updated"] = datetime.now().strftime("%Y-%m-%d")
                        
                        # Update reward stock
                        reward_index = st.session_state.reward_data.index[
                            st.session_state.reward_data["Reward"] == reward["Reward"]
                        ].tolist()[0]
                        st.session_state.reward_data.at[reward_index, "Stock"] -= 1
                        
                        # Log activity
                        log_activity("redeem_reward", f"Redeemed {reward['Reward']} for {reward['Cost']} credits")
                        
                        # Send confirmation
                        send_notification(
                            st.session_state.user,
                            "Reward Redeemed",
                            f"You have successfully redeemed {reward['Reward']} for {reward['Cost']} credits."
                        )
                        
                        st.success(f"You have successfully redeemed {reward['Reward']}!")
                        st.rerun()
                elif not reward["Affordable"]:
                    st.info("You do not have enough credits for this reward")
                else:
                    st.info("This reward is currently out of stock")
                
                st.divider()
        else:
            st.info("No credit information found for your account")
    
    # Group credit summary for group leaders
    if is_group_leader():
        st.divider()
        st.subheader("Group Credit Summary")
        
        # Get leader's group
        leader_group = next(
            (g for g, leader in st.session_state.group_leaders.items() if leader == st.session_state.user),
            None
        )
        
        if leader_group:
            # Get all members in this group
            group_members = st.session_state.groups[leader_group]
            
            # Filter credit data for group members
            group_credit = st.session_state.credit_data[
                st.session_state.credit_data["Name"].isin(group_members)
            ]
            
            if not group_credit.empty:
                # Display group credit summary
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.bar(group_credit["Name"], group_credit["Total_Credits"])
                ax.set_title(f"Total Credits by {leader_group} Member")
                ax.set_xlabel("Members")
                ax.set_ylabel("Total Credits")
                plt.xticks(rotation=45)
                st.pyplot(fig)
                
                # Show detailed table
                st.dataframe(group_credit)
            else:
                st.info(f"No credit data available for {leader_group} members")
    
    # Admin credit management
    if is_admin():
        st.divider()
        st.subheader("Manage Credits (Admin)")
        
        # Select user to modify
        selected_user = st.selectbox("Select User", st.session_state.users.keys())
        
        # Find user's current credit info or create if missing
        user_credit_mask = st.session_state.credit_data["Name"] == selected_user
        if not user_credit_mask.any():
            # Add new user to credit data
            new_user = pd.DataFrame([{
                "Name": selected_user,
                "Total_Credits": 0,
                "RedeemedCredits": 0,
                "Last_Updated": datetime.now().strftime("%Y-%m-%d")
            }])
            st.session_state.credit_data = pd.concat(
                [st.session_state.credit_data, new_user], ignore_index=True
            )
            user_credit_mask = st.session_state.credit_data["Name"] == selected_user
        
        user_index = st.session_state.credit_data.index[user_credit_mask].tolist()[0]
        current_credits = st.session_state.credit_data.at[user_index, "Total_Credits"]
        
        # Credit adjustment form
        with st.form("adjust_credits"):
            credit_change = st.number_input(
                "Credit Adjustment", 
                value=0, 
                help="Use positive numbers to add credits, negative to remove"
            )
            reason = st.text_input("Reason for Adjustment")
            submit_adjustment = st.form_submit_button("Adjust Credits")
            
            if submit_adjustment:
                if credit_change == 0:
                    st.error("Please enter a non-zero credit adjustment")
                elif not reason:
                    st.error("Please provide a reason for the credit adjustment")
                else:
                    new_total = current_credits + credit_change
                    if new_total < 0:
                        st.error("Cannot reduce credits below zero")
                    else:
                        st.session_state.credit_data.at[user_index, "Total_Credits"] = new_total
                        st.session_state.credit_data.at[user_index, "Last_Updated"] = datetime.now().strftime("%Y-%m-%d")
                        
                        # Log activity
                        log_activity("adjust_credits", f"Adjusted {selected_user}'s credits by {credit_change} - {reason}")
                        
                        # Notify user
                        send_notification(
                            selected_user,
                            "Your Credits Have Changed",
                            f"Your credit balance has been adjusted by {credit_change}. New total: {new_total}\nReason: {reason}"
                        )
                        
                        st.success(f"Successfully adjusted {selected_user}'s credits by {credit_change}")
                        st.rerun()
        
        # Manage rewards catalog
        st.subheader("Manage Rewards Catalog")
        with st.expander("Add New Reward"):
            with st.form("new_reward"):
                reward_name = st.text_input("Reward Name")
                reward_cost = st.number_input("Credit Cost", min_value=1)
                reward_stock = st.number_input("Initial Stock", min_value=0)
                reward_supplier = st.text_input("Supplier")
                submit_reward = st.form_submit_button("Add Reward")
                
                if submit_reward:
                    if not reward_name or not reward_supplier:
                        st.error("Please provide both a reward name and supplier")
                    else:
                        new_reward = pd.DataFrame([{
                            "Reward": reward_name,
                            "Cost": reward_cost,
                            "Stock": reward_stock,
                            "Supplier": reward_supplier
                        }])
                        st.session_state.reward_data = pd.concat(
                            [st.session_state.reward_data, new_reward], ignore_index=True
                        )
                        
                        log_activity("add_reward", f"Added new reward: {reward_name}")
                        st.success(f"New reward '{reward_name}' added successfully")
                        st.rerun()
        
        # Update existing rewards
        st.subheader("Update Existing Rewards")
        reward_to_update = st.selectbox("Select Reward to Update", st.session_state.reward_data["Reward"])
        
        if reward_to_update:
            reward_index = st.session_state.reward_data.index[
                st.session_state.reward_data["Reward"] == reward_to_update
            ].tolist()[0]
            
            with st.form("update_reward"):
                new_cost = st.number_input(
                    "New Credit Cost", 
                    value=int(st.session_state.reward_data.at[reward_index, "Cost"]),
                    min_value=1
                )
                new_stock = st.number_input(
                    "New Stock Level", 
                    value=int(st.session_state.reward_data.at[reward_index, "Stock"]),
                    min_value=0
                )
                new_supplier = st.text_input(
                    "Supplier", 
                    value=st.session_state.reward_data.at[reward_index, "Supplier"]
                )
                submit_update = st.form_submit_button("Update Reward")
                
                if submit_update:
                    if not new_supplier:
                        st.error("Please provide a supplier")
                    else:
                        st.session_state.reward_data.at[reward_index, "Cost"] = new_cost
                        st.session_state.reward_data.at[reward_index, "Stock"] = new_stock
                        st.session_state.reward_data.at[reward_index, "Supplier"] = new_supplier
                        
                        log_activity("update_reward", f"Updated reward: {reward_to_update}")
                        st.success(f"Reward '{reward_to_update}' updated successfully")
                        st.rerun()

def render_my_group():
    """Render page with information about user's group"""
    st.header(f"My Group: {st.session_state.current_group}")
    
    # Basic group information
    if not st.session_state.current_group:
        st.warning("You are not assigned to any group")
        return
    
    # Group leader information
    group_leader = st.session_state.group_leaders.get(st.session_state.current_group, "")
    st.subheader("Group Leader")
    st.write(group_leader if group_leader else "No group leader assigned")
    
    # Group members
    st.subheader("Group Members")
    group_members = st.session_state.groups.get(st.session_state.current_group, [])
    
    if group_members:
        for member in group_members:
            # Highlight current user
            if member == st.session_state.user:
                st.write(f"• {member} (You)")
            # Highlight group leader
            elif member == group_leader:
                st.write(f"• {member} (Leader)")
            else:
                st.write(f"• {member}")
    else:
        st.info("No members in this group")
    
    st.divider()
    
    # Group earnings
    st.subheader("Group Earnings")
    group_earnings = st.session_state.group_earnings[
        st.session_state.group_earnings["Group"] == st.session_state.current_group
    ]
    
    if not group_earnings.empty:
        # Show earnings summary
        total_earned = group_earnings["Amount"].sum()
        verified_earned = group_earnings[group_earnings["Verified"] == "Verified"]["Amount"].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Reported", f"${total_earned:.2f}")
        with col2:
            st.metric("Verified", f"${verified_earned:.2f}")
        
        # Show recent earnings
        st.subheader("Recent Earnings")
        st.dataframe(
            group_earnings.sort_values("Date", ascending=False).head(10),
            column_config={
                "Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Date": st.column_config.DateColumn(),
                "Verified": st.column_config.SelectboxColumn(
                    options=["Pending", "Verified", "Rejected"]
                )
            }
        )
        
        # Earnings chart
        fig, ax = plt.subplots(figsize=(10, 4))
        earnings_by_date = group_earnings.groupby("Date")["Amount"].sum()
        earnings_by_date.plot(kind="bar", ax=ax)
        ax.set_title("Earnings by Date")
        ax.set_xlabel("Date")
        ax.set_ylabel("Amount ($)")
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else:
        st.info("No earnings recorded for this group yet")
    
    st.divider()
    
    # Group requests
    st.subheader("Group Requests")
    
    # Reimbursement requests
    st.subheader("Reimbursements")
    group_reimbursements = st.session_state.reimbursement_requests[
        st.session_state.reimbursement_requests["Group"] == st.session_state.current_group
    ]
    
    if not group_reimbursements.empty:
        st.dataframe(
            group_reimbursements.sort_values("Date Submitted", ascending=False),
            column_config={
                "Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Date Submitted": st.column_config.DatetimeColumn(),
                "Status": st.column_config.SelectboxColumn(
                    options=["Pending", "Approved", "Denied"]
                )
            }
        )
    else:
        st.info("No reimbursement requests submitted by this group")
    
    # Event requests
    st.subheader("Event Approvals")
    group_events = st.session_state.event_approval_requests[
        st.session_state.event_approval_requests["Group"] == st.session_state.current_group
    ]
    
    if not group_events.empty:
        st.dataframe(
            group_events.sort_values("Date Submitted", ascending=False),
            column_config={
                "Budget": st.column_config.NumberColumn(format="$%.2f"),
                "Proposed Date": st.column_config.DateColumn(),
                "Date Submitted": st.column_config.DatetimeColumn(),
                "Status": st.column_config.SelectboxColumn(
                    options=["Pending", "Approved", "Denied"]
                )
            }
        )
    else:
        st.info("No event approval requests submitted by this group")

def render_submit_earnings():
    """Render form for submitting group earnings"""
    st.header("Submit Group Earnings")
    
    # Verify user is a group leader
    if not is_group_leader():
        st.error("Only group leaders can submit earnings")
        return
    
    # Get leader's group
    leader_group = next(
        (g for g, leader in st.session_state.group_leaders.items() if leader == st.session_state.user),
        None
    )
    
    if not leader_group:
        st.error("Could not determine your group leadership")
        return
    
    st.subheader(f"Submitting for: {leader_group}")
    
    with st.form("submit_earnings"):
        amount = st.number_input(
            "Amount Earned ($)", 
            min_value=0.01, 
            step=10.0,
            format="%.2f"
        )
        
        description = st.text_area(
            "Description of Earnings Source",
            placeholder="What was the fundraiser? Who donated? etc.",
            height=100
        )
        
        # Optional: upload proof/receipt
        receipt = st.file_uploader(
            "Upload Receipt/Proof (Optional)",
            type=VALID_FILE_EXTENSIONS,
            help=f"Accepted formats: {', '.join(VALID_FILE_EXTENSIONS)}"
        )
        
        submit = st.form_submit_button("Submit Earnings")
        
        if submit:
            if amount <= 0:
                st.error("Amount must be greater than zero")
            elif not description or len(description) < 10:
                st.error("Please provide a detailed description (at least 10 characters)")
            else:
                # Validate file size if provided
                if receipt and receipt.size > MAX_UPLOAD_SIZE:
                    st.error(f"File too large. Maximum size is {MAX_UPLOAD_SIZE/1024/1024:.1f}MB")
                else:
                    # Process earnings submission
                    success, msg = record_group_earning(leader_group, amount, description)
                    
                    if success:
                        # Save data
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

def render_request_reimbursement():
    """Render form for requesting reimbursement"""
    st.header("Request Reimbursement")
    
    # Get user's group
    user_group = st.session_state.current_group
    
    if not user_group:
        st.error("You must be in a group to request reimbursement")
        return
    
    st.subheader(f"Requesting for: {user_group}")
    
    max_amount = st.session_state.config.get("max_reimbursement", REIMBURSEMENT_LIMIT)
    st.info(f"Maximum standard reimbursement: ${max_amount}. For larger amounts, please contact an administrator.")
    
    with st.form("reimbursement_request"):
        amount = st.number_input(
            "Reimbursement Amount ($)", 
            min_value=0.01, 
            step=10.0,
            format="%.2f"
        )
        
        purpose = st.text_area(
            "Purpose of Expenditure",
            placeholder="What was purchased? Why was it necessary?",
            height=100
        )
        
        # Upload receipt
        receipt = st.file_uploader(
            "Upload Receipt (Required)",
            type=VALID_FILE_EXTENSIONS,
            help=f"Accepted formats: {', '.join(VALID_FILE_EXTENSIONS)}"
        )
        
        submit = st.form_submit_button("Submit Reimbursement Request")
        
        if submit:
            if amount <= 0:
                st.error("Amount must be greater than zero")
            elif amount > max_amount:
                st.error(f"Amount exceeds maximum reimbursement limit of ${max_amount}")
            elif not purpose or len(purpose) < 10:
                st.error("Please provide a detailed purpose (at least 10 characters)")
            elif not receipt:
                st.error("Please upload a receipt for verification")
            elif receipt.size > MAX_UPLOAD_SIZE:
                st.error(f"File too large. Maximum size is {MAX_UPLOAD_SIZE/1024/1024:.1f}MB")
            else:
                # Process reimbursement request
                success, msg = submit_reimbursement_request(
                    user_group,
                    st.session_state.user,
                    amount,
                    purpose
                )
                
                if success:
                    # Save data
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

def render_request_event_approval():
    """Render form for requesting event approval"""
    st.header("Request Event Approval")
    
    # Get user's group
    user_group = st.session_state.current_group
    
    if not user_group:
        st.error("You must be in a group to request event approval")
        return
    
    st.subheader(f"Requesting for: {user_group}")
    
    max_budget = st.session_state.config.get("max_event_budget", EVENT_BUDGET_LIMIT)
    st.info(f"Events with budgets over ${max_budget} require special approval.")
    
    with st.form("event_approval_request"):
        event_name = st.text_input("Event Name")
        
        col1, col2 = st.columns(2)
        with col1:
            proposed_date = st.date_input(
                "Proposed Date",
                min_value=date.today()
            )
        with col2:
            expected_attendance = st.number_input(
                "Expected Attendance",
                min_value=1,
                step=5
            )
        
        budget = st.number_input(
            "Estimated Budget ($)",
            min_value=0.00,
            step=50.0,
            format="%.2f"
        )
        
        description = st.text_area(
            "Event Description & Purpose",
            placeholder="What is the event? What is its purpose? How will it benefit the school/community?",
            height=150
        )
        
        additional_notes = st.text_area(
            "Additional Notes (Optional)",
            placeholder="Any special requirements, permissions needed, or other information?",
            height=100
        )
        
        submit = st.form_submit_button("Submit Event Request")
        
        if submit:
            if not event_name or len(event_name) < 3:
                st.error("Please provide a valid event name (at least 3 characters)")
            elif not description or len(description) < 20:
                st.error("Please provide a detailed description (at least 20 characters)")
            elif (proposed_date - date.today()).days > 90:
                st.error("Events cannot be scheduled more than 90 days in advance")
            elif expected_attendance < 1:
                st.error("Expected attendance must be at least 1")
            else:
                # Process event request
                success, msg = submit_event_approval_request(
                    user_group,
                    st.session_state.user,
                    event_name,
                    description,
                    proposed_date.strftime("%Y-%m-%d"),
                    budget,
                    expected_attendance
                )
                
                if success:
                    if budget > max_budget:
                        st.warning(f"Note: Your budget of ${budget} exceeds the standard limit of ${max_budget} and will require special approval.")
                    
                    # Save data
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

def render_manage_groups():
    """Render group management page for admins"""
    st.header("Manage Groups")
    
    # Verify admin access
    if not is_admin():
        st.error("Only administrators can access this page")
        return
    
    # Select group to manage
    selected_group = st.selectbox("Select Group to Manage", GROUP_NAMES)
    
    # Group details
    st.subheader(f"Group: {selected_group}")
    
    # Group leader management
    st.subheader("Group Leader")
    current_leader = st.session_state.group_leaders.get(selected_group, "")
    group_members = st.session_state.groups.get(selected_group, [])
    
    col_leader, col_reset = st.columns(2)
    with col_leader:
        new_leader = st.selectbox(
            "Set Group Leader",
            [""] + group_members,  # Empty option to remove leader
            index=[""] + group_members.index(current_leader) + [1] if current_leader in group_members else 0
        )
        
        if st.button("Update Leader"):
            if new_leader == current_leader:
                st.info("This user is already the group leader")
            else:
                success, msg = set_group_leader(selected_group, new_leader)
                if success:
                    # Save data
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    
    with col_reset:
        st.subheader("Group Access Code")
        current_code = st.session_state.group_codes.get(selected_group, "N/A")
        st.code(current_code)
        
        if st.button("Regenerate Code"):
            if st.session_state.confirm_action == f"regenerate_{selected_group}":
                success, msg = regenerate_group_code(selected_group)
                if success:
                    # Save data
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    
                    st.success(msg)
                    st.session_state.confirm_action = None
                    st.rerun()
                else:
                    st.error(msg)
                    st.session_state.confirm_action = None
            else:
                st.warning("This will invalidate the current group code. New members will need the new code to join.")
                st.session_state.confirm_action = f"regenerate_{selected_group}"
                st.button("Confirm Regenerate Code")
    
    # Group members management
    st.subheader("Group Members")
    st.write(f"Current members: {', '.join(group_members) or 'None'}")
    
    # Add member to group
    st.subheader("Add Member to Group")
    all_users = list(st.session_state.users.keys())
    # Get users not in this group
    users_not_in_group = [user for user in all_users if user not in group_members]
    
    if users_not_in_group:
        user_to_add = st.selectbox("Select User to Add", users_not_in_group)
        
        if st.button("Add to Group"):
            # Get user's current group
            user_current_group = st.session_state.users[user_to_add].get("group", "")
            
            # Move user from current group to new group
            if user_current_group:
                success, msg = move_user_between_groups(user_to_add, user_current_group, selected_group)
            else:
                # Add to group directly if not in any group
                st.session_state.groups[selected_group].append(user_to_add)
                st.session_state.groups[selected_group].sort()
                st.session_state.users[user_to_add]["group"] = selected_group
                success = True
                msg = f"Added {user_to_add} to {selected_group}"
            
            if success:
                # Save data
                sheet = connect_gsheets()
                save_all_data(sheet)
                
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.info("All users are already in this group")
    
    # Remove member from group
    if group_members:
        st.subheader("Remove Member from Group")
        user_to_remove = st.selectbox("Select User to Remove", group_members)
        
        # Prevent removing last member if they're the leader
        if len(group_members) == 1 and user_to_remove == current_leader:
            st.warning("Cannot remove the only member who is also the group leader. Add another member first.")
        else:
            if st.button("Remove from Group"):
                # Remove from group
                st.session_state.groups[selected_group].remove(user_to_remove)
                
                # If removing leader, set new leader
                if user_to_remove == current_leader and group_members:
                    new_leader = group_members[0] if group_members[0] != user_to_remove else group_members[1]
                    st.session_state.group_leaders[selected_group] = new_leader
                    st.session_state.users[new_leader]["role"] = "group_leader"
                
                # Set user's group to empty
                st.session_state.users[user_to_remove]["group"] = ""
                if st.session_state.users[user_to_remove]["role"] == "group_leader":
                    st.session_state.users[user_to_remove]["role"] = "user"
                
                # Log activity
                log_activity("remove_group_member", f"Removed {user_to_remove} from {selected_group}")
                
                # Send notification
                send_notification(
                    user_to_remove,
                    "Removed from Group",
                    f"You have been removed from {selected_group}."
                )
                
                # Save data
                sheet = connect_gsheets()
                save_all_data(sheet)
                
                st.success(f"Removed {user_to_remove} from {selected_group}")
                st.rerun()
    
    # Group earnings verification
    st.subheader("Verify Group Earnings")
    pending_earnings = st.session_state.group_earnings[
        (st.session_state.group_earnings["Group"] == selected_group) &
        (st.session_state.group_earnings["Verified"] == "Pending")
    ]
    
    if not pending_earnings.empty:
        st.dataframe(pending_earnings)
        
        earning_to_verify = st.selectbox(
            "Select Earnings to Verify",
            pending_earnings.index.tolist(),
            format_func=lambda x: f"{pending_earnings.at[x, 'Date']}: ${pending_earnings.at[x, 'Amount']} - {pending_earnings.at[x, 'Description']}"
        )
        
        verification_status = st.radio(
            "Verification Status",
            ["Verified", "Rejected"]
        )
        
        admin_notes = st.text_area("Admin Notes")
        
        if st.button("Update Verification Status"):
            success, msg = verify_group_earning(earning_to_verify, verification_status, admin_notes)
            if success:
                # Save data
                sheet = connect_gsheets()
                save_all_data(sheet)
                
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.info(f"No pending earnings verification for {selected_group}")

def render_financial_overview():
    """Render financial overview page for admins"""
    st.header("Financial Overview")
    
    # Verify admin access
    if not is_admin():
        st.error("Only administrators can access this page")
        return
    
    # Date range filter
    st.subheader("Filter by Date Range")
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Start Date",
            value=st.session_state.date_range_start,
            key="finance_start_date"
        )
    with col_end:
        end_date = st.date_input(
            "End Date",
            value=st.session_state.date_range_end,
            key="finance_end_date"
        )
    
    if start_date > end_date:
        st.error("Start date cannot be after end date")
        return
    
    # Update session state
    st.session_state.date_range_start = start_date
    st.session_state.date_range_end = end_date
    
    # Filter financial data by date range
    if not st.session_state.money_data.empty:
        # Convert to datetime for filtering
        st.session_state.money_data["Date_DT"] = pd.to_datetime(st.session_state.money_data["Date"])
        mask = (st.session_state.money_data["Date_DT"] >= pd.to_datetime(start_date)) & \
               (st.session_state.money_data["Date_DT"] <= pd.to_datetime(end_date))
        filtered_data = st.session_state.money_data[mask].copy()
        
        # Calculate totals
        total_income = filtered_data[filtered_data["Category"] == "Income"]["Amount"].sum()
        total_expenses = abs(filtered_data[filtered_data["Category"] == "Expense"]["Amount"].sum())
        net_balance = total_income - total_expenses
        
        # Display key metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Income", f"${total_income:.2f}")
        with col2:
            st.metric("Total Expenses", f"${total_expenses:.2f}")
        with col3:
            st.metric("Net Balance", f"${net_balance:.2f}")
        
        # Financial summary chart
        st.subheader("Financial Summary")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(["Income", "Expenses"], [total_income, total_expenses], color=['#4CAF50', '#F44336'])
        ax.set_title(f"Financial Summary: {start_date} to {end_date}")
        st.pyplot(fig)
        
        # Income vs expenses over time
        st.subheader("Income vs. Expenses Over Time")
        filtered_data["Month"] = filtered_data["Date_DT"].dt.to_period("M")
        monthly_data = filtered_data.groupby(["Month", "Category"])["Amount"].sum().unstack()
        monthly_data["Expenses"] = -monthly_data["Expense"]  # Show expenses as positive values
        
        fig, ax = plt.subplots(figsize=(12, 6))
        monthly_data[["Income", "Expenses"]].plot(kind="bar", ax=ax)
        ax.set_title("Monthly Income vs. Expenses")
        ax.set_xlabel("Month")
        ax.set_ylabel("Amount ($)")
        plt.xticks(rotation=45)
        st.pyplot(fig)
        
        # Breakdown by group
        st.subheader("Financial Breakdown by Group")
        group_data = filtered_data.groupby(["Group", "Category"])["Amount"].sum().unstack()
        group_data["Expenses"] = -group_data["Expense"]  # Show expenses as positive values
        
        fig, ax = plt.subplots(figsize=(12, 6))
        group_data[["Income", "Expenses"]].plot(kind="bar", ax=ax)
        ax.set_title("Financial Activity by Group")
        ax.set_xlabel("Group")
        ax.set_ylabel("Amount ($)")
        plt.xticks(rotation=45)
        st.pyplot(fig)
        
        # Detailed transaction list
        st.subheader("Transactions")
        # Format for display
        display_data = filtered_data.drop(columns=["Date_DT", "Month"]) if "Month" in filtered_data.columns else filtered_data.drop(columns=["Date_DT"])
        st.dataframe(
            display_data.sort_values("Date", ascending=False),
            column_config={
                "Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Date": st.column_config.DateColumn()
            }
        )
        
        # Export functionality
        if st.button("Export Financial Data"):
            # Create CSV
            csv = display_data.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="student_council_finances_{start_date}_{end_date}.csv">Download CSV File</a>'
            st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("No financial data available")
    
    # Add manual transaction (admin only)
    st.divider()
    st.subheader("Record Manual Transaction")
    
    with st.form("manual_transaction"):
        col1, col2 = st.columns(2)
        with col1:
            transaction_date = st.date_input("Transaction Date", value=date.today())
            transaction_group = st.selectbox("Group", GROUP_NAMES)
        with col2:
            transaction_amount = st.number_input("Amount ($)", value=0.00, step=10.0)
            transaction_type = st.radio("Type", ["Income", "Expense"])
        
        transaction_description = st.text_input("Description")
        submit_transaction = st.form_submit_button("Record Transaction")
        
        if submit_transaction:
            if transaction_amount == 0:
                st.error("Amount cannot be zero")
            elif not transaction_description:
                st.error("Please provide a description")
            else:
                # Adjust amount based on type
                amount = transaction_amount if transaction_type == "Income" else -transaction_amount
                
                # Create new transaction
                new_transaction = pd.DataFrame([{
                    "Amount": amount,
                    "Description": transaction_description,
                    "Date": transaction_date.strftime("%Y-%m-%d"),
                    "Handled By": st.session_state.user,
                    "Group": transaction_group,
                    "Category": transaction_type
                }])
                
                st.session_state.money_data = pd.concat(
                    [st.session_state.money_data, new_transaction], ignore_index=True
                )
                
                # Log activity
                log_activity("record_transaction", f"Recorded {transaction_type} of ${transaction_amount} for {transaction_group}")
                
                # Save data
                sheet = connect_gsheets()
                save_all_data(sheet)
                
                st.success("Transaction recorded successfully")
                st.rerun()

def render_approve_requests():
    """Render page for admins to approve/reject requests"""
    st.header("Approve Requests")
    
    # Verify admin access
    if not is_admin():
        st.error("Only administrators can access this page")
        return
    
    # Tabs for different request types
    reimburse_tab, event_tab = st.tabs(["Reimbursements", "Event Approvals"])
    
    with reimburse_tab:
        st.subheader("Reimbursement Requests")
        
        # Filter options
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Pending", "Approved", "Denied"]
        )
        
        group_filter = st.selectbox(
            "Filter by Group",
            ["All"] + GROUP_NAMES
        )
        
        # Apply filters
        filtered_reimburse = st.session_state.reimbursement_requests.copy()
        
        if status_filter != "All":
            filtered_reimburse = filtered_reimburse[filtered_reimburse["Status"] == status_filter]
        
        if group_filter != "All":
            filtered_reimburse = filtered_reimburse[filtered_reimburse["Group"] == group_filter]
        
        if not filtered_reimburse.empty:
            st.dataframe(
                filtered_reimburse.sort_values("Date Submitted", ascending=False),
                column_config={
                    "Amount": st.column_config.NumberColumn(format="$%.2f"),
                    "Date Submitted": st.column_config.DatetimeColumn(),
                    "Status": st.column_config.SelectboxColumn(
                        options=["Pending", "Approved", "Denied"]
                    )
                }
            )
            
            # Approve/deny section
            if len(filtered_reimburse[filtered_reimburse["Status"] == "Pending"]) > 0:
                st.subheader("Process Pending Requests")
                request_id = st.selectbox(
                    "Select Request to Process",
                    filtered_reimburse[filtered_reimburse["Status"] == "Pending"]["Request ID"]
                )
                
                if request_id:
                    # Get request details
                    request_details = filtered_reimburse[filtered_reimburse["Request ID"] == request_id].iloc[0]
                    
                    st.subheader(f"Request Details: {request_id}")
                    st.write(f"**Requester:** {request_details['Requester']}")
                    st.write(f"**Group:** {request_details['Group']}")
                    st.write(f"**Amount:** ${request_details['Amount']}")
                    st.write(f"**Purpose:** {request_details['Purpose']}")
                    st.write(f"**Submitted:** {request_details['Date Submitted']}")
                    
                    new_status = st.radio("Set Status", ["Approved", "Denied"])
                    admin_notes = st.text_area("Admin Notes")
                    
                    if st.button("Update Request Status"):
                        success, msg = update_request_status(
                            "reimbursement",
                            request_id,
                            new_status,
                            admin_notes
                        )
                        
                        if success:
                            # Save data
                            sheet = connect_gsheets()
                            save_all_data(sheet)
                            
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
        else:
            st.info("No reimbursement requests found matching your filters")
    
    with event_tab:
        st.subheader("Event Approval Requests")
        
        # Filter options
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Pending", "Approved", "Denied"],
            key="event_status_filter"
        )
        
        group_filter = st.selectbox(
            "Filter by Group",
            ["All"] + GROUP_NAMES,
            key="event_group_filter"
        )
        
        # Apply filters
        filtered_events = st.session_state.event_approval_requests.copy()
        
        if status_filter != "All":
            filtered_events = filtered_events[filtered_events["Status"] == status_filter]
        
        if group_filter != "All":
            filtered_events = filtered_events[filtered_events["Group"] == group_filter]
        
        if not filtered_events.empty:
            st.dataframe(
                filtered_events.sort_values("Date Submitted", ascending=False),
                column_config={
                    "Budget": st.column_config.NumberColumn(format="$%.2f"),
                    "Proposed Date": st.column_config.DateColumn(),
                    "Date Submitted": st.column_config.DatetimeColumn(),
                    "Status": st.column_config.SelectboxColumn(
                        options=["Pending", "Approved", "Denied"]
                    )
                }
            )
            
            # Approve/deny section
            if len(filtered_events[filtered_events["Status"] == "Pending"]) > 0:
                st.subheader("Process Pending Requests")
                request_id = st.selectbox(
                    "Select Request to Process",
                    filtered_events[filtered_events["Status"] == "Pending"]["Request ID"],
                    key="event_request_id"
                )
                
                if request_id:
                    # Get request details
                    request_details = filtered_events[filtered_events["Request ID"] == request_id].iloc[0]
                    
                    st.subheader(f"Request Details: {request_id}")
                    st.write(f"**Event Name:** {request_details['Event Name']}")
                    st.write(f"**Requester:** {request_details['Requester']}")
                    st.write(f"**Group:** {request_details['Group']}")
                    st.write(f"**Proposed Date:** {request_details['Proposed Date']}")
                    st.write(f"**Budget:** ${request_details['Budget']}")
                    st.write(f"**Expected Attendance:** {request_details['Expected Attendance']}")
                    st.write(f"**Description:** {request_details['Description']}")
                    st.write(f"**Submitted:** {request_details['Date Submitted']}")
                    
                    # Highlight if budget exceeds limit
                    max_budget = st.session_state.config.get("max_event_budget", EVENT_BUDGET_LIMIT)
                    if float(request_details['Budget']) > max_budget:
                        st.warning(f"This request exceeds the standard budget limit of ${max_budget}")
                    
                    new_status = st.radio("Set Status", ["Approved", "Denied", "Returned for Revision"], key="event_new_status")
                    admin_notes = st.text_area("Admin Notes", key="event_admin_notes")
                    
                    if st.button("Update Request Status", key="event_update_btn"):
                        success, msg = update_request_status(
                            "event",
                            request_id,
                            new_status,
                            admin_notes
                        )
                        
                        if success:
                            # Save data
                            sheet = connect_gsheets()
                            save_all_data(sheet)
                            
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
        else:
            st.info("No event requests found matching your filters")

def render_manage_users():
    """Render user management page for admins"""
    st.header("Manage Users")
    
    # Verify admin access
    if not is_admin():
        st.error("Only administrators can access this page")
        return
    
    # Search and filter users
    col_search, col_role = st.columns(2)
    with col_search:
        search_query = st.text_input("Search Users", value=st.session_state.search_query)
        st.session_state.search_query = search_query
    
    with col_role:
        role_filter = st.selectbox("Filter by Role", ["All"] + ROLES)
    
    # Apply filters
    filtered_users = []
    for username, details in st.session_state.users.items():
        matches_search = search_query.lower() in username.lower()
        matches_role = role_filter == "All" or details["role"] == role_filter
        
        if matches_search and matches_role:
            filtered_users.append({
                "username": username,
                "role": details["role"],
                "group": details.get("group", ""),
                "created_at": details["created_at"],
                "last_login": details.get("last_login", "Never"),
                "email": details.get("email", "")
            })
    
    # Display user list
    st.subheader(f"Users ({len(filtered_users)})")
    
    if filtered_users:
        # Create DataFrame for display
        users_df = pd.DataFrame(filtered_users)
        st.dataframe(
            users_df.sort_values("username"),
            column_config={
                "created_at": st.column_config.DatetimeColumn(),
                "last_login": st.column_config.DatetimeColumn()
            }
        )
        
        # Select user to manage
        st.subheader("Manage User")
        selected_user = st.selectbox("Select User", [u["username"] for u in filtered_users])
        
        if selected_user:
            user_details = st.session_state.users[selected_user]
            
            # User details
            st.subheader(f"User Details: {selected_user}")
            st.write(f"**Role:** {user_details['role']}")
            st.write(f"**Group:** {user_details.get('group', 'None')}")
            st.write(f"**Created:** {user_details['created_at']}")
            st.write(f"**Last Login:** {user_details.get('last_login', 'Never')}")
            st.write(f"**Email:** {user_details.get('email', 'Not provided')}")
            
            # Update user role
            st.subheader("Update User Role")
            new_role = st.selectbox(
                "New Role",
                ROLES,
                index=ROLES.index(user_details["role"])
            )
            
            # Prevent changing creator role unless current user is creator
            if new_role == "creator" and not is_creator():
                st.error("Only the system creator can assign the creator role")
            else:
                if st.button("Update Role"):
                    if new_role == user_details["role"]:
                        st.info("User already has this role")
                    else:
                        # Special handling for group leaders
                        if new_role == "group_leader" and not user_details.get("group"):
                            st.error("Cannot set as group leader - user is not assigned to any group")
                        else:
                            st.session_state.users[selected_user]["role"] = new_role
                            
                            # If demoting from group leader, update group leader record
                            if user_details["role"] == "group_leader" and new_role != "group_leader":
                                for group, leader in st.session_state.group_leaders.items():
                                    if leader == selected_user:
                                        # Set new leader if possible
                                        if st.session_state.groups[group]:
                                            new_leader = st.session_state.groups[group][0]
                                            st.session_state.group_leaders[group] = new_leader
                                            st.session_state.users[new_leader]["role"] = "group_leader"
                                            st.success(f"Also promoted {new_leader} to group leader of {group}")
                                        else:
                                            st.session_state.group_leaders[group] = ""
                            
                            # Log activity
                            log_activity("update_user_role", f"Changed {selected_user}'s role from {user_details['role']} to {new_role}")
                            
                            # Save data
                            sheet = connect_gsheets()
                            save_all_data(sheet)
                            
                            st.success(f"Updated {selected_user}'s role to {new_role}")
                            st.rerun()
            
            # Reset user password
            st.subheader("Reset Password")
            if st.button("Reset User Password"):
                admin_password = st.text_input(
                    "Enter Your Password to Confirm",
                    type="password",
                    key="admin_confirm_password"
                )
                
                if st.button("Confirm Password Reset"):
                    success, msg = reset_user_password(selected_user, admin_password)
                    if success:
                        # Save data
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            
            # Delete user (with caution)
            if selected_user != st.session_state.user and selected_user not in [
                u for u, details in st.session_state.users.items() if details["role"] == "creator"
            ] and not (is_creator() and selected_user == st.session_state.user):
                st.subheader("Delete User")
                st.warning("Deleting a user is permanent and cannot be undone!")
                
                if st.button("Delete User", type="primary", disabled=selected_user == st.session_state.user):
                    if st.session_state.confirm_action == f"delete_{selected_user}":
                        # Remove from groups
                        user_group = user_details.get("group", "")
                        if user_group and selected_user in st.session_state.groups[user_group]:
                            st.session_state.groups[user_group].remove(selected_user)
                            
                            # If deleting group leader, update
                            if st.session_state.group_leaders.get(user_group) == selected_user:
                                if st.session_state.groups[user_group]:
                                    new_leader = st.session_state.groups[user_group][0]
                                    st.session_state.group_leaders[user_group] = new_leader
                                    st.session_state.users[new_leader]["role"] = "group_leader"
                                else:
                                    st.session_state.group_leaders[user_group] = ""
                        
                        # Remove from users
                        del st.session_state.users[selected_user]
                        
                        # Log activity
                        log_activity("delete_user", f"Deleted user: {selected_user}")
                        
                        # Save data
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        
                        st.success(f"User {selected_user} has been deleted")
                        st.session_state.confirm_action = None
                        st.rerun()
                    else:
                        st.session_state.confirm_action = f"delete_{selected_user}"
                        st.button("Type 'DELETE' to confirm", key="confirm_delete")
            else:
                if selected_user == st.session_state.user:
                    st.info("You cannot delete your own account")
                else:
                    st.info("You cannot delete creator accounts")
    
    else:
        st.info("No users found matching your criteria")
    
    # Create new user (admin only)
    st.divider()
    st.subheader("Create New User")
    
    with st.form("admin_create_user"):
        new_username = st.text_input("Username", key="admin_new_username")
        new_email = st.text_input("Email Address", key="admin_new_email")
        
        col1, col2 = st.columns(2)
        with col1:
            new_role = st.selectbox("User Role", ROLES, index=0)  # Default to user
        with col2:
            new_group = st.selectbox("Group Assignment", [""] + GROUP_NAMES, key="admin_new_group")
        
        # Generate temporary password
        temp_password = ''.join(random.choices(
            string.ascii_uppercase + string.ascii_lowercase + string.digits + "!@#$%",
            k=10
        ))
        st.text_input("Temporary Password", value=temp_password, disabled=True)
        st.caption("User will need to change this after first login")
        
        submit_new_user = st.form_submit_button("Create User")
        
        if submit_new_user:
            # Validate inputs
            if not new_username or len(new_username) < 3:
                st.error("Username must be at least 3 characters")
            elif not re.match(r'^[a-zA-Z0-9_]+$', new_username):
                st.error("Username can only contain letters, numbers, and underscores")
            elif new_username in st.session_state.users:
                st.error("Username already exists")
            elif new_role == "group_leader" and not new_group:
                st.error("Group leaders must be assigned to a group")
            elif new_email and not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', new_email):
                st.error("Please enter a valid email address")
            else:
                # Create user
                current_time = datetime.now().isoformat()
                st.session_state.users[new_username] = {
                    "password_hash": hash_password(temp_password),
                    "role": new_role,
                    "created_at": current_time,
                    "last_login": None,
                    "group": new_group,
                    "email": new_email or f"{new_username.lower()}@school.edu"
                }
                
                # Add to group if specified
                if new_group and new_username not in st.session_state.groups[new_group]:
                    st.session_state.groups[new_group].append(new_username)
                    st.session_state.groups[new_group].sort()
                
                # If group leader, update group leaders
                if new_role == "group_leader" and new_group:
                    st.session_state.group_leaders[new_group] = new_username
                
                # Log activity
                log_activity("admin_create_user", f"Admin created user {new_username} with role {new_role}")
                
                # Send welcome notification
                send_notification(
                    new_username,
                    "Account Created",
                    f"Your account has been created. Your temporary password is: {temp_password}\nPlease change it after your first login."
                )
                
                # Save data
                sheet = connect_gsheets()
                save_all_data(sheet)
                
                st.success(f"User {new_username} created successfully. Temporary password: {temp_password}")
                st.rerun()

def render_system_settings():
    """Render system settings page for admins"""
    st.header("System Settings")
    
    # Verify admin access
    if not is_admin():
        st.error("Only administrators can access this page")
        return
    
    # General settings
    st.subheader("General Settings")
    with st.form("general_settings"):
        show_signup = st.checkbox(
            "Allow New User Signups",
            value=st.session_state.config.get("show_signup", True)
        )
        
        max_reimbursement = st.number_input(
            "Maximum Standard Reimbursement ($)",
            min_value=50,
            value=st.session_state.config.get("max_reimbursement", REIMBURSEMENT_LIMIT),
            step=50
        )
        
        max_event_budget = st.number_input(
            "Maximum Standard Event Budget ($)",
            min_value=500,
            value=st.session_state.config.get("max_event_budget", EVENT_BUDGET_LIMIT),
            step=100
        )
        
        submit_general = st.form_submit_button("Save General Settings")
        
        if submit_general:
            st.session_state.config["show_signup"] = show_signup
            st.session_state.config["max_reimbursement"] = max_reimbursement
            st.session_state.config["max_event_budget"] = max_event_budget
            st.session_state.config["last_updated"] = datetime.now().isoformat()
            
            # Log activity
            log_activity("update_system_settings", "Updated general system settings")
            
            # Save data
            sheet = connect_gsheets()
            save_all_data(sheet)
            
            st.success("General settings saved successfully")
            st.rerun()
    
    # Meeting management
    st.subheader("Manage Meetings")
    st.write("Current meetings in system:")
    st.write(", ".join(st.session_state.meeting_names) if st.session_state.meeting_names else "None")
    
    with st.form("add_meeting"):
        new_meeting = st.text_input("New Meeting Name")
        submit_meeting = st.form_submit_button("Add Meeting")
        
        if submit_meeting:
            if not new_meeting:
                st.error("Please enter a meeting name")
            elif new_meeting in st.session_state.meeting_names:
                st.error("This meeting already exists")
            else:
                st.session_state.meeting_names.append(new_meeting)
                
                # Add column to attendance data
                st.session_state.attendance[new_meeting] = [False] * len(st.session_state.attendance)
                
                # Log activity
                log_activity("add_meeting", f"Added new meeting: {new_meeting}")
                
                # Save data
                sheet = connect_gsheets()
                save_all_data(sheet)
                
                st.success(f"Added new meeting: {new_meeting}")
                st.rerun()
    
    # Manage meeting minutes
    st.subheader("Manage Meeting Minutes")
    with st.expander("Add New Meeting Minutes"):
        with st.form("add_meeting_minutes"):
            meeting_name = st.text_input("Meeting Name")
            meeting_date = st.date_input("Meeting Date")
            meeting_location = st.text_input("Location")
            meeting_facilitator = st.text_input("Facilitator")
            meeting_attendees = st.text_input("Attendees")
            meeting_agenda = st.text_area("Agenda")
            meeting_decisions = st.text_area("Key Decisions")
            meeting_next_steps = st.text_area("Next Steps")
            
            submit_minutes = st.form_submit_button("Save Meeting Minutes")
            
            if submit_minutes:
                if not meeting_name or not meeting_date or not meeting_facilitator:
                    st.error("Please fill in all required fields (name, date, facilitator)")
                else:
                    new_minutes = pd.DataFrame([{
                        "Meeting Name": meeting_name,
                        "Date": meeting_date.strftime("%Y-%m-%d"),
                        "Location": meeting_location,
                        "Facilitator": meeting_facilitator,
                        "Attendees": meeting_attendees,
                        "Agenda": meeting_agenda,
                        "Key Decisions": meeting_decisions,
                        "Next Steps": meeting_next_steps,
                        "Created By": st.session_state.user,
                        "Created At": datetime.now().isoformat()
                    }])
                    
                    st.session_state.meeting_minutes = pd.concat(
                        [st.session_state.meeting_minutes, new_minutes], ignore_index=True
                    )
                    
                    # Log activity
                    log_activity("add_meeting_minutes", f"Added minutes for {meeting_name}")
                    
                    # Save data
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    
                    st.success(f"Meeting minutes for {meeting_name} saved successfully")
                    st.rerun()
    
    # View existing meeting minutes
    if not st.session_state.meeting_minutes.empty:
        st.subheader("Existing Meeting Minutes")
        selected_minutes = st.selectbox(
            "Select Meeting",
            st.session_state.meeting_minutes["Meeting Name"].unique()
        )
        
        if selected_minutes:
            minutes_details = st.session_state.meeting_minutes[
                st.session_state.meeting_minutes["Meeting Name"] == selected_minutes
            ].iloc[0]
            
            with st.expander("View Meeting Details", expanded=True):
                st.write(f"**Date:** {minutes_details['Date']}")
                st.write(f"**Location:** {minutes_details['Location']}")
                st.write(f"**Facilitator:** {minutes_details['Facilitator']}")
                st.write(f"**Attendees:** {minutes_details['Attendees']}")
                
                st.subheader("Agenda")
                st.write(minutes_details['Agenda'])
                
                st.subheader("Key Decisions")
                st.write(minutes_details['Key Decisions'])
                
                st.subheader("Next Steps")
                st.write(minutes_details['Next Steps'])
                
                if "Created By" in minutes_details:
                    st.caption(f"Recorded by {minutes_details['Created By']} on {minutes_details.get('Created At', '')}")

def render_system_audit():
    """Render system audit page for creators"""
    st.header("System Audit Log")
    
    # Verify creator access
    if not is_creator():
        st.error("Only the system creator can access this page")
        return
    
    # Filter options
    st.subheader("Filter Audit Log")
    
    col_user, col_action = st.columns(2)
    with col_user:
        user_filter = st.selectbox(
            "Filter by User",
            ["All"] + list(st.session_state.users.keys())
        )
    
    with col_action:
        action_filter = st.text_input("Filter by Action")
    
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=30)
        )
    with col_end:
        end_date = st.date_input(
            "End Date",
            value=date.today()
        )
    
    if start_date > end_date:
        st.error("Start date cannot be after end date")
        return
    
    # Apply filters
    if not st.session_state.activity_log.empty:
        # Convert to datetime for filtering
        st.session_state.activity_log["Timestamp_DT"] = pd.to_datetime(st.session_state.activity_log["Timestamp"])
        mask = (st.session_state.activity_log["Timestamp_DT"] >= pd.to_datetime(start_date)) & \
               (st.session_state.activity_log["Timestamp_DT"] <= pd.to_datetime(end_date))
        
        if user_filter != "All":
            mask &= (st.session_state.activity_log["User"] == user_filter)
        
        if action_filter:
            mask &= st.session_state.activity_log["Action"].str.contains(action_filter, case=False)
        
        filtered_logs = st.session_state.activity_log[mask].copy()
        
        st.subheader(f"Audit Log Entries ({len(filtered_logs)})")
        st.dataframe(
            filtered_logs.sort_values("Timestamp_DT", ascending=False),
            column_config={
                "Timestamp_DT": st.column_config.DatetimeColumn(),
                "Timestamp": st.column_config.DatetimeColumn()
            }
        )
        
        # Export functionality
        if st.button("Export Audit Log"):
            # Create CSV
            csv = filtered_logs.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="system_audit_log_{start_date}_{end_date}.csv">Download CSV File</a>'
            st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("No audit log data available")
    
    # System health metrics
    st.subheader("System Health Metrics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Users", len(st.session_state.users))
    with col2:
        st.metric("Total Transactions", len(st.session_state.money_data))
    with col3:
        st.metric("Audit Log Entries", len(st.session_state.activity_log))
    
    # Active users
    if st.session_state.users:
        active_users = [u for u, details in st.session_state.users.items() if details.get("last_login")]
        st.metric("Active Users (with login)", len(active_users))
    
    # Recent system activity
    st.subheader("Recent System Activity")
    if not st.session_state.activity_log.empty:
        recent_activity = st.session_state.activity_log.sort_values("Timestamp", ascending=False).head(10)
        st.dataframe(recent_activity)
    else:
        st.info("No recent activity")

def render_data_management():
    """Render data management page for creators"""
    st.header("Data Management")
    
    # Verify creator access
    if not is_creator():
        st.error("Only the system creator can access this page")
        return
    
    st.warning("This page contains sensitive data operations. Use with extreme caution!")
    
    # Data export
    st.subheader("Export System Data")
    st.write("Export all system data for backup purposes")
    
    if st.button("Export All Data"):
        # Create a zip file with all dataframes as CSV
        # (In a real implementation, this would create actual files)
        st.info("Data export initiated. In a production system, this would generate a zip file with all data.")
        
        # Log activity
        log_activity("export_all_data", "Exported all system data")
        
        # Simulate download link
        st.success("Data export completed successfully")
    
    # Data import
    st.subheader("Import System Data")
    st.warning("Importing data will overwrite existing data. This operation cannot be undone!")
    
    data_file = st.file_uploader("Upload Data Backup File", type=["zip", "json"])
    
    if data_file:
        if st.button("Import Data"):
            if st.session_state.confirm_action == "import_data":
                st.info("Data import initiated. In a production system, this would process the uploaded file.")
                
                # Log activity
                log_activity("import_all_data", "Imported all system data")
                
                st.success("Data import completed successfully")
                st.session_state.confirm_action = None
            else:
                st.session_state.confirm_action = "import_data"
                st.button("Type 'IMPORT' to confirm", key="confirm_import")
    
    # Data reset
    st.subheader("Reset System Data")
    st.error("This will erase ALL system data and reset to default values. This operation cannot be undone!")
    
    if st.button("Reset to Default Data"):
        if st.session_state.confirm_action == "reset_data":
            # Initialize default data
            initialize_default_data()
            
            # Log activity
            log_activity("reset_system_data", "Reset all system data to defaults")
            
            # Save data
            sheet = connect_gsheets()
            save_all_data(sheet)
            
            st.success("System data has been reset to default values")
            st.session_state.confirm_action = None
            st.rerun()
        else:
            st.session_state.confirm_action = "reset_data"
            st.button("Type 'RESET' to confirm", key="confirm_reset")
    
    # Google Sheets synchronization
    st.subheader("Google Sheets Synchronization")
    sheet = connect_gsheets()
    
    if sheet:
        col_save, col_load = st.columns(2)
        with col_save:
            if st.button("Save All Data to Google Sheets"):
                success, msg = save_all_data(sheet)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
        
        with col_load:
            if st.button("Load All Data from Google Sheets"):
                if st.session_state.confirm_action == "load_gs_data":
                    success, msg = load_all_data(sheet)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                    st.session_state.confirm_action = None
                else:
                    st.session_state.confirm_action = "load_gs_data"
                    st.button("Confirm Load from Google Sheets", key="confirm_gs_load")
    else:
        st.error("Not connected to Google Sheets. Check configuration.")

# ------------------------------
# Main Application Flow
# ------------------------------
def main():
    """Main application function"""
    # Initialize session state
    initialize_session_state()
    
    # Get user IP (simplified for demonstration)
    if st.session_state.user_ip == "unknown":
        try:
            # In a real app, you might use a service to get IP
            st.session_state.user_ip = "192.168.1.1"  # Placeholder
        except:
            pass
    
    # Connect to Google Sheets and load data
    if not st.session_state.user and not st.session_state.users:
        sheet = connect_gsheets()
        if sheet:
            success, msg = load_all_data(sheet)
            if not success:
                st.warning(f"Could not load data: {msg}. Initializing with default data.")
                initialize_default_data()
        else:
            st.warning("Could not connect to Google Sheets. Initializing with default data.")
            initialize_default_data()
    
    # Handle authentication
    if not st.session_state.user:
        login_success = render_login_signup()
        if login_success:
            st.rerun()
        return
    
    # Render main application interface for logged-in users
    render_header()
    selected_tab = render_sidebar()
    
    # Route to appropriate page based on selection
    if selected_tab == "Dashboard":
        render_dashboard()
    elif selected_tab == "Calendar":
        render_calendar()
    elif selected_tab == "Announcements":
        render_announcements()
    elif selected_tab == "Credits & Rewards":
        render_credits_rewards()
    elif selected_tab == "My Group":
        render_my_group()
    elif selected_tab == "Submit Earnings":
        render_submit_earnings()
    elif selected_tab == "Request Reimbursement":
        render_request_reimbursement()
    elif selected_tab == "Request Event Approval":
        render_request_event_approval()
    elif selected_tab == "Manage Groups":
        render_manage_groups()
    elif selected_tab == "Financial Overview":
        render_financial_overview()
    elif selected_tab == "Approve Requests":
        render_approve_requests()
    elif selected_tab == "Manage Users":
        render_manage_users()
    elif selected_tab == "System Settings":
        render_system_settings()
    elif selected_tab == "System Audit":
        render_system_audit()
    elif selected_tab == "Data Management":
        render_data_management()
    
    # Save data periodically for logged-in users
    if st.session_state.user and random.random() < 0.1:  # 10% chance on each run
        sheet = connect_gsheets()
        if sheet:
            save_success, save_msg = save_all_data(sheet)
            if not save_success:
                logging.warning(f"Automatic save failed: {save_msg}")

# Run the application
if __name__ == "__main__":
    import calendar  # Import here to avoid circular import issues
    main()
