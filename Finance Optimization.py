import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
import os
import json
import bcrypt
import datetime
from datetime import date, timedelta
import shutil
import gspread
from google.oauth2.service_account import Credentials
import requests
from io import BytesIO, StringIO
import base64
from datetime import date, datetime

# ------------------------------
# Configuration and Constants
# ------------------------------
st.set_page_config(
    page_title="SCIS HQ US Stuco",
    layout="wide",
    initial_sidebar_state="expanded"
)

WELCOME_MESSAGE = "Welcome to SCIS Student Council Management System"
CREATOR_ROLE = "creator"  # Special role with full access
ROLES = ["admin", "credit_manager", "user"]

DATA_DIR = "stuco_data"
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
DATA_FILE = os.path.join(DATA_DIR, "app_data.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
GROUPS_FILE = os.path.join(DATA_DIR, "groups.json")
REIMBURSEMENTS_FILE = os.path.join(DATA_DIR, "reimbursements.json")
GROUP_CODES_FILE = os.path.join(DATA_DIR, "group_codes.json")
CONFIG_FILE = os.path.join(DATA_DIR, "app_config.json")

st.markdown("""
<style>
.day-header {
    text-align: center;
    font-weight: bold;
    padding: 8px;
    background-color: #f0f2f6;
    border-radius: 4px;
}

.calendar-day {
    text-align: center;
    padding: 10px 5px;
    min-height: 80px;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    margin: 2px;
}

.calendar-day.other-month {
    background-color: #fafafa;
    color: #999;
}

.calendar-day.today {
    background-color: #e3f2fd;
    border: 2px solid #2196f3;
}

.plan-text {
    font-size: 0.8em;
    margin-top: 5px;
    color: #333;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.role-badge {
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: bold;
}

.group-card {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.group-header {
    font-weight: bold;
    font-size: 1.2em;
    margin-bottom: 10px;
}

.meeting-item {
    background-color: #ffffff;
    border-left: 3px solid #2196f3;
    padding: 8px 12px;
    margin-bottom: 8px;
    border-radius: 4px;
}

.reimbursement-item {
    background-color: #ffffff;
    border-left: 3px solid #4caf50;
    padding: 8px 12px;
    margin-bottom: 8px;
    border-radius: 4px;
}
</style>
""", unsafe_allow_html=True)

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        # First convert any numpy types
        obj = convert_numpy_types(obj)
        
        # Then handle date/datetime types
        from datetime import date, datetime
        valid_types = (date, datetime)
        if isinstance(obj, valid_types):
            return obj.isoformat()
        return super().default(obj)

# ------------------------------
# Google Sheets Integration
# ------------------------------
def connect_gsheets():
    try:
        # Extract secrets from Streamlit's secrets manager
        google_secrets = st.secrets["google_sheets"]
        
        # Create credentials dictionary
        credentials = {
            "type": "service_account",
            "project_id": "studentcouncilapp-474307",  # Derived from your service account email
            "private_key_id": google_secrets["private_key_id"],
            "private_key": google_secrets["private_key"].replace("\\n", "\n"),  # Fix newline characters
            "client_email": google_secrets["service_account_email"],
            "client_id": "",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{google_secrets['service_account_email']}"
        }
        
        # Create credentials object
        creds = Credentials.from_service_account_info(
            credentials,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        
        # Authenticate and connect
        client = gspread.authorize(creds)
        
        # Extract spreadsheet ID from URL
        sheet_url = google_secrets["sheet_url"]
        spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]
        
        # Open the spreadsheet
        sheet = client.open_by_key(spreadsheet_id)
        st.success("Successfully connected to Google Sheets!")
        return sheet
        
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {str(e)}")
        st.info("Using local storage only")
        return None

# ------------------------------
# Backup System
# ------------------------------
def backup_data():
    """Create timestamped backups of all data files"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Backup all important data files
    for file_path in [DATA_FILE, USERS_FILE, GROUPS_FILE, REIMBURSEMENTS_FILE, CONFIG_FILE, GROUP_CODES_FILE]:
        if os.path.exists(file_path):
            file_name = os.path.basename(file_path)
            backup_path = os.path.join(BACKUP_DIR, f"{file_name}_{timestamp}")
            shutil.copy2(file_path, backup_path)

# ------------------------------
# File Initialization
# ------------------------------
def initialize_files():
    """Initialize all required data files and directories"""
    # Create directories if they don't exist
    for dir_path in [DATA_DIR, BACKUP_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    
    # Create empty files if they don't exist
    for file_path in [DATA_FILE, USERS_FILE, GROUPS_FILE, REIMBURSEMENTS_FILE, CONFIG_FILE]:
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                json.dump({}, f)  # Initialize with empty dict
    
    # Initialize group codes if they don't exist
    if not os.path.exists(GROUP_CODES_FILE):
        group_codes = generate_group_codes()
        with open(GROUP_CODES_FILE, "w") as f:
            json.dump(group_codes, f, indent=2)

# ------------------------------
# Session State Initialization
# ------------------------------
def initialize_session_state():
    """Initialize all session state variables with defaults"""
    # Core user state
    if "user" not in st.session_state:
        st.session_state.user = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0
    
    # Define all required state variables with defaults
    required_states = {
        # Attendance data
        "attendance": pd.DataFrame(columns=["Name"]),
        "council_members": ["Alice", "Bob", "Charlie", "Diana", "Evan"],
        "meeting_names": ["First Meeting"],
        
        # Financial data
        "scheduled_events": pd.DataFrame(columns=[
            'Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds'
        ]),
        "occasional_events": pd.DataFrame(columns=[
            'Event Name', 'Total Funds Raised', 'Cost', 'Staff Many Or Not', 
            'Preparation Time', 'Rating'
        ]),
        "money_data": pd.DataFrame(columns=['Amount', 'Description', 'Date', 'Handled By']),
        
        # Credit and rewards system
        "credit_data": pd.DataFrame({
            'Name': ["Alice", "Bob", "Charlie", "Diana", "Evan"],
            'Total_Credits': [200, 200, 200, 200, 200],
            'RedeemedCredits': [50, 0, 50, 0, 50]
        }),
        "reward_data": pd.DataFrame({
            'Reward': ['Bubble Tea', 'Chips', 'Café Coupon', 'Movie Ticket'],
            'Cost': [50, 30, 80, 120],
            'Stock': [10, 20, 5, 3]
        }),
        "wheel_prizes": [
            "50 Credits", "Bubble Tea", "Chips", "100 Credits", 
            "Café Coupon", "Free Prom Ticket", "200 Credits"
        ],
        "wheel_colors": plt.cm.tab10(np.linspace(0, 1, 7)),
        "spinning": False,
        "winner": None,
        
        # Calendar and announcements
        "calendar_events": {},
        "current_calendar_month": (date.today().year, date.today().month),
        "announcements": [],
        
        # Group management
        "groups": ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"],
        "group_members": {f"G{i}": [] for i in range(1,9)},
        "group_meetings": {f"G{i}": [] for i in range(1,9)},
        "group_descriptions": {f"G{i}": f"Default group {i}" for i in range(1,9)},
        "current_group": None,
        "reimbursements": {"requests": []},  # Reimbursement data
        
        # Other app state
        "allocation_count": 0,
        "group_codes_initialized": False,
        "initialized": False
    }

    # Initialize any missing variables
    for key, default in required_states.items():
        if key not in st.session_state:
            st.session_state[key] = default

def initialize_group_system():
    """Initialize group system with validation checks"""
    try:
        # Check if group data exists, if not create default
        if not st.session_state.groups:
            st.session_state.groups = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]
            
        # Ensure group members and meetings structures exist for all groups
        for group in st.session_state.groups:
            if group not in st.session_state.group_members:
                st.session_state.group_members[group] = []
            if group not in st.session_state.group_meetings:
                st.session_state.group_meetings[group] = []
            if group not in st.session_state.group_descriptions:
                st.session_state.group_descriptions[group] = f"Group {group}"
                
        # Verify group codes exist
        if not st.session_state.group_codes_initialized:
            codes = load_group_codes()
            # Check if all default groups have codes
            for group in [f"G{i}" for i in range(1,9)]:
                if group not in codes:
                    codes = generate_group_codes()
                    break
            st.session_state.group_codes_initialized = True
            
        return True, "Group system initialized successfully"
    except Exception as e:
        return False, f"Error initializing group system: {str(e)}"

# ------------------------------
# Import Members from GitHub Excel File
# ------------------------------
def import_student_council_members_from_github(github_raw_url):
    """
    Import members from Excel file hosted on GitHub
    
    Args:
        github_raw_url (str): Raw URL to the Excel file on GitHub
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Validate URL
        if not github_raw_url or "github.com" not in github_raw_url or "raw" not in github_raw_url:
            return False, "Invalid GitHub raw URL. Please use the raw content URL."
            
        # Fetch the Excel file from GitHub
        response = requests.get(github_raw_url)
        if response.status_code != 200:
            return False, f"Failed to fetch file from GitHub. Status code: {response.status_code}"
            
        # Read Excel file
        excel_data = BytesIO(response.content)
        df = pd.read_excel(excel_data)
        
        # Validate structure - check for required 'Name' column
        if 'Name' not in df.columns:
            return False, "Excel file must contain a 'Name' column with member names"
            
        # Extract and clean member names
        members = [str(name).strip() for name in df['Name'].dropna() if str(name).strip()]
        
        if not members:
            return False, "No valid member names found in the Excel file"
            
        # Backup data before making changes
        backup_data()
        
        # Update attendance data with new members
        current_attendance = set(st.session_state.attendance['Name'].values) if not st.session_state.attendance.empty else set()
        new_members = [name for name in members if name not in current_attendance]
        
        if new_members:
            new_attendance_rows = []
            for name in new_members:
                row = {'Name': name}
                # Add False for all existing meetings
                for meeting in st.session_state.meeting_names:
                    row[meeting] = False
                new_attendance_rows.append(row)
            
            st.session_state.attendance = pd.concat(
                [st.session_state.attendance, pd.DataFrame(new_attendance_rows)],
                ignore_index=True
            )
        
        # Update credit data with new members
        current_credits = set(st.session_state.credit_data['Name'].values) if not st.session_state.credit_data.empty else set()
        new_credit_members = [name for name in members if name not in current_credits]
        
        if new_credit_members:
            new_credit_rows = pd.DataFrame({
                'Name': new_credit_members,
                'Total_Credits': [0 for _ in new_credit_members],
                'RedeemedCredits': [0 for _ in new_credit_members]
            })
            
            st.session_state.credit_data = pd.concat(
                [st.session_state.credit_data, new_credit_rows],
                ignore_index=True
            )
        
        # Save changes to Google Sheets
        sheet = connect_gsheets()
        if sheet:
            success, msg = save_data(sheet)
            if not success:
                return False, f"Members imported but failed to save to Google Sheets: {msg}"
        else:
            return False, "Members imported but could not connect to Google Sheets for saving"
            
        return True, f"Successfully imported {len(members)} members. {len(new_members)} new members added."
        
    except Exception as e:
        return False, f"Import error: {str(e)}"

def import_student_council_members_from_sheet(sheet):
    """Import members from Google Sheet with robust existence check for 'Members' worksheet"""
    try:
        if not sheet:
            return False, "No Google Sheet connection available"
        
        # Step 1: Explicitly check if "Members" worksheet exists FIRST
        existing_sheets = [ws.title for ws in sheet.worksheets()]
        members_sheet = None
        
        # Check if "Members" is in the list of existing sheets
        if "Members" in existing_sheets:
            # Worksheet exists - safely get it
            members_sheet = sheet.worksheet("Members")
        else:
            # Worksheet doesn't exist - create it
            members_sheet = sheet.add_worksheet(title="Members", rows="200", cols="1")
            members_sheet.append_row(["Name"])  # Add header
            return False, "Created new 'Members' worksheet. Please add member names there first."
        
        # Step 2: Extract and clean member names
        members_data = members_sheet.get_all_values()
        
        # Skip if only header exists
        if len(members_data) <= 1:
            return False, "No members found. Add names to the 'Members' worksheet below the header."
        
        # Extract valid names (skip header row, remove blanks)
        valid_members = []
        for row in members_data[1:]:  # Start from row 2 (skip header)
            if row and len(row[0].strip()) > 0:
                valid_members.append(row[0].strip())
        
        if not valid_members:
            return False, "No valid member names found in 'Members' worksheet."
        
        # Step 3: Backup data before changes
        backup_data()
        
        # Step 4: Update attendance with new members
        current_attendance = set(st.session_state.attendance['Name'].values) if not st.session_state.attendance.empty else set()
        new_attendance_members = [name for name in valid_members if name not in current_attendance]
        
        if new_attendance_members:
            new_attendance_rows = []
            for name in new_attendance_members:
                row = {"Name": name}
                for meeting in st.session_state.meeting_names:
                    row[meeting] = False
                new_attendance_rows.append(row)
            
            st.session_state.attendance = pd.concat(
                [st.session_state.attendance, pd.DataFrame(new_attendance_rows)],
                ignore_index=True
            )
        
        # Step 5: Update credit data with new members
        current_credits = set(st.session_state.credit_data['Name'].values) if not st.session_state.credit_data.empty else set()
        new_credit_members = [name for name in valid_members if name not in current_credits]
        
        if new_credit_members:
            new_credit_rows = pd.DataFrame({
                "Name": new_credit_members,
                "Total_Credits": [0] * len(new_credit_members),
                "RedeemedCredits": [0] * len(new_credit_members)
            })
            
            st.session_state.credit_data = pd.concat(
                [st.session_state.credit_data, new_credit_rows],
                ignore_index=True
            )
        
        # Step 6: Save changes
        save_success, save_msg = save_data(sheet)
        if not save_success:
            return False, f"Members imported but save failed: {save_msg}"
        
        total_imported = len(valid_members)
        new_added = len(new_attendance_members)
        return True, f"Success! Imported {total_imported} members ({new_added} new)"
        
    except gspread.exceptions.APIError as e:
        # Specific handling for duplicate sheet error
        if "A sheet with the name \"Members\" already exists" in str(e):
            return False, "The 'Members' worksheet already exists but there was a connection issue. Please try again."
        return False, f"Google Sheets API error: {str(e)}"
    except Exception as e:
        return False, f"Import failed: {str(e)}"


def clean_up_google_sheets(sheet):
    """Remove old/invalid worksheets and enforce proper Google Sheets structure"""
    try:
        if not sheet:
            return False, "No Google Sheet connection available"
            
        # List of ONLY valid worksheets (delete anything else)
        REQUIRED_WORKSHEETS = ["Attendance", "Credits", "Members", "Financials", "Groups", "Reimbursements"]
        
        # Get all current worksheets in the Google Sheet
        current_worksheets = sheet.worksheets()
        current_sheet_names = [ws.title for ws in current_worksheets]
        
        # Step 1: Delete invalid worksheets (not in REQUIRED_WORKSHEETS)
        deleted_sheets = []
        for ws in current_worksheets:
            if ws.title not in REQUIRED_WORKSHEETS:
                sheet.del_worksheet(ws)  # Delete the old/invalid sheet
                deleted_sheets.append(ws.title)
        
        # Step 2: Create any missing required worksheets
        created_sheets = []
        for required_sheet in REQUIRED_WORKSHEETS:
            if required_sheet not in current_sheet_names:
                # Create new worksheet with enough rows/columns
                new_ws = sheet.add_worksheet(title=required_sheet, rows="200", cols="10")
                
                # Add proper headers to each new worksheet
                if required_sheet == "Attendance":
                    new_ws.append_row(["Name"] + st.session_state.meeting_names)  # Name + all meetings
                elif required_sheet == "Credits":
                    new_ws.append_row(["Name", "Total_Credits", "RedeemedCredits"])  # Credit columns
                elif required_sheet == "Financials":
                    new_ws.append_row(["Amount", "Description", "Date", "Handled By"])  # Transaction columns
                elif required_sheet == "Members":
                    new_ws.append_row(["Name"])  # Simple name column for member list
                elif required_sheet == "Groups":
                    new_ws.append_row(["Group Name", "Members", "Meeting Dates", "Attendance Rate"])  # Group columns
                elif required_sheet == "Reimbursements":  # New worksheet for reimbursements
                    new_ws.append_row(["ID", "Group", "Amount", "Description", "Status", "Submitted By", "Submitted At"])
                
                created_sheets.append(required_sheet)
        
        # Success: Return summary of changes
        return True, f"Google Sheets cleaned up! Deleted: {deleted_sheets} | Created: {created_sheets}"
        
    except Exception as e:
        return False, f"Sheets cleanup failed: {str(e)}"
# ------------------------------
# Group Code Management
# ------------------------------
def generate_group_codes():
    """Generate unique codes for groups G1-G8"""
    import random
    import string
    group_codes = {}
    for i in range(1, 9):  # G1 to G8
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        group_codes[f"G{i}"] = code
    return group_codes

def load_group_codes():
    """Load codes with error handling"""
    try:
        with open(GROUP_CODES_FILE, "r") as f:
            return json.load(f)
    except:
        # Regenerate if load fails
        codes = generate_group_codes()
        with open(GROUP_CODES_FILE, "w") as f:
            json.dump(codes, f, indent=2)
        return codes

def verify_group_code(group_name, code):
    """Check if code matches the group's assigned code"""
    group_codes = load_group_codes()
    return group_codes.get(group_name) == code

def get_group_from_code(code):
    """Get group name from a code"""
    group_codes = load_group_codes()
    for group, group_code in group_codes.items():
        if group_code == code:
            return group
    return None

# ------------------------------
# Group Data Management
# ------------------------------
def load_groups_data():
    """Load group data with backup recovery"""
    try:
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, "r") as f:
                group_data = json.load(f)
            
            # Update session state with group data
            st.session_state.groups = group_data.get("groups", [])
            st.session_state.group_members = group_data.get("group_members", {})
            st.session_state.group_meetings = group_data.get("group_meetings", {})
            st.session_state.group_descriptions = group_data.get("group_descriptions", {})
            return True, "Group data loaded successfully"
        
        # Recover from backup if groups file is missing
        backups = sorted(
            [f for f in os.listdir(BACKUP_DIR) if f.startswith("groups.json")],
            reverse=True
        )
        if backups:
            st.warning("Group data missing - restoring from backup")
            latest_backup = os.path.join(BACKUP_DIR, backups[0])
            shutil.copy2(latest_backup, GROUPS_FILE)
            with open(GROUPS_FILE, "r") as f:
                group_data = json.load(f)
            
            st.session_state.groups = group_data.get("groups", [])
            st.session_state.group_members = group_data.get("group_members", {})
            st.session_state.group_meetings = group_data.get("group_meetings", {})
            st.session_state.group_descriptions = group_data.get("group_descriptions", {})
            return True, "Group data restored from backup"
                
        # Fallback to default if no backups
        st.session_state.groups = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]
        st.session_state.group_members = {f"G{i}": [] for i in range(1,9)}
        st.session_state.group_meetings = {f"G{i}": [] for i in range(1,9)}
        st.session_state.group_descriptions = {f"G{i}": f"Default group {i}" for i in range(1,9)}
        return True, "Initialized with default group data"
    except Exception as e:
        st.error(f"Error loading group data: {str(e)}")
        return False, f"Error loading group data: {str(e)}"

