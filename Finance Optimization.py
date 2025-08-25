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
# App Configuration
# ------------------------------
st.set_page_config(page_title="SCIS Stuco HQ", layout="wide")

# ------------------------------
# File Paths & Initialization
# ------------------------------
DATA_FILE = "stuco_data.json"
USERS_FILE = "stuco_users.json"
CONFIG_FILE = "stuco_config.json"

# Ensure data files exist
for file in [DATA_FILE, USERS_FILE, CONFIG_FILE]:
    if not Path(file).exists():
        initial_data = {}
        if file == CONFIG_FILE:
            initial_data = {"show_signup": False}
        with open(file, "w") as f:
            json.dump(initial_data, f)

# ------------------------------
# Role Definitions
# ------------------------------
ROLES = ["member", "admin", "treasurer"]
CREATOR_ROLE = "creator"

# ------------------------------
# Session State Initialization
# ------------------------------
def init_session_state():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "login_attempted" not in st.session_state:
        st.session_state.login_attempted = False
    if "wheel_prizes" not in st.session_state:
        st.session_state.wheel_prizes = ["50 Credits", "Bubble Tea", "Chips", "100 Credits", "Café Coupon", "Free Prom Ticket"]
    if "wheel_colors" not in st.session_state:
        st.session_state.wheel_colors = plt.cm.tab10(np.linspace(0, 1, len(st.session_state.wheel_prizes)))
    if "spinning" not in st.session_state:
        st.session_state.spinning = False

init_session_state()

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
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed_password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_user(username, password, role="member"):
    users = load_users()
    if username in users:
        return False, "Username exists"
    
    users[username] = {
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now().isoformat()
    }
    
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    return True, "User created"

# ------------------------------
# Data Management
# ------------------------------
def load_app_data():
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        
        st.session_state.scheduled_events = pd.DataFrame(data.get("scheduled_events", []))
        st.session_state.occasional_events = pd.DataFrame(data.get("occasional_events", []))
        st.session_state.credit_data = pd.DataFrame(data.get("credit_data", []))
        st.session_state.reward_data = pd.DataFrame(data.get("reward_data", []))
        st.session_state.calendar_events = data.get("calendar_events", {})
        st.session_state.announcements = data.get("announcements", [])
        st.session_state.attendance = pd.DataFrame(data.get("attendance", []))
        st.session_state.meeting_names = data.get("meeting_names", [])
    else:
        init_default_data()

def init_default_data():
    st.session_state.scheduled_events = pd.DataFrame(columns=[
        'Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds'
    ])

    st.session_state.occasional_events = pd.DataFrame(columns=[
        'Event Name', 'Total Funds Raised', 'Cost', 'Staff Needed', 
        'Prep Time (Weeks)', 'Rating'
    ])

    st.session_state.credit_data = pd.DataFrame({
        'Name': ['Emma', 'Liam', 'Olivia'],
        'Total_Credits': [150, 200, 100],
        'RedeemedCredits': [30, 0, 50]
    })

    st.session_state.reward_data = pd.DataFrame({
        'Reward': ['Bubble Tea', 'Chips', 'Café Coupon'],
        'Cost': [50, 30, 80],
        'Stock': [10, 20, 5]
    })

    st.session_state.calendar_events = {}
    st.session_state.announcements = []
    st.session_state.meeting_names = ["First Meeting"]
    st.session_state.attendance = pd.DataFrame({
        'Name': ['Emma', 'Liam', 'Olivia'],
        'First Meeting': [True, False, True]
    })

