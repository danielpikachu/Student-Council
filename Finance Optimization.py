import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
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
def connect_gsheets():
    """Establish connection to Google Sheets and verify required worksheets"""
    try:
        # Retrieve secrets from Streamlit configuration
        secrets = st.secrets["google_sheets"]
        
        # Create credentials dictionary
        creds = {
            "type": "service_account",
            "client_email": secrets["service_account_email"],
            "private_key_id": secrets["private_key_id"],
            "client_id": "100000000000000000000",
            "private_key": secrets["private_key"].replace("\\n", "\n"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{secrets['service_account_email']}"
        }
        
        # Authenticate using service account credentials
        client = gspread.service_account_from_dict(creds)
        
        # Open the Google Sheet using the provided URL
        sheet = client.open_by_url(secrets["sheet_url"])
        
        # Define all required worksheets
        required_worksheets = [
            "users", "attendance", "credit_data", "reward_data",
            "scheduled_events", "occasional_events", "money_data",
            "calendar_events", "announcements", "config",
            "groups", "group_leader", "group_earnings",
            "reimbursement_requests", "event_approval_requests"
        ]
        
        # Create any missing worksheets
        existing_worksheets = [ws.title for ws in sheet.worksheets()]
        for ws_name in required_worksheets:
            if ws_name not in existing_worksheets:
                sheet.add_worksheet(title=ws_name, rows="1000", cols="30")
                st.success(f"Created required worksheet: {ws_name}")
        
        return sheet
    
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ The specified Google Sheet was not found. Please check the URL in your secrets.")
        return None
    except Exception as e:
        st.error(f"❌ Connection failed: {str(e)}")
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
    if "show_password_reset" not in st.session_state:
        st.session_state.show_password_reset = False
    
    # UI state variables
    if "spinning" not in st.session_state:
        st.session_state.spinning = False
    if "winner" not in st.session_state:
        st.session_state.winner = None
    if "allocation_count" not in st.session_state:
        st.session_state.allocation_count = 0
    if "current_calendar_month" not in st.session_state:
        st.session_state.current_calendar_month = (date.today().year, date.today().month)
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Home"
    if "show_help" not in st.session_state:
        st.session_state.show_help = False
    
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
            "Event Name", "Total Funds Raised", "Cost", "Staff Many Or Not",
            "Preparation Time", "Rating", "Responsible Group"
        ])
    if "money_data" not in st.session_state:
        st.session_state.money_data = pd.DataFrame(columns=[
            "Amount", "Description", "Date", "Handled By", "Group"
        ])
    if "calendar_events" not in st.session_state:
        st.session_state.calendar_events = {}
    if "announcements" not in st.session_state:
        st.session_state.announcements = []
    if "config" not in st.session_state:
        st.session_state.config = {"show_signup": True}
    if "meeting_names" not in st.session_state:
        st.session_state.meeting_names = []
    
    # Group-related variables
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
    if "group_earnings" not in st.session_state:
        st.session_state.group_earnings = pd.DataFrame(columns=[
            "Group", "Date", "Amount", "Description", "Verified"
        ])
    if "reimbursement_requests" not in st.session_state:
        st.session_state.reimbursement_requests = pd.DataFrame(columns=[
            "Request ID", "Group", "Requester", "Amount", "Purpose", 
            "Date Submitted", "Status", "Admin Notes"
        ])
    if "event_approval_requests" not in st.session_state:
        st.session_state.event_approval_requests = pd.DataFrame(columns=[
            "Request ID", "Group", "Requester", "Event Name", "Description",
            "Proposed Date", "Budget", "File Upload", "Date Submitted", 
            "Status", "Admin Notes"
        ])
    if "group_codes" not in st.session_state:
        st.session_state.group_codes = {
            "G1": "G1CODE", "G2": "G2CODE", "G3": "G3CODE", "G4": "G4CODE",
            "G5": "G5CODE", "G6": "G6CODE", "G7": "G7CODE", "G8": "G8CODE"
        }

# ------------------------------
# Data Management Functions
# ------------------------------
def save_all_data(sheet):
    """Save all application data to Google Sheets"""
    if not sheet:
        return False, "No connection to Google Sheets"
    
    try:
        # 1. Save user data
        users_ws = sheet.worksheet("users")
        users_data = [["username", "password_hash", "role", "created_at", "last_login", "group"]]
        for username, user_details in st.session_state.users.items():
            users_data.append([
                username,
                user_details["password_hash"],
                user_details["role"],
                user_details["created_at"],
                user_details.get("last_login", ""),
                user_details.get("group", "")
            ])
        users_ws.clear()
        users_ws.update(users_data)
        
        # 2. Save attendance records
        att_ws = sheet.worksheet("attendance")
        attendance_data = [st.session_state.attendance.columns.tolist()] + st.session_state.attendance.values.tolist()
        att_ws.clear()
        att_ws.update(attendance_data)
        
        # 3. Save credit data
        credit_ws = sheet.worksheet("credit_data")
        credit_data = [st.session_state.credit_data.columns.tolist()] + st.session_state.credit_data.values.tolist()
        credit_ws.clear()
        credit_ws.update(credit_data)
        
        # 4. Save reward data
        reward_ws = sheet.worksheet("reward_data")
        reward_data = [st.session_state.reward_data.columns.tolist()] + st.session_state.reward_data.values.tolist()
        reward_ws.clear()
        reward_ws.update(reward_data)
        
        # 5. Save scheduled events
        scheduled_ws = sheet.worksheet("scheduled_events")
        scheduled_data = [st.session_state.scheduled_events.columns.tolist()] + st.session_state.scheduled_events.values.tolist()
        scheduled_ws.clear()
        scheduled_ws.update(scheduled_data)
        
        # 6. Save occasional events
        occasional_ws = sheet.worksheet("occasional_events")
        occasional_data = [st.session_state.occasional_events.columns.tolist()] + st.session_state.occasional_events.values.tolist()
        occasional_ws.clear()
        occasional_ws.update(occasional_data)
        
        # 7. Save financial transactions
        money_ws = sheet.worksheet("money_data")
        money_data = [st.session_state.money_data.columns.tolist()] + st.session_state.money_data.values.tolist()
        money_ws.clear()
        money_ws.update(money_data)
        
        # 8. Save calendar events
        calendar_ws = sheet.worksheet("calendar_events")
        calendar_data = [["date", "event", "group"]]
        for date_str, event_details in st.session_state.calendar_events.items():
            calendar_data.append([date_str, event_details[0], event_details[1]])
        calendar_ws.clear()
        calendar_ws.update(calendar_data)
        
        # 9. Save announcements
        announcements_ws = sheet.worksheet("announcements")
        announcements_data = [["title", "text", "time", "author", "group"]]
        for announcement in st.session_state.announcements:
            announcements_data.append([
                announcement["title"],
                announcement["text"],
                announcement["time"],
                announcement["author"],
                announcement.get("group", "")
            ])
        announcements_ws.clear()
        announcements_ws.update(announcements_data)
        
        # 10. Save configuration settings
        config_ws = sheet.worksheet("config")
        config_data = [["key", "value"]]
        for key, value in st.session_state.config.items():
            config_data.append([key, str(value)])
        config_ws.clear()
        config_ws.update(config_data)
        
        # 11. Save group information
        groups_ws = sheet.worksheet("groups")
        groups_data = [["group", "members"]]
        for group_name, members in st.session_state.groups.items():
            groups_data.append([group_name, ", ".join(members)])
        groups_data.append(["group_codes", json.dumps(st.session_state.group_codes)])
        groups_ws.clear()
        groups_ws.update(groups_data)
        
        # 12. Save group leaders
        leaders_ws = sheet.worksheet("group_leader")
        leaders_data = [["group", "leader"]]
        for group_name, leader in st.session_state.group_leaders.items():
            leaders_data.append([group_name, leader])
        leaders_ws.clear()
        leaders_ws.update(leaders_data)
        
        # 13. Save group earnings
        earnings_ws = sheet.worksheet("group_earnings")
        earnings_data = [st.session_state.group_earnings.columns.tolist()] + st.session_state.group_earnings.values.tolist()
        earnings_ws.clear()
        earnings_ws.update(earnings_data)
        
        # 14. Save reimbursement requests
        reimburse_ws = sheet.worksheet("reimbursement_requests")
        reimburse_data = [st.session_state.reimbursement_requests.columns.tolist()] + st.session_state.reimbursement_requests.values.tolist()
        reimburse_ws.clear()
        reimburse_ws.update(reimburse_data)
        
        # 15. Save event approval requests
        events_ws = sheet.worksheet("event_approval_requests")
        events_data = [st.session_state.event_approval_requests.columns.tolist()] + st.session_state.event_approval_requests.values.tolist()
        events_ws.clear()
        events_ws.update(events_data)
        
        return True, "Data saved successfully"
    
    except Exception as e:
        return False, f"Save error: {str(e)}"