def save_groups_data():
    """Save group data safely"""
    try:
        backup_data()  # Backup before saving changes
        group_data = {
            "groups": st.session_state.groups,
            "group_members": st.session_state.group_members,
            "group_meetings": st.session_state.group_meetings,
            "group_descriptions": st.session_state.group_descriptions
        }
        
        temp_file = f"{GROUPS_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(group_data, f, indent=2)
        os.replace(temp_file, GROUPS_FILE)
        # Clean up temp file if needed
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return True, "Group data saved successfully"
    except Exception as e:
        return False, f"Error saving group data: {str(e)}"

# ------------------------------
# Reimbursement Management
# ------------------------------
def load_reimbursement_data():
    """Load reimbursement data"""
    try:
        if os.path.exists(REIMBURSEMENTS_FILE):
            with open(REIMBURSEMENTS_FILE, "r") as f:
                st.session_state.reimbursements = json.load(f)
            return True, "Reimbursement data loaded successfully"
        
        # Fallback to default
        st.session_state.reimbursements = {"requests": []}
        return True, "Initialized with default reimbursement data"
    except Exception as e:
        st.error(f"Error loading reimbursement data: {str(e)}")
        return False, f"Error loading reimbursement data: {str(e)}"

def save_reimbursement_data():
    """Save reimbursement data safely"""
    try:
        backup_data()  # Backup before saving changes
        temp_file = f"{REIMBURSEMENTS_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(st.session_state.reimbursements, f, indent=2)
        os.replace(temp_file, REIMBURSEMENTS_FILE)
        # Clean up temp file if needed
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return True, "Reimbursement data saved successfully"
    except Exception as e:
        return False, f"Error saving reimbursement data: {str(e)}"

