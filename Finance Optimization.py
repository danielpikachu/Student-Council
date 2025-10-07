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

# ------------------------------
# App Configuration
# ------------------------------
st.set_page_config(
    page_title="SCIS Student Council",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# Google Sheets Connection & Setup
# ------------------------------
def connect_gsheets():
    """Connect to Google Sheets and ensure all required worksheets exist"""
    try:
        # Get secrets from Streamlit
        secrets = st.secrets["google_sheets"]
        
        # Create credentials dictionary
        creds = {
            "type": "service_account",
            "client_email": secrets["service_account_email"],
            "private_key_id": secrets["private_key_id"],
            "client_id": "100000000000000000000", 
            "private_key": secrets["private_key"].replace("\\n", "\n"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        
        # Authenticate and connect
        client = gspread.service_account_from_dict(creds)
        sheet = client.open_by_url(secrets["sheet_url"])
        
        # List of ALL required worksheets (15 total)
        required_worksheets = [
            "users", "attendance", "credit_data", "reward_data",
            "scheduled_events", "occasional_events", "money_data",
            "calendar_events", "announcements", "config",
            "groups", "group_leader", "group_earnings",
            "reimbursement_requests", "event_approval_requests"
        ]
        
        # Create any missing worksheets
        existing_sheets = [ws.title for ws in sheet.worksheets()]
        for ws_name in required_worksheets:
            if ws_name not in existing_sheets:
                sheet.add_worksheet(title=ws_name, rows="1000", cols="30")
                st.success(f"Created missing worksheet: {ws_name}")
        
        return sheet
    
    except Exception as e:
        st.error(f"Connection failed: {str(e)}")
        return None

# ------------------------------
# Core Initialization
# ------------------------------
def initialize_session_state():
    """Initialize all required session state variables"""
    required_states = {
        # User session
        "user": None, "role": None, "login_attempts": 0,
        "current_group": None, "show_password_reset": False,
        
        # UI state
        "spinning": False, "winner": None, "allocation_count": 0,
        "current_calendar_month": (date.today().year, date.today().month),
        "active_tab": "Calendar", "show_help": False,
        
        # Data storage
        "users": {}, "attendance": pd.DataFrame(), "credit_data": pd.DataFrame(),
        "reward_data": pd.DataFrame(), "scheduled_events": pd.DataFrame(),
        "occasional_events": pd.DataFrame(), "money_data": pd.DataFrame(),
        "calendar_events": {}, "announcements": [], "config": {},
        "meeting_names": [],
        
        # New group features
        "groups": {"G1": [], "G2": [], "G3": [], "G4": [], "G5": [], "G6": [], "G7": [], "G8": []},
        "group_leaders": {}, "group_earnings": pd.DataFrame(),
        "reimbursement_requests": pd.DataFrame(),
        "event_approval_requests": pd.DataFrame(),
        "group_codes": {"G1": "G1CODE", "G2": "G2CODE", "G3": "G3CODE", "G4": "G4CODE",
                        "G5": "G5CODE", "G6": "G6CODE", "G7": "G7CODE", "G8": "G8CODE"}
    }
    for key, default in required_states.items():
        if key not in st.session_state:
            st.session_state[key] = default

def initialize_default_data():
    """Set up default data if Google Sheets is empty"""
    # Default members
    members = ["Alice", "Bob", "Charlie", "Diana", "Evan", "Ahaan", "Bella", "Ella"]
    
    # Attendance
    st.session_state.meeting_names = ["First Meeting", "Planning Session"]
    att_data = {
        "Name": members, 
        "First Meeting": [True, True, False, True, False, True, True, True],
        "Planning Session": [True, False, True, True, True, True, True, True]
    }
    st.session_state.attendance = pd.DataFrame(att_data)
    
    # Credits
    st.session_state.credit_data = pd.DataFrame({
        "Name": members,
        "Total_Credits": [200 for _ in members],
        "RedeemedCredits": [0 for _ in members]
    })
    
    # Rewards
    st.session_state.reward_data = pd.DataFrame({
        "Reward": ["Bubble Tea", "Chips", "Café Coupon", "Movie Ticket", "Gift Card"],
        "Cost": [50, 30, 80, 120, 200],
        "Stock": [10, 20, 5, 3, 2]
    })
    
    # Events
    st.session_state.scheduled_events = pd.DataFrame(columns=[
        "Event Name", "Funds Per Event", "Frequency Per Month", "Total Funds", "Responsible Group"
    ])
    
    st.session_state.occasional_events = pd.DataFrame(columns=[
        "Event Name", "Total Funds Raised", "Cost", "Staff Many Or Not",
        "Preparation Time", "Rating", "Responsible Group"
    ])
    
    # Financial
    st.session_state.money_data = pd.DataFrame(columns=[
        "Amount", "Description", "Date", "Handled By", "Group"
    ])
    
    # Groups initialization
    st.session_state.groups = {
        "G1": ["Ahaan"],
        "G2": ["Bella"],
        "G3": ["Ella"],
        "G4": ["Alice"],
        "G5": ["Bob"],
        "G6": ["Charlie"],
        "G7": ["Diana"],
        "G8": ["Evan"]
    }
    
    # Group leaders
    st.session_state.group_leaders = {
        "G1": "Ahaan",
        "G2": "Bella",
        "G3": "Ella",
        "G4": "Alice",
        "G5": "Bob",
        "G6": "Charlie",
        "G7": "Diana",
        "G8": "Evan"
    }
    
    # Group earnings
    st.session_state.group_earnings = pd.DataFrame(columns=[
        "Group", "Date", "Amount", "Description", "Verified"
    ])
    
    # Requests
    st.session_state.reimbursement_requests = pd.DataFrame(columns=[
        "Request ID", "Group", "Requester", "Amount", "Purpose", 
        "Date Submitted", "Status", "Admin Notes"
    ])
    
    st.session_state.event_approval_requests = pd.DataFrame(columns=[
        "Request ID", "Group", "Requester", "Event Name", "Description",
        "Proposed Date", "Budget", "File Upload", "Date Submitted", 
        "Status", "Admin Notes"
    ])
    
    # Other data
    st.session_state.calendar_events = {}
    st.session_state.announcements = []
    st.session_state.config = {"show_signup": True, "app_version": "2.0.0"}
    
    # Default admin users (from secrets or default)
    admin_creds = st.secrets.get("admins", {})
    creator_creds = st.secrets.get("creator", {})
    
    # Set up users with hashed passwords
    st.session_state.users = {}
    
    # Add admins
    for admin in ["Ahaan", "Bella", "Ella"]:
        pwd = admin_creds.get(admin.lower(), f"{admin.lower()}123")  # Default if not in secrets
        st.session_state.users[admin] = {
            "password_hash": bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode(),
            "role": "admin",
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "group": f"G{['Ahaan', 'Bella', 'Ella'].index(admin) + 1}"
        }
    
    # Add regular users
    regular_users = ["Alice", "Bob", "Charlie", "Diana", "Evan"]
    groups = ["G4", "G5", "G6", "G7", "G8"]
    for user, group in zip(regular_users, groups):
        st.session_state.users[user] = {
            "password_hash": bcrypt.hashpw(f"{user.lower()}123".encode(), bcrypt.gensalt()).decode(),
            "role": "user",
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "group": group
        }
    
    # Add creator if defined in secrets
    if creator_creds.get("username"):
        st.session_state.users[creator_creds["username"]] = {
            "password_hash": bcrypt.hashpw(creator_creds["password"].encode(), bcrypt.gensalt()).decode(),
            "role": "creator",
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "group": ""
        }

# ------------------------------
# Data Management - Google Sheets Only
# ------------------------------
def save_all_data(sheet):
    """Save EVERYTHING to Google Sheets"""
    if not sheet:
        return False, "No sheet connection"
    
    try:
        # 1. Save users
        users_ws = sheet.worksheet("users")
        users_data = [["username", "password_hash", "role", "created_at", "last_login", "group"]]
        for username, user in st.session_state.users.items():
            users_data.append([
                username,
                user["password_hash"],
                user["role"],
                user["created_at"],
                user.get("last_login", ""),
                user.get("group", "")
            ])
        users_ws.clear()
        users_ws.update(users_data)
        
        # 2. Save attendance
        att_ws = sheet.worksheet("attendance")
        att_data = [st.session_state.attendance.columns.tolist()] + st.session_state.attendance.values.tolist()
        att_ws.clear()
        att_ws.update(att_data)
        
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
        
        # 7. Save money transactions
        money_ws = sheet.worksheet("money_data")
        money_data = [st.session_state.money_data.columns.tolist()] + st.session_state.money_data.values.tolist()
        money_ws.clear()
        money_ws.update(money_data)
        
        # 8. Save calendar events
        calendar_ws = sheet.worksheet("calendar_events")
        calendar_data = [["date", "event", "group"]]
        for date_str, event_data in st.session_state.calendar_events.items():
            # Event data stored as [event_text, group]
            calendar_data.append([date_str, event_data[0], event_data[1]])
        calendar_ws.clear()
        calendar_ws.update(calendar_data)
        
        # 9. Save announcements
        announcements_ws = sheet.worksheet("announcements")
        announcements_data = [["title", "text", "time", "author", "group"]]
        for ann in st.session_state.announcements:
            announcements_data.append([
                ann["title"], ann["text"], ann["time"], ann["author"], ann.get("group", "")
            ])
        announcements_ws.clear()
        announcements_ws.update(announcements_data)
        
        # 10. Save configuration
        config_ws = sheet.worksheet("config")
        config_data = [["key", "value"]]
        for key, value in st.session_state.config.items():
            config_data.append([key, str(value)])
        config_ws.clear()
        config_ws.update(config_data)
        
        # 11. Save groups
        groups_ws = sheet.worksheet("groups")
        groups_data = [["group", "members"]]
        for group, members in st.session_state.groups.items():
            groups_data.append([group, ", ".join(members)])
        groups_ws.clear()
        groups_data.append(["group_codes", str(st.session_state.group_codes)])  # Store group codes
        groups_ws.update(groups_data)
        
        # 12. Save group leaders
        leaders_ws = sheet.worksheet("group_leader")
        leaders_data = [["group", "leader"]]
        for group, leader in st.session_state.group_leaders.items():
            leaders_data.append([group, leader])
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
        
        return True, "All data saved to Google Sheets"
    
    except Exception as e:
        return False, f"Save failed: {str(e)}"

def load_all_data(sheet):
    """Load EVERYTHING from Google Sheets"""
    if not sheet:
        return False, "No sheet connection"
    
    try:
        # 1. Load users
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
        
        # 2. Load attendance
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
        
        # 7. Load money transactions
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
        
        # 10. Load configuration
        config_ws = sheet.worksheet("config")
        config_data = config_ws.get_all_records()
        st.session_state.config = {}
        for row in config_data:
            if row["key"]:  # Skip empty rows
                # Convert string back to boolean if needed
                value = row["value"]
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                st.session_state.config[row["key"]] = value
        
        # 11. Load groups
        groups_ws = sheet.worksheet("groups")
        groups_data = groups_ws.get_all_records()
        groups = {}
        group_codes = {}
        for row in groups_data:
            if row["group"] and row["group"] != "group_codes":
                groups[row["group"]] = row["members"].split(", ") if row["members"] else []
            elif row["group"] == "group_codes":
                # Parse group codes from string representation
                try:
                    group_codes = eval(row["members"])
                except:
                    st.warning("Using default group codes")
                    group_codes = {"G1": "G1CODE", "G2": "G2CODE", "G3": "G3CODE", "G4": "G4CODE",
                                  "G5": "G5CODE", "G6": "G6CODE", "G7": "G7CODE", "G8": "G8CODE"}
        
        st.session_state.groups = groups if groups else {
            "G1": [], "G2": [], "G3": [], "G4": [], "G5": [], "G6": [], "G7": [], "G8": []
        }
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
        
        # Verify data exists, use defaults if not
        if not st.session_state.users:
            initialize_default_data()
            return True, "Loaded default data (no existing data found)"
        
        return True, "All data loaded from Google Sheets"
    
    except Exception as e:
        return False, f"Load failed: {str(e)}"

# ------------------------------
# User Authentication & Management
# ------------------------------
def hash_password(password):
    """Hash a password for secure storage"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_user(username, password, group_code):
    """Create a new user with group assignment via code"""
    # Verify group code
    group = None
    for g, code in st.session_state.group_codes.items():
        if group_code == code:
            group = g
            break
    
    if not group:
        return False, "Invalid group code"
    
    if username in st.session_state.users:
        return False, "Username already exists"
    
    # Create user
    st.session_state.users[username] = {
        "password_hash": hash_password(password),
        "role": "user",
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "group": group
    }
    
    # Add user to group
    if username not in st.session_state.groups[group]:
        st.session_state.groups[group].append(username)
    
    return True, f"User {username} created successfully in {group}"

def render_login_signup():
    """Render login and signup forms"""
    st.title("Student Council Management System")
    
    # Tabs for login and signup
    login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
    
    with login_tab:
        st.subheader("Account Login")
        
        if st.session_state.login_attempts >= 3:
            st.error("Too many failed attempts. Please wait 1 minute.")
            return False
        
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        col_login, col_clear = st.columns(2)
        with col_login:
            login_btn = st.button("Login", key="login_btn", use_container_width=True)
        
        with col_clear:
            if st.button("Clear", key="clear_login", use_container_width=True):
                st.session_state.login_attempts = 0
                st.rerun()
        
        if login_btn:
            if not username or not password:
                st.error("Please enter both username and password")
                return False
            
            # Check creator credentials
            creator_creds = st.secrets.get("creator", {})
            if username == creator_creds.get("username") and password == creator_creds.get("password"):
                st.session_state.user = username
                st.session_state.role = "creator"
                st.success("Logged in as Creator")
                return True
            
            # Check regular users
            if username in st.session_state.users:
                if verify_password(password, st.session_state.users[username]["password_hash"]):
                    st.session_state.user = username
                    st.session_state.role = st.session_state.users[username]["role"]
                    st.session_state.current_group = st.session_state.users[username].get("group", "")
                    # Update last login
                    st.session_state.users[username]["last_login"] = datetime.now().isoformat()
                    save_all_data(connect_gsheets())
                    st.success(f"Welcome back, {username}!")
                    return True
                else:
                    st.session_state.login_attempts += 1
                    st.error("Incorrect password")
            else:
                st.session_state.login_attempts += 1
                st.error("Username not found")
        
        return False
    
    with signup_tab:
        if not st.session_state.config.get("show_signup", True):
            st.info("Signup is currently closed. Please contact an administrator.")
            return False
            
        st.subheader("Create New Account")
        new_username = st.text_input("Choose Username", key="new_username")
        new_password = st.text_input("Create Password", type="password", key="new_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        group_code = st.text_input("Enter Group Code (G1-G8)", key="group_code")
        
        if st.button("Create Account", key="create_account"):
            if not new_username or not new_password or not confirm_password or not group_code:
                st.error("Please fill in all fields")
                return False
            
            if new_password != confirm_password:
                st.error("Passwords do not match")
                return False
            
            if len(new_password) < 6:
                st.error("Password must be at least 6 characters")
                return False
            
            success, msg = create_user(new_username, new_password, group_code)
            if success:
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(f"{msg}. You can now log in.")
            else:
                st.error(msg)
    
    return False

# ------------------------------
# Group Management Functions
# ------------------------------
def move_user_between_groups(username, from_group, to_group):
    """Move a user from one group to another"""
    if username not in st.session_state.groups[from_group]:
        return False, f"User {username} not in {from_group}"
    
    # Remove from current group
    st.session_state.groups[from_group].remove(username)
    
    # Add to new group
    if username not in st.session_state.groups[to_group]:
        st.session_state.groups[to_group].append(username)
    
    # Update user's group in their profile
    if username in st.session_state.users:
        st.session_state.users[username]["group"] = to_group
    
    return True, f"Moved {username} from {from_group} to {to_group}"

def set_group_leader(group, username):
    """Set a user as group leader"""
    if username not in st.session_state.groups[group]:
        return False, f"User {username} is not in {group}"
    
    st.session_state.group_leaders[group] = username
    return True, f"Set {username} as leader of {group}"

def record_group_earning(group, amount, description):
    """Record earnings for a group"""
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
    return True, "Earnings recorded successfully (pending verification)"

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
    return True, f"Reimbursement request {request_id} submitted"

def submit_event_approval_request(group, requester, event_name, description, 
                                 proposed_date, budget, file_content):
    """Submit a new event approval request with file"""
    request_id = f"EVENT-{random.randint(1000, 9999)}"
    new_request = pd.DataFrame([{
        "Request ID": request_id,
        "Group": group,
        "Requester": requester,
        "Event Name": event_name,
        "Description": description,
        "Proposed Date": proposed_date,
        "Budget": budget,
        "File Upload": file_content,  # Base64 encoded
        "Date Submitted": datetime.now().isoformat(),
        "Status": "Pending",
        "Admin Notes": ""
    }])
    
    st.session_state.event_approval_requests = pd.concat(
        [st.session_state.event_approval_requests, new_request], ignore_index=True
    )
    return True, f"Event approval request {request_id} submitted"

def update_request_status(request_type, request_id, new_status, admin_notes=""):
    """Update status of a request"""
    if request_type == "reimbursement":
        df = st.session_state.reimbursement_requests
    elif request_type == "event":
        df = st.session_state.event_approval_requests
    else:
        return False, "Invalid request type"
    
    index = df.index[df["Request ID"] == request_id].tolist()
    if not index:
        return False, "Request not found"
    
    idx = index[0]
    if request_type == "reimbursement":
        st.session_state.reimbursement_requests.at[idx, "Status"] = new_status
        st.session_state.reimbursement_requests.at[idx, "Admin Notes"] = admin_notes
    else:
        st.session_state.event_approval_requests.at[idx, "Status"] = new_status
        st.session_state.event_approval_requests.at[idx, "Admin Notes"] = admin_notes
    
    return True, f"Request {request_id} updated to {new_status}"

# ------------------------------
# UI Components
# ------------------------------
def render_calendar():
    st.subheader("Event Calendar")
    year, month = st.session_state.current_calendar_month
    
    # Navigation
    col_prev, col_title, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Previous"):
            new_month = month - 1 if month > 1 else 12
            new_year = year - 1 if month == 1 else year
            st.session_state.current_calendar_month = (new_year, new_month)
            st.rerun()
    
    with col_title:
        st.write(f"**{datetime(year, month, 1).strftime('%B %Y')}**")
    
    with col_next:
        if st.button("Next ▶"):
            new_month = month + 1 if month < 12 else 1
            new_year = year + 1 if month == 12 else year
            st.session_state.current_calendar_month = (new_year, new_month)
            st.rerun()
    
    # Calendar grid
    first_day = date(year, month, 1)
    last_day = (date(year, month+1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    days_in_month = (last_day - first_day).days + 1
    
    # Get weekday of first day (0=Monday)
    first_weekday = first_day.weekday()
    
    # Create calendar grid
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
    remaining = 7 - (len(calendar_days) % 7)
    if remaining < 7:
        for i in range(remaining):
            next_date = last_day + timedelta(days=i+1)
            calendar_days.append((next_date, False))
    
    # Display calendar
    headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for col, header in zip(header_cols, headers):
        col.write(f"**{header}**")
    
    for i in range(0, len(calendar_days), 7):
        week = calendar_days[i:i+7]
        cols = st.columns(7)
        for col, (dt, is_current_month) in zip(cols, week):
            date_str = dt.strftime("%Y-%m-%d")
            day_style = "color: #666;" if not is_current_month else "font-weight: bold;"
            if dt == date.today():
                day_style += "background-color: #e3f2fd; border-radius: 50%; padding: 5px;"
            
            # Get event information
            event_info = st.session_state.calendar_events.get(date_str, ["", ""])
            event_text, event_group = event_info
            event_display = f"\n{event_text[:10]}..." if event_text else ""
            if event_group:
                event_display += f" ({event_group})"
            
            col.markdown(f'<div style="{day_style}">{dt.day}{event_display}</div>', unsafe_allow_html=True)

def render_attendance():
    st.subheader("Attendance Records")
    
    # Display current attendance
    st.dataframe(st.session_state.attendance)
    
    # Add new meeting (admin only)
    if is_admin():
        with st.expander("Manage Attendance", expanded=False):
            new_meeting = st.text_input("New Meeting Name")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Add Meeting"):
                    if new_meeting and new_meeting not in st.session_state.meeting_names:
                        st.session_state.meeting_names.append(new_meeting)
                        st.session_state.attendance[new_meeting] = False
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        st.success(f"Added meeting: {new_meeting}")
                        st.rerun()
            
            # Update attendance
            with col2:
                meeting_to_update = st.selectbox("Select Meeting to Update", st.session_state.meeting_names)
            
            if meeting_to_update:
                st.write("Update attendance (check for present):")
                updated = False
                for idx, name in enumerate(st.session_state.attendance["Name"]):
                    current_val = st.session_state.attendance.at[idx, meeting_to_update]
                    new_val = st.checkbox(name, value=current_val, key=f"att_{meeting_to_update}_{name}")
                    if new_val != current_val:
                        st.session_state.attendance.at[idx, meeting_to_update] = new_val
                        updated = True
                
                if updated and st.button("Save Attendance Changes"):
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success("Attendance updated")

def render_credits_rewards():
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Student Credits")
        st.dataframe(st.session_state.credit_data)
        
        if is_admin():
            with st.expander("Manage Credits"):
                student = st.selectbox("Select Student", st.session_state.credit_data["Name"].tolist())
                amount = st.number_input("Credit Amount", min_value=-100, max_value=500)
                if st.button("Update Credits"):
                    idx = st.session_state.credit_data.index[st.session_state.credit_data["Name"] == student].tolist()[0]
                    st.session_state.credit_data.at[idx, "Total_Credits"] += amount
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success(f"Updated {student}'s credits by {amount}")
    
    with col2:
        st.subheader("Rewards Catalog")
        st.dataframe(st.session_state.reward_data)
        
        if is_admin():
            with st.expander("Manage Rewards"):
                reward_name = st.text_input("Reward Name")
                reward_cost = st.number_input("Reward Cost (Credits)", min_value=10, step=10)
                reward_stock = st.number_input("Stock Quantity", min_value=0, step=1)
                
                col_add, col_remove = st.columns(2)
                with col_add:
                    if st.button("Add Reward"):
                        new_reward = pd.DataFrame([{
                            "Reward": reward_name,
                            "Cost": reward_cost,
                            "Stock": reward_stock
                        }])
                        st.session_state.reward_data = pd.concat(
                            [st.session_state.reward_data, new_reward], ignore_index=True
                        )
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        st.success(f"Added reward: {reward_name}")
                
                with col_remove:
                    reward_to_remove = st.selectbox("Remove Reward", st.session_state.reward_data["Reward"].tolist())
                    if st.button("Delete Selected Reward"):
                        st.session_state.reward_data = st.session_state.reward_data[
                            st.session_state.reward_data["Reward"] != reward_to_remove
                        ]
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        st.success(f"Removed reward: {reward_to_remove}")

def render_events():
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Scheduled Events")
        st.dataframe(st.session_state.scheduled_events)
        
        with st.expander("Add Scheduled Event"):
            event_name = st.text_input("Event Name")
            funds_per = st.number_input("Funds Per Event", min_value=0)
            frequency = st.number_input("Frequency Per Month", min_value=1, max_value=4)
            group = st.selectbox("Responsible Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
            
            if st.button("Add Scheduled Event"):
                new_event = pd.DataFrame([{
                    "Event Name": event_name,
                    "Funds Per Event": funds_per,
                    "Frequency Per Month": frequency,
                    "Total Funds": funds_per * frequency,
                    "Responsible Group": group
                }])
                st.session_state.scheduled_events = pd.concat(
                    [st.session_state.scheduled_events, new_event], ignore_index=True
                )
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(f"Added scheduled event: {event_name}")
    
    with col2:
        st.subheader("Occasional Events")
        st.dataframe(st.session_state.occasional_events)
        
        with st.expander("Add Occasional Event"):
            event_name = st.text_input("Event Name (Occasional)")
            funds_raised = st.number_input("Total Funds Raised", min_value=0)
            cost = st.number_input("Total Cost", min_value=0)
            staff = st.radio("Requires Many Staff?", ["Yes", "No"])
            prep_time = st.number_input("Preparation Time (Days)", min_value=1)
            rating = st.slider("Event Rating", 1, 5)
            group = st.selectbox("Responsible Group (Occasional)", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
            
            if st.button("Add Occasional Event"):
                new_event = pd.DataFrame([{
                    "Event Name": event_name,
                    "Total Funds Raised": funds_raised,
                    "Cost": cost,
                    "Staff Many Or Not": staff,
                    "Preparation Time": prep_time,
                    "Rating": rating,
                    "Responsible Group": group
                }])
                st.session_state.occasional_events = pd.concat(
                    [st.session_state.occasional_events, new_event], ignore_index=True
                )
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(f"Added occasional event: {event_name}")

def render_financials():
    st.subheader("Financial Transactions")
    st.dataframe(st.session_state.money_data)
    
    with st.expander("Add Transaction"):
        amount = st.number_input("Amount", min_value=-10000, max_value=10000)
        desc = st.text_input("Description")
        group = st.selectbox("Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "General"])
        
        if st.button("Record Transaction"):
            new_row = pd.DataFrame([{
                "Amount": amount,
                "Description": desc,
                "Date": date.today().strftime("%Y-%m-%d"),
                "Handled By": st.session_state.user,
                "Group": group
            }])
            st.session_state.money_data = pd.concat(
                [st.session_state.money_data, new_row], ignore_index=True
            )
            sheet = connect_gsheets()
            save_all_data(sheet)
            st.success("Transaction recorded")
    
    # Financial summary
    col_income, col_expenses, col_balance = st.columns(3)
    with col_income:
        income = st.session_state.money_data[st.session_state.money_data["Amount"] > 0]["Amount"].sum()
        st.metric("Total Income", f"${income}")
    
    with col_expenses:
        expenses = abs(st.session_state.money_data[st.session_state.money_data["Amount"] < 0]["Amount"].sum())
        st.metric("Total Expenses", f"${expenses}")
    
    with col_balance:
        balance = income - expenses
        st.metric("Current Balance", f"${balance}")

def render_group_tab(group):
    """Render the tab for a specific group"""
    st.subheader(f"Group {group} Management")
    
    # Group members
    st.write("**Group Members:**")
    members = st.session_state.groups.get(group, [])
    leader = st.session_state.group_leaders.get(group, "")
    
    for member in members:
        if member == leader:
            st.write(f"- {member} (Leader)")
        else:
            st.write(f"- {member}")
    
    # Only leaders, admins, and creator can manage group data
    is_leader = (st.session_state.user == leader)
    if is_leader or is_admin():
        # Record earnings
        with st.expander("Record Group Earnings"):
            amount = st.number_input("Amount Earned", min_value=0, key=f"earn_{group}")
            description = st.text_input("Description", key=f"desc_{group}")
            
            if st.button("Save Earnings", key=f"save_earn_{group}"):
                success, msg = record_group_earning(group, amount, description)
                if success:
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success(msg)
                else:
                    st.error(msg)
        
        # Reimbursement request
        with st.expander("Request Reimbursement"):
            amount = st.number_input("Reimbursement Amount", min_value=10, key=f"reimb_{group}")
            purpose = st.text_area("Purpose for Reimbursement", key=f"purpose_{group}")
            
            if st.button("Submit Reimbursement Request", key=f"submit_reimb_{group}"):
                success, msg = submit_reimbursement_request(
                    group, st.session_state.user, amount, purpose
                )
                if success:
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success(msg)
                else:
                    st.error(msg)
        
        # Event approval request
        with st.expander("Request Event Approval"):
            event_name = st.text_input("Event Name", key=f"event_{group}")
            description = st.text_area("Event Description", key=f"event_desc_{group}")
            proposed_date = st.date_input("Proposed Date", key=f"event_date_{group}")
            budget = st.number_input("Estimated Budget", min_value=0, key=f"event_budget_{group}")
            uploaded_file = st.file_uploader("Upload Proposal Document", key=f"event_file_{group}")
            
            if st.button("Submit Event Request", key=f"submit_event_{group}"):
                if not uploaded_file:
                    st.error("Please upload a proposal document")
                else:
                    # Encode file content as base64
                    file_content = base64.b64encode(uploaded_file.getvalue()).decode()
                    success, msg = submit_event_approval_request(
                        group, st.session_state.user, event_name, description,
                        proposed_date.strftime("%Y-%m-%d"), budget, file_content
                    )
                    if success:
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        st.success(msg)
                    else:
                        st.error(msg)
    
    # Group earnings history
    st.subheader(f"{group} Earnings History")
    group_earnings = st.session_state.group_earnings[st.session_state.group_earnings["Group"] == group]
    st.dataframe(group_earnings)
    
    # Group's pending requests
    st.subheader(f"{group} Pending Requests")
    pending_reimb = st.session_state.reimbursement_requests[
        (st.session_state.reimbursement_requests["Group"] == group) & 
        (st.session_state.reimbursement_requests["Status"] == "Pending")
    ]
    st.write("**Reimbursements:**")
    st.dataframe(pending_reimb)
    
    pending_events = st.session_state.event_approval_requests[
        (st.session_state.event_approval_requests["Group"] == group) & 
        (st.session_state.event_approval_requests["Status"] == "Pending")
    ]
    st.write("**Event Approvals:**")
    st.dataframe(pending_events)

def render_admin_dashboard():
    """Render admin dashboard with management functions"""
    st.subheader("Admin Dashboard")
    
    # User management
    with st.expander("User Management", expanded=False):
        st.subheader("Current Users")
        user_data = []
        for username, details in st.session_state.users.items():
            user_data.append({
                "Username": username,
                "Role": details["role"],
                "Group": details.get("group", "N/A"),
                "Created": details["created_at"].split("T")[0],
                "Last Login": details["last_login"].split("T")[0] if details["last_login"] else "Never"
            })
        st.dataframe(pd.DataFrame(user_data))
        
        # Manage user roles
        st.subheader("Manage User Roles")
        user_to_update = st.selectbox("Select User", list(st.session_state.users.keys()))
        new_role = st.selectbox("New Role", ["user", "admin"])
        
        if st.button("Update Role"):
            if user_to_update in st.session_state.users:
                st.session_state.users[user_to_update]["role"] = new_role
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(f"Updated {user_to_update} to {new_role}")
    
    # Group management
    with st.expander("Group Management", expanded=False):
        st.subheader("Move User Between Groups")
        user_to_move = st.selectbox("Select User to Move", list(st.session_state.users.keys()))
        current_group = st.session_state.users[user_to_move].get("group", "")
        
        if current_group:
            st.write(f"Current Group: {current_group}")
            new_group = st.selectbox("Move to Group", [g for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"] if g != current_group])
            
            if st.button("Move User"):
                success, msg = move_user_between_groups(user_to_move, current_group, new_group)
                if success:
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success(msg)
                else:
                    st.error(msg)
        
        # Set group leaders
        st.subheader("Set Group Leaders")
        group_to_update = st.selectbox("Select Group", ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
        members = st.session_state.groups.get(group_to_update, [])
        leader = st.selectbox("Select Leader", members)
        
        if st.button("Set as Leader"):
            success, msg = set_group_leader(group_to_update, leader)
            if success:
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(msg)
            else:
                st.error(msg)
        
        # Group codes management
        st.subheader("Manage Group Codes")
        for group in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]:
            col_group, col_code, col_update = st.columns(3)
            with col_group:
                st.write(f"**{group}**")
            with col_code:
                current_code = st.session_state.group_codes.get(group, "")
                new_code = st.text_input("Code", current_code, key=f"code_{group}")
            with col_update:
                if st.button("Update", key=f"update_{group}") and new_code:
                    st.session_state.group_codes[group] = new_code
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success(f"Updated {group} code")
    
    # Request approvals
    with st.expander("Approve Requests", expanded=False):
        # Reimbursement requests
        st.subheader("Reimbursement Requests")
        pending_reimb = st.session_state.reimbursement_requests[
            st.session_state.reimbursement_requests["Status"] == "Pending"
        ]
        st.dataframe(pending_reimb)
        
        if not pending_reimb.empty:
            req_id = st.selectbox("Select Reimbursement Request", pending_reimb["Request ID"].tolist())
            action = st.radio("Action", ["Approve", "Deny"])
            notes = st.text_input("Admin Notes")
            
            if st.button("Process Reimbursement Request"):
                success, msg = update_request_status(
                    "reimbursement", req_id, action, notes
                )
                if success:
                    # If approved, add to financial records
                    if action == "Approve":
                        req_data = pending_reimb[pending_reimb["Request ID"] == req_id].iloc[0]
                        new_transaction = pd.DataFrame([{
                            "Amount": -float(req_data["Amount"]),  # Negative for expense
                            "Description": f"Reimbursement: {req_data['Purpose']}",
                            "Date": date.today().strftime("%Y-%m-%d"),
                            "Handled By": st.session_state.user,
                            "Group": req_data["Group"]
                        }])
                        st.session_state.money_data = pd.concat(
                            [st.session_state.money_data, new_transaction], ignore_index=True
                        )
                    
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success(msg)
                else:
                    st.error(msg)
        
        # Event approval requests
        st.subheader("Event Approval Requests")
        pending_events = st.session_state.event_approval_requests[
            st.session_state.event_approval_requests["Status"] == "Pending"
        ]
        st.dataframe(pending_events[["Request ID", "Group", "Event Name", "Proposed Date", "Budget"]])
        
        if not pending_events.empty:
            req_id = st.selectbox("Select Event Request", pending_events["Request ID"].tolist())
            action = st.radio("Event Action", ["Approve", "Deny"], key="event_action")
            notes = st.text_input("Event Admin Notes", key="event_notes")
            
            if st.button("Process Event Request"):
                success, msg = update_request_status(
                    "event", req_id, action, notes
                )
                if success:
                    # If approved, add to calendar
                    if action == "Approve":
                        req_data = pending_events[pending_events["Request ID"] == req_id].iloc[0]
                        st.session_state.calendar_events[req_data["Proposed Date"]] = [
                            req_data["Event Name"], req_data["Group"]
                        ]
                    
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success(msg)
                else:
                    st.error(msg)
    
    # System configuration
    with st.expander("System Configuration", expanded=False):
        signup_status = st.checkbox("Allow New Signups", value=st.session_state.config.get("show_signup", True))
        if st.button("Update Settings"):
            st.session_state.config["show_signup"] = signup_status
            sheet = connect_gsheets()
            save_all_data(sheet)
            st.success("System settings updated")

# ------------------------------
# Permission Checks
# ------------------------------
def is_admin():
    """Check if user has admin or creator role"""
    return st.session_state.get("role") in ["admin", "creator"]

def is_group_leader(group):
    """Check if user is leader of specified group"""
    return st.session_state.get("user") == st.session_state.group_leaders.get(group, "")

# ------------------------------
# Main Application
# ------------------------------
def main():
    # Initialize session state
    initialize_session_state()
    
    # Connect to Google Sheets
    sheet = connect_gsheets()
    
    # Load all data from Google Sheets
    if sheet:
        success, msg = load_all_data(sheet)
        if not success:
            st.warning(f"Using default data: {msg}")
            initialize_default_data()
    
    # Handle authentication
    if not st.session_state.user:
        if render_login_signup():
            st.rerun()
        return
    
    # Main app interface after login
    st.title("Student Council Management System")
    st.sidebar.write(f"Logged in as: **{st.session_state.user}**")
    st.sidebar.write(f"Role: **{st.session_state.role}**")
    st.sidebar.write(f"Group: **{st.session_state.current_group or 'N/A'}**")
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.role = None
        st.session_state.current_group = None
        st.rerun()
    
    # Show announcements
    if st.session_state.announcements:
        with st.expander("Announcements", expanded=True):
            for ann in sorted(st.session_state.announcements, key=lambda x: x["time"], reverse=True)[:3]:
                # Show group-specific or all announcements
                if not ann["group"] or ann["group"] == st.session_state.current_group or is_admin():
                    st.info(f"**{ann['title']}** ({ann['time'].split('T')[0]})\n\n{ann['text']}")
    
    # Create main tabs + group tabs
    main_tabs = ["Calendar", "Attendance", "Credits & Rewards", "Events", "Financials"]
    if is_admin():
        main_tabs.append("Admin Dashboard")
    
    # Add group tabs (G1-G8)
    group_tabs = [f"Group {g}" for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]]
    all_tabs = main_tabs + group_tabs
    
    # Create tabs
    tabs = st.tabs(all_tabs)
    
    # Map tabs to functions
    tab_functions = {
        "Calendar": render_calendar,
        "Attendance": render_attendance,
        "Credits & Rewards": render_credits_rewards,
        "Events": render_events,
        "Financials": render_financials
    }
    
    # Add admin dashboard if present
    if "Admin Dashboard" in all_tabs:
        tab_functions["Admin Dashboard"] = render_admin_dashboard
    
    # Add group tabs
    for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]:
        tab_functions[f"Group {g}"] = lambda g=g: render_group_tab(g)
    
    # Render active tab
    for i, tab_name in enumerate(all_tabs):
        with tabs[i]:
            if tab_name in tab_functions:
                tab_functions[tab_name]()

if __name__ == "__main__":
    main()
