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

# ------------------------------
# Configuration & Security Setup
# ------------------------------
DATA_FILE = "app_data.json"
USERS_FILE = "users.json"
ROLES = ["user", "admin"]  # Simplified roles per request
CREATOR_ROLE = "creator"  # Special super-admin role

# Ensure necessary files exist
for file in [DATA_FILE, USERS_FILE]:
    if not Path(file).exists():
        with open(file, "w") as f:
            json.dump({}, f)

# ------------------------------
# Password & User Management
# ------------------------------
def hash_password(password):
    """Hash a password for storage"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def load_users():
    """Load user data from file"""
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    return {k: v for k, v in users.items() if "password_hash" in v and "role" in v}

def save_user(username, password, role):
    """Save a new user with hashed password"""
    users = load_users()
    if username in users:
        return False, "Username already exists"
    
    users[username] = {
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now().isoformat()
    }
    
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    return True, "User created successfully"

def update_user_role(username, new_role):
    """Update a user's role (creator only)"""
    if new_role not in ROLES + [CREATOR_ROLE]:
        return False, "Invalid role"
        
    users = load_users()
    if username not in users:
        return False, "User not found"
        
    users[username]["role"] = new_role
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    return True, "Role updated successfully"

def delete_user(username):
    """Delete a user (creator only)"""
    users = load_users()
    if username not in users:
        return False, "User not found"
        
    del users[username]
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    return True, "User deleted successfully"

# ------------------------------
# Persistent Data Storage
# ------------------------------
def load_data():
    """Load app data from JSON file with safety checks"""
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        
        # Initialize with defaults if keys are missing
        st.session_state.scheduled_events = pd.DataFrame(data.get("scheduled_events", []))
        required_columns = ['Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds']
        for col in required_columns:
            if col not in st.session_state.scheduled_events.columns:
                st.session_state.scheduled_events[col] = pd.Series(dtype='float64' if col != 'Event Name' else 'object')

        st.session_state.occasional_events = pd.DataFrame(data.get("occasional_events", []))
        st.session_state.credit_data = pd.DataFrame(data.get("credit_data", []))
        st.session_state.reward_data = pd.DataFrame(data.get("reward_data", []))
        st.session_state.calendar_events = data.get("calendar_events", {})
        st.session_state.announcements = data.get("announcements", [])
        st.session_state.money_data = pd.DataFrame(data.get("money_data", []))
        st.session_state.attendance = pd.DataFrame(data.get("attendance", {
            'Name': ['Alice', 'Bob', 'Charlie'],
            'Meeting 1': [True, False, True]
        }))
        st.session_state.meeting_names = data.get("meeting_names", ["Meeting 1"])

    else:
        safe_init_data()
        save_data()

def save_data():
    """Save current session state to JSON file"""
    data = {
        "scheduled_events": st.session_state.scheduled_events.to_dict(orient="records"),
        "occasional_events": st.session_state.occasional_events.to_dict(orient="records"),
        "credit_data": st.session_state.credit_data.to_dict(orient="records"),
        "reward_data": st.session_state.reward_data.to_dict(orient="records"),
        "calendar_events": st.session_state.calendar_events,
        "announcements": st.session_state.announcements,
        "money_data": st.session_state.money_data.to_dict(orient="records"),
        "attendance": st.session_state.attendance.to_dict(orient="records"),
        "meeting_names": st.session_state.meeting_names
    }
    
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def safe_init_data():
    """Initialize default data with guaranteed columns"""
    # Scheduled events
    st.session_state.scheduled_events = pd.DataFrame(columns=[
        'Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds'
    ])

    # Occasional events
    st.session_state.occasional_events = pd.DataFrame(columns=[
        'Event Name', 'Total Funds Raised', 'Cost', 'Staff Many Or Not', 
        'Preparation Time', 'Rating'
    ])

    # Credit data
    st.session_state.credit_data = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Total_Credits': [200, 150, 300],
        'RedeemedCredits': [50, 0, 100]
    })

    # Reward data
    st.session_state.reward_data = pd.DataFrame({
        'Reward': ['Bubble Tea', 'Chips', 'Café Coupon'],
        'Cost': [50, 30, 80],
        'Stock': [10, 20, 5]
    })

    # Wheel prizes
    st.session_state.wheel_prizes = ["50 Credits", "Bubble Tea", "Chips", "100 Credits", "Café Coupon", "Free Prom Ticket"]
    st.session_state.wheel_colors = plt.cm.tab10(np.linspace(0, 1, len(st.session_state.wheel_prizes)))

    # Other data
    st.session_state.money_data = pd.DataFrame(columns=['Money', 'Time'])
    st.session_state.allocation_count = 0
    st.session_state.spinning = False
    st.session_state.calendar_events = {}
    st.session_state.announcements = []

    # Attendance data
    st.session_state.meeting_names = ["Meeting 1"]
    st.session_state.attendance = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Meeting 1': [True, False, True]
    })

