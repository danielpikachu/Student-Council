import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
from datetime import datetime, date, timedelta
import time
import os

# ------------------------------
# Initialize Session State
# ------------------------------
def safe_init_data():
    # Existing data initializations
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
        st.session_state.wheel_prizes = ["50 Credits", "Bubble Tea", "Chips", "100 Credits", "Café Coupon", "Free Prom Ticket"]
        st.session_state.wheel_colors = plt.cm.tab10(np.linspace(0, 1, len(st.session_state.wheel_prizes)))

    if 'money_data' not in st.session_state:
        st.session_state.money_data = pd.DataFrame(columns=['Money', 'Time'])

    if 'allocation_count' not in st.session_state:
        st.session_state.allocation_count = 0

    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False

    if 'spinning' not in st.session_state:
        st.session_state.spinning = False

    # New: Calendar events (date: plan)
    if 'calendar_events' not in st.session_state:
        st.session_state.calendar_events = {}  # Format: {"YYYY-MM-DD": "Short plan text"}

    # New: Announcements (list of dicts with timestamp)
    if 'announcements' not in st.session_state:
        st.session_state.announcements = []  # Format: [{"text": "...", "time": datetime}, ...]

# Initialize data
safe_init_data()

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
# Helper Functions
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

# New: Get current month's dates
def get_current_month_dates():
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    # Get last day of month
    if today.month == 12:
        end_of_month = date(today.year, today.month, 31)
    else:
        end_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)
    
    # Generate all dates in month
    dates = []
    current_date = start_of_month
    while current_date <= end_of_month:
        dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    return dates

# ------------------------------
# Main App Layout
# ------------------------------
st.set_page_config(page_title="Student Council Fund Management", layout="wide")
st.title("Student Council Fund Management")

with st.sidebar:
    st.subheader("Access Control")
    admin_login()
    st.divider()
    
    # New: Data file status only visible to admin
    if st.session_state.is_admin:
        st.subheader("Data File Status")
        if os.path.exists('Credit_Data.csv'):
            st.success("✅ Credit_Data.csv found")
        else:
            st.info("ℹ️ Credit_Data.csv not found - using sample data")
            
        if os.path.exists('Reward_Data.csv'):
            st.success("✅ Reward_Data.csv found")
        else:
            st.info("ℹ️ Reward_Data.csv not found - using sample data")
            
        if os.path.exists('Money.xlsm'):
            st.success("✅ Money.xlsm found")
        else:
            st.info("ℹ️ Money.xlsm not found - table will be empty")

# New: Tabs reordered with calendar (1st) and announcements (2nd)
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Calendar", 
    "Announcements",
    "Financial Optimizing", 
    "Credit & Reward System", 
    "SCIS Specific AI", 
    "Money Transfer"
])

# ------------------------------
# New Tab 1: Calendar (1st tab)
# ------------------------------
with tab1:
    st.subheader(f"Monthly Plans - {date.today().strftime('%B %Y')}")
    
    # Get current month dates
    month_dates = get_current_month_dates()
    
    # Display calendar events
    for d in month_dates:
        # Format date for display (e.g., "2023-10-05" → "Oct 05 (Thu)")
        display_date = datetime.strptime(d, "%Y-%m-%d").strftime("%b %d (%a)")
        
        # Show event if exists
        event_text = st.session_state.calendar_events.get(d, "No plans")
        st.write(f"**{display_date}**: {event_text}")
    
    # Admin-only: Add new plan
    if st.session_state.is_admin:
        with st.expander("Add New Plan (Admin Only)"):
            plan_date = st.date_input("Select Date", date.today())
            plan_text = st.text_input("Plan (max 10 words)", "Fundraiser meeting")
            
            # Validate word count
            word_count = len(plan_text.split())
            if word_count > 10:
                st.warning(f"Plan is too long ({word_count} words). Max 10 words.")
            
            if st.button("Add Plan") and word_count <= 10:
                date_str = plan_date.strftime("%Y-%m-%d")
                st.session_state.calendar_events[date_str] = plan_text
                st.success(f"Added plan for {plan_date.strftime('%b %d')}!")