def submit_reimbursement_request(group, amount, description, file_data, submitted_by):
    """Submit a new reimbursement request"""
    # Generate unique ID
    request_id = f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{np.random.randint(100, 999)}"
    
    new_request = {
        "id": request_id,
        "group": group,
        "amount": amount,
        "description": description,
        "status": "pending",  # pending, approved, rejected
        "file": file_data,  # Base64 encoded file data
        "submitted_by": submitted_by,
        "submitted_at": datetime.now().isoformat()
    }
    
    st.session_state.reimbursements["requests"].append(new_request)
    return save_reimbursement_data()

def update_reimbursement_status(request_id, new_status, comments=""):
    """Update status of a reimbursement request"""
    for request in st.session_state.reimbursements["requests"]:
        if request["id"] == request_id:
            request["status"] = new_status
            if comments:
                request["comments"] = comments
            return save_reimbursement_data()
    return False, "Request not found"

# ------------------------------
# Group Management Functions
# ------------------------------
def create_group(group_name, description=""):
    """Create a new group with proper initialization"""
    if not group_name:
        return False, "Group name cannot be empty"
        
    if group_name in st.session_state.groups:
        return False, f"Group '{group_name}' already exists"
        
    # Add group with proper initialization
    st.session_state.groups.append(group_name)
    if group_name not in st.session_state.group_members:
        st.session_state.group_members[group_name] = []
    if group_name not in st.session_state.group_meetings:
        st.session_state.group_meetings[group_name] = []
    if group_name not in st.session_state.group_descriptions:
        st.session_state.group_descriptions[group_name] = description if description else f"Group {group_name}"
    
    return save_groups_data()

def delete_group(group_name):
    """Delete a group"""
    # Prevent deletion of default groups G1-G8
    if group_name in [f"G{i}" for i in range(1,9)]:
        return False, f"Default groups (G1-G8) cannot be deleted"
        
    if group_name not in st.session_state.groups:
        return False, f"Group '{group_name}' not found"
        
    st.session_state.groups.remove(group_name)
    del st.session_state.group_members[group_name]
    del st.session_state.group_meetings[group_name]
    del st.session_state.group_descriptions[group_name]
    
    return save_groups_data()

def update_group_description(group_name, description):
    """Update group description"""
    if group_name not in st.session_state.groups:
        return False, f"Group '{group_name}' not found"
        
    st.session_state.group_descriptions[group_name] = description
    return save_groups_data()

def add_group_member(group_name, member_name):
    """Add a member to a group"""
    if group_name not in st.session_state.groups:
        return False, f"Group '{group_name}' not found"
        
    if not member_name:
        return False, "Member name cannot be empty"
        
    # Check if member exists in attendance records
    if "Name" in st.session_state.attendance and not st.session_state.attendance.empty:
        if member_name not in st.session_state.attendance['Name'].values:
            # Add option to override check for admins
            if not is_admin():
                return False, f"Member '{member_name}' not found in attendance records"
        
    if member_name in st.session_state.group_members[group_name]:
        return False, f"Member '{member_name}' is already in '{group_name}'"
        
    st.session_state.group_members[group_name].append(member_name)
    return save_groups_data()

def remove_group_member(group_name, member_name):
    """Remove a member from a group"""
    if group_name not in st.session_state.groups:
        return False, f"Group '{group_name}' not found"
        
    if member_name not in st.session_state.group_members[group_name]:
        return False, f"Member '{member_name}' not found in '{group_name}'"
        
    st.session_state.group_members[group_name].remove(member_name)
    return save_groups_data()

def add_group_meeting(group_name, meeting_date, meeting_agenda):
    """Add a meeting to a group"""
    if group_name not in st.session_state.groups:
        return False, f"Group '{group_name}' not found"
        
    if not meeting_agenda:
        return False, "Meeting agenda cannot be empty"
        
    meeting = {
        "date": meeting_date.strftime("%Y-%m-%d"),
        "agenda": meeting_agenda,
        "attendance": {}  # Will store member: boolean attendance
    }
    
    # Initialize attendance for all group members
    for member in st.session_state.group_members[group_name]:
        meeting["attendance"][member] = False
        
    st.session_state.group_meetings[group_name].append(meeting)
    return save_groups_data()

def update_group_meeting_attendance(group_name, meeting_index, member_name, attended):
    """Update attendance for a group meeting"""
    if group_name not in st.session_state.groups:
        return False, f"Group '{group_name}' not found"
        
    if meeting_index < 0 or meeting_index >= len(st.session_state.group_meetings[group_name]):
        return False, "Invalid meeting index"
        
    meeting = st.session_state.group_meetings[group_name][meeting_index]
    if member_name not in meeting["attendance"]:
        return False, f"Member '{member_name}' not found in meeting attendance"
        
    meeting["attendance"][member_name] = attended
    return save_groups_data()

def export_group_data(group_name):
    """Export group data to Excel"""
    if group_name not in st.session_state.groups:
        return None, f"Group '{group_name}' not found"
        
    # Create Excel writer
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Members sheet
        members_df = pd.DataFrame({
            "Group Members": st.session_state.group_members[group_name]
        })
        members_df.to_excel(writer, sheet_name="Members", index=False)
        
        # Meetings sheet
        if st.session_state.group_meetings[group_name]:
            meetings_data = []
            for meeting in st.session_state.group_meetings[group_name]:
                meetings_data.append({
                    "Date": meeting["date"],
                    "Agenda": meeting["agenda"],
                    "Attendance Rate": f"{sum(meeting['attendance'].values)/len(meeting['attendance'])*100:.1f}%"
                })
            meetings_df = pd.DataFrame(meetings_data)
            meetings_df.to_excel(writer, sheet_name="Meetings", index=False)
            
            # Detailed attendance sheets
            for i, meeting in enumerate(st.session_state.group_meetings[group_name]):
                attendance_data = [{"Member": m, "Attended": a} for m, a in meeting["attendance"].items()]
                attendance_df = pd.DataFrame(attendance_data)
                attendance_df.to_excel(writer, sheet_name=f"Attendance_{i+1}", index=False)
    
    output.seek(0)
    return output, f"Successfully exported {group_name} data"

# ------------------------------
# User Authentication
# ------------------------------
def load_users():
    """Load user data from file"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        st.error(f"Error loading users: {str(e)}")
        return {}

def save_users(users):
    """Save user data to file"""
    try:
        backup_data()
        temp_file = f"{USERS_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(users, f, indent=2)
        os.replace(temp_file, USERS_FILE)
        # Clean up temp file if needed
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return True
    except Exception as e:
        st.error(f"Error saving users: {str(e)}")
        return False

def authenticate(username, password):
    """Authenticate user"""
    users = load_users()
    if username in users:
        if bcrypt.checkpw(password.encode(), users[username]["password_hash"].encode()):
            return True, users[username]["role"]
        return False, "Incorrect password"
    return False, "User not found"

def register_user(username, password, role="user", group_name=None):
    """Register new user with group association"""
    if role not in ROLES:
        return False, "Invalid role"
        
    users = load_users()
    if username in users:
        return False, "Username already exists"
        
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_data = {
        "password_hash": hashed_pw,
        "role": role,
        "created_at": datetime.now().isoformat(),
        "last_login": None
    }
    
    # Add group information if provided
    if group_name:
        user_data["group"] = group_name
        
    users[username] = user_data
    return save_users(users), "User registered successfully"

def hash_password(password):
    """Hash a password for secure storage"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

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
            # Clean up temp file if needed
            if os.path.exists(temp_file):
                os.remove(temp_file)
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
        # Clean up temp file if needed
        if os.path.exists(temp_file):
            os.remove(temp_file)
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
        # Clean up temp file if needed
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return True, "User deleted successfully"
    except Exception as e:
        return False, f"Error deleting user: {str(e)}"