def save_app_data():
    data = {
        "scheduled_events": st.session_state.scheduled_events.to_dict(orient="records"),
        "occasional_events": st.session_state.occasional_events.to_dict(orient="records"),
        "credit_data": st.session_state.credit_data.to_dict(orient="records"),
        "reward_data": st.session_state.reward_data.to_dict(orient="records"),
        "calendar_events": st.session_state.calendar_events,
        "announcements": st.session_state.announcements,
        "attendance": st.session_state.attendance.to_dict(orient="records"),
        "meeting_names": st.session_state.meeting_names
    }
    
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ------------------------------
# Login/Signup Functions
# ------------------------------
def show_login_form():
    """Display login form in sidebar"""
    with st.sidebar:
        st.subheader("Account Login")
        
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        
        col_login, col_clear = st.columns(2)
        with col_login:
            if st.button("Login", use_container_width=True):
                st.session_state.login_attempted = True
                return process_login(username, password)
        
        with col_clear:
            if st.button("Clear", use_container_width=True, type="secondary"):
                st.session_state.login_user = ""
                st.session_state.login_pass = ""
                st.session_state.login_attempted = False
                st.rerun()
        
        # Show signup if enabled
        config = load_config()
        if config.get("show_signup", False):
            with st.expander("Create New Account"):
                new_user = st.text_input("New Username", key="new_user")
                new_pass = st.text_input("New Password", type="password", key="new_pass")
                confirm_pass = st.text_input("Confirm Password", type="password", key="confirm_pass")
                
                if st.button("Sign Up", key="signup_btn"):
                    if not new_user or not new_pass:
                        st.error("Fill all fields")
                        return False
                    if new_pass != confirm_pass:
                        st.error("Passwords don't match")
                        return False
                    
                    success, msg = save_user(new_user, new_pass)
                    if success:
                        st.success("Account created! Please log in.")
                    else:
                        st.error(msg)
                    return False
    
    return False

def process_login(username, password):
    """Authenticate user credentials"""
    # Check creator credentials first
    creator_user = st.secrets.get("creator", {}).get("username", "")
    creator_pass = st.secrets.get("creator", {}).get("password", "")
    
    if username == creator_user and password == creator_pass and creator_user:
        st.session_state.user = username
        st.session_state.role = CREATOR_ROLE
        st.success("Logged in as Creator!")
        return True
    
    # Check regular users
    users = load_users()
    if username in users:
        if verify_password(password, users[username]["password_hash"]):
            st.session_state.user = username
            st.session_state.role = users[username]["role"]
            st.success(f"Logged in as {username}")
            return True
        else:
            st.error("Incorrect password")
    else:
        st.error("Username not found")
    
    return False

def show_logout_option():
    """Show logout button in sidebar for logged-in users"""
    with st.sidebar:
        st.subheader(f"Logged in as: {st.session_state.user}")
        
        # Role badge
        role = st.session_state.get("role", "unknown")
        role_styles = {
            "member": "background-color: #e0e0e0; color: #333;",
            "admin": "background-color: #e8f5e9; color: #2e7d32;",
            "treasurer": "background-color: #e3f2fd; color: #1976d2;",
            "creator": "background-color: #fff3e0; color: #e65100;",
            "unknown": "background-color: #f5f5f5; color: #757575;"
        }
        display_role = role if role in role_styles else "unknown"
        st.markdown(
            f'<span style="border-radius:12px;padding:3px 8px;font-size:0.75rem;font-weight:bold;'
            f'{role_styles[display_role]}">{display_role.capitalize()}</span>',
            unsafe_allow_html=True
        )
        
        if st.button("Logout", use_container_width=True, type="secondary"):
            st.session_state.user = None
            st.session_state.role = None
            st.success("Logged out successfully")
            st.rerun()
        
        st.divider()

# ------------------------------
# Permission Checks
# ------------------------------
def is_admin():
    return st.session_state.get("role") in ["admin", CREATOR_ROLE]

def is_treasurer():
    return st.session_state.get("role") in ["treasurer", CREATOR_ROLE]

def is_creator():
    return st.session_state.get("role") == CREATOR_ROLE

# ------------------------------
# Helper Functions
# ------------------------------
def calculate_attendance_rates():
    if not st.session_state.meeting_names:
        return pd.DataFrame({'Name': [], 'Attendance Rate (%)': []})
    
    rates = []
    for _, row in st.session_state.attendance.iterrows():
        attended = sum(row[meeting] for meeting in st.session_state.meeting_names 
                      if pd.notna(row[meeting]))
        rate = (attended / len(st.session_state.meeting_names)) * 100
        rates.append(round(rate, 1))
    
    return pd.DataFrame({
        'Name': st.session_state.attendance['Name'],
        'Attendance Rate (%)': rates
    })

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

    ax.plot([0, 0], [0, 0.9], color='black', linewidth=2)
    ax.plot([-0.05, 0.05], [0.85, 0.9], color='black', linewidth=2)
    return fig

