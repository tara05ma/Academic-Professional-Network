import streamlit as st
import mysql.connector
import pandas as pd
import bcrypt
from contextlib import contextmanager

# -----------------------------------------------------------------
# DATABASE CONFIGURATION
# -----------------------------------------------------------------

# IMPORTANT: Replace with your own MySQL connection details
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "tara123"  # <-- CHANGE THIS
DB_NAME = "apn_db"

# Function to create a new database connection
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except mysql.connector.Error as e:
        st.error(f"Error connecting to MySQL: {e}")
        return None

# Use a context manager for safe database operations
@contextmanager
def db_cursor():
    conn = get_db_connection()
    if conn is None:
        yield None, None
        return
    
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor, conn
    finally:
        cursor.close()
        conn.close()

# -----------------------------------------------------------------
# PASSWORD HASHING
# -----------------------------------------------------------------

def hash_password(password):
    """Hashes a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed_password):
    """Checks if a password matches its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

# -----------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -----------------------------------------------------------------

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.page = 'login' # Controls navigation
    st.session_state.view_profile_id = None # Which user's profile to view

# -----------------------------------------------------------------
# HELPER FUNCTIONS (Database Queries)
# -----------------------------------------------------------------

def fetch_user_by_username(username):
    with db_cursor() as (cursor, conn):
        if cursor:
            cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
            return cursor.fetchone()
    return None

def fetch_user_by_id(user_id):
    with db_cursor() as (cursor, conn):
        if cursor:
            cursor.execute("SELECT * FROM Users WHERE user_id = %s", (user_id,))
            return cursor.fetchone()
    return None

def get_profile_details(user_id):
    """Fetches all profile components for a user."""
    details = {}
    with db_cursor() as (cursor, conn):
        if not cursor:
            return None
        
        # User info
        cursor.execute("SELECT user_id, full_name, email, role, graduation_year, bio FROM Users WHERE user_id = %s", (user_id,))
        details['user'] = cursor.fetchone()
        
        # Skills
        cursor.execute("SELECT skill_id, skill_name FROM Skills WHERE user_id = %s", (user_id,))
        details['skills'] = cursor.fetchall()
        
        # Projects
        cursor.execute("SELECT project_id, project_title, project_description, start_date, end_date FROM Projects WHERE user_id = %s", (user_id,))
        details['projects'] = cursor.fetchall()
        
        # Experience
        cursor.execute("SELECT experience_id, company_name, role_title, description, start_date, end_date FROM Experience WHERE user_id = %s", (user_id,))
        details['experience'] = cursor.fetchall()
        
    return details

def get_connection_status(user_id_1, user_id_2):
    """Calls the fn_GetConnectionStatus function."""
    with db_cursor() as (cursor, conn):
        if cursor:
            cursor.execute("SELECT fn_GetConnectionStatus(%s, %s) AS status", (user_id_1, user_id_2))
            result = cursor.fetchone()
            return result['status'] if result else 'none'
    return 'none'

# -----------------------------------------------------------------
# UI: LOGIN PAGE
# -----------------------------------------------------------------

