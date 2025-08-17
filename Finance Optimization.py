import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
from datetime import datetime
import time
import os  # Added for file existence checks

# ------------------------------
# Initialize Session State with Error Handling
# ------------------------------
def safe_init_data():
    """Initialize and load data with checks for missing files"""
    
    # Initialize only if not already in session state
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
        # Try to load from file if exists, else use sample data
        if os.path.exists('Credit_Data.csv'):
            try:
                st.session_state.credit_data = pd.read_csv('Credit_Data.csv')
            except:
                st.warning("Credit_Data.csv found but could not be loaded. Using sample data.")
                st.session_state.credit_data = pd.DataFrame({
                    'Name': ['Alice', 'Bob', 'Charlie'],
                    'Total_Credits': [200, 150, 300],
                    'RedeemedCredits': [50, 0, 100]
                })
        else:
            st.session_state.credit_data = pd.DataFrame({
                'Name': ['Alice', 'Bob', 'Charlie'],
                'Total_Credits': [200, 150, 300],
                'RedeemedCredits': [50, 0, 100]
            })

    if 'reward_data' not in st.session_state:
        # Try to load from file if exists, else use sample data
        if os.path.exists('Reward_Data.csv'):
            try:
                st.session_state.reward_data = pd.read_csv('Reward_Data.csv')
            except:
                st.warning("Reward_Data.csv found but could not be loaded. Using sample data.")
                st.session_state.reward_data = pd.DataFrame({
                    'Reward': ['Bubble Tea', 'Chips', 'Café Coupon'],
                    'Cost': [50, 30, 80],
                    'Stock': [10, 20, 5]
                })
        else:
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
        st.session_state.is_admin = False  # Track admin status

# Initialize data when app starts
setup_init_data()

# ------------------------------
# Admin Authentication
# ------------------------------
def admin_login():
    """Simple admin login with password check"""
    admin_password = "admin123"  # CHANGE THIS TO A SECURE PASSWORD!
    password = st.text_input("Enter Admin Password (leave blank for user access)", type="password")
    
    if password == admin_password:
        st.session_state.is_admin = True
        st.success("Logged in as Admin!")
    elif password != "":  # If user entered something but wrong
        st.error("Incorrect password. Accessing as regular user.")
        st.session_state.is_admin = False
    else:  # No password entered = regular user
        st.session_state.is_admin = False
        st.info("Accessing as regular user (view-only for most features)")

# ------------------------------
# Helper Functions
# ------------------------------
def update_leaderboard():
    """Sort credit data by total credits (descending)"""
    st.session_state.credit_data = st.session_state.credit_data.sort_values(
        by='Total_Credits', ascending=False
    ).reset_index(drop=True)

def draw_wheel(rotation_angle=0):
    """Draw the lucky draw wheel with matplotlib"""
    n = len(st.session_state.wheel_prizes)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_aspect('equal')
    ax.axis('off')

    # Draw sectors
    for i in range(n):
        start_angle = np.rad2deg(2 * np.pi * i / n + rotation_angle)
        end_angle = np.rad2deg(2 * np.pi * (i + 1) / n + rotation_angle)
        wedge = Wedge(center=(0, 0), r=1, theta1=start_angle, theta2=end_angle, 
                      width=1, facecolor=st.session_state.wheel_colors[i], edgecolor='black')
        ax.add_patch(wedge)

        # Add prize text
        mid_angle = np.deg2rad((start_angle + end_angle) / 2)
        text_x = 0.7 * np.cos(mid_angle)
        text_y = 0.7 * np.sin(mid_angle)
        ax.text(text_x, text_y, st.session_state.wheel_prizes[i],
                ha='center', va='center', rotation=np.rad2deg(mid_angle) - 90,
                fontsize=8)

    # Draw center circle
    circle = plt.Circle((0, 0), 0.1, color='white', edgecolor='black')
    ax.add_patch(circle)

    # Draw pointer
    ax.plot([0, 0], [0, 0.9], color='black', linewidth=2)
    ax.plot([-0.05, 0.05], [0.85, 0.9], color='black', linewidth=2)
    return fig

# ------------------------------
# Main App Layout
# ------------------------------
st.set_page_config(page_title="Student Council Fund Management", layout="wide")
st.title("Student Council Fund Management")

# Admin Login Section (always at top)
with st.sidebar:
    st.subheader("Access Control")
    admin_login()
    st.divider()
    
    # File status information
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

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "Financial Optimizing", 
    "Credit & Reward System", 
    "SCIS Specific AI", 
    "Money Transfer"
])