# ------------------------------
# Authentication System
# ------------------------------
def login():
    """Single login form for all users"""
    if "user" in st.session_state:
        return True  # Already logged in
    
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    col_login, col_clear = st.columns(2)
    
    with col_login:
        if st.button("Login"):
            users = load_users()
            if username in users:
                if verify_password(password, users[username]["password_hash"]):
                    st.session_state.user = username
                    st.session_state.role = users[username]["role"]
                    st.success(f"Logged in as {username} ({users[username]['role']})")
                    return True
                else:
                    st.error("Incorrect password")
            else:
                st.error("Username not found")
    
    with col_clear:
        if st.button("Clear"):
            st.session_state.user = None
            st.session_state.role = None
            st.experimental_rerun()
    
    return False

def creator_login():
    """Special login for creator role (separate from regular users)"""
    if st.session_state.get("role") == CREATOR_ROLE:
        return True
        
    st.subheader("Creator Access")
    creator_password = st.secrets.get("creator_password", "")
    password = st.text_input("Enter Creator Password", type="password")
    
    if st.button("Verify Creator"):
        if password == creator_password and creator_password != "":
            st.session_state.role = CREATOR_ROLE
            st.success("Creator access granted")
            return True
        else:
            st.error("Invalid creator password")
    
    return False

def logout():
    """Log out current user"""
    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.role = None
        st.success("Logged out successfully")
        st.experimental_rerun()

# ------------------------------
# Permission Checks
# ------------------------------
def is_admin():
    """Check if user is admin or creator"""
    role = st.session_state.get("role")
    return role in ["admin", CREATOR_ROLE]

def is_creator():
    """Check if user is creator"""
    return st.session_state.get("role") == CREATOR_ROLE

def is_user():
    """Check if user has basic user role"""
    return st.session_state.get("role") == "user"

# ------------------------------
# Attendance Helpers
# ------------------------------
def calculate_attendance_rates():
    """Calculate attendance rate (% of meetings attended) for each person"""
    if len(st.session_state.meeting_names) == 0:
        return pd.DataFrame({
            'Name': st.session_state.attendance['Name'],
            'Attendance Rate': [0.0 for _ in range(len(st.session_state.attendance))]
        })
    
    rates = []
    for _, row in st.session_state.attendance.iterrows():
        attended = sum(row[meeting] for meeting in st.session_state.meeting_names if pd.notna(row[meeting]))
        rate = (attended / len(st.session_state.meeting_names)) * 100
        rates.append(round(rate, 1))
    
    return pd.DataFrame({
        'Name': st.session_state.attendance['Name'],
        'Attendance Rate (%)': rates
    })

def add_new_meeting():
    """Add a new meeting column to attendance records"""
    new_meeting_num = len(st.session_state.meeting_names) + 1
    new_meeting_name = f"Meeting {new_meeting_num}"
    st.session_state.meeting_names.append(new_meeting_name)
    st.session_state.attendance[new_meeting_name] = False
    save_data()
    st.success(f"Added new meeting: {new_meeting_name}")

def delete_meeting(meeting_name):
    """Delete a meeting column from attendance records"""
    if meeting_name in st.session_state.meeting_names:
        st.session_state.meeting_names.remove(meeting_name)
        st.session_state.attendance = st.session_state.attendance.drop(columns=[meeting_name])
        save_data()
        st.success(f"Deleted meeting: {meeting_name}")
    else:
        st.error(f"Meeting {meeting_name} not found")