def show_login_page():
    st.title("Welcome to the Academic & Professional Network (APN)")
    st.subheader("Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = fetch_user_by_username(username)
            if user and check_password(password, user['password_hash']):
                st.session_state.logged_in = True
                st.session_state.user_id = user['user_id']
                st.session_state.username = user['username']
                st.session_state.role = user['role']
                st.session_state.page = 'dashboard'
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    if st.button("Don't have an account? Sign Up"):
        st.session_state.page = 'signup'
        st.rerun()

# -----------------------------------------------------------------
# UI: SIGNUP PAGE
# -----------------------------------------------------------------

def show_signup_page():
    st.title("Create Your APN Account")

    with st.form("signup_form"):
        full_name = st.text_input("Full Name")
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        role = st.selectbox("I am a:", ('student', 'faculty', 'alumni'))
        
        grad_year = None
        if role in ('student', 'alumni'):
            grad_year = st.number_input("Graduation Year", min_value=1950, max_value=2050, value=2025, step=1)
        
        submitted = st.form_submit_button("Sign Up")

        if submitted:
            if not all([full_name, username, email, password, role]):
                st.error("Please fill out all fields.")
            else:
                # Check if user already exists
                if fetch_user_by_username(username):
                    st.error("Username already taken.")
                else:
                    try:
                        hashed_pass = hash_password(password)
                        with db_cursor() as (cursor, conn):
                            if cursor:
                                cursor.callproc('sp_CreateUser', (username, hashed_pass.decode('utf-8'), full_name, email, role, grad_year))
                                conn.commit()
                                st.success("Account created successfully! Please login.")
                                st.session_state.page = 'login'
                                st.rerun()
                    except mysql.connector.Error as e:
                        st.error(f"Error creating account: {e}")

    if st.button("Already have an account? Login"):
        st.session_state.page = 'login'
        st.rerun()

# -----------------------------------------------------------------
# UI: MAIN APPLICATION (Sidebar & Page Routing)
# -----------------------------------------------------------------

def show_main_app():
    
    # --- Sidebar Navigation ---
    with st.sidebar:
        st.title(f"APN Menu")
        st.write(f"Welcome, {st.session_state.username}!")
        st.write(f"Role: {st.session_state.role.capitalize()}")
        st.divider()

        if st.button("Dashboard", use_container_width=True):
            st.session_state.page = 'dashboard'
            st.session_state.view_profile_id = None
            st.rerun()
        
        if st.button("My Profile", use_container_width=True):
            st.session_state.page = 'profile'
            st.session_state.view_profile_id = st.session_state.user_id # View self
            st.rerun()
            
        if st.button("Find Users", use_container_width=True):
            st.session_state.page = 'find_users'
            st.session_state.view_profile_id = None
            st.rerun()
            
        if st.button("Opportunities", use_container_width=True):
            st.session_state.page = 'opportunities'
            st.session_state.view_profile_id = None
            st.rerun()
            
        if st.button("My Connections", use_container_width=True):
            st.session_state.page = 'connections'
            st.session_state.view_profile_id = None
            st.rerun()

        if st.session_state.role == 'admin':
            if st.button("Admin: Run Rubric Queries", use_container_width=True):
                st.session_state.page = 'rubric_queries'
                st.session_state.view_profile_id = None
                st.rerun()
        
        st.divider()
        if st.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key] # Clear session
            st.rerun()

    # --- Page Content Routing ---
    if st.session_state.page == 'dashboard':
        show_dashboard()
    elif st.session_state.page == 'profile':
        show_profile(st.session_state.view_profile_id)
    elif st.session_state.page == 'find_users':
        show_find_users()
    elif st.session_state.page == 'opportunities':
        show_opportunities()
    elif st.session_state.page == 'connections':
        show_connections()
    elif st.session_state.page == 'rubric_queries':
        show_rubric_queries()

# -----------------------------------------------------------------
# UI: DASHBOARD PAGE
# -----------------------------------------------------------------

def show_dashboard():
    st.title("Dashboard")
    role = st.session_state.role
    user_id = st.session_state.user_id

    with db_cursor() as (cursor, conn):
        if not cursor:
            return

        if role == 'student':
            st.subheader("My Ongoing Projects")
            # Query for projects where this student was approved
            query = """
                SELECT p.ongoing_project_id, o.title, u.full_name AS faculty_name
                FROM OngoingProjects p
                JOIN Opportunities o ON p.opportunity_id = o.opportunity_id
                JOIN Users u ON p.faculty_user_id = u.user_id
                WHERE p.student_user_id = %s
            """
            cursor.execute(query, (user_id,))
            projects = cursor.fetchall()
            if projects:
                for proj in projects:
                    st.info(f"**{proj['title']}** (with {proj['faculty_name']})")
            else:
                st.write("You have no ongoing projects yet. Apply for an opportunity!")
        
        elif role in ('faculty', 'alumni'):
            st.subheader("My Ongoing Projects (as Mentor)")
            # Query for projects this faculty/alumni created and are ongoing
            query = """
                SELECT p.ongoing_project_id, o.title, u.full_name AS student_name
                FROM OngoingProjects p
                JOIN Opportunities o ON p.opportunity_id = o.opportunity_id
                JOIN Users u ON p.student_user_id = u.user_id
                WHERE p.faculty_user_id = %s
            """
            cursor.execute(query, (user_id,))
            projects = cursor.fetchall()
            if projects:
                for proj in projects:
                    st.info(f"**{proj['title']}** (with {proj['student_name']})")
            else:
                st.write("You have no ongoing projects with students.")
                
            st.subheader("My Posted Opportunities")
            # Aggregate query: Count applicants for each opportunity
            query = """
                SELECT o.title, o.status, COUNT(a.application_id) AS applicant_count
                FROM Opportunities o
                LEFT JOIN Applications a ON o.opportunity_id = a.opportunity_id
                WHERE o.created_by_user_id = %s
                GROUP BY o.opportunity_id, o.title, o.status
            """
            cursor.execute(query, (user_id,))
            opportunities = cursor.fetchall()
            if opportunities:
                df = pd.DataFrame(opportunities)
                st.dataframe(df)
            else:
                st.write("You have not posted any opportunities.")


