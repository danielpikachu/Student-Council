import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
from datetime import datetime, date, timedelta
import time
import os
import json
import bcrypt
from pathlib import Path
import random
import shutil

# ------------------------------
# App Configuration
# ------------------------------
st.set_page_config(
    page_title="SCIS HQ US Stuco",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# Connect to Google Sheets
# ------------------------------
def connect_gsheets():
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
        
        # Authenticate using gspread's service_account_from_dict
        client = gspread.service_account_from_dict(creds)
        
        # Open the sheet with explicit permission check
        sheet = client.open_by_url(secrets["sheet_url"])
        
        # Test read access (to verify permissions)
        try:
            sheet.sheet1.get_all_records()  # Try reading the first tab
            st.success("✅ Full access to Google Sheet confirmed!")
            return sheet
        except Exception as e:
            st.error(f"❌ Can connect but no read access: {str(e)}")
            return None
            
    except Exception as e:
        st.error(f"❌ Connection failed: {str(e)}")
        return None
# ------------------------------
# Secured File Management (With Backup)
# ------------------------------
def ensure_directory(path):
    """Ensure directory exists (with error handling to prevent crashes)"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        st.error(f"Failed to create directory {path}: {str(e)}")
        return False

# Define data directories (absolute paths for consistency)
DATA_DIR = os.path.abspath("stuco_data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
ensure_directory(DATA_DIR)
ensure_directory(BACKUP_DIR)

# Data file paths
DATA_FILE = os.path.join(DATA_DIR, "app_data.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "app_config.json")

# Constants
ROLES = ["user", "admin", "credit_manager"]
CREATOR_ROLE = "creator"
WELCOME_MESSAGE = "Welcome to SCIS HQ US Stuco"

# ------------------------------
# Automatic Backup System (Prevents Data Loss)
# ------------------------------
def backup_data():
    """Create backups of all data files (keeps last 5 backups)"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_files = [DATA_FILE, USERS_FILE, CONFIG_FILE]
        
        # Create backup for each existing file
        for file in backup_files:
            if os.path.exists(file):
                backup_path = os.path.join(BACKUP_DIR, f"{os.path.basename(file)}_{timestamp}")
                shutil.copy2(file, backup_path)
        
        # Clean up old backups (keep only most recent 5)
        for file_type in ["app_data.json", "users.json", "app_config.json"]:
            backups = sorted(
                [f for f in os.listdir(BACKUP_DIR) if f.startswith(file_type)],
                reverse=True  # Newest first
            )
            for old_backup in backups[5:]:  # Delete backups beyond the 5th newest
                os.remove(os.path.join(BACKUP_DIR, old_backup))
                
    except Exception as e:
        st.warning(f"Backup warning (data still safe): {str(e)}")

# ------------------------------
# Initialization & Setup
# ------------------------------
def initialize_files():
    """Ensure all required data files exist (with safe defaults)"""
    for file in [DATA_FILE, USERS_FILE, CONFIG_FILE]:
        if not Path(file).exists():
            initial_data = {}
            if file == CONFIG_FILE:
                initial_data = {"show_signup": False, "app_version": "1.0.0"}
            # Write to temp file first to avoid corruption
            temp_file = f"{file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(initial_data, f, indent=2)
            os.replace(temp_file, file)

def initialize_session_state():
    """Initialize session state variables and load permanent data from Google Sheets"""
    # 1. Initialize core session state variables (your original setup)
    required_states = {
        "user": None,
        "role": None,
        "login_attempts": 0,
        "spinning": False,
        "winner": None,
        "allocation_count": 0,
        "current_calendar_month": (date.today().year, date.today().month)  # For calendar navigation
    }
    for key, default in required_states.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # 2. Load permanent data from Google Sheets (users, attendance, credits, etc.)
    # Only load if data hasn't been loaded yet
    if "users" not in st.session_state:
        # Show a brief loading message while fetching data
        with st.spinner("Loading app data..."):
            load_success, load_msg = load_data()  # Uses your new Google Sheets load function
            
            if load_success:
                st.success(load_msg)  # Optional: Show success to admins
            else:
                # If load fails, use safe defaults to keep the app running
                st.warning(f"Using backup data: {load_msg}")
                
                # Set default users (admin account) if no data loaded
                st.session_state.users = [{
                    "username": "admin",
                    "password": bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
                    "role": "admin"
                }]
                
                # Set default empty data for other tables
                st.session_state.attendance = pd.DataFrame({"Name": []})
                st.session_state.credit_data = pd.DataFrame({"Name": [], "Total_Credits": [], "RedeemedCredits": []})
                st.session_state.reward_data = pd.DataFrame({"Reward": [], "Cost": [], "Stock": []})
                st.session_state.meeting_names = []

# ------------------------------
# Config Management
# ------------------------------
def load_config():
    """Load config with backup recovery (fixes lost signup settings)"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        
        # Recover from backup if main config is missing
        backups = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith("app_config.json")],
            reverse=True
        )
        if backups:
            st.warning("Config file missing - restoring from backup")
            latest_backup = os.path.join(BACKUP_DIR, backups[0])
            shutil.copy2(latest_backup, CONFIG_FILE)
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
                
        # Fallback to default if no backups
        default_config = {"show_signup": False, "app_version": "1.0.0"}
        save_config(default_config)
        return default_config
    except Exception as e:
        st.error(f"Error loading config: {str(e)}")
        return {"show_signup": False}

def save_config(config):
    """Save config safely (prevents corruption)"""
    try:
        backup_data()  # Backup before saving changes
        temp_file = f"{CONFIG_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(config, f, indent=2)
        os.replace(temp_file, CONFIG_FILE)
    except Exception as e:
        st.error(f"Error saving config: {str(e)}")

# ------------------------------
# User Authentication (Preserves User Accounts)
# ------------------------------
def hash_password(password):
    """Hash a password for secure storage"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def load_users():
    """Load users with backup recovery (fixes lost user accounts)"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
            # Filter invalid entries (prevents crashes)
            return {k: v for k, v in users.items() if "password_hash" in v and "role" in v}
        
        # Recover from backup if users file is missing
        backups = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith("users.json")],
            reverse=True
        )
        if backups:
            st.warning("User data missing - restoring from backup")
            latest_backup = os.path.join(BACKUP_DIR, backups[0])
            shutil.copy2(latest_backup, USERS_FILE)
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
            return {k: v for k, v in users.items() if "password_hash" in v and "role" in v}
                
        # Fallback to empty dict if no backups
        return {}
    except Exception as e:
        st.error(f"Error loading users: {str(e)}")
        # Last resort: try backup again
        try:
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("users.json")], reverse=True)
            if backups:
                latest_backup = os.path.join(BACKUP_DIR, backups[0])
                shutil.copy2(latest_backup, USERS_FILE)
                with open(USERS_FILE, "r") as f:
                    users = json.load(f)
                return {k: v for k, v in users.items() if "password_hash" in v and "role" in v}
        except:
            st.error("Failed to recover users - starting fresh (check backups folder)")
        return {}

def save_user(username, password, role="user"):
    """Save a new user safely (with backups)"""
    try:
        backup_data()  # Backup before adding user
        users = load_users()
        if username in users:
            return False, "Username already exists"
        
        users[username] = {
            "password_hash": hash_password(password),
            "role": role,
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        # Safe write (temp file first)
        temp_file = f"{USERS_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(users, f, indent=2)
        os.replace(temp_file, USERS_FILE)
        return True, "User created successfully"
    except Exception as e:
        return False, f"Error saving user: {str(e)}"

def update_user_login(username):
    """Update last login timestamp (safe write)"""
    try:
        users = load_users()
        if username in users:
            users[username]["last_login"] = datetime.now().isoformat()
            temp_file = f"{USERS_FILE}.tmp"
            with open(temp_file, "w") as f:
                json.dump(users, f, indent=2)
            os.replace(temp_file, USERS_FILE)
    except Exception as e:
        st.warning(f"Could not update login time: {str(e)}")

def update_user_role(username, new_role):
    """Update a user's role (with validation)"""
    valid_roles = ROLES + [CREATOR_ROLE]
    if new_role not in valid_roles:
        return False, f"Invalid role. Choose: {', '.join(valid_roles)}"
        
    try:
        backup_data()  # Backup before changing role
        users = load_users()
        if username not in users:
            return False, "User not found"
        
        users[username]["role"] = new_role
        temp_file = f"{USERS_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(users, f, indent=2)
        os.replace(temp_file, USERS_FILE)
        return True, f"Role updated to {new_role}"
    except Exception as e:
        return False, f"Error updating role: {str(e)}"

def delete_user(username):
    """Delete a user safely (with backups)"""
    try:
        backup_data()  # Backup before deleting
        users = load_users()
        if username not in users:
            return False, "User not found"
        
        del users[username]
        temp_file = f"{USERS_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(users, f, indent=2)
        os.replace(temp_file, USERS_FILE)
        return True, "User deleted successfully"
    except Exception as e:
        return False, f"Error deleting user: {str(e)}"

# ------------------------------
# Data Management (Preserves All App Data)
# ------------------------------
def load_student_council_members():
    """Load student council members with detailed logging to identify missing entries"""
    try:
        file_path = "student_council_members.xlsx"
        import_log = []  # To track exactly what's happening
        import_log.append(f"Looking for Excel file at: {os.path.abspath(file_path)}")

        if not os.path.exists(file_path):
            st.warning("\n".join(import_log))
            st.error("File not found")
            return ["Alice", "Bob", "Charlie", "Diana", "Evan"]

        # Try to read the file with all sheets
        try:
            # Get all sheet names to check if data is on another sheet
            excel_file = pd.ExcelFile(file_path, engine="openpyxl")
            import_log.append(f"Found Excel file with sheets: {excel_file.sheet_names}")
            
            # Try first sheet (default)
            members_df = pd.read_excel(excel_file, sheet_name=0)
            import_log.append(f"Reading data from sheet: {excel_file.sheet_names[0]}")
            import_log.append(f"Total rows in sheet: {len(members_df)}")
        except Exception as e:
            import_log.append(f"Error reading Excel: {str(e)}")
            st.warning("\n".join(import_log))
            return ["Alice", "Bob", "Charlie", "Diana", "Evan"]

        # Find name column (case-insensitive)
        name_columns = [col for col in members_df.columns if str(col).strip().lower() == "name"]
        import_log.append(f"Found potential name columns: {name_columns}")
        
        if not name_columns:
            import_log.append(f"Available columns: {list(members_df.columns)}")
            st.warning("\n".join(import_log))
            st.error("No column containing 'name' found")
            return ["Alice", "Bob", "Charlie", "Diana", "Evan"]
        
        name_column = name_columns[0]
        import_log.append(f"Using name column: {name_column}")

        # Detailed row-by-row processing
        all_names = []
        for row_idx, value in enumerate(members_df[name_column], start=2):  # Rows start at 2 in Excel
            row_num = row_idx  # Excel rows are 1-indexed
            try:
                if pd.isna(value):
                    import_log.append(f"Row {row_num}: Skipped - empty value")
                    continue
                
                name = str(value).strip()
                if not name:
                    import_log.append(f"Row {row_num}: Skipped - blank after cleaning")
                    continue
                
                # Check for special characters that might cause issues
                if any(c in name for c in ['\n', '\r', '\t']):
                    name = name.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                    import_log.append(f"Row {row_num}: Cleaned special characters - '{name}'")
                
                all_names.append(name)
                import_log.append(f"Row {row_num}: Imported - '{name}'")
            except Exception as e:
                import_log.append(f"Row {row_num}: Error processing - {str(e)}")

        # Show results with details
        st.success(f"Successfully imported {len(all_names)} members")
        
        # Show the log in an expandable section
        with st.expander("View Import Details (click to expand)", expanded=False):
            st.text("\n".join(import_log))
        
        # Check for hidden sheets that might contain the other members
        if len(all_names) < 47 and len(excel_file.sheet_names) > 1:
            st.info(f"Note: The Excel file has {len(excel_file.sheet_names)} sheets. "
                   f"We only read the first one ('{excel_file.sheet_names[0]}'). "
                   "If your members are on other sheets, they won't be imported.")

        return list(pd.unique(all_names))  # Remove duplicates

    except Exception as e:
        st.error(f"Import error: {str(e)}")
        return ["Alice", "Bob", "Charlie", "Diana", "Evan"]

def safe_init_data():
    """Safely initialize all data structures (fallback)"""
    council_members = load_student_council_members()
    
    st.session_state.scheduled_events = pd.DataFrame(columns=[
        'Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds'
    ])

    st.session_state.occasional_events = pd.DataFrame(columns=[
        'Event Name', 'Total Funds Raised', 'Cost', 'Staff Many Or Not', 
        'Preparation Time', 'Rating'
    ])

    st.session_state.credit_data = pd.DataFrame({
        'Name': council_members,
        'Total_Credits': [200 for _ in council_members],
        'RedeemedCredits': [50 if i % 2 == 0 else 0 for i in range(len(council_members))]
    })

    st.session_state.reward_data = pd.DataFrame({
        'Reward': ['Bubble Tea', 'Chips', 'Café Coupon', 'Movie Ticket'],
        'Cost': [50, 30, 80, 120],
        'Stock': [10, 20, 5, 3]
    })

    st.session_state.wheel_prizes = [
        "50 Credits", "Bubble Tea", "Chips", "100 Credits", 
        "Café Coupon", "Free Prom Ticket", "200 Credits"
    ]
    st.session_state.wheel_colors = plt.cm.tab10(np.linspace(0, 1, len(st.session_state.wheel_prizes)))

    st.session_state.money_data = pd.DataFrame(columns=['Amount', 'Description', 'Date', 'Handled By'])
    st.session_state.calendar_events = {}
    st.session_state.announcements = []

    st.session_state.meeting_names = ["First Semester Meeting", "Event Planning Session"]
    attendance_data = {'Name': council_members}
    for meeting in st.session_state.meeting_names:
        attendance_data[meeting] = [i % 3 != 0 for i in range(len(council_members))]
        
    st.session_state.attendance = pd.DataFrame(attendance_data)

def save_data(sheet):
    if not sheet:
        return False, "No sheet connection"
    
    try:
        # Save users to "users" tab
        users_tab = sheet.worksheet("users")
        users_tab.update([st.session_state.users])
        
        # Save attendance to "attendance" tab
        att_tab = sheet.worksheet("attendance")
        att_tab.update([st.session_state.attendance.columns.tolist()] + st.session_state.attendance.values.tolist())
        
        return True, "Data saved"
    except Exception as e:
        return False, f"Save error: {str(e)}"

def load_data(sheet):
    if not sheet:
        return False, "No sheet connection"
    
    try:
        # Load users
        users = sheet.worksheet("users").get_all_records()
        st.session_state.users = users if users else [{"username": "admin", "password": "hashed_pw", "role": "admin"}]
        
        # Load attendance
        att_data = sheet.worksheet("attendance").get_all_records()
        st.session_state.attendance = pd.DataFrame(att_data)
        
        return True, "Data loaded"
    except Exception as e:
        return False, f"Load error: {str(e)}"

# ------------------------------
# Authentication UI
# ------------------------------
def render_login_form():
    """Render login form in sidebar"""
    with st.sidebar:
        st.subheader("Account Login")
        
        # Show error if too many attempts
        if st.session_state.login_attempts >= 3:
            st.error("Too many failed attempts. Please wait 1 minute.")
            return False
        
        username = st.text_input("Username", key="login_username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
        
        col_login, col_clear = st.columns(2)
        with col_login:
            login_btn = st.button("Login", key="login_btn", use_container_width=True)
        
        with col_clear:
            clear_btn = st.button("Clear", key="clear_login", use_container_width=True, type="secondary")
        
        if clear_btn:
            st.session_state.login_attempts = 0
            st.rerun()
        
        if login_btn:
            if not username or not password:
                st.error("Please enter both username and password")
                return False
            
            # Check creator credentials first
            creator_creds = st.secrets.get("creator", {})
            creator_un = creator_creds.get("username", "")
            creator_pw = creator_creds.get("password", "")
            
            if username == creator_un and password == creator_pw and creator_un:
                st.session_state.user = username
                st.session_state.role = CREATOR_ROLE
                update_user_login(username)
                st.success("Logged in as Creator!")
                return True
            
            # Check regular users
            users = load_users()
            if username in users:
                if verify_password(password, users[username]["password_hash"]):
                    st.session_state.user = username
                    st.session_state.role = users[username]["role"]
                    update_user_login(username)
                    st.success(f"Welcome back, {username}!")
                    return True
                else:
                    st.session_state.login_attempts += 1
                    st.error("Incorrect password")
                    return False
            else:
                st.session_state.login_attempts += 1
                st.error("Username not found")
                return False
        
        return False

def render_signup_form():
    """Render signup form in sidebar if enabled"""
    config = load_config()
    if not config.get("show_signup", False):
        return
    
    with st.sidebar.expander("Create New Account", expanded=False):
        st.subheader("Sign Up")
        new_username = st.text_input("Choose Username", key="signup_username")
        new_password = st.text_input("Choose Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm")
        
        if st.button("Create Account", key="signup_btn"):
            if not new_username or not new_password:
                st.error("Please fill in all fields")
                return
            
            if len(new_password) < 6:
                st.error("Password must be at least 6 characters")
                return
            
            if new_password != confirm_password:
                st.error("Passwords do not match")
                return
            
            success, msg = save_user(new_username, new_password)
            if success:
                st.success(f"{msg} You can now log in.")
            else:
                st.error(msg)

# ------------------------------
# Permission Checks
# ------------------------------
def is_admin():
    return st.session_state.get("role") in ["admin", CREATOR_ROLE]

def is_creator():
    return st.session_state.get("role") == CREATOR_ROLE

def is_credit_manager():
    return st.session_state.get("role") == "credit_manager"

def is_user():
    return st.session_state.get("role") == "user"

# ------------------------------
# UI Helper Functions
# ------------------------------
def list_backups():
    """List all available backups in stuco_data/backups"""
    backup_folder = "stuco_data/backups"
    if not os.path.exists(backup_folder):
        return []
    
    # Get all backup files (sorted by newest first)
    backup_files = [f for f in os.listdir(backup_folder) if f.startswith(("app_data.json_", "users.json_"))]
    backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_folder, x)), reverse=True)
    return backup_files