def add_new_person(name):
    """Add a new person to attendance records"""
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
    save_data()
    st.success(f"Added {name} to attendance list")

def delete_person(name):
    """Delete a person from attendance records"""
    if name in st.session_state.attendance['Name'].values:
        st.session_state.attendance = st.session_state.attendance[
            st.session_state.attendance['Name'] != name
        ].reset_index(drop=True)
        save_data()
        st.success(f"Deleted {name} from attendance list")
    else:
        st.error(f"Person {name} not found")

# ------------------------------
# Calendar Helpers
# ------------------------------
def get_month_grid():
    today = date.today()
    year, month = today.year, today.month
    
    first_day = date(year, month, 1)
    last_day = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    first_day_weekday = first_day.isoweekday() % 7  # 0=Monday
    
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

def format_date_for_display(dt):
    return dt.strftime("%d")

# ------------------------------
# Other Helpers
# ------------------------------
def update_leaderboard():
    if not st.session_state.credit_data.empty:
        st.session_state.credit_data = st.session_state.credit_data.sort_values(
            by='Total_Credits', ascending=False
        ).reset_index(drop=True)

def draw_wheel(rotation_angle=0):
    n = len(st.session_state.wheel_prizes)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_aspect('equal')
    ax.axis('off')

    for i in range(n):
        start_angle = np.rad2deg(2 * np.pi * i / n + rotation_angle)
        end_angle = np.rad2deg(2 * np.pi * (i + 1) / n + rotation_angle)
        wedge = Wedge(center=(0, 0), r=1, theta1=start_angle, theta2=end_angle, 
                      width=1, facecolor=st.session_state.wheel_colors[i], edgecolor='black')
        ax.add_patch(wedge)

        mid_angle = np.deg2rad((start_angle + end_angle) / 2)
        text_x = 0.7 * np.cos(mid_angle)
        text_y = 0.7 * np.sin(mid_angle)
        ax.text(text_x, text_y, st.session_state.wheel_prizes[i],
                ha='center', va='center', rotation=np.rad2deg(mid_angle) - 90,
                fontsize=8)

    circle = plt.Circle((0, 0), 0.1, color='white', edgecolor='black')
    ax.add_patch(circle)
    ax.plot([0, 0], [0, 0.9], color='black', linewidth=2)
    ax.plot([-0.05, 0.05], [0.85, 0.9], color='black', linewidth=2)
    
    return fig

# ------------------------------
# Main App Layout
# ------------------------------
st.set_page_config(page_title="Student Council Manager", layout="wide")
st.title("Student Council Manager")

# Initialize session state
if "user" not in st.session_state:
    st.session_state.user = None