# -----------------------------------------------------------------
# UI: PROFILE PAGE (View & Edit)
# -----------------------------------------------------------------

def show_profile(profile_user_id):
    details = get_profile_details(profile_user_id)
    if not details:
        st.error("Could not load profile.")
        return

    user_info = details['user']
    is_own_profile = (profile_user_id == st.session_state.user_id)

    st.title(f"{user_info['full_name']}'s Profile")
    st.caption(f"Role: {user_info['role'].capitalize()} | {user_info['email']}")
    
    # --- Connection Button (if viewing others) ---
    if not is_own_profile:
        status = get_connection_status(st.session_state.user_id, profile_user_id)
        if status == 'none':
            if st.button("Send Connection Request"):
                try:
                    with db_cursor() as (cursor, conn):
                        if cursor:
                            # --- FIX IS HERE: No sorting, direct assignment ---
                            req_id = st.session_state.user_id
                            rec_id = profile_user_id

                            cursor.execute(
                                "INSERT INTO Connections (requester_id, receiver_id, status) VALUES (%s, %s, 'pending')",
                                (req_id, rec_id)
                            )
                            conn.commit()
                            st.success("Connection request sent!")
                            st.rerun()
                except mysql.connector.Error as e:
                    st.error(f"Error: {e}")
        elif status == 'pending':
            st.info("Connection request pending.")
        elif status == 'accepted':
            st.success("You are connected.")
        elif status == 'rejected':
            st.warning("Connection request was rejected.")

    st.divider()

    # --- Bio Section (Editable if own profile) ---
    st.subheader("Bio")
    if is_own_profile:
        current_bio = user_info['bio'] if user_info['bio'] else ""
        new_bio = st.text_area("Edit your bio:", value=current_bio, height=150)
        if st.button("Save Bio"):
            with db_cursor() as (cursor, conn):
                if cursor:
                    cursor.execute("UPDATE Users SET bio = %s WHERE user_id = %s", (new_bio, st.session_state.user_id))
                    conn.commit()
                    st.success("Bio updated!")
                    st.rerun()
    else:
        st.write(user_info['bio'] if user_info['bio'] else "*No bio provided.*")

    # --- CRUD Sections (Skills, Projects, Experience) ---
    profile_sections = {
        'Skills': {'table': 'Skills', 'col': 'skill_name', 'data': details['skills']},
        'Projects': {'table': 'Projects', 'col': 'project_title', 'data': details['projects']},
        'Experience': {'table': 'Experience', 'col': 'company_name', 'data': details['experience']}
    }

    for section_name, info in profile_sections.items():
        st.divider()
        st.subheader(section_name)
        
        # Read/Delete
        if info['data']:
            for item in info['data']:
                item_id = item[f"{info['table'].lower()[:-1]}_id"]
                item_name = item[info['col']]
                
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{item_name}**")
                    if section_name == 'Projects':
                        st.caption(item.get('project_description', ''))
                    if section_name == 'Experience':
                        st.caption(f"{item.get('role_title', '')} | {item.get('description', '')}")
                
                if is_own_profile:
                    with col2:
                        if st.button(f"Delete", key=f"del_{info['table']}_{item_id}"):
                            with db_cursor() as (cursor, conn):
                                if cursor:
                                    query = f"DELETE FROM {info['table']} WHERE {info['table'].lower()[:-1]}_id = %s AND user_id = %s"
                                    cursor.execute(query, (item_id, st.session_state.user_id))
                                    conn.commit()
                                    st.success(f"{section_name} item deleted.")
                                    st.rerun()
        else:
            st.write(f"*No {section_name.lower()} added yet.*")

        # Create
        if is_own_profile:
            with st.expander(f"Add New {section_name[:-1]}"):
                with st.form(f"add_{info['table']}_form"):
                    if section_name == 'Skills':
                        val1 = st.text_input("Skill Name")
                        submitted = st.form_submit_button("Add Skill")
                        if submitted and val1:
                            with db_cursor() as (cursor, conn):
                                cursor.execute("INSERT INTO Skills (user_id, skill_name) VALUES (%s, %s)", (st.session_state.user_id, val1))
                                conn.commit()
                                st.success("Skill added!")
                                st.rerun()
                    
                    elif section_name == 'Projects':
                        val1 = st.text_input("Project Title")
                        val2 = st.text_area("Project Description")
                        submitted = st.form_submit_button("Add Project")
                        if submitted and val1:
                            with db_cursor() as (cursor, conn):
                                cursor.execute("INSERT INTO Projects (user_id, project_title, project_description) VALUES (%s, %s, %s)", (st.session_state.user_id, val1, val2))
                                conn.commit()
                                st.success("Project added!")
                                st.rerun()

                    elif section_name == 'Experience':
                        val1 = st.text_input("Company Name")
                        val2 = st.text_input("Role / Title")
                        val3 = st.text_area("Description")
                        submitted = st.form_submit_button("Add Experience")
                        if submitted and val1 and val2:
                            with db_cursor() as (cursor, conn):
                                cursor.execute("INSERT INTO Experience (user_id, company_name, role_title, description) VALUES (%s, %s, %s, %s)", (st.session_state.user_id, val1, val2, val3))
                                conn.commit()
                                st.success("Experience added!")
                                st.rerun()