def load_all_data(sheet):
    """Load all application data from Google Sheets"""
    if not sheet:
        return False, "No connection to Google Sheets"
    
    try:
        # 1. Load user data
        users_ws = sheet.worksheet("users")
        users_data = users_ws.get_all_records()
        st.session_state.users = {}
        for row in users_data:
            if row["username"]:  # Skip empty rows
                st.session_state.users[row["username"]] = {
                    "password_hash": row["password_hash"],
                    "role": row["role"],
                    "created_at": row["created_at"],
                    "last_login": row["last_login"] if row["last_login"] else None,
                    "group": row.get("group", "")
                }
        
        # 2. Load attendance records
        att_ws = sheet.worksheet("attendance")
        att_data = att_ws.get_all_records()
        st.session_state.attendance = pd.DataFrame(att_data)
        st.session_state.meeting_names = [
            col for col in st.session_state.attendance.columns 
            if col != "Name"
        ]
        
        # 3. Load credit data
        credit_ws = sheet.worksheet("credit_data")
        credit_data = credit_ws.get_all_records()
        st.session_state.credit_data = pd.DataFrame(credit_data)
        
        # 4. Load reward data
        reward_ws = sheet.worksheet("reward_data")
        reward_data = reward_ws.get_all_records()
        st.session_state.reward_data = pd.DataFrame(reward_data)
        
        # 5. Load scheduled events
        scheduled_ws = sheet.worksheet("scheduled_events")
        scheduled_data = scheduled_ws.get_all_records()
        st.session_state.scheduled_events = pd.DataFrame(scheduled_data)
        
        # 6. Load occasional events
        occasional_ws = sheet.worksheet("occasional_events")
        occasional_data = occasional_ws.get_all_records()
        st.session_state.occasional_events = pd.DataFrame(occasional_data)
        
        # 7. Load financial transactions
        money_ws = sheet.worksheet("money_data")
        money_data = money_ws.get_all_records()
        st.session_state.money_data = pd.DataFrame(money_data)
        
        # 8. Load calendar events
        calendar_ws = sheet.worksheet("calendar_events")
        calendar_data = calendar_ws.get_all_records()
        st.session_state.calendar_events = {}
        for row in calendar_data:
            if row["date"]:  # Skip empty rows
                st.session_state.calendar_events[row["date"]] = [row["event"], row.get("group", "")]
        
        # 9. Load announcements
        announcements_ws = sheet.worksheet("announcements")
        announcements_data = announcements_ws.get_all_records()
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
        
        # 10. Load configuration settings
        config_ws = sheet.worksheet("config")
        config_data = config_ws.get_all_records()
        st.session_state.config = {}
        for row in config_data:
            if row["key"]:  # Skip empty rows
                # Convert string back to appropriate type
                value = row["value"]
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                st.session_state.config[row["key"]] = value
        
        # 11. Load group information
        groups_ws = sheet.worksheet("groups")
        groups_data = groups_ws.get_all_records()
        groups = {}
        group_codes = {}
        
        for row in groups_data:
            if row["group"] and row["group"] != "group_codes":
                groups[row["group"]] = row["members"].split(", ") if row["members"] else []
            elif row["group"] == "group_codes":
                try:
                    group_codes = json.loads(row["members"])
                except:
                    st.warning("Using default group codes")
                    group_codes = {
                        "G1": "G1CODE", "G2": "G2CODE", "G3": "G3CODE", "G4": "G4CODE",
                        "G5": "G5CODE", "G6": "G6CODE", "G7": "G7CODE", "G8": "G8CODE"
                    }
        
        st.session_state.groups = groups
        st.session_state.group_codes = group_codes
        
        # 12. Load group leaders
        leaders_ws = sheet.worksheet("group_leader")
        leaders_data = leaders_ws.get_all_records()
        leaders = {}
        for row in leaders_data:
            if row["group"]:
                leaders[row["group"]] = row["leader"] if row["leader"] else ""
        st.session_state.group_leaders = leaders
        
        # 13. Load group earnings
        earnings_ws = sheet.worksheet("group_earnings")
        earnings_data = earnings_ws.get_all_records()
        st.session_state.group_earnings = pd.DataFrame(earnings_data)
        
        # 14. Load reimbursement requests
        reimburse_ws = sheet.worksheet("reimbursement_requests")
        reimburse_data = reimburse_ws.get_all_records()
        st.session_state.reimbursement_requests = pd.DataFrame(reimburse_data)
        
        # 15. Load event approval requests
        events_ws = sheet.worksheet("event_approval_requests")
        events_data = events_ws.get_all_records()
        st.session_state.event_approval_requests = pd.DataFrame(events_data)
        
        return True, "Data loaded successfully"
    
    except Exception as e:
        return False, f"Load error: {str(e)}"

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
    # Verify the group code
    assigned_group = None
    for group, code in st.session_state.group_codes.items():
        if group_code == code:
            assigned_group = group
            break
    
    if not assigned_group:
        return False, "Invalid group code. Please check and try again."
    
    # Check if username already exists
    if username in st.session_state.users:
        return False, "Username already exists. Please choose another."
    
    # Create the new user
    current_time = datetime.now().isoformat()
    st.session_state.users[username] = {
        "password_hash": hash_password(password),
        "role": "user",
        "created_at": current_time,
        "last_login": None,
        "group": assigned_group
    }
    
    # Add user to their group
    if username not in st.session_state.groups[assigned_group]:
        st.session_state.groups[assigned_group].append(username)
    
    return True, f"Account created successfully for {username} in {assigned_group}"