def restore_latest_backup():
    """Restore the newest backup (app_data.json and users.json)"""
    backup_folder = "stuco_data/backups"
    backups = list_backups()
    
    if not backups:
        return False, "No backups found."
    
    # Restore app_data.json (attendance/credits)
    app_backups = [f for f in backups if f.startswith("app_data.json_")]
    if app_backups:
        latest_app_backup = os.path.join(backup_folder, app_backups[0])
        shutil.copy2(latest_app_backup, "stuco_data/app_data.json")
    
    # Restore users.json (usernames/passwords)
    user_backups = [f for f in backups if f.startswith("users.json_")]
    if user_backups:
        latest_user_backup = os.path.join(backup_folder, user_backups[0])
        shutil.copy2(latest_user_backup, "stuco_data/users.json")
    
    return True, f"Restored latest backups: {app_backups[0] if app_backups else 'No app backup'}, {user_backups[0] if user_backups else 'No user backup'}"

def render_role_badge():
    """Render a visual badge for the user's role"""
    role = st.session_state.get("role", "unknown")
    role_styles = {
        "user": "background-color: #e0e0e0; color: #333;",
        "admin": "background-color: #e8f5e9; color: #2e7d32;",
        "credit_manager": "background-color: #e3f2fd; color: #1976d2;",
        "creator": "background-color: #fff3e0; color: #e65100;",
        "unknown": "background-color: #f5f5f5; color: #757575;"
    }
    
    display_role = role if role in role_styles else "unknown"
    return f'<span class="role-badge" style="{role_styles[display_role]}">{display_role.capitalize()}</span>'