# -----------------------------------------------------------------
# UI: FIND USERS PAGE
# -----------------------------------------------------------------

def show_find_users():
    st.title("Find Users")
    search_term = st.text_input("Search by name:")

    if search_term:
        with db_cursor() as (cursor, conn):
            if cursor:
                query = "SELECT user_id, full_name, role, email FROM Users WHERE full_name LIKE %s AND user_id != %s"
                cursor.execute(query, (f"%{search_term}%", st.session_state.user_id))
                results = cursor.fetchall()
                
                if results:
                    for user in results:
                        st.subheader(user['full_name'])
                        st.caption(f"{user['role'].capitalize()} | {user['email']}")
                        if st.button("View Profile", key=f"view_user_{user['user_id']}"):
                            st.session_state.page = 'profile'
                            st.session_state.view_profile_id = user['user_id']
                            st.rerun()
                        st.divider()
                else:
                    st.write("No users found.")

# -----------------------------------------------------------------
# UI: OPPORTUNITIES PAGE
# -----------------------------------------------------------------

def show_opportunities():
    st.title("Opportunities")
    role = st.session_state.role
    user_id = st.session_state.user_id

    if role == 'student':
        st.subheader("Available Opportunities")
        
        # --- RUBRIC: JOIN QUERY ---
        # This query joins Opportunities and Users to show who posted it.
        query = """
            SELECT o.opportunity_id, o.title, o.description, u.full_name AS posted_by
            FROM Opportunities o
            JOIN Users u ON o.created_by_user_id = u.user_id
            WHERE o.status = 'open'
        """
        
        with db_cursor() as (cursor, conn):
            if not cursor:
                return
            cursor.execute(query)
            opportunities = cursor.fetchall()
            
            if not opportunities:
                st.write("No open opportunities at this time.")
                return

            for op in opportunities:
                with st.container(border=True):
                    st.subheader(op['title'])
                    st.caption(f"Posted by: {op['posted_by']}")
                    st.write(op['description'])
                    
                    # Check if already applied
                    cursor.execute(
                        "SELECT * FROM Applications WHERE opportunity_id = %s AND student_user_id = %s",
                        (op['opportunity_id'], user_id)
                    )
                    application = cursor.fetchone()
                    
                    if application:
                        st.info(f"You applied for this. Status: {application['status']}")
                    else:
                        if st.button("Apply Now", key=f"apply_{op['opportunity_id']}"):
                            try:
                                cursor.execute(
                                    "INSERT INTO Applications (opportunity_id, student_user_id, status) VALUES (%s, %s, 'pending')",
                                    (op['opportunity_id'], user_id)
                                )
                                conn.commit()
                                st.success("Application submitted!")
                                st.rerun()
                            except mysql.connector.Error as e:
                                st.error(f"Error applying: {e}")
    
    elif role in ('faculty', 'alumni'):
        with st.expander("Post a New Opportunity"):
            with st.form("new_opportunity_form"):
                title = st.text_input("Opportunity Title")
                description = st.text_area("Description")
                submitted = st.form_submit_button("Post Opportunity")
                
                if submitted and title and description:
                    with db_cursor() as (cursor, conn):
                        if cursor:
                            cursor.execute(
                                "INSERT INTO Opportunities (created_by_user_id, title, description, status) VALUES (%s, %s, %s, 'open')",
                                (user_id, title, description)
                            )
                            conn.commit()
                            st.success("Opportunity posted!")
                            st.rerun()
                            
        st.divider()
        st.subheader("Manage My Posted Opportunities")
        with db_cursor() as (cursor, conn):
            if not cursor:
                return
            # Get opportunities posted by this user
            cursor.execute("SELECT * FROM Opportunities WHERE created_by_user_id = %s", (user_id,))
            my_ops = cursor.fetchall()
            
            if not my_ops:
                st.write("You haven't posted any opportunities.")
                return
                
            for op in my_ops:
                # --- NEW CODE BLOCK: Close, Re-open, and Delete ---
                # --- This block is now correctly indented ---
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.subheader(f"{op['title']} ({op['status']})")

                with col2:
                    if op['status'] == 'open':
                        if st.button("Close", key=f"close_{op['opportunity_id']}", use_container_width=True):
                            with db_cursor() as (cursor, conn):
                                if cursor:
                                    cursor.execute("UPDATE Opportunities SET status = 'closed' WHERE opportunity_id = %s", (op['opportunity_id'],))
                                    conn.commit()
                            st.success("Opportunity closed.")
                            st.rerun()
                    else:
                        if st.button("Re-open", key=f"reopen_{op['opportunity_id']}", use_container_width=True):
                            with db_cursor() as (cursor, conn):
                                if cursor:
                                    cursor.execute("UPDATE Opportunities SET status = 'open' WHERE opportunity_id = %s", (op['opportunity_id'],))
                                    conn.commit()
                            st.success("Opportunity re-opened.")
                            st.rerun()

                with col3:
                    if st.button("Delete", key=f"delete_{op['opportunity_id']}", use_container_width=True):
                        with db_cursor() as (cursor, conn):
                            if cursor:
                                # The 'ON DELETE CASCADE' in your SQL file will
                                # automatically delete all associated applications.
                                cursor.execute("DELETE FROM Opportunities WHERE opportunity_id = %s", (op['opportunity_id'],))
                                conn.commit()
                        st.warning("Opportunity deleted.")
                        st.rerun()
                
                # Get applicants for this opportunity
                cursor.execute(
                    """
                    SELECT a.application_id, a.status, u.full_name, u.user_id AS student_user_id
                    FROM Applications a
                    JOIN Users u ON a.student_user_id = u.user_id
                    WHERE a.opportunity_id = %s
                    """,
                    (op['opportunity_id'],)
                )
                applicants = cursor.fetchall()
                
                if not applicants:
                    st.write("No applicants yet.")
                    st.divider() # Add divider even if no applicants
                    continue

                for app in applicants:
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    col1.write(f"Applicant: **{app['full_name']}**")
                    col2.write(f"Status: *{app['status']}*")
                    
                    with col3:
                        if st.button("View Profile", key=f"view_app_{app['student_user_id']}_{op['opportunity_id']}"):
                            st.session_state.page = 'profile'
                            st.session_state.view_profile_id = app['student_user_id']
                            st.rerun()

                    if app['status'] == 'pending':
                        with col4:
                            col4a, col4b = st.columns(2)
                            with col4a:
                                if st.button("✅", key=f"approve_{app['application_id']}", help="Approve"):
                                    # Call procedure to approve
                                    cursor.callproc('sp_ApproveApplication', (app['application_id'],))
                                    conn.commit()
                                    st.success(f"Approved {app['full_name']}! Project created.")
                                    st.rerun()
                            with col4b:
                                if st.button("❌", key=f"reject_{app['application_id']}", help="Reject"):
                                    cursor.execute("UPDATE Applications SET status = 'rejected' WHERE application_id = %s", (app['application_id'],))
                                    conn.commit()
                                    st.warning(f"Rejected {app['full_name']}.")
                                    st.rerun()
                st.divider()

