# 🏥 SmartClinic
 
SmartClinic is a web-based clinic management system designed to reduce waiting times in clinics by managing patient appointments and live queues efficiently.
 
---
 
## 👥 Team Members
- **Simhadri Katroth**
- **Zikra Begum**
- **John Wesly**
- **Rahul Vangala**
- **Ashish**
 
---
 
## 🎯 Project Goal
To create a simple web-based system that helps clinics manage patient appointments and live queues to reduce waiting time and improve efficiency.
 
---
 
## 🧰 Tech Stack
**Frontend:** HTML, CSS  
**Backend:** Python (Flask)  
# 🏥 SmartClinic
 
SmartClinic is a web-based clinic management system designed to reduce waiting times in clinics by managing patient appointments and live queues efficiently.
 
---
 
## 👥 Team Members
- **Simhadri Katroth**
- **Zikra Begum**
- **John Wesly**
- **Rahul Vangala**
- **Ashish**
 
---
 
## 🎯 Project Goal
To create a simple web-based system that helps clinics manage patient appointments and live queues to reduce waiting time and improve efficiency.
 
---
 
## 🧰 Tech Stack
**Frontend:** HTML, CSS  
**Backend:** Python (Flask)  
**Database:** SQLite  
**Version Control:** Git & GitHub  
**Editor:** Visual Studio Code
 
---
 
## ⚙️ Setup Instructions

### Prerequisites
- **Python 3.x** installed on your system.
- **Internet Connection** (required for loading fonts and icons via CDN).

### Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/SIMHADRI-1817/smart--clinic
   cd smart--clinic
   ```

2. **Create a virtual environment (Optional but recommended):**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the Database:**
   Run the initialization script to create the database and default users.
   ```bash
   python init_db.py
   ```

5. **Run the Application:**
   ```bash
   python app.py
   ```

6. **Access the App:**
   Open your browser and go to: `http://127.0.0.1:5000`

---

## 🔐 Default Credentials
Use these accounts to test different roles:

| Role | Username | Password |
|------|----------|----------|
| **Admin** | `admin` | `admin123` |
| **Reception** | `reception` | `reception123` |
| **Doctor** | `dr_ashish` | `12345` |

> **Note:** You can register new patient accounts directly from the login page.