# ------------------------------
# New Tab 2: Announcements (2nd tab)
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
            st.info(f"**{ann['time'].strftime('%b %d, %H:%M')}**\n\n{ann['text']}")
            if idx < len(sorted_announcements) - 1:
                st.divider()
    else:
        st.info("No announcements yet.")
    
    # Admin-only: Add new announcement
    if st.session_state.is_admin:
        with st.expander("Add New Announcement (Admin Only)"):
            new_announcement = st.text_area("New Announcement", "Next meeting: Friday 3 PM")
            if st.button("Post Announcement"):
                st.session_state.announcements.append({
                    "text": new_announcement,
                    "time": datetime.now()  # Auto-add timestamp
                })
                st.success("Announcement posted!")

# ------------------------------
# Tab 3: Financial Optimizing (fully accessible to users)
# ------------------------------
with tab3:
    st.subheader("Financial Progress")
    col1, col2 = st.columns(2)
    with col1:
        # New: Fully accessible to users (removed disabled flag)
        current_fund_raised = st.number_input("Current Fund Raised", value=0.0, step=100.0)
    with col2:
        # New: Fully accessible to users
        total_funds_needed = st.number_input("Total Funds Needed", value=10000.0, step=1000.0)
    
    progress = min(100.0, (current_fund_raised / total_funds_needed) * 100) if total_funds_needed > 0 else 0
    st.slider("Current Progress", 0.0, 100.0, progress, disabled=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Scheduled Events")
        st.dataframe(st.session_state.scheduled_events, use_container_width=True)

        # New: Fully accessible to users (removed admin check)
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
                st.success("Event added!")

        # New: Fully accessible to users
        if not st.session_state.scheduled_events.empty:
            event_to_delete = st.selectbox("Select Event to Delete", st.session_state.scheduled_events['Event Name'])
            if st.button("Delete Scheduled Event"):
                st.session_state.scheduled_events = st.session_state.scheduled_events[
                    st.session_state.scheduled_events['Event Name'] != event_to_delete
                ].reset_index(drop=True)
                st.success("Event deleted!")

        total_scheduled = st.session_state.scheduled_events['Total Funds'].sum()
        st.metric("Aggregate Funds (Scheduled)", f"${total_scheduled:.2f}")

    with col_right:
        st.subheader("Occasional Events")
        st.dataframe(st.session_state.occasional_events, use_container_width=True)

        # New: Fully accessible to users
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
                st.success("Event added!")

        # New: Fully accessible to users
        if not st.session_state.occasional_events.empty:
            event_to_delete = st.selectbox("Select Occasional Event to Delete", st.session_state.occasional_events['Event Name'])
            if st.button("Delete Occasional Event"):
                st.session_state.occasional_events = st.session_state.occasional_events[
                    st.session_state.occasional_events['Event Name'] != event_to_delete
                ].reset_index(drop=True)
                st.success("Event deleted!")

        # New: Fully accessible to users
        if not st.session_state.occasional_events.empty:
            if st.button("Sort by Rating (Descending)"):
                st.session_state.occasional_events = st.session_state.occasional_events.sort_values(
                    by='Rating', ascending=False
                ).reset_index(drop=True)
                st.success("Sorted!")

        if not st.session_state.occasional_events.empty:
            total_target = st.number_input("Total Fundraising Target (Public Calculator)", value=5000.0)
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
                st.success("Optimization complete!")

        if not st.session_state.occasional_events.empty:
            total_occasional = (st.session_state.occasional_events['Total Funds Raised'] - st.session_state.occasional_events['Cost']).sum()
            st.metric("Aggregate Funds (Occasional)", f"${total_occasional:.2f}")

# ------------------------------
# Tab 4: Credit & Reward System (unchanged, admin-only edits)
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