# -----------------------------------------------------------------
# UI: CONNECTIONS PAGE
# -----------------------------------------------------------------

def show_connections():
    st.title("My Connections")
    user_id = st.session_state.user_id

    with db_cursor() as (cursor, conn):
        if not cursor:
            return

        # --- Pending Requests Received ---
        st.subheader("Pending Requests")
        query = """
            SELECT u.user_id, u.full_name
            FROM Connections c
            JOIN Users u ON c.requester_id = u.user_id
            WHERE c.receiver_id = %s AND c.status = 'pending'
        """
        cursor.execute(query, (user_id,))
        requests = cursor.fetchall()
        
        if not requests:
            st.write("No pending requests.")
        else:
            for req in requests:
                col1, col2, col3 = st.columns(3)
                col1.write(req['full_name'])
                if col2.button("Accept", key=f"accept_{req['user_id']}"):
                    cursor.execute(
                        "UPDATE Connections SET status = 'accepted' WHERE requester_id = %s AND receiver_id = %s",
                        (req['user_id'], user_id)
                    )
                    conn.commit()
                    st.success("Connection accepted!")
                    st.rerun()
                if col3.button("Reject", key=f"reject_conn_{req['user_id']}"):
                    cursor.execute(
                        "UPDATE Connections SET status = 'rejected' WHERE requester_id = %s AND receiver_id = %s",
                        (req['user_id'], user_id)
                    )
                    conn.commit()
                    st.warning("Connection rejected.")
                    st.rerun()
        
        st.divider()
        
        # --- Accepted Connections ---
        st.subheader("My Connections")
        query = """
            SELECT u.user_id, u.full_name, u.role
            FROM Users u
            WHERE u.user_id IN (
                -- Users who sent me a request that I accepted
                SELECT requester_id FROM Connections WHERE receiver_id = %s AND status = 'accepted'
                UNION
                -- Users I sent a request to that they accepted
                SELECT receiver_id FROM Connections WHERE requester_id = %s AND status = 'accepted'
            )
        """
        cursor.execute(query, (user_id, user_id))
        connections = cursor.fetchall()
        
        if not connections:
            st.write("You have no connections yet.")
        else:
            for conn_user in connections:
                st.write(f"**{conn_user['full_name']}** ({conn_user['role'].capitalize()})")
                if st.button("View Profile", key=f"view_conn_{conn_user['user_id']}"):
                    st.session_state.page = 'profile'
                    st.session_state.view_profile_id = conn_user['user_id']
                    st.rerun()
                st.markdown("---")


