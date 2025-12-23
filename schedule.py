import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_calendar import calendar
import json

# Page configuration
st.set_page_config(page_title="Production Scheduler", layout="wide", initial_sidebar_state="expanded")

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None
if 'last_saved' not in st.session_state:
    st.session_state.last_saved = None
if 'pending_calendar_changes' not in st.session_state:
    st.session_state.pending_calendar_changes = {}
if 'force_calendar_refresh' not in st.session_state:
    st.session_state.force_calendar_refresh = False

# Color mapping for statuses
STATUS_COLORS = {
    'Completed': '#28a745',  # Green
    'In Progress': '#007bff',  # Blue
    'Scheduled': '#ffc107',  # Yellow
    'Placeholder': '#fd7e14',  # Orange
    'Unscheduled': '#6c757d'  # Grey
}

def load_data(uploaded_file):
    """Load and clean the CSV data"""
    try:
        df = pd.read_csv(uploaded_file)
        
        # Clean and standardize column names
        df.columns = df.columns.str.strip()
        
        # Convert date columns
        date_columns = ['Scheduled Date', 'Actual Delivery Date']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Add color column based on status
        if 'Status' in df.columns:
            df['Color'] = df['Status'].map(STATUS_COLORS).fillna(STATUS_COLORS['Unscheduled'])
        else:
            df['Color'] = STATUS_COLORS['Scheduled']
        
        # Add type column (Job vs Placeholder)
        if 'Type' not in df.columns:
            df['Type'] = 'Job'
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

def update_colors(df):
    """Update color column based on status"""
    if 'Status' in df.columns:
        df['Color'] = df['Status'].map(STATUS_COLORS).fillna(STATUS_COLORS['Unscheduled'])
    return df

def df_to_calendar_events(df):
    """Convert dataframe to FullCalendar event format"""
    events = []
    
    for idx, row in df.iterrows():
        # Skip rows without scheduled dates
        if pd.isna(row.get('Scheduled Date')):
            continue
        
        # Create event title
        title = f"{row.get('WO', 'N/A')} - {row.get('Customer Name', 'N/A')}"
        
        # Create event object
        event = {
            'title': title,
            'start': row['Scheduled Date'].strftime('%Y-%m-%d'),
            'id': str(idx),  # Use index as unique ID
            'backgroundColor': row.get('Color', STATUS_COLORS['Scheduled']),
            'borderColor': row.get('Color', STATUS_COLORS['Scheduled']),
            'extendedProps': {
                'wo': str(row.get('WO', '')),
                'customer': str(row.get('Customer Name', '')),
                'model': str(row.get('Model Description', '')),
                'price': str(row.get('Price', '')),
                'status': str(row.get('Status', ''))
            }
        }
        events.append(event)
    
    return events

def save_data(df, filename="ORDER_BOOK_TRACKER_UPDATED.csv"):
    """Save dataframe back to CSV"""
    try:
        # Remove Color column before saving (it's computed)
        df_to_save = df.drop(columns=['Color'], errors='ignore')
        df_to_save.to_csv(filename, index=False)
        st.session_state.last_saved = datetime.now()
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

