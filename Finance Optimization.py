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

# ------------------------------
# App Configuration
# ------------------------------
st.set_page_config(
    page_title="SCIS HQ US Stuco",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# File Paths & Constants
# ------------------------------
DATA_DIR = "stuco_data"
Path(DATA_DIR).mkdir(exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "app_data.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "app_config.json")

ROLES = ["user", "admin", "credit_manager"]
CREATOR_ROLE = "creator"
WELCOME_MESSAGE = "Welcome to SCIS HQ US Stuco"

# ------------------------------
# Initialization & Setup
# ------------------------------
def initialize_files():
    """Ensure all required data files exist"""
    for file in [DATA_FILE, USERS_FILE, CONFIG_FILE]:
        if not Path(file).exists():
            initial_data = {}
            if file == CONFIG_FILE:
                initial_data = {"show_signup": False, "app_version": "1.0.0"}
            with open(file, "w") as f:
                json.dump(initial_data, f, indent=2)

# Initialize session state variables
def initialize_session_state():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0
    if "spinning" not in st.session_state:
        st.session_state.spinning = False
    if "winner" not in st.session_state:
        st.session_state.winner = None
    if "allocation_count" not in st.session_state:
        st.session_state.allocation_count = 0

# ------------------------------
# Config Management
# ------------------------------
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# ------------------------------
# User Authentication
# ------------------------------
def hash_password(password):
    """Hash a password for storage"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def load_users():
    """Load all users from file"""
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    return {k: v for k, v in users.items() if "password_hash" in v and "role" in v}

def save_user(username, password, role="user"):
    """Save a new user to the database"""
    users = load_users()
    if username in users:
        return False, "Username already exists"
    
    users[username] = {
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now().isoformat(),
        "last_login": None
    }
    
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    return True, "User created successfully"

def update_user_login(username):
    """Update last login timestamp"""
    users = load_users()
    if username in users:
        users[username]["last_login"] = datetime.now().isoformat()
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)

def update_user_role(username, new_role):
    """Update a user's role"""
    valid_roles = ROLES + [CREATOR_ROLE]
    if new_role not in valid_roles:
        return False, f"Invalid role. Choose: {', '.join(valid_roles)}"
        
    users = load_users()
    if username not in users:
        return False, "User not found"
        
    users[username]["role"] = new_role
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    return True, f"Role updated to {new_role}"

def delete_user(username):
    """Delete a user"""
    users = load_users()
    if username not in users:
        return False, "User not found"
        
    del users[username]
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    return True, "User deleted successfully"

# ------------------------------
# Data Management
# ------------------------------
def safe_init_data():
    """Safely initialize all data structures"""
    st.session_state.scheduled_events = pd.DataFrame(columns=[
        'Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds'
    ])

    st.session_state.occasional_events = pd.DataFrame(columns=[
        'Event Name', 'Total Funds Raised', 'Cost', 'Staff Many Or Not', 
        'Preparation Time', 'Rating'
    ])

    st.session_state.credit_data = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie', 'Diana'],
        'Total_Credits': [200, 150, 300, 180],
        'RedeemedCredits': [50, 0, 100, 30]
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
    st.session_state.attendance = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Evan'],
        'First Semester Meeting': [True, False, True, True, False],
        'Event Planning Session': [True, True, True, False, True]
    })