def render_calendar():
    """Render monthly calendar view with navigation buttons"""
    # Initialize session state for current calendar month if not exists
    if "current_calendar_month" not in st.session_state:
        today = date.today()
        st.session_state.current_calendar_month = (today.year, today.month)
    
    # Get current year and month from session state
    current_year, current_month = st.session_state.current_calendar_month
    
    # Create navigation buttons
    col_prev, col_title, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Previous", key="prev_month"):
            # Calculate previous month
            new_month = current_month - 1
            new_year = current_year
            if new_month < 1:
                new_month = 12
                new_year -= 1
            st.session_state.current_calendar_month = (new_year, new_month)
            st.rerun()  # Refresh to show new month
    
    with col_title:
        # Display current month and year
        st.subheader(f"{datetime(current_year, current_month, 1).strftime('%B %Y')}")
    
    with col_next:
        if st.button("Next ▶", key="next_month"):
            # Calculate next month
            new_month = current_month + 1
            new_year = current_year
            if new_month > 12:
                new_month = 1
                new_year += 1
            st.session_state.current_calendar_month = (new_year, new_month)
            st.rerun()  # Refresh to show new month
    
    # Generate calendar grid for current month
    grid, month, year = get_month_grid(current_year, current_month)
    
    # Display weekday headers
    headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for col, header in zip(header_cols, headers):
        col.markdown(f'<div class="day-header">{header}</div>', unsafe_allow_html=True)
    
    # Display calendar days
    for week in grid:
        day_cols = st.columns(7)
        for col, dt in zip(day_cols, week):
            date_str = dt.strftime("%Y-%m-%d")
            day_display = dt.strftime("%d")
            
            css_class = "calendar-day "
            if dt.month != month:
                css_class += "other-month "
            elif dt == date.today():
                css_class += "today "
            
            plan_text = st.session_state.calendar_events.get(date_str, "")
            plan_html = f'<div class="plan-text">{plan_text}</div>' if plan_text else ""
            
            col.markdown(
                f'<div class="{css_class}"><strong>{day_display}</strong>{plan_html}</div>',
                unsafe_allow_html=True
            )

def get_month_grid(year, month):
    """Generate grid of dates for specified month calendar"""
    first_day = date(year, month, 1)
    last_day = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    first_day_weekday = first_day.isoweekday() % 7  # Convert to 0=Monday
    
    total_days = (last_day - first_day).days + 1
    total_slots = first_day_weekday + total_days
    rows = (total_slots + 6) // 7
    
    grid = []
    current_date = first_day - timedelta(days=first_day_weekday)
    
    for _ in range(rows):
        week = []
        for _ in range(7):
            week.append(current_date)
            current_date += timedelta(days=1)
        grid.append(week)
    
    return grid, month, year
    
def calculate_attendance_rates():
        """Safely calculate attendance rates with error handling for missing meetings"""
        try:
            # Get valid meeting names that actually exist in the attendance DataFrame
            valid_meetings = [
                meeting for meeting in st.session_state.meeting_names 
                if meeting in st.session_state.attendance.columns
            ]
            
            # If no valid meetings, return empty dict to avoid errors
            if not valid_meetings:
                return {}
            
            # Calculate rates using only valid meetings
            attendance_rates = {}
            for _, row in st.session_state.attendance.iterrows():
                name = row['Name']
                attended = sum(row[meeting] for meeting in valid_meetings if pd.notna(row[meeting]))
                total = len(valid_meetings)
                attendance_rates[name] = (attended / total) * 100 if total > 0 else 0
            
            return attendance_rates
        except Exception as e:
            # If any error occurs, return empty dict to prevent app crash
            st.warning(f"Attendance calculation temporarily disabled: {str(e)}")
            return {}

def reset_attendance_data():
        """Reset attendance data to fix corruption"""
        backup_data()  # Save backup before resetting
        council_members = load_student_council_members()
        st.session_state.meeting_names = ["First Semester Meeting", "Event Planning Session"]
        
        # Rebuild attendance DataFrame with valid structure
        attendance_data = {'Name': council_members}
        for meeting in st.session_state.meeting_names:
            attendance_data[meeting] = [False for _ in range(len(council_members))]
        
        st.session_state.attendance = pd.DataFrame(attendance_data)
        save_data()
        st.success("Attendance data reset successfully")

