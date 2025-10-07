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

# ------------------------------
# App Configuration & Setup
# ------------------------------
st.set_page_config(
    page_title="Student Council Management System",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# Global Constants & Variables
# ------------------------------
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
    """Establish connection to Google Sheets using service account credentials"""
    try:
        if "google_sheets" not in st.secrets:
            st.error("Google Sheets configuration not found")
            return None
            
        secrets = st.secrets["google_sheets"]
        
        # Validate required secrets
        required_secrets = ["service_account_email", "private_key_id", "private_key", "sheet_url"]
        for secret in required_secrets:
            if secret not in secrets or not secrets[secret]:
                st.error(f"Missing required configuration: {secret}")
                return None
        
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
        
        # Authenticate
        try:
            client = gspread.service_account_from_dict(creds)
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            return None
        
        # Open spreadsheet
        try:
            sheet = client.open_by_url(secrets["sheet_url"])
        except gspread.exceptions.SpreadsheetNotFound:
            st.error("Spreadsheet not found. Please check the URL.")
            return None
        except Exception as e:
            st.error(f"Failed to open spreadsheet: {str(e)}")
            return None
        
        # Create required worksheets if missing
        required_worksheets = [
            "users", "attendance", "credit_data", "reward_data",
            "scheduled_events", "occasional_events", "money_data",
            "calendar_events", "announcements", "config",
            "groups", "group_leaders", "group_earnings",
            "reimbursement_requests", "event_approval_requests",
            "activity_log"
        ]
        
        existing_sheets = [ws.title for ws in sheet.worksheets()]
        for ws_name in required_worksheets:
            if ws_name not in existing_sheets:
                try:
                    sheet.add_worksheet(title=ws_name, rows="2000", cols="50")
                    st.success(f"Created missing worksheet: {ws_name}")
                    
                    # Initialize headers for new worksheets
                    if ws_name == "activity_log":
                        ws = sheet.worksheet(ws_name)
                        ws.append_row(["Timestamp", "User", "Action", "Details", "IP Address"])
                except Exception as e:
                    st.warning(f"Could not create worksheet {ws_name}: {str(e)}")
        
        return sheet
    
    except Exception as e:
        st.error(f"Connection failed: {str(e)}")
        return None

# ------------------------------
# Session State Initialization
# ------------------------------
def initialize_session_state():
    """Initialize all required session state variables"""
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
        "sidebar_collapsed": False
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
        "activity_log": pd.DataFrame()
    }
    
    # Initialize variables if missing
    all_vars = {**user_session_vars,** ui_state_vars, **data_storage_vars}
    for key, default_value in all_vars.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def generate_group_code(group):
    """Generate a random group code"""
    prefix = group.replace("G", "GRP")
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{random_suffix}"

# ------------------------------
# Default Data Initialization
# ------------------------------
def initialize_default_data():
    """Set up default data for all system components"""
    # Default members
    members = [
        "Ahaan", "Bella", "Ella",  # Admins
        "Alice", "Bob", "Charlie", "Diana", "Evan",  # Regular members
        "Frank", "Grace", "Henry", "Ivy", "Jack",
        "Kate", "Liam", "Mia", "Noah", "Olivia"
    ]
    
    # Initialize attendance with multiple meetings
    st.session_state.meeting_names = [
        "First Semester Kickoff",
        "Event Planning Session",
        "Budget Review Meeting",
        "Monthly General Meeting",
        "Community Outreach Discussion"
    ]
    
    # Create attendance data
    att_data = {"Name": members}
    for meeting in st.session_state.meeting_names:
        att_data[meeting] = [random.choice([True, False]) for _ in range(len(members))]
    st.session_state.attendance = pd.DataFrame(att_data)
    
    # Initialize credit data
    st.session_state.credit_data = pd.DataFrame({
        "Name": members,
        "Total_Credits": [random.randint(100, 500) for _ in members],
        "RedeemedCredits": [random.randint(0, 100) for _ in members],
        "Last_Updated": [datetime.now().strftime("%Y-%m-%d") for _ in members]
    })
    
    # Initialize reward catalog
    st.session_state.reward_data = pd.DataFrame([
        {"Reward": "Bubble Tea", "Cost": 50, "Stock": 15, "Category": "Food"},
        {"Reward": "Chips & Soda", "Cost": 30, "Stock": 25, "Category": "Food"},
        {"Reward": "Café Coupon", "Cost": 80, "Stock": 10, "Category": "Food"},
        {"Reward": "Movie Ticket", "Cost": 120, "Stock": 5, "Category": "Entertainment"},
        {"Reward": "Gift Card ($10)", "Cost": 200, "Stock": 8, "Category": "Gift"},
        {"Reward": "School Merchandise", "Cost": 150, "Stock": 12, "Category": "Merchandise"},
        {"Reward": "Study Kit", "Cost": 90, "Stock": 10, "Category": "Academic"},
        {"Reward": "Art Supplies", "Cost": 110, "Stock": 7, "Category": "Creative"}
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
            "Next Scheduled": (date.today() + timedelta(days=16)).strftime("%Y-%m-%d"),
            "Organizer": "Ahaan"
        },
        {
            "Event Name": "Tutoring Sessions",
            "Funds Per Event": 0,
            "Frequency Per Month": 4,
            "Total Funds": 0,
            "Responsible Group": "G3",
            "Last Held": (date.today() - timedelta(days=3)).strftime("%Y-%m-%d"),
            "Next Scheduled": (date.today() + timedelta(days=4)).strftime("%Y-%m-%d"),
            "Organizer": "Ella"
        },
        {
            "Event Name": "School Newspaper",
            "Funds Per Event": 150,
            "Frequency Per Month": 2,
            "Total Funds": 300,
            "Responsible Group": "G5",
            "Last Held": (date.today() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "Next Scheduled": (date.today() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "Organizer": "Bob"
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
            "Responsible Group": "G2",
            "Date Held": (date.today() - timedelta(days=45)).strftime("%Y-%m-%d"),
            "Attendance": 150
        },
        {
            "Event Name": "Charity Run",
            "Total Funds Raised": 3500,
            "Cost": 800,
            "Staff Many Or Not": "Yes",
            "Preparation Time": 30,
            "Rating": 4.8,
            "Responsible Group": "G4",
            "Date Held": (date.today() - timedelta(days=60)).strftime("%Y-%m-%d"),
            "Attendance": 220
        }
    ])
    
    # Initialize financial data
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
    
    # Initialize group earnings
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
                "Fundraiser Event", "Community Outreach",
                "Volunteer Training"
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
        },
        {
            "title": "New Reward Options",
            "text": "Several new rewards have been added to the catalog. Check the Credits & Rewards tab to see what's available.",
            "time": (today - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
            "author": "Ella",
            "group": ""  # All groups
        }
    ]
    
    # Initialize system configuration
    st.session_state.config = {
        "show_signup": True,
        "max_reimbursement": 500,
        "max_event_budget": 2000,
        "meeting_reminder_days": 2,
        "auto_approve_small_purchases": True,
        "small_purchase_limit": 100
    }
    
    # Initialize users with proper roles
    st.session_state.users = {}
    
    # Add admins: Ahaan, Bella, Ella
    for admin in ["Ahaan", "Bella", "Ella"]:
        # Assign to first three groups
        group_index = ["Ahaan", "Bella", "Ella"].index(admin)
        group = GROUP_NAMES[group_index] if group_index < len(GROUP_NAMES) else "G1"
        
        st.session_state.users[admin] = {
            "password_hash": bcrypt.hashpw(f"{admin.lower()}@2023".encode(), bcrypt.gensalt()).decode(),
            "role": "admin",
            "created_at": datetime.now().isoformat(),
            "last_login": (today - timedelta(days=random.randint(1, 7))).isoformat() if random.choice([True, False]) else None,
            "group": group
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
            "group": user_group
        }

# ------------------------------
# Data Management - Google Sheets Operations
# ------------------------------
def get_worksheet_data(sheet, worksheet_name):
    """Retrieve data from a specific worksheet"""
    try:
        ws = sheet.worksheet(worksheet_name)
        return ws.get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        st.warning(f"Worksheet {worksheet_name} not found")
        return []
    except Exception as e:
        st.warning(f"Error retrieving data from {worksheet_name}: {str(e)}")
        return []

