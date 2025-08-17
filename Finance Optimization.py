import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
from datetime import datetime, date, timedelta
import time
import os
import json
from pathlib import Path

# ------------------------------
# Persistent Data Storage (Fixes Refresh Reset Issue)
# ------------------------------
DATA_FILE = "app_data.json"

def load_data():
    """Load data from JSON file (persists between app restarts)"""
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        
        # Restore data to session state
        st.session_state.scheduled_events = pd.DataFrame(data["scheduled_events"])
        st.session_state.occasional_events = pd.DataFrame(data["occasional_events"])
        st.session_state.credit_data = pd.DataFrame(data["credit_data"])
        st.session_state.reward_data = pd.DataFrame(data["reward_data"])
        st.session_state.calendar_events = data["calendar_events"]
        st.session_state.announcements = data["announcements"]
        st.session_state.money_data = pd.DataFrame(data["money_data"])
    else:
        # Initialize with default data if file doesn't exist
        safe_init_data()
        save_data()  # Create the file

def save_data():
    """Save current session state to JSON file"""
    # Convert DataFrames to dicts for JSON serialization
    data = {
        "scheduled_events": st.session_state.scheduled_events.to_dict(orient="records"),
        "occasional_events": st.session_state.occasional_events.to_dict(orient="records"),
        "credit_data": st.session_state.credit_data.to_dict(orient="records"),
        "reward_data": st.session_state.reward_data.to_dict(orient="records"),
        "calendar_events": st.session_state.calendar_events,
        "announcements": st.session_state.announcements,
        "money_data": st.session_state.money_data.to_dict(orient="records")
    }
    
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def safe_init_data():
    """Initialize default data if no saved data exists"""
    if 'scheduled_events' not in st.session_state:
        st.session_state.scheduled_events = pd.DataFrame(columns=[
            'Event Name', 'Funds Per Event', 'Frequency Per Month', 'Total Funds'
        ])

    if 'occasional_events' not in st.session_state:
        st.session_state.occasional_events = pd.DataFrame(columns=[
            'Event Name', 'Total Funds Raised', 'Cost', 'Staff Many Or Not', 
            'Preparation Time', 'Rating'
        ])

    if 'credit_data' not in st.session_state:
        st.session_state.credit_data = pd.DataFrame({
            'Name': ['Alice', 'Bob', 'Charlie'],
            'Total_Credits': [200, 150, 300],
            'RedeemedCredits': [50, 0, 100]
        })

    if 'reward_data' not in st.session_state:
        st.session_state.reward_data = pd.DataFrame({
            'Reward': ['Bubble Tea', 'Chips', 'Café Coupon'],
            'Cost': [50, 30, 80],
            'Stock': [10, 20, 5]
        })

    if 'wheel_prizes' not in st.session_state:
        st.session_state.wheel_prizes = ["50 Credits", "Bubble Tea", "Chips", "100 Creditsits", "Café Coupon", "Free Prom Ticket"]
        st.session_state.wheel_colors = plt.cm.tab10(np.linspace(0, 1, len(st.session_state.wheel_prizes)))

    if 'money_data' not in st.session_state:
        st.session_state.money_data = pd.DataFrame(columns=['Money', 'Time'])

    if 'allocation_count' not in st.session_state:
        st.session_state.allocation_count = 0

    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False

    if 'spinning' not in st.session_state:
        st.session_state.spinning = False

    if 'calendar_events' not in st.session_state:
        st.session_state.calendar_events = {}  # {"YYYY-MM-DD": "Plan text"}

    if 'announcements' not in st.session_state:
        st.session_state.announcements = []  # [{"text": "...", "time": "ISO string"}]

# Load persistent data on app start
load_data()

# ------------------------------
# Admin Authentication
# ------------------------------
def admin_login():
    admin_password = "admin123"  # CHANGE THIS!
    password = st.text_input("Enter Admin Password (leave blank for user access)", type="password")
    
    if password == admin_password:
        st.session_state.is_admin = True
        st.success("Logged in as Admin!")
    elif password != "":
        st.error("Incorrect password. Accessing as regular user.")
        st.session_state.is_admin = False
    else:
        st.session_state.is_admin = False
        st.info("Accessing as regular user")