def draw_wheel(rotation_angle=0):
    """Draw the lucky draw wheel"""
    n = len(st.session_state.wheel_prizes)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_aspect('equal')
    ax.axis('off')

    for i in range(n):
        start_angle = np.rad2deg(2 * np.pi * i / n + rotation_angle)
        end_angle = np.rad2deg(2 * np.pi * (i + 1) / n + rotation_angle)
        wedge = Wedge(
            center=(0, 0), 
            r=1, 
            theta1=start_angle, 
            theta2=end_angle, 
            width=1, 
            facecolor=st.session_state.wheel_colors[i], 
            edgecolor='black',
            linewidth=1
        )
        ax.add_patch(wedge)

        mid_angle = np.deg2rad((start_angle + end_angle) / 2)
        text_x = 0.7 * np.cos(mid_angle)
        text_y = 0.7 * np.sin(mid_angle)
        ax.text(
            text_x, text_y, 
            st.session_state.wheel_prizes[i],
            ha='center', va='center', 
            rotation=np.rad2deg(mid_angle) - 90,
            fontsize=8
        )

    # Wheel center and pointer
    circle = plt.Circle((0, 0), 0.1, color='white', edgecolor='black', linewidth=1)
    ax.add_patch(circle)
    ax.plot([0, 0], [0, 0.9], color='black', linewidth=2)
    ax.plot([-0.05, 0.05], [0.85, 0.9], color='black', linewidth=2)
    
    return fig

# ------------------------------
# Meeting & Attendance Management
# ------------------------------
def add_new_meeting():
    """Add a new meeting to attendance records"""
    new_meeting_num = len(st.session_state.meeting_names) + 1
    new_meeting_name = f"Meeting {new_meeting_num}"
    st.session_state.meeting_names.append(new_meeting_name)
    st.session_state.attendance[new_meeting_name] = False
    success, msg = save_data()
    if success:
        st.success(f"Added new meeting: {new_meeting_name}")
    else:
        st.error(msg)

def delete_meeting(meeting_name):
    """Delete a meeting from attendance records"""
    if meeting_name in st.session_state.meeting_names:
        st.session_state.meeting_names.remove(meeting_name)
        st.session_state.attendance = st.session_state.attendance.drop(columns=[meeting_name])
        success, msg = save_data()
        if success:
            st.success(f"Deleted meeting: {meeting_name}")
        else:
            st.error(msg)
    else:
        st.error(f"Meeting {meeting_name} not found")

def add_new_person(name):
    """Add a new person to attendance records"""
    if not name:
        st.error("Please enter a name")
        return
        
    if name in st.session_state.attendance['Name'].values:
        st.warning(f"{name} is already in the attendance list")
        return
    
    new_row = {'Name': name}
    for meeting in st.session_state.meeting_names:
        new_row[meeting] = False
    
    st.session_state.attendance = pd.concat(
        [st.session_state.attendance, pd.DataFrame([new_row])],
        ignore_index=True
    )
    success, msg = save_data()
    if success:
        st.success(f"Added {name} to attendance list")
    else:
        st.error(msg)

def delete_person(name):
    """Remove a person from attendance records"""
    if name in st.session_state.attendance['Name'].values:
        st.session_state.attendance = st.session_state.attendance[
            st.session_state.attendance['Name'] != name
        ].reset_index(drop=True)
        success, msg = save_data()
        if success:
            st.success(f"Deleted {name} from attendance list")
        else:
            st.error(msg)
    else:
        st.error(f"Person {name} not found")
        
def mark_all_present(meeting_name):
    """Mark all students as present for a specific meeting with backup"""
    if not meeting_name or meeting_name not in st.session_state.attendance.columns:
        return False, "Invalid meeting name"
        
    # Create backup before making changes
    backup_data()
        
    # Set all students to present for this meeting
    st.session_state.attendance[meeting_name] = True
        
    # Save changes
    success, msg = save_data()
    if success:
        return True, f"All students marked as present for {meeting_name}"
    else:
        return False, f"Failed to save changes: {msg}"

# ------------------------------
# Excel Import Function for Credit and Reward System (Only for Credit)
# ------------------------------
def import_credit_members_from_excel():
    """Import members from attendance Excel file to Credit system (0 default credits) with backup"""
    try:
        # Step 1: Create backup BEFORE making changes (matches existing backup system)
        backup_data()
        st.info("Created backup before importing credit members.")

        # Step 2: Load Excel file (same as attendance uses)
        file_path = "student_council_members.xlsx"
        if not os.path.exists(file_path):
            return False, f"Excel file not found at: {os.path.abspath(file_path)}"

        # Step 3: Read Excel and find Name column (case-insensitive)
        excel_file = pd.ExcelFile(file_path, engine="openpyxl")
        members_df = pd.read_excel(excel_file, sheet_name=0)  # Same sheet as attendance
        
        name_columns = [col for col in members_df.columns if str(col).strip().lower() == "name"]
        if not name_columns:
            return False, f"No 'Name' column found. Available columns: {list(members_df.columns)}"
        
        name_column = name_columns[0]

        # Step 4: Clean names (remove blanks/duplicates)
        imported_names = []
        for value in members_df[name_column]:
            if pd.notna(value):
                name = str(value).strip()
                if name and name not in imported_names:
                    imported_names.append(name)

        if len(imported_names) == 0:
            return False, "No valid names found in Excel file."

        # Step 5: Create new credit data (0 total/redeemed credits for everyone)
        new_credit_data = pd.DataFrame({
            "Name": imported_names,
            "Total_Credits": [0 for _ in imported_names],  # Default to 0
            "RedeemedCredits": [0 for _ in imported_names]  # Default to 0
        })

        # Step 6: Save to session state and persist (safe write with backup)
        st.session_state.credit_data = new_credit_data
        success, save_msg = save_data()
        if not success:
            return False, f"Failed to save imported members: {save_msg}"

        return True, f"Successfully imported {len(imported_names)} members to Credit system. All have 0 total/redeemed credits."

    except Exception as e:
        return False, f"Import error: {str(e)}"