if "role" not in st.session_state:
    st.session_state.role = None

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
}
.other-month {
    background-color: #f5f5f5;
    color: #9e9e9e;
}
.day-header {
    font-weight: bold;
    text-align: center;
    padding: 8px;
}
.plan-text {
    font-size: 0.85rem;
    margin-top: 5px;
}
.delete-btn {
    background-color: #fff0f0;
    color: #dc2626;
}
.role-badge {
    border-radius: 12px;
    padding: 3px 8px;
    font-size: 0.75rem;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------
# Authentication Flow - Single Login
# ------------------------------
if not login():
    st.stop()  # Stop app if not logged in

# ------------------------------
# Sidebar with User Info & Logout
# ------------------------------
with st.sidebar:
    st.subheader(f"Logged in as: {st.session_state.user}")
    role = st.session_state.get("role", "unknown")  # Add default value "unknown"
    role_color = {
        "user": "background-color: #e0e0e0; color: #333;",
        "admin": "background-color: #e8f5e9; color: #2e7d32;",
        "creator": "background-color: #fff3e0; color: #e65100;",
        "unknown": "background-color: #f5f5f5; color: #757575;"  # Add style for unknown
    }.get(role, "background-color: #f5f5f5; color: #757575;")
    
    # Use role directly since we have a default
    st.markdown(f'<span class="role-badge" style="{role_color}">{role.capitalize()}</span>', unsafe_allow_html=True)
    logout()
    st.divider()
    
    # Creator access section
    if role != CREATOR_ROLE and st.button("Creator Access"):
        creator_login()

# ------------------------------
# Creator-only User Management
# ------------------------------
if is_creator():
    with st.sidebar.expander("User Management (Creator Only)"):
        st.subheader("Add New User")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        new_role = st.selectbox("User Role", ROLES)
        
        if st.button("Create User") and new_username and new_password:
            success, msg = save_user(new_username, new_password, new_role)
            if success:
                st.success(msg)
            else:
                st.error(msg)
        
        st.divider()
        st.subheader("Manage Existing Users")
        users = load_users()
        if users:
            selected_user = st.selectbox("Select User", list(users.keys()))
            col_update, col_delete = st.columns(2)
            
            with col_update:
                new_role = st.selectbox("New Role", ROLES + [CREATOR_ROLE], 
                                      index=ROLES.index(users[selected_user]["role"]) if users[selected_user]["role"] in ROLES else 0)
                if st.button("Update Role"):
                    success, msg = update_user_role(selected_user, new_role)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
            
            with col_delete:
                if st.button("Delete User", type="secondary"):
                    success, msg = delete_user(selected_user)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
        else:
            st.info("No users found")

# Load data after authentication
load_data()

# ------------------------------
# Main Tabs (With Role-Specific Access)
# ------------------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Calendar", 
    "Announcements",
    "Financial Optimizing", 
    "Attendance",
    "Credit & Reward System", 
    "SCIS Specific AI", 
    "Money Transfer"
])

# ------------------------------
# Tab 1: Calendar (View for all, edit for admins)
# ------------------------------
with tab1:
    st.subheader("Calendar")
    today = date.today()
    grid, month, year = get_month_grid()
    st.subheader(f"{datetime(year, month, 1).strftime('%B %Y')}")
    
    # Day headers
    headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for col, header in zip(header_cols, headers):
        col.markdown(f'<div class="day-header">{header}</div>', unsafe_allow_html=True)
    
    # Calendar grid - Viewable by all
    for week in grid:
        day_cols = st.columns(7)
        for col, dt in zip(day_cols, week):
            date_str = dt.strftime("%Y-%m-%d")
            day_display = format_date_for_display(dt)
            
            css_class = "calendar-day "
            if dt.month != month:
                css_class += "other-month "
            elif dt == today:
                css_class += "today "
            
            plan_text = st.session_state.calendar_events.get(date_str, "")
            plan_html = f'<div class="plan-text">{plan_text}</div>' if plan_text else ""
            
            col.markdown(
                f'<div class="{css_class}"><strong>{day_display}</strong>{plan_html}</div>',
                unsafe_allow_html=True
            )
    
    # Admin-only calendar management
    if is_admin():
        with st.expander("Manage Plans (Admin Only)"):
            plan_date = st.date_input("Select Date", today)
            date_str = plan_date.strftime("%Y-%m-%d")
            current_plan = st.session_state.calendar_events.get(date_str, "")
            plan_text = st.text_input("Plan (max 10 words)", current_plan)
            
            word_count = len(plan_text.split())
            if word_count > 10:
                st.warning(f"Plan is too long ({word_count} words). Max 10 words.")
            
            col_save, col_delete = st.columns(2)
            with col_save:
                if st.button("Save Plan") and word_count <= 10:
                    st.session_state.calendar_events[date_str] = plan_text
                    save_data()
                    st.success(f"Saved plan for {plan_date.strftime('%b %d')}!")
            
            with col_delete:
                if st.button("Delete Plan", type="secondary") and date_str in st.session_state.calendar_events:
                    del st.session_state.calendar_events[date_str]
                    save_data()
                    st.success(f"Deleted plan for {plan_date.strftime('%b %d')}!")