def update_user_login_time(username):
    """Update the last login time for a user"""
    if username in st.session_state.users:
        st.session_state.users[username]["last_login"] = datetime.now().isoformat()
        sheet = connect_gsheets()
        if sheet:
            save_all_data(sheet)

# ------------------------------
# Login and Signup UI
# ------------------------------
def render_authentication_forms():
    """Render login and signup forms in the sidebar"""
    # Main title and subtitle on the main page
    st.title("STUDENT COUNCIL MANAGEMENT SYSTEM")
    st.write("---")
    st.subheader("Streamline your student council operations with our integrated management tools")
    st.write("Track attendance, manage credits, plan events, and coordinate group activities all in one place.")
    st.write("---")
    
    # Authentication forms in the sidebar
    with st.sidebar:
        st.header("Account Access")
        
        # Tabs for login and signup
        login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
        
        with login_tab:
            st.subheader("Login to Your Account")
            
            # Too many attempts handling
            if st.session_state.login_attempts >= 3:
                st.error("Too many failed login attempts. Please try again later.")
                return False
            
            # Login form fields
            username = st.text_input("Username", key="login_username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
            
            # Login and clear buttons
            col_login, col_clear = st.columns(2)
            with col_login:
                login_button = st.button("Login", key="login_btn", use_container_width=True)
            
            with col_clear:
                clear_button = st.button("Clear", key="clear_login", use_container_width=True, type="secondary")
            
            if clear_button:
                st.session_state.login_attempts = 0
                st.rerun()
            
            if login_button:
                if not username or not password:
                    st.error("Please enter both username and password")
                    return False
                
                # Check creator credentials
                creator_creds = st.secrets.get("creator", {})
                if username == creator_creds.get("username") and password == creator_creds.get("password"):
                    st.session_state.user = username
                    st.session_state.role = "creator"
                    update_user_login_time(username)
                    st.success("Successfully logged in as Creator")
                    return True
                
                # Check admin credentials from secrets
                admin_creds = st.secrets.get("admins", {})
                admin_users = ["Ahaan", "Bella", "Ella"]
                if username in admin_users and password == admin_creds.get(username.lower(), ""):
                    # Create admin user if not exists
                    if username not in st.session_state.users:
                        group_mapping = {"Ahaan": "G1", "Bella": "G2", "Ella": "G3"}
                        st.session_state.users[username] = {
                            "password_hash": hash_password(password),
                            "role": "admin",
                            "created_at": datetime.now().isoformat(),
                            "last_login": None,
                            "group": group_mapping[username]
                        }
                        st.session_state.groups[group_mapping[username]].append(username)
                        st.session_state.group_leaders[group_mapping[username]] = username
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                    
                    st.session_state.user = username
                    st.session_state.role = "admin"
                    st.session_state.current_group = {"Ahaan": "G1", "Bella": "G2", "Ella": "G3"}[username]
                    update_user_login_time(username)
                    st.success(f"Successfully logged in as Admin: {username}")
                    return True
                
                # Check regular users
                if username in st.session_state.users:
                    if verify_password(password, st.session_state.users[username]["password_hash"]):
                        st.session_state.user = username
                        st.session_state.role = st.session_state.users[username]["role"]
                        st.session_state.current_group = st.session_state.users[username].get("group", "")
                        update_user_login_time(username)
                        st.success(f"Welcome back, {username}!")
                        return True
                    else:
                        st.session_state.login_attempts += 1
                        st.error("Incorrect password. Please try again.")
                else:
                    st.session_state.login_attempts += 1
                    st.error("Username not found. Please check or create an account.")
        
        with signup_tab:
            st.subheader("Create a New Account")
            
            # Check if signup is enabled
            if not st.session_state.config.get("show_signup", True):
                st.info("Signup is currently disabled. Please contact an administrator.")
                return False
            
            # Signup form fields
            new_username = st.text_input("Choose a Username", key="new_username", placeholder="Your username")
            new_password = st.text_input("Create a Password", type="password", key="new_password", placeholder="At least 6 characters")
            confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password", placeholder="Re-enter your password")
            group_code = st.text_input("Group Code", key="group_code", placeholder="Enter your G1-G8 group code")
            
            # Create account button
            if st.button("Create Account", key="create_account_btn", use_container_width=True):
                # Validate input
                if not new_username or not new_password or not confirm_password or not group_code:
                    st.error("Please fill in all required fields")
                    return False
                
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                    return False
                
                if len(new_password) < 6:
                    st.error("Password must be at least 6 characters long")
                    return False
                
                # Create the user
                success, message = create_new_user(new_username, new_password, group_code)
                if success:
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    if sheet:
                        save_success, save_msg = save_all_data(sheet)
                        if save_success:
                            st.success(f"{message}. You can now log in.")
                        else:
                            st.warning(f"{message} but there was an error saving to the sheet: {save_msg}")
                    else:
                        st.warning(f"{message} but we couldn't connect to Google Sheets. Your account will only exist temporarily.")
                else:
                    st.error(message)
        
        return False

# ------------------------------
# Group Management Functions
# ------------------------------
def move_user_between_groups(username, from_group, to_group):
    """Move a user from one group to another"""
    if username not in st.session_state.groups[from_group]:
        return False, f"User {username} is not in {from_group}"
    
    # Remove from current group
    st.session_state.groups[from_group].remove(username)
    
    # Add to new group
    if username not in st.session_state.groups[to_group]:
        st.session_state.groups[to_group].append(username)
    
    # Update user's group in their profile
    if username in st.session_state.users:
        st.session_state.users[username]["group"] = to_group
    
    return True, f"Successfully moved {username} from {from_group} to {to_group}"

def assign_group_leader(group, username):
    """Assign a user as leader of a group"""
    if username not in st.session_state.groups[group]:
        return False, f"User {username} is not a member of {group}"
    
    st.session_state.group_leaders[group] = username
    return True, f"Successfully assigned {username} as leader of {group}"

def record_group_earnings(group, amount, description):
    """Record earnings for a specific group"""
    new_entry = pd.DataFrame([{
        "Group": group,
        "Date": date.today().strftime("%Y-%m-%d"),
        "Amount": amount,
        "Description": description,
        "Verified": "Pending"
    }])
    
    st.session_state.group_earnings = pd.concat(
        [st.session_state.group_earnings, new_entry], ignore_index=True
    )
    return True, "Earnings recorded successfully (pending admin verification)"

# ------------------------------
# Request Management Functions
# ------------------------------
def submit_reimbursement_request(group, requester, amount, purpose):
    """Submit a new reimbursement request"""
    request_id = f"REIMB-{random.randint(1000, 9999)}"
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
    
    st.session_state.reimbursement_requests = pd.concat(
        [st.session_state.reimbursement_requests, new_request], ignore_index=True
    )
    return True, f"Reimbursement request {request_id} submitted successfully"

def submit_event_approval_request(group, requester, event_name, description, 
                                 proposed_date, budget, file_content):
    """Submit a new event approval request with file attachment"""
    request_id = f"EVENT-{random.randint(1000, 9999)}"
    new_request = pd.DataFrame([{
        "Request ID": request_id,
        "Group": group,
        "Requester": requester,
        "Event Name": event_name,
        "Description": description,
        "Proposed Date": proposed_date,
        "Budget": budget,
        "File Upload": file_content,  # Base64 encoded content
        "Date Submitted": datetime.now().isoformat(),
        "Status": "Pending",
        "Admin Notes": ""
    }])
    
    st.session_state.event_approval_requests = pd.concat(
        [st.session_state.event_approval_requests, new_request], ignore_index=True
    )
    return True, f"Event approval request {request_id} submitted successfully"

def update_request_status(request_type, request_id, new_status, admin_notes=""):
    """Update the status of a reimbursement or event request"""
    if request_type == "reimbursement":
        requests_df = st.session_state.reimbursement_requests
    elif request_type == "event":
        requests_df = st.session_state.event_approval_requests
    else:
        return False, "Invalid request type specified"
    
    # Find the request index
    request_index = requests_df.index[requests_df["Request ID"] == request_id].tolist()
    if not request_index:
        return False, f"No {request_type} request found with ID: {request_id}"
    
    idx = request_index[0]
    
    # Update the request status
    if request_type == "reimbursement":
        st.session_state.reimbursement_requests.at[idx, "Status"] = new_status
        st.session_state.reimbursement_requests.at[idx, "Admin Notes"] = admin_notes
    else:
        st.session_state.event_approval_requests.at[idx, "Status"] = new_status
        st.session_state.event_approval_requests.at[idx, "Admin Notes"] = admin_notes
    
    return True, f"Request {request_id} updated to {new_status}"

# ------------------------------
# Main UI Components
# ------------------------------
def render_home_tab():
    """Render the home/dashboard tab"""
    st.subheader("Dashboard Overview")
    st.write("Welcome to the Student Council Management System. Use the tabs above to navigate through different features.")
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_users = len(st.session_state.users)
        st.metric("Total Members", total_users)
    
    with col2:
        total_meetings = len(st.session_state.meeting_names)
        st.metric("Total Meetings", total_meetings)
    
    with col3:
        total_events = len(st.session_state.scheduled_events) + len(st.session_state.occasional_events)
        st.metric("Total Events", total_events)
    
    st.write("---")
    
    # Upcoming events
    st.subheader("Upcoming Events")
    today = date.today()
    upcoming_events = []
    
    for date_str, event_details in st.session_state.calendar_events.items():
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if event_date >= today:
            upcoming_events.append({
                "date": date_str,
                "event": event_details[0],
                "group": event_details[1]
            })
    
    # Sort by date
    upcoming_events.sort(key=lambda x: x["date"])
    
    if upcoming_events:
        for event in upcoming_events[:5]:  # Show next 5 events
            st.write(f"**{event['date']}** - {event['event']} ({event['group']})")
    else:
        st.info("No upcoming events scheduled")
    
    st.write("---")
    
    # Recent announcements
    st.subheader("Recent Announcements")
    if st.session_state.announcements:
        # Sort announcements by date (newest first)
        sorted_announcements = sorted(
            st.session_state.announcements, 
            key=lambda x: x["time"], 
            reverse=True
        )
        
        for ann in sorted_announcements[:3]:  # Show 3 most recent
            # Show group-specific announcements only to members of that group or admins
            if (not ann["group"] or 
                ann["group"] == st.session_state.current_group or 
                is_admin()):
                
                with st.expander(f"{ann['title']} - {ann['time'].split('T')[0]}"):
                    st.write(ann["text"])
                    st.caption(f"Posted by: {ann['author']}")
    else:
        st.info("No announcements at this time")

def render_calendar_tab():
    """Render the calendar tab"""
    st.subheader("Event Calendar")
    year, month = st.session_state.current_calendar_month
    
    # Month navigation
    col_prev, col_title, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Previous Month"):
            new_month = month - 1 if month > 1 else 12
            new_year = year - 1 if month == 1 else year
            st.session_state.current_calendar_month = (new_year, new_month)
            st.rerun()
    
    with col_title:
        st.write(f"**{datetime(year, month, 1).strftime('%B %Y')}**")
    
    with col_next:
        if st.button("Next Month ▶"):
            new_month = month + 1 if month < 12 else 1
            new_year = year + 1 if month == 12 else year
            st.session_state.current_calendar_month = (new_year, new_month)
            st.rerun()
    
    # Calculate calendar days
    first_day = date(year, month, 1)
    last_day = (date(year, month+1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    days_in_month = (last_day - first_day).days + 1
    
    # Get first day of month's weekday (0=Monday)
    first_weekday = first_day.weekday()
    
    # Build calendar grid
    calendar_days = []
    # Add days from previous month
    for i in range(first_weekday):
        prev_date = first_day - timedelta(days=first_weekday - i)
        calendar_days.append((prev_date, False))
    # Add current month days
    for i in range(days_in_month):
        current_date = first_day + timedelta(days=i)
        calendar_days.append((current_date, True))
    # Add days from next month
    remaining_days = 7 - (len(calendar_days) % 7)
    if remaining_days < 7:
        for i in range(remaining_days):
            next_date = last_day + timedelta(days=i+1)
            calendar_days.append((next_date, False))
    
    # Display calendar headers
    weekday_headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_columns = st.columns(7)
    for col, header in zip(header_columns, weekday_headers):
        col.write(f"**{header}**")
    
    # Display calendar days
    for i in range(0, len(calendar_days), 7):
        week_days = calendar_days[i:i+7]
        day_columns = st.columns(7)
        
        for col, (date_obj, is_current_month) in zip(day_columns, week_days):
            date_string = date_obj.strftime("%Y-%m-%d")
            day_style = "color: #999;" if not is_current_month else "font-weight: bold;"
            
            # Highlight today
            if date_obj == date.today():
                day_style += "background-color: #e3f2fd; border-radius: 50%; padding: 5px;"
            
            # Get event information
            event_details = st.session_state.calendar_events.get(date_string, ["", ""])
            event_text, event_group = event_details
            event_display = f"\n{event_text[:10]}..." if event_text else ""
            if event_group:
                event_display += f" ({event_group})"
            
            # Display the day with styling
            col.markdown(
                f'<div style="{day_style}">{date_obj.day}{event_display}</div>',
                unsafe_allow_html=True
            )
    
    # Add new event (admin and group leaders only)
    if is_admin() or is_group_leader(st.session_state.current_group):
        with st.expander("Add New Event to Calendar"):
            event_date = st.date_input("Event Date")
            event_name = st.text_input("Event Name")
            event_group = st.selectbox("Event Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
            
            if st.button("Save Event"):
                date_str = event_date.strftime("%Y-%m-%d")
                st.session_state.calendar_events[date_str] = [event_name, event_group]
                sheet = connect_gsheets()
                if sheet:
                    success, msg = save_all_data(sheet)
                    if success:
                        st.success("Event added to calendar")
                        st.rerun()
                    else:
                        st.error(f"Failed to save event: {msg}")

def render_attendance_tab():
    """Render the attendance tab"""
    st.subheader("Attendance Records")
    
    # Display attendance data
    if not st.session_state.attendance.empty:
        st.dataframe(st.session_state.attendance)
    else:
        st.info("No attendance records available yet. Add your first meeting to begin tracking attendance.")
    
    # Add new meeting (admin only)
    if is_admin():
        with st.expander("Manage Meetings and Attendance", expanded=False):
            st.subheader("Add New Meeting")
            new_meeting_name = st.text_input("Meeting Name")
            
            if st.button("Create New Meeting"):
                if new_meeting_name and new_meeting_name not in st.session_state.meeting_names:
                    # Add new column to attendance dataframe
                    st.session_state.attendance[new_meeting_name] = False
                    st.session_state.meeting_names.append(new_meeting_name)
                    
                    # Save changes
                    sheet = connect_gsheets()
                    if sheet:
                        success, msg = save_all_data(sheet)
                        if success:
                            st.success(f"New meeting '{new_meeting_name}' created")
                            st.rerun()
                        else:
                            st.error(f"Failed to create meeting: {msg}")
                elif not new_meeting_name:
                    st.error("Please enter a meeting name")
                else:
                    st.error("A meeting with this name already exists")
            
            # Update existing attendance
            if st.session_state.meeting_names:
                st.subheader("Update Attendance")
                selected_meeting = st.selectbox("Select Meeting", st.session_state.meeting_names)
                
                if selected_meeting:
                    st.write(f"Update attendance for: {selected_meeting}")
                    attendance_updated = False
                    
                    # Display checkboxes for each member
                    for idx, member_name in enumerate(st.session_state.attendance["Name"]):
                        current_status = st.session_state.attendance.at[idx, selected_meeting]
                        new_status = st.checkbox(
                            member_name, 
                            value=current_status, 
                            key=f"att_{selected_meeting}_{idx}"
                        )
                        
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
                                    st.success("Attendance updated successfully")
                                else:
                                    st.error(f"Failed to save attendance: {msg}")
    
    # Attendance statistics
    if st.session_state.meeting_names and not st.session_state.attendance.empty:
        st.subheader("Attendance Statistics")
        attendance_rates = []
        
        for _, row in st.session_state.attendance.iterrows():
            name = row["Name"]
            meetings_attended = sum(row[meeting] for meeting in st.session_state.meeting_names)
            total_meetings = len(st.session_state.meeting_names)
            attendance_rate = (meetings_attended / total_meetings) * 100 if total_meetings > 0 else 0
            
            attendance_rates.append({
                "Name": name,
                "Meetings Attended": meetings_attended,
                "Total Meetings": total_meetings,
                "Attendance Rate": f"{attendance_rate:.1f}%"
            })
        
        st.dataframe(pd.DataFrame(attendance_rates))

def render_credits_tab():
    """Render the credits and rewards tab"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Student Credits")
        
        if not st.session_state.credit_data.empty:
            st.dataframe(st.session_state.credit_data)
        else:
            st.info("No credit data available yet. Add students to begin tracking credits.")
        
        # Manage credits (admin only)
        if is_admin():
            with st.expander("Manage Student Credits"):
                if not st.session_state.credit_data.empty:
                    student_name = st.selectbox("Select Student", st.session_state.credit_data["Name"].tolist())
                    credit_amount = st.number_input("Credit Amount", min_value=-500, max_value=1000)
                    reason = st.text_input("Reason for Adjustment")
                    
                    if st.button("Update Credits"):
                        student_index = st.session_state.credit_data.index[
                            st.session_state.credit_data["Name"] == student_name
                        ].tolist()[0]
                        
                        # Update total credits
                        st.session_state.credit_data.at[student_index, "Total_Credits"] += credit_amount
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Updated {student_name}'s credits by {credit_amount}")
                            else:
                                st.error(f"Failed to update credits: {msg}")
                else:
                    st.info("Add students to manage their credits")
        
        # Redeem credits (all users)
        with st.expander("Redeem Credits for Rewards"):
            if not st.session_state.credit_data.empty and not st.session_state.reward_data.empty:
                student_name = st.selectbox("Your Name", st.session_state.credit_data["Name"].tolist(), key="redeem_name")
                reward_name = st.selectbox("Select Reward", st.session_state.reward_data["Reward"].tolist())
                
                if st.button("Redeem Reward"):
                    # Get student and reward data
                    student_idx = st.session_state.credit_data.index[
                        st.session_state.credit_data["Name"] == student_name
                    ].tolist()[0]
                    
                    reward_data = st.session_state.reward_data[
                        st.session_state.reward_data["Reward"] == reward_name
                    ].iloc[0]
                    
                    # Check if student has enough credits
                    current_credits = st.session_state.credit_data.at[student_idx, "Total_Credits"]
                    if current_credits >= reward_data["Cost"] and reward_data["Stock"] > 0:
                        # Update student credits
                        st.session_state.credit_data.at[student_idx, "Total_Credits"] -= reward_data["Cost"]
                        st.session_state.credit_data.at[student_idx, "RedeemedCredits"] += reward_data["Cost"]
                        
                        # Update reward stock
                        reward_idx = st.session_state.reward_data.index[
                            st.session_state.reward_data["Reward"] == reward_name
                        ].tolist()[0]
                        st.session_state.reward_data.at[reward_idx, "Stock"] -= 1
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Successfully redeemed {reward_name} for {reward_data['Cost']} credits")
                            else:
                                st.error(f"Failed to process redemption: {msg}")
                    elif current_credits < reward_data["Cost"]:
                        st.error("Not enough credits to redeem this reward")
                    else:
                        st.error("This reward is out of stock")
            else:
                st.info("No students or rewards available for redemption")
    
    with col2:
        st.subheader("Available Rewards")
        
        if not st.session_state.reward_data.empty:
            st.dataframe(st.session_state.reward_data)
        else:
            st.info("No rewards available yet. Add rewards to the catalog.")
        
        # Manage rewards (admin only)
        if is_admin():
            with st.expander("Manage Reward Catalog"):
                st.subheader("Add New Reward")
                reward_name = st.text_input("Reward Name")
                reward_cost = st.number_input("Credit Cost", min_value=10, step=10)
                reward_stock = st.number_input("Initial Stock", min_value=0, step=1)
                
                if st.button("Add Reward"):
                    if reward_name:
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
                    else:
                        st.error("Please enter a reward name")
                
                st.subheader("Remove Reward")
                if not st.session_state.reward_data.empty:
                    reward_to_remove = st.selectbox("Select Reward to Remove", st.session_state.reward_data["Reward"].tolist())
                    
                    if st.button("Delete Selected Reward"):
                        st.session_state.reward_data = st.session_state.reward_data[
                            st.session_state.reward_data["Reward"] != reward_to_remove
                        ]
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Removed reward: {reward_to_remove}")
                            else:
                                st.error(f"Failed to remove reward: {msg}")

def render_events_tab():
    """Render the events tab"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Scheduled Events")
        
        if not st.session_state.scheduled_events.empty:
            st.dataframe(st.session_state.scheduled_events)
        else:
            st.info("No scheduled events yet. Add a recurring event.")
        
        # Add scheduled event (admin and group leaders)
        if is_admin() or is_group_leader(st.session_state.current_group):
            with st.expander("Add Scheduled Event"):
                event_name = st.text_input("Event Name")
                funds_per_event = st.number_input("Funds Per Event", min_value=0)
                frequency = st.number_input("Frequency Per Month", min_value=1, max_value=4)
                responsible_group = st.selectbox("Responsible Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
                
                if st.button("Create Scheduled Event"):
                    if event_name:
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
                                st.success(f"Created scheduled event: {event_name}")
                            else:
                                st.error(f"Failed to create event: {msg}")
                    else:
                        st.error("Please enter an event name")
    
    with col2:
        st.subheader("Occasional Events")
        
        if not st.session_state.occasional_events.empty:
            st.dataframe(st.session_state.occasional_events)
        else:
            st.info("No occasional events yet. Add a one-time event.")
        
        # Add occasional event (admin and group leaders)
        if is_admin() or is_group_leader(st.session_state.current_group):
            with st.expander("Add Occasional Event"):
                event_name = st.text_input("Event Name", key="occasional_name")
                funds_raised = st.number_input("Total Funds Raised", min_value=0)
                event_cost = st.number_input("Total Cost", min_value=0)
                staff_required = st.radio("Requires Many Staff?", ["Yes", "No"])
                prep_time = st.number_input("Preparation Time (Days)", min_value=1)
                event_rating = st.slider("Event Rating (1-5)", 1, 5)
                responsible_group = st.selectbox("Responsible Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"], key="occasional_group")
                
                if st.button("Create Occasional Event"):
                    if event_name:
                        new_event = pd.DataFrame([{
                            "Event Name": event_name,
                            "Total Funds Raised": funds_raised,
                            "Cost": event_cost,
                            "Staff Many Or Not": staff_required,
                            "Preparation Time": prep_time,
                            "Rating": event_rating,
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
                                st.success(f"Created occasional event: {event_name}")
                            else:
                                st.error(f"Failed to create event: {msg}")
                    else:
                        st.error("Please enter an event name")

def render_financials_tab():
    """Render the financials tab"""
    st.subheader("Financial Transactions")
    
    if not st.session_state.money_data.empty:
        st.dataframe(st.session_state.money_data)
    else:
        st.info("No financial transactions recorded yet.")
    
    # Add new transaction (admin only)
    if is_admin():
        with st.expander("Record New Transaction"):
            amount = st.number_input("Amount", min_value=-10000, max_value=10000)
            description = st.text_input("Description")
            transaction_group = st.selectbox("Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "General"])
            
            if st.button("Record Transaction"):
                if description:
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
                            st.success("Transaction recorded successfully")
                        else:
                            st.error(f"Failed to record transaction: {msg}")
                else:
                    st.error("Please enter a description")
    
    # Financial summary
    if not st.session_state.money_data.empty:
        st.subheader("Financial Summary")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_income = st.session_state.money_data[st.session_state.money_data["Amount"] > 0]["Amount"].sum()
            st.metric("Total Income", f"${total_income:.2f}")
        
        with col2:
            total_expenses = abs(st.session_state.money_data[st.session_state.money_data["Amount"] < 0]["Amount"].sum())
            st.metric("Total Expenses", f"${total_expenses:.2f}")
        
        with col3:
            current_balance = total_income - total_expenses
            st.metric("Current Balance", f"${current_balance:.2f}")
        
        # Group financial breakdown
        st.subheader("Group Financial Breakdown")
        group_balances = {}
        
        for group in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]:
            group_transactions = st.session_state.money_data[st.session_state.money_data["Group"] == group]
            income = group_transactions[group_transactions["Amount"] > 0]["Amount"].sum()
            expenses = abs(group_transactions[group_transactions["Amount"] < 0]["Amount"].sum())
            group_balances[group] = {
                "Income": income,
                "Expenses": expenses,
                "Balance": income - expenses
            }
        
        # Convert to DataFrame and display
        group_finance_df = pd.DataFrame.from_dict(group_balances, orient="index")
        st.dataframe(group_finance_df)

def render_group_tab(group):
    """Render the tab for a specific group"""
    st.subheader(f"Group {group}")
    
    # Display group members
    st.write("**Group Members:**")
    members = st.session_state.groups.get(group, [])
    leader = st.session_state.group_leaders.get(group, "")
    
    if members:
        for member in members:
            if member == leader:
                st.write(f"- {member} (Group Leader)")
            else:
                st.write(f"- {member}")
    else:
        st.info("No members in this group yet")
    
    # Group-specific actions (members only)
    if st.session_state.current_group == group or is_admin():
        # Record earnings
        with st.expander("Record Group Earnings"):
            amount = st.number_input("Amount Earned", min_value=0, key=f"earn_{group}")
            description = st.text_input("Description of Earnings", key=f"earn_desc_{group}")
            
            if st.button("Save Earnings", key=f"save_earn_{group}"):
                if description:
                    success, msg = record_group_earnings(group, amount, description)
                    if success:
                        sheet = connect_gsheets()
                        if sheet:
                            save_success, save_msg = save_all_data(sheet)
                            if save_success:
                                st.success(msg)
                            else:
                                st.warning(f"{msg} but could not save to sheet: {save_msg}")
                else:
                    st.error("Please enter a description")
        
        # Reimbursement request
        with st.expander("Request Reimbursement"):
            amount = st.number_input("Reimbursement Amount", min_value=10, key=f"reimb_{group}")
            purpose = st.text_area("Purpose for Reimbursement", key=f"reimb_purpose_{group}")
            
            if st.button("Submit Reimbursement Request", key=f"submit_reimb_{group}"):
                if purpose:
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
                                st.warning(f"{msg} but could not save to sheet: {save_msg}")
                else:
                    st.error("Please enter a purpose for the reimbursement")
        
        # Event approval request
        with st.expander("Request Event Approval"):
            event_name = st.text_input("Event Name", key=f"event_name_{group}")
            description = st.text_area("Event Description", key=f"event_desc_{group}")
            proposed_date = st.date_input("Proposed Date", key=f"event_date_{group}")
            budget = st.number_input("Estimated Budget", min_value=0, key=f"event_budget_{group}")
            uploaded_file = st.file_uploader("Upload Proposal Document", key=f"event_file_{group}")
            
            if st.button("Submit Event Request", key=f"submit_event_{group}"):
                if not event_name or not description:
                    st.error("Please fill in event name and description")
                elif not uploaded_file:
                    st.error("Please upload a proposal document")
                else:
                    # Encode file content as base64 for storage
                    file_content = base64.b64encode(uploaded_file.getvalue()).decode()
                    
                    success, msg = submit_event_approval_request(
                        group, st.session_state.user, event_name, description,
                        proposed_date.strftime("%Y-%m-%d"), budget, file_content
                    )
                    
                    if success:
                        sheet = connect_gsheets()
                        if sheet:
                            save_success, save_msg = save_all_data(sheet)
                            if save_success:
                                st.success(msg)
                            else:
                                st.warning(f"{msg} but could not save to sheet: {save_msg}")
    
    # Group earnings history
    st.subheader(f"{group} Earnings History")
    group_earnings = st.session_state.group_earnings[st.session_state.group_earnings["Group"] == group]
    
    if not group_earnings.empty:
        st.dataframe(group_earnings)
    else:
        st.info("No earnings recorded for this group yet")
    
    # Group requests
    st.subheader(f"{group} Pending Requests")
    
    # Reimbursement requests
    st.write("**Reimbursement Requests:**")
    group_reimb = st.session_state.reimbursement_requests[
        (st.session_state.reimbursement_requests["Group"] == group) &
        (st.session_state.reimbursement_requests["Status"] == "Pending")
    ]
    
    if not group_reimb.empty:
        st.dataframe(group_reimb)
    else:
        st.info("No pending reimbursement requests")
    
    # Event approval requests
    st.write("**Event Approval Requests:**")
    group_events = st.session_state.event_approval_requests[
        (st.session_state.event_approval_requests["Group"] == group) &
        (st.session_state.event_approval_requests["Status"] == "Pending")
    ]
    
    if not group_events.empty:
        st.dataframe(group_events[["Request ID", "Event Name", "Proposed Date", "Budget"]])
    else:
        st.info("No pending event approval requests")

def render_admin_tab():
    """Render the admin dashboard tab"""
    st.subheader("Admin Dashboard")
    
    # User management section
    with st.expander("User Management", expanded=False):
        st.subheader("Current Users")
        
        # Prepare user data for display
        user_list = []
        for username, details in st.session_state.users.items():
            user_list.append({
                "Username": username,
                "Role": details["role"],
                "Group": details.get("group", "N/A"),
                "Created": details["created_at"].split("T")[0],
                "Last Login": details["last_login"].split("T")[0] if details["last_login"] else "Never"
            })
        
        if user_list:
            st.dataframe(pd.DataFrame(user_list))
        else:
            st.info("No users in the system yet")
        
        # Manage user roles
        if user_list:
            st.subheader("Manage User Roles")
            selected_user = st.selectbox("Select User", [user["Username"] for user in user_list])
            new_role = st.selectbox("New Role", ["user", "admin"])
            
            if st.button("Update User Role"):
                if selected_user in st.session_state.users:
                    # Prevent changing creator role
                    if st.session_state.users[selected_user]["role"] == "creator":
                        st.error("Cannot change creator role")
                    else:
                        st.session_state.users[selected_user]["role"] = new_role
                        
                        # Save changes
                        sheet = connect_gsheets()
                        if sheet:
                            success, msg = save_all_data(sheet)
                            if success:
                                st.success(f"Updated {selected_user}'s role to {new_role}")
                            else:
                                st.error(f"Failed to update role: {msg}")
        
        # Add student to credit system
        st.subheader("Add Student to Credit System")
        student_name = st.text_input("Student Name")
        
        if st.button("Add Student"):
            if student_name and student_name not in st.session_state.credit_data["Name"].tolist():
                new_student = pd.DataFrame([{
                    "Name": student_name,
                    "Total_Credits": 0,
                    "RedeemedCredits": 0
                }])
                
                st.session_state.credit_data = pd.concat(
                    [st.session_state.credit_data, new_student], ignore_index=True
                )
                
                # Also add to attendance if not already present
                if student_name not in st.session_state.attendance["Name"].tolist():
                    new_attendance = pd.DataFrame([{"Name": student_name}])
                    st.session_state.attendance = pd.concat(
                        [st.session_state.attendance, new_attendance], ignore_index=True
                    )
                    
                    # Set default attendance to False for existing meetings
                    for meeting in st.session_state.meeting_names:
                        st.session_state.attendance[meeting].iloc[-1] = False
                
                # Save changes
                sheet = connect_gsheets()
                if sheet:
                    success, msg = save_all_data(sheet)
                    if success:
                        st.success(f"Added {student_name} to the system")
                    else:
                        st.error(f"Failed to add student: {msg}")
            elif not student_name:
                st.error("Please enter a student name")
            else:
                st.error("This student is already in the system")
    
    # Group management section
    with st.expander("Group Management", expanded=False):
        st.subheader("Move User Between Groups")
        
        if st.session_state.users:
            user_to_move = st.selectbox("Select User to Move", list(st.session_state.users.keys()))
            current_group = st.session_state.users[user_to_move].get("group", "")
            
            if current_group:
                st.write(f"Current Group: {current_group}")
                new_group = st.selectbox(
                    "Move to Group", 
                    [g for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"] if g != current_group]
                )
                
                if st.button("Move User"):
                    success, msg = move_user_between_groups(user_to_move, current_group, new_group)
                    if success:
                        sheet = connect_gsheets()
                        if sheet:
                            save_success, save_msg = save_all_data(sheet)
                            if save_success:
                                st.success(msg)
                            else:
                                st.warning(f"{msg} but could not save to sheet: {save_msg}")
                    else:
                        st.error(msg)
        
        # Assign group leaders
        st.subheader("Assign Group Leaders")
        selected_group = st.selectbox("Select Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
        group_members = st.session_state.groups.get(selected_group, [])
        
        if group_members:
            new_leader = st.selectbox("Select Group Leader", group_members)
            
            if st.button("Set as Leader"):
                success, msg = assign_group_leader(selected_group, new_leader)
                if success:
                    sheet = connect_gsheets()
                    if sheet:
                        save_success, save_msg = save_all_data(sheet)
                        if save_success:
                            st.success(msg)
                        else:
                            st.warning(f"{msg} but could not save to sheet: {save_msg}")
                else:
                    st.error(msg)
        else:
            st.info(f"No members in {selected_group} to assign as leader")
        
        # Manage group codes
        st.subheader("Manage Group Codes")
        for group in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**{group}**")
            with col2:
                current_code = st.session_state.group_codes.get(group, "")
                new_code = st.text_input("Code", current_code, key=f"code_{group}")
            with col3:
                if st.button("Update", key=f"update_code_{group}") and new_code:
                    st.session_state.group_codes[group] = new_code
                    sheet = connect_gsheets()
                    if sheet:
                        save_success, save_msg = save_all_data(sheet)
                        if save_success:
                            st.success(f"Updated {group} code")
                        else:
                            st.warning(f"Code updated but could not save to sheet: {save_msg}")
    
    # Approve requests section
    with st.expander("Approve Requests", expanded=False):
        # Reimbursement requests
        st.subheader("Reimbursement Requests")
        pending_reimbursements = st.session_state.reimbursement_requests[
            st.session_state.reimbursement_requests["Status"] == "Pending"
        ]
        
        if not pending_reimbursements.empty:
            st.dataframe(pending_reimbursements)
            
            selected_request = st.selectbox(
                "Select Reimbursement Request", 
                pending_reimbursements["Request ID"].tolist()
            )
            
            action = st.radio("Action", ["Approve", "Deny"], key="reimb_action")
            admin_notes = st.text_input("Admin Notes", key="reimb_notes")
            
            if st.button("Process Reimbursement Request"):
                success, msg = update_request_status(
                    "reimbursement", selected_request, action, admin_notes
                )
                
                if success:
                    # If approved, add to financial records
                    if action == "Approve":
                        request_data = pending_reimbursements[
                            pending_reimbursements["Request ID"] == selected_request
                        ].iloc[0]
                        
                        # Record as expense
                        new_transaction = pd.DataFrame([{
                            "Amount": -float(request_data["Amount"]),
                            "Description": f"Reimbursement: {request_data['Purpose']}",
                            "Date": date.today().strftime("%Y-%m-%d"),
                            "Handled By": st.session_state.user,
                            "Group": request_data["Group"]
                        }])
                        
                        st.session_state.money_data = pd.concat(
                            [st.session_state.money_data, new_transaction], ignore_index=True
                        )
                    
                    # Save changes
                    sheet = connect_gsheets()
                    if sheet:
                        save_success, save_msg = save_all_data(sheet)
                        if save_success:
                            st.success(msg)
                        else:
                            st.warning(f"{msg} but could not save to sheet: {save_msg}")
                else:
                    st.error(msg)
        else:
            st.info("No pending reimbursement requests")
        
        # Event approval requests
        st.subheader("Event Approval Requests")
        pending_events = st.session_state.event_approval_requests[
            st.session_state.event_approval_requests["Status"] == "Pending"
        ]
        
        if not pending_events.empty:
            st.dataframe(pending_events[["Request ID", "Group", "Event Name", "Proposed Date", "Budget"]])
            
            selected_event = st.selectbox(
                "Select Event Request", 
                pending_events["Request ID"].tolist()
            )
            
            action = st.radio("Action", ["Approve", "Deny"], key="event_action")
            admin_notes = st.text_input("Admin Notes", key="event_notes")
            
            if st.button("Process Event Request"):
                success, msg = update_request_status(
                    "event", selected_event, action, admin_notes
                )
                
                if success:
                    # If approved, add to calendar
                    if action == "Approve":
                        event_data = pending_events[
                            pending_events["Request ID"] == selected_event
                        ].iloc[0]
                        
                        st.session_state.calendar_events[event_data["Proposed Date"]] = [
                            event_data["Event Name"], event_data["Group"]
                        ]
                    
                    # Save changes
                    sheet = connect_gsheets()
                    if sheet:
                        save_success, save_msg = save_all_data(sheet)
                        if save_success:
                            st.success(msg)
                        else:
                            st.warning(f"{msg} but could not save to sheet: {save_msg}")
                else:
                    st.error(msg)
        else:
            st.info("No pending event approval requests")
    
    # System configuration
    with st.expander("System Configuration", expanded=False):
        st.subheader("System Settings")
        signup_status = st.checkbox(
            "Allow New User Signups", 
            value=st.session_state.config.get("show_signup", True)
        )
        
        if st.button("Update Settings"):
            st.session_state.config["show_signup"] = signup_status
            
            # Save changes
            sheet = connect_gsheets()
            if sheet:
                success, msg = save_all_data(sheet)
                if success:
                    st.success("System settings updated successfully")
                else:
                    st.error(f"Failed to update settings: {msg}")
        
        # Announcements management
        st.subheader("Manage Announcements")
        with st.expander("Create New Announcement"):
            ann_title = st.text_input("Announcement Title")
            ann_text = st.text_area("Announcement Text")
            ann_group = st.selectbox(
                "Group (leave as 'All' for system-wide)", 
                ["All", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]
            )
            
            if st.button("Post Announcement"):
                if ann_title and ann_text:
                    new_announcement = {
                        "title": ann_title,
                        "text": ann_text,
                        "time": datetime.now().isoformat(),
                        "author": st.session_state.user,
                        "group": "" if ann_group == "All" else ann_group
                    }
                    
                    st.session_state.announcements.append(new_announcement)
                    
                    # Save changes
                    sheet = connect_gsheets()
                    if sheet:
                        success, msg = save_all_data(sheet)
                        if success:
                            st.success("Announcement posted successfully")
                        else:
                            st.error(f"Failed to post announcement: {msg}")
                else:
                    st.error("Please enter both title and text")

# ------------------------------
# Permission Check Functions
# ------------------------------
def is_admin():
    """Check if current user has admin or creator privileges"""
    return st.session_state.get("role") in ["admin", "creator"]

def is_group_leader(group):
    """Check if current user is the leader of the specified group"""
    if not group or group not in st.session_state.group_leaders:
        return False
    return st.session_state.get("user") == st.session_state.group_leaders.get(group, "")

# ------------------------------
# Main Application Function
# ------------------------------
def main():
    # Initialize session state with empty values
    initialize_session_state()
    
    # Connect to Google Sheets
    sheet = connect_gsheets()
    
    # Load data from Google Sheets if connection is successful
    if sheet:
        success, message = load_all_data(sheet)
        if not success:
            st.warning(f"Note: {message}. Starting with empty data.")
    
    # Handle authentication
    if not st.session_state.user:
        if render_authentication_forms():
            st.rerun()
        return
    
    # Main application interface after login
    st.title("STUDENT COUNCIL MANAGEMENT SYSTEM")
    
    # Sidebar with user info and logout
    with st.sidebar:
        st.header("User Information")
        st.write(f"**Username:** {st.session_state.user}")
        st.write(f"**Role:** {st.session_state.role}")
        st.write(f"**Group:** {st.session_state.current_group or 'N/A'}")
        st.write("---")
        
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.role = None
            st.session_state.current_group = None
            st.rerun()
        
        # Quick links
        st.header("Quick Links")
        if st.button("Home", use_container_width=True):
            st.session_state.active_tab = "Home"
            st.rerun()
        
        if is_admin() and st.button("Admin Dashboard", use_container_width=True):
            st.session_state.active_tab = "Admin Dashboard"
            st.rerun()
    
    # Display announcements
    if st.session_state.announcements:
        with st.expander("Announcements", expanded=True):
            # Show 3 most recent announcements
            recent_announcements = sorted(
                st.session_state.announcements, 
                key=lambda x: x["time"], 
                reverse=True
            )[:3]
            
            for ann in recent_announcements:
                # Show group-specific announcements only to members or admins
                if (not ann["group"] or 
                    ann["group"] == st.session_state.current_group or 
                    is_admin()):
                    
                    st.info(f"**{ann['title']}** ({ann['time'].split('T')[0]})\n\n{ann['text']}")
    
    # Define main tabs
    main_tabs = [
        "Home", "Calendar", "Attendance", "Credits & Rewards", 
        "Events", "Financials"
    ]
    
    # Add admin dashboard tab if user is admin
    if is_admin():
        main_tabs.append("Admin Dashboard")
    
    # Add group tabs (G1-G8) after main tabs
    group_tabs = [f"Group {g}" for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]]
    all_tabs = main_tabs + group_tabs
    
    # Create tabs interface
    tabs = st.tabs(all_tabs)
    
    # Map tabs to their respective rendering functions
    tab_functions = {
        "Home": render_home_tab,
        "Calendar": render_calendar_tab,
        "Attendance": render_attendance_tab,
        "Credits & Rewards": render_credits_tab,
        "Events": render_events_tab,
        "Financials": render_financials_tab
    }
    
    # Add admin dashboard function if present
    if "Admin Dashboard" in all_tabs:
        tab_functions["Admin Dashboard"] = render_admin_tab
    
    # Add group tab functions
    for group in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]:
        tab_functions[f"Group {group}"] = lambda g=group: render_group_tab(g)
    
    # Render the selected tab
    for i, tab_name in enumerate(all_tabs):
        with tabs[i]:
            if tab_name in tab_functions:
                tab_functions[tab_name]()

if __name__ == "__main__":
    main()