# ------------------------------
# Tab 1: Financial Optimizing (Public calculator, admin-only edits)
# ------------------------------
with tab1:
    st.subheader("Financial Progress")
    col1, col2 = st.columns(2)
    with col1:
        current_fund_raised = st.number_input("Current Fund Raised", value=0.0, step=100.0, disabled=not st.session_state.is_admin)
    with col2:
        total_funds_needed = st.number_input("Total Funds Needed", value=10000.0, step=1000.0, disabled=not st.session_state.is_admin)
    
    # Calculate progress percentage
    progress = min(100.0, (current_fund_raised / total_funds_needed) * 100) if total_funds_needed > 0 else 0
    st.slider("Current Progress", 0.0, 100.0, progress, disabled=True)

    # Split into Scheduled Events and Occasional Events panels
    col_left, col_right = st.columns(2)

    # Left Panel: Scheduled Events
    with col_left:
        st.subheader("Scheduled Events")
        st.dataframe(st.session_state.scheduled_events, use_container_width=True)

        # Input new scheduled event (ADMIN ONLY)
        if st.session_state.is_admin:
            with st.expander("Add New Scheduled Event (Admin Only)"):
                event_name = st.text_input("Event Name", "Fundraiser")
                funds_per_event = st.number_input("Funds Per Event", value=100.0)
                freq_per_month = st.number_input("Frequency Per Month", value=1, step=1)
                
                if st.button("Add Scheduled Event"):
                    total = funds_per_event * freq_per_month * 11  # 11 weeks
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

        # Delete scheduled event (ADMIN ONLY)
        if st.session_state.is_admin and not st.session_state.scheduled_events.empty:
            event_to_delete = st.selectbox("Select Event to Delete (Admin Only)", st.session_state.scheduled_events['Event Name'])
            if st.button("Delete Scheduled Event"):
                st.session_state.scheduled_events = st.session_state.scheduled_events[
                    st.session_state.scheduled_events['Event Name'] != event_to_delete
                ].reset_index(drop=True)
                st.success("Event deleted!")

        # Total funds for scheduled events (visible to all)
        total_scheduled = st.session_state.scheduled_events['Total Funds'].sum()
        st.metric("Aggregate Funds (Scheduled)", f"${total_scheduled:.2f}")

    # Right Panel: Occasional Events
    with col_right:
        st.subheader("Occasional Events")
        st.dataframe(st.session_state.occasional_events, use_container_width=True)

        # Input new occasional event (ADMIN ONLY)
        if st.session_state.is_admin:
            with st.expander("Add New Occasional Event (Admin Only)"):
                event_name = st.text_input("Event Name (Occasional)", "Charity Drive")
                funds_raised = st.number_input("Total Funds Raised", value=500.0)
                cost = st.number_input("Cost", value=100.0)
                staff_many = st.selectbox("Staff Many? (1=Yes, 0=No)", [0, 1])
                prep_time = st.selectbox("Prep Time <1 Week? (1=Yes, 0=No)", [0, 1])
                
                if st.button("Add Occasional Event"):
                    # Calculate rating
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

        # Delete occasional event (ADMIN ONLY)
        if st.session_state.is_admin and not st.session_state.occasional_events.empty:
            event_to_delete = st.selectbox("Select Event to Delete (Admin Only)", st.session_state.occasional_events['Event Name'])
            if st.button("Delete Occasional Event"):
                st.session_state.occasional_events = st.session_state.occasional_events[
                    st.session_state.occasional_events['Event Name'] != event_to_delete
                ].reset_index(drop=True)
                st.success("Event deleted!")

        # Sort by rating (ADMIN ONLY)
        if st.session_state.is_admin and not st.session_state.occasional_events.empty:
            if st.button("Sort by Rating (Descending)"):
                st.session_state.occasional_events = st.session_state.occasional_events.sort_values(
                    by='Rating', ascending=False
                ).reset_index(drop=True)
                st.success("Sorted!")

        # Optimize event allocation (PUBLIC - anyone can use calculator)
        if not st.session_state.occasional_events.empty:
            total_target = st.number_input("Total Fundraising Target (Public Calculator)", value=5000.0)
            if st.button("Optimize Allocation (Public)"):
                net_profits = st.session_state.occasional_events['Total Funds Raised'] - st.session_state.occasional_events['Cost']
                allocated_times = np.zeros(len(net_profits), dtype=int)
                remaining = total_target

                # Ensure each event is held at least once (if affordable)
                for i in range(len(net_profits)):
                    if remaining >= net_profits[i] and allocated_times[i] < 3:
                        allocated_times[i] = 1
                        remaining -= net_profits[i]

                # Greedy allocation for remaining funds
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

                # Add allocation as a new column
                st.session_state.allocation_count += 1
                col_name = f'Allocated Times (Target: ${total_target})'
                st.session_state.occasional_events[col_name] = allocated_times
                st.success("Optimization complete!")

        # Total net funds for occasional events (visible to all)
        if not st.session_state.occasional_events.empty:
            total_occasional = (st.session_state.occasional_events['Total Funds Raised'] - st.session_state.occasional_events['Cost']).sum()
            st.metric("Aggregate Funds (Occasional)", f"${total_occasional:.2f}")