# ------------------------------
# Tab 2: Announcements (View for all, edit for admins)
# ------------------------------
with tab2:
    st.subheader("Announcements")
    
    # Viewable by all
    if st.session_state.announcements:
        sorted_announcements = sorted(
            st.session_state.announcements, 
            key=lambda x: x["time"], 
            reverse=True
        )
        
        for idx, ann in enumerate(sorted_announcements):
            col_text, col_delete = st.columns([4, 1])
            with col_text:
                st.info(f"**{datetime.fromisoformat(ann['time']).strftime('%b %d, %H:%M')}**\n\n{ann['text']}")
            with col_delete:
                if is_admin():
                    if st.button("Delete", key=f"del_ann_{idx}", type="secondary"):
                        st.session_state.announcements.pop(idx)
                        save_data()
                        st.success("Announcement deleted. Refresh to see changes.")
            
            if idx < len(sorted_announcements) - 1:
                st.divider()
    else:
        st.info("No announcements yet.")
    
    # Admin-only announcement creation
    if is_admin():
        with st.expander("Add New Announcement (Admin Only)"):
            new_announcement = st.text_area("New Announcement", "Next meeting: Friday 3 PM")
            if st.button("Post Announcement"):
                st.session_state.announcements.append({
                    "text": new_announcement,
                    "time": datetime.now().isoformat()
                })
                save_data()
                st.success("Announcement posted!")

