**Academic & Professional Network (APN)** 

The Academic & Professional Network (APN) is a web application designed to streamline academic collaboration. It allows students, faculty, and alumni to register, maintain professional profiles, post or apply for academic/research opportunities, and build connections through a structured networking system. The platform uses a MySQL database with triggers, procedures, and role-based workflows to ensure smooth interaction between all user types.

**Installation & Setup**

**1. Clone the Repository**

git clone https://github.com/tara05ma/Academic-Professional-Network

cd Academic-Professional-Network

**2. Install Dependencies**

pip install -r requirements.txt

**3. Configure MySQL**

CREATE DATABASE apn;

USE apn;

SOURCE schema.sql;

**Update DB credentials in Python:**

host="localhost"

user="root"

password="your_password"

database="apn"

**4. Run the App**

streamlit run app.py
