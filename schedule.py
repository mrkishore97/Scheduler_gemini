import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_calendar import calendar
import json

# Page configuration with light theme
st.set_page_config(
    page_title="Production Scheduler", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Apply light theme styling with proper text colors
st.markdown("""
    <style>
    .main {
        background-color: #ffffff;
    }
    .stApp {
        background-color: #ffffff;
    }
    /* Fix text visibility */
    .stMarkdown, .stText, p, span, div {
        color: #1f1f1f !important;
    }
    /* Fix selectbox and dropdown colors */
    .stSelectbox label, .stMultiSelect label {
        color: #1f1f1f !important;
    }
    /* Fix metric labels and values */
    .stMetric label {
        color: #1f1f1f !important;
    }
    .stMetric .metric-value {
        color: #1f1f1f !important;
    }
    /* Fix input labels */
    .stTextInput label, .stDateInput label {
        color: #1f1f1f !important;
    }
    /* Fix tab text */
    .stTabs [data-baseweb="tab"] {
        color: #1f1f1f !important;
    }
    /* Fix info box text */
    .stAlert {
        color: #1f1f1f !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'df' not in st.session_state:
    st.session_state.df = None
if 'last_saved' not in st.session_state:
    st.session_state.last_saved = None
if 'pending_calendar_changes' not in st.session_state:
    st.session_state.pending_calendar_changes = []
if 'pending_table_changes' not in st.session_state:
    st.session_state.pending_table_changes = False

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

def df_to_calendar_events(df):
    """Convert dataframe to FullCalendar event format with detailed titles"""
    events = []
    
    for idx, row in df.iterrows():
        # Skip rows without scheduled dates
        if pd.isna(row.get('Scheduled Date')):
            continue
        
        # Create detailed event title with line breaks
        wo = str(row.get('WO', 'N/A'))
        customer = str(row.get('Customer Name', 'N/A'))
        model = str(row.get('Model Description', 'N/A'))
        
        # Truncate long descriptions for better display
        if len(model) > 40:
            model = model[:37] + "..."
        if len(customer) > 30:
            customer = customer[:27] + "..."
        
        title = f"{wo}\n{customer}\n{model}"
        
        # Create event object
        event = {
            'title': title,
            'start': row['Scheduled Date'].strftime('%Y-%m-%d'),
            'id': str(idx),  # Use index as unique ID
            'backgroundColor': row.get('Color', STATUS_COLORS['Scheduled']),
            'borderColor': row.get('Color', STATUS_COLORS['Scheduled']),
            'extendedProps': {
                'wo': wo,
                'customer': customer,
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

def generate_pdf_schedule(df, year, month):
    """Generate HTML for PDF printing of monthly schedule"""
    # Filter data for the selected month
    df_month = df[
        (df['Scheduled Date'].dt.year == year) & 
        (df['Scheduled Date'].dt.month == month) &
        (df['Scheduled Date'].notna())
    ].copy()
    
    # Sort by date
    df_month = df_month.sort_values('Scheduled Date')
    
    # Generate HTML
    month_name = datetime(year, month, 1).strftime('%B %Y')
    
    html = f"""
    <html>
    <head>
        <title>Production Schedule - {month_name}</title>
        <style>
            @media print {{
                body {{ margin: 0; }}
            }}
            body {{
                font-family: Arial, sans-serif;
                padding: 20px;
                background: white;
            }}
            h1 {{
                color: #333;
                text-align: center;
                border-bottom: 3px solid #007bff;
                padding-bottom: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th {{
                background-color: #007bff;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: bold;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }}
            tr:nth-child(even) {{
                background-color: #f8f9fa;
            }}
            tr:hover {{
                background-color: #e9ecef;
            }}
            .status-badge {{
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }}
            .completed {{ background-color: #28a745; color: white; }}
            .scheduled {{ background-color: #ffc107; color: black; }}
            .placeholder {{ background-color: #fd7e14; color: white; }}
            .footer {{
                margin-top: 30px;
                text-align: center;
                color: #666;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <h1>Production Schedule - {month_name}</h1>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>WO #</th>
                    <th>Customer</th>
                    <th>Model Description</th>
                    <th>Status</th>
                    <th>Price</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for _, row in df_month.iterrows():
        date_str = row['Scheduled Date'].strftime('%Y-%m-%d')
        status = row.get('Status', 'Scheduled')
        status_class = status.lower().replace(' ', '-')
        
        html += f"""
                <tr>
                    <td><strong>{date_str}</strong></td>
                    <td>{row.get('WO', 'N/A')}</td>
                    <td>{row.get('Customer Name', 'N/A')}</td>
                    <td>{row.get('Model Description', 'N/A')}</td>
                    <td><span class="status-badge {status_class}">{status}</span></td>
                    <td>{row.get('Price', 'N/A')}</td>
                </tr>
        """
    
    html += f"""
            </tbody>
        </table>
        <div class="footer">
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Total Jobs: {len(df_month)}</p>
        </div>
    </body>
    </html>
    """
    
    return html

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
            if st.session_state.df is not None:
                st.success(f"Loaded {len(st.session_state.df)} orders")
    
    st.markdown("---")
    
    # PDF Export functionality
    if st.session_state.df is not None:
        st.header("📄 Export to PDF")
        
        current_date = datetime.now()
        col1, col2 = st.columns(2)
        
        with col1:
            export_month = st.selectbox(
                "Month",
                range(1, 13),
                index=current_date.month - 1,
                format_func=lambda x: datetime(2000, x, 1).strftime('%B')
            )
        
        with col2:
            export_year = st.selectbox(
                "Year",
                range(current_date.year - 1, current_date.year + 3),
                index=1
            )
        
        if st.button("Generate PDF View", type="primary"):
            html_content = generate_pdf_schedule(st.session_state.df, export_year, export_month)
            st.download_button(
                label="📥 Download PDF (HTML)",
                data=html_content,
                file_name=f"schedule_{export_year}_{export_month:02d}.html",
                mime="text/html"
            )
            st.info("💡 Open the downloaded HTML file and use your browser's Print to PDF feature (Ctrl+P / Cmd+P)")
        
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
        
        # Calendar configuration with larger display
        calendar_options = {
            "editable": True,
            "selectable": True,
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay"
            },
            "initialView": "dayGridMonth",
            "height": 800,
            "eventDisplay": "block",
            "displayEventTime": False,
            "eventColor": "#007bff",
        }
        
        # Convert dataframe to events
        events = df_to_calendar_events(st.session_state.df)
        
        # Display calendar with enhanced styling
        calendar_result = calendar(
            events=events,
            options=calendar_options,
            custom_css="""
                .fc {
                    background-color: white;
                }
                .fc-event {
                    font-size: 11px;
                    cursor: move;
                    padding: 4px;
                    margin: 2px 0;
                    border-radius: 4px;
                    white-space: pre-line;
                    line-height: 1.3;
                    min-height: 60px;
                }
                .fc-daygrid-day {
                    background-color: #ffffff;
                }
                .fc-day-today {
                    background-color: #fff3cd !important;
                }
                .fc-daygrid-day-number {
                    color: #333;
                    font-weight: bold;
                    font-size: 14px;
                }
                .fc-col-header-cell {
                    background-color: #f8f9fa;
                    font-weight: bold;
                }
                .fc-scrollgrid {
                    border: 1px solid #dee2e6;
                }
            """
        )
        
        # Handle calendar interactions
        if calendar_result.get("eventDrop"):
            dropped_event = calendar_result["eventDrop"]
            event_id = int(dropped_event["event"]["id"])
            new_date = pd.Timestamp(dropped_event["event"]["start"])
            
            # Store pending change instead of immediate update
            change_info = {
                'event_id': event_id,
                'new_date': new_date,
                'wo': st.session_state.df.loc[event_id, 'WO']
            }
            
            # Check if this event already has a pending change and update it
            existing_change = next((i for i, c in enumerate(st.session_state.pending_calendar_changes) 
                                   if c['event_id'] == event_id), None)
            if existing_change is not None:
                st.session_state.pending_calendar_changes[existing_change] = change_info
            else:
                st.session_state.pending_calendar_changes.append(change_info)
            
            st.warning(f"📌 Pending: {st.session_state.df.loc[event_id, 'WO']} → {new_date.strftime('%Y-%m-%d')} (Click 'Update Schedule' to apply)")
        
        # Update Schedule button below calendar
        if st.session_state.pending_calendar_changes:
            st.markdown("### 📝 Pending Changes")
            for change in st.session_state.pending_calendar_changes:
                st.write(f"- **{change['wo']}** → {change['new_date'].strftime('%Y-%m-%d')}")
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("✅ Update Schedule", type="primary", key="update_calendar"):
                    # Apply all pending changes
                    for change in st.session_state.pending_calendar_changes:
                        st.session_state.df.loc[change['event_id'], 'Scheduled Date'] = change['new_date']
                    
                    st.success(f"✅ Updated {len(st.session_state.pending_calendar_changes)} job(s) successfully!")
                    st.session_state.pending_calendar_changes = []
                    st.rerun()
            with col2:
                if st.button("❌ Cancel Changes", key="cancel_calendar"):
                    st.session_state.pending_calendar_changes = []
                    st.rerun()
        
        # Show event details on click
        if calendar_result.get("eventClick"):
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
        filtered_df = st.session_state.df[st.session_state.df['Status'].isin(status_filter)]
        
        if show_unscheduled:
            filtered_df = filtered_df[filtered_df['Scheduled Date'].isna()]
        
        if customer_search:
            filtered_df = filtered_df[filtered_df['Customer Name'].str.contains(customer_search, case=False, na=False)]
        
        # Display editable dataframe
        st.info("💡 Click cells to edit or add new rows. Click 'Update Schedule' to apply changes!")
        
        edited_df = st.data_editor(
            filtered_df[['WO', 'Quote', 'PO Number', 'Status', 'Customer Name', 
                        'Model Description', 'Scheduled Date', 'Actual Delivery Date', 'Price']],
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Scheduled Date": st.column_config.DateColumn("Scheduled Date", format="YYYY-MM-DD"),
                "Actual Delivery Date": st.column_config.DateColumn("Actual Delivery Date", format="YYYY-MM-DD"),
                "Price": st.column_config.NumberColumn("Price", format="$%.2f")
            },
            key="order_book_editor"
        )
        
        # Check if there are changes
        changes_detected = not edited_df.equals(filtered_df[edited_df.columns])
        
        # Update Schedule button for table
        if changes_detected or st.session_state.pending_table_changes:
            st.markdown("---")
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("✅ Update Schedule", type="primary", key="update_table"):
                    # Update session state with edits
                    for col in edited_df.columns:
                        st.session_state.df.loc[filtered_df.index, col] = edited_df[col].values
                    
                    # Update color column based on status
                    if 'Status' in st.session_state.df.columns:
                        st.session_state.df['Color'] = st.session_state.df['Status'].map(STATUS_COLORS).fillna(STATUS_COLORS['Unscheduled'])
                    
                    st.session_state.pending_table_changes = False
                    st.success("✅ Schedule updated successfully!")
                    st.rerun()
            with col2:
                if st.button("❌ Cancel Changes", key="cancel_table"):
                    st.session_state.pending_table_changes = False
                    st.rerun()
        
        # Mark that there are pending changes
        if changes_detected:
            st.session_state.pending_table_changes = True

else:
    # Welcome screen
    st.info("👈 Please upload your Order Book CSV file using the sidebar to get started")
    
    st.markdown("""
    ### Features:
    - 📅 **Interactive Calendar** - Drag and drop jobs to reschedule
    - 📊 **Order Book Table** - View and edit all orders in one place
    - ➕ **Add Placeholders** - Reserve dates for tentative orders
    - 💾 **Save Changes** - Export your updated schedule
    - 📄 **PDF Export** - Print monthly schedules
    - 🔍 **Filter & Search** - Find orders quickly
    - 🎨 **Color Coding** - Visual status indicators
    
    ### How to Use:
    1. Upload your ORDER BOOK TRACKER.csv file
    2. Click "Load Data" to initialize the scheduler
    3. Use the Calendar tab to drag jobs to new dates
    4. Use the Order Book Table to edit details or view unscheduled items
    5. Add placeholders for tentative bookings
    6. Export monthly schedules to PDF for printing
    7. Save your changes when done
    """)