def get_user_group(username):
    """Get the group associated with a user"""
    users = load_users()
    if username in users and "group" in users[username]:
        return users[username]["group"]
    return None

# ------------------------------
# Main Application Functions
# ------------------------------
def load_student_council_members():
    """Load council members from attendance data"""
    try:
        if not st.session_state.attendance.empty and "Name" in st.session_state.attendance:
            return st.session_state.attendance["Name"].tolist()
        return None
    except:
        return None

def load_data(sheet):
    """Load application data"""
    try:
        # Load reimbursement data
        load_reimbursement_data()
        
        # If we have a Google Sheet connection, use it
        if sheet:
            # Load attendance data
            attendance_sheet = sheet.worksheet("Attendance")
            attendance_data = attendance_sheet.get_all_records()
            st.session_state.attendance = pd.DataFrame(attendance_data)
            
            # Load credit data
            credit_sheet = sheet.worksheet("Credits")
            credit_data = credit_sheet.get_all_records()
            st.session_state.credit_data = pd.DataFrame(credit_data)
            
            return True, "Data loaded from Google Sheets"
        
        # Fallback to local data
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                
            # Convert back to DataFrames
            for key, value in data.items():
                if key in st.session_state and isinstance(st.session_state[key], pd.DataFrame):
                    st.session_state[key] = pd.DataFrame(value)
                else:
                    st.session_state[key] = value
                    
            return True, "Data loaded from local storage"
            
        return True, "No existing data found - using defaults"
        
    except Exception as e:
        return False, f"Error loading data: {str(e)}"
        
def save_data(sheet=None):
    try:
        if 'backup_data' in globals():
            backup_data()
        
        data_to_save = {}
        excluded_keys = {"user", "role", "login_attempts", "spinning", "winner"}
        
        for key in st.session_state:
            if key in excluded_keys:
                continue
                
            value = st.session_state[key]
            # Convert numpy types first
            value = convert_numpy_types(value)
            
            # 1. Check for DataFrames - using pd.DataFrame type directly
            if isinstance(value, pd.DataFrame):
                if value.empty:
                    st.warning(f"Session state {key} is an empty DataFrame")
                    continue
                
                df = value.copy()
                # Apply numpy conversion to all elements in DataFrame
                df = df.applymap(convert_numpy_types)
                
                # Check for datetime columns using pandas' type checking
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].dt.isoformat()
                
                data_to_save[key] = df.to_dict('records')
            
            # 2. Check for date/datetime objects - using the actual classes
            elif isinstance(value, (date, datetime)):
                data_to_save[key] = value.isoformat()
            
            # 3. Handle all other valid types
            else:
                data_to_save[key] = value
        
        # Save to file with proper temp file handling
        temp_file = f"{DATA_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(data_to_save, f, indent=2, cls=DateEncoder)
        
        os.replace(temp_file, DATA_FILE)
        
        # Save reimbursement data separately
        save_reimbursement_data()
        
        # Enhanced Google Sheets integration
        if sheet:
            # Create a list of data types to sync with their worksheet names
            data_sync = [
                ("attendance", "Attendance"),
                ("occasional_events", "Events"),
                ("money_data", "Finances"),
                ("credit_data", "Credits"),
                ("reward_data", "Rewards"),
                ("users", "Users"),
                ("reimbursements", "Reimbursements")
            ]
            
            # Sync each data type if it exists in session state
            for data_key, worksheet_name in data_sync:
                if data_key in st.session_state:
                    try:
                        # Get value and convert numpy types
                        value = convert_numpy_types(st.session_state[data_key])
                        
                        # Handle DataFrames with validation
                        if isinstance(value, pd.DataFrame) and not value.empty:
                            # Apply numpy conversion to all elements
                            df = value.applymap(convert_numpy_types)
                            
                            # Check for required columns before syncing
                            required_columns = {
                                "credit_data": ["Name"],
                                # Add other data types' required columns as needed
                            }
                            
                            # Validate required columns if defined for this data type
                            if data_key in required_columns:
                                missing = [col for col in required_columns[data_key] if col not in df.columns]
                                if missing:
                                    st.warning(f"Missing columns in {data_key}: {missing}. Skipping sync.")
                                    continue
                            
                            ws = sheet.worksheet(worksheet_name)
                            ws.clear()  # Clear existing data
                            # Prepare data with headers
                            data = [df.columns.tolist()] + df.values.tolist()
                            ws.update(data)
                            
                        # Handle user dictionary
                        elif data_key == "users" and value:
                            ws = sheet.worksheet(worksheet_name)
                            ws.clear()
                            # Prepare user data with headers
                            user_data = [["Username", "Password Hash", "Role", "Last Login"]]
                            for user, details in value.items():
                                user_data.append([
                                    user,
                                    details["password"],
                                    details["role"],
                                    details.get("last_login", "")
                                ])
                            ws.update(user_data)
                            
                    except Exception as e:
                        st.warning(f"Could not sync {data_key} to Google Sheets: {str(e)}")
                        continue  # Continue with other data types even if one fails
        
        return True, "Data saved successfully (local storage and Google Sheets where available)"
        
    except Exception as e:
        return False, f"Error saving data: {str(e)}"