# Main UI
st.title("🏭 Production Scheduler")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("📁 Data Management")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload Order Book CSV", type=['csv'])
    
    if uploaded_file is not None:
        if st.button("Load Data", type="primary"):
            st.session_state.df = load_data(uploaded_file)
            st.session_state.pending_calendar_changes = {}
            st.session_state.force_calendar_refresh = False
            if st.session_state.df is not None:
                st.success(f"Loaded {len(st.session_state.df)} orders")
    
    st.markdown("---")
    
    # Add Placeholder functionality
    if st.session_state.df is not None:
        st.header("➕ Add Placeholder")
        
        with st.form("add_placeholder"):
            placeholder_name = st.text_input("Description", "Tentative - Customer")
            placeholder_date = st.date_input("Date")
            submit_placeholder = st.form_submit_button("Add Placeholder")
            
            if submit_placeholder:
                new_row = {
                    'WO': f'PLACEHOLDER-{len(st.session_state.df)+1}',
                    'Quote': '',
                    'PO Number': '',
                    'Status': 'Placeholder',
                    'Customer Name': placeholder_name,
                    'Model Description': 'Placeholder',
                    'Scheduled Date': pd.Timestamp(placeholder_date),
                    'Actual Delivery Date': pd.NaT,
                    'Price': '',
                    'Color': STATUS_COLORS['Placeholder'],
                    'Type': 'Placeholder'
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.df = st.session_state.df.reset_index(drop=True)
                st.session_state.force_calendar_refresh = True
                st.success("Placeholder added!")
                st.rerun()
    
    st.markdown("---")
    
    # Save functionality
    if st.session_state.df is not None:
        st.header("💾 Save Changes")
        
        if st.button("Save to CSV", type="primary"):
            if save_data(st.session_state.df):
                st.success("✅ Data saved successfully!")
                st.download_button(
                    label="Download Updated CSV",
                    data=st.session_state.df.to_csv(index=False).encode('utf-8'),
                    file_name=f"order_book_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime='text/csv'
                )
        
        if st.session_state.last_saved:
            st.info(f"Last saved: {st.session_state.last_saved.strftime('%I:%M %p')}")

# Main content area
if st.session_state.df is not None:
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_orders = len(st.session_state.df[st.session_state.df['Type'] == 'Job'])
        st.metric("Total Orders", total_orders)
    
    with col2:
        scheduled = len(st.session_state.df[st.session_state.df['Scheduled Date'].notna()])
        st.metric("Scheduled", scheduled)
    
    with col3:
        unscheduled = len(st.session_state.df[st.session_state.df['Scheduled Date'].isna()])
        st.metric("Unscheduled", unscheduled)
    
    with col4:
        completed = len(st.session_state.df[st.session_state.df['Status'] == 'Completed'])
        st.metric("Completed", completed)
    
    st.markdown("---")
    
    # Create tabs for Calendar and Table views
    tab1, tab2 = st.tabs(["📅 Calendar View", "📋 Order Book Table"])
    
    with tab1:
        st.subheader("Production Calendar")
        
        # Show pending changes notification and buttons at the top
        if st.session_state.pending_calendar_changes:
            st.warning(f"⚠️ {len(st.session_state.pending_calendar_changes)} pending change(s)")
            
            # Show what's pending
            with st.expander("View Pending Changes"):
                for event_id, new_date in st.session_state.pending_calendar_changes.items():
                    wo = st.session_state.df.loc[event_id, 'WO']
                    old_date = st.session_state.df.loc[event_id, 'Scheduled Date']
                    st.write(f"**{wo}**: {old_date.strftime('%Y-%m-%d') if pd.notna(old_date) else 'None'} → {new_date.strftime('%Y-%m-%d')}")
            
            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("✅ Update Schedule", type="primary", key="update_calendar_btn"):
                    # Apply all pending changes
                    for event_id, new_date in st.session_state.pending_calendar_changes.items():
                        st.session_state.df.loc[event_id, 'Scheduled Date'] = new_date
                    
                    # Update colors in case status changed
                    st.session_state.df = update_colors(st.session_state.df)
                    
                    # Clear pending changes and force refresh
                    st.session_state.pending_calendar_changes = {}
                    st.session_state.force_calendar_refresh = True
                    st.success(f"✅ Schedule updated successfully!")
                    st.rerun()
            
            with col2:
                if st.button("❌ Cancel", key="cancel_calendar_btn"):
                    st.session_state.pending_calendar_changes = {}
                    st.session_state.force_calendar_refresh = True
                    st.rerun()
        
        st.markdown("---")
        
        # Calendar configuration
        calendar_options = {
            "editable": True,
            "selectable": True,
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay"
            },
            "initialView": "dayGridMonth",
            "height": 650,
        }
        
        # Convert dataframe to events
        events = df_to_calendar_events(st.session_state.df)
        
        # Create unique key for calendar to force refresh when needed
        calendar_key = f"calendar_{hash(str(st.session_state.df['Scheduled Date'].tolist()))}"
        if st.session_state.force_calendar_refresh:
            calendar_key = f"calendar_{datetime.now().timestamp()}"
            st.session_state.force_calendar_refresh = False
        
        # Display calendar
        calendar_result = calendar(
            events=events,
            options=calendar_options,
            key=calendar_key,
            custom_css="""
                .fc-event-past {
                    opacity: 0.8;
                }
                .fc-event {
                    font-size: 0.85em;
                    cursor: move;
                }
            """
        )
        
        # Handle calendar interactions - store in pending changes
        if calendar_result and calendar_result.get("eventDrop"):
            dropped_event = calendar_result["eventDrop"]
            event_id = int(dropped_event["event"]["id"])
            new_date = pd.Timestamp(dropped_event["event"]["start"])
            
            # Store in pending changes (not applied yet)
            st.session_state.pending_calendar_changes[event_id] = new_date
            st.rerun()
        
        # Show event details on click
        if calendar_result and calendar_result.get("eventClick"):
            clicked_event = calendar_result["eventClick"]["event"]
            event_id = int(clicked_event["id"])
            row = st.session_state.df.loc[event_id]
            
            st.info(f"""
            **WO:** {row['WO']}  
            **Customer:** {row['Customer Name']}  
            **Model:** {row['Model Description']}  
            **Status:** {row['Status']}  
            **Scheduled:** {row['Scheduled Date'].strftime('%Y-%m-%d') if pd.notna(row['Scheduled Date']) else 'N/A'}  
            **Price:** {row['Price']}
            """)
    
    with tab2:
        st.subheader("Order Book Table")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.multiselect(
                "Filter by Status",
                options=st.session_state.df['Status'].unique(),
                default=st.session_state.df['Status'].unique()
            )
        
        with col2:
            show_unscheduled = st.checkbox("Show Only Unscheduled", False)
        
        with col3:
            customer_search = st.text_input("Search Customer")
        
        # Apply filters
        filtered_df = st.session_state.df[st.session_state.df['Status'].isin(status_filter)].copy()
        
        if show_unscheduled:
            filtered_df = filtered_df[filtered_df['Scheduled Date'].isna()]
        
        if customer_search:
            filtered_df = filtered_df[filtered_df['Customer Name'].str.contains(customer_search, case=False, na=False)]
        
        # Display editable dataframe
        st.info("💡 Edit cells or add new rows, then click 'Update Schedule' to sync with calendar")
        
        edited_df = st.data_editor(
            filtered_df[['WO', 'Quote', 'PO Number', 'Status', 'Customer Name', 
                        'Model Description', 'Scheduled Date', 'Actual Delivery Date', 'Price', 'Type']],
            use_container_width=True,
            num_rows="dynamic",
            key="order_table_editor",
            column_config={
                "Scheduled Date": st.column_config.DateColumn("Scheduled Date", format="YYYY-MM-DD"),
                "Actual Delivery Date": st.column_config.DateColumn("Actual Delivery Date", format="YYYY-MM-DD"),
                "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=list(STATUS_COLORS.keys()),
                    required=True
                ),
                "Type": st.column_config.SelectboxColumn(
                    "Type",
                    options=['Job', 'Placeholder'],
                    required=True
                )
            }
        )
        
        st.markdown("---")
        
        # Update button for table
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("✅ Update Schedule", type="primary", key="update_table_btn"):
                # Check if there are actual changes
                has_changes = False
                
                # Handle new rows
                if len(edited_df) > len(filtered_df):
                    has_changes = True
                    # Get new rows
                    new_rows = edited_df.iloc[len(filtered_df):]
                    
                    for _, new_row in new_rows.iterrows():
                        # Create new row with all required columns
                        row_dict = {
                            'WO': new_row.get('WO', f'NEW-{len(st.session_state.df)+1}'),
                            'Quote': new_row.get('Quote', ''),
                            'PO Number': new_row.get('PO Number', ''),
                            'Status': new_row.get('Status', 'Scheduled'),
                            'Customer Name': new_row.get('Customer Name', ''),
                            'Model Description': new_row.get('Model Description', ''),
                            'Scheduled Date': pd.Timestamp(new_row['Scheduled Date']) if pd.notna(new_row.get('Scheduled Date')) else pd.NaT,
                            'Actual Delivery Date': pd.Timestamp(new_row['Actual Delivery Date']) if pd.notna(new_row.get('Actual Delivery Date')) else pd.NaT,
                            'Price': new_row.get('Price', ''),
                            'Type': new_row.get('Type', 'Job')
                        }
                        
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([row_dict])], ignore_index=True)
                
                # Handle edited rows
                for col in edited_df.columns:
                    if not edited_df[col].equals(filtered_df[col]):
                        has_changes = True
                        st.session_state.df.loc[filtered_df.index, col] = edited_df[col].values
                
                if has_changes:
                    # Reset index after changes
                    st.session_state.df = st.session_state.df.reset_index(drop=True)
                    
                    # Update colors based on new status
                    st.session_state.df = update_colors(st.session_state.df)
                    
                    # Force calendar refresh
                    st.session_state.force_calendar_refresh = True
                    
                    st.success("✅ Schedule updated! Switch to Calendar tab to see changes.")
                    st.rerun()
                else:
                    st.info("No changes detected")

else:
    # Welcome screen
    st.info("👈 Please upload your Order Book CSV file using the sidebar to get started")
    
    st.markdown("""
    ### Features:
    - 📅 **Interactive Calendar** - Drag and drop jobs to reschedule
    - 📊 **Order Book Table** - View and edit all orders in one place
    - 🔄 **Synchronized Updates** - Calendar and table stay in sync
    - ➕ **Add Entries** - Add new orders or placeholders from table
    - 💾 **Save Changes** - Export your updated schedule
    - 🔍 **Filter & Search** - Find orders quickly
    - 🎨 **Color Coding** - Visual status indicators
    
    ### How to Use:
    1. Upload your ORDER BOOK TRACKER.csv file
    2. Click "Load Data" to initialize the scheduler
    3. **Calendar View**: Drag jobs to new dates, then click "✅ Update Schedule"
    4. **Order Book Table**: Edit details or add new rows, then click "✅ Update Schedule"
    5. Both views are synchronized - changes in one update the other
    6. Add placeholders for tentative bookings via sidebar
    7. Save your changes when done
    """)