# ------------------------------
# Main App UI
# ------------------------------
def render_welcome_screen():
    """Render screen for non-authenticated users"""
    st.markdown(f"<h1 style='text-align: center; margin-top: 50px;'>{WELCOME_MESSAGE}</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div style='text-align: center; margin: 30px; padding: 20px; border-radius: 10px; background-color: #f0f2f6;'>
        <p style='font-size: 1.2rem;'>Please log in using the form in the sidebar to access the Student Council management tools.</p>
        <p style='margin-top: 15px;'>If you don't have an account, please contact an administrator to create one for you.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Add some visual elements
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("📅 Event Planning")
    with col2:
        st.info("💰 Financial Management")
    with col3:
        st.info("🏆 Student Recognition")

def render_main_app():
    """Render the full application after login"""
    st.title("Student Council Management System")
    
    # ------------------------------
    # Sidebar with User Info
    # ------------------------------
    with st.sidebar:
        st.subheader(f"Logged in as: {st.session_state.user}")
        st.markdown(render_role_badge(), unsafe_allow_html=True)

        if is_creator():
            st.divider()
            st.subheader("📂 View stuco_data Files")
            
            # Path to stuco_data (matches your code)
            stuco_path = "stuco_data"
            
            # Check if stuco_data exists
            if os.path.exists(stuco_path):
                # List files in stuco_data (main files: users.json, app_data.json)
                main_files = os.listdir(stuco_path)
                st.info("Main stuco_data files:")
                for file in main_files:
                    file_path = os.path.join(stuco_path, file)
                    # Show file name + size
                    file_size = os.path.getsize(file_path) / 1024  # Convert to KB
                    st.text(f"- {file} ({round(file_size, 2)} KB)")
                
                # List backup files (in stuco_data/backups)
                backup_path = os.path.join(stuco_path, "backups")
                if os.path.exists(backup_path):
                    backup_files = os.listdir(backup_path)
                    st.info(f"\nBackup files ({len(backup_files)} total):")
                    # Show newest backups first
                    backup_files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_path, x)), reverse=True)
                    for file in backup_files[:10]:  # Show top 10 newest
                        st.text(f"- {file}")
            else:
                st.warning("stuco_data folder not found (app will create it when it runs)")

        if is_creator():
            st.divider()
            st.subheader("Restore Backup")
            st.caption("Recover lost data (attendance, users, credits)")
        
        # Show available backups
        backups = list_backups()
        if backups:
            st.info(f"Available backups ({len(backups)}):")
            for i, backup in enumerate(backups[:5], 1):
                st.text(f"{i}. {backup}")
        else:
            st.warning("No backups found.")
        
        # Restore button
        if st.button("Restore Latest Backup", type="primary"):
            success, msg = restore_latest_backup()
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        
        if st.button("Logout", key="logout_btn", use_container_width=True):
            st.session_state.user = None
            st.session_state.role = None
            st.success("Logged out successfully")
            st.rerun()
        
        st.divider()
        
        # Creator-only controls
        if is_creator():
            st.subheader("Creator Controls")
            
            # Toggle signup visibility
            config = load_config()
            new_signup_state = st.checkbox(
                "Enable Signup Form", 
                value=config.get("show_signup", False),
                key="toggle_signup"
            )
            if new_signup_state != config.get("show_signup", False):
                config["show_signup"] = new_signup_state
                save_config(config)
                st.success(f"Signup form {'enabled' if new_signup_state else 'disabled'}")
                st.rerun()
            
            st.divider()
            
            # User management
            st.subheader("User Management")
            new_username = st.text_input("New Username", key="creator_add_user")
            new_password = st.text_input("New Password", type="password", key="creator_add_pass")
            new_role = st.selectbox("User Role", ROLES + [CREATOR_ROLE], key="creator_add_role")
            
            if st.button("Create User", key="creator_add_btn") and new_username and new_password:
                success, msg = save_user(new_username, new_password, new_role)
                st.success(msg) if success else st.error(msg)
            
            st.divider()
            
            # Manage existing users
            st.subheader("Manage Users")
            users = load_users()
            if users:
                user_table = pd.DataFrame([
                    {
                        "Username": username,
                        "Role": user["role"].capitalize(),
                        "Created": datetime.fromisoformat(user["created_at"]).strftime("%Y-%m-%d"),
                        "Last Login": datetime.fromisoformat(user["last_login"]).strftime("%Y-%m-%d") 
                                      if user["last_login"] else "Never"
                    }
                    for username, user in users.items()
                ])
                st.dataframe(user_table, use_container_width=True)
                
                selected_user = st.selectbox("Select User", list(users.keys()), key="creator_select_user")
                if selected_user:
                    col_update, col_delete = st.columns(2)
                    
                    with col_update:
                        current_role = users[selected_user]["role"]
                        updated_role = st.selectbox(
                            "Update Role", 
                            ROLES + [CREATOR_ROLE], 
                            index=(ROLES + [CREATOR_ROLE]).index(current_role),
                            key="creator_update_role"
                        )
                        if st.button("Update Role", key="creator_update_btn"):
                            success, msg = update_user_role(selected_user, updated_role)
                            st.success(msg) if success else st.error(msg)
                    
                    with col_delete:
                        if st.button("Delete User", type="secondary", key="creator_delete_btn"):
                            success, msg = delete_user(selected_user)
                            st.success(msg) if success else st.error(msg)
                            st.rerun()
            else:
                st.info("No users found")
        
        # Admin-only quick stats
        if is_admin():
            st.divider()
            st.subheader("Quick Stats")
            st.metric("Total Members", len(st.session_state.attendance))
            st.metric("Total Funds (Estimated)", f"${sum(st.session_state.scheduled_events['Total Funds']):.2f}")

    # ------------------------------
    # Main Tabs
    # ------------------------------
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Calendar", 
        "Announcements",
        "Financial Planning", 
        "Attendance",
        "Credit & Rewards", 
        "SCIS AI Tools", 
        "Money Transfers"
    ])

    # ------------------------------
    # Tab 1: Calendar
    # ------------------------------
    with tab1:
        st.subheader("Event Calendar")
        render_calendar()
        
        if is_admin():
            with st.expander("Manage Calendar Events (Admin Only)", expanded=False):
                st.subheader("Add/Edit Calendar Entry")
                plan_date = st.date_input("Select Date", date.today())
                date_str = plan_date.strftime("%Y-%m-%d")
                current_plan = st.session_state.calendar_events.get(date_str, "")
                plan_text = st.text_input("Event Description (max 100 characters)", current_plan, max_chars=100)
                
                col_save, col_delete = st.columns(2)
                with col_save:
                    if st.button("Save Event"):
                        st.session_state.calendar_events[date_str] = plan_text
                        success, msg = save_data()
                        if success:
                            st.success(f"Saved event for {plan_date.strftime('%b %d, %Y')}")
                        else:
                            st.error(msg)
                
                with col_delete:
                    if st.button("Delete Event", type="secondary") and date_str in st.session_state.calendar_events:
                        del st.session_state.calendar_events[date_str]
                        success, msg = save_data()
                        if success:
                            st.success(f"Deleted event for {plan_date.strftime('%b %d, %Y')}")
                        else:
                            st.error(msg)

    # ------------------------------
    # Tab 2: Announcements
    # ------------------------------
    with tab2:
        st.subheader("Announcements")
        
        # Display announcements with titles
        if st.session_state.announcements:
            # Sort by newest first
            sorted_announcements = sorted(
                st.session_state.announcements, 
                key=lambda x: x["time"], 
                reverse=True
            )
            
            for idx, ann in enumerate(sorted_announcements):
                col_content, col_actions = st.columns([5, 1])
                with col_content:
                    # Display with title
                    st.info(f"**{ann['title']}**\n\n"
                            f"*{datetime.fromisoformat(ann['time']).strftime('%b %d, %Y - %H:%M')}*\n\n"
                            f"{ann['text']}")
                with col_actions:
                    if is_admin():
                        if st.button("Delete", key=f"del_ann_{idx}", type="secondary", use_container_width=True):
                            st.session_state.announcements.pop(idx)
                            success, msg = save_data()
                            if success:
                                st.success("Announcement deleted")
                                st.rerun()
                            else:
                                st.error(msg)
            
                if idx < len(sorted_announcements) - 1:
                    st.divider()
        else:
            st.info("No announcements yet. Check back later!")
        
        # Add new announcement with title (admin only)
        if is_admin():
            with st.expander("Add New Announcement (Admin Only)", expanded=False):
                st.subheader("New Announcement")
                ann_title = st.text_input("Announcement Title", "Upcoming Meeting")
                new_announcement = st.text_area(
                    "Announcement Content", 
                    "Attention: Next student council meeting will be held on Friday at 3 PM.",
                    height=100
                )
                if st.button("Post Announcement"):
                    if not ann_title.strip():
                        st.error("Please enter a title for the announcement")
                    elif not new_announcement.strip():
                        st.error("Announcement content cannot be empty")
                    else:
                        st.session_state.announcements.append({
                            "title": ann_title,
                            "text": new_announcement,
                            "time": datetime.now().isoformat(),
                            "author": st.session_state.user
                        })
                        success, msg = save_data()
                        if success:
                            st.success("Announcement posted successfully!")
                        else:
                            st.error(msg)

    # ------------------------------
    # Tab 3: Financial Planning
    # ------------------------------
    with tab3:
        st.subheader("Financial Dashboard")
        
        # Overall progress
        col1, col2 = st.columns(2)
        with col1:
            current_funds = st.number_input("Current Funds Raised", value=0.0, step=100.0, format="%.2f")
        with col2:
            target_funds = st.number_input("Annual Fundraising Target", value=15000.0, step=1000.0, format="%.2f")
        
        # Progress bar
        progress = min(100.0, (current_funds / target_funds) * 100) if target_funds > 0 else 0
        st.progress(progress / 100)
        st.caption(f"Progress: {progress:.1f}% of ${target_funds:,.2f} target")

        # Split view for event types
        col_scheduled, col_occasional = st.columns(2)

        with col_scheduled:
            st.subheader("Scheduled Events")
            st.dataframe(st.session_state.scheduled_events, use_container_width=True)

            if is_admin():
                with st.expander("Manage Scheduled Events (Admin Only)", expanded=False):
                    event_name = st.text_input("Event Name", "Monthly Bake Sale")
                    funds_per = st.number_input("Funds Per Event", value=250.0, step=50.0)
                    freq_per_month = st.number_input("Frequency Per Month", value=1, step=1, min_value=1)
                    
                    if st.button("Add Scheduled Event"):
                        total = funds_per * freq_per_month * 12  # Annual total
                        new_event = pd.DataFrame({
                            'Event Name': [event_name],
                            'Funds Per Event': [funds_per],
                            'Frequency Per Month': [freq_per_month],
                            'Total Funds': [total]
                        })
                        st.session_state.scheduled_events = pd.concat(
                            [st.session_state.scheduled_events, new_event], ignore_index=True
                        )
                        success, msg = save_data()
                        if success:
                            st.success("Event added successfully!")
                        else:
                            st.error(msg)

                # Delete scheduled event
                if not st.session_state.scheduled_events.empty:
                    col_select, col_delete = st.columns([3,1])
                    with col_select:
                        event_to_delete = st.selectbox(
                            "Select Event to Remove", 
                            st.session_state.scheduled_events['Event Name']
                        )
                    with col_delete:
                        if st.button("Remove", type="secondary"):
                            st.session_state.scheduled_events = st.session_state.scheduled_events[
                                st.session_state.scheduled_events['Event Name'] != event_to_delete
                            ].reset_index(drop=True)
                            success, msg = save_data()
                            if success:
                                st.success("Event removed")
                            else:
                                st.error(msg)

            # Total calculation
            total_scheduled = st.session_state.scheduled_events['Total Funds'].sum() if not st.session_state.scheduled_events.empty else 0
            st.metric("Annual Projected Funds", f"${total_scheduled:,.2f}")

        with col_occasional:
            st.subheader("Occasional Events")
            st.dataframe(st.session_state.occasional_events, use_container_width=True)

            if is_admin():
                with st.expander("Manage Occasional Events (Admin Only)", expanded=False):
                    event_name = st.text_input("Event Name (Occasional)", "Charity Run")
                    funds_raised = st.number_input("Funds Raised", value=1500.0, step=100.0)
                    cost = st.number_input("Organizational Cost", value=300.0, step=50.0)
                    staff_many = st.selectbox("Requires Many Staff? (1=Yes, 0=No)", [0, 1])
                    prep_time = st.selectbox("Preparation Time <1 Week? (1=Yes, 0=No)", [0, 1])
                    
                    if st.button("Add Occasional Event"):
                        # Calculate event rating based on profitability and effort
                        rating = (funds_raised * 0.5) - (cost * 0.3) + (staff_many * -50) + (prep_time * 50)
                        new_event = pd.DataFrame({
                            'Event Name': [event_name],
                            'Total Funds Raised': [funds_raised],
                            'Cost': [cost],
                            'Staff Many Or Not': [staff_many],
                            'Preparation Time': [prep_time],
                            'Rating': [rating]
                        })
                        st.session_state.occasional_events = pd.concat(
                            [st.session_state.occasional_events, new_event], ignore_index=True
                        )
                        success, msg = save_data()
                        if success:
                            st.success("Event added successfully!")
                        else:
                            st.error(msg)

                # Delete occasional event
                if not st.session_state.occasional_events.empty:
                    col_select, col_delete = st.columns([3,1])
                    with col_select:
                        event_to_delete = st.selectbox(
                            "Select Occasional Event to Remove", 
                            st.session_state.occasional_events['Event Name']
                        )
                    with col_delete:
                        if st.button("Remove", type="secondary"):
                            st.session_state.occasional_events = st.session_state.occasional_events[
                                st.session_state.occasional_events['Event Name'] != event_to_delete
                            ].reset_index(drop=True)
                            success, msg = save_data()
                            if success:
                                st.success("Event removed")
                            else:
                                st.error(msg)

            # Sort functionality
            if not st.session_state.occasional_events.empty:
                if st.button("Sort by Rating (Best First)"):
                    st.session_state.occasional_events = st.session_state.occasional_events.sort_values(
                        by='Rating', ascending=False
                    ).reset_index(drop=True)
                    success, msg = save_data()
                    if success:
                        st.success("Events sorted by rating")
                    else:
                        st.error(msg)

            # Optimization tool
            if not st.session_state.occasional_events.empty and is_admin():
                st.subheader("Event Optimization")
                target = st.number_input("Fundraising Target", value=5000.0, step=500.0)
                if st.button("Optimize Event Schedule"):
                    net_profits = st.session_state.occasional_events['Total Funds Raised'] - st.session_state.occasional_events['Cost']
                    allocations = np.zeros(len(net_profits), dtype=int)
                    remaining = target

                    # Initial allocation
                    for i in range(len(net_profits)):
                        if remaining <= 0:
                            break
                        if net_profits[i] > 0 and allocations[i] < 2:
                            allocations[i] = 1
                            remaining -= net_profits[i]

                    # Additional allocation if needed
                    while remaining > 0:
                        available = np.where(allocations < 2)[0]
                        if len(available) == 0:
                            break
                        best_idx = available[np.argmax(net_profits[available])]
                        if net_profits[best_idx] <= remaining:
                            allocations[i] += 1
                            remaining -= net_profits[best_idx]
                        else:
                            break

                    st.session_state.allocation_count += 1
                    col_name = f'Allocations (Target: ${target:,.0f})'
                    st.session_state.occasional_events[col_name] = allocations
                    success, msg = save_data()
                    if success:
                        st.success("Optimization complete! See results in table.")
                    else:
                        st.error(msg)

            # Calculate totals
            if not st.session_state.occasional_events.empty:
                net_occasional = (st.session_state.occasional_events['Total Funds Raised'] - st.session_state.occasional_events['Cost']).sum()
                st.metric("Net from Occasional Events", f"${net_occasional:,.2f}")

    # ------------------------------
    # Tab 4: Attendance
    # ------------------------------
    with tab4:
            st.subheader("Attendance Tracking")
            if is_admin() and st.button("Reset Attendance Data", type="secondary"):
                reset_attendance_data()
                st.rerun()
            
            def mark_all_present(meeting_name):
                """Mark all students as present for a specific meeting with backup"""
                if not meeting_name or meeting_name not in st.session_state.attendance.columns:
                    return False, "Invalid meeting name"
                
                # Create backup before making changes
                backup_data()
                
                # Set all students to present for this meeting
                st.session_state.attendance[meeting_name] = True
                
                # Save changes
                success, msg = save_data()
                if success:
                    return True, f"All students marked as present for {meeting_name}"
                else:
                    return False, f"Failed to save changes: {msg}"
            
            # Summary statistics
            st.subheader("Attendance Summary")
            attendance_rates = calculate_attendance_rates()
            st.dataframe(attendance_rates, use_container_width=True)
            
            # Detailed view for admins
            if is_admin():
                st.subheader("Detailed Attendance Records")
                
                if len(st.session_state.meeting_names) > 0:
                    st.caption("Quick Actions:")
                    # Arrange buttons in rows of 3 to prevent clutter
                    cols = st.columns(min(3, len(st.session_state.meeting_names)))
                    for i, meeting in enumerate(st.session_state.meeting_names):
                        with cols[i % 3]:
                            if st.button(
                                f"Mark All Present: {meeting}",
                                type="secondary",
                                key=f"mark_all_{meeting}"
                            ):
                                success, msg = mark_all_present(meeting)
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    st.divider()  # Separate buttons from the table
                
                if len(st.session_state.meeting_names) == 0:
                    st.info("No meetings created yet. Add your first meeting below.")
                else:
                    st.write("Update attendance records (check boxes for attendees):")
                    edited_df = st.data_editor(
                        st.session_state.attendance,
                        column_config={"Name": st.column_config.TextColumn("Member Name", disabled=True)},
                        disabled=False,
                        use_container_width=True
                    )
                    
                    if not edited_df.equals(st.session_state.attendance):
                        st.session_state.attendance = edited_df
                        success, msg = save_data()
                        if success:
                            st.success("Attendance records updated")
                        else:
                            st.error(msg)
                
                # Meeting management
                st.divider()
                st.subheader("Manage Meetings")
                col_add, col_remove = st.columns(2)
                
                with col_add:
                    if st.button("Add New Meeting"):
                        add_new_meeting()
                
                with col_remove:
                    if st.session_state.meeting_names:
                        meeting_to_remove = st.selectbox("Select Meeting to Remove", st.session_state.meeting_names)
                        if st.button("Remove Meeting", type="secondary"):
                            delete_meeting(meeting_to_remove)
                
                # Member management
                st.divider()
                st.subheader("Manage Members")
                col_add_mem, col_remove_mem = st.columns(2)
                
                with col_add_mem:
                    new_member = st.text_input("Add New Member")
                    if st.button("Add Member"):
                        add_new_person(new_member)
                
                with col_remove_mem:
                    if not st.session_state.attendance.empty:
                        member_to_remove = st.selectbox("Select Member to Remove", st.session_state.attendance['Name'])
                        if st.button("Remove Member", type="secondary"):
                            delete_person(member_to_remove)

    # ------------------------------
    # Tab 5: Credit & Rewards
    # ------------------------------
    with tab5:
        col_credits, col_rewards = st.columns(2)
    
        # ------------------------------
        # Left Column: Credit Management (Simplified)
        # ------------------------------
        with col_credits:
            st.subheader("Student Credits")
            # Show current credit data (sorted by name for easier finding)
            st.dataframe(
                st.session_state.credit_data.sort_values("Name").reset_index(drop=True),
                use_container_width=True
            )
    
            # ------------------------------
            # 1. Excel Import (Keep for bulk adding students)
            # ------------------------------
            if is_admin() or is_credit_manager():
                st.divider()
                st.subheader("Import Students (Excel)")
                st.caption("Uses 'student_council_members.xlsx' (all get 0 default credits)")
                st.caption("⚠️ Replaces existing credit members (backup created automatically)")
                
                if st.button("Import from Excel", type="primary", key="credit_excel_import"):
                    import_success, import_msg = import_credit_members_from_excel()
                    if import_success:
                        st.success(import_msg)
                        st.rerun()
                    else:
                        st.error(import_msg)
    
            # ------------------------------
            # 2. Simplified Credit Adjustment (Add/Remove Specific Amounts)
            # ------------------------------
            if is_admin() or is_credit_manager():
                st.divider()
                st.subheader("Adjust Student Credits")
                
                # Step 1: Select student (dropdown, no typing)
                if not st.session_state.credit_data.empty:
                    # Sort students alphabetically for easier selection
                    sorted_students = sorted(st.session_state.credit_data["Name"].tolist())
                    selected_student = st.selectbox(
                        "Choose a Student",
                        options=sorted_students,
                        key="credit_student_select"
                    )
    
                    # Step 2: Choose action (Add or Remove)
                    action = st.radio(
                        "Action",
                        options=["Add Credits", "Remove Credits"],
                        key="credit_action"
                    )
    
                    # Step 3: Enter specific credit amount
                    credit_amount = st.number_input(
                        "Credit Amount",
                        min_value=1,  # Prevent 0 or negative amounts by default
                        value=10,
                        step=1,
                        key="credit_amount"
                    )
    
                    # Step 4: Confirm and apply change
                    if st.button("Apply Change", type="secondary", key="credit_apply"):
                        # Create backup first (safety first)
                        backup_data()
                        
                        # Get current credit balance
                        current_credits = st.session_state.credit_data.loc[
                            st.session_state.credit_data["Name"] == selected_student,
                            "Total_Credits"
                        ].iloc[0]
    
                        # Update credits based on action
                        if action == "Add Credits":
                            new_credits = current_credits + credit_amount
                            st.session_state.credit_data.loc[
                                st.session_state.credit_data["Name"] == selected_student,
                                "Total_Credits"
                            ] = new_credits
                            success_msg = f"Added {credit_amount} credits to {selected_student} (New total: {new_credits})"
                        
                        else:  # Remove Credits
                            # Prevent negative credits
                            if current_credits >= credit_amount:
                                new_credits = current_credits - credit_amount
                                st.session_state.credit_data.loc[
                                    st.session_state.credit_data["Name"] == selected_student,
                                    "Total_Credits"
                                ] = new_credits
                                success_msg = f"Removed {credit_amount} credits from {selected_student} (New total: {new_credits})"
                            else:
                                st.error(f"Cannot remove {credit_amount} credits—{selected_student} only has {current_credits} credits.")
                                # Skip saving if removal would cause negative credits
                                pass
    
                        # Save changes to file
                        save_success, save_msg = save_data()
                        if save_success:
                            st.success(success_msg)
                            # Refresh to show updated credit table
                            st.rerun()
                        else:
                            st.error(f"Failed to save changes: {save_msg}")
    
                else:
                    # No students in credit system yet
                    st.info("No students found in credit system. Use 'Import from Excel' to add students first.")
    
                # ------------------------------
                # 3. Remove Entire Student (Keep, with dropdown)
                # ------------------------------
                st.divider()
                st.subheader("Remove Student from Credit System")
                
                if not st.session_state.credit_data.empty:
                    student_to_remove = st.selectbox(
                        "Choose Student to Remove",
                        options=sorted(st.session_state.credit_data["Name"].tolist()),
                        key="remove_student_select"
                    )
    
                    if st.button("Remove Student", type="secondary", key="student_remove"):
                        backup_data()  # Backup before deletion
                        st.session_state.credit_data = st.session_state.credit_data[
                            st.session_state.credit_data["Name"] != student_to_remove
                        ].reset_index(drop=True)
                        
                        save_success, save_msg = save_data()
                        if save_success:
                            st.success(f"Successfully removed {student_to_remove} from credit system")
                            st.rerun()
                        else:
                            st.error(f"Failed to remove student: {save_msg}")
                else:
                    st.info("No students to remove—credit system is empty.")
    
        # ------------------------------
        # Right Column: Rewards (Keep Existing Functionality)
        # ------------------------------
        with col_rewards:
            st.subheader("Available Rewards")
            st.dataframe(st.session_state.reward_data, use_container_width=True)
    
            if is_admin():
                with st.expander("Manage Rewards (Admin Only)", expanded=False):
                    # Add New Reward
                    st.subheader("Add New Reward")
                    reward_name = st.text_input("Reward Name", "School Merchandise")
                    reward_cost = st.number_input("Credit Cost", min_value=1, value=75, step=5)
                    reward_stock = st.number_input("Initial Stock", min_value=0, value=15, step=1)
                    
                    if st.button("Add Reward", key="add_reward"):
                        backup_data()
                        new_reward = pd.DataFrame({
                            'Reward': [reward_name],
                            'Cost': [reward_cost],
                            'Stock': [reward_stock]
                        })
                        st.session_state.reward_data = pd.concat(
                            [st.session_state.reward_data, new_reward], ignore_index=True
                        )
                        success, msg = save_data()
                        if success:
                            st.success(f"Added reward: {reward_name} (Cost: {reward_cost} credits)")
                        else:
                            st.error(msg)
    
                    # Process Reward Redemption
                    st.divider()
                    st.subheader("Process Reward Redemption")
                    if not st.session_state.credit_data.empty and not st.session_state.reward_data.empty:
                        # Student selection (dropdown, matches credit adjustment)
                        redeem_student = st.selectbox(
                            "Student Redeeming",
                            options=sorted(st.session_state.credit_data["Name"].tolist()),
                            key="redeem_student_select"
                        )
                        # Reward selection
                        redeem_reward = st.selectbox(
                            "Reward",
                            options=st.session_state.reward_data["Reward"].tolist(),
                            key="redeem_reward_select"
                        )
                        
                        if st.button("Confirm Redemption", key="confirm_redeem"):
                            backup_data()
                            # Get student's available credits
                            student_credits = st.session_state.credit_data.loc[
                                st.session_state.credit_data["Name"] == redeem_student,
                                "Total_Credits"
                            ].iloc[0]
                            student_redeemed = st.session_state.credit_data.loc[
                                st.session_state.credit_data["Name"] == redeem_student,
                                "RedeemedCredits"
                            ].iloc[0]
                            available_credits = student_credits - student_redeemed
    
                            # Get reward cost and stock
                            reward_cost = st.session_state.reward_data.loc[
                                st.session_state.reward_data["Reward"] == redeem_reward,
                                "Cost"
                            ].iloc[0]
                            reward_stock = st.session_state.reward_data.loc[
                                st.session_state.reward_data["Reward"] == redeem_reward,
                                "Stock"
                            ].iloc[0]
    
                            # Validate redemption
                            if available_credits >= reward_cost and reward_stock > 0:
                                # Update student's redeemed credits
                                st.session_state.credit_data.loc[
                                    st.session_state.credit_data["Name"] == redeem_student,
                                    "RedeemedCredits"
                                ] += reward_cost
                                # Update reward stock
                                st.session_state.reward_data.loc[
                                    st.session_state.reward_data["Reward"] == redeem_reward,
                                    "Stock"
                                ] -= 1
    
                                success, msg = save_data()
                                if success:
                                    st.success(f"{redeem_student} redeemed {redeem_reward}! Remaining credits: {available_credits - reward_cost}")
                                else:
                                    st.error(msg)
                            else:
                                if available_credits < reward_cost:
                                    st.error(f"Insufficient credits! {redeem_student} has {available_credits} available (needs {reward_cost}).")
                                else:
                                    st.error(f"Out of stock! No {redeem_reward} left.")
    
                    # Remove Reward
                    st.divider()
                    st.subheader("Remove Reward")
                    if not st.session_state.reward_data.empty:
                        reward_to_remove = st.selectbox(
                            "Choose Reward to Remove",
                            options=st.session_state.reward_data["Reward"].tolist(),
                            key="remove_reward_select"
                        )
                        if st.button("Remove Reward", type="secondary", key="reward_remove"):
                            backup_data()
                            st.session_state.reward_data = st.session_state.reward_data[
                                st.session_state.reward_data["Reward"] != reward_to_remove
                            ].reset_index(drop=True)
                            success, msg = save_data()
                            if success:
                                st.success(f"Removed reward: {reward_to_remove}")
                            else:
                                st.error(msg)
    
        # ------------------------------
        # Lucky Draw (Keep Existing, with dropdown student selection)
        # ------------------------------
        st.divider()
        st.subheader("Lucky Draw (50 Credits per Spin)")
        if is_admin():
            col_wheel, col_results = st.columns(2)
            
            with col_wheel:
                if not st.session_state.credit_data.empty:
                    # Dropdown for student selection (matches credit system)
                    draw_student = st.selectbox(
                        "Select Student for Spin",
                        options=sorted(st.session_state.credit_data["Name"].tolist()),
                        key="draw_student_select"
                    )
                    
                    if st.button("Spin Lucky Wheel", key="spin_wheel") and not st.session_state.get("spinning", False):
                        st.session_state["spinning"] = True
                        
                        # Check if student has enough credits
                        student_credits = st.session_state.credit_data.loc[
                            st.session_state.credit_data["Name"] == draw_student,
                            "Total_Credits"
                        ].iloc[0]
                        
                        if student_credits < 50:
                            st.error(f"Cannot spin! {draw_student} only has {student_credits} credits (needs 50).")
                            st.session_state["spinning"] = False
                        else:
                            # Deduct spin cost first
                            backup_data()
                            st.session_state.credit_data.loc[
                                st.session_state.credit_data["Name"] == draw_student,
                                "Total_Credits"
                            ] -= 50
                            
                            # Simulate wheel spin
                            time.sleep(1)
                            prize_idx = random.randint(0, len(st.session_state.wheel_prizes) - 1)
                            final_rotation = 3 * 360 + (prize_idx * (360 / len(st.session_state.wheel_prizes)))
                            fig = draw_wheel(np.deg2rad(final_rotation))
                            st.pyplot(fig)
                            
                            # Record and display prize
                            st.session_state["winner_prize"] = st.session_state.wheel_prizes[prize_idx]
                            save_data()  # Save credit deduction
                            st.session_state["spinning"] = False
                else:
                    st.info("No students in credit system—add students first to use Lucky Draw.")
            
            with col_results:
                if "winner_prize" in st.session_state and st.session_state["winner_prize"]:
                    st.success(f"🎉 {draw_student} won: {st.session_state['winner_prize']}")
                    
                    # Add credit prizes back to student
                    if "Credits" in st.session_state["winner_prize"]:
                        try:
                            prize_amount = int(st.session_state["winner_prize"].split()[0])
                            backup_data()
                            st.session_state.credit_data.loc[
                                st.session_state.credit_data["Name"] == draw_student,
                                "Total_Credits"
                            ] += prize_amount
                            save_data()
                            st.info(f"Added {prize_amount} credits to {draw_student}'s account!")
                        except:
                            st.warning("Could not automatically add prize credits—please adjust manually.")
        else:
            st.info("Lucky Draw is managed by administrators. Contact an admin to participate.")
    # ------------------------------
    # Tab 6: SCIS AI Tools
    # ------------------------------
    with tab6:
        st.subheader("SCIS AI Assistant Tools")
        st.info("This section is under development. Coming soon!")
        
        # Placeholder features
        with st.expander("Event Idea Generator (Beta)"):
            event_type = st.selectbox("Event Category", ["Fundraiser", "Social", "Community Service", "School Spirit"])
            if st.button("Generate Ideas"):
                ideas = {
                    "Fundraiser": [
                        "Themed bake sale with student-decorated cookies",
                        "Silent auction with donated items from local businesses",
                        "Talent show with admission fee",
                        "Movie night under the stars"
                    ],
                    "Social": [
                        "School dance with photo booth",
                        "Game night with board games and video games",
                        "Potluck dinner with international cuisine",
                        "Hiking trip to local trails"
                    ],
                    "Community Service": [
                        "Park cleanup day with local organization",
                        "Food drive for community pantry",
                        "Senior center visit with performances",
                        "Environmental awareness workshop"
                    ],
                    "School Spirit": [
                        "Spirit week with daily themes",
                        "Rally before big games",
                        "Teacher appreciation day",
                        "School history trivia contest"
                    ]
                }
                
                st.success(f"Generated ideas for {event_type} events:")
                for i, idea in enumerate(ideas[event_type], 1):
                    st.write(f"{i}. {idea}")

    # ------------------------------
    # Tab 7: Money Transfers
    # ------------------------------
    with tab7:
        st.subheader("Money Transfer Records")
        
        if not st.session_state.money_data.empty:
            st.dataframe(st.session_state.money_data, use_container_width=True)
        else:
            st.info("No money transfer records yet")
        
        if is_admin():
            with st.expander("Manage Financial Records (Admin Only)", expanded=False):
                st.subheader("Record New Transaction")
                amount = st.number_input("Amount ($)", value=0.0, step=50.0)
                description = st.text_input("Description", "Bake sale proceeds")
                transaction_date = st.date_input("Date", date.today())
                
                if st.button("Record Transaction"):
                    new_entry = pd.DataFrame({
                        'Amount': [amount],
                        'Description': [description],
                        'Date': [transaction_date.strftime("%Y-%m-%d")],
                        'Handled By': [st.session_state.user]
                    })
                    st.session_state.money_data = pd.concat(
                        [st.session_state.money_data, new_entry], ignore_index=True
                    )
                    success, msg = save_data()
                    if success:
                        st.success("Transaction recorded")
                    else:
                        st.error(msg)
            
            if not st.session_state.money_data.empty and is_admin():
                if st.button("Clear All Records", type="secondary"):
                    confirm = st.checkbox("I confirm I want to delete all financial records")
                    if confirm:
                        st.session_state.money_data = pd.DataFrame(columns=['Amount', 'Description', 'Date', 'Handled By'])
                        success, msg = save_data()
                        if success:
                            st.success("All records cleared")
                        else:
                            st.error(msg)