# ------------------------------
# Calendar Helper Functions
# ------------------------------
def get_month_grid():
    """Generate a grid of dates for the current month (including empty days)"""
    today = date.today()
    year, month = today.year, today.month
    
    # Get first and last day of the month
    first_day = date(year, month, 1)
    last_day = (date(year, month + 1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    
    # Get day of week for first day (0=Monday, 6=Sunday in ISO week)
    first_day_weekday = first_day.isoweekday() % 7  # Convert to 0=Monday, 6=Sunday
    
    # Calculate number of rows needed (weeks)
    total_days = (last_day - first_day).days + 1
    total_slots = first_day_weekday + total_days
    rows = (total_slots + 6) // 7  # Round up to nearest week
    
    # Create grid: list of lists (each sublist = 1 week)
    grid = []
    current_date = first_day - timedelta(days=first_day_weekday)  # Start from first slot
    
    for _ in range(rows):
        week = []
        for _ in range(7):
            week.append(current_date)
            current_date += timedelta(days=1)
        grid.append(week)
    
    return grid, month, year

def format_date_for_display(dt):
    """Format date as "DD" (e.g., "05" for 5th)"""
    return dt.strftime("%d")

# ------------------------------
# Other Helpers
# ------------------------------
def update_leaderboard():
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

# Custom CSS for calendar grid
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
    background-color: #e3f2fd;  /* Light blue for today */
}
.other-month {
    background-color: #f5f5f5;  /* Gray for days from other months */
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
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Access Control")
    admin_login()
    st.divider()
    
    # Admin-only data status
    if st.session_state.is_admin:
        st.subheader("Data File Status")
        st.success("✅ Data automatically saved")
        if os.path.exists(DATA_FILE):
            st.info(f"Data stored in: {DATA_FILE}")
        else:
            st.warning("Data file will be created on first save")

# Tabs with new order
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Calendar", 
    "Announcements",
    "Financial Optimizing", 
    "Credit & Reward System", 
    "SCIS Specific AI", 
    "Money Transfer"
])

# ------------------------------
# Tab 1: Grid-Style Calendar (1st tab)
# ------------------------------
with tab1:
    today = date.today()
    grid, month, year = get_month_grid()
    st.subheader(f"{datetime(year, month, 1).strftime('%B %Y')}")
    
    # Day headers (Monday to Sunday)
    headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for col, header in zip(header_cols, headers):
        col.markdown(f'<div class="day-header">{header}</div>', unsafe_allow_html=True)
    
    # Display calendar grid
    for week in grid:
        day_cols = st.columns(7)
        for col, dt in zip(day_cols, week):
            # Format date
            date_str = dt.strftime("%Y-%m-%d")
            day_display = format_date_for_display(dt)
            
            # Determine CSS class
            css_class = "calendar-day "
            if dt.month != month:
                css_class += "other-month "  # Days from other months
            elif dt == today:
                css_class += "today "  # Highlight today
            
            # Get plan text if exists
            plan_text = st.session_state.calendar_events.get(date_str, "")
            plan_html = f'<div class="plan-text">{plan_text}</div>' if plan_text else ""
            
            # Display day square
            col.markdown(
                f'<div class="{css_class}"><strong>{day_display}</strong>{plan_html}</div>',
                unsafe_allow_html=True
            )
    
    # Admin-only: Add/edit plans
    if st.session_state.is_admin:
        with st.expander("Add/Edit Plan (Admin Only)"):
            plan_date = st.date_input("Select Date", today)
            date_str = plan_date.strftime("%Y-%m-%d")
            current_plan = st.session_state.calendar_events.get(date_str, "")
            plan_text = st.text_input("Plan (max 10 words)", current_plan)
            
            # Validate word count
            word_count = len(plan_text.split())
            if word_count > 10:
                st.warning(f"Plan is too long ({word_count} words). Max 10 words.")
            
            # Buttons
            col_save, col_delete = st.columns(2)
            with col_save:
                if st.button("Save Plan") and word_count <= 10:
                    st.session_state.calendar_events[date_str] = plan_text
                    save_data()  # Save to file
                    st.success(f"Saved plan for {plan_date.strftime('%b %d')}!")
            
            with col_delete:
                if st.button("Delete Plan") and date_str in st.session_state.calendar_events:
                    del st.session_state.calendar_events[date_str]
                    save_data()  # Save to file
                    st.success(f"Deleted plan for {plan_date.strftime('%b %d')}!")

# ------------------------------
# Tab 2: Announcements (2nd tab)
# ------------------------------
with tab2:
    st.subheader("Announcements")
    
    # Display announcements (newest first)
    if st.session_state.announcements:
        # Sort by timestamp (newest first)
        sorted_announcements = sorted(
            st.session_state.announcements, 
            key=lambda x: x["time"], 
            reverse=True
        )
        
        for idx, ann in enumerate(sorted_announcements):
            st.info(f"**{datetime.fromisoformat(ann['time']).strftime('%b %d, %H:%M')}**\n\n{ann['text']}")
            if idx < len(sorted_announcements) - 1:
                st.divider()
                
            # Admin-only delete button
            if st.session_state.is_admin:
                if st.button(f"Delete this announcement", key=f"del_{idx}"):
                    st.session_state.announcements.pop(idx)
                    save_data()  # Save to file
                    st.success("Announcement deleted. Refresh to see changes.")
    else:
        st.info("No announcements yet.")
    
    # Admin-only: Add new announcement
    if st.session_state.is_admin:
        with st.expander("Add New Announcement (Admin Only)"):
            new_announcement = st.text_area("New Announcement", "Next meeting: Friday 3 PM")
            if st.button("Post Announcement"):
                st.session_state.announcements.append({
                    "text": new_announcement,
                    "time": datetime.now().isoformat()  # ISO format for easy parsing
                })
                save_data()  # Save to file
                st.success("Announcement posted!")