# ------------------------------
# UI Components
# ------------------------------
def login_ui():
    """Login interface"""
    st.title("SCIS Stuco Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            success, result = authenticate(username, password)
            if success:
                st.session_state.user = username
                st.session_state.role = result
                update_user_login(username)
                st.success(f"Welcome {username}!")
                st.rerun()
            else:
                st.session_state.login_attempts += 1
                st.error(result)
                
                if st.session_state.login_attempts >= 3:
                    st.warning("Too many attempts. Please try again later.")

def group_management_ui():
    """Group management interface with detailed views and reimbursement feature"""
    st.subheader("📊 Group Management System")
    
    # Show initialization status
    success, msg = initialize_group_system()
    if success:
        st.info(msg)
    else:
        st.error(msg)
    
    # Get user's group (for non-admins)
    user_group = get_user_group(st.session_state.user) if not is_admin() else None
    
    # Display groups - admins see all, users see only their group
    st.subheader("Your Groups" if user_group else "All Groups")
    
    # Filter groups based on user role
    if user_group:
        groups_to_display = [user_group] if user_group in st.session_state.groups else []
    else:
        # Ensure groups are sorted with G1-G8 first
        groups_to_display = sorted(
            st.session_state.groups,
            key=lambda x: (x[0] != 'G', int(x[1:]) if x.startswith('G') else 999)
        )
    
    if not groups_to_display:
        st.info("You are not assigned to any group yet.")
    else:
        for group in groups_to_display:
            with st.expander(f"Group: {group}", expanded=True):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Group description
                    desc = st.session_state.group_descriptions.get(group, "")
                    if is_admin():
                        new_desc = st.text_area(
                            "Group Description", 
                            desc, 
                            key=f"desc_{group}",
                            height=50
                        )
                        if new_desc != desc:
                            update_group_description(group, new_desc)
                            st.success("Description updated")
                            st.rerun()
                    else:
                        st.text_area(
                            "Group Description", 
                            desc, 
                            key=f"view_desc_{group}",
                            height=50,
                            disabled=True
                        )
                    
                    # Show members
                    st.write("**Members:**")
                    members = st.session_state.group_members.get(group, [])
                    if members:
                        for i, member in enumerate(members):
                            col_m1, col_m2 = st.columns([4, 1])
                            col_m1.write(f"- {member}")
                            if is_admin():
                                if st.button("Remove", key=f"remove_{group}_{i}", type="secondary", use_container_width=True):
                                    success, msg = remove_group_member(group, member)
                                    if success:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                    else:
                        st.write("No members in this group yet")
                    
                    # Add member form (admin only)
                    if is_admin():
                        new_member = st.text_input(f"Add member to {group}", key=f"new_member_{group}")
                        if st.button(f"Add to {group}", key=f"add_btn_{group}"):
                            success, msg = add_group_member(group, new_member)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                
                with col2:
                    # Group actions
                    st.write("**Actions**")
                    
                    # Meeting management
                    meeting_date = st.date_input(
                        f"Meeting date for {group}", 
                        key=f"meeting_date_{group}",
                        value=date.today()
                    )
                    meeting_agenda = st.text_area(
                        "Meeting agenda", 
                        key=f"agenda_{group}",
                        height=100
                    )
                    if st.button(f"Add Meeting", key=f"add_meeting_{group}"):
                        success, msg = add_group_meeting(group, meeting_date, meeting_agenda)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    
                    # Export data
                    if st.button(f"Export Data", key=f"export_{group}"):
                        output, msg = export_group_data(group)
                        if output:
                            st.download_button(
                                label="Download Excel",
                                data=output,
                                file_name=f"{group}_data.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_{group}"
                            )
                        else:
                            st.error(msg)
            
            # Show meetings if any exist
            if st.session_state.group_meetings.get(group, []):
                with st.expander(f"Past Meetings for {group}"):
                    for i, meeting in enumerate(st.session_state.group_meetings[group]):
                        st.write(f"**Date:** {meeting['date']}")
                        st.write(f"**Agenda:** {meeting['agenda']}")
                        
                        st.write("**Attendance:**")
                        for member, attended in meeting['attendance'].items():
                            attended_status = st.checkbox(
                                member, 
                                value=attended,
                                key=f"attendance_{group}_{i}_{member}",
                                disabled=not is_admin() and st.session_state.user != member
                            )
                            if attended_status != attended and (is_admin() or st.session_state.user == member):
                                update_group_meeting_attendance(group, i, member, attended_status)
                                st.rerun()
                        st.divider()
        
        # Reimbursement section
        st.subheader("💸 Reimbursement Requests")
        
        # Get relevant requests (all for admins, only user's group for regular users)
        if is_admin():
            relevant_requests = []
        
        # Check if reimbursements data exists and is valid
        if 'reimbursements' in st.session_state and isinstance(st.session_state.reimbursements, dict):
            # Check if requests key exists and is a list
            if "requests" in st.session_state.reimbursements and isinstance(st.session_state.reimbursements["requests"], list):
                all_requests = st.session_state.reimbursements["requests"]
                
                # Filter based on user role/group
                if is_admin():
                    relevant_requests = all_requests
                elif user_group:
                    relevant_requests = [r for r in all_requests if r.get("group") == user_group]
                # else remains empty list as defined initially
            else:
                st.error("Reimbursements data is missing 'requests' key or it's not a list")
        else:
            st.error("Reimbursements data not found or is in invalid format")
        
        # Display requests
        if relevant_requests:
            # Sort by date (newest first)
            # Add safety check for the 'submitted_at' key before sorting
            relevant_requests.sort(
                key=lambda x: x.get("submitted_at", ""), 
                reverse=True
            )
            
            for req in relevant_requests:
                # Use get() with defaults to prevent KeyErrors
                status = req.get("status", "unknown")
                status_color = "orange" if status == "pending" else "green" if status == "approved" else "red"
                
                with st.expander(
                    f"Request {req.get('id', 'N/A')} - Status: <span style='color:{status_color}'>{status.upper()}</span>", 
                    expanded=False
                ):
                    st.write(f"**Group:** {req.get('group', 'N/A')}")
                    st.write(f"**Amount:** ${req.get('amount', 0):.2f}")
                    st.write(f"**Description:** {req.get('description', 'No description')}")
                    st.write(f"**Submitted by:** {req.get('submitted_by', 'Unknown')}")
                    
                    # Safely handle date formatting
                    submitted_at = req.get('submitted_at')
                    if submitted_at:
                        try:
                            formatted_date = datetime.fromisoformat(submitted_at).strftime('%Y-%m-%d %H:%M')
                            st.write(f"**Submitted on:** {formatted_date}")
                        except ValueError:
                            st.write(f"**Submitted on:** Invalid date format")
                    else:
                        st.write(f"**Submitted on:** No date available")
                    
                    # Show file if available
                    if req.get("file"):
                        st.write("**Attached Document:**")
                        # Convert base64 back to bytes
                        file_bytes = base64.b64decode(req["file"])
                        st.download_button(
                            label="Download Document",
                            data=file_bytes,
                            file_name=f"receipt_{req['id']}.pdf",  # Assuming PDF, could be other formats
                            mime="application/pdf"
                        )
                    
                    # Show comments if any
                    if "comments" in req:
                        st.text_area("**Admin Comments:**", req["comments"], disabled=True, key=f"comments_{req['id']}")
                    
                    # Admin actions
                    if is_admin() and req["status"] == "pending":
                        col_approve, col_reject = st.columns(2)
                        with col_approve:
                            comments = st.text_input("Approval Comments (optional)", key=f"approve_{req['id']}")
                            if st.button("Approve", key=f"app_{req['id']}", type="primary"):
                                success, msg = update_reimbursement_status(req["id"], "approved", comments)
                                if success:
                                    st.success("Request approved!")
                                    st.rerun()
                                else:
                                    st.error(msg)
                        
                        with col_reject:
                            comments = st.text_input("Rejection Comments", key=f"reject_{req['id']}")
                            if st.button("Reject", key=f"rej_{req['id']}", type="secondary"):
                                if not comments:
                                    st.error("Please provide a reason for rejection")
                                else:
                                    success, msg = update_reimbursement_status(req["id"], "rejected", comments)
                                    if success:
                                        st.success("Request rejected")
                                        st.rerun()
                                    else:
                                        st.error(msg)
        else:
            st.info("No reimbursement requests found")
        
        # Submit new reimbursement request
        with st.expander("Submit New Reimbursement Request", expanded=False):
            st.subheader("Request Funding Reimbursement")
            
            # For admins, let them choose any group; for users, default to their group
            if is_admin():
                selected_group = st.selectbox("Select Group", st.session_state.groups, key="reimb_group")
            elif user_group:
                selected_group = st.selectbox("Your Group", [user_group], disabled=True, key="reimb_user_group")
            else:
                st.error("You are not assigned to any group and cannot submit requests")
                selected_group = None
            
            if selected_group:
                amount = st.number_input("Amount to Reimburse ($)", min_value=0.01, step=10.0, format="%.2f", key="reimb_amount")
                description = st.text_area("Description of Expense", "Please provide details about what this expense was for", key="reimb_desc")
                receipt_file = st.file_uploader("Upload Receipt/Document (PDF only)", type=["pdf"], key="reimb_file")
                
                if st.button("Submit Request", key="submit_reimb"):
                    if amount <= 0:
                        st.error("Amount must be greater than zero")
                    elif not description.strip():
                        st.error("Please provide a description")
                    elif not receipt_file:
                        st.error("Please upload a receipt or document")
                    else:
                        # Convert file to base64 for storage
                        file_bytes = receipt_file.read()
                        file_base64 = base64.b64encode(file_bytes).decode()
                        
                        success, msg = submit_reimbursement_request(
                            selected_group, 
                            amount, 
                            description, 
                            file_base64,
                            st.session_state.user
                        )
                        if success:
                            st.success("Reimbursement request submitted successfully!")
                            st.rerun()
                        else:
                            st.error(msg)
    
    # Admin section for group codes (only admins see this)
    if is_admin():
        with st.expander("🔑 Group Access Codes (Admin Only)", expanded=False):
            st.subheader("Group Verification Codes")
            codes = load_group_codes()
            for group in [f"G{i}" for i in range(1,9)]:  # Show G1-G8 codes first
                code = codes.get(group, "Not available")
                st.text_input(
                    f"{group} Code",
                    value=code,
                    disabled=True,
                    key=f"code_{group}"
                )

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
        # Clean up temp file if needed
        if os.path.exists(temp_file):
            os.remove(temp_file)
    except Exception as e:
        st.error(f"Error saving config: {str(e)}")

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
    """Render signup form with group code verification"""
    config = load_config()
    if not config.get("show_signup", False):
        return
    
    with st.sidebar.expander("Create New Account", expanded=False):
        st.subheader("Sign Up")
        new_username = st.text_input("Choose Username", key="signup_username")
        new_password = st.text_input("Choose Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm")
        
        group_code = st.text_input("Group Code (G1-G8)", key="signup_group_code", 
                                  placeholder="Enter your 6-character group code")
        
        if st.button("Create Account", key="signup_btn"):
            # Validate group code first
            group_name = get_group_from_code(group_code)
            if not group_name:
                st.error("Invalid group code. Please check your code and try again.")
                return
            
            # Existing validation
            if not new_username or not new_password:
                st.error("Please fill in all fields")
                return
            
            if len(new_password) < 6:
                st.error("Password must be at least 6 characters")
                return
            
            if new_password != confirm_password:
                st.error("Passwords do not match")
                return
            
            # Create user with group association
            success, msg = register_user(new_username, new_password, group_name=group_name)
            if success:
                # Add user to their group
                add_group_member(group_name, new_username)
                st.success(f"{msg} You've been added to {group_name}!")
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
def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    import numpy as np
    
    if isinstance(obj, np.ndarray):
        return obj.tolist()  # Convert arrays to lists
    elif isinstance(obj, np.integer):
        return int(obj)      # Convert numpy integers to Python int
    elif isinstance(obj, np.floating):
        return float(obj)    # Convert numpy floats to Python float
    elif isinstance(obj, np.bool_):
        return bool(obj)     # Convert numpy booleans to Python bool
    return obj

def group_diagnostics():
    """Debug tool to verify group system status"""
    if is_creator():  # Use your existing admin check function
        with st.expander("Group System Diagnostics (Admin Only)", expanded=False):
            st.subheader("System Status")
            
            # Check if groups exist
            st.write("Groups defined:", st.session_state.get("groups", "NOT FOUND"))
            
            # Check group members structure
            st.write("Group members structure:", 
                    "VALID" if all(f"G{i}" in st.session_state.group_members for i in range(1,9)) 
                    else "INVALID")
            
            # Check group codes file
            GROUP_CODES_FILE = os.path.join(DATA_DIR, "group_codes.json")
            st.write("Group codes file exists:", os.path.exists(GROUP_CODES_FILE))
            
            # Show current group codes if available
            if os.path.exists(GROUP_CODES_FILE):
                try:
                    with open(GROUP_CODES_FILE, "r") as f:
                        codes = json.load(f)
                        st.write("Loaded group codes:", codes)
                except Exception as e:
                    st.error(f"Error loading codes: {str(e)}")
                    
def list_backups():
    """List all available backups in stuco_data/backups"""
    backup_folder = "stuco_data/backups"
    if not os.path.exists(backup_folder):
        return []
    
    # Get all backup files (sorted by newest first)
    backup_files = [f for f in os.listdir(backup_folder) if f.startswith(("app_data.json_", "users.json_", "groups.json_"))]
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
    
    # Restore groups.json
    group_backups = [f for f in backups if f.startswith("groups.json_")]
    if group_backups:
        latest_group_backup = os.path.join(backup_folder, group_backups[0])
        shutil.copy2(latest_group_backup, "stuco_data/groups.json")
    
    # Restore reimbursements.json
    reimb_backups = [f for f in backups if f.startswith("reimbursements.json_")]
    if reimb_backups:
        latest_reimb_backup = os.path.join(backup_folder, reimb_backups[0])
        shutil.copy2(latest_reimb_backup, "stuco_data/reimbursements.json")
    
    return True, f"Restored latest backups: {app_backups[0] if app_backups else 'No app backup'}, {user_backups[0] if user_backups else 'No user backup'}, {group_backups[0] if group_backups else 'No group backup'}"

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
        save_data(connect_gsheets())  # Pass connected sheet to save_data()
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

def show_group_codes():
    """Ensure group codes are displayed correctly"""
    if is_creator():  # Make sure only admins can see this
        with st.expander("Group Codes (Admin Only)", expanded=False):
            st.subheader("Current Group Codes")
            group_codes = load_group_codes()
            
            if not group_codes:  # If no codes found, regenerate them
                st.warning("No group codes found. Generating new ones...")
                group_codes = generate_group_codes()
                # Save the new codes
                GROUP_CODES_FILE = os.path.join(DATA_DIR, "group_codes.json")
                with open(GROUP_CODES_FILE, "w") as f:
                    json.dump(group_codes, f, indent=2)
            
            # Display codes in a clear format
            for group in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]:
                code = group_codes.get(group, "MISSING")
                st.text_input(
                    f"{group} Code", 
                    value=code, 
                    disabled=True,
                    key=f"code_display_{group}"
                )