# ------------------------------
# Tab 2: Credit & Reward System (Admin-only edits)
# ------------------------------
with tab2:
    col_credits, col_rewards = st.columns(2)

    # Left: Credit Management (Viewable by all, editable by admin)
    with col_credits:
        st.subheader("Student Credits")
        update_leaderboard()
        st.dataframe(st.session_state.credit_data, use_container_width=True)

        # Input new credits (ADMIN ONLY)
        if st.session_state.is_admin:
            with st.expander("Log New Contribution (Admin Only)"):
                student_name = st.text_input("Student Name", "Dave")
                contribution_type = st.selectbox("Contribution Type", ["Money", "Hours", "Events"])
                amount = st.number_input("Amount", value=10.0)
                
                if st.button("Add Credits"):
                    # Calculate credits
                    if contribution_type == "Money":
                        credits = amount * 10  # $1 = 10 credits
                    elif contribution_type == "Hours":
                        credits = amount * 5   # 1 hour = 5 credits
                    else:  # Events
                        credits = amount * 25  # 1 event = 25 credits

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
                    st.success(f"Added {credits} credits to {student_name}!")

    # Right: Reward Management (Viewable by all, editable by admin)
    with col_rewards:
        st.subheader("Available Rewards")
        st.dataframe(st.session_state.reward_data, use_container_width=True)

        # Redeem rewards (ADMIN ONLY)
        if st.session_state.is_admin:
            with st.expander("Redeem Reward (Admin Only)"):
                student_name = st.selectbox("Select Student", st.session_state.credit_data['Name'])
                reward_name = st.selectbox("Select Reward", st.session_state.reward_data['Reward'])
                
                if st.button("Redeem"):
                    # Check if student and reward exist
                    student = st.session_state.credit_data[st.session_state.credit_data['Name'] == student_name].iloc[0]
                    reward = st.session_state.reward_data[st.session_state.reward_data['Reward'] == reward_name].iloc[0]

                    # Check credits and stock
                    available_credits = student['Total_Credits'] - student['RedeemedCredits']
                    if available_credits >= reward['Cost'] and reward['Stock'] > 0:
                        # Update student credits
                        st.session_state.credit_data.loc[
                            st.session_state.credit_data['Name'] == student_name, 'RedeemedCredits'
                        ] += reward['Cost']
                        # Update reward stock
                        st.session_state.reward_data.loc[
                            st.session_state.reward_data['Reward'] == reward_name, 'Stock'
                        ] -= 1
                        st.success(f"{student_name} redeemed {reward_name}!")
                    else:
                        st.error("Not enough credits or reward out of stock!")

    # Lucky Draw Wheel (ADMIN ONLY - affects credits)
    if st.session_state.is_admin:
        st.subheader("Lucky Draw (Admin Only)")
        col_wheel, col_result = st.columns(2)
        
        with col_wheel:
            student_name = st.selectbox("Select Student for Lucky Draw", st.session_state.credit_data['Name'])
            if st.button("Spin Wheel"):
                # Check credits
                student = st.session_state.credit_data[st.session_state.credit_data['Name'] == student_name].iloc[0]
                if student['Total_Credits'] < 50:
                    st.error("Need at least 50 credits to spin!")
                else:
                    # Deduct credits
                    st.session_state.credit_data.loc[
                        st.session_state.credit_data['Name'] == student_name, 'Total_Credits'
                    ] -= 50

                    # Animate wheel
                    st.write("Spinning...")
                    for i in range(50):  # 50 animation steps
                        rotation = (3 * 360) + (i * 10)  # Spin 3 full circles + incremental
                        fig = draw_wheel(np.deg2rad(rotation))
                        col_wheel.pyplot(fig)
                        time.sleep(0.05)

                    # Final result
                    prize_idx = np.random.randint(0, len(st.session_state.wheel_prizes))
                    final_rotation = 3 * 360 + (prize_idx * (360 / len(st.session_state.wheel_prizes)))
                    fig = draw_wheel(np.deg2rad(final_rotation))
                    col_wheel.pyplot(fig)
                    st.session_state.winner = st.session_state.wheel_prizes[prize_idx]

        with col_result:
            if 'winner' in st.session_state:
                st.success(f"Winner: {st.session_state.winner}!")
    else:
        st.subheader("Lucky Draw")
        st.info("Lucky draw is only accessible to admins.")

# ------------------------------
# Tab 3: SCIS Specific AI (Empty as requested)
# ------------------------------
with tab3:
    st.subheader("SCIS Specific AI")
    st.info("This section is under development and will be available soon.")

# ------------------------------
# Tab 4: Money Transfer (Optional file loading)
# ------------------------------
with tab4:
    st.subheader("Money Transfer Records")
    
    # Load data (ADMIN can load, users can view)
    if st.session_state.is_admin:
        if st.button("Load Money Data (Admin Only)"):
            if os.path.exists('Money.xlsm'):
                try:
                    st.session_state.money_data = pd.read_excel("Money.xlsm", engine='openpyxl')
                    st.dataframe(st.session_state.money_data, use_container_width=True)
                except Exception as e:
                    st.error(f"Error loading Money.xlsm: {str(e)}")
                    st.info("Showing empty table instead.")
            else:
                st.warning("Money.xlsm file not found. Showing empty table.")
                st.session_state.money_data = pd.DataFrame(columns=['Money', 'Time'])
                st.dataframe(st.session_state.money_data, use_container_width=True)
    else:
        if not st.session_state.money_data.empty:
            st.dataframe(st.session_state.money_data, use_container_width=True)
        else:
            st.info("Money transfer records will be displayed here if available. Contact an admin to load data.")