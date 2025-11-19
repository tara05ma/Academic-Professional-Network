-- Create the database
drop database apn_db;

CREATE DATABASE IF NOT EXISTS apn_db;
USE apn_db;

-- Table: Users
-- Stores core user information and their role
CREATE TABLE IF NOT EXISTS Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    role ENUM('student', 'faculty', 'alumni', 'admin') NOT NULL,
    graduation_year INT, -- NULLable, mainly for students/alumni
    bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Skills
-- Stores individual skills linked to a user
CREATE TABLE IF NOT EXISTS Skills (
    skill_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- Table: Projects
-- Stores past projects for a user's profile
CREATE TABLE IF NOT EXISTS Projects (
    project_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    project_title VARCHAR(255) NOT NULL,
    project_description TEXT,
    start_date DATE,
    end_date DATE,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- Table: Experience
-- Stores work/internship experience for a user's profile
CREATE TABLE IF NOT EXISTS Experience (
    experience_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    role_title VARCHAR(100) NOT NULL,
    description TEXT,
    start_date DATE,
    end_date DATE,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- Table: Connections
-- Stores the relationship between two users
CREATE TABLE IF NOT EXISTS Connections (
    requester_id INT NOT NULL,
    receiver_id INT NOT NULL,
    status ENUM('pending', 'accepted', 'rejected') NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (requester_id, receiver_id),
    FOREIGN KEY (requester_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    CHECK (requester_id <> receiver_id) -- Ensures user can't connect with themselves
);

-- Table: Opportunities
-- Stores project/research opportunities posted by faculty/alumni
CREATE TABLE IF NOT EXISTS Opportunities (
    opportunity_id INT AUTO_INCREMENT PRIMARY KEY,
    created_by_user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status ENUM('open', 'closed') NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by_user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- Table: Applications
-- Tracks student applications for opportunities
CREATE TABLE IF NOT EXISTS Applications (
    application_id INT AUTO_INCREMENT PRIMARY KEY,
    opportunity_id INT NOT NULL,
    student_user_id INT NOT NULL,
    status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES Opportunities(opportunity_id) ON DELETE CASCADE,
    FOREIGN KEY (student_user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- Table: OngoingProjects
-- Tracks projects that are formed after an application is approved
CREATE TABLE IF NOT EXISTS OngoingProjects (
    ongoing_project_id INT AUTO_INCREMENT PRIMARY KEY,
    opportunity_id INT NOT NULL,
    student_user_id INT NOT NULL,
    faculty_user_id INT NOT NULL,
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opportunity_id) REFERENCES Opportunities(opportunity_id) ON DELETE CASCADE,
    FOREIGN KEY (student_user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (faculty_user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- Table: UserAuditLog
-- For Trigger 2: Logs new user registrations
CREATE TABLE IF NOT EXISTS UserAuditLog (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action_performed VARCHAR(100),
    log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- -----------------------------------------------------------------
-- PROCEDURES
-- -----------------------------------------------------------------

-- Procedure 1: sp_CreateUser
-- Securely creates a new user (password hash is passed from Python)
DELIMITER $$
CREATE PROCEDURE sp_CreateUser(
    IN p_username VARCHAR(50),
    IN p_password_hash VARCHAR(255),
    IN p_full_name VARCHAR(100),
    IN p_email VARCHAR(100),
    IN p_role ENUM('student', 'faculty', 'alumni', 'admin'),
    IN p_graduation_year INT
)
BEGIN
    INSERT INTO Users(username, password_hash, full_name, email, role, graduation_year)
    VALUES (p_username, p_password_hash, p_full_name, p_email, p_role, p_graduation_year);
END$$
DELIMITER ;


-- Procedure 2: sp_ApproveApplication
-- Approves an application. The associated trigger will handle the rest.
DELIMITER $$
CREATE PROCEDURE sp_ApproveApplication(
    IN p_application_id INT
)
BEGIN
    -- Update the application status to 'approved'
    -- This action will fire tr_AfterApplicationApproved
    UPDATE Applications
    SET status = 'approved'
    WHERE application_id = p_application_id;
END$$
DELIMITER ;


-- -----------------------------------------------------------------
-- FUNCTIONS 
-- -----------------------------------------------------------------

-- Function 1: fn_GetUserRole
-- Returns the role of a given user_id
DELIMITER $$
CREATE FUNCTION fn_GetUserRole(
    f_user_id INT
)
RETURNS VARCHAR(10)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE user_role VARCHAR(10);
    SELECT role INTO user_role FROM Users WHERE user_id = f_user_id;
    RETURN user_role;
END$$
DELIMITER ;


-- Function 2: fn_GetConnectionStatus
-- Checks the connection status between two users
DELIMITER $$
CREATE FUNCTION fn_GetConnectionStatus(
    f_user_id_1 INT,
    f_user_id_2 INT
)
RETURNS VARCHAR(10)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE conn_status VARCHAR(10);
    
    SELECT status INTO conn_status FROM Connections
    WHERE (requester_id = f_user_id_1 AND receiver_id = f_user_id_2)
       OR (requester_id = f_user_id_2 AND receiver_id = f_user_id_1);
       
    IF conn_status IS NULL THEN
        RETURN 'none';
    ELSE
        RETURN conn_status;
    END IF;
END$$
DELIMITER ;


-- -----------------------------------------------------------------
-- TRIGGERS 
-- -----------------------------------------------------------------

-- Trigger 1: tr_AfterApplicationApproved
-- After an application is set to 'approved', this trigger automatically
-- creates an entry in OngoingProjects.
DELIMITER $$
CREATE TRIGGER tr_AfterApplicationApproved
AFTER UPDATE ON Applications
FOR EACH ROW
BEGIN
    DECLARE v_faculty_user_id INT;

    -- Check if the new status is 'approved' and old was not
    IF NEW.status = 'approved' AND OLD.status <> 'approved' THEN
        
        -- Find the faculty/alumni who created the opportunity
        SELECT created_by_user_id INTO v_faculty_user_id
        FROM Opportunities
        WHERE opportunity_id = NEW.opportunity_id;
        
        -- Insert into OngoingProjects
        INSERT INTO OngoingProjects(opportunity_id, student_user_id, faculty_user_id)
        VALUES (NEW.opportunity_id, NEW.student_user_id, v_faculty_user_id);
    END IF;
END$$
DELIMITER ;


-- Trigger 2: tr_LogUserCreation
-- After a new user is inserted, log the event in the audit table.
DELIMITER $$
CREATE TRIGGER tr_LogUserCreation
AFTER INSERT ON Users
FOR EACH ROW
BEGIN
    INSERT INTO UserAuditLog(user_id, action_performed)
    VALUES (NEW.user_id, 'NEW_USER_CREATED');
END$$
DELIMITER ;

ALTER USER 'root'@'localhost' IDENTIFIED WITH 'mysql_native_password' BY '$Cakeandchips07';
ALTER USER 'root'@'localhost' IDENTIFIED WITH 'caching_sha2_password' BY '$Cakeandchips07';
FLUSH PRIVILEGES;

-- Nested Query- Finds all students who have applied for opportunities created by a specific faculty member
SELECT u.full_name, u.email
FROM Users u
WHERE u.user_id IN (
    SELECT a.student_user_id
    FROM Applications a
    WHERE a.opportunity_id IN (
        SELECT o.opportunity_id
        FROM Opportunities o
        WHERE o.created_by_user_id = 2
    )
);

-- Nested Query- View All Connections Uses a nested query with UNION to find all users you are connected with (either as sender or receiver).
SELECT u.user_id, u.full_name, u.role
FROM Users u
WHERE u.user_id IN (
    -- Users who sent me a request that I accepted
    SELECT requester_id FROM Connections WHERE receiver_id = 2 AND status = 'accepted'
    UNION
    -- Users I sent a request to that they accepted
    SELECT receiver_id FROM Connections WHERE requester_id = 2 AND status = 'accepted'
);

-- Join Query-Fetches available open opportunities and joins them with the Users table to display the name of the person who posted the opportunity.
SELECT o.opportunity_id, o.title, o.description, u.full_name AS posted_by
FROM Opportunities o
JOIN Users u ON o.created_by_user_id = u.user_id
WHERE o.status = 'open';

-- Join Query-Dashboard: Student's Ongoing Projects Fetches projects by joining the projects table with opportunities and faculty user details.
SELECT p.ongoing_project_id, o.title, u.full_name AS faculty_name
FROM OngoingProjects p
JOIN Opportunities o ON p.opportunity_id = o.opportunity_id
JOIN Users u ON p.faculty_user_id = u.user_id
WHERE p.student_user_id = 2;

-- Join Query- Dashboard: Faculty's Ongoing Projects joins to get the student's name for the faculty view
SELECT p.ongoing_project_id, o.title, u.full_name AS student_name
FROM OngoingProjects p
JOIN Opportunities o ON p.opportunity_id = o.opportunity_id
JOIN Users u ON p.student_user_id = u.user_id
WHERE p.faculty_user_id = 3;


-- Join Query- Opportunity Management: View Applicants Joins the Applications table with Users to show the names of students who applied.
SELECT a.application_id, a.status, u.full_name, u.user_id AS student_user_id
FROM Applications a
JOIN Users u ON a.student_user_id = u.user_id
WHERE a.opportunity_id =2;

-- Join Query- Connections: View Pending Requests Joins Connections with Users to show the names of people asking to connect.
SELECT u.user_id, u.full_name
FROM Connections c
JOIN Users u ON c.requester_id = u.user_id
WHERE c.receiver_id =3 AND c.status = 'pending';

-- Aggregate Query- Counts the total number of applications submitted by each student and orders them by the most active applicants.


SELECT u.full_name, COUNT(a.application_id) AS application_count
FROM Users u
JOIN Applications a ON u.user_id = a.student_user_id
GROUP BY u.user_id, u.full_name
ORDER BY application_count DESC;

-- Aggregate Query-Applicant Counts per Opportunity Counts how many applications each opportunity has received using a LEFT JOIN and GROUP BY.

SELECT o.title, o.status, COUNT(a.application_id) AS applicant_count
FROM Opportunities o
LEFT JOIN Applications a ON o.opportunity_id = a.opportunity_id
WHERE o.created_by_user_id = 3
GROUP BY o.opportunity_id, o.title, o.status;


select * from Users;
select * from Skills;
select * from Projects;
select * from Applications;
select * from Connections;
select * from Experience;
select * from Opportunities;
select * from OngoingProjects;
select * from UserAuditLog;