def load_data():
    """Load application data from file"""
    if Path(DATA_FILE).exists():
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            
            # Load scheduled events
            st.session_state.scheduled_events = pd.DataFrame(data.get("scheduled_events", []))
            required_cols = ['Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds']
            for col in required_cols:
                if col not in st.session_state.scheduled_events.columns:
                    st.session_state.scheduled_events[col] = pd.Series(dtype='float64' if col != 'Event Name' else 'object')

            # Load occasional events
            st.session_state.occasional_events = pd.DataFrame(data.get("occasional_events", []))
            
            # Load credit data
            st.session_state.credit_data = pd.DataFrame(data.get("credit_data", []))
            if st.session_state.credit_data.empty:
                st.session_state.credit_data = pd.DataFrame({
                    'Name': ['Alice', 'Bob', 'Charlie'],
                    'Total_Credits': [200, 150, 300],
                    'RedeemedCredits': [50, 0, 100]
                })

            # Load reward data
            st.session_state.reward_data = pd.DataFrame(data.get("reward_data", []))
            if st.session_state.reward_data.empty:
                st.session_state.reward_data = pd.DataFrame({
                    'Reward': ['Bubble Tea', 'Chips', 'Café Coupon'],
                    'Cost': [50, 30, 80],
                    'Stock': [10, 20, 5]
                })

            # Wheel configuration
            st.session_state.wheel_prizes = data.get("wheel_prizes", [
                "50 Credits", "Bubble Tea", "Chips", "100 Credits", 
                "Café Coupon", "Free Prom Ticket"
            ])
            st.session_state.wheel_colors = plt.cm.tab10(np.linspace(0, 1, len(st.session_state.wheel_prizes)))

            # Other data
            st.session_state.money_data = pd.DataFrame(data.get("money_data", []))
            st.session_state.calendar_events = data.get("calendar_events", {})
            st.session_state.announcements = data.get("announcements", [])
            st.session_state.meeting_names = data.get("meeting_names", ["Meeting 1"])
            st.session_state.attendance = pd.DataFrame(data.get("attendance", {}))
            
            if st.session_state.attendance.empty:
                st.session_state.attendance = pd.DataFrame({
                    'Name': ['Alice', 'Bob', 'Charlie'],
                    'Meeting 1': [True, False, True]
                })

        except Exception as e:
            st.error(f"Error loading data: {str(e)}. Resetting to default data.")
            safe_init_data()
    else:
        safe_init_data()
        save_data()

def save_data():
    """Save application data to file"""
    try:
        data = {
            "scheduled_events": st.session_state.scheduled_events.to_dict(orient="records"),
            "occasional_events": st.session_state.occasional_events.to_dict(orient="records"),
            "credit_data": st.session_state.credit_data.to_dict(orient="records"),
            "reward_data": st.session_state.reward_data.to_dict(orient="records"),
            "wheel_prizes": st.session_state.wheel_prizes,
            "calendar_events": st.session_state.calendar_events,
            "announcements": st.session_state.announcements,
            "money_data": st.session_state.money_data.to_dict(orient="records"),
            "attendance": st.session_state.attendance.to_dict(orient="records"),
            "meeting_names": st.session_state.meeting_names
        }
        
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True, "Data saved successfully"
    except Exception as e:
        return False, f"Error saving data: {str(e)}"

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

# Find and replace the render_calendar() function with this version
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

