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
# Configuration & Setup
# ------------------------------
st.set_page_config(page_title="SCIS StuCo HQ", layout="wide")

# File paths
DATA_FILE = "stuco_data.json"
USERS_FILE = "users.json"
CONFIG_FILE = "config.json"

# Roles configuration
ROLES = ["user", "admin", "credit_manager"]
CREATOR_ROLE = "creator"

# Initialize files if they don't exist
for file in [DATA_FILE, USERS_FILE, CONFIG_FILE]:
    if not Path(file).exists():
        initial_data = {}
        if file == CONFIG_FILE:
            initial_data = {"show_signup": False}
        with open(file, "w") as f:
            json.dump(initial_data, f)

# ------------------------------
# Style Configuration
# ------------------------------
st.markdown("""
<style>
    .welcome-header {
        text-align: center;
        margin-top: 50px;
        color: #2c3e50;
    }
    .welcome-subheader {
        text-align: center;
        color: #34495e;
    }
    .login-container {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin-top: 20px;
    }
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
    .role-badge {
        border-radius: 12px;
        padding: 3px 8px;
        font-size: 0.75rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

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

def save_user(username, password, role="user"):
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

def login():
    """Display login form in sidebar - returns True if logged in"""
    if "user" in st.session_state:
        return True

    with st.sidebar:
        st.markdown("### 🔐 Login")
        with st.container():
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            
            col1, col2 = st.columns(2)
            with col1:
                login_btn = st.button("Login", use_container_width=True)
            with col2:
                clear_btn = st.button("Clear", use_container_width=True, type="secondary")

            if clear_btn:
                st.session_state.user = None
                st.session_state.role = None
                st.rerun()

            if login_btn and username and password:
                # Check creator credentials
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
                        st.success(f"Welcome, {username}!")
                        return True
                    else:
                        st.error("Incorrect password")
                else:
                    st.error("Username not found")

    return False

def signup():
    """Display signup form in sidebar if enabled"""
    with open(CONFIG_FILE, "r") as f:
        show_signup = json.load(f).get("show_signup", False)
    
    if not show_signup:
        return

    with st.sidebar.expander("Create Account", expanded=False):
        st.subheader("Sign Up")
        new_user = st.text_input("New Username", key="signup_user")
        new_pass = st.text_input("New Password", type="password", key="signup_pass")
        confirm_pass = st.text_input("Confirm Password", type="password", key="signup_confirm")
        
        if st.button("Create Account", key="signup_btn"):
            if not new_user or not new_pass:
                st.error("Fill all fields")
                return
            if new_pass != confirm_pass:
                st.error("Passwords don't match")
                return
            
            success, msg = save_user(new_user, new_pass)
            if success:
                st.success("Account created! Please log in.")
            else:
                st.error(msg)

# ------------------------------
# Data Management
# ------------------------------
def load_data():
    """Load application data into session state"""
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        
        st.session_state.scheduled_events = pd.DataFrame(data.get("scheduled_events", []))
        st.session_state.occasional_events = pd.DataFrame(data.get("occasional_events", []))
        st.session_state.credit_data = pd.DataFrame(data.get("credit_data", []))
        st.session_state.reward_data = pd.DataFrame(data.get("reward_data", []))
        st.session_state.calendar_events = data.get("calendar_events", {})
        st.session_state.announcements = data.get("announcements", [])
        st.session_state.attendance = pd.DataFrame(data.get("attendance", {}))
        st.session_state.meeting_names = data.get("meeting_names", [])
    else:
        init_default_data()

def save_data():
    """Save session state data to file"""
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

def init_default_data():
    """Initialize default data structures"""
    st.session_state.scheduled_events = pd.DataFrame(columns=[
        'Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds'
    ])

    st.session_state.occasional_events = pd.DataFrame(columns=[
        'Event Name', 'Total Funds Raised', 'Cost', 'Staff Many Or Not', 
        'Preparation Time', 'Rating'
    ])

    st.session_state.credit_data = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Total_Credits': [200, 150, 300],
        'RedeemedCredits': [50, 0, 100]
    })

    st.session_state.reward_data = pd.DataFrame({
        'Reward': ['Bubble Tea', 'Chips', 'Café Coupon'],
        'Cost': [50, 30, 80],
        'Stock': [10, 20, 5]
    })

    st.session_state.calendar_events = {}
    st.session_state.announcements = []
    st.session_state.meeting_names = ["Meeting 1"]
    st.session_state.attendance = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Meeting 1': [True, False, True]
    })

# ------------------------------
# Permission Checks
# ------------------------------
def is_admin():
    return st.session_state.get("role") in ["admin", CREATOR_ROLE]

def is_creator():
    return st.session_state.get("role") == CREATOR_ROLE

def is_credit_manager():
    return st.session_state.get("role") == "credit_manager"

# ------------------------------
# Helper Functions
# ------------------------------
def calculate_attendance_rates():
    if not st.session_state.meeting_names:
        return pd.DataFrame({'Name': [], 'Attendance Rate (%)': []})
    
    rates = []
    for _, row in st.session_state.attendance.iterrows():
        attended = sum(row[meeting] for meeting in st.session_state.meeting_names if pd.notna(row[meeting]))
        rate = (attended / len(st.session_state.meeting_names)) * 100
        rates.append(round(rate, 1))
    
    return pd.DataFrame({
        'Name': st.session_state.attendance['Name'],
        'Attendance Rate (%)': rates
    })

def get_month_calendar():
    today = date.today()
    year, month = today.year, today.month
    
    first_day = date(year, month, 1)
    last_day = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    first_weekday = first_day.isoweekday() % 7  # 0 = Monday
    
    total_days = (last_day - first_day).days + 1
    total_slots = first_weekday + total_days
    rows = (total_slots + 6) // 7
    
    grid = []
    current_date = first_day - timedelta(days=first_weekday)
    
    for _ in range(rows):
        week = []
        for _ in range(7):
            week.append(current_date)
            current_date += timedelta(days=1)
        grid.append(week)
    
    return grid, month, year

def draw_lucky_wheel(rotation=0):
    prizes = ["50 Credits", "Bubble Tea", "Chips", "100 Credits", "Café Coupon", "Free Ticket"]
    colors = plt.cm.tab10(np.linspace(0, 1, len(prizes)))
    
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_aspect('equal')
    ax.axis('off')

    for i, (prize, color) in enumerate(zip(prizes, colors)):
        start_angle = np.rad2deg(2 * np.pi * i / len(prizes) + rotation)
        end_angle = np.rad2deg(2 * np.pi * (i + 1) / len(prizes) + rotation)
        wedge = Wedge((0, 0), 1, start_angle, end_angle, width=1, 
                      facecolor=color, edgecolor='black')
        ax.add_patch(wedge)

        mid_angle = np.deg2rad((start_angle + end_angle) / 2)
        ax.text(0.7 * np.cos(mid_angle), 0.7 * np.sin(mid_angle), prize,
                ha='center', va='center', rotation=np.rad2deg(mid_angle) - 90,
                fontsize=8)

    ax.add_patch(plt.Circle((0, 0), 0.1, color='white', edgecolor='black'))
    ax.plot([0, 0], [0, 0.9], color='black', linewidth=2)
    return fig

# ------------------------------
# Main App Layout (After Login)
# ------------------------------
def main_app():
    """Main application content shown after login"""
    # Load application data
    load_data()

    # Sidebar with user info
    with st.sidebar:
        st.subheader(f"Logged in as: {st.session_state.user}")
        
        # Role badge
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
            f'<span class="role-badge" style="{role_styles[display_role]}">{display_role.capitalize()}</span>',
            unsafe_allow_html=True
        )
        
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.role = None
            st.rerun()
        
        st.divider()

        # Creator controls
        if is_creator():
            st.subheader("Creator Settings")
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            
            new_signup_state = st.checkbox("Enable Signup", config.get("show_signup", False))
            if new_signup_state != config.get("show_signup"):
                with open(CONFIG_FILE, "w") as f:
                    json.dump({"show_signup": new_signup_state}, f)
                st.success(f"Signup {'enabled' if new_signup_state else 'disabled'}")
                st.rerun()

    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Calendar", "Announcements", "Finances", "Attendance", "Rewards"
    ])

    # Calendar Tab
    with tab1:
        st.subheader("Calendar")
        grid, month, year = get_month_calendar()
        st.subheader(f"{datetime(year, month, 1).strftime('%B %Y')}")
        
        # Day headers
        headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        header_cols = st.columns(7)
        for col, header in zip(header_cols, headers):
            col.markdown(f'<div class="day-header">{header}</div>', unsafe_allow_html=True)
        
        # Calendar grid
        for week in grid:
            day_cols = st.columns(7)
            for col, dt in zip(day_cols, week):
                date_str = dt.strftime("%Y-%m-%d")
                css = "calendar-day "
                if dt.month != month:
                    css += "other-month "
                if dt == date.today():
                    css += "today "
                
                event = st.session_state.calendar_events.get(date_str, "")
                event_html = f"<br>{event}" if event else ""
                
                col.markdown(
                    f'<div class="{css}"><strong>{dt.day}</strong>{event_html}</div>',
                    unsafe_allow_html=True
                )
        
        # Admin event management
        if is_admin():
            with st.expander("Manage Events (Admin)"):
                event_date = st.date_input("Event Date")
                event_text = st.text_input("Event Description")
                if st.button("Save Event"):
                    st.session_state.calendar_events[event_date.strftime("%Y-%m-%d")] = event_text
                    save_data()
                    st.success("Event saved!")

    # Announcements Tab
    with tab2:
        st.subheader("Announcements")
        
        # Show announcements
        if st.session_state.announcements:
            for idx, ann in enumerate(sorted(
                st.session_state.announcements, 
                key=lambda x: x["time"], 
                reverse=True
            )):
                col_text, col_del = st.columns([4, 1])
                with col_text:
                    st.info(f"**{datetime.fromisoformat(ann['time']).strftime('%b %d, %H:%M')}**\n\n{ann['text']}")
                with col_del:
                    if is_admin() and st.button("×", key=f"del_ann_{idx}", type="secondary"):
                        st.session_state.announcements.pop(idx)
                        save_data()
                        st.rerun()
        else:
            st.info("No announcements yet")
        
        # Add announcement (admin)
        if is_admin():
            with st.expander("Add Announcement (Admin)"):
                new_ann = st.text_area("New Announcement")
                if st.button("Post"):
                    st.session_state.announcements.append({
                        "text": new_ann,
                        "time": datetime.now().isoformat()
                    })
                    save_data()
                    st.success("Announcement posted!")

    # Finances Tab
    with tab3:
        st.subheader("Financial Management")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Scheduled Events")
            st.dataframe(st.session_state.scheduled_events, use_container_width=True)
            
            if is_admin():
                with st.expander("Add Scheduled Event"):
                    name = st.text_input("Event Name")
                    funds = st.number_input("Funds Per Event", 0.0)
                    freq = st.number_input("Monthly Frequency", 1, 31)
                    
                    if st.button("Add"):
                        total = funds * freq * 12
                        new_event = pd.DataFrame({
                            'Event Name': [name],
                            'Funds Per Event': [funds],
                            'Frequency Per Month': [freq],
                            'Total Funds': [total]
                        })
                        st.session_state.scheduled_events = pd.concat(
                            [st.session_state.scheduled_events, new_event], ignore_index=True
                        )
                        save_data()
                        st.success("Event added!")

        with col2:
            st.subheader("Occasional Events")
            st.dataframe(st.session_state.occasional_events, use_container_width=True)
            
            if is_admin():
                with st.expander("Add Occasional Event"):
                    name = st.text_input("Event Name")
                    raised = st.number_input("Funds Raised", 0.0)
                    cost = st.number_input("Cost", 0.0)
                    
                    if st.button("Add"):
                        rating = (raised * 0.6) - (cost * 0.4)
                        new_event = pd.DataFrame({
                            'Event Name': [name],
                            'Total Funds Raised': [raised],
                            'Cost': [cost],
                            'Rating': [rating]
                        })
                        st.session_state.occasional_events = pd.concat(
                            [st.session_state.occasional_events, new_event], ignore_index=True
                        )
                        save_data()
                        st.success("Event added!")

    # Attendance Tab
    with tab4:
        st.subheader("Attendance Tracking")
        st.dataframe(calculate_attendance_rates(), use_container_width=True)
        
        if is_admin():
            with st.expander("Manage Attendance (Admin)"):
                st.dataframe(st.session_state.attendance, use_container_width=True)
                if st.button("Add Meeting"):
                    new_meeting = f"Meeting {len(st.session_state.meeting_names) + 1}"
                    st.session_state.meeting_names.append(new_meeting)
                    st.session_state.attendance[new_meeting] = False
                    save_data()
                    st.success(f"Added {new_meeting}")

    # Rewards Tab
    with tab5:
        col_credits, col_rewards = st.columns(2)
        
        with col_credits:
            st.subheader("Student Credits")
            st.dataframe(st.session_state.credit_data, use_container_width=True)
            
            if is_credit_manager() or is_admin():
                with st.expander("Manage Credits"):
                    student = st.text_input("Student Name")
                    credits = st.number_input("Add Credits", 10, 1000)
                    if st.button("Add"):
                        if student in st.session_state.credit_data['Name'].values:
                            st.session_state.credit_data.loc[
                                st.session_state.credit_data['Name'] == student, 'Total_Credits'
                            ] += credits
                        else:
                            new_row = pd.DataFrame({
                                'Name': [student],
                                'Total_Credits': [credits],
                                'RedeemedCredits': [0]
                            })
                            st.session_state.credit_data = pd.concat(
                                [st.session_state.credit_data, new_row], ignore_index=True
                            )
                        save_data()
                        st.success(f"Added {credits} credits to {student}")
        
        with col_rewards:
            st.subheader("Available Rewards")
            st.dataframe(st.session_state.reward_data, use_container_width=True)
            
            if is_admin():
                with st.expander("Lucky Draw"):
                    if not st.session_state.credit_data.empty:
                        student = st.selectbox("Select Student", st.session_state.credit_data['Name'])
                        if st.button("Spin Wheel (50 credits)"):
                            student_data = st.session_state.credit_data[
                                st.session_state.credit_data['Name'] == student
                            ].iloc[0]
                            
                            if student_data['Total_Credits'] >= 50:
                                st.session_state.credit_data.loc[
                                    st.session_state.credit_data['Name'] == student, 'Total_Credits'
                                ] -= 50
                                
                                st.write("Spinning...")
                                time.sleep(1)
                                final_rotation = np.random.uniform(0, 2 * np.pi)
                                st.pyplot(draw_lucky_wheel(final_rotation))
                                save_data()
                            else:
                                st.error("Not enough credits (needs 50)")

# ------------------------------
# Application Entry Point
# ------------------------------
def main():
    # Check login status
    logged_in = login()
    signup()  # Show signup form if enabled

    # Show welcome screen if not logged in
    if not logged_in:
        st.markdown("# <div class='welcome-header'>Welcome to SCIS HQ US StuCo</div>", unsafe_allow_html=True)
        st.markdown("## <div class='welcome-subheader'>Please log in to access the student council management system</div>", unsafe_allow_html=True)
        return

    # Show main app if logged in
    st.title("SCIS Student Council Management System")
    main_app()

if __name__ == "__main__":
    main()
