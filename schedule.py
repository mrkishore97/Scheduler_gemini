import streamlit as st
from streamlit_calendar import calendar
import pandas as pd
import datetime
import os

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(layout="wide", page_title="Production Scheduler")

FILE_PATH = "ORDER BOOK TRACKER.csv"

# --- 2. HELPER FUNCTIONS ---

@st.cache_data(ttl=60)
def load_data_from_csv():
    """Loads and cleans the initial data from CSV."""
    if os.path.exists(FILE_PATH):
        df = pd.read_csv(FILE_PATH)
        # Clean column names (remove leading/trailing spaces)
        df.columns = df.columns.str.strip()
        
        # Ensure 'Scheduled Date' is strictly datetime (NaT for errors/empty)
        df['Scheduled Date'] = pd.to_datetime(df['Scheduled Date'], errors='coerce')
        
        # Ensure 'WO' is string to avoid ID conflicts
        df['WO'] = df['WO'].astype(str)
        return df
    else:
        st.error(f"File {FILE_PATH} not found. Please ensure it is in the app directory.")
        return pd.DataFrame(columns=['WO', 'Customer Name', 'Scheduled Date', 'Status', 'Model Description'])

def save_data_to_csv(df):
    """Saves the current session state dataframe back to CSV."""
    df_to_save = df.copy()
    # Format dates as YYYY-MM-DD for the CSV file
    df_to_save['Scheduled Date'] = df_to_save['Scheduled Date'].dt.strftime('%Y-%m-%d')
    try:
        df_to_save.to_csv(FILE_PATH, index=False)
        st.toast("✅ Schedule saved to ORDER BOOK TRACKER.csv", icon="💾")
    except Exception as e:
        st.error(f"Error saving file: {e}")

def get_event_color(status):
    """Returns color code based on Status."""
    status = str(status).lower()
    if 'placeholder' in status:
        return 'orange'
    elif status == 'completed':
        return 'green'
    elif status == 'in progress':
        return '#FFC107' # Amber/Yellow
    elif status == 'open':
        return '#3788d8' # Standard Blue
    elif status == 'flag':
        return 'red'
    return 'gray' # Default for others

# --- 3. SESSION STATE INITIALIZATION ---
# We load data into session_state so we can manipulate it in memory before saving.
if 'df' not in st.session_state:
    st.session_state.df = load_data_from_csv()

# --- 4. SIDEBAR ACTIONS ---
with st.sidebar:
    st.header("🏭 Scheduler Controls")
    
    # Action 2: Add Placeholder
    with st.expander("Add Placeholder", expanded=True):
        ph_title = st.text_input("Customer/Title", placeholder="e.g. Tentative - Mond")
        ph_date = st.date_input("Target Date", value=datetime.date.today())
        
        if st.button("Add Slot"):
            if ph_title:
                new_wo_id = f"PH-{len(st.session_state.df) + 100}" # Generate Temp ID
                new_row = {
                    'WO': new_wo_id,
                    'Customer Name': ph_title,
                    'Scheduled Date': pd.to_datetime(ph_date),
                    'Status': 'Placeholder',
                    'Model Description': 'Manual Placeholder Entry'
                }
                # Add to session state
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                st.success(f"Added {ph_title} on {ph_date}")
                st.rerun()

    st.markdown("---")
    
    # Action C: Save & Close
    st.write("### Data Persistence")
    if st.button("💾 Save Changes to CSV", type="primary"):
        save_data_to_csv(st.session_state.df)

# --- 5. MAIN LAYOUT ---
col_calendar, col_list = st.columns([0.65, 0.35], gap="large")