# ------------------------------
# Main App Tabs
# ------------------------------
def show_calendar_tab():
    st.subheader("Student Council Calendar")
    today = date.today()
    year, month = today.year, today.month
    
    # Generate calendar grid
    first_day = date(year, month, 1)
    last_day = (date(year, month+1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    first_weekday = first_day.weekday()  # 0=Monday
    
    # Create calendar grid
    grid = []
    current = first_day - timedelta(days=first_weekday)
    for _ in range(6):  # Max 6 weeks
        week = []
        for _ in range(7):
            week.append(current)
            current += timedelta(days=1)
        grid.append(week)
        if current > last_day:
            break
    
    # Display calendar headers
    headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")
    
    # Display calendar days
    for week in grid:
        day_cols = st.columns(7)
        for col, dt in zip(day_cols, week):
            date_str = dt.strftime("%Y-%m-%d")
            css = "background-color:#e3f2fd;" if dt == today else ""
            if dt.month != month:
                css = "background-color:#f0f0f0;color:#999;"
            
            events = st.session_state.calendar_events.get(date_str, "")
            col.markdown(
                f'<div style="border:1px solid #ddd;padding:5px;border-radius:5px;{css}">'
                f'<strong>{dt.day}</strong><br>'
                f'<small>{events}</small></div>',
                unsafe_allow_html=True
            )
    
    # Admin controls
    if is_admin():
        with st.expander("Manage Calendar Events (Admin Only)"):
            event_date = st.date_input("Select Date")
            event_text = st.text_input("Event Description")
            date_key = event_date.strftime("%Y-%m-%d")
            
            if st.button("Save Event"):
                st.session_state.calendar_events[date_key] = event_text
                save_app_data()
                st.success("Event saved!")
            
            if date_key in st.session_state.calendar_events:
                if st.button("Delete Event", type="secondary"):
                    del st.session_state.calendar_events[date_key]
                    save_app_data()
                    st.success("Event deleted!")

def show_announcements_tab():
    st.subheader("Announcements")
    
    # Display announcements
    if st.session_state.announcements:
        for idx, ann in enumerate(sorted(
            st.session_state.announcements, 
            key=lambda x: x["time"], 
            reverse=True
        )):
            col_text, col_del = st.columns([5, 1])
            with col_text:
                st.info(f"**{datetime.fromisoformat(ann['time']).strftime('%b %d, %H:%M')}**\n\n{ann['text']}")
            with col_del:
                if is_admin() and st.button("×", key=f"del_ann_{idx}", type="secondary"):
                    st.session_state.announcements.pop(idx)
                    save_app_data()
                    st.rerun()
    else:
        st.info("No announcements yet.")
    
    # Add announcement (admin only)
    if is_admin():
        with st.expander("Add New Announcement (Admin Only)"):
            new_ann = st.text_area("Announcement Text")
            if st.button("Post Announcement"):
                st.session_state.announcements.append({
                    "text": new_ann,
                    "time": datetime.now().isoformat()
                })
                save_app_data()
                st.success("Announcement posted!")

def show_finance_tab():
    st.subheader("Financial Management")
    
    col1, col2 = st.columns(2)
    with col1:
        current_funds = st.number_input("Current Funds", value=0.0, step=100.0)
    with col2:
        target_funds = st.number_input("Fundraising Target", value=5000.0, step=500.0)
    
    # Progress indicator
    progress = min(100.0, (current_funds / target_funds) * 100) if target_funds > 0 else 0
    st.progress(progress / 100)
    st.caption(f"Progress: {progress:.1f}% of target")

    # Scheduled events
    st.subheader("Scheduled Events")
    st.dataframe(st.session_state.scheduled_events, use_container_width=True)
    
    if is_treasurer():
        with st.expander("Add Scheduled Event (Treasurer/Admin Only)"):
            event_name = st.text_input("Event Name")
            funds_per = st.number_input("Funds Per Event", 0.0, step=50.0)
            freq = st.number_input("Monthly Frequency", 1, 12)
            
            if st.button("Add Event"):
                total = funds_per * freq * 12
                new_event = pd.DataFrame([{
                    'Event Name': event_name,
                    'Funds Per Event': funds_per,
                    'Frequency Per Month': freq,
                    'Total Funds': total
                }])
                st.session_state.scheduled_events = pd.concat(
                    [st.session_state.scheduled_events, new_event], ignore_index=True
                )
                save_app_data()
                st.success("Event added!")

    # Occasional events
    st.subheader("Occasional Events")
    st.dataframe(st.session_state.occasional_events, use_container_width=True)
    
    if is_treasurer():
        with st.expander("Add Occasional Event (Treasurer/Admin Only)"):
            event_name = st.text_input("Event Name (Occasional)")
            funds_raised = st.number_input("Funds Raised", 0.0)
            cost = st.number_input("Event Cost", 0.0)
            staff = st.slider("Staff Needed (1-10)", 1, 10)
            prep_time = st.number_input("Prep Time (Weeks)", 1, 8)
            
            if st.button("Add Occasional Event"):
                rating = (funds_raised - cost) - (staff * 10) - (prep_time * 15)
                new_event = pd.DataFrame([{
                    'Event Name': event_name,
                    'Total Funds Raised': funds_raised,
                    'Cost': cost,
                    'Staff Needed': staff,
                    'Prep Time (Weeks)': prep_time,
                    'Rating': rating
                }])
                st.session_state.occasional_events = pd.concat(
                    [st.session_state.occasional_events, new_event], ignore_index=True
                )
                save_app_data()
                st.success("Event added!")

def show_attendance_tab():
    st.subheader("Meeting Attendance")
    
    # Show summary
    rates = calculate_attendance_rates()
    st.dataframe(rates, use_container_width=True)
    
    # Admin controls
    if is_admin():
        st.subheader("Detailed Records (Admin Only)")
        edited = st.data_editor(
            st.session_state.attendance,
            column_config={"Name": st.column_config.TextColumn(disabled=True)},
            use_container_width=True
        )
        
        if not edited.equals(st.session_state.attendance):
            st.session_state.attendance = edited
            save_app_data()
            st.success("Attendance updated!")
        
        # Manage meetings
        st.subheader("Manage Meetings")
        col_add, col_del = st.columns(2)
        with col_add:
            if st.button("Add New Meeting"):
                new_meeting = f"Meeting {len(st.session_state.meeting_names) + 1}"
                st.session_state.meeting_names.append(new_meeting)
                st.session_state.attendance[new_meeting] = False
                save_app_data()
                st.success(f"Added {new_meeting}")
        
        with col_del:
            if st.session_state.meeting_names:
                to_delete = st.selectbox("Delete Meeting", st.session_state.meeting_names)
                if st.button("Delete Selected", type="secondary"):
                    st.session_state.meeting_names.remove(to_delete)
                    st.session_state.attendance = st.session_state.attendance.drop(columns=[to_delete])
                    save_app_data()
                    st.success(f"Deleted {to_delete}")

def show_credits_tab():
    col_credits, col_rewards = st.columns(2)
    
    with col_credits:
        st.subheader("Student Credits")
        st.dataframe(st.session_state.credit_data, use_container_width=True)
        
        if is_treasurer():
            with st.expander("Manage Credits (Treasurer/Admin Only)"):
                student = st.text_input("Student Name")
                contribution = st.selectbox("Contribution Type", ["Event Help", "Fundraising", "Meeting"])
                amount = st.number_input("Amount", 1)
                
                if st.button("Add Credits"):
                    credit_values = {"Event Help": 20, "Fundraising": 50, "Meeting": 10}
                    credits = amount * credit_values[contribution]
                    
                    if student in st.session_state.credit_data['Name'].values:
                        st.session_state.credit_data.loc[
                            st.session_state.credit_data['Name'] == student, 'Total_Credits'
                        ] += credits
                    else:
                        new_entry = pd.DataFrame([{
                            'Name': student,
                            'Total_Credits': credits,
                            'RedeemedCredits': 0
                        }])
                        st.session_state.credit_data = pd.concat(
                            [st.session_state.credit_data, new_entry], ignore_index=True
                        )
                    save_app_data()
                    st.success(f"Added {credits} credits to {student}")
    
    with col_rewards:
        st.subheader("Rewards Catalog")
        st.dataframe(st.session_state.reward_data, use_container_width=True)
        
        if is_admin():
            with st.expander("Manage Rewards (Admin Only)"):
                reward = st.text_input("Reward Name")
                cost = st.number_input("Credit Cost", 10, step=10)
                stock = st.number_input("Stock Quantity", 1)
                
                if st.button("Add Reward"):
                    new_reward = pd.DataFrame([{
                        'Reward': reward,
                        'Cost': cost,
                        'Stock': stock
                    }])
                    st.session_state.reward_data = pd.concat(
                        [st.session_state.reward_data, new_reward], ignore_index=True
                    )
                    save_app_data()
                    st.success(f"Added {reward}")
    
    # Lucky draw
    if is_admin():
        st.subheader("Lucky Draw")
        if not st.session_state.credit_data.empty:
            student = st.selectbox("Select Student", st.session_state.credit_data['Name'])
            if st.button("Spin Wheel") and not st.session_state.spinning:
                st.session_state.spinning = True
                student_data = st.session_state.credit_data[
                    st.session_state.credit_data['Name'] == student
                ].iloc[0]
                
                if student_data['Total_Credits'] < 50:
                    st.error("Need 50 credits to spin!")
                    st.session_state.spinning = False
                else:
                    st.session_state.credit_data.loc[
                        st.session_state.credit_data['Name'] == student, 'Total_Credits'
                    ] -= 50
                    
                    # Animate spin
                    for _ in range(10):
                        rotation = np.random.uniform(0, 2*np.pi)
                        fig = draw_wheel(rotation)
                        st.pyplot(fig)
                        time.sleep(0.1)
                    
                    # Final result
                    final_idx = np.random.randint(0, len(st.session_state.wheel_prizes))
                    final_rotation = 3*2*np.pi + (final_idx * (2*np.pi / len(st.session_state.wheel_prizes)))
                    fig = draw_wheel(final_rotation)
                    st.pyplot(fig)
                    st.success(f"{student} won: {st.session_state.wheel_prizes[final_idx]}!")
                    save_app_data()
                    st.session_state.spinning = False

# ------------------------------
# Main Application Flow
# ------------------------------
def main():
    # Custom CSS
    st.markdown("""
    <style>
    .welcome-header {
        text-align: center;
        padding: 2rem 0;
    }
    .app-header {
        padding: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # Check login status
    if not st.session_state.user:
        # Show welcome screen for non-logged-in users
        st.markdown('<h1 class="welcome-header">Welcome to SCIS HQ US Stuco</h1>', unsafe_allow_html=True)
        st.image("https://picsum.photos/800/400", use_column_width=True, 
                 caption="Student Council Management System")
        
        # Show login form in sidebar - app stops here if not logged in
        if not show_login_form():
            return
    
    # If logged in, show main app
    st.markdown('<h1 class="app-header">SCIS Student Council Manager</h1>', unsafe_allow_html=True)
    show_logout_option()
    load_app_data()

    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Calendar", 
        "Announcements", 
        "Financials", 
        "Attendance", 
        "Credits & Rewards"
    ])

    with tab1:
        show_calendar_tab()
    with tab2:
        show_announcements_tab()
    with tab3:
        show_finance_tab()
    with tab4:
        show_attendance_tab()
    with tab5:
        show_credits_tab()

    # Creator-only settings
    if is_creator():
        with st.sidebar.expander("Creator Settings", expanded=False):
            config = load_config()
            new_signup = st.checkbox("Enable Signup", config.get("show_signup", False))
            if new_signup != config.get("show_signup"):
                config["show_signup"] = new_signup
                save_config(config)
                st.success(f"Signup {'enabled' if new_signup else 'disabled'}")

if __name__ == "__main__":
    main()
