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
import base64
import io
from collections import defaultdict

# ------------------------------
# Application Configuration
# ------------------------------
APP_TITLE = "Student Council Management System"
APP_ICON = "📊"
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
DATA_FILE = os.path.join(DATA_DIR, "app_data.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LOG_FILE = os.path.join(DATA_DIR, "activity_logs.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Role definitions
ROLES = {
    "user": "Regular User",
    "admin": "Administrator",
    "credit_manager": "Credit Manager",
    "creator": "System Creator"
}

# ------------------------------
# Logging System
# ------------------------------
def log_activity(action, details=""):
    """Log user activities for audit purposes"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user": st.session_state.get("user", "anonymous"),
        "role": st.session_state.get("role", "unknown"),
        "action": action,
        "details": details
    }
    
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                logs = json.load(f)
        else:
            logs = []
            
        logs.append(log_entry)
        
        # Keep only last 1000 logs to prevent file bloat
        if len(logs) > 1000:
            logs = logs[-1000:]
            
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        st.error(f"Error logging activity: {str(e)}")

# ------------------------------
# Configuration Management
# ------------------------------
def load_config():
    """Load application configuration"""
    default_config = {
        "show_signup": False,
        "max_announcement_length": 500,
        "default_currency": "USD",
        "meeting_limit": 50
    }
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            # Merge with defaults to ensure all keys exist
            return {**default_config,** config}
        return default_config
    except Exception as e:
        st.error(f"Error loading configuration: {str(e)}")
        return default_config

def save_config(config):
    """Save application configuration"""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving configuration: {str(e)}")
        return False

# ------------------------------
# User Authentication & Management
# ------------------------------
def hash_password(password):
    """Hash a password for storage"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def load_users():
    """Load user data from file"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
            # Validate user data structure
            valid_users = {}
            for username, data in users.items():
                if all(k in data for k in ["password_hash", "role", "created_at"]):
                    valid_users[username] = data
                else:
                    st.warning(f"Invalid user data for {username}, skipping")
            return valid_users
        return {}
    except Exception as e:
        st.error(f"Error loading users: {str(e)}")
        return {}

def save_user(username, password, role="user"):
    """Create a new user"""
    if role not in ROLES:
        return False, f"Invalid role. Valid roles: {', '.join(ROLES.keys())}"
        
    users = load_users()
    if username in users:
        return False, "Username already exists"
    
    try:
        users[username] = {
            "password_hash": hash_password(password),
            "role": role,
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
            
        log_activity("user_created", f"Created user {username} with role {role}")
        return True, "User created successfully"
    except Exception as e:
        return False, f"Error saving user: {str(e)}"

def update_user(username, data):
    """Update existing user data"""
    users = load_users()
    if username not in users:
        return False, "User not found"
    
    try:
        users[username].update(data)
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
        log_activity("user_updated", f"Updated user {username}")
        return True, "User updated successfully"
    except Exception as e:
        return False, f"Error updating user: {str(e)}"

def delete_user(username):
    """Delete a user"""
    # Prevent deleting the creator account
    if username == st.secrets.get("creator", {}).get("username"):
        return False, "Cannot delete creator account"
        
    users = load_users()
    if username not in users:
        return False, "User not found"
    
    try:
        del users[username]
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
        log_activity("user_deleted", f"Deleted user {username}")
        return True, "User deleted successfully"
    except Exception as e:
        return False, f"Error deleting user: {str(e)}"

def login_user(username, password):
    """Authenticate a user and set session state"""
    # Check creator credentials first
    creator_username = st.secrets.get("creator", {}).get("username", "")
    creator_password = st.secrets.get("creator", {}).get("password", "")
    
    if username == creator_username and password == creator_password and creator_username:
        st.session_state.user = username
        st.session_state.role = "creator"
        log_activity("login", "Creator login")
        return True, f"Logged in as {username} (Creator)"
    
    # Check regular users
    users = load_users()
    if username in users:
        if verify_password(password, users[username]["password_hash"]):
            # Update last login time
            update_user(username, {"last_login": datetime.now().isoformat()})
            
            st.session_state.user = username
            st.session_state.role = users[username]["role"]
            log_activity("login", f"User {username} logged in")
            return True, f"Logged in as {username} ({ROLES[users[username]['role']]})"
        else:
            log_activity("login_failed", f"Incorrect password for {username}")
            return False, "Incorrect password"
    else:
        log_activity("login_failed", f"Username {username} not found")
        return False, "Username not found"

def logout_user():
    """Log out the current user"""
    username = st.session_state.get("user", "unknown")
    log_activity("logout", f"User {username} logged out")
    st.session_state.user = None
    st.session_state.role = None
    st.session_state.clear()  # Clear all session state data
    st.session_state.user = None
    st.session_state.role = None

# ------------------------------
# Data Management
# ------------------------------
def initialize_data():
    """Initialize empty data structures"""
    return {
        "scheduled_events": pd.DataFrame(columns=[
            'Event Name', 'Funds Per Event', 'Frequency Per Month', 
            'Total Funds', 'Last Updated'
        ]),
        "occasional_events": pd.DataFrame(columns=[
            'Event Name', 'Total Funds Raised', 'Cost', 'Staff Required', 
            'Preparation Time (days)', 'Rating', 'Last Updated'
        ]),
        "credit_data": pd.DataFrame({
            'Name': ['Alice', 'Bob', 'Charlie', 'Diana'],
            'Total_Credits': [200, 150, 300, 100],
            'RedeemedCredits': [50, 0, 100, 20],
            'Last_Updated': [datetime.now().isoformat() for _ in range(4)]
        }),
        "reward_data": pd.DataFrame({
            'Reward': ['Bubble Tea', 'Chips', 'Café Coupon', 'Movie Ticket'],
            'Cost': [50, 30, 80, 120],
            'Stock': [10, 20, 5, 3],
            'Last_Updated': [datetime.now().isoformat() for _ in range(4)]
        }),
        "calendar_events": {},
        "announcements": [],
        "money_data": pd.DataFrame(columns=['Amount', 'Description', 'Date', 'Type']),
        "meeting_names": ["First Meeting", "Second Meeting"],
        "attendance": pd.DataFrame({
            'Name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
            'First Meeting': [True, False, True, True, False],
            'Second Meeting': [True, True, False, True, True]
        }),
        "wheel_prizes": ["50 Credits", "Bubble Tea", "Chips", "100 Credits", "Café Coupon", "Free Prom Ticket"],
        "wheel_colors": plt.cm.tab10(np.linspace(0, 1, 6)).tolist()
    }

def load_app_data():
    """Load application data from file"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            
            # Convert JSON data back to DataFrames
            result = {}
            
            # Scheduled Events
            result["scheduled_events"] = pd.DataFrame(data.get("scheduled_events", []))
            
            # Occasional Events
            result["occasional_events"] = pd.DataFrame(data.get("occasional_events", []))
            
            # Credit Data
            result["credit_data"] = pd.DataFrame(data.get("credit_data", []))
            
            # Reward Data
            result["reward_data"] = pd.DataFrame(data.get("reward_data", []))
            
            # Calendar Events
            result["calendar_events"] = data.get("calendar_events", {})
            
            # Announcements
            result["announcements"] = data.get("announcements", [])
            
            # Money Data
            result["money_data"] = pd.DataFrame(data.get("money_data", []))
            
            # Meeting Names
            result["meeting_names"] = data.get("meeting_names", [])
            
            # Attendance
            result["attendance"] = pd.DataFrame(data.get("attendance", []))
            
            # Wheel Data
            result["wheel_prizes"] = data.get("wheel_prizes", [])
            result["wheel_colors"] = data.get("wheel_colors", [])
            
            return result
        else:
            # Initialize with default data if file doesn't exist
            return initialize_data()
    except Exception as e:
        st.error(f"Error loading application data: {str(e)}")
        # Return default data on error
        return initialize_data()

def save_app_data(data):
    """Save application data to file"""
    try:
        # Convert DataFrames to JSON-serializable formats
        data_to_save = {
            "scheduled_events": data["scheduled_events"].to_dict(orient="records"),
            "occasional_events": data["occasional_events"].to_dict(orient="records"),
            "credit_data": data["credit_data"].to_dict(orient="records"),
            "reward_data": data["reward_data"].to_dict(orient="records"),
            "calendar_events": data["calendar_events"],
            "announcements": data["announcements"],
            "money_data": data["money_data"].to_dict(orient="records"),
            "meeting_names": data["meeting_names"],
            "attendance": data["attendance"].to_dict(orient="records"),
            "wheel_prizes": data["wheel_prizes"],
            "wheel_colors": data["wheel_colors"]
        }
        
        with open(DATA_FILE, "w") as f:
            json.dump(data_to_save, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving application data: {str(e)}")
        return False

# ------------------------------
# Permission Utilities
# ------------------------------
def has_permission(required_role):
    """Check if current user has required permissions"""
    user_role = st.session_state.get("role", "")
    
    # Creator has all permissions
    if user_role == "creator":
        return True
        
    # Admin has permissions for admin and below
    if user_role == "admin" and required_role in ["admin", "credit_manager", "user"]:
        return True
        
    # Credit manager has permissions for credit_manager and user
    if user_role == "credit_manager" and required_role in ["credit_manager", "user"]:
        return True
        
    # Regular user only has user permissions
    return user_role == "user" and required_role == "user"

def is_admin():
    """Check if user is admin or creator"""
    return has_permission("admin")

def is_credit_manager():
    """Check if user is credit manager, admin, or creator"""
    return has_permission("credit_manager")

# ------------------------------
# UI Components & Helpers
# ------------------------------
def display_role_badge():
    """Display styled role badge"""
    role = st.session_state.get("role", "unknown")
    role_styles = {
        "user": "background-color: #e0e0e0; color: #333;",
        "admin": "background-color: #e8f5e9; color: #2e7d32;",
        "credit_manager": "background-color: #e3f2fd; color: #1976d2;",
        "creator": "background-color: #fff3e0; color: #e65100;",
        "unknown": "background-color: #f5f5f5; color: #757575;"
    }
    
    display_role = role if role in role_styles else "unknown"
    st.markdown(
        f'<span class="role-badge" style="{role_styles[display_role]}">{ROLES.get(display_role, display_role.capitalize())}</span>',
        unsafe_allow_html=True
    )

def draw_wheel(rotation_angle=0):
    """Draw the lucky draw wheel"""
    prizes = st.session_state.app_data["wheel_prizes"]
    colors = st.session_state.app_data["wheel_colors"]
    
    # Ensure we have enough colors
    if len(colors) < len(prizes):
        colors = plt.cm.tab10(np.linspace(0, 1, len(prizes))).tolist()
        st.session_state.app_data["wheel_colors"] = colors
        save_app_data(st.session_state.app_data)
    
    n = len(prizes)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_aspect('equal')
    ax.axis('off')

    for i in range(n):
        start_angle = np.rad2deg(2 * np.pi * i / n + rotation_angle)
        end_angle = np.rad2deg(2 * np.pi * (i + 1) / n + rotation_angle)
        wedge = Wedge(center=(0, 0), r=1, theta1=start_angle, theta2=end_angle, 
                      width=1, facecolor=colors[i], edgecolor='black', linewidth=1)
        ax.add_patch(wedge)

        # Add prize text
        mid_angle = np.deg2rad((start_angle + end_angle) / 2)
        text_x = 0.7 * np.cos(mid_angle)
        text_y = 0.7 * np.sin(mid_angle)
        ax.text(text_x, text_y, prizes[i],
                ha='center', va='center', rotation=np.rad2deg(mid_angle) - 90,
                fontsize=8, wrap=True)

    # Add center circle and pointer
    circle = plt.Circle((0, 0), 0.1, color='white', edgecolor='black', linewidth=1)
    ax.add_patch(circle)
    ax.plot([0, 0], [0, 0.9], color='black', linewidth=2)
    ax.plot([-0.05, 0.05], [0.85, 0.9], color='black', linewidth=2)
    
    return fig

def generate_calendar_grid():
    """Generate calendar grid for current month"""
    today = date.today()
    year, month = today.year, today.month
    
    # Get first and last days of the month
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year, 12, 31)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    # Get weekday of first day (0 = Monday, 6 = Sunday)
    first_day_weekday = first_day.weekday()
    
    # Calculate total days and grid size
    total_days = (last_day - first_day).days + 1
    total_slots = first_day_weekday + total_days
    rows = (total_slots + 6) // 7  # Round up to nearest week
    
    # Generate date grid
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
    """Calculate attendance rates for all members"""
    if not st.session_state.app_data["meeting_names"]:
        return pd.DataFrame({
            'Name': st.session_state.app_data["attendance"]['Name'],
            'Attendance Rate (%)': [0.0 for _ in range(len(st.session_state.app_data["attendance"]))]
        })
    
    rates = []
    for _, row in st.session_state.app_data["attendance"].iterrows():
        attended = 0
        total = 0
        for meeting in st.session_state.app_data["meeting_names"]:
            if meeting in row and pd.notna(row[meeting]):
                attended += 1 if row[meeting] else 0
                total += 1
        
        rate = (attended / total) * 100 if total > 0 else 0
        rates.append(round(rate, 1))
    
    return pd.DataFrame({
        'Name': st.session_state.app_data["attendance"]['Name'],
        'Attendance Rate (%)': rates
    })

def export_to_excel(df, filename="data_export.xlsx"):
    """Export DataFrame to Excel and return download link"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    
    b64 = base64.b64encode(output.getvalue()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Download Excel File</a>'
    return href

# ------------------------------
# Main Application Functions
# ------------------------------
def render_login_sidebar():
    """Render login form in sidebar"""
    with st.sidebar:
        st.subheader("Account Login")
        
        # Login form
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        col_login, col_clear = st.columns(2)
        with col_login:
            if st.button("Login", key="login_btn", use_container_width=True):
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    success, message = login_user(username, password)
                    if success:
                        st.success(message)
                        log_activity("login_attempt", f"Successful login for {username}")
                        st.rerun()
                    else:
                        st.error(message)
                        log_activity("login_attempt", f"Failed login for {username}: {message}")
        
        with col_clear:
            if st.button("Clear", key="clear_login_btn", use_container_width=True):
                st.session_state.login_username = ""
                st.session_state.login_password = ""
        
        # Signup option if enabled
        config = load_config()
        if config.get("show_signup", False):
            with st.expander("Create New Account", expanded=False):
                st.subheader("Sign Up")
                new_username = st.text_input("Choose Username", key="signup_username")
                new_password = st.text_input("Choose Password", type="password", key="signup_password")
                confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm")
                
                if st.button("Create Account", key="signup_btn"):
                    if not new_username or not new_password:
                        st.error("Please fill in all fields")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        success, message = save_user(new_username, new_password)
                        if success:
                            st.success(f"{message} You can now log in.")
                        else:
                            st.error(message)
        
        st.divider()
        st.info("Contact system administrator for account assistance")

def render_user_sidebar():
    """Render sidebar for logged-in users"""
    with st.sidebar:
        # User info
        st.subheader(f"Welcome, {st.session_state.user}")
        display_role_badge()
        
        # Logout button
        if st.button("Logout", key="logout_btn", use_container_width=True):
            logout_user()
            st.success("Logged out successfully")
            st.rerun()
        
        st.divider()
        
        # Creator-only controls
        if st.session_state.role == "creator":
            st.subheader("System Settings")
            
            # Signup toggle
            config = load_config()
            new_signup_state = st.checkbox(
                "Enable User Signup", 
                value=config.get("show_signup", False),
                key="toggle_signup"
            )
            
            if new_signup_state != config.get("show_signup", False):
                config["show_signup"] = new_signup_state
                if save_config(config):
                    st.success(f"Signup has been {'enabled' if new_signup_state else 'disabled'}")
                    st.rerun()
            
            st.divider()
            
            # User management
            st.subheader("User Management")
            users = load_users()
            
            # Add new user
            with st.expander("Add New User", expanded=False):
                new_username = st.text_input("New Username", key="new_username")
                new_password = st.text_input("New Password", type="password", key="new_password")
                new_role = st.selectbox(
                    "User Role", 
                    list(ROLES.keys()), 
                    index=0,
                    key="new_user_role"
                )
                
                if st.button("Create User", key="create_user_btn"):
                    if new_username and new_password:
                        success, message = save_user(new_username, new_password, new_role)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Please fill in all fields")
            
            # Manage existing users
            if users:
                st.subheader("Manage Existing Users")
                user_list = list(users.keys())
                selected_user = st.selectbox("Select User", user_list, key="selected_user")
                
                if selected_user:
                    user_data = users[selected_user]
                    
                    # Display user info
                    st.write(f"**Role:** {ROLES.get(user_data['role'], user_data['role'])}")
                    st.write(f"**Created:** {datetime.fromisoformat(user_data['created_at']).strftime('%Y-%m-%d')}")
                    if user_data['last_login']:
                        st.write(f"**Last Login:** {datetime.fromisoformat(user_data['last_login']).strftime('%Y-%m-%d %H:%M')}")
                    else:
                        st.write("**Last Login:** Never")
                    
                    # Update role
                    new_role = st.selectbox(
                        "Update Role", 
                        list(ROLES.keys()), 
                        index=list(ROLES.keys()).index(user_data['role']),
                        key="update_user_role"
                    )
                    
                    col_update, col_delete = st.columns(2)
                    with col_update:
                        if st.button("Update Role", key="update_role_btn"):
                            if new_role != user_data['role']:
                                success, message = update_user(selected_user, {"role": new_role})
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
                    
                    with col_delete:
                        if st.button("Delete User", key="delete_user_btn", type="secondary"):
                            if st.warning("Are you sure you want to delete this user?"):
                                success, message = delete_user(selected_user)
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
            else:
                st.info("No users found in the system")
            
            st.divider()
            
            # Activity logs
            with st.expander("View Activity Logs", expanded=False):
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, "r") as f:
                        logs = json.load(f)
                    
                    # Show most recent logs first
                    logs.reverse()
                    
                    # Filter by user
                    log_user = st.selectbox("Filter by user", ["All Users"] + list(load_users().keys()), key="log_user")
                    
                    # Display logs
                    count = 0
                    for log in logs:
                        if log_user == "All Users" or log["user"] == log_user:
                            st.write(f"**{datetime.fromisoformat(log['timestamp']).strftime('%Y-%m-%d %H:%M')}** - {log['user']} ({log['role']}): {log['action']}")
                            if log["details"]:
                                st.caption(f"Details: {log['details']}")
                            count += 1
                            if count >= 20:  # Limit to 20 logs
                                break
                else:
                    st.info("No activity logs available")
        
        # Admin-only controls
        if is_admin() and st.session_state.role != "creator":
            st.subheader("Admin Controls")
            st.info("Manage system settings and users here")

def render_calendar_tab():
    """Render Calendar tab"""
    st.subheader("📅 Calendar & Events")
    
    # Generate and display calendar
    grid, month, year = generate_calendar_grid()
    st.subheader(f"{datetime(year, month, 1).strftime('%B %Y')}")
    
    # Day headers
    headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for col, header in zip(header_cols, headers):
        col.markdown(f'<div class="day-header">{header}</div>', unsafe_allow_html=True)
    
    # Calendar days
    today = date.today()
    for week in grid:
        day_cols = st.columns(7)
        for col, dt in zip(day_cols, week):
            date_str = dt.strftime("%Y-%m-%d")
            day_display = dt.day
            
            # Determine CSS class
            css_class = "calendar-day "
            if dt.month != month:
                css_class += "other-month "
            elif dt == today:
                css_class += "today "
            
            # Get event for this date
            event_text = st.session_state.app_data["calendar_events"].get(date_str, "")
            event_html = f'<div class="event-text">{event_text}</div>' if event_text else ""
            
            # Display day
            col.markdown(
                f'<div class="{css_class}"><strong>{day_display}</strong>{event_html}</div>',
                unsafe_allow_html=True
            )
    
    # Event management for admins
    if is_admin():
        with st.expander("Manage Calendar Events (Admin Only)", expanded=False):
            st.subheader("Add/Edit Event")
            
            event_date = st.date_input("Select Date", today)
            date_str = event_date.strftime("%Y-%m-%d")
            current_event = st.session_state.app_data["calendar_events"].get(date_str, "")
            
            event_text = st.text_input(
                "Event Description", 
                current_event,
                max_chars=100,
                help="Enter a brief description of the event (max 100 characters)"
            )
            
            col_save, col_delete = st.columns(2)
            with col_save:
                if st.button("Save Event"):
                    if event_text:
                        st.session_state.app_data["calendar_events"][date_str] = event_text
                        save_app_data(st.session_state.app_data)
                        log_activity("calendar_event_saved", f"Event on {date_str}: {event_text}")
                        st.success(f"Event saved for {event_date.strftime('%B %d, %Y')}")
                    else:
                        st.warning("Event description cannot be empty")
            
            with col_delete:
                if st.button("Delete Event", type="secondary") and date_str in st.session_state.app_data["calendar_events"]:
                    del st.session_state.app_data["calendar_events"][date_str]
                    save_app_data(st.session_state.app_data)
                    log_activity("calendar_event_deleted", f"Event deleted for {date_str}")
                    st.success(f"Event deleted for {event_date.strftime('%B %d, %Y')}")

def render_announcements_tab():
    """Render Announcements tab"""
    st.subheader("📢 Announcements")
    
    # Display announcements
    if st.session_state.app_data["announcements"]:
        # Sort by most recent first
        sorted_announcements = sorted(
            st.session_state.app_data["announcements"],
            key=lambda x: x["timestamp"],
            reverse=True
        )
        
        for idx, ann in enumerate(sorted_announcements):
            col_content, col_actions = st.columns([5, 1])
            
            with col_content:
                st.info(f"**{datetime.fromisoformat(ann['timestamp']).strftime('%B %d, %Y - %H:%M')}**\n\n{ann['content']}")
            
            with col_actions:
                if is_admin():
                    if st.button("Delete", key=f"del_ann_{idx}", type="secondary"):
                        st.session_state.app_data["announcements"].pop(idx)
                        save_app_data(st.session_state.app_data)
                        log_activity("announcement_deleted", f"Deleted announcement from {ann['timestamp']}")
                        st.success("Announcement deleted")
                        st.rerun()
            
            if idx < len(sorted_announcements) - 1:
                st.divider()
    else:
        st.info("No announcements have been posted yet.")
    
    # Add new announcement (admin only)
    if is_admin():
        with st.expander("Create New Announcement (Admin Only)", expanded=False):
            st.subheader("New Announcement")
            config = load_config()
            announcement_content = st.text_area(
                "Announcement Text",
                "",
                max_chars=config.get("max_announcement_length", 500),
                height=150
            )
            
            if st.button("Post Announcement"):
                if announcement_content.strip():
                    new_announcement = {
                        "timestamp": datetime.now().isoformat(),
                        "content": announcement_content.strip(),
                        "author": st.session_state.user
                    }
                    
                    st.session_state.app_data["announcements"].append(new_announcement)
                    save_app_data(st.session_state.app_data)
                    log_activity("announcement_created", "New announcement posted")
                    st.success("Announcement posted successfully!")
                else:
                    st.error("Announcement cannot be empty")

def render_financial_tab():
    """Render Financial Optimization tab"""
    st.subheader("💰 Financial Management")
    
    # Financial summary
    col1, col2 = st.columns(2)
    with col1:
        current_funds = st.number_input(
            "Current Funds Raised", 
            value=0.0, 
            step=100.0,
            format="%.2f"
        )
    with col2:
        target_funds = st.number_input(
            "Fundraising Target", 
            value=10000.0, 
            step=1000.0,
            format="%.2f"
        )
    
    # Progress indicator
    if target_funds > 0:
        progress = min(100.0, (current_funds / target_funds) * 100)
        st.progress(progress / 100)
        st.caption(f"Progress: {progress:.1f}% of target")
    else:
        st.warning("Please set a valid fundraising target greater than 0")
    
    st.divider()
    
    # Scheduled and occasional events
    col_scheduled, col_occasional = st.columns(2)
    
    with col_scheduled:
        st.subheader("Scheduled Events")
        st.dataframe(
            st.session_state.app_data["scheduled_events"],
            use_container_width=True,
            hide_index=True
        )
        
        # Calculate totals
        total_scheduled = st.session_state.app_data["scheduled_events"]["Total Funds"].sum() if not st.session_state.app_data["scheduled_events"].empty else 0
        st.metric("Total Projected Funds", f"${total_scheduled:,.2f}")
        
        # Add/edit scheduled events (admin only)
        if is_admin():
            with st.expander("Add Scheduled Event", expanded=False):
                event_name = st.text_input("Event Name", "Monthly Fundraiser")
                funds_per = st.number_input("Funds Per Event", value=500.0, step=100.0)
                frequency = st.number_input("Frequency Per Month", value=1, step=1, min_value=1)
                
                if st.button("Add Event"):
                    if event_name and funds_per > 0 and frequency > 0:
                        total = funds_per * frequency * 12  # Annual projection
                        new_event = pd.DataFrame({
                            'Event Name': [event_name],
                            'Funds Per Event': [funds_per],
                            'Frequency Per Month': [frequency],
                            'Total Funds': [total],
                            'Last Updated': [datetime.now().isoformat()]
                        })
                        
                        st.session_state.app_data["scheduled_events"] = pd.concat(
                            [st.session_state.app_data["scheduled_events"], new_event],
                            ignore_index=True
                        )
                        
                        save_app_data(st.session_state.app_data)
                        log_activity("scheduled_event_added", f"Added event: {event_name}")
                        st.success(f"Added {event_name} successfully!")
                    else:
                        st.error("Please fill in all fields with valid values")
            
            # Delete scheduled event
            if not st.session_state.app_data["scheduled_events"].empty:
                with st.expander("Manage Scheduled Events", expanded=False):
                    event_to_delete = st.selectbox(
                        "Select Event to Delete",
                        st.session_state.app_data["scheduled_events"]["Event Name"]
                    )
                    
                    if st.button("Delete Selected Event", type="secondary"):
                        st.session_state.app_data["scheduled_events"] = st.session_state.app_data["scheduled_events"][
                            st.session_state.app_data["scheduled_events"]["Event Name"] != event_to_delete
                        ].reset_index(drop=True)
                        
                        save_app_data(st.session_state.app_data)
                        log_activity("scheduled_event_deleted", f"Deleted event: {event_to_delete}")
                        st.success(f"Deleted {event_to_delete} successfully!")
    
    with col_occasional:
        st.subheader("Occasional Events")
        st.dataframe(
            st.session_state.app_data["occasional_events"],
            use_container_width=True,
            hide_index=True
        )
        
        # Calculate totals
        if not st.session_state.app_data["occasional_events"].empty:
            net_profit = (st.session_state.app_data["occasional_events"]["Total Funds Raised"] - 
                         st.session_state.app_data["occasional_events"]["Cost"]).sum()
            st.metric("Total Net Profit", f"${net_profit:,.2f}")
        else:
            st.metric("Total Net Profit", "$0.00")
        
        # Add occasional event (admin only)
        if is_admin():
            with st.expander("Add Occasional Event", expanded=False):
                event_name = st.text_input("Event Name", "Charity Gala", key="occ_event_name")
                funds_raised = st.number_input("Funds Raised", value=2000.0, step=100.0, key="occ_funds")
                cost = st.number_input("Total Cost", value=500.0, step=100.0, key="occ_cost")
                staff = st.number_input("Staff Required", value=5, step=1, min_value=1, key="occ_staff")
                prep_time = st.number_input("Preparation Time (days)", value=14, step=1, min_value=1, key="occ_prep")
                
                if st.button("Add Event", key="add_occ_event"):
                    if event_name and funds_raised > 0 and cost >= 0:
                        # Calculate event rating (higher is better)
                        rating = (funds_raised * 0.6) - (cost * 0.3) - (staff * 5) - (prep_time * 2)
                        
                        new_event = pd.DataFrame({
                            'Event Name': [event_name],
                            'Total Funds Raised': [funds_raised],
                            'Cost': [cost],
                            'Staff Required': [staff],
                            'Preparation Time (days)': [prep_time],
                            'Rating': [rating],
                            'Last Updated': [datetime.now().isoformat()]
                        })
                        
                        st.session_state.app_data["occasional_events"] = pd.concat(
                            [st.session_state.app_data["occasional_events"], new_event],
                            ignore_index=True
                        )
                        
                        save_app_data(st.session_state.app_data)
                        log_activity("occasional_event_added", f"Added event: {event_name}")
                        st.success(f"Added {event_name} successfully!")
                    else:
                        st.error("Please fill in all fields with valid values")
            
            # Delete occasional event
            if not st.session_state.app_data["occasional_events"].empty:
                with st.expander("Manage Occasional Events", expanded=False):
                    event_to_delete = st.selectbox(
                        "Select Event to Delete",
                        st.session_state.app_data["occasional_events"]["Event Name"],
                        key="occ_event_delete"
                    )
                    
                    if st.button("Delete Selected Event", type="secondary", key="delete_occ_event"):
                        st.session_state.app_data["occasional_events"] = st.session_state.app_data["occasional_events"][
                            st.session_state.app_data["occasional_events"]["Event Name"] != event_to_delete
                        ].reset_index(drop=True)
                        
                        save_app_data(st.session_state.app_data)
                        log_activity("occasional_event_deleted", f"Deleted event: {event_to_delete}")
                        st.success(f"Deleted {event_to_delete} successfully!")
        
        # Optimization tools
        if not st.session_state.app_data["occasional_events"].empty and is_admin():
            with st.expander("Event Optimization", expanded=False):
                st.subheader("Event Rating Analysis")
                
                if st.button("Sort Events by Rating"):
                    st.session_state.app_data["occasional_events"] = st.session_state.app_data["occasional_events"].sort_values(
                        by="Rating", ascending=False
                    ).reset_index(drop=True)
                    st.success("Events sorted by rating (highest first)")
                
                target = st.number_input("Optimization Target", value=5000.0, step=1000.0)
                
                if st.button("Optimize Event Schedule"):
                    # Simple optimization algorithm
                    events = st.session_state.app_data["occasional_events"].copy()
                    events["Net"] = events["Total Funds Raised"] - events["Cost"]
                    events = events[events["Net"] > 0]  # Only consider profitable events
                    
                    if events.empty:
                        st.warning("No profitable events to optimize")
                    else:
                        # Sort by efficiency (rating per unit cost)
                        events["Efficiency"] = events["Rating"] / events["Cost"]
                        events = events.sort_values("Efficiency", ascending=False)
                        
                        remaining = target
                        allocation = defaultdict(int)
                        
                        # First pass: allocate one of each efficient event
                        for _, event in events.iterrows():
                            if remaining <= 0:
                                break
                            if event["Net"] <= remaining:
                                allocation[event["Event Name"]] = 1
                                remaining -= event["Net"]
                        
                        # Second pass: allocate additional events until target is met
                        while remaining > 0:
                            allocated = False
                            for _, event in events.iterrows():
                                if allocation[event["Event Name"]] < 3 and event["Net"] <= remaining:
                                    allocation[event["Event Name"]] += 1
                                    remaining -= event["Net"]
                                    allocated = True
                                    break
                            if not allocated:
                                break
                        
                        # Display results
                        st.subheader("Optimization Results")
                        st.write(f"Target: ${target:,.2f}")
                        st.write(f"Projected: ${(target - remaining):,.2f}")
                        st.write(f"Remaining: ${remaining:,.2f}")
                        
                        results = []
                        for event_name, count in allocation.items():
                            if count > 0:
                                event = events[events["Event Name"] == event_name].iloc[0]
                                results.append({
                                    "Event": event_name,
                                    "Times": count,
                                    "Net Profit Each": f"${event['Net']:,.2f}",
                                    "Total Contribution": f"${event['Net'] * count:,.2f}"
                                })
                        
                        st.dataframe(results, use_container_width=True, hide_index=True)
                        log_activity("event_optimization", f"Optimized for target: ${target}")

def render_attendance_tab():
    """Render Attendance tab"""
    st.subheader("📋 Attendance Records")
    
    # Display attendance summary
    st.subheader("Attendance Summary")
    attendance_rates = calculate_attendance_rates()
    st.dataframe(attendance_rates, use_container_width=True, hide_index=True)
    
    # Detailed attendance for admins
    if is_admin():
        st.subheader("Detailed Attendance Records")
        
        if not st.session_state.app_data["meeting_names"]:
            st.info("No meetings have been created yet")
        else:
            # Allow editing attendance
            edited_attendance = st.data_editor(
                st.session_state.app_data["attendance"],
                column_config={
                    "Name": st.column_config.TextColumn("Member Name", disabled=True)
                },
                use_container_width=True,
                hide_index=True
            )
            
            if not edited_attendance.equals(st.session_state.app_data["attendance"]):
                st.session_state.app_data["attendance"] = edited_attendance
                save_app_data(st.session_state.app_data)
                log_activity("attendance_updated", "Attendance records modified")
                st.success("Attendance records updated successfully")
        
        # Manage meetings
        st.divider()
        st.subheader("Manage Meetings")
        
        col_add_meeting, col_delete_meeting = st.columns(2)
        
        with col_add_meeting:
            new_meeting_name = st.text_input("New Meeting Name", "Monthly General Meeting")
            if st.button("Add Meeting"):
                if new_meeting_name and new_meeting_name not in st.session_state.app_data["meeting_names"]:
                    # Add new meeting column to attendance
                    st.session_state.app_data["meeting_names"].append(new_meeting_name)
                    st.session_state.app_data["attendance"][new_meeting_name] = False
                    
                    save_app_data(st.session_state.app_data)
                    log_activity("meeting_added", f"Added meeting: {new_meeting_name}")
                    st.success(f"Added meeting: {new_meeting_name}")
                else:
                    st.error("Please enter a unique meeting name")
        
        with col_delete_meeting:
            if st.session_state.app_data["meeting_names"]:
                meeting_to_delete = st.selectbox(
                    "Select Meeting to Delete",
                    st.session_state.app_data["meeting_names"]
                )
                
                if st.button("Delete Meeting", type="secondary"):
                    # Remove meeting from list and attendance records
                    st.session_state.app_data["meeting_names"].remove(meeting_to_delete)
                    st.session_state.app_data["attendance"] = st.session_state.app_data["attendance"].drop(
                        columns=[meeting_to_delete]
                    )
                    
                    save_app_data(st.session_state.app_data)
                    log_activity("meeting_deleted", f"Deleted meeting: {meeting_to_delete}")
                    st.success(f"Deleted meeting: {meeting_to_delete}")
            else:
                st.info("No meetings to delete")
        
        # Manage members
        st.divider()
        st.subheader("Manage Members")
        
        col_add_member, col_delete_member = st.columns(2)
        
        with col_add_member:
            new_member_name = st.text_input("New Member Name", "John Doe")
            if st.button("Add Member"):
                if new_member_name and new_member_name not in st.session_state.app_data["attendance"]["Name"].values:
                    # Create new row with False for all meetings
                    new_row = {"Name": new_member_name}
                    for meeting in st.session_state.app_data["meeting_names"]:
                        new_row[meeting] = False
                    
                    # Add to attendance
                    st.session_state.app_data["attendance"] = pd.concat(
                        [st.session_state.app_data["attendance"], pd.DataFrame([new_row])],
                        ignore_index=True
                    )
                    
                    save_app_data(st.session_state.app_data)
                    log_activity("member_added", f"Added member: {new_member_name}")
                    st.success(f"Added member: {new_member_name}")
                else:
                    st.error("Member name already exists or is empty")
        
        with col_delete_member:
            if not st.session_state.app_data["attendance"].empty:
                member_to_delete = st.selectbox(
                    "Select Member to Remove",
                    st.session_state.app_data["attendance"]["Name"]
                )
                
                if st.button("Remove Member", type="secondary"):
                    st.session_state.app_data["attendance"] = st.session_state.app_data["attendance"][
                        st.session_state.app_data["attendance"]["Name"] != member_to_delete
                    ].reset_index(drop=True)
                    
                    save_app_data(st.session_state.app_data)
                    log_activity("member_removed", f"Removed member: {member_to_delete}")
                    st.success(f"Removed member: {member_to_delete}")
            else:
                st.info("No members to remove")
        
        # Export option
        if st.button("Export Attendance Data"):
            excel_link = export_to_excel(
                st.session_state.app_data["attendance"], 
                "attendance_records.xlsx"
            )
            st.markdown(excel_link, unsafe_allow_html=True)

def render_credit_system_tab():
    """Render Credit & Reward System tab"""
    st.subheader("🎁 Credit & Reward System")
    
    col_credits, col_rewards = st.columns(2)
    
    with col_credits:
        st.subheader("Student Credits")
        st.dataframe(
            st.session_state.app_data["credit_data"],
            use_container_width=True,
            hide_index=True
        )
        
        # Credit management (credit managers and admins)
        if is_credit_manager():
            with st.expander("Manage Student Credits", expanded=False):
                st.subheader("Add Credits")
                student_name = st.text_input("Student Name", "New Student")
                contribution_type = st.selectbox(
                    "Contribution Type",
                    ["Monetary Donation", "Volunteer Hours", "Event Organization", "Other"]
                )
                amount = st.number_input("Amount/Value", value=10.0, step=1.0)
                
                if st.button("Add Credits"):
                    # Calculate credits based on contribution type
                    if contribution_type == "Monetary Donation":
                        credits = amount * 10  # $1 = 10 credits
                    elif contribution_type == "Volunteer Hours":
                        credits = amount * 15  # 1 hour = 15 credits
                    elif contribution_type == "Event Organization":
                        credits = amount * 25  # Major contribution
                    else:
                        credits = amount * 5  # Other contributions
                    
                    # Check if student exists
                    if student_name in st.session_state.app_data["credit_data"]["Name"].values:
                        # Update existing student
                        idx = st.session_state.app_data["credit_data"][
                            st.session_state.app_data["credit_data"]["Name"] == student_name
                        ].index[0]
                        st.session_state.app_data["credit_data"].at[idx, "Total_Credits"] += credits
                        st.session_state.app_data["credit_data"].at[idx, "Last_Updated"] = datetime.now().isoformat()
                    else:
                        # Add new student
                        new_student = pd.DataFrame({
                            'Name': [student_name],
                            'Total_Credits': [credits],
                            'RedeemedCredits': [0],
                            'Last_Updated': [datetime.now().isoformat()]
                        })
                        st.session_state.app_data["credit_data"] = pd.concat(
                            [st.session_state.app_data["credit_data"], new_student],
                            ignore_index=True
                        )
                    
                    save_app_data(st.session_state.app_data)
                    log_activity(
                        "credits_added", 
                        f"Added {credits} credits to {student_name} for {contribution_type}"
                    )
                    st.success(f"Added {credits} credits to {student_name}!")
                
                st.divider()
                st.subheader("Remove Student")
                if not st.session_state.app_data["credit_data"].empty:
                    student_to_remove = st.selectbox(
                        "Select Student to Remove",
                        st.session_state.app_data["credit_data"]["Name"]
                    )
                    
                    if st.button("Remove Student", type="secondary"):
                        st.session_state.app_data["credit_data"] = st.session_state.app_data["credit_data"][
                            st.session_state.app_data["credit_data"]["Name"] != student_to_remove
                        ].reset_index(drop=True)
                        
                        save_app_data(st.session_state.app_data)
                        log_activity("student_removed", f"Removed student: {student_to_remove}")
                        st.success(f"Removed {student_to_remove} from credit records")
        
        # Export credits data
        if st.button("Export Credits Data"):
            excel_link = export_to_excel(
                st.session_state.app_data["credit_data"], 
                "student_credits.xlsx"
            )
            st.markdown(excel_link, unsafe_allow_html=True)
    
    with col_rewards:
        st.subheader("Available Rewards")
        st.dataframe(
            st.session_state.app_data["reward_data"],
            use_container_width=True,
            hide_index=True
        )
        
        # Reward management (admin only)
        if is_admin():
            with st.expander("Manage Rewards", expanded=False):
                st.subheader("Add New Reward")
                reward_name = st.text_input("Reward Name", "New Reward")
                reward_cost = st.number_input("Credit Cost", value=50, step=10, min_value=10)
                reward_stock = st.number_input("Initial Stock", value=10, step=1, min_value=1)
                
                if st.button("Add Reward"):
                    if reward_name and reward_cost > 0 and reward_stock > 0:
                        new_reward = pd.DataFrame({
                            'Reward': [reward_name],
                            'Cost': [reward_cost],
                            'Stock': [reward_stock],
                            'Last_Updated': [datetime.now().isoformat()]
                        })
                        
                        st.session_state.app_data["reward_data"] = pd.concat(
                            [st.session_state.app_data["reward_data"], new_reward],
                            ignore_index=True
                        )
                        
                        save_app_data(st.session_state.app_data)
                        log_activity("reward_added", f"Added reward: {reward_name} (Cost: {reward_cost})")
                        st.success(f"Added new reward: {reward_name}")
                    else:
                        st.error("Please fill in all fields with valid values")
                
                st.divider()
                st.subheader("Update Reward Stock")
                if not st.session_state.app_data["reward_data"].empty:
                    reward_to_update = st.selectbox(
                        "Select Reward",
                        st.session_state.app_data["reward_data"]["Reward"],
                        key="reward_update"
                    )
                    
                    new_stock = st.number_input(
                        "New Stock Level",
                        value=10,
                        step=1,
                        min_value=0,
                        key="new_stock"
                    )
                    
                    if st.button("Update Stock"):
                        idx = st.session_state.app_data["reward_data"][
                            st.session_state.app_data["reward_data"]["Reward"] == reward_to_update
                        ].index[0]
                        st.session_state.app_data["reward_data"].at[idx, "Stock"] = new_stock
                        st.session_state.app_data["reward_data"].at[idx, "Last_Updated"] = datetime.now().isoformat()
                        
                        save_app_data(st.session_state.app_data)
                        log_activity("reward_updated", f"Updated {reward_to_update} stock to {new_stock}")
                        st.success(f"Updated {reward_to_update} stock to {new_stock}")
                
                st.divider()
                st.subheader("Remove Reward")
                if not st.session_state.app_data["reward_data"].empty:
                    reward_to_remove = st.selectbox(
                        "Select Reward to Remove",
                        st.session_state.app_data["reward_data"]["Reward"],
                        key="reward_remove"
                    )
                    
                    if st.button("Remove Reward", type="secondary"):
                        st.session_state.app_data["reward_data"] = st.session_state.app_data["reward_data"][
                            st.session_state.app_data["reward_data"]["Reward"] != reward_to_remove
                        ].reset_index(drop=True)
                        
                        save_app_data(st.session_state.app_data)
                        log_activity("reward_removed", f"Removed reward: {reward_to_remove}")
                        st.success(f"Removed reward: {reward_to_remove}")
        
        # Reward redemption
        if is_credit_manager():
            with st.expander("Redeem Reward", expanded=False):
                st.subheader("Process Reward Redemption")
                
                if st.session_state.app_data["credit_data"].empty:
                    st.info("No students in credit system")
                elif st.session_state.app_data["reward_data"].empty:
                    st.info("No rewards available")
                else:
                    student_name = st.selectbox(
                        "Select Student",
                        st.session_state.app_data["credit_data"]["Name"],
                        key="redeem_student"
                    )
                    
                    reward_name = st.selectbox(
                        "Select Reward",
                        st.session_state.app_data["reward_data"]["Reward"],
                        key="redeem_reward"
                    )
                    
                    if st.button("Process Redemption"):
                        # Get student and reward data
                        student_idx = st.session_state.app_data["credit_data"][
                            st.session_state.app_data["credit_data"]["Name"] == student_name
                        ].index[0]
                        
                        reward_idx = st.session_state.app_data["reward_data"][
                            st.session_state.app_data["reward_data"]["Reward"] == reward_name
                        ].index[0]
                        
                        student = st.session_state.app_data["credit_data"].iloc[student_idx]
                        reward = st.session_state.app_data["reward_data"].iloc[reward_idx]
                        
                        # Check if student has enough credits
                        available_credits = student["Total_Credits"] - student["RedeemedCredits"]
                        
                        if available_credits >= reward["Cost"] and reward["Stock"] > 0:
                            # Update student credits
                            st.session_state.app_data["credit_data"].at[student_idx, "RedeemedCredits"] += reward["Cost"]
                            st.session_state.app_data["credit_data"].at[student_idx, "Last_Updated"] = datetime.now().isoformat()
                            
                            # Update reward stock
                            st.session_state.app_data["reward_data"].at[reward_idx, "Stock"] -= 1
                            st.session_state.app_data["reward_data"].at[reward_idx, "Last_Updated"] = datetime.now().isoformat()
                            
                            save_app_data(st.session_state.app_data)
                            log_activity(
                                "reward_redeemed", 
                                f"{student_name} redeemed {reward_name} (Cost: {reward['Cost']})"
                            )
                            st.success(f"{student_name} successfully redeemed {reward_name}!")
                        elif reward["Stock"] <= 0:
                            st.error(f"Sorry, {reward_name} is out of stock!")
                        else:
                            st.error(f"{student_name} does not have enough credits! (Needs {reward['Cost']}, has {available_credits})")
    
    # Lucky draw wheel (admin only)
    st.divider()
    st.subheader("🎰 Lucky Draw")
    
    if is_admin():
        if st.session_state.app_data["credit_data"].empty:
            st.info("No students in credit system to participate in lucky draw")
        else:
            col_wheel, col_results = st.columns(2)
            
            with col_wheel:
                student_name = st.selectbox(
                    "Select Student for Lucky Draw",
                    st.session_state.app_data["credit_data"]["Name"],
                    key="lucky_student"
                )
                
                if st.button("Spin Wheel"):
                    # Check if student has enough credits
                    student = st.session_state.app_data["credit_data"][
                        st.session_state.app_data["credit_data"]["Name"] == student_name
                    ].iloc[0]
                    
                    if student["Total_Credits"] < 50:
                        st.error("Student needs at least 50 credits to spin the wheel!")
                    else:
                        # Deduct credits
                        idx = st.session_state.app_data["credit_data"][
                            st.session_state.app_data["credit_data"]["Name"] == student_name
                        ].index[0]
                        st.session_state.app_data["credit_data"].at[idx, "Total_Credits"] -= 50
                        st.session_state.app_data["credit_data"].at[idx, "Last_Updated"] = datetime.now().isoformat()
                        
                        # Spin animation
                        st.write("Spinning the wheel...")
                        progress_bar = st.progress(0)
                        
                        for i in range(100):
                            # Update progress bar
                            progress_bar.progress(i + 1)
                            time.sleep(0.02)
                        
                        # Random result
                        prize_idx = np.random.randint(0, len(st.session_state.app_data["wheel_prizes"]))
                        final_rotation = 3 * 360 + (prize_idx * (360 / len(st.session_state.app_data["wheel_prizes"])))
                        
                        # Display wheel
                        fig = draw_wheel(np.deg2rad(final_rotation))
                        st.pyplot(fig)
                        
                        # Award prize
                        prize = st.session_state.app_data["wheel_prizes"][prize_idx]
                        
                        # Add credits if prize is credit-based
                        if "Credits" in prize:
                            credits = int(prize.split()[0])
                            st.session_state.app_data["credit_data"].at[idx, "Total_Credits"] += credits
                            st.success(f"Congratulations! {student_name} won {prize}!")
                        else:
                            st.success(f"Congratulations! {student_name} won {prize}!")
                        
                        save_app_data(st.session_state.app_data)
                        log_activity(
                            "lucky_draw", 
                            f"{student_name} won {prize} in lucky draw"
                        )
    else:
        st.info("Lucky draw is available to administrators only")

def render_ai_tab():
    """Render SCIS Specific AI tab"""
    st.subheader("🤖 SCIS Specific AI Tools")
    st.info("This section contains AI-powered tools specifically designed for student council management.")
    
    with st.expander("Event Recommendation Engine", expanded=True):
        st.subheader("Event Recommendation Engine")
        st.write("Get personalized event recommendations based on past performance and current goals.")
        
        goal = st.selectbox(
            "Primary Goal",
            ["Maximize Fundraising", "Increase Participation", "Build Community", "Minimize Costs"]
        )
        
        budget = st.slider("Event Budget", 100, 10000, 1000)
        audience = st.selectbox(
            "Target Audience",
            ["Students Only", "Students & Faculty", "School & Community", "Special Interest Group"]
        )
        
        if st.button("Generate Recommendations"):
            with st.spinner("Analyzing data and generating recommendations..."):
                time.sleep(2)  # Simulate AI processing
                
                # Sample recommendations
                if goal == "Maximize Fundraising":
                    recommendations = [
                        {"Event": "Charity Auction", "Estimated Revenue": "$5,000-$8,000", "Difficulty": "Medium"},
                        {"Event": "Benefit Concert", "Estimated Revenue": "$3,000-$6,000", "Difficulty": "High"},
                        {"Event": "Bake Sale Series", "Estimated Revenue": "$800-$1,500", "Difficulty": "Low"}
                    ]
                elif goal == "Increase Participation":
                    recommendations = [
                        {"Event": "School Fair", "Estimated Participants": "200-300", "Difficulty": "High"},
                        {"Event": "Trivia Night", "Estimated Participants": "50-100", "Difficulty": "Medium"},
                        {"Event": "Sports Tournament", "Estimated Participants": "80-150", "Difficulty": "Medium"}
                    ]
                elif goal == "Build Community":
                    recommendations = [
                        {"Event": "Community Service Day", "Impact": "High", "Difficulty": "Medium"},
                        {"Event": "Cultural Exchange", "Impact": "Medium", "Difficulty": "Medium"},
                        {"Event": "Mentorship Program", "Impact": "High", "Difficulty": "Low"}
                    ]
                else:  # Minimize Costs
                    recommendations = [
                        {"Event": "Movie Night", "Estimated Cost": "$200-$300", "Potential Revenue": "$500-$800"},
                        {"Event": "Game Tournament", "Estimated Cost": "$100-$200", "Potential Revenue": "$300-$600"},
                        {"Event": "Potluck Dinner", "Estimated Cost": "$50-$100", "Potential Revenue": "$200-$400"}
                    ]
                
                st.dataframe(recommendations, use_container_width=True, hide_index=True)
                log_activity("ai_recommendation", f"Generated event recommendations for {goal}")
    
    with st.expander("Budget Optimizer", expanded=False):
        st.subheader("Budget Optimizer")
        st.write("Optimize your budget allocation across different council activities.")
        
        total_budget = st.number_input("Total Budget", value=10000, step=1000)
        
        if st.button("Optimize Budget"):
            with st.spinner("Calculating optimal budget allocation..."):
                time.sleep(2)  # Simulate AI processing
                
                allocation = [
                    {"Category": "Events", "Percentage": 40, "Amount": f"${total_budget * 0.4:,.2f}"},
                    {"Category": "Materials", "Percentage": 25, "Amount": f"${total_budget * 0.25:,.2f}"},
                    {"Category": "Prizes/Rewards", "Percentage": 15, "Amount": f"${total_budget * 0.15:,.2f}"},
                    {"Category": "Marketing", "Percentage": 10, "Amount": f"${total_budget * 0.10:,.2f}"},
                    {"Category": "Contingency", "Percentage": 10, "Amount": f"${total_budget * 0.10:,.2f}"}
                ]
                
                st.dataframe(allocation, use_container_width=True, hide_index=True)
                
                fig, ax = plt.subplots(figsize=(8, 4))
                categories = [item["Category"] for item in allocation]
                percentages = [item["Percentage"] for item in allocation]
                ax.pie(percentages, labels=categories, autopct='%1.1f%%', startangle=90)
                ax.axis('equal')
                st.pyplot(fig)
                log_activity("ai_budget_optimization", f"Optimized budget of ${total_budget}")

def render_money_transfer_tab():
    """Render Money Transfer tab"""
    st.subheader("💸 Financial Transactions")
    
    # Display transaction history
    if not st.session_state.app_data["money_data"].empty:
        st.subheader("Transaction History")
        st.dataframe(
            st.session_state.app_data["money_data"],
            use_container_width=True,
            hide_index=True
        )
        
        # Calculate totals
        incoming = st.session_state.app_data["money_data"][
            st.session_state.app_data["money_data"]["Type"] == "Incoming"
        ]["Amount"].sum()
        
        outgoing = st.session_state.app_data["money_data"][
            st.session_state.app_data["money_data"]["Type"] == "Outgoing"
        ]["Amount"].sum()
        
        balance = incoming - outgoing
        
        col_in, col_out, col_bal = st.columns(3)
        col_in.metric("Total Incoming", f"${incoming:,.2f}")
        col_out.metric("Total Outgoing", f"${outgoing:,.2f}")
        col_bal.metric("Current Balance", f"${balance:,.2f}")
    else:
        st.info("No financial transactions recorded yet")
    
    # Add transaction (admin only)
    if is_admin():
        with st.expander("Record New Transaction", expanded=False):
            st.subheader("New Transaction")
            
            trans_type = st.selectbox("Transaction Type", ["Incoming", "Outgoing"])
            amount = st.number_input("Amount", value=100.0, step=10.0, min_value=0.01)
            description = st.text_input("Description", "Fundraising proceeds")
            trans_date = st.date_input("Date", date.today())
            
            if st.button("Record Transaction"):
                if amount > 0 and description:
                    new_transaction = pd.DataFrame({
                        'Amount': [amount],
                        'Description': [description],
                        'Date': [trans_date.strftime("%Y-%m-%d")],
                        'Type': [trans_type]
                    })
                    
                    st.session_state.app_data["money_data"] = pd.concat(
                        [st.session_state.app_data["money_data"], new_transaction],
                        ignore_index=True
                    )
                    
                    save_app_data(st.session_state.app_data)
                    log_activity(
                        "transaction_recorded", 
                        f"Recorded {trans_type} transaction: ${amount} - {description}"
                    )
                    st.success("Transaction recorded successfully!")
                else:
                    st.error("Please enter a valid amount and description")
        
        # Export transaction data
        if not st.session_state.app_data["money_data"].empty:
            if st.button("Export Financial Data"):
                excel_link = export_to_excel(
                    st.session_state.app_data["money_data"], 
                    "financial_transactions.xlsx"
                )
                st.markdown(excel_link, unsafe_allow_html=True)
            
            # Clear transaction history (with confirmation)
            if st.button("Clear Transaction History", type="secondary"):
                confirm = st.checkbox("I confirm I want to clear all transaction records")
                if confirm:
                    st.session_state.app_data["money_data"] = pd.DataFrame(columns=['Amount', 'Description', 'Date', 'Type'])
                    save_app_data(st.session_state.app_data)
                    log_activity("transactions_cleared", "All financial transactions cleared")
                    st.success("Transaction history cleared")

# ------------------------------
# Main Application Entry
# ------------------------------
def main():
    # Set page config
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide"
    )
    
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
        border: 2px solid #2196f3;
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
    .event-text {
        font-size: 0.85rem;
        margin-top: 5px;
        color: #1e88e5;
    }
    .role-badge {
        border-radius: 12px;
        padding: 3px 8px;
        font-size: 0.75rem;
        font-weight: bold;
    }
    .stButton>button {
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if "user" not in st.session_state:
        st.session_state.user = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "app_data" not in st.session_state:
        st.session_state.app_data = load_app_data()
    
    # Main title
    st.title(f"{APP_ICON} {APP_TITLE}")
    
    # Handle authentication
    if not st.session_state.user:
        # Show login form in sidebar
        render_login_sidebar()
        
        # Show welcome message in main area
        st.write("""
        Welcome to the Student Council Management System. This platform helps manage:
        
        - Calendar and events
        - Financial planning and optimization
        - Attendance tracking
        - Credit and reward systems
        - Financial transactions
        
        Please log in using your credentials in the sidebar to access the system.
        """)
        
        st.image("https://picsum.photos/id/26/800/400", caption="Student Council Activities", use_column_width=True)
    else:
        # Show user-specific sidebar
        render_user_sidebar()
        
        # Main tabs
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "Calendar", 
            "Announcements",
            "Financials", 
            "Attendance",
            "Credits & Rewards", 
            "AI Tools", 
            "Transactions"
        ])
        
        with tab1:
            render_calendar_tab()
        
        with tab2:
            render_announcements_tab()
        
        with tab3:
            render_financial_tab()
        
        with tab4:
            render_attendance_tab()
        
        with tab5:
            render_credit_system_tab()
        
        with tab6:
            render_ai_tab()
        
        with tab7:
            render_money_transfer_tab()

if __name__ == "__main__":
    main()