# ------------------------------
# Tab 3: Financial Optimizing
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

        with st.expander("Add New Scheduled Event"):
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
                save_data()  # Save to file
                st.success("Event added!")

        if not st.session_state.scheduled_events.empty:
            event_to_delete = st.selectbox("Select Event to Delete", st.session_state.scheduled_events['Event Name'])
            if st.button("Delete Scheduled Event"):
                st.session_state.scheduled_events = st.session_state.scheduled_events[
                    st.session_state.scheduled_events['Event Name'] != event_to_delete
                ].reset_index(drop=True)
                save_data()  # Save to file
                st.success("Event deleted!")

        total_scheduled = st.session_state.scheduled_events['Total Funds'].sum()
        st.metric("Aggregate Funds (Scheduled)", f"${total_scheduled:.2f}")

    with col_right:
        st.subheader("Occasional Events")
        st.dataframe(st.session_state.occasional_events, use_container_width=True)

        with st.expander("Add New Occasional Event"):
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
                save_data()  # Save to file
                st.success("Event added!")

        if not st.session_state.occasional_events.empty:
            event_to_delete = st.selectbox("Select Occasional Event to Delete", st.session_state.occasional_events['Event Name'])
            if st.button("Delete Occasional Event"):
                st.session_state.occasional_events = st.session_state.occasional_events[
                    st.session_state.occasional_events['Event Name'] != event_to_delete
                ].reset_index(drop=True)
                save_data()  # Save to file
                st.success("Event deleted!")

        if not st.session_state.occasional_events.empty:
            if st.button("Sort by Rating (Descending)"):
                st.session_state.occasional_events = st.session_state.occasional_events.sort_values(
                    by='Rating', ascending=False
                ).reset_index(drop=True)
                save_data()  # Save to file
                st.success("Sorted!")

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
                save_data()  # Save to file
                st.success("Optimization complete!")

        if not st.session_state.occasional_events.empty:
            total_occasional = (st.session_state.occasional_events['Total Funds Raised'] - st.session_state.occasional_events['Cost']).sum()
            st.metric("Aggregate Funds (Occasional)", f"${total_occasional:.2f}")

# ------------------------------
# Tab 4: Credit & Reward System
# ------------------------------
with tab4:
    col_credits, col_rewards = st.columns(2)

    with col_credits:
        st.subheader("Student Credits")
        update_leaderboard()
        st.dataframe(st.session_state.credit_data, use_container_width=True)

        if st.session_state.is_admin:
            with st.expander("Log New Contribution (Admin Only)"):
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
                    save_data()  # Save to file
                    st.success(f"Added {credits} credits to {student_name}!")

    with col_rewards:
        st.subheader("Available Rewards")
        st.dataframe(st.session_state.reward_data, use_container_width=True)

        if st.session_state.is_admin:
            with st.expander("Redeem Reward (Admin Only)"):
                student_name = st.selectbox("Select Student", st.session_state.credit_data['Name'])
                reward_name = st.selectbox("Select Reward", st.session_state.reward_data['Reward'])
                
                if st.button("Redeem"):
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
                        save_data()  # Save to file
                        st.success(f"{student_name} redeemed {reward_name}!")
                    else:
                        st.error("Not enough credits or reward out of stock!")

    if st.session_state.is_admin:
        st.subheader("Lucky Draw (Admin Only)")
        col_wheel, col_result = st.columns(2)
        
        with col_wheel:
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
                    save_data()  # Save to file
                    st.session_state.spinning = False

        with col_result:
            if 'winner' in st.session_state:
                st.success(f"Winner: {st.session_state.winner}!")
    else:
        st.subheader("Lucky Draw")
        st.info("Lucky draw is only accessible to admins.")

# ------------------------------
# Tab 5: SCIS Specific AI
# ------------------------------
with tab5:
    st.subheader("SCIS Specific AI")
    st.info("This section is under development and will be available soon.")

# ------------------------------
# Tab 6: Money Transfer
# ------------------------------
with tab6:
    st.subheader("Money Transfer Records")
    
    if st.session_state.is_admin:
        if st.button("Load Money Data (Admin Only)"):
            if os.path.exists('Money.xlsm'):
                try:
                    st.session_state.money_data = pd.read_excel("Money.xlsm", engine='openpyxl')
                    save_data()  # Save to file
                    st.dataframe(st.session_state.money_data, use_container_width=True)
                except Exception as e:
                    st.error(f"Error loading Money.xlsm: {str(e)}")
            else:
                st.warning("Money.xlsm file not found. Showing empty table.")
                st.session_state.money_data = pd.DataFrame(columns=['Money', 'Time'])
                st.dataframe(st.session_state.money_data, use_container_width=True)
    else:
        if not st.session_state.money_data.empty:
            st.dataframe(st.session_state.money_data, use_container_width=True)
        else:
            st.info("Money transfer records will be displayed here if available.")