# ------------------------------
# Main Execution Flow
# ------------------------------
def main():
    # File lock to prevent concurrent writes
    lock_file = os.path.join(DATA_DIR, ".app_lock")
    if os.path.exists(lock_file):
        # Check if lock is older than 5 minutes (stale)
        lock_time = datetime.fromtimestamp(os.path.getmtime(lock_file))
        if datetime.now() - lock_time > timedelta(minutes=5):
            os.remove(lock_file)  # Remove stale lock
        else:
            st.warning("Another instance is using the app. Please try again shortly.")
            return
    
    # Create lock file
    try:
        with open(lock_file, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        st.error(f"Could not create lock file: {str(e)}")
        return
    
    try:
        # Initialize everything
        initialize_files()
        initialize_session_state()
        
        # Custom CSS
        st.markdown("""
        <style>
        .calendar-day {
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 8px;
            min-height: 100px;
            margin: 2px;
        }
        .today {
            background-color: #e3f2fd;
            border: 2px solid #1976d2;
        }
        .other-month {
            background-color: #f5f5f5;
            color: #9e9e9e;
        }
        .day-header {
            font-weight: bold;
            text-align: center;
            padding: 8px;
            background-color: #f0f2f6;
            border-radius: 5px;
        }
        .plan-text {
            font-size: 0.85rem;
            margin-top: 5px;
            color: #374151;
        }
        .role-badge {
            border-radius: 12px;
            padding: 3px 8px;
            font-size: 0.75rem;
            font-weight: bold;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Login flow
        if st.session_state.user is None:
            # Show login form in sidebar
            login_success = render_login_form()
            render_signup_form()
            
            # Show welcome screen in main area
            render_welcome_screen()
            
            # If login successful, reload
            if login_success:
                time.sleep(1)
                st.rerun()
        else:
            # Load app data and show main app
            load_data()
            render_main_app()
    finally:
        # Remove lock file when done
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except:
                pass

if __name__ == "__main__":
    main()




