# ------------------------------
# Tab 3: Financial Optimizing (View and use for users, full control for admins)
# ------------------------------
with tab3:
    st.subheader("Financial Progress")
    col1, col2 = st.columns(2)
    with col1:
        current_fund_raised = st.number_input("Current Fund Raised", value=0.0, step=100.0)
    with col2:
        total_funds_needed = st.number_input("Total Funds Needed", value=10000.0, step=1000.0)
    
    progress = min(100.0, (current_fund_raised / total_funds_needed) * 100) if total_funds_needed > 0 else 0
    st.slider("Current Progress", 0.0, 100.0, progress, disabled=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Scheduled Events")
        st.dataframe(st.session_state.scheduled_events, use_container_width=True)

        # Admin-only event management
        if is_admin():
            with st.expander("Add/Edit Scheduled Events (Admin Only)"):
                event_name = st.text_input("Event Name", "Fundraiser")
                funds_per_event = st.number_input("Funds Per Event", value=100.0)
                freq_per_month = st.number_input("Frequency Per Month", value=1, step=1)
                
                if st.button("Add Scheduled Event"):
                    total = funds_per_event * freq_per_month * 11
                    new_event = pd.DataFrame({
                        'Event Name': [event_name],
                        'Funds Per Event': [funds_per_event],
                        'Frequency Per Month': [freq_per_month],
                        'Total Funds': [total]
                    })
                    st.session_state.scheduled_events = pd.concat(
                        [st.session_state.scheduled_events, new_event], ignore_index=True
                    )
                    save_data()
                    st.success("Event added!")

            if not st.session_state.scheduled_events.empty:
                col_select, col_delete = st.columns([3,1])
                with col_select:
                    event_to_delete = st.selectbox("Select Event to Delete (Admin Only)", st.session_state.scheduled_events['Event Name'])
                with col_delete:
                    if st.button("Delete", type="secondary"):
                        st.session_state.scheduled_events = st.session_state.scheduled_events[
                            st.session_state.scheduled_events['Event Name'] != event_to_delete
                        ].reset_index(drop=True)
                        save_data()
                        st.success("Event deleted!")
            else:
                st.info("No scheduled events to delete.")

        if 'Total Funds' in st.session_state.scheduled_events.columns:
            total_scheduled = st.session_state.scheduled_events['Total Funds'].sum()
        else:
            total_scheduled = 0.0
        st.metric("Aggregate Funds (Scheduled)", f"${total_scheduled:.2f}")

    with col_right:
        st.subheader("Occasional Events")
        st.dataframe(st.session_state.occasional_events, use_container_width=True)

        # Admin-only event management
        if is_admin():
            with st.expander("Add/Edit Occasional Events (Admin Only)"):
                event_name = st.text_input("Event Name (Occasional)", "Charity Drive")
                funds_raised = st.number_input("Total Funds Raised", value=500.0)
                cost = st.number_input("Cost", value=100.0)
                staff_many = st.selectbox("Staff Many? (1=Yes, 0=No)", [0, 1])
                prep_time = st.selectbox("Prep Time <1 Week? (1=Yes, 0=No)", [0, 1])
                
                if st.button("Add Occasional Event"):
                    rating = (funds_raised * 0.5) - (cost * 0.5) + (staff_many * 0.1 * 100) + (prep_time * 0.1 * 100)
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
                    save_data()
                    st.success("Event added!")

            if not st.session_state.occasional_events.empty:
                col_select, col_delete = st.columns([3,1])
                with col_select:
                    event_to_delete = st.selectbox("Select Occasional Event to Delete (Admin Only)", st.session_state.occasional_events['Event Name'])
                with col_delete:
                    if st.button("Delete", type="secondary"):
                        st.session_state.occasional_events = st.session_state.occasional_events[
                            st.session_state.occasional_events['Event Name'] != event_to_delete
                        ].reset_index(drop=True)
                        save_data()
                        st.success("Event deleted!")
            else:
                st.info("No occasional events to delete.")

        # Both users and admins can sort and use optimizer
        if not st.session_state.occasional_events.empty:
            if st.button("Sort by Rating (Descending)"):
                st.session_state.occasional_events = st.session_state.occasional_events.sort_values(
                    by='Rating', ascending=False
                ).reset_index(drop=True)
                save_data()
                st.success("Sorted!")

        # Financial optimizer - Accessible to all users (main user functionality)
        if not st.session_state.occasional_events.empty:
            total_target = st.number_input("Total Fundraising Target", value=5000.0)
            if st.button("Optimize Allocation"):
                net_profits = st.session_state.occasional_events['Total Funds Raised'] - st.session_state.occasional_events['Cost']
                allocated_times = np.zeros(len(net_profits), dtype=int)
                remaining = total_target

                for i in range(len(net_profits)):
                    if remaining >= net_profits[i] and allocated_times[i] < 3:
                        allocated_times[i] = 1
                        remaining -= net_profits[i]

                while remaining > 0:
                    available = np.where(allocated_times < 3)[0]
                    if len(available) == 0:
                        break
                    best_idx = available[np.argmax(net_profits[available])]
                    if net_profits[best_idx] <= remaining:
                        allocated_times[best_idx] += 1
                        remaining -= net_profits[best_idx]
                    else:
                        break

                st.session_state.allocation_count += 1
                col_name = f'Allocated Times (Target: ${total_target})'
                st.session_state.occasional_events[col_name] = allocated_times
                save_data()
                st.success("Optimization complete!")

        if not st.session_state.occasional_events.empty and 'Total Funds Raised' in st.session_state.occasional_events.columns and 'Cost' in st.session_state.occasional_events.columns:
            total_occasional = (st.session_state.occasional_events['Total Funds Raised'] - st.session_state.occasional_events['Cost']).sum()
        else:
            total_occasional = 0.0
        st.metric("Aggregate Funds (Occasional)", f"${total_occasional:.2f}")

# ------------------------------
# Tab 4: Attendance (View for all, edit for admins)
# ------------------------------
with tab4:
    st.subheader("Attendance Records")
    
    # Show public attendance rates for all users
    st.subheader("Attendance Summary")
    attendance_rates = calculate_attendance_rates()
    st.dataframe(attendance_rates, use_container_width=True)
    
    # Admin-only detailed view
    if is_admin():
        st.subheader("Detailed Attendance (Admin Only)")
        
        if len(st.session_state.meeting_names) == 0:
            st.info("No meetings created yet. Add a meeting below.")
        else:
            st.write("Check the box if the person attended the meeting:")
            edited_attendance = st.data_editor(
                st.session_state.attendance,
                column_config={
                    "Name": st.column_config.TextColumn("Name", disabled=True),
                },
                disabled=False,
                use_container_width=True
            )
            
            if not edited_attendance.equals(st.session_state.attendance):
                st.session_state.attendance = edited_attendance
                save_data()
                st.success("Attendance records updated!")
        
        # Meeting management
        st.divider()
        st.subheader("Manage Meetings (Admin Only)")
        col_add_meeting, col_delete_meeting = st.columns(2)
        
        with col_add_meeting:
            if st.button("Add New Meeting"):
                add_new_meeting()
        
        with col_delete_meeting:
            if len(st.session_state.meeting_names) > 0:
                meeting_to_delete = st.selectbox("Select Meeting to Delete", st.session_state.meeting_names)
                if st.button("Delete Meeting", type="secondary"):
                    delete_meeting(meeting_to_delete)
            else:
                st.info("No meetings to delete")
        
        # People management
        st.divider()
        st.subheader("Manage People (Admin Only)")
        col_add_person, col_delete_person = st.columns(2)
        
        with col_add_person:
            new_person_name = st.text_input("Add New Person to Attendance List")
            if st.button("Add Person") and new_person_name:
                add_new_person(new_person_name)
        
        with col_delete_person:
            if not st.session_state.attendance.empty:
                person_to_delete = st.selectbox("Select Person to Delete", st.session_state.attendance['Name'])
                if st.button("Delete Person", type="secondary"):
                    delete_person(person_to_delete)
            else:
                st.info("No people to delete")

# ------------------------------
# Tab 5: Credit & Reward System (View for all, edit for admins)
# ------------------------------
with tab5:
    col_credits, col_rewards = st.columns(2)

    with col_credits:
        st.subheader("Student Credits")
        update_leaderboard()
        st.dataframe(st.session_state.credit_data, use_container_width=True)

        # Admin-only credit management
        if is_admin():
            with st.expander("Manage Student Credits (Admin Only)"):
                st.subheader("Add New Contribution")
                student_name = st.text_input("Student Name", "Dave")
                contribution_type = st.selectbox("Contribution Type", ["Money", "Hours", "Events"])
                amount = st.number_input("Amount", value=10.0)
                
                if st.button("Add Credits"):
                    if contribution_type == "Money":
                        credits = amount * 10
                    elif contribution_type == "Hours":
                        credits = amount * 5
                    else:
                        credits = amount * 25

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
                    save_data()
                    st.success(f"Added {credits} credits to {student_name}!")
                
                st.divider()
                st.subheader("Remove Student")
                if not st.session_state.credit_data.empty:
                    student_to_remove = st.selectbox("Select Student to Remove", st.session_state.credit_data['Name'])
                    if st.button("Remove Student", type="secondary"):
                        st.session_state.credit_data = st.session_state.credit_data[
                            st.session_state.credit_data['Name'] != student_to_remove
                        ].reset_index(drop=True)
                        save_data()
                        st.success(f"Removed {student_to_remove} from credit records")

    with col_rewards:
        st.subheader("Available Rewards")
        st.dataframe(st.session_state.reward_data, use_container_width=True)

        # Admin-only reward management
        if is_admin():
            with st.expander("Manage Rewards (Admin Only)"):
                st.subheader("Add New Reward")
                reward_name = st.text_input("Reward Name", "New Reward")
                reward_cost = st.number_input("Reward Cost (Credits)", value=50)
                reward_stock = st.number_input("Initial Stock", value=10, step=1)
                
                if st.button("Add Reward"):
                    new_reward = pd.DataFrame({
                        'Reward': [reward_name],
                        'Cost': [reward_cost],
                        'Stock': [reward_stock]
                    })
                    st.session_state.reward_data = pd.concat(
                        [st.session_state.reward_data, new_reward], ignore_index=True
                    )
                    save_data()
                    st.success(f"Added new reward: {reward_name}")
                
                st.divider()
                st.subheader("Redeem Reward")
                student_name = st.selectbox("Select Student", st.session_state.credit_data['Name'] if not st.session_state.credit_data.empty else [], key="redeem_student")
                reward_name = st.selectbox("Select Reward", st.session_state.reward_data['Reward'] if not st.session_state.reward_data.empty else [], key="redeem_reward")
                
                if st.button("Redeem") and student_name and reward_name:
                    student = st.session_state.credit_data[st.session_state.credit_data['Name'] == student_name].iloc[0]
                    reward = st.session_state.reward_data[st.session_state.reward_data['Reward'] == reward_name].iloc[0]

                    available_credits = student['Total_Credits'] - student['RedeemedCredits']
                    if available_credits >= reward['Cost'] and reward['Stock'] > 0:
                        st.session_state.credit_data.loc[
                            st.session_state.credit_data['Name'] == student_name, 'RedeemedCredits'
                        ] += reward['Cost']
                        st.session_state.reward_data.loc[
                            st.session_state.reward_data['Reward'] == reward_name, 'Stock'
                        ] -= 1
                        save_data()
                        st.success(f"{student_name} redeemed {reward_name}!")
                    else:
                        st.error("Not enough credits or reward out of stock!")
                
                st.divider()
                st.subheader("Remove Reward")
                if not st.session_state.reward_data.empty:
                    reward_to_remove = st.selectbox("Select Reward to Remove", st.session_state.reward_data['Reward'])
                    if st.button("Remove Reward", type="secondary"):
                        st.session_state.reward_data = st.session_state.reward_data[
                            st.session_state.reward_data['Reward'] != reward_to_remove
                        ].reset_index(drop=True)
                        save_data()
                        st.success(f"Removed reward: {reward_to_remove}")

    # Lucky draw accessible to admins
    if is_admin():
        st.subheader("Lucky Draw (Admin Only)")
        col_wheel, col_result = st.columns(2)
        
        with col_wheel:
            if not st.session_state.credit_data.empty:
                student_name = st.selectbox("Select Student for Lucky Draw", st.session_state.credit_data['Name'])
                if st.button("Spin Wheel") and not st.session_state.spinning:
                    st.session_state.spinning = True
                    student = st.session_state.credit_data[st.session_state.credit_data['Name'] == student_name].iloc[0]
                    
                    if student['Total_Credits'] < 50:
                        st.error("Need at least 50 credits to spin!")
                        st.session_state.spinning = False
                    else:
                        st.session_state.credit_data.loc[
                            st.session_state.credit_data['Name'] == student_name, 'Total_Credits'
                        ] -= 50

                        st.write("Spinning...")
                        time.sleep(1)
                        
                        prize_idx = np.random.randint(0, len(st.session_state.wheel_prizes))
                        final_rotation = 3 * 360 + (prize_idx * (360 / len(st.session_state.wheel_prizes)))
                        fig = draw_wheel(np.deg2rad(final_rotation))
                        col_wheel.pyplot(fig)
                        st.session_state.winner = st.session_state.wheel_prizes[prize_idx]
                        save_data()
                        st.session_state.spinning = False
            else:
                st.info("No students in credit data to select.")

        with col_result:
            if 'winner' in st.session_state:
                st.success(f"Winner: {st.session_state.winner}!")
    else:
        st.subheader("Lucky Draw")
        st.info("Lucky draw is only accessible to admins.")

# ------------------------------
# Tab 6: SCIS Specific AI (View for all)
# ------------------------------
with tab6:
    st.subheader("SCIS Specific AI")
    st.info("This section is under development and will be available soon.")

# ------------------------------
# Tab 7: Money Transfer (View for all, edit for admins)
# ------------------------------
with tab7:
    st.subheader("Money Transfer Records")
    
    if is_admin():
        st.subheader("Manage Records (Admin Only)")
        if st.button("Load Money Data"):
            if os.path.exists('Money.xlsm'):
                try:
                    st.session_state.money_data = pd.read_excel("Money.xlsm", engine='openpyxl')
                    save_data()
                    st.dataframe(st.session_state.money_data, use_container_width=True)
                except Exception as e:
                    st.error(f"Error loading Money.xlsm: {str(e)}")
            else:
                st.warning("Money.xlsm file not found. Showing empty table.")
                st.session_state.money_data = pd.DataFrame(columns=['Money', 'Time'])
                st.dataframe(st.session_state.money_data, use_container_width=True)
        
        if not st.session_state.money_data.empty:
            if st.button("Clear Money Records", type="secondary"):
                st.session_state.money_data = pd.DataFrame(columns=['Money', 'Time'])
                save_data()
                st.success("Money records cleared")
    else:
        if not st.session_state.money_data.empty:
            st.dataframe(st.session_state.money_data, use_container_width=True)
        else:
            st.info("Money transfer records will be displayed here if available.")