def save_all_data(sheet):
    """Save all application data to Google Sheets"""
    if not sheet:
        return False, "No Google Sheets connection available"
    
    try:
        success_count = 0
        error_messages = []
        
        # 1. Save users
        try:
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
            success_count += 1
        except Exception as e:
            error_messages.append(f"Users: {str(e)}")
        
        # 2. Save attendance
        try:
            att_ws = sheet.worksheet("attendance")
            att_data = [st.session_state.attendance.columns.tolist()] + st.session_state.attendance.values.tolist()
            att_ws.clear()
            att_ws.update(att_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Attendance: {str(e)}")
        
        # 3. Save credit data
        try:
            credit_ws = sheet.worksheet("credit_data")
            credit_data = [st.session_state.credit_data.columns.tolist()] + st.session_state.credit_data.values.tolist()
            credit_ws.clear()
            credit_ws.update(credit_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Credit data: {str(e)}")
        
        # 4. Save reward data
        try:
            reward_ws = sheet.worksheet("reward_data")
            reward_data = [st.session_state.reward_data.columns.tolist()] + st.session_state.reward_data.values.tolist()
            reward_ws.clear()
            reward_ws.update(reward_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Reward data: {str(e)}")
        
        # 5. Save scheduled events
        try:
            scheduled_ws = sheet.worksheet("scheduled_events")
            scheduled_data = [st.session_state.scheduled_events.columns.tolist()] + st.session_state.scheduled_events.values.tolist()
            scheduled_ws.clear()
            scheduled_ws.update(scheduled_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Scheduled events: {str(e)}")
        
        # 6. Save occasional events
        try:
            occasional_ws = sheet.worksheet("occasional_events")
            occasional_data = [st.session_state.occasional_events.columns.tolist()] + st.session_state.occasional_events.values.tolist()
            occasional_ws.clear()
            occasional_ws.update(occasional_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Occasional events: {str(e)}")
        
        # 7. Save money transactions
        try:
            money_ws = sheet.worksheet("money_data")
            money_data = [st.session_state.money_data.columns.tolist()] + st.session_state.money_data.values.tolist()
            money_ws.clear()
            money_ws.update(money_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Money data: {str(e)}")
        
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
        
        # 11. Save groups
        try:
            groups_ws = sheet.worksheet("groups")
            groups_data = [["group", "members"]]
            for group, members in st.session_state.groups.items():
                groups_data.append([group, ", ".join(members)])
            # Add group codes
            groups_data.append(["group_codes", str(st.session_state.group_codes)])
            groups_ws.clear()
            groups_ws.update(groups_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Groups: {str(e)}")
        
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
        
        # 13. Save group earnings
        try:
            earnings_ws = sheet.worksheet("group_earnings")
            earnings_data = [st.session_state.group_earnings.columns.tolist()] + st.session_state.group_earnings.values.tolist()
            earnings_ws.clear()
            earnings_ws.update(earnings_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Group earnings: {str(e)}")
        
        # 14. Save reimbursement requests
        try:
            reimburse_ws = sheet.worksheet("reimbursement_requests")
            reimburse_data = [st.session_state.reimbursement_requests.columns.tolist()] + st.session_state.reimbursement_requests.values.tolist()
            reimburse_ws.clear()
            reimburse_ws.update(reimburse_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Reimbursement requests: {str(e)}")
        
        # 15. Save event approval requests
        try:
            events_ws = sheet.worksheet("event_approval_requests")
            events_data = [st.session_state.event_approval_requests.columns.tolist()] + st.session_state.event_approval_requests.values.tolist()
            events_ws.clear()
            events_ws.update(events_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Event requests: {str(e)}")
        
        # 16. Save activity log
        try:
            activity_ws = sheet.worksheet("activity_log")
            activity_data = [st.session_state.activity_log.columns.tolist()] + st.session_state.activity_log.values.tolist()
            activity_ws.clear()
            activity_ws.update(activity_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Activity log: {str(e)}")
        
        total_worksheet = 16
        if success_count == total_worksheet:
            return True, "All data saved successfully"
        elif success_count > 0:
            return False, f"Partial save completed. {success_count}/{total_worksheet} updated. Errors: {', '.join(error_messages[:3])}"
        else:
            return False, f"Failed to save data. Errors: {', '.join(error_messages[:3])}"
    
    except Exception as e:
        return False, f"Error during save: {str(e)}"

def load_all_data(sheet):
    """Load all application data from Google Sheets"""
    if not sheet:
        return False, "No Google Sheets connection available"
    
    try:
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
                        "group": row.get("group", "")
                    }
            success_count += 1
        except Exception as e:
            error_messages.append(f"Users: {str(e)}")
        
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
        
        # 3. Load credit data
        try:
            credit_data = get_worksheet_data(sheet, "credit_data")
            st.session_state.credit_data = pd.DataFrame(credit_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Credit data: {str(e)}")
        
        # 4. Load reward data
        try:
            reward_data = get_worksheet_data(sheet, "reward_data")
            st.session_state.reward_data = pd.DataFrame(reward_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Reward data: {str(e)}")
        
        # 5. Load scheduled events
        try:
            scheduled_data = get_worksheet_data(sheet, "scheduled_events")
            st.session_state.scheduled_events = pd.DataFrame(scheduled_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Scheduled events: {str(e)}")
        
        # 6. Load occasional events
        try:
            occasional_data = get_worksheet_data(sheet, "occasional_events")
            st.session_state.occasional_events = pd.DataFrame(occasional_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Occasional events: {str(e)}")
        
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
        
        # 10. Load configuration
        try:
            config_data = get_worksheet_data(sheet, "config")
            st.session_state.config = {"show_signup": True}
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
                    st.session_state.config[row["key"]] = value
            success_count += 1
        except Exception as e:
            error_messages.append(f"Config: {str(e)}")
        
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
                        pass  # Keep default codes
            
            st.session_state.groups = groups
            st.session_state.group_codes = group_codes
            success_count += 1
        except Exception as e:
            error_messages.append(f"Groups: {str(e)}")
        
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
        
        # 16. Load activity log
        try:
            activity_data = get_worksheet_data(sheet, "activity_log")
            st.session_state.activity_log = pd.DataFrame(activity_data)
            success_count += 1
        except Exception as e:
            error_messages.append(f"Activity log: {str(e)}")
        
        # Check if we have critical data
        critical_data_missing = not st.session_state.users or st.session_state.attendance.empty
        
        total_worksheet = 16
        if critical_data_missing:
            return False, "Critical data (users or attendance) is missing"
        elif success_count == total_worksheet:
            return True, "All data loaded successfully"
        elif success_count > 0:
            return True, f"Loaded most data. {success_count}/{total_worksheet} loaded. Some features may be limited."
        else:
            return False, f"Failed to load data. Errors: {', '.join(error_messages[:3])}"
    
    except Exception as e:
        return False, f"Error during load: {str(e)}"

# ------------------------------
# User Authentication & Management
# ------------------------------
def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against a hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except:
        return False

def validate_password(password):
    """Validate password strength"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"

def create_user(username, password, group_code):
    """Create a new user with group assignment via code"""
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
        "group": group
    }
    
    # Add user to group
    if username not in st.session_state.groups[group]:
        st.session_state.groups[group].append(username)
        st.session_state.groups[group].sort()  # Keep sorted
    
    # Log activity
    log_activity(f"create_user", f"Created new user {username} in group {group}")
    
    return True, f"User {username} created successfully in {group}. You can now log in."

def update_user_password(username, current_password, new_password):
    """Update a user's password"""
    if username not in st.session_state.users:
        return False, "User not found"
    
    # Verify current password
    if not verify_password(current_password, st.session_state.users[username]["password_hash"]):
        return False, "Current password is incorrect"
    
    # Validate new password
    pass_valid, pass_msg = validate_password(new_password)
    if not pass_valid:
        return False, pass_msg
    
    # Check if new password is different
    if verify_password(new_password, st.session_state.users[username]["password_hash"]):
        return False, "New password must be different from current password"
    
    # Update password
    st.session_state.users[username]["password_hash"] = hash_password(new_password)
    
    # Log activity
    log_activity(f"update_password", f"Updated password for user {username}")
    
    return True, "Password updated successfully"

def render_login_signup():
    """Render login and signup forms"""
    st.title("Student Council Management System")
    
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
            else:
                # Failed login - user not found
                st.session_state.login_attempts += 1
                remaining_attempts = 5 - st.session_state.login_attempts
                st.error(f"Username not found. {remaining_attempts} attempt(s) remaining.")
        
        return False
    
    with signup_tab:
        if not st.session_state.config.get("show_signup", True):
            st.info("Signup is currently closed. Please contact an administrator.")
            return False
            
        st.subheader("Create New Account")
        
        new_username = st.text_input("Choose Username", key="new_username", placeholder="3+ characters")
        new_password = st.text_input("Create Password", type="password", key="new_password", 
                                    placeholder="8+ chars with uppercase, number and special char")
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
                st.error("Please fill in all required fields")
                return False
            
            if new_password != confirm_password:
                st.error("Passwords do not match. Please try again.")
                return False
            
            # Create user
            success, msg = create_user(new_username, new_password, group_code)
            if success:
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(f"{msg}")
            else:
                st.error(msg)
    
    with forgot_tab:
        st.subheader("Reset Password")
        st.write("Enter your username to request a password reset.")
        
        username = st.text_input("Username", key="forgot_username")
        
        if st.button("Request Password Reset", key="request_reset"):
            if not username:
                st.error("Please enter your username")
                return False
                
            if username not in st.session_state.users:
                st.error("Username not found")
                return False
            
            # Log request
            log_activity("password_reset_request", f"Password reset requested for {username}")
            
            # Notify admins
            admin_users = [u for u, details in st.session_state.users.items() if details["role"] in ["admin", "creator"]]
            st.success("Password reset request submitted. An administrator will process your request.")
    
    return False

# ------------------------------
# Group Management Functions
# ------------------------------
def move_user_between_groups(username, from_group, to_group):
    """Move a user from one group to another"""
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
    st.session_state.groups[from_group].sort()
    
    # Add to new group if not already present
    if username not in st.session_state.groups[to_group]:
        st.session_state.groups[to_group].append(username)
        st.session_state.groups[to_group].sort()
    
    # Update user's group in their profile
    if username in st.session_state.users:
        st.session_state.users[username]["group"] = to_group
        
        # If user was a leader of old group, remove them
        if st.session_state.group_leaders.get(from_group) == username:
            # Promote another member or clear
            if st.session_state.groups[from_group]:
                new_leader = st.session_state.groups[from_group][0]
                st.session_state.group_leaders[from_group] = new_leader
            else:
                st.session_state.group_leaders[from_group] = ""
    
    # Log activity
    log_activity(f"move_user_group", f"Moved {username} from {from_group} to {to_group}")
    
    return True, f"Moved {username} from {from_group} to {to_group} successfully"

def set_group_leader(group, username):
    """Set a user as group leader"""
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
    
    # Demote previous leader if they exist and are different
    if prev_leader and prev_leader != username and prev_leader in st.session_state.users:
        if st.session_state.users[prev_leader]["role"] == "group_leader":
            st.session_state.users[prev_leader]["role"] = "user"
    
    return True, f"Successfully set {username} as leader of {group}"

def regenerate_group_code(group):
    """Generate a new code for a group"""
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    # Generate new code
    new_code = generate_group_code(group)
    st.session_state.group_codes[group] = new_code
    
    # Log activity
    log_activity(f"regenerate_group_code", f"Regenerated code for {group}")
    
    return True, f"New code for {group}: {new_code}"

def record_group_earning(group, amount, description):
    """Record earnings for a group"""
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    if amount <= 0:
        return False, "Amount must be greater than zero"
    
    if not description or len(description) < 5:
        return False, "Please provide a meaningful description"
    
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
    log_activity(f"record_group_earning", f"Recorded ${amount} earning for {group}")
    
    return True, "Earnings recorded successfully and are pending verification"

def verify_group_earning(earning_index, verify_status, notes=""):
    """Verify or reject a group's earnings submission"""
    if verify_status not in ["Verified", "Rejected"]:
        return False, "Status must be either Verified or Rejected"
    
    if earning_index < 0 or earning_index >= len(st.session_state.group_earnings):
        return False, "Invalid earning record specified"
    
    # Update the record
    earning = st.session_state.group_earnings.iloc[earning_index]
    st.session_state.group_earnings.at[earning_index, "Verified"] = verify_status
    st.session_state.group_earnings.at[earning_index, "Verified By"] = st.session_state.user
    
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
    
    return True, f"Earnings {verify_status.lower()} successfully"

# ------------------------------
# Request Management Functions
# ------------------------------
def submit_reimbursement_request(group, requester, amount, purpose):
    """Submit a new reimbursement request"""
    # Validate inputs
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    if amount <= 0:
        return False, "Reimbursement amount must be greater than zero"
    
    max_amount = st.session_state.config.get("max_reimbursement", REIMBURSEMENT_LIMIT)
    if amount > max_amount:
        return False, f"Amount exceeds maximum reimbursement limit of ${max_amount}."
    
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
    
    return True, f"Reimbursement request {request_id} submitted successfully"

def submit_event_approval_request(group, requester, event_name, description, 
                                 proposed_date, budget, expected_attendance):
    """Submit a new event approval request"""
    # Validate inputs
    if group not in GROUP_NAMES:
        return False, "Invalid group specified"
    
    if not event_name or len(event_name) < 3:
        return False, "Please provide a valid event name"
    
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
        st.warning(f"This budget exceeds the standard limit of ${max_budget}. Special approval required.")
    
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
    
    return True, f"Event approval request {request_id} submitted successfully"

def update_request_status(request_type, request_id, new_status, admin_notes=""):
    """Update status of a reimbursement or event request"""
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
                "Next Scheduled": event_date,
                "Organizer": request_data["Requester"]
            }])
            
            st.session_state.scheduled_events = pd.concat(
                [st.session_state.scheduled_events, new_event], ignore_index=True
            )
    
    # Log activity
    log_activity(f"update_{request_type}_status", f"Updated {request_type} request {request_id} to {new_status}")
    
    return True, f"Successfully updated {request_type} request {request_id} to {new_status}"

# ------------------------------
# Activity Logging
# ------------------------------
def log_activity(action, details):
    """Log user actions for audit purposes"""
    new_entry = pd.DataFrame([{
        "Timestamp": datetime.now().isoformat(),
        "User": st.session_state.user or "system",
        "Action": action,
        "Details": details,
        "IP Address": "unknown"  # In a real app, get from request
    }])
    
    st.session_state.activity_log = pd.concat(
        [st.session_state.activity_log, new_entry], ignore_index=True
    )
    
    # Keep log size manageable
    if len(st.session_state.activity_log) > 10000:
        st.session_state.activity_log = st.session_state.activity_log.tail(10000).reset_index(drop=True)

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
    """Check if current user is a group leader"""
    if not st.session_state.user:
        return False
        
    if group:
        return st.session_state.group_leaders.get(group) == st.session_state.user
    else:
        # Check if user is leader of any group
        return st.session_state.user in st.session_state.group_leaders.values()

def can_access_group(group):
    """Check if current user can access a specific group's data"""
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
    """Render application header with user info"""
    col_title, col_user = st.columns([3, 1])
    
    with col_title:
        st.title("Student Council Management System")
    
    with col_user:
        if st.session_state.user:
            st.write(f"Logged in as: **{st.session_state.user}**")
            st.write(f"Role: **{st.session_state.role.title()}**")
            st.write(f"Group: **{st.session_state.current_group or 'N/A'}**")

def render_sidebar():
    """Render navigation sidebar with role-based options"""
    with st.sidebar:
        st.subheader("Navigation")
        
        # Core navigation items for all users
        nav_items = {
            "Dashboard": "dashboard",
            "Meetings & Attendance": "attendance",
            "Events": "events",
            "Finances": "finances",
            "Credits & Rewards": "credits"
        }
        
        # Add group leader specific items
        if is_group_leader():
            nav_items["Group Management"] = "group_management"
            nav_items["Submit Requests"] = "submit_requests"
        
        # Add admin specific items
        if is_admin():
            nav_items["Admin Dashboard"] = "admin_dashboard"
            nav_items["User Management"] = "user_management"
            nav_items["Approve Requests"] = "approve_requests"
            nav_items["System Configuration"] = "configuration"
        
        # Create navigation buttons
        for item, key in nav_items.items():
            if st.button(item, key=f"nav_{key}", use_container_width=True):
                st.session_state.active_tab = key
                st.rerun()
        
        # Add logout button
        if st.button("Logout", key="logout_btn", use_container_width=True, type="secondary"):
            log_activity("logout", f"User {st.session_state.user} logged out")
            # Clear user session data
            st.session_state.user = None
            st.session_state.role = None
            st.session_state.current_group = None
            st.session_state.notification_count = 0
            st.session_state.unread_notifications = []
            st.rerun()

def render_dashboard():
    """Render main dashboard with overview information"""
    st.header("Dashboard Overview")
    
    # Show announcements first
    st.subheader("Latest Announcements")
    for ann in st.session_state.announcements[:3]:  # Show top 3
        # Only show if for all groups or user's group
        if not ann["group"] or ann["group"] == st.session_state.current_group:
            with st.expander(f"{ann['title']} - {ann['author']} ({ann['time'][:10]})"):
                st.write(ann["text"])
    
    # Quick stats in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Your Credits", 
                 st.session_state.credit_data[st.session_state.credit_data["Name"] == st.session_state.user]["Total_Credits"].values[0] 
                 if not st.session_state.credit_data.empty and st.session_state.user in st.session_state.credit_data["Name"].values 
                 else 0)
    
    with col2:
        # Calculate meeting attendance percentage
        if st.session_state.user in st.session_state.attendance["Name"].values:
            user_attendance = st.session_state.attendance[st.session_state.attendance["Name"] == st.session_state.user]
            meetings = [col for col in user_attendance.columns if col != "Name"]
            attended = sum(user_attendance[meetings].iloc[0])
            percentage = round((attended / len(meetings)) * 100) if len(meetings) > 0 else 0
            st.metric("Meeting Attendance", f"{percentage}%")
        else:
            st.metric("Meeting Attendance", "N/A")
    
    with col3:
        # Count upcoming events
        today = date.today()
        upcoming_events = 0
        for event_date in st.session_state.calendar_events:
            try:
                event_dt = datetime.strptime(event_date, "%Y-%m-%d").date()
                if event_dt >= today:
                    # Check if event is for user's group or all groups
                    event_group = st.session_state.calendar_events[event_date][1]
                    if not event_group or event_group == st.session_state.current_group:
                        upcoming_events += 1
            except:
                continue
        st.metric("Upcoming Events", upcoming_events)
    
    with col4:
        # Count pending requests for user's group
        user_group = st.session_state.current_group
        pending_reimbursements = len(st.session_state.reimbursement_requests[
            (st.session_state.reimbursement_requests["Group"] == user_group) &
            (st.session_state.reimbursement_requests["Status"] == "Pending")
        ]) if not st.session_state.reimbursement_requests.empty else 0
        
        pending_events = len(st.session_state.event_approval_requests[
            (st.session_state.event_approval_requests["Group"] == user_group) &
            (st.session_state.event_approval_requests["Status"] == "Pending")
        ]) if not st.session_state.event_approval_requests.empty else 0
        
        st.metric("Pending Requests", pending_reimbursements + pending_events)
    
    # Recent activities
    st.subheader("Recent Activities")
    if not st.session_state.activity_log.empty:
        # Show last 10 activities relevant to user
        user_activities = st.session_state.activity_log[
            (st.session_state.activity_log["User"] == st.session_state.user) |
            (st.session_state.activity_log["Details"].str.contains(st.session_state.current_group))
        ].tail(10)
        
        if not user_activities.empty:
            st.dataframe(user_activities[["Timestamp", "User", "Action", "Details"]], use_container_width=True)
        else:
            st.info("No recent activities found")
    else:
        st.info("No activity logs available")

def render_attendance():
    """Render meetings and attendance page"""
    st.header("Meetings & Attendance")
    
    # Tab structure
    view_tab, record_tab = st.tabs(["View Attendance", "Record New Meeting"])
    
    with view_tab:
        # Filter by group if not admin
        if not is_admin():
            st.info(f"Showing attendance for your group: {st.session_state.current_group}")
            group_members = st.session_state.groups.get(st.session_state.current_group, [])
            filtered_attendance = st.session_state.attendance[
                st.session_state.attendance["Name"].isin(group_members)
            ]
        else:
            # Admin can filter by group
            filter_group = st.selectbox("Filter by group", ["All"] + GROUP_NAMES, key="attendance_filter")
            if filter_group != "All":
                group_members = st.session_state.groups.get(filter_group, [])
                filtered_attendance = st.session_state.attendance[
                    st.session_state.attendance["Name"].isin(group_members)
                ]
            else:
                filtered_attendance = st.session_state.attendance
        
        if filtered_attendance.empty:
            st.info("No attendance records found")
        else:
            st.dataframe(filtered_attendance, use_container_width=True)
            
            # Calculate and display attendance statistics
            st.subheader("Attendance Statistics")
            if len(st.session_state.meeting_names) > 0:
                # Overall attendance rate
                attendance_counts = {}
                for name in filtered_attendance["Name"]:
                    user_data = filtered_attendance[filtered_attendance["Name"] == name]
                    attended = sum(user_data[st.session_state.meeting_names].iloc[0])
                    total = len(st.session_state.meeting_names)
                    attendance_counts[name] = (attended / total) * 100 if total > 0 else 0
                
                # Sort by attendance rate
                sorted_attendance = sorted(attendance_counts.items(), key=lambda x: x[1], reverse=True)
                
                # Create chart
                fig, ax = plt.subplots(figsize=(10, 6))
                names = [item[0] for item in sorted_attendance[:10]]  # Top 10
                rates = [item[1] for item in sorted_attendance[:10]]
                
                ax.barh(names, rates, color='skyblue')
                ax.set_xlabel('Attendance Rate (%)')
                ax.set_title('Top 10 Attendance Rates')
                ax.set_xlim(0, 100)
                
                st.pyplot(fig)
    
    with record_tab:
        if not is_admin() and not is_group_leader():
            st.warning("Only administrators and group leaders can record new meetings")
            return
            
        st.subheader("Record New Meeting Attendance")
        meeting_name = st.text_input("Meeting Name", placeholder="e.g., Monthly General Meeting")
        meeting_date = st.date_input("Meeting Date", date.today())
        
        # Get relevant members based on user role
        if is_admin():
            selected_group = st.selectbox("Select Group", GROUP_NAMES, key="new_meeting_group")
            members = st.session_state.groups.get(selected_group, [])
        else:
            # Group leaders can only record for their group
            selected_group = st.session_state.current_group
            members = st.session_state.groups.get(selected_group, [])
            st.info(f"Recording attendance for {selected_group}")
        
        if not members:
            st.warning(f"No members found in {selected_group}")
            return
        
        # Create attendance checkboxes
        st.subheader("Attendance")
        attendance = {}
        cols = st.columns(3)  # 3 columns for checkboxes
        
        for i, member in enumerate(members):
            with cols[i % 3]:
                attendance[member] = st.checkbox(member, value=True)
        
        if st.button("Save Meeting Attendance", key="save_attendance"):
            if not meeting_name:
                st.error("Please enter a meeting name")
                return
            
            # Add new column to attendance dataframe
            if meeting_name not in st.session_state.attendance.columns:
                # For existing members, set their attendance
                st.session_state.attendance[meeting_name] = st.session_state.attendance["Name"].apply(
                    lambda x: attendance.get(x, False) if x in attendance else False
                )
                
                # Add any new members who might not be in the dataframe yet
                for member in members:
                    if member not in st.session_state.attendance["Name"].values:
                        new_row = {"Name": member}
                        for col in st.session_state.attendance.columns:
                            if col == "Name":
                                continue
                            new_row[col] = False  # Assume not attended previous meetings
                        new_row[meeting_name] = attendance.get(member, False)
                        st.session_state.attendance = pd.concat(
                            [st.session_state.attendance, pd.DataFrame([new_row])], 
                            ignore_index=True
                        )
            
            # Update meeting names list
            if meeting_name not in st.session_state.meeting_names:
                st.session_state.meeting_names.append(meeting_name)
            
            # Save to Google Sheets
            sheet = connect_gsheets()
            success, msg = save_all_data(sheet)
            if success:
                log_activity("record_attendance", f"Recorded attendance for meeting: {meeting_name}")
                st.success(f"Successfully recorded attendance for {meeting_name}")
            else:
                st.error(f"Failed to save attendance: {msg}")

def render_events():
    """Render events page with calendar and event lists"""
    st.header("Events Management")
    
    # Tab structure
    calendar_tab, scheduled_tab, occasional_tab = st.tabs(["Calendar View", "Scheduled Events", "Occasional Events"])
    
    with calendar_tab:
        st.subheader("Event Calendar")
        
        # Month navigation
        col_prev, col_month, col_next = st.columns([1, 2, 1])
        current_year, current_month = st.session_state.current_calendar_month
        
        with col_prev:
            if st.button("◀ Previous", key="prev_month"):
                current_month -= 1
                if current_month < 1:
                    current_month = 12
                    current_year -= 1
                st.session_state.current_calendar_month = (current_year, current_month)
                st.rerun()
        
        with col_month:
            st.write(f"### {datetime(current_year, current_month, 1).strftime('%B %Y')}")
        
        with col_next:
            if st.button("Next ▶", key="next_month"):
                current_month += 1
                if current_month > 12:
                    current_month = 1
                    current_year += 1
                st.session_state.current_calendar_month = (current_year, current_month)
                st.rerun()
        
        # Generate calendar days
        days_in_month = (date(current_year, current_month % 12 + 1, 1) - timedelta(days=1)).day
        first_day = date(current_year, current_month, 1).weekday()  # 0 = Monday
        
        # Create calendar grid
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        calendar_grid = [weekdays]
        
        # Add empty cells for days before first of month
        week = [""] * first_day
        
        # Add days of month
        for day in range(1, days_in_month + 1):
            week.append(day)
            if len(week) == 7:
                calendar_grid.append(week)
                week = []
        
        # Add remaining days to last week
        if week:
            week += [""] * (7 - len(week))
            calendar_grid.append(week)
        
        # Display calendar
        for week in calendar_grid:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day in weekdays:  # Header
                        st.write(f"**{day}**")
                    elif day:  # Day number
                        date_str = f"{current_year}-{current_month:02d}-{day:02d}"
                        st.write(f"**{day}**")
                        
                        # Check for events on this day
                        if date_str in st.session_state.calendar_events:
                            event_name, event_group = st.session_state.calendar_events[date_str]
                            
                            # Show event if user can access it
                            if not event_group or can_access_group(event_group):
                                with st.expander(f"{event_name}"):
                                    st.write(f"Group: {event_group}" if event_group else "All groups")
                                    if st.button("View Details", key=f"event_{date_str}"):
                                        # Find the event in scheduled events
                                        event_details = st.session_state.scheduled_events[
                                            st.session_state.scheduled_events["Event Name"] == event_name
                                        ]
                                        if not event_details.empty:
                                            st.dataframe(event_details, use_container_width=True)
        
        # Add new event to calendar (leaders and admins only)
        if is_admin() or is_group_leader():
            with st.expander("Add New Calendar Event", expanded=False):
                event_name = st.text_input("Event Name", key="new_calendar_event_name")
                event_date = st.date_input("Event Date", key="new_calendar_event_date")
                event_group = st.selectbox(
                    "Event Group", 
                    [st.session_state.current_group] + GROUP_NAMES if is_admin() else [st.session_state.current_group],
                    key="new_calendar_event_group"
                )
                
                if st.button("Add Event", key="add_calendar_event"):
                    if not event_name:
                        st.error("Please enter an event name")
                        return
                    
                    date_str = event_date.strftime("%Y-%m-%d")
                    st.session_state.calendar_events[date_str] = [event_name, event_group]
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    success, msg = save_all_data(sheet)
                    if success:
                        log_activity("add_calendar_event", f"Added event: {event_name} on {date_str}")
                        st.success(f"Added event: {event_name} on {date_str}")
                        st.rerun()
                    else:
                        st.error(f"Failed to save event: {msg}")
    
    with scheduled_tab:
        st.subheader("Regularly Scheduled Events")
        
        # Filter by group
        if is_admin():
            filter_group = st.selectbox("Filter by group", ["All"] + GROUP_NAMES, key="scheduled_filter")
            if filter_group != "All":
                filtered_events = st.session_state.scheduled_events[
                    st.session_state.scheduled_events["Responsible Group"] == filter_group
                ]
            else:
                filtered_events = st.session_state.scheduled_events
        else:
            # Regular users see only their group's events
            filtered_events = st.session_state.scheduled_events[
                st.session_state.scheduled_events["Responsible Group"] == st.session_state.current_group
            ]
        
        if filtered_events.empty:
            st.info("No scheduled events found")
        else:
            st.dataframe(filtered_events, use_container_width=True)
        
        # Add new scheduled event (leaders and admins only)
        if is_admin() or is_group_leader():
            with st.expander("Add New Scheduled Event", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    event_name = st.text_input("Event Name", key="new_scheduled_event_name")
                    funds_per_event = st.number_input("Funds Per Event", min_value=0, step=10, key="funds_per_event")
                    frequency = st.number_input("Frequency Per Month", min_value=1, max_value=4, key="event_frequency")
                
                with col2:
                    responsible_group = st.selectbox(
                        "Responsible Group", 
                        GROUP_NAMES if is_admin() else [st.session_state.current_group],
                        key="responsible_group"
                    )
                    next_scheduled = st.date_input("Next Scheduled Date", key="next_scheduled_date")
                    organizer = st.text_input("Organizer Name", value=st.session_state.user, key="event_organizer")
                
                if st.button("Add Scheduled Event", key="add_scheduled_event"):
                    if not event_name or not organizer:
                        st.error("Please fill in all required fields")
                        return
                    
                    total_funds = funds_per_event * frequency
                    
                    new_event = pd.DataFrame([{
                        "Event Name": event_name,
                        "Funds Per Event": funds_per_event,
                        "Frequency Per Month": frequency,
                        "Total Funds": total_funds,
                        "Responsible Group": responsible_group,
                        "Last Held": "",
                        "Next Scheduled": next_scheduled.strftime("%Y-%m-%d"),
                        "Organizer": organizer
                    }])
                    
                    st.session_state.scheduled_events = pd.concat(
                        [st.session_state.scheduled_events, new_event], ignore_index=True
                    )
                    
                    # Add to calendar
                    st.session_state.calendar_events[next_scheduled.strftime("%Y-%m-%d")] = [event_name, responsible_group]
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    success, msg = save_all_data(sheet)
                    if success:
                        log_activity("add_scheduled_event", f"Added scheduled event: {event_name}")
                        st.success(f"Added scheduled event: {event_name}")
                        st.rerun()
                    else:
                        st.error(f"Failed to save event: {msg}")
    
    with occasional_tab:
        st.subheader("Occasional/Special Events")
        
        # Filter by group
        if is_admin():
            filter_group = st.selectbox("Filter by group", ["All"] + GROUP_NAMES, key="occasional_filter")
            if filter_group != "All":
                filtered_events = st.session_state.occasional_events[
                    st.session_state.occasional_events["Responsible Group"] == filter_group
                ]
            else:
                filtered_events = st.session_state.occasional_events
        else:
            # Regular users see only their group's events
            filtered_events = st.session_state.occasional_events[
                st.session_state.occasional_events["Responsible Group"] == st.session_state.current_group
            ]
        
        if filtered_events.empty:
            st.info("No occasional events found")
        else:
            st.dataframe(filtered_events, use_container_width=True)
        
        # Add new occasional event (leaders and admins only)
        if is_admin() or is_group_leader():
            with st.expander("Record Completed Event", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    event_name = st.text_input("Event Name", key="new_occasional_event_name")
                    funds_raised = st.number_input("Total Funds Raised", min_value=0, step=10, key="funds_raised")
                    cost = st.number_input("Total Cost", min_value=0, step=10, key="event_cost")
                    date_held = st.date_input("Date Held", key="date_held")
                
                with col2:
                    responsible_group = st.selectbox(
                        "Responsible Group", 
                        GROUP_NAMES if is_admin() else [st.session_state.current_group],
                        key="occasional_responsible_group"
                    )
                    staff_many = st.selectbox("Required Many Staff?", ["Yes", "No"], key="staff_many")
                    prep_time = st.number_input("Preparation Time (days)", min_value=1, key="prep_time")
                    rating = st.slider("Success Rating", 1.0, 5.0, 3.0, 0.1, key="event_rating")
                    attendance = st.number_input("Attendance", min_value=0, key="event_attendance")
                
                if st.button("Record Event", key="record_occasional_event"):
                    if not event_name:
                        st.error("Please enter an event name")
                        return
                    
                    new_event = pd.DataFrame([{
                        "Event Name": event_name,
                        "Total Funds Raised": funds_raised,
                        "Cost": cost,
                        "Staff Many Or Not": staff_many,
                        "Preparation Time": prep_time,
                        "Rating": rating,
                        "Responsible Group": responsible_group,
                        "Date Held": date_held.strftime("%Y-%m-%d"),
                        "Attendance": attendance
                    }])
                    
                    st.session_state.occasional_events = pd.concat(
                        [st.session_state.occasional_events, new_event], ignore_index=True
                    )
                    
                    # Record net funds as group earnings
                    net_earnings = funds_raised - cost
                    if net_earnings > 0:
                        record_group_earning(
                            responsible_group, 
                            net_earnings, 
                            f"Net proceeds from {event_name}"
                        )
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    success, msg = save_all_data(sheet)
                    if success:
                        log_activity("add_occasional_event", f"Added occasional event: {event_name}")
                        st.success(f"Recorded event: {event_name}")
                        st.rerun()
                    else:
                        st.error(f"Failed to save event: {msg}")

def render_finances():
    """Render finances page with transactions and group earnings"""
    st.header("Financial Management")
    
    # Tab structure
    transactions_tab, earnings_tab, budget_tab = st.tabs(["Transactions", "Group Earnings", "Budget Overview"])
    
    with transactions_tab:
        st.subheader("Financial Transactions")
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            date_filter = st.selectbox(
                "Date Range",
                ["All Time", "This Month", "Last Month", "This Quarter", "This Year", "Custom Range"],
                key="transaction_date_filter"
            )
        
        with col2:
            category_filter = st.selectbox(
                "Category",
                ["All", "Income", "Expense"],
                key="transaction_category_filter"
            )
        
        with col3:
            if is_admin():
                group_filter = st.selectbox(
                    "Group",
                    ["All"] + GROUP_NAMES,
                    key="transaction_group_filter"
                )
            else:
                group_filter = st.session_state.current_group
                st.write(f"Group: {group_filter}")
        
        # Apply date filter
        if not st.session_state.money_data.empty:
            # Convert to datetime for filtering
            st.session_state.money_data["Date"] = pd.to_datetime(st.session_state.money_data["Date"])
            filtered_transactions = st.session_state.money_data.copy()
            
            # Date filter
            today = date.today()
            if date_filter == "This Month":
                start_date = date(today.year, today.month, 1)
                filtered_transactions = filtered_transactions[
                    filtered_transactions["Date"].dt.date >= start_date
                ]
            elif date_filter == "Last Month":
                last_month = today.month - 1 if today.month > 1 else 12
                last_month_year = today.year if today.month > 1 else today.year - 1
                start_date = date(last_month_year, last_month, 1)
                end_date = date(today.year, today.month, 1) - timedelta(days=1)
                filtered_transactions = filtered_transactions[
                    (filtered_transactions["Date"].dt.date >= start_date) &
                    (filtered_transactions["Date"].dt.date <= end_date)
                ]
            elif date_filter == "This Quarter":
                quarter_start = (today.month - 1) // 3 * 3 + 1
                start_date = date(today.year, quarter_start, 1)
                filtered_transactions = filtered_transactions[
                    filtered_transactions["Date"].dt.date >= start_date
                ]
            elif date_filter == "This Year":
                start_date = date(today.year, 1, 1)
                filtered_transactions = filtered_transactions[
                    filtered_transactions["Date"].dt.date >= start_date
                ]
            elif date_filter == "Custom Range":
                start_date = st.date_input("Start Date", key="custom_start_date")
                end_date = st.date_input("End Date", key="custom_end_date")
                filtered_transactions = filtered_transactions[
                    (filtered_transactions["Date"].dt.date >= start_date) &
                    (filtered_transactions["Date"].dt.date <= end_date)
                ]
            
            # Category filter
            if category_filter != "All":
                filtered_transactions = filtered_transactions[
                    filtered_transactions["Category"] == category_filter
                ]
            
            # Group filter
            if group_filter != "All":
                filtered_transactions = filtered_transactions[
                    filtered_transactions["Group"] == group_filter
                ]
            
            # Display transactions
            if filtered_transactions.empty:
                st.info("No transactions found matching your filters")
            else:
                # Format date for display
                filtered_transactions["Date"] = filtered_transactions["Date"].dt.strftime("%Y-%m-%d")
                st.dataframe(filtered_transactions, use_container_width=True)
                
                # Calculate totals
                total_income = filtered_transactions[
                    filtered_transactions["Category"] == "Income"
                ]["Amount"].sum() if "Income" in filtered_transactions["Category"].values else 0
                
                total_expense = filtered_transactions[
                    filtered_transactions["Category"] == "Expense"
                ]["Amount"].sum() if "Expense" in filtered_transactions["Category"].values else 0
                
                net_total = total_income + total_expense  # Expenses are negative values
                
                col_total_income, col_total_expense, col_net = st.columns(3)
                with col_total_income:
                    st.metric("Total Income", f"${total_income:.2f}")
                with col_total_expense:
                    st.metric("Total Expenses", f"${abs(total_expense):.2f}")
                with col_net:
                    st.metric("Net Balance", f"${net_total:.2f}")
                
                # Chart
                st.subheader("Financial Overview")
                fig, ax = plt.subplots(figsize=(10, 6))
                
                # Group by date for trend
                filtered_transactions["Date"] = pd.to_datetime(filtered_transactions["Date"])
                monthly_data = filtered_transactions.groupby(
                    [filtered_transactions["Date"].dt.to_period("M"), "Category"]
                )["Amount"].sum().unstack(fill_value=0)
                
                if not monthly_data.empty:
                    monthly_data.plot(kind="bar", ax=ax)
                    ax.set_title("Monthly Financial Activity")
                    ax.set_xlabel("Month")
                    ax.set_ylabel("Amount ($)")
                    plt.xticks(rotation=45)
                    st.pyplot(fig)
        else:
            st.info("No financial transactions recorded yet")
        
        # Record new transaction (leaders and admins only)
        if is_admin() or is_group_leader():
            with st.expander("Record New Transaction", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    transaction_date = st.date_input("Transaction Date", key="transaction_date")
                    amount = st.number_input("Amount", min_value=0.01, step=0.01, key="transaction_amount")
                    category = st.selectbox("Category", ["Income", "Expense"], key="transaction_category")
                
                with col2:
                    transaction_group = st.selectbox(
                        "Group", 
                        GROUP_NAMES if is_admin() else [st.session_state.current_group],
                        key="transaction_group"
                    )
                    description = st.text_input("Description", key="transaction_description")
                    handled_by = st.text_input("Handled By", value=st.session_state.user, key="handled_by")
                
                # Adjust amount for expenses (store as negative)
                if category == "Expense":
                    amount = -amount
                
                if st.button("Record Transaction", key="record_transaction"):
                    if not description:
                        st.error("Please enter a description")
                        return
                    
                    new_transaction = pd.DataFrame([{
                        "Amount": amount,
                        "Description": description,
                        "Date": transaction_date.strftime("%Y-%m-%d"),
                        "Handled By": handled_by,
                        "Group": transaction_group,
                        "Category": category
                    }])
                    
                    st.session_state.money_data = pd.concat(
                        [st.session_state.money_data, new_transaction], ignore_index=True
                    )
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    success, msg = save_all_data(sheet)
                    if success:
                        log_activity("record_transaction", f"Recorded {category.lower()}: ${abs(amount)}")
                        st.success(f"Recorded {category.lower()} successfully")
                        st.rerun()
                    else:
                        st.error(f"Failed to save transaction: {msg}")
    
    with earnings_tab:
        st.subheader("Group Earnings")
        
        # Filter options
        if is_admin():
            earnings_group_filter = st.selectbox(
                "Group",
                ["All"] + GROUP_NAMES,
                key="earnings_group_filter"
            )
        else:
            earnings_group_filter = st.session_state.current_group
            st.write(f"Group: {earnings_group_filter}")
        
        # Apply filter
        if not st.session_state.group_earnings.empty:
            if earnings_group_filter != "All":
                filtered_earnings = st.session_state.group_earnings[
                    st.session_state.group_earnings["Group"] == earnings_group_filter
                ]
            else:
                filtered_earnings = st.session_state.group_earnings
            
            if filtered_earnings.empty:
                st.info("No earnings records found")
            else:
                st.dataframe(filtered_earnings, use_container_width=True)
                
                # Show verification options for admins
                if is_admin():
                    st.subheader("Verify Earnings")
                    pending_earnings = filtered_earnings[filtered_earnings["Verified"] == "Pending"]
                    
                    if pending_earnings.empty:
                        st.info("No pending earnings to verify")
                    else:
                        earning_index = st.selectbox(
                            "Select earning to verify",
                            pending_earnings.index,
                            format_func=lambda x: f"{pending_earnings.at[x, 'Group']}: ${pending_earnings.at[x, 'Amount']} - {pending_earnings.at[x, 'Description']}"
                        )
                        
                        verify_status = st.selectbox("Status", ["Verified", "Rejected"], key="verify_status")
                        admin_notes = st.text_input("Admin Notes", key="verify_notes")
                        
                        if st.button("Update Status", key="update_earning_status"):
                            success, msg = verify_group_earning(earning_index, verify_status, admin_notes)
                            if success:
                                # Save to Google Sheets
                                sheet = connect_gsheets()
                                save_all_data(sheet)
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        
        # Record new earnings (group leaders and admins)
        if is_admin() or is_group_leader():
            with st.expander("Record New Earnings", expanded=False):
                earnings_group = st.selectbox(
                    "Group", 
                    GROUP_NAMES if is_admin() else [st.session_state.current_group],
                    key="new_earnings_group"
                )
                earnings_amount = st.number_input("Amount", min_value=0.01, step=0.01, key="earnings_amount")
                earnings_description = st.text_input("Description", key="earnings_description")
                
                if st.button("Record Earnings", key="record_earnings"):
                    if not earnings_description:
                        st.error("Please enter a description")
                        return
                    
                    success, msg = record_group_earning(earnings_group, earnings_amount, earnings_description)
                    if success:
                        # Save to Google Sheets
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    
    with budget_tab:
        st.subheader("Budget Overview")
        
        # Calculate overall budget
        if not st.session_state.money_data.empty:
            total_income = st.session_state.money_data[
                st.session_state.money_data["Category"] == "Income"
            ]["Amount"].sum() if "Income" in st.session_state.money_data["Category"].values else 0
            
            total_expense = st.session_state.money_data[
                st.session_state.money_data["Category"] == "Expense"
            ]["Amount"].sum() if "Expense" in st.session_state.money_data["Category"].values else 0
            
            current_balance = total_income + total_expense  # Expenses are negative
            
            st.metric("Current Total Balance", f"${current_balance:.2f}")
            
            # Budget by group
            st.subheader("Balance by Group")
            group_balances = {}
            for group in GROUP_NAMES:
                group_income = st.session_state.money_data[
                    (st.session_state.money_data["Group"] == group) &
                    (st.session_state.money_data["Category"] == "Income")
                ]["Amount"].sum() if "Income" in st.session_state.money_data["Category"].values else 0
                
                group_expense = st.session_state.money_data[
                    (st.session_state.money_data["Group"] == group) &
                    (st.session_state.money_data["Category"] == "Expense")
                ]["Amount"].sum() if "Expense" in st.session_state.money_data["Category"].values else 0
                
                group_balances[group] = group_income + group_expense
            
            # Create pie chart
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.pie(group_balances.values(), labels=group_balances.keys(), autopct='%1.1f%%')
            ax.set_title('Budget Distribution by Group')
            st.pyplot(fig)
            
            # Create bar chart of balances
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.bar(group_balances.keys(), group_balances.values(), color='lightgreen')
            ax.set_title('Current Balance by Group')
            ax.set_ylabel('Balance ($)')
            st.pyplot(fig)
        else:
            st.info("No financial data available to display budget overview")

def render_credits():
    """Render credits and rewards page"""
    st.header("Credits & Rewards System")
    
    # Tab structure
    my_credits_tab, rewards_tab, history_tab = st.tabs(["My Credits", "Reward Catalog", "Redeemption History"])
    
    with my_credits_tab:
        st.subheader("Your Credit Balance")
        
        # Display current user's credits
        if not st.session_state.credit_data.empty and st.session_state.user in st.session_state.credit_data["Name"].values:
            user_credits = st.session_state.credit_data[st.session_state.credit_data["Name"] == st.session_state.user].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Credits Earned", user_credits["Total_Credits"])
            with col2:
                st.metric("Credits Redeemed", user_credits["RedeemedCredits"])
            
            available_credits = user_credits["Total_Credits"] - user_credits["RedeemedCredits"]
            st.metric("Available Credits", available_credits)
            
            # Credit history visualization
            st.subheader("Credit History")
            fig, ax = plt.subplots(figsize=(10, 4))
            
            # Simulated monthly data for demonstration
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
            monthly_earnings = [
                random.randint(10, 50) for _ in range(len(months))
            ]
            
            ax.plot(months, monthly_earnings, marker='o', color='blue')
            ax.set_title('Monthly Credit Earnings')
            ax.set_ylabel('Credits Earned')
            ax.grid(True, linestyle='--', alpha=0.7)
            st.pyplot(fig)
            
            # Ways to earn more credits
            with st.expander("Ways to Earn More Credits"):
                st.write("1. Attend student council meetings (10 credits each)")
                st.write("2. Volunteer for events (20-50 credits depending on event size)")
                st.write("3. Contribute ideas that get implemented (30 credits)")
                st.write("4. Lead a successful project (50-100 credits)")
                st.write("5. Recruit new members (25 credits per recruit)")
        else:
            st.info("No credit data found for your account")
        
        # Admin section to manage credits
        if is_admin():
            with st.expander("Manage Credits (Admin Only)", expanded=False):
                st.subheader("Adjust User Credits")
                
                # Select user
                user_to_adjust = st.selectbox(
                    "Select User",
                    sorted(st.session_state.users.keys()),
                    key="credit_user_select"
                )
                
                # Get current credits
                current_credits = 0
                if not st.session_state.credit_data.empty and user_to_adjust in st.session_state.credit_data["Name"].values:
                    current_credits = st.session_state.credit_data[
                        st.session_state.credit_data["Name"] == user_to_adjust
                    ]["Total_Credits"].values[0]
                
                st.write(f"Current credits: {current_credits}")
                
                # Adjustment
                adjustment = st.number_input(
                    "Credit Adjustment",
                    value=0,
                    step=5,
                    key="credit_adjustment"
                )
                
                reason = st.text_input("Reason for adjustment", key="credit_adjustment_reason")
                
                if st.button("Apply Adjustment", key="apply_credit_adjustment"):
                    if adjustment == 0:
                        st.error("Please enter a non-zero adjustment")
                        return
                    
                    if not reason:
                        st.error("Please provide a reason for the adjustment")
                        return
                    
                    # Update or create credit record
                    if user_to_adjust in st.session_state.credit_data["Name"].values:
                        # Update existing record
                        index = st.session_state.credit_data[
                            st.session_state.credit_data["Name"] == user_to_adjust
                        ].index[0]
                        st.session_state.credit_data.at[index, "Total_Credits"] += adjustment
                        st.session_state.credit_data.at[index, "Last_Updated"] = datetime.now().strftime("%Y-%m-%d")
                    else:
                        # Create new record
                        new_record = pd.DataFrame([{
                            "Name": user_to_adjust,
                            "Total_Credits": adjustment,
                            "RedeemedCredits": 0,
                            "Last_Updated": datetime.now().strftime("%Y-%m-%d")
                        }])
                        st.session_state.credit_data = pd.concat(
                            [st.session_state.credit_data, new_record], ignore_index=True
                        )
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    success, msg = save_all_data(sheet)
                    if success:
                        log_activity(
                            "adjust_credits", 
                            f"Adjusted {user_to_adjust}'s credits by {adjustment} - {reason}"
                        )
                        st.success(f"Successfully adjusted {user_to_adjust}'s credits by {adjustment}")
                    else:
                        st.error(f"Failed to save adjustment: {msg}")
    
    with rewards_tab:
        st.subheader("Reward Catalog")
        
        # Display available rewards
        if not st.session_state.reward_data.empty:
            # Filter by category
            categories = ["All"] + list(st.session_state.reward_data["Category"].unique())
            selected_category = st.selectbox("Filter by Category", categories, key="reward_category_filter")
            
            # Apply filter
            if selected_category != "All":
                filtered_rewards = st.session_state.reward_data[
                    st.session_state.reward_data["Category"] == selected_category
                ]
            else:
                filtered_rewards = st.session_state.reward_data
            
            # Display rewards in a grid
            reward_rows = []
            current_row = []
            
            for _, reward in filtered_rewards.iterrows():
                current_row.append(reward)
                if len(current_row) == 3:
                    reward_rows.append(current_row)
                    current_row = []
            
            if current_row:
                reward_rows.append(current_row)
            
            # Display each row
            for row in reward_rows:
                cols = st.columns(3)
                for i, reward in enumerate(row):
                    with cols[i]:
                        with st.card():
                            st.subheader(reward["Reward"])
                            st.write(f"**Cost:** {reward['Cost']} credits")
                            st.write(f"**Category:** {reward['Category']}")
                            st.write(f"**In Stock:** {reward['Stock']}")
                            
                            # Check if user can redeem
                            user_can_redeem = False
                            available_credits = 0
                            
                            if not st.session_state.credit_data.empty and st.session_state.user in st.session_state.credit_data["Name"].values:
                                user_credits = st.session_state.credit_data[
                                    st.session_state.credit_data["Name"] == st.session_state.user
                                ].iloc[0]
                                available_credits = user_credits["Total_Credits"] - user_credits["RedeemedCredits"]
                                
                                if available_credits >= reward["Cost"] and reward["Stock"] > 0:
                                    user_can_redeem = True
                            
                            if user_can_redeem:
                                if st.button(f"Redeem", key=f"redeem_{reward['Reward']}"):
                                    # Update user credits
                                    index = st.session_state.credit_data[
                                        st.session_state.credit_data["Name"] == st.session_state.user
                                    ].index[0]
                                    st.session_state.credit_data.at[index, "RedeemedCredits"] += reward["Cost"]
                                    st.session_state.credit_data.at[index, "Last_Updated"] = datetime.now().strftime("%Y-%m-%d")
                                    
                                    # Update reward stock
                                    reward_index = st.session_state.reward_data[
                                        st.session_state.reward_data["Reward"] == reward["Reward"]
                                    ].index[0]
                                    st.session_state.reward_data.at[reward_index, "Stock"] -= 1
                                    
                                    # Save to Google Sheets
                                    sheet = connect_gsheets()
                                    success, msg = save_all_data(sheet)
                                    if success:
                                        log_activity(
                                            "redeem_reward", 
                                            f"Redeemed {reward['Reward']} for {reward['Cost']} credits"
                                        )
                                        st.success(f"Successfully redeemed {reward['Reward']}!")
                                        st.rerun()
                                    else:
                                        st.error(f"Failed to process redemption: {msg}")
                            else:
                                if reward["Stock"] == 0:
                                    st.button("Out of Stock", disabled=True, key=f"outofstock_{reward['Reward']}")
                                else:
                                    st.button(
                                        f"Not Enough Credits (Need {reward['Cost']})", 
                                        disabled=True, 
                                        key=f"nocredits_{reward['Reward']}"
                                    )
        
        # Admin section to manage rewards
        if is_admin():
            with st.expander("Manage Rewards (Admin Only)", expanded=False):
                st.subheader("Add New Reward")
                
                col1, col2 = st.columns(2)
                with col1:
                    new_reward_name = st.text_input("Reward Name", key="new_reward_name")
                    new_reward_cost = st.number_input("Credit Cost", min_value=1, step=5, key="new_reward_cost")
                with col2:
                    new_reward_category = st.text_input("Category", key="new_reward_category")
                    new_reward_stock = st.number_input("Initial Stock", min_value=0, step=1, key="new_reward_stock")
                
                if st.button("Add Reward", key="add_new_reward"):
                    if not new_reward_name or not new_reward_category:
                        st.error("Please fill in all fields")
                        return
                    
                    new_reward = pd.DataFrame([{
                        "Reward": new_reward_name,
                        "Cost": new_reward_cost,
                        "Stock": new_reward_stock,
                        "Category": new_reward_category
                    }])
                    
                    st.session_state.reward_data = pd.concat(
                        [st.session_state.reward_data, new_reward], ignore_index=True
                    )
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    success, msg = save_all_data(sheet)
                    if success:
                        log_activity("add_reward", f"Added new reward: {new_reward_name}")
                        st.success(f"Added new reward: {new_reward_name}")
                    else:
                        st.error(f"Failed to add reward: {msg}")
                
                st.subheader("Update Reward Stock")
                reward_to_update = st.selectbox(
                    "Select Reward",
                    st.session_state.reward_data["Reward"].tolist(),
                    key="reward_to_update"
                )
                
                if reward_to_update:
                    current_stock = st.session_state.reward_data[
                        st.session_state.reward_data["Reward"] == reward_to_update
                    ]["Stock"].values[0]
                    
                    new_stock = st.number_input(
                        "New Stock Level",
                        min_value=0,
                        value=current_stock,
                        key="new_reward_stock_level"
                    )
                    
                    if st.button("Update Stock", key="update_reward_stock"):
                        index = st.session_state.reward_data[
                            st.session_state.reward_data["Reward"] == reward_to_update
                        ].index[0]
                        st.session_state.reward_data.at[index, "Stock"] = new_stock
                        
                        # Save to Google Sheets
                        sheet = connect_gsheets()
                        success, msg = save_all_data(sheet)
                        if success:
                            log_activity(
                                "update_reward_stock", 
                                f"Updated {reward_to_update} stock from {current_stock} to {new_stock}"
                            )
                            st.success(f"Updated {reward_to_update} stock to {new_stock}")
                        else:
                            st.error(f"Failed to update stock: {msg}")
    
    with history_tab:
        st.subheader("Redemption History")
        
        # This would normally be a separate data store, but for this demo
        # we'll generate some sample data
        st.info("This section shows your redemption history. In a full implementation, this would connect to a redemption records database.")
        
        # Generate sample redemption history
        sample_history = []
        today = date.today()
        
        for i in range(5):
            redemption_date = today - timedelta(days=random.randint(7, 90))
            reward = random.choice(st.session_state.reward_data["Reward"].tolist()) if not st.session_state.reward_data.empty else "Bubble Tea"
            cost = random.randint(30, 200)
            
            sample_history.append({
                "Date": redemption_date.strftime("%Y-%m-%d"),
                "Reward": reward,
                "Cost": cost,
                "Status": random.choice(["Completed", "Pending", "Completed"])
            })
        
        # Sort by date (newest first)
        sample_history.sort(key=lambda x: x["Date"], reverse=True)
        
        # Display
        st.dataframe(sample_history, use_container_width=True)
        
        # Admin view of all redemptions
        if is_admin():
            with st.expander("View All Redemptions (Admin Only)", expanded=False):
                st.subheader("System-wide Redemption History")
                
                # Generate system-wide sample data
                system_history = []
                for i in range(20):
                    user = random.choice(list(st.session_state.users.keys()))
                    redemption_date = today - timedelta(days=random.randint(7, 90))
                    reward = random.choice(st.session_state.reward_data["Reward"].tolist()) if not st.session_state.reward_data.empty else "Bubble Tea"
                    cost = random.randint(30, 200)
                    
                    system_history.append({
                        "User": user,
                        "Date": redemption_date.strftime("%Y-%m-%d"),
                        "Reward": reward,
                        "Cost": cost,
                        "Status": random.choice(["Completed", "Pending", "Cancelled"])
                    })
                
                # Sort by date (newest first)
                system_history.sort(key=lambda x: x["Date"], reverse=True)
                
                # Display
                st.dataframe(system_history, use_container_width=True)

def render_group_management():
    """Render group management page for leaders and admins"""
    st.header("Group Management")
    
    # Only group leaders and admins can access this page
    if not is_group_leader() and not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    # Determine which groups the user can manage
    if is_admin():
        # Admins can manage all groups
        selected_group = st.selectbox("Select Group to Manage", GROUP_NAMES, key="manage_group_select")
    else:
        # Group leaders can only manage their own group
        selected_group = st.session_state.current_group
        st.info(f"Managing group: {selected_group}")
    
    # Tab structure
    members_tab, leaders_tab, codes_tab, performance_tab = st.tabs(
        ["Members", "Leaders", "Group Code", "Performance"]
    )
    
    with members_tab:
        st.subheader(f"{selected_group} Members")
        
        # Display current members
        current_members = st.session_state.groups.get(selected_group, [])
        if current_members:
            st.write(f"Total members: {len(current_members)}")
            
            # Display members in a list with checkboxes
            cols = st.columns(3)
            for i, member in enumerate(current_members):
                with cols[i % 3]:
                    st.checkbox(member, value=True, disabled=True)
            
            # Remove member (admin or group leader)
            if is_admin() or (is_group_leader(selected_group)):
                member_to_remove = st.selectbox(
                    "Select member to remove",
                    current_members,
                    key="member_to_remove"
                )
                
                if st.button("Remove Member", key="remove_member_btn"):
                    if member_to_remove in st.session_state.groups[selected_group]:
                        # Remove from group
                        st.session_state.groups[selected_group].remove(member_to_remove)
                        
                        # If removing group leader, update leader
                        if st.session_state.group_leaders.get(selected_group) == member_to_remove:
                            if st.session_state.groups[selected_group]:
                                new_leader = st.session_state.groups[selected_group][0]
                                st.session_state.group_leaders[selected_group] = new_leader
                                st.session_state.users[new_leader]["role"] = "group_leader"
                            else:
                                st.session_state.group_leaders[selected_group] = ""
                        
                        # Update user's role if needed
                        if st.session_state.users.get(member_to_remove, {}).get("role") == "group_leader" and \
                           not any(l == member_to_remove for l in st.session_state.group_leaders.values()):
                            st.session_state.users[member_to_remove]["role"] = "user"
                        
                        # Save to Google Sheets
                        sheet = connect_gsheets()
                        success, msg = save_all_data(sheet)
                        if success:
                            log_activity(
                                "remove_group_member", 
                                f"Removed {member_to_remove} from {selected_group}"
                            )
                            st.success(f"Removed {member_to_remove} from {selected_group}")
                            st.rerun()
                        else:
                            st.error(f"Failed to remove member: {msg}")
        
        else:
            st.info(f"No members in {selected_group} yet")
        
        # Add member (admin or group leader)
        if is_admin() or (is_group_leader(selected_group)):
            st.subheader("Add New Member")
            
            # Option 1: Create new user with group code
            st.write("Option 1: Provide this group code to new members during signup:")
            st.code(st.session_state.group_codes[selected_group])
            
            # Option 2: Move existing user to this group
            st.write("Option 2: Move existing user to this group:")
            all_users = list(st.session_state.users.keys())
            users_not_in_group = [user for user in all_users if user not in current_members]
            
            if users_not_in_group:
                user_to_add = st.selectbox(
                    "Select user to add",
                    users_not_in_group,
                    key="user_to_add"
                )
                
                # Find current group of user
                current_user_group = next(
                    (g for g, members in st.session_state.groups.items() if user_to_add in members),
                    None
                )
                
                if current_user_group and st.button("Move User to Group", key="move_user_btn"):
                    success, msg = move_user_between_groups(user_to_add, current_user_group, selected_group)
                    if success:
                        # Save to Google Sheets
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.info("All users are already in this group")
    
    with leaders_tab:
        st.subheader(f"{selected_group} Leaders")
        
        current_leader = st.session_state.group_leaders.get(selected_group, "")
        if current_leader:
            st.write(f"Current group leader: **{current_leader}**")
        else:
            st.info(f"No leader assigned to {selected_group} yet")
        
        # Only admins can change leaders
        if is_admin():
            group_members = st.session_state.groups.get(selected_group, [])
            if group_members:
                new_leader = st.selectbox(
                    "Select new group leader",
                    group_members,
                    index=group_members.index(current_leader) if current_leader in group_members else 0,
                    key="new_group_leader"
                )
                
                if st.button("Set as Leader", key="set_leader_btn"):
                    if new_leader == current_leader:
                        st.info(f"{new_leader} is already the group leader")
                        return
                    
                    success, msg = set_group_leader(selected_group, new_leader)
                    if success:
                        # Save to Google Sheets
                        sheet = connect_gsheets()
                        save_all_data(sheet)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.warning("Cannot set leader - group has no members")
        else:
            st.info("Only administrators can change group leaders")
    
    with codes_tab:
        st.subheader(f"{selected_group} Access Code")
        
        st.write("This code allows new members to join your group during signup:")
        st.code(st.session_state.group_codes[selected_group])
        
        # Regenerate code (admin or group leader)
        if is_admin() or is_group_leader(selected_group):
            if st.button("Regenerate Group Code", key="regenerate_code_btn"):
                success, msg = regenerate_group_code(selected_group)
                if success:
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    save_all_data(sheet)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        # Instructions for new members
        with st.expander("Instructions for New Members"):
            st.write("1. New members should click 'Sign Up' on the login page")
            st.write("2. They should complete the signup form with their details")
            st.write(f"3. They must enter this code in the 'Group Code' field: {st.session_state.group_codes[selected_group]}")
            st.write("4. After signup, they will be added to this group automatically")
    
    with performance_tab:
        st.subheader(f"{selected_group} Performance Metrics")
        
        # Calculate metrics
        group_members = st.session_state.groups.get(selected_group, [])
        member_count = len(group_members)
        
        # Attendance rate
        attendance_rate = 0
        if member_count > 0 and not st.session_state.attendance.empty and len(st.session_state.meeting_names) > 0:
            group_attendance = st.session_state.attendance[
                st.session_state.attendance["Name"].isin(group_members)
            ]
            
            if not group_attendance.empty:
                total_attendances = group_attendance[st.session_state.meeting_names].sum().sum()
                possible_attendances = len(group_attendance) * len(st.session_state.meeting_names)
                attendance_rate = round((total_attendances / possible_attendances) * 100) if possible_attendances > 0 else 0
        
        # Total earnings
        if not st.session_state.group_earnings.empty:
            group_earnings = st.session_state.group_earnings[
                (st.session_state.group_earnings["Group"] == selected_group) &
                (st.session_state.group_earnings["Verified"] == "Verified")
            ]["Amount"].sum()
        else:
            group_earnings = 0
        
        # Number of events organized
        scheduled_events_count = len(st.session_state.scheduled_events[
            st.session_state.scheduled_events["Responsible Group"] == selected_group
        ]) if not st.session_state.scheduled_events.empty else 0
        
        occasional_events_count = len(st.session_state.occasional_events[
            st.session_state.occasional_events["Responsible Group"] == selected_group
        ]) if not st.session_state.occasional_events.empty else 0
        
        total_events = scheduled_events_count + occasional_events_count
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Members", member_count)
        with col2:
            st.metric("Attendance Rate", f"{attendance_rate}%")
        with col3:
            st.metric("Total Earnings", f"${group_earnings}")
        with col4:
            st.metric("Events Organized", total_events)
        
        # Earnings chart
        st.subheader("Monthly Earnings")
        if not st.session_state.group_earnings.empty:
            # Filter data
            group_verified_earnings = st.session_state.group_earnings[
                (st.session_state.group_earnings["Group"] == selected_group) &
                (st.session_state.group_earnings["Verified"] == "Verified")
            ].copy()
            
            if not group_verified_earnings.empty:
                # Process dates
                group_verified_earnings["Date"] = pd.to_datetime(group_verified_earnings["Date"])
                group_verified_earnings["Month"] = group_verified_earnings["Date"].dt.to_period("M")
                
                # Group by month
                monthly_earnings = group_verified_earnings.groupby("Month")["Amount"].sum()
                
                # Create chart
                fig, ax = plt.subplots(figsize=(10, 6))
                monthly_earnings.plot(kind="bar", ax=ax, color='green')
                ax.set_title(f'Monthly Earnings for {selected_group}')
                ax.set_xlabel('Month')
                ax.set_ylabel('Earnings ($)')
                plt.xticks(rotation=45)
                st.pyplot(fig)
            else:
                st.info(f"No verified earnings data for {selected_group}")
        else:
            st.info("No earnings data available")

def render_submit_requests():
    """Render page for submitting reimbursement and event requests"""
    st.header("Submit Requests")
    
    # Only group leaders and admins can submit requests
    if not is_group_leader() and not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    # Tab structure
    reimbursement_tab, event_tab = st.tabs(["Reimbursement Request", "Event Approval Request"])
    
    with reimbursement_tab:
        st.subheader("Submit Reimbursement Request")
        
        # Determine group
        if is_admin():
            request_group = st.selectbox("Group", GROUP_NAMES, key="reimbursement_group")
        else:
            request_group = st.session_state.current_group
            st.info(f"Requesting for group: {request_group}")
        
        # Form fields
        col1, col2 = st.columns(2)
        with col1:
            requester_name = st.text_input("Requester Name", value=st.session_state.user, key="requester_name")
            amount = st.number_input(
                "Amount to Reimburse", 
                min_value=0.01, 
                step=0.01, 
                key="reimbursement_amount"
            )
        
        with col2:
            request_date = st.date_input("Expense Date", key="expense_date")
            max_amount = st.session_state.config.get("max_reimbursement", REIMBURSEMENT_LIMIT)
            st.info(f"Maximum without special approval: ${max_amount}")
        
        purpose = st.text_area(
            "Purpose of Expense", 
            placeholder="Please provide a detailed explanation of the expense...",
            key="reimbursement_purpose"
        )
        
        # Receipt upload
        receipt = st.file_uploader(
            "Upload Receipt (PDF or Image)", 
            type=["pdf", "jpg", "jpeg", "png"],
            key="receipt_upload"
        )
        
        if st.button("Submit Reimbursement Request", key="submit_reimbursement_btn"):
            if not requester_name or amount <= 0 or not purpose:
                st.error("Please fill in all required fields")
                return
            
            if len(purpose) < 10:
                st.error("Please provide a more detailed explanation (at least 10 characters)")
                return
            
            if not receipt:
                st.warning("Note: No receipt uploaded. This may delay processing.")
            
            # Submit request
            success, msg = submit_reimbursement_request(
                request_group,
                requester_name,
                amount,
                purpose
            )
            
            if success:
                # Save to Google Sheets
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(msg)
                
                # Clear form
                st.session_state.requester_name = st.session_state.user
                st.session_state.reimbursement_amount = 0.01
                st.session_state.reimbursement_purpose = ""
            else:
                st.error(msg)
        
        # View existing requests
        st.subheader("Your Reimbursement Requests")
        user_requests = st.session_state.reimbursement_requests[
            st.session_state.reimbursement_requests["Requester"] == st.session_state.user
        ] if not st.session_state.reimbursement_requests.empty else pd.DataFrame()
        
        if user_requests.empty:
            st.info("You have no reimbursement requests")
        else:
            st.dataframe(user_requests, use_container_width=True)
    
    with event_tab:
        st.subheader("Submit Event Approval Request")
        
        # Determine group
        if is_admin():
            event_group = st.selectbox("Group", GROUP_NAMES, key="event_request_group")
        else:
            event_group = st.session_state.current_group
            st.info(f"Event for group: {event_group}")
        
        # Form fields
        col1, col2 = st.columns(2)
        with col1:
            event_name = st.text_input("Event Name", key="event_request_name")
            requester_name = st.text_input("Requester Name", value=st.session_state.user, key="event_requester_name")
            proposed_date = st.date_input("Proposed Date", key="event_proposed_date")
        
        with col2:
            budget = st.number_input(
                "Estimated Budget ($)", 
                min_value=0, 
                step=10, 
                key="event_budget"
            )
            expected_attendance = st.number_input(
                "Expected Attendance", 
                min_value=1, 
                step=5, 
                key="event_attendance"
            )
            max_budget = st.session_state.config.get("max_event_budget", EVENT_BUDGET_LIMIT)
            st.info(f"Max budget without special approval: ${max_budget}")
        
        description = st.text_area(
            "Event Description", 
            placeholder="Please provide details about the event, its purpose, and how it benefits the school...",
            key="event_description"
        )
        
        # Additional details
        with st.expander("Additional Details", expanded=False):
            need_staff = st.selectbox(
                "Will you need additional staff?", 
                ["Yes", "No", "Not Sure"], 
                key="event_need_staff"
            )
            prep_time = st.number_input(
                "Estimated preparation time (days)", 
                min_value=1, 
                key="event_prep_time"
            )
            special_requirements = st.text_input(
                "Special requirements or permissions needed", 
                key="event_special_requirements"
            )
        
        if st.button("Submit Event Request", key="submit_event_btn"):
            if not event_name or not requester_name or not description:
                st.error("Please fill in all required fields")
                return
            
            if len(description) < 20:
                st.error("Please provide a more detailed description (at least 20 characters)")
                return
            
            # Submit request
            success, msg = submit_event_approval_request(
                event_group,
                requester_name,
                event_name,
                description,
                proposed_date.strftime("%Y-%m-%d"),
                budget,
                expected_attendance
            )
            
            if success:
                # Save to Google Sheets
                sheet = connect_gsheets()
                save_all_data(sheet)
                st.success(msg)
                
                # Clear form
                st.session_state.event_request_name = ""
                st.session_state.event_description = ""
            else:
                st.error(msg)
        
        # View existing requests
        st.subheader("Your Event Requests")
        user_event_requests = st.session_state.event_approval_requests[
            st.session_state.event_approval_requests["Requester"] == st.session_state.user
        ] if not st.session_state.event_approval_requests.empty else pd.DataFrame()
        
        if user_event_requests.empty:
            st.info("You have no event requests")
        else:
            st.dataframe(user_event_requests, use_container_width=True)

def render_admin_dashboard():
    """Render admin dashboard with system-wide overview"""
    st.header("Administrator Dashboard")
    
    # Only admins can access this page
    if not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    # System overview metrics
    st.subheader("System Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Users", len(st.session_state.users))
    
    with col2:
        total_meetings = len(st.session_state.meeting_names)
        st.metric("Total Meetings", total_meetings)
    
    with col3:
        total_events = len(st.session_state.scheduled_events) + len(st.session_state.occasional_events)
        st.metric("Total Events", total_events)
    
    with col4:
        if not st.session_state.money_data.empty:
            total_balance = st.session_state.money_data["Amount"].sum()
            st.metric("Total Balance", f"${total_balance:.2f}")
        else:
            st.metric("Total Balance", "$0.00")
    
    # Activity summary
    st.subheader("System Activity")
    if not st.session_state.activity_log.empty:
        # Show most recent activities
        recent_activity = st.session_state.activity_log.tail(10)
        st.dataframe(recent_activity, use_container_width=True)
    else:
        st.info("No activity logs available")
    
    # Group comparison
    st.subheader("Group Comparison")
    
    # Prepare comparison data
    group_data = []
    for group in GROUP_NAMES:
        members = len(st.session_state.groups.get(group, []))
        
        # Calculate attendance rate
        attendance_rate = 0
        if members > 0 and not st.session_state.attendance.empty and len(st.session_state.meeting_names) > 0:
            group_attendance = st.session_state.attendance[
                st.session_state.attendance["Name"].isin(st.session_state.groups[group])
            ]
            
            if not group_attendance.empty:
                total_attendances = group_attendance[st.session_state.meeting_names].sum().sum()
                possible_attendances = len(group_attendance) * len(st.session_state.meeting_names)
                attendance_rate = round((total_attendances / possible_attendances) * 100) if possible_attendances > 0 else 0
        
        # Calculate earnings
        earnings = 0
        if not st.session_state.group_earnings.empty:
            earnings = st.session_state.group_earnings[
                (st.session_state.group_earnings["Group"] == group) &
                (st.session_state.group_earnings["Verified"] == "Verified")
            ]["Amount"].sum()
        
        # Count events
        events = len(st.session_state.scheduled_events[
            st.session_state.scheduled_events["Responsible Group"] == group
        ]) if not st.session_state.scheduled_events.empty else 0
        
        events += len(st.session_state.occasional_events[
            st.session_state.occasional_events["Responsible Group"] == group
        ]) if not st.session_state.occasional_events.empty else 0
        
        group_data.append({
            "Group": group,
            "Members": members,
            "Attendance Rate": f"{attendance_rate}%",
            "Total Earnings": f"${earnings}",
            "Events Organized": events
        })
    
    # Display comparison table
    st.dataframe(group_data, use_container_width=True)
    
    # Create comparison chart
    fig, ax = plt.subplots(figsize=(12, 6))
    
    groups = [g["Group"] for g in group_data]
    earnings = [float(g["Total Earnings"].replace("$", "")) for g in group_data]
    events = [g["Events Organized"] for g in group_data]
    
    x = np.arange(len(groups))  # the label locations
    width = 0.35  # the width of the bars
    
    rects1 = ax.bar(x - width/2, earnings, width, label='Earnings ($)')
    rects2 = ax.bar(x + width/2, events, width, label='Events')
    
    ax.set_title('Group Performance Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.legend()
    
    st.pyplot(fig)
    
    # Pending items requiring attention
    st.subheader("Pending Items Requiring Attention")
    
    # Count pending requests
    pending_reimbursements = len(st.session_state.reimbursement_requests[
        st.session_state.reimbursement_requests["Status"] == "Pending"
    ]) if not st.session_state.reimbursement_requests.empty else 0
    
    pending_events = len(st.session_state.event_approval_requests[
        st.session_state.event_approval_requests["Status"] == "Pending"
    ]) if not st.session_state.event_approval_requests.empty else 0
    
    pending_earnings = len(st.session_state.group_earnings[
        st.session_state.group_earnings["Verified"] == "Pending"
    ]) if not st.session_state.group_earnings.empty else 0
    
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        st.metric("Pending Reimbursements", pending_reimbursements)
    with col_p2:
        st.metric("Pending Event Approvals", pending_events)
    with col_p3:
        st.metric("Pending Earnings Verification", pending_earnings)
    
    # Quick actions for admins
    st.subheader("Quick Actions")
    col_action1, col_action2, col_action3 = st.columns(3)
    
    with col_action1:
        if st.button("Manage Users", key="quick_manage_users"):
            st.session_state.active_tab = "user_management"
            st.rerun()
    
    with col_action2:
        if st.button("Approve Requests", key="quick_approve_requests"):
            st.session_state.active_tab = "approve_requests"
            st.rerun()
    
    with col_action3:
        if st.button("System Settings", key="quick_system_settings"):
            st.session_state.active_tab = "configuration"
            st.rerun()

def render_user_management():
    """Render user management page for admins"""
    st.header("User Management")
    
    # Only admins can access this page
    if not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    # Tab structure
    user_list_tab, create_user_tab, reset_password_tab = st.tabs(
        ["User List", "Create User", "Reset Password"]
    )
    
    with user_list_tab:
        st.subheader("System Users")
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            role_filter = st.selectbox("Filter by Role", ["All"] + ROLES, key="user_role_filter")
        
        with col2:
            group_filter = st.selectbox("Filter by Group", ["All"] + GROUP_NAMES, key="user_group_filter")
        
        # Apply filters
        filtered_users = []
        for username, details in st.session_state.users.items():
            role_match = role_filter == "All" or details["role"] == role_filter
            group_match = group_filter == "All" or details.get("group", "") == group_filter
            
            if role_match and group_match:
                last_login = details["last_login"] if details["last_login"] else "Never"
                filtered_users.append({
                    "Username": username,
                    "Role": details["role"].title(),
                    "Group": details.get("group", "N/A"),
                    "Created": details["created_at"][:10],
                    "Last Login": last_login[:10] if last_login != "Never" else "Never"
                })
        
        if not filtered_users:
            st.info("No users found matching your filters")
        else:
            # Display users
            st.dataframe(filtered_users, use_container_width=True)
            
            # User actions
            st.subheader("User Actions")
            user_to_manage = st.selectbox(
                "Select User",
                [u["Username"] for u in filtered_users],
                key="user_to_manage"
            )
            
            if user_to_manage:
                user_details = st.session_state.users[user_to_manage]
                
                # Change role
                new_role = st.selectbox(
                    "Change Role",
                    ROLES,
                    index=ROLES.index(user_details["role"]),
                    key="change_user_role"
                )
                
                # Change group
                current_group = user_details.get("group", "")
                group_index = GROUP_NAMES.index(current_group) if current_group in GROUP_NAMES else 0
                new_group = st.selectbox(
                    "Change Group",
                    GROUP_NAMES,
                    index=group_index,
                    key="change_user_group"
                )
                
                col_update, col_delete = st.columns(2)
                with col_update:
                    if st.button("Update User", key="update_user_btn"):
                        # Update role if changed
                        role_changed = new_role != user_details["role"]
                        group_changed = new_group != current_group
                        
                        if not role_changed and not group_changed:
                            st.info("No changes made to user")
                            return
                        
                        # Update role
                        if role_changed:
                            st.session_state.users[user_to_manage]["role"] = new_role
                            
                            # If demoting from group leader, update group leader
                            if new_role != "group_leader" and user_details["role"] == "group_leader":
                                for group, leader in st.session_state.group_leaders.items():
                                    if leader == user_to_manage:
                                        # Promote first member of group
                                        if st.session_state.groups[group]:
                                            new_leader = st.session_state.groups[group][0]
                                            st.session_state.group_leaders[group] = new_leader
                                            st.session_state.users[new_leader]["role"] = "group_leader"
                                        else:
                                            st.session_state.group_leaders[group] = ""
                        
                        # Update group if changed
                        if group_changed:
                            # Remove from current group
                            if current_group and current_group in st.session_state.groups:
                                if user_to_manage in st.session_state.groups[current_group]:
                                    st.session_state.groups[current_group].remove(user_to_manage)
                                    st.session_state.groups[current_group].sort()
                            
                            # Add to new group
                            if user_to_manage not in st.session_state.groups[new_group]:
                                st.session_state.groups[new_group].append(user_to_manage)
                                st.session_state.groups[new_group].sort()
                            
                            # Update user's group
                            st.session_state.users[user_to_manage]["group"] = new_group
                            
                            # If user is a leader, update their leadership
                            if user_details["role"] == "group_leader":
                                # Remove from previous group leadership if applicable
                                for group, leader in st.session_state.group_leaders.items():
                                    if leader == user_to_manage:
                                        st.session_state.group_leaders[group] = ""
                                
                                # Make them leader of new group
                                st.session_state.group_leaders[new_group] = user_to_manage
                        
                        # Save to Google Sheets
                        sheet = connect_gsheets()
                        success, msg = save_all_data(sheet)
                        if success:
                            log_activity(
                                "update_user", 
                                f"Updated {user_to_manage} - role: {new_role}, group: {new_group}"
                            )
                            st.success(f"Updated {user_to_manage} successfully")
                            st.rerun()
                        else:
                            st.error(f"Failed to update user: {msg}")
                
                with col_delete:
                    # Prevent deleting self
                    if user_to_manage == st.session_state.user:
                        st.button("Delete User", disabled=True, key="delete_self_btn")
                        st.warning("You cannot delete your own account")
                    else:
                        if st.button("Delete User", key="delete_user_btn", type="secondary"):
                            # Confirm deletion
                            confirm = st.checkbox("I confirm I want to delete this user", key="confirm_delete")
                            
                            if confirm and st.button("Yes, Delete Permanently", key="confirm_delete_btn"):
                                # Remove from group
                                user_group = user_details.get("group", "")
                                if user_group and user_group in st.session_state.groups:
                                    if user_to_manage in st.session_state.groups[user_group]:
                                        st.session_state.groups[user_group].remove(user_to_manage)
                                
                                # Remove from group leaders if applicable
                                for group, leader in st.session_state.group_leaders.items():
                                    if leader == user_to_manage:
                                        st.session_state.group_leaders[group] = ""
                                
                                # Remove user record
                                if user_to_manage in st.session_state.users:
                                    del st.session_state.users[user_to_manage]
                                
                                # Save to Google Sheets
                                sheet = connect_gsheets()
                                success, msg = save_all_data(sheet)
                                if success:
                                    log_activity("delete_user", f"Deleted user: {user_to_manage}")
                                    st.success(f"Deleted {user_to_manage} successfully")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to delete user: {msg}")
    
    with create_user_tab:
        st.subheader("Create New User")
        
        # Form fields
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username", key="admin_new_username")
            new_role = st.selectbox("Role", ROLES, key="admin_new_role")
        
        with col2:
            new_group = st.selectbox("Group", GROUP_NAMES, key="admin_new_group")
            new_password = st.text_input("Password", type="password", key="admin_new_password")
        
        # Password requirements info
        with st.expander("Password Requirements"):
            st.write(f"- At least {MIN_PASSWORD_LENGTH} characters")
            st.write("- At least one uppercase letter (A-Z)")
            st.write("- At least one lowercase letter (a-z)")
            st.write("- At least one number (0-9)")
            st.write("- At least one special character (!@#$%^&*(), etc.)")
        
        if st.button("Create User", key="admin_create_user_btn"):
            # Validate inputs
            if not new_username or not new_password:
                st.error("Please fill in all required fields")
                return
            
            # Validate password
            pass_valid, pass_msg = validate_password(new_password)
            if not pass_valid:
                st.error(pass_msg)
                return
            
            # Check if user already exists
            if new_username in st.session_state.users:
                st.error("Username already exists")
                return
            
            # Create user
            current_time = datetime.now().isoformat()
            st.session_state.users[new_username] = {
                "password_hash": hash_password(new_password),
                "role": new_role,
                "created_at": current_time,
                "last_login": None,
                "group": new_group
            }
            
            # Add to group
            if new_username not in st.session_state.groups[new_group]:
                st.session_state.groups[new_group].append(new_username)
                st.session_state.groups[new_group].sort()
            
            # If role is group leader, update group leaders
            if new_role == "group_leader":
                st.session_state.group_leaders[new_group] = new_username
            
            # Save to Google Sheets
            sheet = connect_gsheets()
            success, msg = save_all_data(sheet)
            if success:
                log_activity(
                    "admin_create_user", 
                    f"Created user {new_username} with role {new_role} in {new_group}"
                )
                st.success(f"Created user {new_username} successfully")
                
                # Clear form
                st.session_state.admin_new_username = ""
                st.session_state.admin_new_password = ""
            else:
                st.error(f"Failed to create user: {msg}")
    
    with reset_password_tab:
        st.subheader("Reset User Password")
        
        # Select user
        user_to_reset = st.selectbox(
            "Select User",
            sorted(st.session_state.users.keys()),
            key="user_to_reset"
        )
        
        new_password = st.text_input("New Password", type="password", key="admin_reset_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="admin_confirm_reset_password")
        
        if st.button("Reset Password", key="admin_reset_password_btn"):
            if not new_password or not confirm_password:
                st.error("Please fill in all password fields")
                return
            
            if new_password != confirm_password:
                st.error("Passwords do not match")
                return
            
            # Validate password
            pass_valid, pass_msg = validate_password(new_password)
            if not pass_valid:
                st.error(pass_msg)
                return
            
            # Update password
            st.session_state.users[user_to_reset]["password_hash"] = hash_password(new_password)
            
            # Save to Google Sheets
            sheet = connect_gsheets()
            success, msg = save_all_data(sheet)
            if success:
                log_activity("reset_password", f"Reset password for {user_to_reset}")
                st.success(f"Password for {user_to_reset} has been reset successfully")
                
                # Clear form
                st.session_state.admin_reset_password = ""
                st.session_state.admin_confirm_reset_password = ""
            else:
                st.error(f"Failed to reset password: {msg}")

def render_approve_requests():
    """Render page for admins to approve requests"""
    st.header("Approve Requests")
    
    # Only admins can access this page
    if not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    # Tab structure
    reimburse_tab, event_tab, earnings_tab = st.tabs(
        ["Reimbursements", "Event Approvals", "Earnings Verification"]
    )
    
    with reimburse_tab:
        st.subheader("Reimbursement Requests")
        
        # Filter options
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Pending", "Approved", "Denied"],
            key="reimburse_status_filter"
        )
        
        group_filter = st.selectbox(
            "Filter by Group",
            ["All"] + GROUP_NAMES,
            key="reimburse_approval_group_filter"
        )
        
        # Apply filters
        if not st.session_state.reimbursement_requests.empty:
            filtered_requests = st.session_state.reimbursement_requests.copy()
            
            if status_filter != "All":
                filtered_requests = filtered_requests[
                    filtered_requests["Status"] == status_filter
                ]
            
            if group_filter != "All":
                filtered_requests = filtered_requests[
                    filtered_requests["Group"] == group_filter
                ]
            
            if filtered_requests.empty:
                st.info("No reimbursement requests found matching your filters")
            else:
                st.dataframe(filtered_requests, use_container_width=True)
                
                # Approve/deny requests
                if status_filter in ["All", "Pending"]:
                    pending_requests = filtered_requests[filtered_requests["Status"] == "Pending"]
                    
                    if not pending_requests.empty:
                        st.subheader("Process Reimbursement Requests")
                        request_id = st.selectbox(
                            "Select Request to Process",
                            pending_requests["Request ID"],
                            format_func=lambda x: f"{x} - {pending_requests[pending_requests['Request ID'] == x]['Requester'].values[0]} - ${pending_requests[pending_requests['Request ID'] == x]['Amount'].values[0]}"
                        )
                        
                        new_status = st.selectbox(
                            "Set Status",
                            ["Approved", "Denied", "Returned for Revision"],
                            key="reimburse_new_status"
                        )
                        
                        admin_notes = st.text_area(
                            "Admin Notes",
                            placeholder="Provide a reason for approval/denial...",
                            key="reimburse_admin_notes"
                        )
                        
                        if st.button("Update Request", key="update_reimburse_request_btn"):
                            success, msg = update_request_status(
                                "reimbursement",
                                request_id,
                                new_status,
                                admin_notes
                            )
                            
                            if success:
                                # Save to Google Sheets
                                sheet = connect_gsheets()
                                save_all_data(sheet)
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        else:
            st.info("No reimbursement requests found in the system")
    
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
            key="event_approval_group_filter"
        )
        
        # Apply filters
        if not st.session_state.event_approval_requests.empty:
            filtered_requests = st.session_state.event_approval_requests.copy()
            
            if status_filter != "All":
                filtered_requests = filtered_requests[
                    filtered_requests["Status"] == status_filter
                ]
            
            if group_filter != "All":
                filtered_requests = filtered_requests[
                    filtered_requests["Group"] == group_filter
                ]
            
            if filtered_requests.empty:
                st.info("No event requests found matching your filters")
            else:
                st.dataframe(filtered_requests, use_container_width=True)
                
                # Approve/deny requests
                if status_filter in ["All", "Pending"]:
                    pending_requests = filtered_requests[filtered_requests["Status"] == "Pending"]
                    
                    if not pending_requests.empty:
                        st.subheader("Process Event Requests")
                        request_id = st.selectbox(
                            "Select Request to Process",
                            pending_requests["Request ID"],
                            format_func=lambda x: f"{x} - {pending_requests[pending_requests['Request ID'] == x]['Event Name'].values[0]} - {pending_requests[pending_requests['Request ID'] == x]['Proposed Date'].values[0]}"
                        )
                        
                        new_status = st.selectbox(
                            "Set Status",
                            ["Approved", "Denied", "In Review", "Returned for Revision"],
                            key="event_new_status"
                        )
                        
                        admin_notes = st.text_area(
                            "Admin Notes",
                            placeholder="Provide feedback or reasons for your decision...",
                            key="event_admin_notes"
                        )
                        
                        # Budget approval warning for large events
                        request_data = pending_requests[pending_requests["Request ID"] == request_id].iloc[0]
                        max_budget = st.session_state.config.get("max_event_budget", EVENT_BUDGET_LIMIT)
                        
                        if float(request_data["Budget"]) > max_budget and new_status == "Approved":
                            st.warning(f"This event exceeds the standard budget limit of ${max_budget}. Special approval is required.")
                            confirm_large = st.checkbox("I confirm this large budget is approved", key="confirm_large_budget")
                        else:
                            confirm_large = True
                        
                        if confirm_large and st.button("Update Request", key="update_event_request_btn"):
                            success, msg = update_request_status(
                                "event",
                                request_id,
                                new_status,
                                admin_notes
                            )
                            
                            if success:
                                # Save to Google Sheets
                                sheet = connect_gsheets()
                                save_all_data(sheet)
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        else:
            st.info("No event requests found in the system")
    
    with earnings_tab:
        st.subheader("Earnings Verification")
        
        # Filter options
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Pending", "Verified", "Rejected"],
            key="earnings_status_filter"
        )
        
        group_filter = st.selectbox(
            "Filter by Group",
            ["All"] + GROUP_NAMES,
            key="earnings_approval_group_filter"
        )
        
        # Apply filters
        if not st.session_state.group_earnings.empty:
            filtered_earnings = st.session_state.group_earnings.copy()
            
            if status_filter != "All":
                filtered_earnings = filtered_earnings[
                    filtered_earnings["Verified"] == status_filter
                ]
            
            if group_filter != "All":
                filtered_earnings = filtered_earnings[
                    filtered_earnings["Group"] == group_filter
                ]
            
            if filtered_earnings.empty:
                st.info("No earnings records found matching your filters")
            else:
                st.dataframe(filtered_earnings, use_container_width=True)
                
                # Verify earnings
                if status_filter in ["All", "Pending"]:
                    pending_earnings = filtered_earnings[filtered_earnings["Verified"] == "Pending"]
                    
                    if not pending_earnings.empty:
                        st.subheader("Verify Earnings Records")
                        earning_index = st.selectbox(
                            "Select Earnings to Verify",
                            pending_earnings.index,
                            format_func=lambda x: f"{pending_earnings.at[x, 'Group']}: ${pending_earnings.at[x, 'Amount']} - {pending_earnings.at[x, 'Description']}"
                        )
                        
                        verify_status = st.selectbox(
                            "Verification Status",
                            ["Verified", "Rejected"],
                            key="earnings_verify_status"
                        )
                        
                        admin_notes = st.text_input(
                            "Verification Notes",
                            key="earnings_verify_notes"
                        )
                        
                        if st.button("Update Verification", key="update_earnings_verification_btn"):
                            success, msg = verify_group_earning(earning_index, verify_status, admin_notes)
                            if success:
                                # Save to Google Sheets
                                sheet = connect_gsheets()
                                save_all_data(sheet)
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        else:
            st.info("No earnings records found in the system")

def render_configuration():
    """Render system configuration page for admins"""
    st.header("System Configuration")
    
    # Only admins can access this page
    if not is_admin():
        st.warning("You don't have permission to access this page")
        return
    
    # Only creator can see certain settings
    is_system_creator = is_creator()
    
    # Tab structure
    general_tab, financial_tab, notifications_tab, advanced_tab = st.tabs(
        ["General Settings", "Financial Settings", "Notifications", "Advanced"]
    )
    
    with general_tab:
        st.subheader("General System Settings")
        
        # Signup enabled
        show_signup = st.checkbox(
            "Allow new user signups",
            value=st.session_state.config.get("show_signup", True),
            key="config_show_signup"
        )
        
        # Meeting reminders
        meeting_reminder_days = st.number_input(
            "Send meeting reminders (days in advance)",
            min_value=0,
            max_value=7,
            value=st.session_state.config.get("meeting_reminder_days", 2),
            key="config_meeting_reminders"
        )
        
        # Default group size
        default_group_size = st.number_input(
            "Default maximum group size",
            min_value=3,
            max_value=20,
            value=st.session_state.config.get("default_group_size", 8),
            key="config_group_size"
        )
        
        if st.button("Save General Settings", key="save_general_settings"):
            st.session_state.config["show_signup"] = show_signup
            st.session_state.config["meeting_reminder_days"] = meeting_reminder_days
            st.session_state.config["default_group_size"] = default_group_size
            
            # Save to Google Sheets
            sheet = connect_gsheets()
            success, msg = save_all_data(sheet)
            if success:
                log_activity("update_config", "Updated general system settings")
                st.success("General settings saved successfully")
            else:
                st.error(f"Failed to save settings: {msg}")
    
    with financial_tab:
        st.subheader("Financial Configuration")
        
        # Reimbursement limit
        max_reimbursement = st.number_input(
            "Maximum reimbursement without special approval ($)",
            min_value=100,
            max_value=2000,
            value=st.session_state.config.get("max_reimbursement", REIMBURSEMENT_LIMIT),
            step=50,
            key="config_max_reimbursement"
        )
        
        # Event budget limit
        max_event_budget = st.number_input(
            "Maximum event budget without special approval ($)",
            min_value=500,
            max_value=10000,
            value=st.session_state.config.get("max_event_budget", EVENT_BUDGET_LIMIT),
            step=100,
            key="config_max_event_budget"
        )
        
        # Small purchases
        auto_approve_small = st.checkbox(
            "Auto-approve small purchases",
            value=st.session_state.config.get("auto_approve_small_purchases", True),
            key="config_auto_approve_small"
        )
        
        small_purchase_limit = st.number_input(
            "Small purchase limit ($)",
            min_value=25,
            max_value=500,
            value=st.session_state.config.get("small_purchase_limit", 100),
            step=25,
            key="config_small_purchase_limit",
            disabled=not auto_approve_small
        )
        
        if st.button("Save Financial Settings", key="save_financial_settings"):
            st.session_state.config["max_reimbursement"] = max_reimbursement
            st.session_state.config["max_event_budget"] = max_event_budget
            st.session_state.config["auto_approve_small_purchases"] = auto_approve_small
            st.session_state.config["small_purchase_limit"] = small_purchase_limit
            
            # Save to Google Sheets
            sheet = connect_gsheets()
            success, msg = save_all_data(sheet)
            if success:
                log_activity("update_config", "Updated financial system settings")
                st.success("Financial settings saved successfully")
            else:
                st.error(f"Failed to save settings: {msg}")
    
    with notifications_tab:
        st.subheader("Notification Settings")
        
        st.info("Configure when system notifications should be sent to users")
        
        # Meeting reminders
        st.checkbox(
            "Send reminders for upcoming meetings",
            value=True,
            key="notify_meetings"
        )
        
        # Request status changes
        st.checkbox(
            "Notify when request status changes",
            value=True,
            key="notify_requests"
        )
        
        # New announcements
        st.checkbox(
            "Notify about new announcements",
            value=True,
            key="notify_announcements"
        )
        
        # Low credits warning
        low_credit_threshold = st.number_input(
            "Low credit threshold (send warning below this amount)",
            min_value=10,
            max_value=100,
            value=30,
            key="low_credit_threshold"
        )
        
        if st.button("Save Notification Settings", key="save_notification_settings"):
            st.session_state.config["low_credit_threshold"] = low_credit_threshold
            # In a full implementation, other notification settings would be saved here
            
            # Save to Google Sheets
            sheet = connect_gsheets()
            success, msg = save_all_data(sheet)
            if success:
                log_activity("update_config", "Updated notification settings")
                st.success("Notification settings saved successfully")
            else:
                st.error(f"Failed to save settings: {msg}")
    
    with advanced_tab:
        st.subheader("Advanced Settings")
        
        if not is_system_creator:
            st.warning("Only the system creator can access advanced settings")
            return
        
        st.warning("Advanced settings can affect system stability. Use with caution.")
        
        # Data management
        with st.expander("Data Management", expanded=False):
            st.write("Perform system-wide data operations")
            
            col_export, col_import = st.columns(2)
            
            with col_export:
                if st.button("Export All Data", key="export_data_btn"):
                    # In a full implementation, this would export data to a file
                    st.info("Data export functionality would be implemented here")
            
            with col_import:
                data_file = st.file_uploader("Import Data", key="import_data_file")
                if data_file and st.button("Import Data", key="import_data_btn"):
                    st.warning("Data import can overwrite existing data. Proceed with caution.")
                    confirm_import = st.checkbox("I confirm I want to import data", key="confirm_import")
                    if confirm_import:
                        # In a full implementation, this would import data from a file
                        st.info("Data import functionality would be implemented here")
        
        # System reset
        with st.expander("System Maintenance", expanded=False):
            st.write("Perform system maintenance tasks")
            
            if st.button("Clear Activity Log", key="clear_activity_log_btn"):
                confirm_clear = st.checkbox("I confirm I want to clear the activity log", key="confirm_clear_log")
                if confirm_clear:
                    st.session_state.activity_log = pd.DataFrame(columns=["Timestamp", "User", "Action", "Details", "IP Address"])
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    success, msg = save_all_data(sheet)
                    if success:
                        log_activity("system_maintenance", "Cleared activity log")
                        st.success("Activity log cleared successfully")
                    else:
                        st.error(f"Failed to clear log: {msg}")
            
            # Danger zone
            st.subheader("Danger Zone")
            st.warning("These operations cannot be undone!")
            
            if st.button("Reset All Data", key="reset_all_data_btn", type="secondary"):
                st.error("This will erase all system data and reset to defaults!")
                confirm_reset = st.checkbox("I understand the consequences", key="confirm_reset")
                
                if confirm_reset and st.button("Yes, Reset Everything", key="confirm_reset_btn"):
                    # Reinitialize default data
                    initialize_default_data()
                    
                    # Save to Google Sheets
                    sheet = connect_gsheets()
                    success, msg = save_all_data(sheet)
                    if success:
                        log_activity("system_maintenance", "Performed full system reset")
                        st.success("System reset to default state")
                    else:
                        st.error(f"Reset failed: {msg}")

# ------------------------------
# Main Application Flow
# ------------------------------
def main():
    """Main application function"""
    # Initialize session state
    initialize_session_state()
    
    # Connect to Google Sheets
    sheet = connect_gsheets()
    
    # Load data if we have a connection, otherwise use defaults
    if sheet:
        with st.spinner("Loading data..."):
            success, msg = load_all_data(sheet)
            if not success:
                st.warning(f"Could not load data: {msg}. Using default data instead.")
                initialize_default_data()
    else:
        st.warning("No connection to Google Sheets. Using local default data.")
        initialize_default_data()
    
    # Handle authentication
    if not st.session_state.user:
        # Show login/signup screen
        login_success = render_login_signup()
        if not login_success:
            return
    
    # Render main application interface
    render_header()
    render_sidebar()
    
    # Display appropriate content based on active tab
    if st.session_state.active_tab == "dashboard":
        render_dashboard()
    elif st.session_state.active_tab == "attendance":
        render_attendance()
    elif st.session_state.active_tab == "events":
        render_events()
    elif st.session_state.active_tab == "finances":
        render_finances()
    elif st.session_state.active_tab == "credits":
        render_credits()
    elif st.session_state.active_tab == "group_management":
        render_group_management()
    elif st.session_state.active_tab == "submit_requests":
        render_submit_requests()
    elif st.session_state.active_tab == "admin_dashboard":
        render_admin_dashboard()
    elif st.session_state.active_tab == "user_management":
        render_user_management()
    elif st.session_state.active_tab == "approve_requests":
        render_approve_requests()
    elif st.session_state.active_tab == "configuration":
        render_configuration()
    
    # Auto-save data periodically if we have a connection
    if sheet and "last_saved" not in st.session_state:
        st.session_state.last_saved = datetime.now()
    elif sheet:
        time_since_save = (datetime.now() - st.session_state.last_saved).total_seconds()
        if time_since_save > 300:  # Save every 5 minutes
            with st.spinner("Auto-saving data..."):
                success, msg = save_all_data(sheet)
                if success:
                    st.session_state.last_saved = datetime.now()
                    # Show a temporary success message
                    with st.empty():
                        st.success("Data auto-saved successfully")
                        time.sleep(2)
                        st.empty()

if __name__ == "__main__":
    main()