# -----------------------------------------------------------------
# UI: ADMIN RUBRIC QUERIES PAGE
# -----------------------------------------------------------------

def show_rubric_queries():
    st.title("Admin: Run Rubric Queries")
    if st.session_state.role != 'admin':
        st.error("You do not have permission to view this page.")
        return

    st.subheader("1. Nested Query (with GUI)")
    st.write("Find students who applied for opportunities by a specific faculty member.")
    
    with db_cursor() as (cursor, conn):
        if not cursor:
            return
            
        # Get list of faculty/alumni to choose from
        cursor.execute("SELECT user_id, full_name FROM Users WHERE role IN ('faculty', 'alumni')")
        faculty_list = cursor.fetchall()
        faculty_names = {f['full_name']: f['user_id'] for f in faculty_list}
        
        selected_name = st.selectbox("Select Faculty/Alumni:", faculty_names.keys())
        
        if selected_name:
            faculty_id = faculty_names[selected_name]
            query = """
                SELECT u.full_name, u.email
                FROM Users u
                WHERE u.user_id IN (
                    SELECT a.student_user_id
                    FROM Applications a
                    WHERE a.opportunity_id IN (
                        SELECT o.opportunity_id
                        FROM Opportunities o
                        WHERE o.created_by_user_id = %s
                    )
                )
            """
            cursor.execute(query, (faculty_id,))
            results = cursor.fetchall()
            st.write(f"Students who applied to {selected_name}'s opportunities:")
            st.dataframe(results)
            
    st.divider()
    
    st.subheader("2. Aggregate Query (with GUI)")
    st.write("Count the number of applications each student has submitted.")
    
    # --- RUBRIC: AGGREGATE QUERY ---
    query = """
        SELECT u.full_name, COUNT(a.application_id) AS application_count
        FROM Users u
        JOIN Applications a ON u.user_id = a.student_user_id
        GROUP BY u.user_id, u.full_name
        ORDER BY application_count DESC
    """
    with db_cursor() as (cursor, conn):
        if cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            st.write("Application count per student:")
            st.dataframe(results)

    st.divider()
    
    st.subheader("3. Join Query (with GUI)")
    st.write("This query is already used on the 'Opportunities' page for students. It joins Opportunities with Users to show who posted the opportunity.")
    st.code("""
        SELECT o.opportunity_id, o.title, o.description, u.full_name AS posted_by
        FROM Opportunities o
        JOIN Users u ON o.created_by_user_id = u.user_id
        WHERE o.status = 'open'
    """, language='sql')


# -----------------------------------------------------------------
# MAIN ROUTER
# -----------------------------------------------------------------

if not st.session_state.logged_in:
    if st.session_state.page == 'signup':
        show_signup_page()
    else:
        show_login_page()
else:
    show_main_app()