# ------------------------------
# Meeting & Attendance Management
# ------------------------------
def add_new_meeting():
    """Add a new meeting to attendance records"""
    new_meeting_num = len(st.session_state.meeting_names) + 1
    new_meeting_name = f"Meeting {new_meeting_num}"
    st.session_state.meeting_names.append(new_meeting_name)
    st.session_state.attendance[new_meeting_name] = False
    success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
    if success:
        st.success(f"Added new meeting: {new_meeting_name}")
    else:
        st.error(msg)

def delete_meeting(meeting_name):
    """Delete a meeting from attendance records"""
    if meeting_name in st.session_state.meeting_names:
        st.session_state.meeting_names.remove(meeting_name)
        st.session_state.attendance = st.session_state.attendance.drop(columns=[meeting_name])
        success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
    success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
        success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
    success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
        success, save_msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
        
        # Show user's group if available
        user_group = get_user_group(st.session_state.user)
        if user_group:
            st.info(f"Your Group: {user_group}")

        # Only show backup section to admins/creators
        if is_admin():
            st.divider()
            st.subheader("📂 View stuco_data Files")
            
            # Path to stuco_data
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

            st.divider()
            st.subheader("Restore Backup")
            st.caption("Recover lost data (attendance, users, credits, groups)")
        
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
                success, msg = register_user(new_username, new_password, new_role)
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
                        "Group": user.get("group", "N/A"),  # Show user's group
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
            st.subheader("Data Management")
            
            # GitHub Excel import section
            st.text_input(
                "GitHub Raw Excel URL",
                value="https://raw.githubusercontent.com/[username]/[repo]/main/student_council_members.xlsx",
                key="github_excel_url",
                help="Paste the raw URL to your student_council_members.xlsx file on GitHub"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                # Member import from GitHub button
                if st.button("Import Members from GitHub", key="import_github_btn"):
                    github_url = st.session_state.github_excel_url
                    with st.spinner("Importing members from GitHub..."):
                        success, msg = import_student_council_members_from_github(github_url)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col2:
                # Member import from Google Sheet button (keep existing)
                if st.button("Import Members from Google Sheet", key="import_gs_btn"):
                    sheet = connect_gsheets()
                    if sheet:
                        with st.spinner("Importing members from Google Sheet..."):
                            success, msg = import_student_council_members_from_sheet(sheet)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.error("Could not connect to Google Sheets")
            
            # Google Sheets cleanup button (keep existing)
            if st.button("Clean Up Google Sheets", key="clean_sheets_btn"):
                sheet = connect_gsheets()
                if sheet:
                    with st.spinner("Cleaning up Google Sheets..."):
                        success, msg = clean_up_google_sheets(sheet)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                else:
                    st.error("Could not connect to Google Sheets")

    # ------------------------------
    # Main Tabs
    # ------------------------------
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Calendar", 
        "Announcements",
        "Financial Planning", 
        "Attendance",
        "Credit & Rewards", 
        "SCIS AI Tools", 
        "Money Transfers",
        "Groups"
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
                        success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
                        if success:
                            st.success(f"Saved event for {plan_date.strftime('%b %d, %Y')}")
                        else:
                            st.error(msg)
                
                with col_delete:
                    if st.button("Delete Event", type="secondary") and date_str in st.session_state.calendar_events:
                        del st.session_state.calendar_events[date_str]
                        success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
                            success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
                        success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
                        success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
                            success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
                        success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
                            success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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
                    success, msg = save_data(connect_gsheets())  # Pass connected sheet to save_data()
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

                    # Initial allocation based on efficiency rating
                    efficiency = (net_profits * 0.6) + (st.session_state.occasional_events['Rating'] * 0.4)
                    sorted_indices = np.argsort(efficiency)[::-1]
                    
                    # Greedy algorithm to allocate events
                    for i in sorted_indices:
                        if remaining <= 0:
                            break
                            
                        if net_profits[i] <= 0:
                            continue
                            
                        max_possible = int(remaining // net_profits[i])
                        max_occurrences = min(max_possible, 5)  # Limit to 5 occurrences max
                        
                        if max_occurrences > 0:
                            allocations[i] = max_occurrences
                            remaining -= allocations[i] * net_profits[i]

                    # Create results dataframe
                    results = pd.DataFrame({
                        'Event Name': st.session_state.occasional_events['Event Name'],
                        'Net Profit': net_profits,
                        'Efficiency Score': efficiency,
                        'Recommended Occurrences': allocations,
                        'Total Contribution': net_profits * allocations
                    })
                    
                    st.subheader("Optimization Results")
                    st.dataframe(results[results['Recommended Occurrences'] > 0], use_container_width=True)
                    
                    # Summary statistics
                    total_raised = results['Total Contribution'].sum()
                    col_summary1, col_summary2 = st.columns(2)
                    with col_summary1:
                        st.metric("Total Projected Funds", f"${total_raised:,.2f}")
                    with col_summary2:
                        st.metric("Remaining Target", f"${max(0, remaining):,.2f}")
                    
                    # Visualization
                    if total_raised > 0:
                        fig, ax = plt.subplots(figsize=(10, 6))
                        ax.pie(
                            results[results['Total Contribution'] > 0]['Total Contribution'],
                            labels=results[results['Total Contribution'] > 0]['Event Name'],
                            autopct='%1.1f%%',
                            startangle=90
                        )
                        ax.axis('equal')
                        plt.title('Fund Distribution by Event')
                        st.pyplot(fig)
                    
                    # Recommendations
                    if total_raised >= target:
                        st.success(f"Success! The optimized schedule meets your target of ${target:,.2f}")
                    else:
                        st.warning(f"Optimized schedule falls short by ${remaining:,.2f}. Consider adding more events.")

    # ------------------------------
    # Tab 4: Attendance
    # ------------------------------
    with tab4:
        st.subheader("Meeting Attendance Tracking")
        
        # Display attendance data
        if st.session_state.attendance.empty:
            st.info("No attendance data available. Please add members and meetings.")
        else:
            # Show attendance rates (only if there are meetings)
            attendance_rates = calculate_attendance_rates()
            if attendance_rates:
                st.subheader("Attendance Rates")
                rate_df = pd.DataFrame(list(attendance_rates.items()), columns=['Name', 'Attendance Rate (%)'])
                rate_df = rate_df.sort_values('Attendance Rate (%)', ascending=False)
                st.dataframe(rate_df.style.format({'Attendance Rate (%)': '{:.1f}%'}), use_container_width=True)
                
                # Visualization
                fig, ax = plt.subplots(figsize=(10, 6))
                top_bottom = pd.concat([rate_df.head(5), rate_df.tail(5)])
                ax.bar(top_bottom['Name'], top_bottom['Attendance Rate (%)'], color='skyblue')
                ax.set_ylim(0, 100)
                ax.set_title('Top and Bottom 5 Attendance Rates')
                plt.xticks(rotation=45, ha='right')
                st.pyplot(fig)
        
        # Show main attendance table
        st.subheader("Meeting Attendance Records")
        edited_attendance = st.data_editor(
            st.session_state.attendance,
            use_container_width=True,
            disabled=not is_admin(),  # Only admins can edit
            column_config={
                "Name": st.column_config.TextColumn("Member Name", disabled=True)
            }
        )
        
        # Save changes if edited
        if is_admin() and not edited_attendance.equals(st.session_state.attendance):
            st.session_state.attendance = edited_attendance
            success, msg = save_data(connect_gsheets())
            if success:
                st.success("Attendance records updated")
            else:
                st.error(msg)
        
        # Admin tools
        if is_admin():
            st.divider()
            st.subheader("Attendance Management Tools")
            
            # Meeting management
            col_meet1, col_meet2 = st.columns(2)
            with col_meet1:
                if st.button("Add New Meeting", key="add_meeting_btn"):
                    add_new_meeting()
                    st.rerun()
            
            with col_meet2:
                if st.session_state.meeting_names:
                    meeting_to_delete = st.selectbox(
                        "Select Meeting to Delete", 
                        st.session_state.meeting_names,
                        key="delete_meeting_select"
                    )
                    if st.button("Delete Meeting", key="delete_meeting_btn", type="secondary"):
                        delete_meeting(meeting_to_delete)
                        st.rerun()
            
            # Member management
            col_mem1, col_mem2 = st.columns(2)
            with col_mem1:
                new_name = st.text_input("Add New Member", key="new_member_name")
                if st.button("Add Member", key="add_member_btn"):
                    add_new_person(new_name)
                    st.rerun()
            
            with col_mem2:
                if not st.session_state.attendance.empty:
                    person_to_delete = st.selectbox(
                        "Select Member to Remove",
                        st.session_state.attendance['Name'],
                        key="delete_person_select"
                    )
                    if st.button("Remove Member", key="delete_person_btn", type="secondary"):
                        delete_person(person_to_delete)
                        st.rerun()
            
            # Quick actions
            if st.session_state.meeting_names:
                st.subheader("Quick Actions")
                col_quick1, col_quick2 = st.columns(2)
                with col_quick1:
                    meeting_to_mark = st.selectbox(
                        "Select Meeting",
                        st.session_state.meeting_names,
                        key="mark_all_meeting"
                    )
                    if st.button("Mark All Present", key="mark_all_btn"):
                        success, msg = mark_all_present(meeting_to_mark)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            # Import/reset tools
            st.subheader("Data Management")
            col_data1, col_data2 = st.columns(2)
            with col_data1:
                if st.button("Import Members from Excel", key="import_attendance_btn"):
                    members = load_student_council_members()
                    st.success(f"Imported {len(members)} members")
            
            with col_data2:
                if st.button("Reset Attendance Data", key="reset_attendance_btn", type="secondary"):
                    if st.checkbox("Confirm reset (will erase all attendance records)", key="confirm_reset"):
                        reset_attendance_data()
                        st.rerun()

    # ------------------------------
    # Tab 5: Credit & Rewards
    # ------------------------------
    with tab5:
        st.subheader("Student Credit & Rewards System")
        
        # Display credit balances
        st.subheader("Current Credit Balances")
        st.dataframe(
            st.session_state.credit_data,
            use_container_width=True,
            column_config={
                "Total_Credits": st.column_config.NumberColumn("Total Credits"),
                "RedeemedCredits": st.column_config.NumberColumn("Redeemed Credits")
            }
        )
        
        # Calculate and display available credits
        if not st.session_state.credit_data.empty:
            st.session_state.credit_data['Available_Credits'] = (
                st.session_state.credit_data['Total_Credits'] - 
                st.session_state.credit_data['RedeemedCredits']
            )
            
            col_total, col_redeemed, col_available = st.columns(3)
            with col_total:
                st.metric("Total Credits Issued", st.session_state.credit_data['Total_Credits'].sum())
            with col_redeemed:
                st.metric("Total Credits Redeemed", st.session_state.credit_data['RedeemedCredits'].sum())
            with col_available:
                st.metric("Total Available Credits", st.session_state.credit_data['Available_Credits'].sum())
        
        # Reward catalog
        st.subheader("Rewards Catalog")
        st.dataframe(
            st.session_state.reward_data,
            use_container_width=True,
            column_config={
                "Cost": st.column_config.NumberColumn("Credit Cost"),
                "Stock": st.column_config.NumberColumn("Available Stock")
            }
        )
        
        # Lucky draw wheel
        st.subheader("Lucky Draw Wheel")
        if not st.session_state.spinning:
            if st.button("Spin the Wheel!", key="spin_btn"):
                st.session_state.spinning = True
                st.session_state.winner = None
                st.rerun()
        else:
            # Add spinning animation with increasing rotation
            rotation = np.random.uniform(0, 10 * 2 * np.pi)  # 10 full rotations + random
            fig = draw_wheel(rotation_angle=rotation)
            st.pyplot(fig)
            
            # Determine winner based on final position
            if st.session_state.winner is None:
                n = len(st.session_state.wheel_prizes)
                segment_angle = 2 * np.pi / n
                final_angle = rotation % (2 * np.pi)
                winner_index = int((2 * np.pi - final_angle) / segment_angle) % n
                st.session_state.winner = st.session_state.wheel_prizes[winner_index]
            
            st.success(f"Congratulations! You won: {st.session_state.winner}")
            
            if st.button("Stop Spinning", key="stop_spin_btn"):
                st.session_state.spinning = False
                # Add credits if winner is a credit prize
                if "Credits" in st.session_state.winner:
                    try:
                        credits = int(st.session_state.winner.split()[0])
                        if st.session_state.user in st.session_state.credit_data['Name'].values:
                            idx = st.session_state.credit_data[st.session_state.credit_data['Name'] == st.session_state.user].index[0]
                            st.session_state.credit_data.at[idx, 'Total_Credits'] += credits
                            save_data(connect_gsheets())
                            st.success(f"Added {credits} credits to your account!")
                    except:
                        pass
                st.rerun()
        
        # Admin/reward manager tools
        if is_admin() or is_credit_manager():
            st.divider()
            st.subheader("Credit Management Tools")
            
            # Add credits to student
            col_add1, col_add2, col_add3 = st.columns(3)
            
            # Validate credit_data and 'Name' column before using
            if 'credit_data' in st.session_state and isinstance(st.session_state.credit_data, pd.DataFrame):
                if not st.session_state.credit_data.empty and 'Name' in st.session_state.credit_data.columns:
                    # Convert pandas Series to a Python list (KEY FIX 1)
                    student_names = st.session_state.credit_data['Name'].tolist()
                else:
                    st.error("Credit data is empty or missing 'Name' column")
                    student_names = []  # Empty list as fallback
            else:
                st.error("Credit data not found in system")
                student_names = []  # Empty list as fallback
            
            with col_add1:
                student_to_credit = st.selectbox(
                    "Select Student",
                    student_names,  # Now using a proper list
                    key="student_credit_select",
                    # Check if list is empty using len() (KEY FIX 2)
                    disabled=len(student_names) == 0  # Disable if no names available
                )
            with col_add2:
                credit_amount = st.number_input(
                    "Credit Amount",
                    min_value=10,
                    step=10,
                    key="credit_amount"
                )
            with col_add3:
                if st.button("Add Credits", key="add_credit_btn"):
                    idx = st.session_state.credit_data[st.session_state.credit_data['Name'] == student_to_credit].index[0]
                    st.session_state.credit_data.at[idx, 'Total_Credits'] += credit_amount
                    success, msg = save_data(connect_gsheets())
                    if success:
                        st.success(f"Added {credit_amount} credits to {student_to_credit}")
                    else:
                        st.error(msg)
            
            # Redeem credits for reward
            st.subheader("Redeem Credits")
            col_red1, col_red2, col_red3 = st.columns(3)
            
            # Validate credit_data and 'Name' column before using
            if 'credit_data' in st.session_state and isinstance(st.session_state.credit_data, pd.DataFrame):
                if not st.session_state.credit_data.empty and 'Name' in st.session_state.credit_data.columns:
                    # Convert pandas Series to Python list (critical fix)
                    redeem_student_names = st.session_state.credit_data['Name'].tolist()
                else:
                    st.error("Credit data is empty or missing 'Name' column")
                    redeem_student_names = []  # Empty list fallback
            else:
                st.error("Credit data not found in system")
                redeem_student_names = []  # Empty list fallback
            
            with col_red1:
                student_redeem = st.selectbox(
                    "Student Redeeming",
                    redeem_student_names,  # Use the converted list
                    key="student_redeem_select",
                    # Proper empty list check using len() (critical fix)
                    disabled=len(redeem_student_names) == 0
                )
            with col_red2:
                reward_selected = st.selectbox(
                    "Reward Selected",
                    st.session_state.reward_data['Reward'],
                    key="reward_select"
                )
            
            if student_redeem and reward_selected:
                with col_red3:
                    # Get cost and check availability
                    student_idx = st.session_state.credit_data[st.session_state.credit_data['Name'] == student_redeem].index[0]
                    available_credits = (st.session_state.credit_data.at[student_idx, 'Total_Credits'] - 
                                        st.session_state.credit_data.at[student_idx, 'RedeemedCredits'])
                    
                    reward_cost = st.session_state.reward_data[st.session_state.reward_data['Reward'] == reward_selected]['Cost'].values[0]
                    reward_stock = st.session_state.reward_data[st.session_state.reward_data['Reward'] == reward_selected]['Stock'].values[0]
                    
                    if available_credits < reward_cost:
                        st.error(f"Not enough credits! Needs {reward_cost}, has {available_credits}")
                    elif reward_stock <= 0:
                        st.error("This reward is out of stock!")
                    elif st.button("Process Redemption", key="redeem_btn"):
                        # Update student credits
                        st.session_state.credit_data.at[student_idx, 'RedeemedCredits'] += reward_cost
                        
                        # Update reward stock
                        reward_idx = st.session_state.reward_data[st.session_state.reward_data['Reward'] == reward_selected].index[0]
                        st.session_state.reward_data.at[reward_idx, 'Stock'] -= 1
                        
                        success, msg = save_data(connect_gsheets())
                        if success:
                            st.success(f"{student_redeem} successfully redeemed {reward_selected}")
                        else:
                            st.error(msg)
            
            # Import credits from Excel
            if st.button("Import Credit Members from Excel", key="import_credits_btn"):
                success, msg = import_credit_members_from_excel()
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

    # ------------------------------
    # Tab 6: SCIS AI Tools
    # ------------------------------
    with tab6:
        st.subheader("AI-Powered Student Council Tools")
        
        # Meeting agenda generator
        st.subheader("📋 Meeting Agenda Generator")
        meeting_topic = st.text_input("Meeting Topic", "End of Semester Events Planning")
        attendees = st.text_input("Attendees (comma separated)", "Council President, Activity Coordinator, Treasurer")
        duration = st.slider("Meeting Duration (minutes)", 30, 120, 60)
        
        if st.button("Generate Agenda"):
            with st.spinner("Generating meeting agenda..."):
                # In a real implementation, this would call an AI API
                agenda_items = [
                    f"Welcome and introductions (5 min)",
                    f"Approval of previous meeting minutes (5 min)",
                    f"Main discussion: {meeting_topic} ({(duration-20)*0.6:.0f} min)",
                    f"Budget considerations ({(duration-20)*0.2:.0f} min)",
                    f"Action items and responsibilities ({(duration-20)*0.1:.0f} min)",
                    f"Next meeting planning (5 min)",
                    f"Adjournment (5 min)"
                ]
                
                st.success("Agenda generated successfully!")
                st.markdown("### Proposed Agenda:")
                for item in agenda_items:
                    st.markdown(f"- {item}")
                
                # Save to calendar option
                if st.button("Add to Calendar"):
                    meeting_date = st.date_input("Select Meeting Date", date.today() + timedelta(days=7))
                    meeting_time = st.time_input("Select Meeting Time", datetime.time(15, 0))
                    
                    date_str = meeting_date.strftime("%Y-%m-%d")
                    event_details = f"{meeting_topic} - {', '.join(attendees.split(',')[:3])}{' + more' if len(attendees.split(',')) > 3 else ''}"
                    st.session_state.calendar_events[date_str] = event_details
                    save_data(connect_gsheets())
                    st.success(f"Meeting added to calendar for {meeting_date.strftime('%b %d, %Y')}")
        
        # Event idea generator
        st.subheader("💡 Event Idea Generator")
        event_type = st.selectbox("Event Type", ["Fundraiser", "Community Service", "School Spirit", "Educational", "Social"])
        target_group = st.selectbox("Target Group", ["Entire School", "Student Council", "Freshmen", "Seniors", "Parents"])
        budget_level = st.selectbox("Budget Level", ["Low ($0-$50)", "Medium ($50-$200)", "High ($200+)"])
        
        if st.button("Generate Event Ideas"):
            with st.spinner("Generating event ideas..."):
                # Sample ideas based on selections
                ideas = []
                if event_type == "Fundraiser" and budget_level == "Low ($0-$50)":
                    ideas = [
                        "Penny War - Compete between classes to collect the most pennies",
                        "Dress Down Day - $2 donation to wear casual clothes",
                        "Bake Sale - Students bring homemade treats to sell",
                        "Movie Night - $5 admission with free popcorn"
                    ]
                elif event_type == "School Spirit" and target_group == "Entire School":
                    ideas = [
                        "Spirit Week - Themed dress days leading up to a big game",
                        "School Color Day - Everyone wears the school colors",
                        "Talent Show - Showcase student talents with admission fee",
                        "Homecoming Parade - Class floats and spirit competition"
                    ]
                else:
                    ideas = [
                        f"{event_type} Fair - Booths and activities for {target_group.lower()}",
                        f"Guest Speaker Series - Focus on {event_type.lower()} topics",
                        f"Workshop Day - Interactive sessions about {event_type.lower()}",
                        f"Field Day - Competitive games with {event_type.lower()} themes"
                    ]
                
                st.success("Event ideas generated!")
                for i, idea in enumerate(ideas, 1):
                    st.markdown(f"{i}. {idea}")
                
                # Add to financial planning button
                selected_idea = st.selectbox("Add to Financial Planning?", ["None"] + ideas)
                if selected_idea != "None" and st.button("Add to Financials"):
                    est_cost = 50 if budget_level.startswith("Low") else 150 if budget_level.startswith("Medium") else 300
                    est_raised = est_cost * 3 if event_type == "Fundraiser" else 0
                    
                    new_event = pd.DataFrame({
                        'Event Name': [selected_idea[:30] + "..."],
                        'Total Funds Raised': [est_raised],
                        'Cost': [est_cost],
                        'Staff Many Or Not': [1 if target_group == "Entire School" else 0],
                        'Preparation Time': [0],
                        'Rating': [7.5]
                    })
                    
                    st.session_state.occasional_events = pd.concat(
                        [st.session_state.occasional_events, new_event], ignore_index=True
                    )
                    save_data(connect_gsheets())
                    st.success("Event added to Financial Planning!")

    # ------------------------------
    # Tab 7: Money Transfers
    # ------------------------------
    with tab7:
        st.subheader("Financial Transactions")
        
        # Display transaction history
        st.subheader("Transaction History")
        if st.session_state.money_data.empty:
            st.info("No financial transactions recorded yet.")
        else:
            # Sort by date (newest first)
            st.session_state.money_data['Date'] = pd.to_datetime(st.session_state.money_data['Date'])
            st.session_state.money_data = st.session_state.money_data.sort_values('Date', ascending=False)
            
            st.dataframe(
                st.session_state.money_data,
                use_container_width=True,
                column_config={
                    "Amount": st.column_config.NumberColumn("Amount ($)"),
                    "Date": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD")
                }
            )
            
            # Financial summary
            col_income, col_expense, col_balance = st.columns(3)
            income = st.session_state.money_data[st.session_state.money_data['Amount'] > 0]['Amount'].sum()
            expense = st.session_state.money_data[st.session_state.money_data['Amount'] < 0]['Amount'].sum()
            balance = income + expense
            
            with col_income:
                st.metric("Total Income", f"${income:,.2f}")
            with col_expense:
                st.metric("Total Expenses", f"${expense:,.2f}")
            with col_balance:
                st.metric("Current Balance", f"${balance:,.2f}")
            
            # Visualization
            fig, ax = plt.subplots(figsize=(10, 6))
            monthly_data = st.session_state.money_data.resample('M', on='Date')['Amount'].sum().reset_index()
            monthly_data['Month'] = monthly_data['Date'].dt.strftime('%b %Y')
            ax.bar(monthly_data['Month'], monthly_data['Amount'], color=np.where(monthly_data['Amount'] > 0, 'green', 'red'))
            ax.set_title('Monthly Financial Overview')
            plt.xticks(rotation=45, ha='right')
            st.pyplot(fig)
        
        # Record new transaction (admin only)
        if is_admin():
            st.divider()
            st.subheader("Record New Transaction")
            
            col1, col2 = st.columns(2)
            with col1:
                amount = st.number_input("Amount", value=100.0, step=10.0)
                is_expense = st.checkbox("This is an expense (negative amount)")
                if is_expense:
                    amount = -abs(amount)
            
            with col2:
                description = st.text_input("Description", "Fundraiser proceeds")
                transaction_date = st.date_input("Date", date.today())
            
            handled_by = st.text_input("Handled By", st.session_state.user)
            
            if st.button("Record Transaction"):
                new_transaction = pd.DataFrame({
                    'Amount': [amount],
                    'Description': [description],
                    'Date': [transaction_date.strftime("%Y-%m-%d")],
                    'Handled By': [handled_by]
                })
                
                st.session_state.money_data = pd.concat(
                    [st.session_state.money_data, new_transaction], ignore_index=True
                )
                
                success, msg = save_data(connect_gsheets())
                if success:
                    st.success("Transaction recorded successfully!")
                else:
                    st.error(msg)
            
            # Export financial report
            if not st.session_state.money_data.empty and st.button("Export Financial Report"):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    st.session_state.money_data.to_excel(writer, sheet_name='Transactions', index=False)
                    
                    # Add summary sheet
                    summary_data = {
                        'Category': ['Total Income', 'Total Expenses', 'Current Balance'],
                        'Amount': [income, expense, balance]
                    }
                    pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
                
                output.seek(0)
                st.download_button(
                    label="Download Excel Report",
                    data=output,
                    file_name=f"financial_report_{date.today().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # ------------------------------
    # Tab 8: Groups
    # ------------------------------
    with tab8:
        group_management_ui()
        # Add diagnostic tools for admins
        if is_admin():
            group_diagnostics()
            show_group_codes()

if 'attendance' not in st.session_state:
    # Include "Date" as a column (with appropriate datetime values)
    st.session_state.attendance = pd.DataFrame(
        columns=["Name", "Date", "Status"],  # "Date" is required
        data=[
            # Example row
            ["John Doe", datetime.now().date(), "Present"]
        ]
    )

if 'occasional_events' not in st.session_state or st.session_state.occasional_events.empty:
    st.session_state.occasional_events = pd.DataFrame(columns=['EventName', 'Date', 'Description', 'Cost'])  # Adjust columns as needed

if 'credit_data' not in st.session_state or st.session_state.credit_data.empty:
    st.session_state.credit_data = pd.DataFrame(columns=['Name', 'Date', 'Credits', 'Reason'])  # Adjust columns as needed

if 'scheduled_events' not in st.session_state or st.session_state.scheduled_events.empty:
    st.session_state.scheduled_events = pd.DataFrame(columns=['EventName', 'Date', 'Location', 'Organizer'])  # Adjust columns as needed

if 'money_data' not in st.session_state or st.session_state.money_data.empty:
    st.session_state.money_data = pd.DataFrame(columns=['Date', 'Amount', 'Category', 'Description'])  # Adjust columns as needed
# ------------------------------
# Main Application Flow
# ------------------------------
def main():
    # Initialize files and session state
    initialize_files()
    initialize_session_state()
    
    # Load group data
    load_groups_data()
    
    # Connect to Google Sheets
    sheet = connect_gsheets()
    
    # Load application data if not initialized
    if not st.session_state.initialized:
        success, msg = load_data(sheet)
        if not success:
            st.warning(f"Using default data: {msg}")
            safe_init_data()
        st.session_state.initialized = True
    
    # Check login status
    if st.session_state.user:
        render_main_app()
    else:
        # Show login and signup forms
        login_success = render_login_form()
        if not login_success:
            render_signup_form()
            render_welcome_screen()

if __name__ == "__main__":
    main()





