# --- CALENDAR COMPONENT ---
with col_calendar:
    st.subheader("📅 Master Calendar")
    
    # Transform Dataframe to Calendar Events JSON
    events = []
    for idx, row in st.session_state.df.iterrows():
        if pd.notna(row['Scheduled Date']):
            events.append({
                "id": row['WO'],
                "title": f"{row['Customer Name']} ({row['WO']})",
                "start": row['Scheduled Date'].strftime('%Y-%m-%d'),
                "backgroundColor": get_event_color(row.get('Status', '')),
                "borderColor": get_event_color(row.get('Status', '')),
                # Extended props for tooltip or future use
                "extendedProps": {
                    "description": str(row.get('Model Description', '')),
                    "status": str(row.get('Status', ''))
                }
            })

    calendar_options = {
        "editable": True, # Enables Drag & Drop
        "navLinks": True,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek"
        },
        "initialView": "dayGridMonth",
    }
    
    # Render Calendar
    calendar_state = calendar(events=events, options=calendar_options, key="scheduler_cal")
    
    # Logic: Listen for Drag & Drop (eventChange)
    if calendar_state.get("eventChange"):
        change_info = calendar_state["eventChange"]
        event_data = change_info["event"]
        wo_id = event_data["id"]
        new_start = event_data["start"] # format usually YYYY-MM-DD for dayGrid
        
        # Update Session State
        try:
            # Locate row by WO
            mask = st.session_state.df['WO'] == wo_id
            if mask.any():
                new_date_obj = pd.to_datetime(new_start)
                st.session_state.df.loc[mask, 'Scheduled Date'] = new_date_obj
                st.toast(f"Moved WO #{wo_id} to {new_start}")
                # We need to rerun to refresh the Table view immediately
                st.rerun()
        except Exception as e:
            st.error(f"Failed to update date: {e}")

# --- ORDER BOOK TABLE ---
with col_list:
    st.subheader("📋 Order Book")
    
    # Action 3: Handling Unscheduled Jobs
    filter_mode = st.radio("Show:", ["All Jobs", "Scheduled", "Unscheduled"], horizontal=True)
    
    # Filter Data for View
    df_view = st.session_state.df.copy()
    if filter_mode == "Scheduled":
        df_view = df_view[df_view['Scheduled Date'].notna()]
    elif filter_mode == "Unscheduled":
        df_view = df_view[df_view['Scheduled Date'].isna()]
    
    # We display a subset of columns for clarity
    cols_to_show = ['WO', 'Customer Name', 'Scheduled Date', 'Status']
    
    # Use Data Editor to allow manual changes in the list
    edited_df = st.data_editor(
        df_view[cols_to_show],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Scheduled Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "WO": st.column_config.TextColumn("WO", disabled=True) # Lock IDs
        },
        key="data_editor"
    )
    
    # Two-Way Sync Logic: Table -> Session State
    # If the user edits the table, we must update the main dataframe
    # We check if 'edited_df' differs from the current view in session state
    # (Simplified check: we iterate and update based on WO key)
    
    if st.session_state.get("data_editor"):
        # This block triggers if edits were made
        # We assume WO is unique. We update the main df based on the edits.
        # Iterate through edited rows (Streamlit returns the full edited dataframe)
        for index, row in edited_df.iterrows():
            wo_key = row['WO']
            new_date = row['Scheduled Date']
            
            # Find in master DF
            master_idx = st.session_state.df[st.session_state.df['WO'] == wo_key].index
            if not master_idx.empty:
                current_val = st.session_state.df.at[master_idx[0], 'Scheduled Date']
                
                # Check if date changed (handle NaT/None comparison)
                val_changed = False
                if pd.isna(current_val) and pd.notna(new_date):
                    val_changed = True
                elif pd.notna(current_val) and pd.isna(new_date):
                    val_changed = True
                elif pd.notna(current_val) and pd.notna(new_date):
                     # Convert both to timestamps for comparison if needed, or compare logic
                     if pd.to_datetime(current_val).date() != pd.to_datetime(new_date):
                         val_changed = True

                if val_changed:
                    st.session_state.df.at[master_idx[0], 'Scheduled Date'] = pd.to_datetime(new_date)
                    st.toast(f"Updated {wo_key} from Table")
                    # Force rerun to sync Calendar
                    st.rerun()