# Also update the get_month_grid() function to accept year and month parameters
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
    """Calculate attendance rates for each member"""
    if len(st.session_state.meeting_names) == 0:
        return pd.DataFrame({
            'Name': st.session_state.attendance['Name'],
            'Attendance Rate (%)': [0.0 for _ in range(len(st.session_state.attendance))]
        })
    
    rates = []
    for _, row in st.session_state.attendance.iterrows():
        attended = sum(row[meeting] for meeting in st.session_state.meeting_names if pd.notna(row[meeting]))
        rate = (attended / len(st.session_state.meeting_names)) * 100 if len(st.session_state.meeting_names) > 0 else 0
        rates.append(round(rate, 1))
    
    return pd.DataFrame({
        'Name': st.session_state.attendance['Name'],
        'Attendance Rate (%)': rates
    })

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
        
        # Display announcements
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
                    st.info(f"**{datetime.fromisoformat(ann['time']).strftime('%b %d, %Y - %H:%M')}**\n\n{ann['text']}")
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
        
        # Add new announcement (admin only)
        if is_admin():
            with st.expander("Add New Announcement (Admin Only)", expanded=False):
                new_announcement = st.text_area(
                    "New Announcement", 
                    "Attention: Next student council meeting will be held on Friday at 3 PM.",
                    height=100
                )
                if st.button("Post Announcement"):
                    if new_announcement.strip():
                        st.session_state.announcements.append({
                            "text": new_announcement,
                            "time": datetime.now().isoformat(),
                            "author": st.session_state.user
                        })
                        success, msg = save_data()
                        if success:
                            st.success("Announcement posted successfully!")
                        else:
                            st.error(msg)
                    else:
                        st.error("Announcement cannot be empty")

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
        
        # Summary statistics
        st.subheader("Attendance Summary")
        attendance_rates = calculate_attendance_rates()
        st.dataframe(attendance_rates, use_container_width=True)
        
        # Detailed view for admins
        if is_admin():
            st.subheader("Detailed Attendance Records")
            
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

        with col_credits:
            st.subheader("Student Credits")
            st.dataframe(st.session_state.credit_data, use_container_width=True)

            if is_admin() or is_credit_manager():
                with st.expander("Manage Credits (Admin/Credit Managers)", expanded=False):
                    st.subheader("Add Contribution")
                    student_name = st.text_input("Student Name", "John Doe")
                    contribution_type = st.selectbox("Contribution Type", ["Monetary", "Time", "Event Organization"])
                    amount = st.number_input("Amount/ Hours", value=5.0, step=1.0)
                    
                    if st.button("Add Credits"):
                        # Calculate credits based on contribution type
                        if contribution_type == "Monetary":
                            credits = amount * 10  # $1 = 10 credits
                        elif contribution_type == "Time":
                            credits = amount * 5   # 1 hour = 5 credits
                        else:
                            credits = amount * 25  # Events get more credits
                        
                        # Update or add student
                        if student_name in st.session_state.credit_data['Name'].values:
                            st.session_state.credit_data.loc[
                                st.session_state.credit_data['Name'] == student_name, 'Total_Credits'
                            ] += credits
                        else:
                            new_student = pd.DataFrame({
                                'Name': [student_name],
                                'Total_Credits': [credits],
                                'RedeemedCredits': [0]
                            })
                            st.session_state.credit_data = pd.concat(
                                [st.session_state.credit_data, new_student], ignore_index=True
                            )
                        
                        success, msg = save_data()
                        if success:
                            st.success(f"Added {credits} credits to {student_name}")
                        else:
                            st.error(msg)

                    st.divider()
                    st.subheader("Remove Student")
                    if not st.session_state.credit_data.empty:
                        student_to_remove = st.selectbox("Select Student", st.session_state.credit_data['Name'])
                        if st.button("Remove Student", type="secondary"):
                            st.session_state.credit_data = st.session_state.credit_data[
                                st.session_state.credit_data['Name'] != student_to_remove
                            ].reset_index(drop=True)
                            success, msg = save_data()
                            if success:
                                st.success(f"Removed {student_to_remove}")
                            else:
                                st.error(msg)

        with col_rewards:
            st.subheader("Available Rewards")
            st.dataframe(st.session_state.reward_data, use_container_width=True)

            if is_admin():
                with st.expander("Manage Rewards (Admin Only)", expanded=False):
                    st.subheader("Add New Reward")
                    reward_name = st.text_input("Reward Name", "School Merchandise")
                    reward_cost = st.number_input("Credit Cost", value=75, step=5)
                    reward_stock = st.number_input("Initial Stock", value=15, step=1)
                    
                    if st.button("Add Reward"):
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
                            st.success(f"Added {reward_name}")
                        else:
                            st.error(msg)

                    st.divider()
                    st.subheader("Process Redemption")
                    if not st.session_state.credit_data.empty and not st.session_state.reward_data.empty:
                        student = st.selectbox("Student Name", st.session_state.credit_data['Name'], key="redeem_student")
                        reward = st.selectbox("Reward", st.session_state.reward_data['Reward'], key="redeem_reward")
                        
                        if st.button("Redeem Reward"):
                            # Get student and reward data
                            student_data = st.session_state.credit_data[st.session_state.credit_data['Name'] == student].iloc[0]
                            reward_data = st.session_state.reward_data[st.session_state.reward_data['Reward'] == reward].iloc[0]
                            
                            # Check if redemption is possible
                            available_credits = student_data['Total_Credits'] - student_data['RedeemedCredits']
                            if available_credits >= reward_data['Cost'] and reward_data['Stock'] > 0:
                                # Update student credits
                                st.session_state.credit_data.loc[
                                    st.session_state.credit_data['Name'] == student, 'RedeemedCredits'
                                ] += reward_data['Cost']
                                
                                # Update reward stock
                                st.session_state.reward_data.loc[
                                    st.session_state.reward_data['Reward'] == reward, 'Stock'
                                ] -= 1
                                
                                success, msg = save_data()
                                if success:
                                    st.success(f"{student} successfully redeemed {reward}!")
                                else:
                                    st.error(msg)
                            else:
                                if available_credits < reward_data['Cost']:
                                    st.error("Not enough credits for this reward")
                                else:
                                    st.error("Reward is out of stock")

                    st.divider()
                    st.subheader("Remove Reward")
                    if not st.session_state.reward_data.empty:
                        reward_to_remove = st.selectbox("Select Reward to Remove", st.session_state.reward_data['Reward'])
                        if st.button("Remove Reward", type="secondary"):
                            st.session_state.reward_data = st.session_state.reward_data[
                                st.session_state.reward_data['Reward'] != reward_to_remove
                            ].reset_index(drop=True)
                            success, msg = save_data()
                            if success:
                                st.success(f"Removed {reward_to_remove}")
                            else:
                                st.error(msg)

        # Lucky draw section
        st.subheader("Lucky Draw")
        if is_admin():
            col_wheel, col_results = st.columns(2)
            
            with col_wheel:
                if not st.session_state.credit_data.empty:
                    student = st.selectbox("Select Student for Draw", st.session_state.credit_data['Name'])
                    if st.button("Spin Lucky Wheel") and not st.session_state.spinning:
                        st.session_state.spinning = True
                        
                        # Check if student has enough credits
                        student_data = st.session_state.credit_data[st.session_state.credit_data['Name'] == student].iloc[0]
                        if student_data['Total_Credits'] < 50:
                            st.error("Student needs at least 50 credits to spin")
                            st.session_state.spinning = False
                        else:
                            # Deduct credits
                            st.session_state.credit_data.loc[
                                st.session_state.credit_data['Name'] == student, 'Total_Credits'
                            ] -= 50
                            
                            # Spin animation
                            st.write("Spinning...")
                            time.sleep(1)
                            
                            # Random result
                            prize_idx = random.randint(0, len(st.session_state.wheel_prizes) - 1)
                            final_rotation = 3 * 360 + (prize_idx * (360 / len(st.session_state.wheel_prizes)))
                            fig = draw_wheel(np.deg2rad(final_rotation))
                            st.pyplot(fig)
                            
                            # Record result
                            st.session_state.winner = st.session_state.wheel_prizes[prize_idx]
                            success, msg = save_data()
                            if not success:
                                st.error(msg)
                            
                            st.session_state.spinning = False
                else:
                    st.info("No students in credit system")
            
            with col_results:
                if 'winner' in st.session_state and st.session_state.winner:
                    st.success(f"Congratulations! You won: {st.session_state.winner}")
                    
                    # Add credits if prize is credit-based
                    if "Credits" in st.session_state.winner:
                        try:
                            credit_amount = int(st.session_state.winner.split()[0])
                            st.session_state.credit_data.loc[
                                st.session_state.credit_data['Name'] == student, 'Total_Credits'
                            ] += credit_amount
                            save_data()
                            st.info(f"Added {credit_amount} credits to {student}'s account")
                        except:
                            pass
        else:
            st.info("Lucky Draw is managed by administrators. See an admin to participate!")

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

if __name__ == "__main__":
    main()

